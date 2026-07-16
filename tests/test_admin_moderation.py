"""Тесты модуля модерации админ-панели (этап 4.2): runtime-режим гейта, enforcement
(moderation_hold правила + блокировка аккаунта в decide), автопауза по страйкам, admin-API
(очередь жалоб, действия, классификатор, редактор словаря).

Запуск:  .venv/bin/python -m pytest tests/test_admin_moderation.py -q
"""
import asyncio
import os
import sys
import tempfile
import time
from pathlib import Path

_TMP = Path(tempfile.mkdtemp(prefix="admmod_"))
os.environ.setdefault("MESYNC_DATA_DIR", str(_TMP / "control"))
os.environ.setdefault("MESYNC_SESSION_SECRET", "test-secret")
os.environ.setdefault("MESYNC_AUTH_INSECURE", "1")
os.environ.setdefault("MESYNC_ADMIN_PASSWORD", "pw")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "111:TESTTOKEN")
os.environ.setdefault("MAX_BOT_TOKEN", "maxtoken")

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from unittest.mock import AsyncMock  # noqa: E402

from control import config  # noqa: E402
from control.integration import RuleDispatcher  # noqa: E402
from control.message_map import MessageMap  # noqa: E402
from control.moderation import Verdict, VERDICT_VIOLATION, VERDICT_OK  # noqa: E402
from control.reports import Reports, make_report_token  # noqa: E402
from control.settings import Settings  # noqa: E402
from control.store import ControlStore  # noqa: E402

run = asyncio.run
_VIOLATION = Verdict(VERDICT_VIOLATION, category="drugs", confidence=0.9, reason="сбыт")
_OK = Verdict(VERDICT_OK, reason="норма")


def teardown_function(_):
    config.MODERATION_GATE_MODE = "off"


# ---------------- фейки ----------------
class FakeTg:
    def __init__(self): self.sent = []
    async def send_message(self, chat_id, text, parse_mode=None, message_thread_id=None,
                           reply_markup=None, **kw):
        self.sent.append({"chat_id": chat_id, "text": text})


class StubStop:
    def __init__(self, hits): self._hits = set(hits)
    def match(self, text): return set(self._hits)


class StubAI:
    def __init__(self, verdict, enabled=True): self._v = verdict; self.enabled = enabled; self.calls = 0
    async def classify(self, text, *, context=""): self.calls += 1; return self._v


def _store_with_rule(a=("max", "100"), b=("tg", "200")):
    s = ControlStore(_TMP / f"s_{time.time_ns()}.json")
    acc = run(s.get_or_create_account("max", 1, None))["id"]
    run(s.set_subscription(acc, {"status": "active"}))
    rule = run(s.add_rule({"account_id": acc, "a": {"messenger": a[0], "chat_id": a[1]},
                           "b": {"messenger": b[0], "chat_id": b[1]}, "dir": "both", "status": "active"}))
    return s, acc, rule["id"]


def _max_norm(chat_id, mid, text):
    return {"chat_id": chat_id, "sender_id": None, "message_id": None, "mid": mid,
            "is_group": True, "thread_id": None, "sender_name": None,
            "forward_from": None, "text": text, "entities": [], "media": [], "url": None}


# ================= runtime-режим гейта (settings > config) =================
def test_runtime_gate_mode_overrides_config():
    config.MODERATION_GATE_MODE = "off"           # в config гейт выключен
    s, acc, _ = _store_with_rule()
    st = Settings(s)
    run(s.set_setting("moderation_gate_mode", "enforce"))   # но в панели — enforce
    ft = FakeTg()
    d = RuleDispatcher(s, tg_client=ft, settings=st)
    d._stoplist = StubStop({"drugs"})
    d._moderation = StubAI(_VIOLATION)
    run(d.on_max_message(_max_norm("100", "m1", "продам мефедрон")))
    assert ft.sent == []                          # заблокировано по runtime-режиму, не по config


# ================= enforcement в decide (hold / blocked) =================
def test_decide_skips_moderation_hold_and_blocked():
    s, acc, rule_id = _store_with_rule()
    d = RuleDispatcher(s)
    assert len(d.decide("max", "100", None)) == 1          # базово доставляем
    run(s.update_rule(rule_id, {"moderation_hold": True}))
    assert d.decide("max", "100", None) == []              # правило на модерационной паузе
    run(s.update_rule(rule_id, {"moderation_hold": False}))
    assert len(d.decide("max", "100", None)) == 1
    run(s.set_account_blocked(acc, True))
    assert d.decide("max", "100", None) == []              # аккаунт заблокирован
    run(s.set_account_blocked(acc, False))
    assert len(d.decide("max", "100", None)) == 1


# ================= автопауза по страйкам =================
class _Rec:
    def __init__(self): self.calls = []
    async def __call__(self, rule_id, acc, count): self.calls.append((rule_id, acc, count))


def test_autopause_on_strikes():
    s, acc, rule_id = _store_with_rule(a=("tg", "100"), b=("max", "200"))
    mm = MessageMap(_TMP / f"mm_{time.time_ns()}.json")
    mm.record("tg", "100", "m1", "max", "200", "c1")
    mm.record("tg", "100", "m2", "max", "200", "c2")
    st = Settings(s)
    run(s.set_setting("moderation_autopause_strikes", 2))
    hold = _Rec()

    async def fetch(m, c, mid): return "продам мефедрон"
    async def dele(m, c, mid): return True

    r = Reports(s, moderation=StubAI(_VIOLATION), message_map=mm, fetch_text=fetch,
                delete_copy=dele, settings=st, hold_cb=hold)
    tok1 = make_report_token("tg", 100, "m1", rule_id)
    tok2 = make_report_token("tg", 100, "m2", rule_id)

    async def scenario():
        res1 = await r.submit(tok1, "", reporter="max:a")   # 1-е нарушение (1 < 2 — паузы нет)
        await r._process(res1["id"])
        assert s.rule(rule_id).get("moderation_hold") is not True and hold.calls == []
        res2 = await r.submit(tok2, "", reporter="max:b")   # 2-е (другое сообщение) — порог
        await r._process(res2["id"])
    run(scenario())
    assert s.rule(rule_id).get("moderation_hold") is True
    assert hold.calls and hold.calls[0] == (rule_id, acc, 2)


def test_muted_rule_drops_report_silently():
    s, acc, rule_id = _store_with_rule(a=("tg", "100"), b=("max", "200"))
    run(s.update_rule(rule_id, {"report_muted": True}))
    r = Reports(s, moderation=StubAI(_OK))
    tok = make_report_token("tg", 100, "m1", rule_id)
    res = run(r.submit(tok, "", reporter="max:a"))
    assert res == {"ok": True}
    assert r._queue.qsize() == 0                # в очередь не поставлено
    assert s.reports_page()["total"] == 0       # запись не создана


# ================= admin-API модерации =================
class FakeOps:
    async def classify_test(self, text):
        return {"hits": ["drugs"] if text else [], "verdict": {"verdict": "violation"} if text else None}
    async def admin_delete_copies(self, rid): return 2
    async def admin_reclassify(self, rid): return {"verdict": "ok"}


def _client(with_ops=True):
    from fastapi.testclient import TestClient
    from control.api import create_app, set_settings, set_reports
    # Пароль и AUTH_INSECURE выставляем в config В РАНТАЙМЕ (не через env): значения config
    # читаются при ПЕРВОМ импорте и зависят от порядка тест-файлов; прямая установка делает
    # тест самодостаточным (AUTH_INSECURE=True → cookie входа без Secure → ходит по HTTP).
    config.ADMIN_PASSWORD = "pw"
    config.AUTH_INSECURE = True
    s = ControlStore(_TMP / f"api_{time.time_ns()}.json")
    set_settings(Settings(s))
    set_reports(FakeOps() if with_ops else None)
    c = TestClient(create_app(s))
    r = c.post("/api/admin/login", json={"password": "pw"})
    assert r.status_code == 200, r.text
    return c, s


def _seed_report(s):
    acc = run(s.get_or_create_account("max", 7, None))["id"]
    rule = run(s.add_rule({"account_id": acc, "a": {"messenger": "tg", "chat_id": "100"},
                           "b": {"messenger": "max", "chat_id": "200"}, "dir": "both", "status": "active"}))
    rec = run(s.add_report({"src_messenger": "tg", "src_chat": "100", "src_mid": "m1",
                            "src_key": "tg:100:m1", "rule_id": rule["id"], "account_id": acc,
                            "reporter": "max:u1", "status": "done", "verdict": "violation",
                            "category": "drugs"}))
    return acc, rule["id"], rec["id"]


def test_reports_list_requires_auth():
    from fastapi.testclient import TestClient
    from control.api import create_app, set_settings
    s = ControlStore(_TMP / f"noauth_{time.time_ns()}.json")
    set_settings(Settings(s))
    c = TestClient(create_app(s))          # без логина
    assert c.get("/api/admin/moderation/reports").status_code == 401


def test_reports_list_and_filter():
    c, s = _client()
    _seed_report(s)
    run(s.add_report({"src_key": "tg:1:2", "rule_id": None, "account_id": None,
                      "status": "done", "verdict": "ok"}))
    page = c.get("/api/admin/moderation/reports").json()
    assert page["total"] == 2 and len(page["items"]) == 2
    viol = c.get("/api/admin/moderation/reports", params={"verdict": "violation"}).json()
    assert viol["total"] == 1 and viol["items"][0]["verdict"] == "violation"


def test_report_detail_404_and_200():
    c, s = _client()
    _, _, rid = _seed_report(s)
    assert c.get("/api/admin/moderation/reports/nope").status_code == 404
    assert c.get(f"/api/admin/moderation/reports/{rid}").json()["report"]["id"] == rid


def test_actions_store_side():
    c, s = _client()
    acc, rule_id, rid = _seed_report(s)
    # пауза правила
    assert c.post(f"/api/admin/moderation/reports/{rid}/action", json={"action": "hold_rule"}).status_code == 200
    assert s.rule(rule_id)["moderation_hold"] is True
    # снятие
    c.post(f"/api/admin/moderation/reports/{rid}/action", json={"action": "unhold_rule"})
    assert s.rule(rule_id).get("moderation_hold") is False
    # блокировка аккаунта
    c.post(f"/api/admin/moderation/reports/{rid}/action", json={"action": "block_account"})
    assert s.account_blocked(acc) is True
    c.post(f"/api/admin/moderation/reports/{rid}/action", json={"action": "unblock_account"})
    assert s.account_blocked(acc) is False
    # мьют
    c.post(f"/api/admin/moderation/reports/{rid}/action", json={"action": "mute_rule"})
    assert s.rule(rule_id)["report_muted"] is True
    # override вердикта
    r = c.post(f"/api/admin/moderation/reports/{rid}/action",
               json={"action": "override", "verdict": "ok"})
    assert r.status_code == 200 and s.report(rid)["verdict"] == "ok" and s.report(rid)["reviewed"] is True
    # dismiss
    c.post(f"/api/admin/moderation/reports/{rid}/action", json={"action": "dismiss"})
    assert s.report(rid)["reviewed"] is True
    # неизвестное действие
    assert c.post(f"/api/admin/moderation/reports/{rid}/action", json={"action": "boom"}).status_code == 400
    # всё записалось в аудит
    actions = [i["action"] for i in c.get("/api/admin/audit").json()["items"]]
    assert any(a.startswith("moderation:") for a in actions)


def test_actions_io_side():
    c, s = _client()
    _, _, rid = _seed_report(s)
    r1 = c.post(f"/api/admin/moderation/reports/{rid}/action", json={"action": "hide_copies"})
    assert r1.status_code == 200
    assert r1.json()["hidden"] == 2 and r1.json()["deleted"] == 2
    r1_legacy = c.post(f"/api/admin/moderation/reports/{rid}/action",
                       json={"action": "delete_copies"})
    assert r1_legacy.status_code == 200 and r1_legacy.json()["hidden"] == 2
    r2 = c.post(f"/api/admin/moderation/reports/{rid}/action", json={"action": "reclassify"})
    assert r2.status_code == 200 and r2.json()["verdict"] == {"verdict": "ok"}


def test_io_action_503_without_ops():
    c, s = _client(with_ops=False)
    _, _, rid = _seed_report(s)
    assert c.post(f"/api/admin/moderation/reports/{rid}/action",
                  json={"action": "delete_copies"}).status_code == 503


def test_classify_endpoint():
    c, _ = _client()
    r = c.post("/api/admin/moderation/classify", json={"text": "продам мефедрон"})
    assert r.status_code == 200 and r.json()["hits"] == ["drugs"]


def test_stoplist_get_put():
    # ВАЖНО: пишем во ВРЕМЕННЫЙ файл, а не в боевой config.MODERATION_STOPLIST_FILE.
    old = config.MODERATION_STOPLIST_FILE
    config.MODERATION_STOPLIST_FILE = str(_TMP / f"sl_{time.time_ns()}.yaml")
    try:
        c, _ = _client()
        good = "drugs:\n  terms:\n    - мефедрон\n"
        assert c.put("/api/admin/moderation/stoplist", json={"text": good}).status_code == 200
        assert "мефедрон" in c.get("/api/admin/moderation/stoplist").json()["text"]
        assert c.put("/api/admin/moderation/stoplist", json={"text": "a:\n  - b\n c: bad"}).status_code == 400
        # защита от инцидента: пустышка/скаляр/список НЕ должны затирать словарь
        for bad in ("", "   ", "мефедрон", "[]", "null"):
            assert c.put("/api/admin/moderation/stoplist", json={"text": bad}).status_code == 400, bad
        # и файл остался прежним (последнее валидное сохранение)
        assert "мефедрон" in c.get("/api/admin/moderation/stoplist").json()["text"]
    finally:
        config.MODERATION_STOPLIST_FILE = old


def test_override_and_dismiss_set_status_done():
    # находка ревью: без status=done воркер переобработал бы и перезатёр решение оператора.
    c, s = _client()
    acc = run(s.get_or_create_account("max", 8, None))["id"]
    rule = run(s.add_rule({"account_id": acc, "a": {"messenger": "tg", "chat_id": "100"},
                           "b": {"messenger": "max", "chat_id": "200"}, "dir": "both", "status": "active"}))
    r1 = run(s.add_report({"src_key": "tg:100:mX", "rule_id": rule["id"], "account_id": acc,
                           "status": "queued", "verdict": "violation"}))
    assert c.post(f"/api/admin/moderation/reports/{r1['id']}/action",
                  json={"action": "override", "verdict": "ok"}).status_code == 200
    assert s.report(r1["id"])["status"] == "done" and s.report(r1["id"])["verdict"] == "ok"
    r2 = run(s.add_report({"src_key": "tg:100:mY", "rule_id": rule["id"], "account_id": acc,
                           "status": "queued", "verdict": "violation"}))
    c.post(f"/api/admin/moderation/reports/{r2['id']}/action", json={"action": "dismiss"})
    assert s.report(r2["id"])["status"] == "done"


def test_action_no_target_returns_400():
    # находка ревью: тихий no-op + ложный аудит → теперь 400 no_target.
    c, s = _client()
    r1 = run(s.add_report({"src_key": "tg:1:1", "rule_id": None, "account_id": None,
                           "status": "done", "verdict": "violation"}))
    assert c.post(f"/api/admin/moderation/reports/{r1['id']}/action", json={"action": "block_account"}).status_code == 400
    assert c.post(f"/api/admin/moderation/reports/{r1['id']}/action", json={"action": "hold_rule"}).status_code == 400
    r2 = run(s.add_report({"src_key": "tg:1:2", "rule_id": "rule_ghost", "account_id": "acc_ghost",
                           "status": "done", "verdict": "violation"}))
    assert c.post(f"/api/admin/moderation/reports/{r2['id']}/action", json={"action": "hold_rule"}).status_code == 400
    assert c.post(f"/api/admin/moderation/reports/{r2['id']}/action", json={"action": "block_account"}).status_code == 400


def test_strike_count_by_unique_src_key():
    # находка ревью: страйки — по уникальным сообщениям, не по числу строк-жалоб.
    s = ControlStore(_TMP / f"strk_{time.time_ns()}.json")
    for mid in ("m1", "m1", "m2"):   # m1 дважды (повтор), m2 один → 2 уникальных
        run(s.add_report({"src_key": f"tg:100:{mid}", "rule_id": "rule_x",
                          "verdict": "violation", "status": "done"}))
    assert s.count_rule_violations_since("rule_x", 0) == 2


def test_held_rule_edit_not_propagated():
    # находка ревью: правка не должна обходить moderation_hold.
    s, acc, rule_id = _store_with_rule(a=("tg", "100"), b=("max", "200"))
    config.MODERATION_GATE_MODE = "off"
    from control.message_map import MessageMap
    mm = MessageMap(_TMP / f"mm_{time.time_ns()}.json")
    mm.record("tg", "100", "m1", "max", "200", "c1")
    d = RuleDispatcher(s, message_map=mm)
    d._edit_max = AsyncMock()
    norm = {"chat": {"id": "100"}, "message_id": "m1", "text": "новый текст", "entities": []}
    run(d.on_tg_edit(norm))
    d._edit_max.assert_awaited()                 # активное правило → правка идёт
    d._edit_max.reset_mock()
    run(s.update_rule(rule_id, {"moderation_hold": True}))
    run(d.on_tg_edit({**norm, "text": "ещё правка"}))
    d._edit_max.assert_not_awaited()             # правило на паузе → правку не пропагируем
