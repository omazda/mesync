"""Тесты жалоб на пересланный контент (модерация, этап 3): токен, стор, приём и воркер.

Реальные ControlStore/MessageMap; ИИ и I/O (перечитывание текста, скрытие копий,
уведомление) — фейками. Сценарии Reports гоняем в ОДНОМ event loop (общая asyncio.Queue).
Запуск:  .venv/bin/python -m pytest tests/test_reports.py -q
"""
import asyncio
import json
import os
import re
import sys
import tempfile
import time
from pathlib import Path

_TMP = Path(tempfile.mkdtemp(prefix="reports_test_"))
os.environ.setdefault("MESYNC_DATA_DIR", str(_TMP / "control"))
os.environ.setdefault("MESYNC_SESSION_SECRET", "test-secret")
os.environ.setdefault("MESYNC_AUTH_INSECURE", "1")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "111:T")
os.environ.setdefault("MAX_BOT_TOKEN", "m")
os.environ.setdefault("MESYNC_TG_BOT_URL", "https://t.me/test_mesync_bot")
os.environ.setdefault("MESYNC_MAX_BOT_URL", "https://max.ru/test_mesync_bot")

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from control import config  # noqa: E402
from control.content_lookup import lookup_tg_content_text_sync  # noqa: E402
from control.message_map import MessageMap  # noqa: E402
from control.moderation import (  # noqa: E402
    Verdict, VERDICT_OK, VERDICT_VIOLATION, VERDICT_UNSURE, VERDICT_UNAVAILABLE)
from control.reports import (  # noqa: E402
    Reports, ReportError, make_report_token, parse_report_token, report_deeplink)
from control.store import ControlStore  # noqa: E402

run = asyncio.run

_VIOLATION = Verdict(VERDICT_VIOLATION, category="drugs", confidence=0.9, reason="сбыт")
_OK = Verdict(VERDICT_OK, reason="норма")
_UNSURE = Verdict(VERDICT_UNSURE, category="other", confidence=0.4, reason="завуалировано")
_QUOTA = Verdict(VERDICT_UNAVAILABLE, quota_exhausted=True)


def teardown_function(_):
    # Не оставляем глобальные флаги модерации включёнными для соседних тестов.
    config.MODERATION_REPORTS_ENABLED = False
    config.MODERATION_GATE_MODE = "off"


# ------------------------- фейки -------------------------
class FakeAI:
    def __init__(self, verdict, enabled=True):
        self._verdict = verdict
        self.enabled = enabled
        self.calls = 0

    async def classify(self, text, *, context=""):
        self.calls += 1
        return self._verdict


class SvcLog:
    enabled = True

    def __init__(self):
        self.reports = []

    async def report(self, title, lines, quote=None, error=None):
        self.reports.append({"title": title, "lines": lines, "quote": quote})


class FetchText:
    def __init__(self, mapping=None):
        self.map = mapping or {}
        self.calls = []

    async def __call__(self, messenger, chat_id, mid):
        self.calls.append((messenger, str(chat_id), str(mid)))
        return self.map.get((messenger, str(chat_id), str(mid)))


class DeleteCopy:
    def __init__(self, ok=True):
        self.calls = []
        self.ok = ok

    async def __call__(self, messenger, chat_id, mid):
        self.calls.append((messenger, str(chat_id), str(mid)))
        return self.ok


class Notify:
    def __init__(self):
        self.calls = []

    async def __call__(self, account_id, category, reason):
        self.calls.append((account_id, category, reason))


# ------------------------- хелперы -------------------------
def _store():
    s = ControlStore(_TMP / f"store_{time.time_ns()}.json")
    acc = run(s.get_or_create_account("max", 1, None))["id"]
    rule = run(s.add_rule({"account_id": acc, "a": {"messenger": "tg", "chat_id": "100"},
                           "b": {"messenger": "max", "chat_id": "200"},
                           "dir": "both", "status": "active"}))
    return s, acc, rule["id"]


def _reports(s, *, verdict=None, ai_enabled=True, fetch_map=None, mm=None,
             delete_ok=True, cooldown=0.0, report_max=3, report_window=600, clock=None,
             chat_member_ok=None, source_admin_ok=None, settings=None):
    ai = FakeAI(verdict, enabled=ai_enabled) if verdict is not None else None
    svc, ft, dc, no = SvcLog(), FetchText(fetch_map), DeleteCopy(delete_ok), Notify()
    r = Reports(s, moderation=ai, message_map=mm, fetch_text=ft, delete_copy=dc,
                notify_owner=no, chat_member_ok=chat_member_ok, service_log=svc,
                source_admin_ok=source_admin_ok,
                settings=settings,
                clock=clock or time.time, report_max=report_max,
                report_window=report_window, quota_cooldown=cooldown)
    return r, ai, svc, ft, dc, no


def test_tg_content_lookup_matches_album_message_ids_and_textless_album():
    path = _TMP / f"content_{time.time_ns()}.jsonl"
    rows = [
        {"chat": {"id": 100}, "message_ids": [101, 102], "caption": None,
         "parts": [{"message_id": 101, "caption": "подпись альбома"},
                   {"message_id": 102, "caption": "вторая подпись"}]},
        {"chat": {"id": 100}, "message_ids": [201, 202],
         "parts": [{"message_id": 201}, {"message_id": 202}]},
    ]
    path.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n",
                    encoding="utf-8")

    assert lookup_tg_content_text_sync(path, 100, 101) == "подпись альбома\n\nвторая подпись"
    assert lookup_tg_content_text_sync(path, 100, 102) == "вторая подпись\n\nподпись альбома"
    assert lookup_tg_content_text_sync(path, 100, 201) == ""
    assert lookup_tg_content_text_sync(path, 100, 999) is None


# ========================= токен =========================
def test_token_roundtrip_and_prefix():
    tok = make_report_token("tg", -1001234567890, 42, "rule_abc")
    assert parse_report_token(tok) == {
        "messenger": "tg", "chat_id": "-1001234567890", "mid": "42", "rule_id": "rule_abc"}
    assert parse_report_token("r_" + tok) == parse_report_token(tok)  # префикс диплинка
    # MAX mid вида mid.<hash> и пустой rule
    tok2 = make_report_token("max", 987, "mid.0aZ-_x", None)
    assert parse_report_token(tok2) == {
        "messenger": "max", "chat_id": "987", "mid": "mid.0aZ-_x", "rule_id": None}


def test_token_with_copy_location_roundtrip():
    tok = make_report_token(
        "tg", -1001234567890, 42, "rule_abc",
        copy_messenger="max", copy_chat_id=-500, copy_mid="mid.copy_1", copy_thread_id=12)
    assert parse_report_token("r_" + tok) == {
        "messenger": "tg", "chat_id": "-1001234567890", "mid": "42",
        "rule_id": "rule_abc",
        "copy_messenger": "max", "copy_chat": "-500", "copy_mid": "mid.copy_1",
        "copy_thread": "12"}


def test_token_with_multi_copy_location_roundtrip():
    mids = [
        "mid.ffffbae648af5fc3019f1e13d3730c46",
        "mid.ffffbae648af5fc3019f1e13ebbd1e02",
        "mid.ffffbae648af5fc3019f1e1400aa1b9",
    ]
    tok = make_report_token(
        "tg", -1001234567890, 42, "rule_abc",
        copy_messenger="max", copy_chat_id=-500, copy_mid=mids[0],
        copy_mids=mids, copy_thread_id=12)
    assert parse_report_token("r_" + tok) == {
        "messenger": "tg", "chat_id": "-1001234567890", "mid": "42",
        "rule_id": "rule_abc",
        "copy_messenger": "max", "copy_chat": "-500", "copy_mid": mids[0],
        "copy_mids": mids,
        "copy_thread": "12"}


def test_token_with_media_flag_roundtrip():
    tok = make_report_token(
        "tg", -1001234567890, 42, "rule_abc",
        copy_messenger="tg", copy_chat_id=-500, copy_mid=1001,
        copy_mids=[1001, 1002], copy_thread_id=12, has_media=True)
    assert parse_report_token("r_" + tok) == {
        "messenger": "tg", "chat_id": "-1001234567890", "mid": "42",
        "rule_id": "rule_abc",
        "copy_messenger": "tg", "copy_chat": "-500", "copy_mid": "1001",
        "copy_mids": ["1001", "1002"],
        "copy_thread": "12",
        "has_media": True}


def test_token_tamper_rejected():
    tok = make_report_token("tg", 100, 5, "rule_x")
    assert parse_report_token(tok[:-1] + ("A" if tok[-1] != "A" else "B")) is None  # подпись
    assert parse_report_token(tok[:3] + ("Z" if tok[3] != "Z" else "Y") + tok[4:]) is None  # тело
    assert parse_report_token("garbage") is None
    assert parse_report_token("") is None
    assert parse_report_token(None) is None


def test_deeplink_charset():
    tok = make_report_token("max", 1, "mid.x", "rule_y")
    for m, host in (("tg", "t.me/test_mesync_bot"), ("max", "max.ru/test_mesync_bot")):
        dl = report_deeplink(m, tok)
        assert host in dl
        sp = dl.split("startapp=")[1]
        assert re.fullmatch(r"[A-Za-z0-9_-]+", sp), f"недопустимые символы startapp: {sp}"


# ========================= стор =========================
def test_store_report_lifecycle():
    s, acc, _ = _store()
    rec = run(s.add_report({"src_key": "tg:100:m1", "account_id": acc, "status": "queued"}))
    rid = rec["id"]
    assert rec["status"] == "queued" and rec["repeat_count"] == 0
    assert rid in s.queued_report_ids()
    run(s.update_report(rid, {"status": "done", "verdict": "violation", "text_hash": "h1"}))
    assert rid not in s.queued_report_ids()
    found = s.find_processed_report("tg:100:m1", "h1")
    assert found and found["id"] == rid
    assert s.find_processed_report("tg:100:m1", "OTHER") is None   # другой hash — не матч
    assert run(s.bump_report_repeat(rid)) == 1
    assert run(s.bump_report_repeat(rid)) == 2
    assert len(s.reports_since(acc, 0, verdict="violation")) == 1


# ========================= приём (submit) =========================
# Стор/Reports строим СИНХРОННО (внутри своих run()) ДО входа в scenario — вложенный
# asyncio.run внутри работающего loop недопустим; в scenario только await submit/_process.
def test_submit_records_and_enqueues():
    s, acc, rule_id = _store()
    r, *_ = _reports(s, verdict=_OK)
    tok = make_report_token("tg", 100, "m1", rule_id)

    async def scenario():
        return await r.submit(tok, "спам", reporter="max:u9")
    res = run(scenario())
    rec = s.report(res["id"])
    assert rec["account_id"] == acc              # выведен из rule_id токена
    assert rec["src_key"] == "tg:100:m1"
    assert rec["reporter"] == "max:u9"
    assert rec["status"] == "queued"
    assert r._queue.qsize() == 1


def test_submit_records_encoded_copy_location():
    s, _, rule_id = _store()
    r, *_ = _reports(s, verdict=_OK)
    tok = make_report_token("tg", 100, "m1", rule_id,
                            copy_messenger="max", copy_chat_id=200, copy_mid="c1")

    async def scenario():
        return await r.submit(tok, "", reporter="max:u9")
    res = run(scenario())
    rec = s.report(res["id"])
    assert rec["src_key"] == "tg:100:m1"
    assert rec["copy_messenger"] == "max"
    assert rec["copy_chat"] == "200"
    assert rec["copy_mid"] == "c1"


def test_report_check_blocks_when_tg_copy_chat_not_served():
    s, _, rule_id = _store()
    calls = []
    async def chat_ok(messenger, chat_id):
        calls.append((messenger, str(chat_id)))
        return False
    r, *_ = _reports(s, verdict=_OK, chat_member_ok=chat_ok)
    tok = make_report_token("max", 500, "mid.src", rule_id,
                            copy_messenger="tg", copy_chat_id=600, copy_mid=777)

    async def scenario():
        out = []
        for call in (lambda: r.check(tok), lambda: r.submit(tok, "", reporter="tg:u")):
            try:
                await call()
                out.append(None)
            except ReportError as e:
                out.append(e)
        return out
    e_check, e_submit = run(scenario())
    assert calls == [("tg", "600"), ("tg", "600")]
    assert e_check.status == 410 and e_check.code == "bot_not_in_chat"
    assert e_submit.status == 410 and e_submit.code == "bot_not_in_chat"
    assert s.reports_page()["total"] == 0


def test_report_check_allows_old_max_source_only_token_without_target_chat():
    s, _, rule_id = _store()
    calls = []
    async def chat_ok(messenger, chat_id):
        calls.append((messenger, str(chat_id)))
        return False
    r, *_ = _reports(s, verdict=_OK, chat_member_ok=chat_ok)
    tok = make_report_token("max", 500, "mid.src", rule_id)

    async def scenario():
        return await r.check(tok)
    assert run(scenario()) == {"ok": True}
    assert calls == []


def test_submit_bad_token_400():
    s, *_ = _store()
    r, *_ = _reports(s, verdict=_OK)

    async def scenario():
        try:
            await r.submit("not-a-token", "x", reporter="tg:1")
            return None
        except ReportError as e:
            return e
    e = run(scenario())
    assert e is not None and e.status == 400 and e.code == "bad_token"


def test_submit_antispam_429():
    s, _, rule_id = _store()
    r, *_ = _reports(s, verdict=_OK, report_max=2)
    tok = make_report_token("tg", 100, "m1", rule_id)

    async def scenario():
        await r.submit(tok, "1", reporter="tg:spam")
        await r.submit(tok, "2", reporter="tg:spam")
        try:
            await r.submit(tok, "3", reporter="tg:spam")
            return None
        except ReportError as e:
            await r.submit(tok, "1", reporter="tg:other")   # другой жалобщик — не затронут
            return e
    e = run(scenario())
    assert e is not None and e.status == 429 and e.code == "too_many_reports"


# ========================= воркер (_process) =========================
def _run_report(r, token, *, reporter="max:u1", desc=""):
    async def scenario():
        res = await r.submit(token, desc, reporter=reporter)
        await r._process(res["id"])
        return res
    return run(scenario())


def test_hide_copy_callback_preferred_over_legacy_delete_copy():
    s, _, _ = _store()
    calls = []
    mm = MessageMap(_TMP / f"mm_{time.time_ns()}.json")
    mm.record("tg", "100", "m1", "max", "200", "c1")

    async def legacy_delete(messenger, chat_id, mid):
        calls.append(("delete", messenger, str(chat_id), str(mid)))
        return True

    async def hide(messenger, chat_id, mid):
        calls.append(("hide", messenger, str(chat_id), str(mid)))
        return True

    r = Reports(s, message_map=mm, delete_copy=legacy_delete, hide_copy=hide)
    n = run(r._hide_all_copies({"src_messenger": "tg", "src_chat": "100", "src_mid": "m1"}))

    assert n == 1
    assert calls == [("hide", "max", "200", "c1")]


def test_violation_hides_notifies_cards():
    s, acc, rule_id = _store()
    mm = MessageMap(_TMP / f"mm_{time.time_ns()}.json")
    mm.record("tg", "100", "m1", "max", "200", "c1")         # источник TG → копия MAX
    r, ai, svc, ft, dc, no = _reports(
        s, verdict=_VIOLATION, mm=mm, fetch_map={("max", "200", "c1"): "продам мефедрон"})
    res = _run_report(r, make_report_token("tg", 100, "m1", rule_id), desc="наркотики")
    assert ai.calls == 1
    assert ft.calls == [("max", "200", "c1")]                # текст перечитан со стороны MAX
    assert dc.calls == [("max", "200", "c1")]                # копия скрыта
    assert no.calls and no.calls[0] == (acc, "drugs", "сбыт")
    assert len(svc.reports) == 1
    assert "Скрыто копий: 1" in "\n".join(svc.reports[0]["lines"])
    rec = s.report(res["id"])
    assert rec["status"] == "done" and rec["verdict"] == "violation"
    assert rec["category"] == "drugs" and rec["text_hash"]


def test_source_admin_report_auto_blocks_without_ai_review():
    s, acc, rule_id = _store()
    mm = MessageMap(_TMP / f"mm_{time.time_ns()}.json")
    mm.record("tg", "100", "m1", "max", "200", "c1")
    admin_checks = []

    async def source_admin_ok(messenger, chat_id, user_id):
        admin_checks.append((messenger, str(chat_id), str(user_id)))
        return True

    r, ai, svc, ft, dc, no = _reports(
        s, verdict=_OK, mm=mm, fetch_map={("max", "200", "c1"): "обычный текст"},
        source_admin_ok=source_admin_ok)
    res = _run_report(r, make_report_token("tg", 100, "m1", rule_id),
                      reporter="tg:42", desc="удалить")

    assert admin_checks == [("tg", "100", "42")]
    assert ai.calls == 0                                      # без ИИ/очереди рассмотрения
    assert ft.calls == []                                     # текст не нужен для auto-block
    assert dc.calls == [("max", "200", "c1")]
    assert no.calls and no.calls[0] == (
        acc, "source_admin", "жалоба администратора источника: сообщение скрыто без ИИ-проверки")
    rec = s.report(res["id"])
    assert rec["status"] == "done" and rec["verdict"] == "violation"
    assert rec["category"] == "source_admin"
    assert rec["source_admin_report"] is True and rec["reviewed"] is True
    assert "text_hash" not in rec
    assert "Причина: жалоба администратора источника" in "\n".join(svc.reports[-1]["lines"])


def test_source_admin_report_requires_same_messenger_identity():
    s, _, rule_id = _store()
    mm = MessageMap(_TMP / f"mm_{time.time_ns()}.json")
    mm.record("tg", "100", "m1", "max", "200", "c1")
    admin_checks = []

    async def source_admin_ok(messenger, chat_id, user_id):
        admin_checks.append((messenger, chat_id, user_id))
        return True

    r, ai, _svc, ft, dc, _no = _reports(
        s, verdict=_OK, mm=mm, fetch_map={("max", "200", "c1"): "обычный текст"},
        source_admin_ok=source_admin_ok)
    res = _run_report(r, make_report_token("tg", 100, "m1", rule_id), reporter="max:42")

    assert admin_checks == []                    # MAX user_id не доказывает админство TG-источника
    assert ai.calls == 1
    assert ft.calls == [("max", "200", "c1")]
    assert dc.calls == []
    assert s.report(res["id"])["verdict"] == "ok"


def test_ok_no_hide_but_card():
    s, _, rule_id = _store()
    mm = MessageMap(_TMP / f"mm_{time.time_ns()}.json")
    mm.record("tg", "100", "m1", "max", "200", "c1")
    r, ai, svc, ft, dc, no = _reports(
        s, verdict=_OK, mm=mm, fetch_map={("max", "200", "c1"): "новость"})
    res = _run_report(r, make_report_token("tg", 100, "m1", rule_id))
    assert ai.calls == 1 and dc.calls == [] and no.calls == []
    assert len(svc.reports) == 1                             # карточка есть даже при ok
    assert s.report(res["id"])["verdict"] == "ok"


def test_unavailable_when_no_text():
    s, _, rule_id = _store()
    mm = MessageMap(_TMP / f"mm_{time.time_ns()}.json")      # маппинга нет → нет MAX-стороны
    r, ai, svc, ft, dc, no = _reports(s, verdict=_VIOLATION, mm=mm, fetch_map={})
    res = _run_report(r, make_report_token("tg", 100, "m1", rule_id))
    assert ai.calls == 0 and dc.calls == []                  # без текста ИИ не звали
    assert s.report(res["id"])["verdict"] == "unavailable"
    assert len(svc.reports) == 1


def test_tg_only_report_uses_message_map_text_snapshot():
    s, _, rule_id = _store()
    mm = MessageMap(_TMP / f"mm_{time.time_ns()}.json")
    mm.record("tg", "100", "m1", "tg", "100", "m2", text="продам мефедрон")
    r, ai, svc, ft, dc, no = _reports(s, verdict=_VIOLATION, mm=mm, fetch_map={})
    tok = make_report_token("tg", 100, "m1", rule_id,
                            copy_messenger="tg", copy_chat_id=100, copy_mid="m2")
    res = _run_report(r, tok)
    assert ft.calls == []                                    # Telegram не перечитываем по id
    assert ai.calls == 1
    assert dc.calls == [("tg", "100", "m2")]
    assert s.report(res["id"])["verdict"] == "violation"
    assert svc.reports[-1]["quote"] == "продам мефедрон"


def test_tg_only_report_uses_local_fetch_when_snapshot_missing():
    s, _, rule_id = _store()
    mm = MessageMap(_TMP / f"mm_{time.time_ns()}.json")
    mm.record("tg", "100", "m1", "tg", "100", "m2")        # старый mapping без text
    r, ai, svc, ft, dc, no = _reports(
        s, verdict=_VIOLATION, mm=mm, fetch_map={("tg", "100", "m1"): "продам пистолет"})
    tok = make_report_token("tg", 100, "m1", rule_id,
                            copy_messenger="tg", copy_chat_id=100, copy_mid="m2")
    _run_report(r, tok)
    assert ft.calls == [("tg", "100", "m1")]
    assert ai.calls == 1
    assert dc.calls == [("tg", "100", "m2")]
    assert svc.reports[-1]["quote"] == "продам пистолет"


def test_report_aggregates_split_max_copy_parts():
    s, _, rule_id = _store()
    mm = MessageMap(_TMP / f"mm_{time.time_ns()}.json")
    mm.record("tg", "100", "m1", "max", "200", "c_media")
    mm.record("tg", "100", "m1", "max", "200", "c_text_1")
    mm.record("tg", "100", "m1", "max", "200", "c_text_2")
    r, ai, svc, ft, dc, no = _reports(
        s, verdict=_OK, mm=mm,
        fetch_map={
            ("max", "200", "c_media"): "",
            ("max", "200", "c_text_1"): "первая часть",
            ("max", "200", "c_text_2"): "вторая часть",
        })
    tok = make_report_token("tg", 100, "m1", rule_id,
                            copy_messenger="max", copy_chat_id=200, copy_mid="c_text_2")
    _run_report(r, tok)
    assert ft.calls == [
        ("max", "200", "c_media"),
        ("max", "200", "c_text_1"),
        ("max", "200", "c_text_2"),
    ]
    assert ai.calls == 1
    assert svc.reports[-1]["quote"] == "первая часть\n\nвторая часть"


def test_tg_only_report_known_textless_message_requires_manual_review():
    s, _, rule_id = _store()
    mm = MessageMap(_TMP / f"mm_{time.time_ns()}.json")
    mm.record("tg", "100", "m1", "tg", "100", "m2")        # старый mapping без text
    r, ai, svc, ft, dc, no = _reports(
        s, verdict=_VIOLATION, mm=mm, fetch_map={("tg", "100", "m1"): ""})
    tok = make_report_token("tg", 100, "m1", rule_id,
                            copy_messenger="tg", copy_chat_id=100, copy_mid="m2")
    res = _run_report(r, tok)
    rec = s.report(res["id"])

    assert ft.calls == [("tg", "100", "m1")]
    assert ai.calls == 0 and dc.calls == []
    assert rec["verdict"] == "unsure"
    assert rec["review_required"] is True and rec["has_media"] is True
    assert "нет текста" in rec["reason"]
    assert "Ручная проверка" in "\n".join(svc.reports[-1]["lines"])


def test_encoded_max_copy_used_when_message_map_lost():
    s, _, rule_id = _store()
    r, ai, svc, ft, dc, no = _reports(
        s, verdict=_OK, mm=MessageMap(_TMP / f"mm_{time.time_ns()}.json"),
        fetch_map={("max", "200", "c1"): "текст из копии"})
    tok = make_report_token("tg", 100, "m1", rule_id,
                            copy_messenger="max", copy_chat_id=200, copy_mid="c1")
    res = _run_report(r, tok)
    assert ft.calls == [("max", "200", "c1")]
    assert ai.calls == 1
    assert s.report(res["id"])["verdict"] == "ok"


def test_hide_falls_back_to_encoded_copy_when_message_map_lost():
    s, _, rule_id = _store()
    r, ai, svc, ft, dc, no = _reports(
        s, verdict=_VIOLATION, mm=MessageMap(_TMP / f"mm_{time.time_ns()}.json"),
        fetch_map={("max", "200", "c1"): "продам мефедрон"})
    tok = make_report_token("tg", 100, "m1", rule_id,
                            copy_messenger="max", copy_chat_id=200, copy_mid="c1")
    _run_report(r, tok)
    assert dc.calls == [("max", "200", "c1")]


def test_encoded_multi_max_copies_used_when_message_map_lost():
    s, _, rule_id = _store()
    r, ai, svc, ft, dc, no = _reports(
        s, verdict=_VIOLATION, mm=MessageMap(_TMP / f"mm_{time.time_ns()}.json"),
        fetch_map={
            ("max", "200", "c_media"): "",
            ("max", "200", "c_text_1"): "первая часть",
            ("max", "200", "c_text_2"): "вторая часть",
        })
    tok = make_report_token(
        "tg", 100, "m1", rule_id,
        copy_messenger="max", copy_chat_id=200, copy_mid="c_text_2",
        copy_mids=["c_media", "c_text_1", "c_text_2"])
    _run_report(r, tok)
    assert ft.calls == [
        ("max", "200", "c_text_2"),
        ("max", "200", "c_media"),
        ("max", "200", "c_text_1"),
    ]
    assert ai.calls == 1
    assert svc.reports[-1]["quote"] == "вторая часть\n\nпервая часть"
    assert dc.calls == [
        ("max", "200", "c_text_2"),
        ("max", "200", "c_media"),
        ("max", "200", "c_text_1"),
    ]


def test_media_report_ok_requires_manual_review():
    s, _, rule_id = _store()
    r, ai, svc, ft, dc, no = _reports(
        s, verdict=_OK, fetch_map={("max", "300", "s1"): "обычный текст"})
    tok = make_report_token("max", 300, "s1", rule_id, has_media=True)
    res = _run_report(r, tok)
    rec = s.report(res["id"])

    assert ai.calls == 1 and dc.calls == []
    assert rec["verdict"] == "unsure"
    assert rec["review_required"] is True and rec["has_media"] is True
    assert "медиа" in rec["reason"].lower()
    assert "Ручная проверка" in "\n".join(svc.reports[-1]["lines"])


def test_unsure_verdict_requires_manual_review():
    s, _, rule_id = _store()
    r, ai, svc, ft, dc, no = _reports(
        s, verdict=_UNSURE, fetch_map={("max", "300", "s1"): "завуалированный текст"})
    res = _run_report(r, make_report_token("max", 300, "s1", rule_id))
    rec = s.report(res["id"])

    assert ai.calls == 1 and dc.calls == []
    assert rec["verdict"] == "unsure"
    assert rec["review_required"] is True
    assert rec["review_reason"] == "завуалировано"


def test_max_source_reads_itself():
    s, _, rule_id = _store()
    r, ai, svc, ft, dc, no = _reports(s, verdict=_OK, fetch_map={("max", "300", "s1"): "текст"})
    _run_report(r, make_report_token("max", 300, "s1", rule_id))  # источник MAX → читаем сам
    assert ft.calls == [("max", "300", "s1")]
    assert ai.calls == 1


def test_dedup_repeat_skips_ai():
    s, _, rule_id = _store()
    mm = MessageMap(_TMP / f"mm_{time.time_ns()}.json")
    mm.record("tg", "100", "m1", "max", "200", "c1")
    r, ai, svc, ft, dc, no = _reports(
        s, verdict=_VIOLATION, mm=mm, fetch_map={("max", "200", "c1"): "продам мефедрон"})
    tok = make_report_token("tg", 100, "m1", rule_id)
    first = _run_report(r, tok, reporter="max:a")
    assert ai.calls == 1
    # вторая жалоба на ТОТ ЖЕ неизменённый текст — без ИИ, повтор учтён у первой записи
    second = _run_report(r, tok, reporter="max:b")
    assert ai.calls == 1                                     # ИИ повторно НЕ звали
    assert s.report(first["id"])["repeat_count"] == 1
    rec2 = s.report(second["id"])
    assert rec2["verdict"] == "violation" and rec2["repeat_of"] == first["id"]


def test_quota_pauses_keeps_queued():
    s, _, rule_id = _store()
    mm = MessageMap(_TMP / f"mm_{time.time_ns()}.json")
    mm.record("tg", "100", "m1", "max", "200", "c1")
    r, ai, svc, ft, dc, no = _reports(
        s, verdict=_QUOTA, mm=mm, fetch_map={("max", "200", "c1"): "текст"}, cooldown=0.0)
    tok = make_report_token("tg", 100, "m1", rule_id)

    async def scenario():
        res = await r.submit(tok, "", reporter="max:a")
        await r._process(res["id"])                          # квота исчерпана
        assert ai.calls == 1
        assert s.report(res["id"])["status"] == "queued"     # НЕ done — переобработается
        assert dc.calls == [] and no.calls == []
        r._moderation = FakeAI(_VIOLATION)                   # окно сброшено
        await r._process(res["id"])
        return res
    res = run(scenario())
    assert s.report(res["id"])["status"] == "done"
    assert dc.calls == [("max", "200", "c1")]


def test_ai_disabled_unsure():
    s, _, rule_id = _store()
    r, ai, svc, ft, dc, no = _reports(
        s, verdict=_VIOLATION, ai_enabled=False, fetch_map={("max", "300", "s1"): "текст"})
    res = _run_report(r, make_report_token("max", 300, "s1", rule_id))
    assert ai.calls == 0                                     # выключенный ИИ не зовём
    assert s.report(res["id"])["verdict"] == "unsure"
    assert dc.calls == []


def test_process_idempotent_on_done():
    s, _, rule_id = _store()
    r, ai, svc, ft, dc, no = _reports(s, verdict=_OK, fetch_map={("max", "300", "s1"): "текст"})
    tok = make_report_token("max", 300, "s1", rule_id)

    async def scenario():
        res = await r.submit(tok, "", reporter="tg:u1")
        await r._process(res["id"])
        await r._process(res["id"])                          # повтор по той же записи
        return res
    run(scenario())
    assert ai.calls == 1                                     # done → второй раз не обрабатываем


# --- доработка ревью: находки #1/#4/#3/#5 ---
def test_unsure_verdict_does_not_poison_dedup():
    # Находка #1 (HIGH, обход модерации): ИИ был недоступен → unsure; после включения ИИ
    # тот же неизменённый текст должен ПЕРЕПРОВЕРИТЬСЯ, а не залипнуть на кэшированном unsure.
    s, _, rule_id = _store()
    mm = MessageMap(_TMP / f"mm_{time.time_ns()}.json")
    mm.record("tg", "100", "m1", "max", "200", "c1")
    r, ai, svc, ft, dc, no = _reports(
        s, verdict=_VIOLATION, ai_enabled=False, mm=mm,
        fetch_map={("max", "200", "c1"): "продам мефедрон"})
    tok = make_report_token("tg", 100, "m1", rule_id)
    r1 = _run_report(r, tok, reporter="max:a")
    assert s.report(r1["id"])["verdict"] == "unsure" and ai.calls == 0
    newai = FakeAI(_VIOLATION, enabled=True)                 # окно ИИ восстановилось
    r._moderation = newai
    r2 = _run_report(r, tok, reporter="max:b")
    assert newai.calls == 1                                  # перепроверено, а НЕ дедуп в unsure
    assert s.report(r2["id"])["verdict"] == "violation"
    assert dc.calls == [("max", "200", "c1")]                # теперь копия скрыта


def test_repeat_counter_accumulates_on_root():
    # Находка #4: счётчик повторов копится на КОРНЕ (а не «повторная №1» на каждой новой).
    s, _, rule_id = _store()
    mm = MessageMap(_TMP / f"mm_{time.time_ns()}.json")
    mm.record("tg", "100", "m1", "max", "200", "c1")
    r, ai, svc, ft, dc, no = _reports(
        s, verdict=_VIOLATION, mm=mm, fetch_map={("max", "200", "c1"): "продам мефедрон"})
    tok = make_report_token("tg", 100, "m1", rule_id)
    root = _run_report(r, tok, reporter="max:a")
    rep2 = _run_report(r, tok, reporter="max:b")
    rep3 = _run_report(r, tok, reporter="max:c")
    assert s.report(root["id"])["repeat_count"] == 2         # оба повтора учтены на корне
    assert s.report(rep2["id"])["repeat_of"] == root["id"]
    assert s.report(rep3["id"])["repeat_of"] == root["id"]
    assert ai.calls == 1                                     # ИИ только на корне


def test_merge_account_migrates_reports():
    # Находка #3: слияние аккаунтов переносит и таблицу reports (иначе запись осиротеет).
    s = ControlStore(_TMP / f"merge_{time.time_ns()}.json")
    src = run(s.get_or_create_account("tg", 111, None))["id"]
    dst = run(s.get_or_create_account("max", 222, None))["id"]
    run(s.add_report({"src_key": "tg:1:1", "account_id": src, "status": "queued"}))
    assert run(s.merge_account(src, dst)) is True
    reps = list(s.table("reports").values())
    assert reps and all(r["account_id"] == dst for r in reps)


def test_antispam_sweeps_stale_keys():
    # Находка #5: словарь антиспама не растёт вечно — протухшие ключи выметаются.
    s, *_ = _store()
    r, *_ = _reports(s, verdict=_OK, report_window=100)
    r._attempts = {f"tg:{i}": [0.0] for i in range(r._ATTEMPTS_SWEEP_AT + 5)}
    r.clock = lambda: 1000.0                                 # далеко за окном (все протухли)
    r._register_attempt("tg:new")
    assert len(r._attempts) == 1 and "tg:new" in r._attempts


def test_load_pending_enqueues():
    s, acc, _ = _store()
    run(s.add_report({"src_key": "tg:1:1", "account_id": acc, "status": "queued"}))
    run(s.add_report({"src_key": "tg:1:2", "account_id": acc, "status": "done",
                      "verdict": "ok"}))
    r, *_ = _reports(s, verdict=_OK)
    assert r.load_pending() == 1                              # только queued
    assert r._queue.qsize() == 1


# ============ подпись «Пожаловаться» в копии (integration._deliver) ============
class FakeTgSend:
    def __init__(self):
        self.sent = []
        self.edits = []

    async def send_message(self, chat_id, text, parse_mode=None, message_thread_id=None,
                           reply_markup=None, disable_web_page_preview=None):
        self.sent.append({"chat_id": chat_id, "text": text,
                          "disable_web_page_preview": disable_web_page_preview})
        return {"chat": {"id": chat_id}, "message_id": 777}

    async def edit_message_text(self, chat_id, message_id, text, *, parse_mode=None,
                                reply_markup=None, disable_web_page_preview=None):
        self.edits.append({"chat_id": chat_id, "message_id": message_id,
                           "text": text, "parse_mode": parse_mode,
                           "disable_web_page_preview": disable_web_page_preview})

    async def edit_message_caption(self, chat_id, message_id, caption, *, parse_mode=None,
                                   reply_markup=None):
        self.edits.append({"chat_id": chat_id, "message_id": message_id,
                           "caption": caption, "parse_mode": parse_mode})


def _max_norm(chat_id, mid, text):
    return {"chat_id": chat_id, "sender_id": None, "message_id": None, "mid": mid,
            "is_group": True, "thread_id": None, "sender_name": None,
            "forward_from": None, "text": text, "entities": [], "media": [], "url": None}


def _max_to_tg_dispatcher():
    from control.integration import RuleDispatcher
    s = ControlStore(_TMP / f"fs_{time.time_ns()}.json")
    acc = run(s.get_or_create_account("max", 7, None))["id"]
    run(s.set_subscription(acc, {"status": "active"}))
    run(s.add_rule({"account_id": acc, "a": {"messenger": "max", "chat_id": "500"},
                    "b": {"messenger": "tg", "chat_id": "600"}, "dir": "both", "status": "active"}))
    ft = FakeTgSend()
    d = RuleDispatcher(s, tg_client=ft)
    config.MODERATION_GATE_MODE = "off"
    return d, ft, s, acc


def test_footer_report_link_injected():
    d, ft, s, acc = _max_to_tg_dispatcher()
    config.MODERATION_REPORTS_ENABLED = True
    try:
        run(d.on_max_message(_max_norm("500", "mid.abc", "привет")))
    finally:
        config.MODERATION_REPORTS_ENABLED = False
    assert ft.sent, "копия не доставлена"
    txt = ft.sent[0]["text"]
    assert "Пожаловаться" in txt
    assert "t.me/test_mesync_bot?startapp=r_" in txt    # диплинк на площадке читателя (TG)
    assert ft.sent[0]["disable_web_page_preview"] is True
    m = re.search(r"startapp=(r_[A-Za-z0-9_-]+)", txt)   # токен обратим к координатам источника
    assert m and parse_report_token(m.group(1)) == {
        "messenger": "max", "chat_id": "500", "mid": "mid.abc",
        "rule_id": s.rules_of(acc)[0]["id"]}
    assert ft.edits, "ссылка должна обновиться после получения message_id копии"
    edited = ft.edits[-1]["text"]
    assert ft.edits[-1]["disable_web_page_preview"] is True
    m2 = re.search(r"startapp=(r_[A-Za-z0-9_-]+)", edited)
    assert m2 and parse_report_token(m2.group(1)) == {
        "messenger": "max", "chat_id": "500", "mid": "mid.abc",
        "rule_id": s.rules_of(acc)[0]["id"],
        "copy_messenger": "tg", "copy_chat": "600", "copy_mid": "777",
        "copy_thread": None}


def test_footer_absent_when_reports_disabled():
    d, ft, s, acc = _max_to_tg_dispatcher()
    config.MODERATION_REPORTS_ENABLED = False
    run(d.on_max_message(_max_norm("500", "mid.abc", "привет")))
    assert ft.sent and "Пожаловаться" not in ft.sent[0]["text"]


# ========================= API-эндпоинт =========================
def _client(reports_obj, enabled):
    from fastapi.testclient import TestClient
    from control.api import create_app, set_reports, set_settings
    s = ControlStore(_TMP / f"api_{time.time_ns()}.json")
    config.MODERATION_REPORTS_ENABLED = enabled
    set_reports(reports_obj)
    set_settings(None)
    return TestClient(create_app(s)), s


def test_endpoint_disabled_503():
    c, _ = _client(None, enabled=False)
    r = c.post("/api/report", json={"token": "r_x", "text": "x", "messenger": "tg"})
    assert r.status_code == 503
    assert r.json()["detail"]["message"] == "Модерация временно недоступна."
    config.MODERATION_REPORTS_ENABLED = False


def test_endpoint_disabled_by_runtime_settings_503_message():
    from fastapi.testclient import TestClient
    from control.api import create_app, set_reports, set_settings
    from control.settings import Settings

    s = ControlStore(_TMP / f"api_{time.time_ns()}.json")
    reports_obj, *_ = _reports(s, verdict=_OK)
    settings = Settings(s)
    run(settings.set("moderation_reports_enabled", False))
    config.MODERATION_REPORTS_ENABLED = True
    set_reports(reports_obj)
    set_settings(settings)
    try:
        c = TestClient(create_app(s))
        r = c.post("/api/report/check", json={"token": "r_x"})
        assert r.status_code == 503
        assert r.json()["detail"] == {
            "code": "reports_disabled",
            "message": "Модерация временно недоступна.",
        }
    finally:
        set_settings(None)
        config.MODERATION_REPORTS_ENABLED = False


def test_reports_ai_can_be_disabled_by_runtime_settings():
    from control.settings import Settings

    s = ControlStore(_TMP / f"reports_{time.time_ns()}.json")
    settings = Settings(s)
    run(settings.set("moderation_ai_enabled", False))
    reports_obj, ai, *_ = _reports(s, verdict=_VIOLATION, settings=settings)
    assert run(reports_obj.classify_test("продам запрещённое"))["verdict"] is None
    assert ai.calls == 0


def test_endpoint_enabled_ok_and_bad_token():
    s, acc, rule_id = _store()
    reports_obj, *_ = _reports(s, verdict=_OK)
    c, _ = _client(reports_obj, enabled=True)
    tok = make_report_token("tg", 100, "m1", rule_id)
    ok = c.post("/api/report", json={"token": tok, "text": "спам", "messenger": "max"})
    assert ok.status_code == 200 and ok.json()["ok"] is True and ok.json()["id"]
    bad = c.post("/api/report", json={"token": "nope", "text": "x", "messenger": "max"})
    assert bad.status_code == 400 and bad.json()["detail"]["code"] == "bad_token"
    config.MODERATION_REPORTS_ENABLED = False
