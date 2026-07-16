"""Тесты предотправочного гейта модерации в RuleDispatcher._route (integration.py).

Стоп-словарь и ИИ подменяются заглушками — проверяем именно логику гейта/режимов.
Запуск:  .venv/bin/python -m pytest tests/test_moderation_gate.py -q
"""
import asyncio
import os
import sys
import tempfile
import time
from pathlib import Path

_TMP = Path(tempfile.mkdtemp(prefix="gate_test_"))
os.environ.setdefault("MESYNC_DATA_DIR", str(_TMP / "control"))
os.environ.setdefault("MESYNC_SESSION_SECRET", "test-secret")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "111:T")
os.environ.setdefault("MAX_BOT_TOKEN", "m")

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from unittest.mock import AsyncMock  # noqa: E402

from control import config  # noqa: E402
from control.integration import RuleDispatcher  # noqa: E402
from control.message_map import MessageMap  # noqa: E402
from control.moderation import Verdict, VERDICT_OK, VERDICT_VIOLATION, VERDICT_UNSURE  # noqa: E402
from control.settings import Settings  # noqa: E402
from control.store import ControlStore  # noqa: E402

run = asyncio.run


class FakeTg:
    def __init__(self):
        self.sent = []

    async def send_message(self, chat_id, text, parse_mode=None, message_thread_id=None,
                           reply_markup=None, **kw):
        self.sent.append({"chat_id": chat_id, "text": text})


class StubStop:
    def __init__(self, hits):
        self._hits = set(hits)
        self.calls = 0

    def match(self, text):
        self.calls += 1
        return set(self._hits)


class StubAI:
    def __init__(self, verdict, *, enabled=True, raises=False):
        self._verdict = verdict
        self.enabled = enabled
        self._raises = raises
        self.calls = 0

    async def classify(self, text, *, context=""):
        self.calls += 1
        if self._raises:
            raise RuntimeError("ai boom")
        return self._verdict


class SvcLog:
    def __init__(self):
        self.reports = []

    async def report(self, title, lines, quote=None, error=None):
        self.reports.append({"title": title, "lines": lines, "quote": quote})


def _store_rule():
    p = _TMP / f"store_{time.time_ns()}.json"
    s = ControlStore(p)
    acc = run(s.get_or_create_account("max", 1, None))["id"]
    run(s.set_subscription(acc, {"status": "active"}))
    run(s.add_rule({"account_id": acc, "a": {"messenger": "max", "chat_id": "100"},
                    "b": {"messenger": "tg", "chat_id": "200"}, "dir": "both", "status": "active"}))
    return s, acc


def _msg(text):
    return {"chat_id": "100", "sender_id": None, "message_id": None, "mid": "m1",
            "is_group": True, "thread_id": None, "sender_name": "Иван",
            "forward_from": None, "text": text, "entities": [], "media": [], "url": None}


def _dispatcher(hits, verdict, *, mode, enabled=True, raises=False, settings=None):
    s, acc = _store_rule()
    ft = FakeTg()
    d = RuleDispatcher(s, tg_client=ft, settings=settings)
    d._stoplist = StubStop(hits)
    d._moderation = StubAI(verdict, enabled=enabled, raises=raises)
    d.service_log = SvcLog()
    blocks = []

    async def block_cb(messenger, chat_id, account_ids, category, reason):
        blocks.append({"messenger": messenger, "chat_id": chat_id,
                       "account_ids": account_ids, "category": category, "reason": reason})

    d.moderation_block_cb = block_cb
    config.MODERATION_GATE_MODE = mode
    return d, ft, blocks, acc


_VIOLATION = Verdict(VERDICT_VIOLATION, category="drugs", confidence=0.9, reason="сбыт")
_OK = Verdict(VERDICT_OK, reason="норма")
_UNSURE = Verdict(VERDICT_UNSURE, reason="не ясно")


def teardown_function(_):
    config.MODERATION_GATE_MODE = "off"


# ---------------- режим off ----------------

def test_mode_off_delivers_without_checking():
    d, ft, blocks, _ = _dispatcher({"drugs"}, _VIOLATION, mode="off")
    run(d.on_max_message(_msg("продам мефедрон")))
    assert len(ft.sent) == 1                 # доставлено
    assert d._stoplist.calls == 0            # словарь даже не смотрели
    assert d._moderation.calls == 0
    assert blocks == []


# ---------------- enforce ----------------

def test_enforce_blocks_violation():
    d, ft, blocks, acc = _dispatcher({"drugs"}, _VIOLATION, mode="enforce")
    run(d.on_max_message(_msg("продам мефедрон")))
    assert ft.sent == []                     # НЕ доставлено
    assert d._moderation.calls == 1
    assert len(blocks) == 1                  # владелец уведомлён
    assert blocks[0]["category"] == "drugs"
    assert blocks[0]["account_ids"] == [acc]
    assert len(d.service_log.reports) == 1   # отчёт оператору


def test_enforce_delivers_when_ai_says_ok():
    d, ft, blocks, _ = _dispatcher({"drugs"}, _OK, mode="enforce")
    run(d.on_max_message(_msg("новость про наркотики в стране")))
    assert len(ft.sent) == 1                 # ИИ снял подозрение → доставлено
    assert d._moderation.calls == 1
    assert blocks == []


def test_enforce_delivers_on_unsure():
    d, ft, blocks, _ = _dispatcher({"drugs"}, _UNSURE, mode="enforce")
    run(d.on_max_message(_msg("что-то непонятное")))
    assert len(ft.sent) == 1                 # unsure → fail-open доставка
    assert blocks == []


def test_no_stopword_hit_skips_ai_and_delivers():
    d, ft, blocks, _ = _dispatcher(set(), _VIOLATION, mode="enforce")
    run(d.on_max_message(_msg("обычное сообщение")))
    assert len(ft.sent) == 1
    assert d._moderation.calls == 0          # чистое → ИИ не звали (бережём квоту)
    assert blocks == []


def test_profanity_only_hit_does_not_escalate():
    d, ft, blocks, _ = _dispatcher({"profanity"}, _VIOLATION, mode="enforce")
    run(d.on_max_message(_msg("грубый текст с матом")))
    assert len(ft.sent) == 1                 # мат не эскалирует и не блокирует
    assert d._moderation.calls == 0
    assert blocks == []


def test_profanity_plus_heavy_still_checks():
    d, ft, blocks, _ = _dispatcher({"profanity", "drugs"}, _VIOLATION, mode="enforce")
    run(d.on_max_message(_msg("мат и продажа")))
    assert ft.sent == []                     # тяжёлая категория осталась → блок
    assert d._moderation.calls == 1


# ---------------- shadow ----------------

def test_shadow_delivers_but_reports():
    d, ft, blocks, _ = _dispatcher({"drugs"}, _VIOLATION, mode="shadow")
    run(d.on_max_message(_msg("продам мефедрон")))
    assert len(ft.sent) == 1                 # shadow: доставлено несмотря на нарушение
    assert d._moderation.calls == 1
    assert len(d.service_log.reports) == 1   # но оператору отчёт есть
    assert blocks == []                      # владельца НЕ беспокоим (доставлено же)


# ---------------- fail-open ----------------

def test_ai_error_fails_open():
    d, ft, blocks, _ = _dispatcher({"drugs"}, _VIOLATION, mode="enforce", raises=True)
    run(d.on_max_message(_msg("продам мефедрон")))
    assert len(ft.sent) == 1                 # ИИ упал → доставляем (не роняем пересылку)
    assert blocks == []


def test_ai_disabled_fails_open():
    d, ft, blocks, _ = _dispatcher({"drugs"}, _VIOLATION, mode="enforce", enabled=False)
    run(d.on_max_message(_msg("продам мефедрон")))
    assert len(ft.sent) == 1                 # без ключа ИИ предфильтр не блокирует
    assert d._moderation.calls == 0
    assert blocks == []


def test_ai_disabled_by_runtime_setting_fails_open():
    s = ControlStore(_TMP / f"settings_{time.time_ns()}.json")
    settings = Settings(s)
    run(settings.set("moderation_ai_enabled", False))
    d, ft, blocks, _ = _dispatcher(
        {"drugs"}, _VIOLATION, mode="enforce", enabled=True, settings=settings)
    run(d.on_max_message(_msg("продам мефедрон")))
    assert len(ft.sent) == 1
    assert d._moderation.calls == 0
    assert blocks == []


def test_empty_text_skips_gate():
    d, ft, blocks, _ = _dispatcher({"drugs"}, _VIOLATION, mode="enforce")
    run(d.on_max_message(_msg("   ")))
    assert d._stoplist.calls == 0            # пустой текст — гейт не работает
    # доставка пустого текста — уже забота _deliver; гейт её не трогает


# ---------------- enforce на РЕДАКТИРОВАНИИ (находка ревью #1) ----------------

def _edit_dispatcher(hits, verdict, *, mode):
    """Диспетчер с message_map и записанным маппингом tg:100:m1 → tg:200:t1;
    _edit_tg подменён шпионом (тестируем через on_tg_edit — читает norm напрямую)."""
    s, acc = _store_rule_tg()
    mm = MessageMap(_TMP / f"mm_{time.time_ns()}.json")
    mm.record("tg", "100", "m1", "tg", "200", "t1")
    d = RuleDispatcher(s, tg_client=FakeTg(), message_map=mm)
    d._stoplist = StubStop(hits)
    d._moderation = StubAI(verdict)
    d.service_log = SvcLog()
    d.moderation_block_cb = AsyncMock()
    d._edit_tg = AsyncMock()
    config.MODERATION_GATE_MODE = mode
    return d


def _store_rule_tg():
    p = _TMP / f"store_{time.time_ns()}.json"
    s = ControlStore(p)
    acc = run(s.get_or_create_account("tg", 1, None))["id"]
    run(s.set_subscription(acc, {"status": "active"}))
    run(s.add_rule({"account_id": acc, "a": {"messenger": "tg", "chat_id": "100"},
                    "b": {"messenger": "tg", "chat_id": "200"}, "dir": "both", "status": "active"}))
    return s, acc


def _edit_norm(text):
    return {"chat": {"id": "100"}, "message_id": "m1", "text": text, "entities": []}


def test_enforce_blocks_prohibited_edit():
    d = _edit_dispatcher({"drugs"}, _VIOLATION, mode="enforce")
    run(d.on_tg_edit(_edit_norm("теперь продам мефедрон")))
    d._edit_tg.assert_not_awaited()          # запрещённая правка НЕ пропагирована
    assert len(d.service_log.reports) == 1


def test_shadow_propagates_edit_but_reports():
    d = _edit_dispatcher({"drugs"}, _VIOLATION, mode="shadow")
    run(d.on_tg_edit(_edit_norm("теперь продам мефедрон")))
    d._edit_tg.assert_awaited()              # shadow: правка доставлена
    assert len(d.service_log.reports) == 1   # но залогирована


def test_clean_edit_propagates_without_block():
    d = _edit_dispatcher(set(), _VIOLATION, mode="enforce")
    run(d.on_tg_edit(_edit_norm("обычная правка текста")))
    d._edit_tg.assert_awaited()              # нет стоп-хита → правка идёт как обычно
    assert d._moderation.calls == 0
