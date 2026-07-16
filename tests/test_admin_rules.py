"""Тесты глобальных обзоров админ-панели (этап 4.4): правила / источники / трафик —
кросс-аккаунтные списки, деривация статуса, действия оператора и аудит.

Запуск:  .venv/bin/python -m pytest tests/test_admin_rules.py -q
"""
import asyncio
import json
import os
import sys
import tempfile
import time
from pathlib import Path

import pytest

_TMP = Path(tempfile.mkdtemp(prefix="admrules_"))
os.environ.setdefault("MESYNC_DATA_DIR", str(_TMP / "control"))
os.environ.setdefault("MESYNC_SESSION_SECRET", "test-secret")
os.environ.setdefault("MESYNC_AUTH_INSECURE", "1")
os.environ.setdefault("MESYNC_ADMIN_PASSWORD", "pw")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "111:TESTTOKEN")
os.environ.setdefault("MAX_BOT_TOKEN", "maxtoken")

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from control import config, rules as rules_mod, sources as sources_mod  # noqa: E402
from control.store import ControlStore  # noqa: E402

run = asyncio.run

# Изоляция ownership от боевых путей и от других тест-модулей: подменяем захваченный
# sources._FILES ТОЛЬКО на время своих тестов и восстанавливаем (иначе течёт в
# test_control, который пишет ownership по своим путям).
_TG_OWN = _TMP / "tg_own.json"
_MAX_OWN = _TMP / "max_own.json"


@pytest.fixture(autouse=True)
def _own_paths(monkeypatch):
    async def _to_thread_sync(func, /, *args, **kwargs):
        return func(*args, **kwargs)

    saved = dict(sources_mod._FILES)
    monkeypatch.setattr(asyncio, "to_thread", _to_thread_sync)
    sources_mod._FILES["tg"] = str(_TG_OWN)
    sources_mod._FILES["max"] = str(_MAX_OWN)
    yield
    sources_mod._FILES.clear()
    sources_mod._FILES.update(saved)


def _write_own(path: Path, owners: dict) -> None:
    path.write_text(json.dumps({"chats": {}, "owners": owners, "pending": {}}), encoding="utf-8")


def _endpoint(messenger: str, chat_id: str) -> dict:
    return {"messenger": messenger, "chat_id": chat_id}


def _fixture():
    """2 аккаунта, 3 источника (ok/err), правила: active / broken / paused."""
    s = ControlStore(_TMP / f"r_{time.time_ns()}.json")
    a1 = run(s.get_or_create_account("max", 10, "79990001111"))["id"]
    a2 = run(s.get_or_create_account("tg", 20, "79990002222"))["id"]
    _write_own(_MAX_OWN, {
        "100": {"user_id": 10, "title": "Канал А", "rights_ok": True, "type": "channel"},
        "300": {"user_id": 10, "title": "Канал B", "rights_ok": False, "type": "channel"},  # err
    })
    _write_own(_TG_OWN, {
        "200": {"user_id": 20, "title": "Группа", "rights_ok": True, "type": "group"},  # tg group → ok
    })
    # rule1: max:100 ⇄ tg:200 → active; rule2: max:300 ⇄ tg:200 → broken; rule3: paused
    run(s.add_rule({"account_id": a1, "a": _endpoint("max", "100"), "b": _endpoint("tg", "200"),
                    "dir": "both", "status": "active"}))
    run(s.add_rule({"account_id": a1, "a": _endpoint("max", "300"), "b": _endpoint("tg", "200"),
                    "dir": "both", "status": "active"}))
    run(s.add_rule({"account_id": a2, "a": _endpoint("max", "100"), "b": _endpoint("tg", "200"),
                    "dir": "both", "status": "paused"}))
    return s, a1, a2


def _client(s, source_notifier=None):
    from fastapi.testclient import TestClient
    from control.api import create_app, set_settings, set_source_notifier
    from control.settings import Settings
    config.ADMIN_PASSWORD = "pw"
    config.AUTH_INSECURE = True
    set_source_notifier(source_notifier)
    set_settings(Settings(s))
    c = TestClient(create_app(s))
    assert c.post("/api/admin/login", json={"password": "pw"}).status_code == 200
    return c


# ================= правила: глобальный список + статусы =================
def test_admin_rules_page_status_derivation():
    s, a1, a2 = _fixture()
    page = run(rules_mod.admin_rules_page(s))
    assert page["stats"] == {"total": 3, "active": 1, "paused": 1, "broken": 1}
    broken = run(rules_mod.admin_rules_page(s, status="broken"))
    assert broken["total"] == 1
    r = broken["items"][0]
    assert r["status"] == "broken" and "brokenReason" in r
    assert r["account_id"] == a1 and r["phone"] == "79990001111"
    # фильтр по аккаунту
    assert run(rules_mod.admin_rules_page(s, account_id=a2))["total"] == 1
    # фильтр по источнику
    assert run(rules_mod.admin_rules_page(s, source_id="max:300"))["total"] == 1


def test_admin_rules_endpoint_and_auth():
    s, a1, a2 = _fixture()
    from fastapi.testclient import TestClient
    from control.api import create_app, set_settings
    from control.settings import Settings
    set_settings(Settings(s))
    noauth = TestClient(create_app(s))
    assert noauth.get("/api/admin/rules").status_code == 401
    assert noauth.get("/api/admin/traffic").status_code == 401
    assert noauth.get("/api/admin/sources").status_code == 401

    c = _client(s)
    body = c.get("/api/admin/rules", params={"status": "active"}).json()
    assert body["total"] == 1 and body["stats"]["broken"] == 1
    rid = body["items"][0]["id"]
    d = c.get(f"/api/admin/rules/{rid}").json()
    assert d["rule"]["id"] == rid and "perRuleBytes" in d
    assert c.get("/api/admin/rules/nope").status_code == 404


def test_admin_rule_actions_and_audit():
    s, a1, a2 = _fixture()
    c = _client(s)
    rid = run(rules_mod.admin_rules_page(s, account_id=a2))["items"][0]["id"]  # paused rule
    assert c.post(f"/api/admin/rules/{rid}/action", json={"action": "resume"}).status_code == 200
    assert s.rule(rid)["status"] == "active"
    c.post(f"/api/admin/rules/{rid}/action", json={"action": "pause"})
    assert s.rule(rid)["status"] == "paused"
    c.post(f"/api/admin/rules/{rid}/action", json={"action": "hold_rule"})
    assert s.rule(rid)["moderation_hold"] is True
    assert c.post(f"/api/admin/rules/{rid}/action", json={"action": "boom"}).status_code == 400
    c.post(f"/api/admin/rules/{rid}/action", json={"action": "delete"})
    assert s.rule(rid) is None
    assert c.post(f"/api/admin/rules/{rid}/action", json={"action": "pause"}).status_code == 404
    actions = [i["action"] for i in c.get("/api/admin/audit").json()["items"]]
    assert "rule:delete" in actions and "rule:pause" in actions


def test_admin_rule_hold_unhold_notifies_owner_once_per_state_change():
    from control.api import set_rule_moderation_hold, set_source_notifier

    s, _a1, a2 = _fixture()
    sent: list[dict[str, str]] = []

    async def notify(messenger, user_id, text, **kwargs):
        sent.append({"messenger": messenger, "user_id": str(user_id), "text": text})

    set_source_notifier(notify)
    try:
        rid = run(rules_mod.admin_rules_page(s, account_id=a2))["items"][0]["id"]

        assert run(set_rule_moderation_hold(s, rid, True))["moderation_hold"] is True
        assert s.rule(rid)["moderation_hold"] is True
        public_rule = run(rules_mod.list_rules(s, a2))["rules"][0]
        assert public_rule["moderationHold"] is True
        notes = s.notifications_of(a2)
        assert len(notes) == 1
        assert notes[0]["type"] == "rules"
        assert notes[0]["title"] == "Правило остановлено модерацией"
        assert notes[0]["link"] == {"screen": "rules", "ruleId": rid}
        assert sent == [{"messenger": "tg", "user_id": "20",
                         "text": "🛡 Правило №1: пересылка временно приостановлена. Проверьте источник и дождитесь снятия ограничения."}]

        assert run(set_rule_moderation_hold(s, rid, True))["moderation_hold"] is True
        assert len(s.notifications_of(a2)) == 1
        assert len(sent) == 1

        assert run(set_rule_moderation_hold(s, rid, False))["moderation_hold"] is False
        assert s.rule(rid)["moderation_hold"] is False
        notes = s.notifications_of(a2)
        assert len(notes) == 2
        assert notes[0]["title"] == "Ограничение правила снято"
        assert sent[-1] == {"messenger": "tg", "user_id": "20",
                            "text": "✅ Правило №1: пересылка снова работает."}
    finally:
        set_source_notifier(None)


def test_moderation_hold_blocks_owner_mutations_but_allows_delete():
    s, _a1, a2 = _fixture()
    rid = run(rules_mod.admin_rules_page(s, account_id=a2))["items"][0]["id"]
    run(s.update_rule(rid, {"moderation_hold": True, "delivery_warn": True}))

    for action in (
        lambda: run(rules_mod.update_rule(s, a2, rid, {"signAB": True})),
        lambda: run(rules_mod.set_status(s, a2, rid, "active")),
        lambda: run(rules_mod.dismiss_warning(s, a2, rid)),
    ):
        with pytest.raises(rules_mod.RuleError) as exc:
            action()
        assert exc.value.code == "moderation_hold"
        assert exc.value.status == 409

    # Админские операции явно обходят пользовательский запрет, удаление владельцем остаётся доступным.
    assert run(rules_mod.set_status(s, a2, rid, "active",
                                    allow_moderation_hold=True))["status"] == "active"
    assert run(rules_mod.dismiss_warning(s, a2, rid,
                                         allow_moderation_hold=True))["deliveryWarn"] is False
    assert run(rules_mod.delete_rule(s, a2, rid)) is True
    assert s.rule(rid) is None


def test_admin_enrich_matches_real_for_topic_and_absent():
    # Лёгкое обогащение (без сети) должно давать тот же статус, что настоящий _enrich_rule:
    # для endpoint-темы форума (статус берётся у базового чата) и для источника, которого
    # нет в ownership (base=None → broken).
    s = ControlStore(_TMP / f"m_{time.time_ns()}.json")
    a1 = run(s.get_or_create_account("max", 30, "79993334444"))["id"]
    _write_own(_MAX_OWN, {"100": {"user_id": 30, "title": "Канал", "rights_ok": True, "type": "channel"}})
    _write_own(_TG_OWN, {"100": {"user_id": 30, "title": "Форум", "rights_ok": True, "type": "group", "is_forum": True}})
    # правило с темой форума tg:100:2 ⇄ max:100 → оба ok → active
    run(s.add_rule({"account_id": a1, "a": {"messenger": "tg", "chat_id": "100", "thread_id": "2"},
                    "b": _endpoint("max", "100"), "dir": "both", "status": "active"}))
    # правило с отсутствующим источником max:999 → broken
    run(s.add_rule({"account_id": a1, "a": _endpoint("max", "999"), "b": _endpoint("tg", "100"),
                    "dir": "both", "status": "active"}))
    admin = {r["id"]: r["status"] for r in run(rules_mod.admin_rules_page(s))["items"]}
    real = {r["id"]: r["status"] for r in run(rules_mod.list_rules(s, a1))["rules"]}
    assert admin == real                                   # паритет лёгкого и полного обогащения
    assert sorted(admin.values()) == ["active", "broken"]  # тема→active, отсутствующий→broken


# ================= источники: доска здоровья =================
def test_admin_sources_board():
    s, a1, a2 = _fixture()
    c = _client(s)
    body = c.get("/api/admin/sources").json()
    assert body["counts"]["total"] == 3
    assert body["counts"]["ok"] == 2 and body["counts"]["err"] == 1
    by_id = {x["id"]: x for x in body["items"]}
    assert by_id["max:100"]["usedInRules"] == 2   # rule1 + rule3
    assert by_id["max:300"]["status"] == "err"
    assert any(acc["id"] == a1 for acc in by_id["max:100"]["accounts"])
    # фильтр по статусу
    assert c.get("/api/admin/sources", params={"status": "err"}).json()["total"] == 1


def test_admin_sources_account_sources_path_and_messenger_filter():
    s, a1, a2 = _fixture()
    # осиротевший канал (owner.user_id=None) + прямая привязка к аккаунту через account_sources
    own = json.loads(_MAX_OWN.read_text())
    own["owners"]["500"] = {"user_id": None, "title": "Канал-осиротыш", "rights_ok": True, "type": "channel"}
    _MAX_OWN.write_text(json.dumps(own))
    run(s.add_account_source(a1, "max:500"))
    c = _client(s)
    by = {x["id"]: x for x in c.get("/api/admin/sources").json()["items"]}
    # атрибуция канала к аккаунту идёт ТОЛЬКО через ветку account_sources (owner=None)
    assert "max:500" in by and any(acc["id"] == a1 for acc in by["max:500"]["accounts"])
    # messenger-фильтр на источниках и правилах
    tg_only = c.get("/api/admin/sources", params={"messenger": "tg"}).json()
    assert tg_only["items"] and all(x["messenger"] == "tg" for x in tg_only["items"])
    assert c.get("/api/admin/rules", params={"messenger": "tg"}).json()["total"] >= 1


# ================= трафик: рейтинг + сброс =================
def test_admin_traffic_page_and_reset():
    s, a1, a2 = _fixture()
    a3 = run(s.get_or_create_account("max", 30, "79990003333"))["id"]
    run(s.set_account_overrides(a1, {"traffic_limit": 2000}))
    run(s.set_account_overrides(a2, {"traffic_limit": 4000}))
    run(s.add_traffic(a1, 1000))   # 50%
    run(s.add_topup(a1, 333))
    run(s.add_traffic(a2, 5000))   # >100%
    run(s.add_topup(a3, 7000))     # add-on виден даже без расхода месяца
    c = _client(s)
    body = c.get("/api/admin/traffic", params={"sort": "used"}).json()
    assert body["items"][0]["account_id"] == a2   # больше всех
    assert body["totals"]["sumUsed"] == 6000 and body["totals"]["over100"] == 1
    assert body["totals"]["sumTopup"] == 7333 and body["totals"]["sumOverage"] == 1000
    assert body["totals"]["mediaBlocked"] == 1
    assert body["total"] == 3
    by_acc = {r["account_id"]: r for r in body["items"]}
    assert by_acc[a1]["includedRemainingBytes"] == 1000
    assert by_acc[a2]["mediaAllowed"] is False
    assert by_acc[a3]["usedBytes"] == 0 and by_acc[a3]["topupBytes"] == 7000
    only_over = c.get("/api/admin/traffic", params={"state": "over"}).json()
    assert only_over["total"] == 1 and only_over["items"][0]["account_id"] == a2
    only_blocked = c.get("/api/admin/traffic", params={"state": "blocked"}).json()
    assert only_blocked["total"] == 1 and only_blocked["items"][0]["account_id"] == a2
    only_addon = c.get("/api/admin/traffic", params={"state": "addon", "sort": "topup"}).json()
    assert only_addon["total"] == 2 and only_addon["items"][0]["account_id"] == a3
    # сброс
    assert c.post(f"/api/admin/traffic/{a1}/action", json={"action": "reset_traffic"}).status_code == 200
    assert s.traffic(a1)["used_bytes"] == 0
    assert s.traffic(a1)["topup_bytes"] == 333
    assert c.post(f"/api/admin/traffic/{a1}/action", json={"action": "boom"}).status_code == 400
    assert c.post("/api/admin/traffic/nope/action", json={"action": "reset_traffic"}).status_code == 404
    assert "traffic:reset" in [i["action"] for i in c.get("/api/admin/audit").json()["items"]]
