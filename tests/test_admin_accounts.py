"""Тесты аккаунтов + биллинга админ-панели (этап 4.3): индивидуальные переопределения
(лимит правил / цена / трафик) и их проводка, admin-API аккаунтов/подписок/кодов.

Запуск:  .venv/bin/python -m pytest tests/test_admin_accounts.py -q
"""
import asyncio
import os
import sys
import tempfile
import time
from pathlib import Path
from urllib.parse import parse_qs, urlparse

_TMP = Path(tempfile.mkdtemp(prefix="admacc_"))
os.environ.setdefault("MESYNC_DATA_DIR", str(_TMP / "control"))
os.environ.setdefault("MESYNC_SESSION_SECRET", "test-secret")
os.environ.setdefault("MESYNC_AUTH_INSECURE", "1")
os.environ.setdefault("MESYNC_ADMIN_PASSWORD", "pw")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "111:TESTTOKEN")
os.environ.setdefault("MAX_BOT_TOKEN", "maxtoken")

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from control import config, rules as rules_mod  # noqa: E402
from control import security  # noqa: E402
from control.activation import Activation  # noqa: E402
from control.billing import Billing  # noqa: E402
from control.integration import RuleDispatcher  # noqa: E402
from control.store import ControlStore  # noqa: E402

run = asyncio.run
PW = "pw"


# ================= эффективные значения переопределений =================
def test_override_getters_default_and_override():
    s = ControlStore(_TMP / f"o_{time.time_ns()}.json")
    acc = run(s.get_or_create_account("max", 1, None))["id"]
    assert s.rule_limit_for(acc) == config.RULE_LIMIT
    assert s.price_for(acc) == config.PRICE_RUB
    assert s.traffic_limit_for(acc) == config.TRAFFIC_LIMIT_BYTES
    run(s.set_account_overrides(acc, {"rule_limit": 25, "price": 499,
                                      "traffic_limit": 1024 ** 4}))
    assert s.rule_limit_for(acc) == 25 and s.price_for(acc) == 499
    assert s.traffic_limit_for(acc) == 1024 ** 4
    run(s.set_account_overrides(acc, {"price": None}))   # снять только цену
    assert s.price_for(acc) == config.PRICE_RUB and s.rule_limit_for(acc) == 25


def test_rule_limit_override_flows_to_list_rules():
    s = ControlStore(_TMP / f"rl_{time.time_ns()}.json")
    acc = run(s.get_or_create_account("max", 2, None))["id"]
    assert run(rules_mod.list_rules(s, acc))["limit"] == config.RULE_LIMIT
    run(s.set_account_overrides(acc, {"rule_limit": 3}))
    assert run(rules_mod.list_rules(s, acc))["limit"] == 3


def test_traffic_override_flows_to_decide():
    s = ControlStore(_TMP / f"tr_{time.time_ns()}.json")
    acc = run(s.get_or_create_account("max", 3, None))["id"]
    run(s.set_subscription(acc, {"status": "active"}))
    run(s.add_rule({"account_id": acc, "a": {"messenger": "max", "chat_id": "100"},
                    "b": {"messenger": "tg", "chat_id": "200"}, "dir": "both", "status": "active"}))
    d = RuleDispatcher(s)
    assert d.decide("max", "100", None)[0]["media_allowed"] is True   # дефолтный лимит велик
    run(s.set_account_overrides(acc, {"traffic_limit": 1000}))
    run(s.add_traffic(acc, 2000))                                     # израсходовано выше лимита
    assert d.decide("max", "100", None)[0]["media_allowed"] is False  # персональный лимит бьёт


def test_override_zero_is_honored_not_default():
    # Явно заданный 0 — это оверрайд (комп/запрет медиа), а не «пусто» → не должен падать
    # обратно на дефолт из config (регресс ревью 4.3: было `int(v) if v else default`).
    s = ControlStore(_TMP / f"z_{time.time_ns()}.json")
    acc = run(s.get_or_create_account("max", 91, None))["id"]
    run(s.set_account_overrides(acc, {"price": 0, "traffic_limit": 0}))
    assert s.price_for(acc) == 0
    assert s.traffic_limit_for(acc) == 0
    # деталь API не должна себе противоречить: raw и effective совпадают
    assert s.price_for(acc) == 0 != config.PRICE_RUB


def test_accounts_search_by_formatted_phone():
    # Телефон хранится цифрами; запрос вида «+7 999 …» должен находить (регресс ревью 4.3).
    s = ControlStore(_TMP / f"ph_{time.time_ns()}.json")
    acc = run(s.get_or_create_account("max", 92, "79990001122"))["id"]
    assert s.accounts_page(q="+7 999 000-11-22")["total"] == 1
    assert s.accounts_page(q="79990001122")["items"][0]["id"] == acc
    assert s.accounts_page(q="+7 (999) 000")["total"] == 1


def test_traffic_notify_uses_effective_limit():
    # Порог уведомления берётся из эффективного лимита аккаунта, а не из config-дефолта
    # (регресс ревью 4.3): при персональном лимите 1000 Б расход 1000 Б → «исчерпан».
    s = ControlStore(_TMP / f"tn_{time.time_ns()}.json")
    acc = run(s.get_or_create_account("max", 93, None))["id"]
    run(s.set_account_overrides(acc, {"traffic_limit": 1000}))
    run(s.add_traffic(acc, 1000))
    d = RuleDispatcher(s)
    run(d._maybe_traffic_notify(acc))
    titles = [n.get("title", "") for n in s.notifications_of(acc)]
    assert any("исчерпан" in t for t in titles)


class FakeYk:
    enabled = True

    def __init__(self):
        self.amounts = []

    async def create_payment(self, *, amount_rub, **k):
        self.amounts.append(amount_rub)
        return {"id": "p1", "status": "pending", "confirmation": {"confirmation_token": "t"}}


def test_price_override_flows_to_billing_charge():
    s = ControlStore(_TMP / f"pr_{time.time_ns()}.json")
    a1 = run(s.get_or_create_account("max", 41, None))["id"]   # дефолтная цена
    a2 = run(s.get_or_create_account("max", 42, None))["id"]
    run(s.set_account_overrides(a2, {"price": 499}))            # персональная цена
    yk = FakeYk()
    b = Billing(s, yk, price_rub=299, trial_days=7, return_url="u")

    async def scenario():
        await b.start_checkout(a1, "pay", autopay=False)
        await b.start_checkout(a2, "pay", autopay=False)
    run(scenario())
    assert yk.amounts == [299, 499]                             # персональная цена ушла в списание


# ================= admin-API аккаунтов =================
def _client():
    from fastapi.testclient import TestClient
    from control.api import create_app, set_settings, set_activation
    from control.settings import Settings
    config.ADMIN_PASSWORD = "pw"
    config.AUTH_INSECURE = True
    s = ControlStore(_TMP / f"api_{time.time_ns()}.json")
    set_settings(Settings(s))
    set_activation(Activation(s))
    c = TestClient(create_app(s))
    r = c.post("/api/admin/login", json={"password": "pw"})
    assert r.status_code == 200, r.text
    return c, s


def test_accounts_require_auth():
    from fastapi.testclient import TestClient
    from control.api import create_app, set_settings
    from control.settings import Settings
    s = ControlStore(_TMP / f"na_{time.time_ns()}.json")
    set_settings(Settings(s))
    c = TestClient(create_app(s))
    assert c.get("/api/admin/accounts").status_code == 401
    assert c.get("/api/admin/subscriptions").status_code == 401


def test_accounts_search_and_detail():
    c, s = _client()
    acc = run(s.get_or_create_account("max", 800111, "79990001122"))["id"]
    page = c.get("/api/admin/accounts", params={"q": "79990001122"}).json()
    assert page["total"] == 1 and page["items"][0]["id"] == acc
    assert page["items"][0]["overrides"] == {"rule_limit": None, "price": None, "traffic_limit": None}
    d = c.get(f"/api/admin/accounts/{acc}").json()
    assert d["account"]["id"] == acc
    assert d["overrides"]["effective"]["price"] == config.PRICE_RUB
    assert d["strikes24h"] == 0
    assert c.get("/api/admin/accounts/nope").status_code == 404


def test_accounts_profile_prefers_max_name_and_avatar_then_tg():
    c, s = _client()
    acc = run(s.get_or_create_account("tg", 8001111, "79990001122"))["id"]
    run(s.link_identity("max", 9002222, acc))
    run(s.update_identity_profile("tg", 8001111, {
        "id": 8001111, "first_name": "Таня", "last_name": "Телеграм", "username": "t_tg",
    }))
    run(s.update_identity_profile("max", 9002222, {
        "id": 9002222, "first_name": "Максим", "last_name": "Максов", "username": "m_max",
        "avatar_url": "https://cdn.example/avatar-small.jpg",
    }))

    page = c.get("/api/admin/accounts", params={"q": "79990001122"}).json()
    p = page["items"][0]["profile"]
    assert p["name"] == "Максим Максов"
    assert p["username"] == "m_max"
    assert p["messenger"] == "max"
    assert p["avatar"] == "https://cdn.example/avatar-small.jpg"

    detail = c.get(f"/api/admin/accounts/{acc}").json()
    assert detail["profile"]["name"] == "Максим Максов"


def test_accounts_profile_falls_back_to_tg_when_max_has_no_avatar_or_name():
    c, s = _client()
    acc = run(s.get_or_create_account("max", 9003333, "79990001123"))["id"]
    run(s.link_identity("tg", 8003333, acc))
    run(s.update_identity_profile("tg", 8003333, {
        "id": 8003333, "first_name": "Таня", "last_name": "Телеграм", "username": "t_tg",
    }))

    page = c.get("/api/admin/accounts", params={"q": "79990001123"}).json()
    p = page["items"][0]["profile"]
    assert p["name"] == "Таня Телеграм"
    assert p["username"] == "t_tg"
    assert p["messenger"] == "tg"
    u = urlparse(p["avatar"])
    qs = parse_qs(u.query)
    assert u.path == f"/api/admin/accounts/{acc}/avatar"
    assert security.decode_account_avatar_token(qs["t"][0]) == acc


def test_accounts_profile_exposes_tg_avatar_without_cached_profile():
    c, s = _client()
    acc = run(s.get_or_create_account("tg", 8005555, "79990001125"))["id"]

    page = c.get("/api/admin/accounts", params={"q": "79990001125"}).json()
    p = page["items"][0]["profile"]
    assert p["name"] is None
    assert p["messenger"] == "tg"
    u = urlparse(p["avatar"])
    qs = parse_qs(u.query)
    assert u.path == f"/api/admin/accounts/{acc}/avatar"
    assert security.decode_account_avatar_token(qs["t"][0]) == acc
    assert "v=tg-8005555" in p["avatar"]


def test_account_avatar_signed_url_works_without_admin_cookie():
    from fastapi.testclient import TestClient
    from control.api import set_account_avatar_fetcher

    c, s = _client()
    acc = run(s.get_or_create_account("tg", 8006666, "79990001126"))["id"]
    page = c.get("/api/admin/accounts", params={"q": "79990001126"}).json()
    avatar_url = page["items"][0]["profile"]["avatar"]
    calls = []

    async def fake(messenger, user_id, profile):
        calls.append((messenger, str(user_id), profile))
        return "image/png", b"TGPIC", None

    set_account_avatar_fetcher(fake)
    try:
        anon = TestClient(c.app)
        r = anon.get(avatar_url)
    finally:
        set_account_avatar_fetcher(None)
    assert r.status_code == 200, r.text
    assert r.content == b"TGPIC"
    assert calls == [("tg", "8006666", {})]


def test_account_avatar_endpoint_uses_max_then_tg_choice():
    from control.api import set_account_avatar_fetcher

    c, s = _client()
    acc = run(s.get_or_create_account("tg", 8004444, "79990001124"))["id"]
    run(s.link_identity("max", 9004444, acc))
    run(s.update_identity_profile("tg", 8004444, {"id": 8004444, "first_name": "Таня"}))
    run(s.update_identity_profile("max", 9004444, {
        "id": 9004444, "first_name": "Максим", "avatar_url": "https://cdn.example/max.jpg",
    }))
    calls = []

    async def fake(messenger, user_id, profile):
        calls.append((messenger, str(user_id), profile.get("avatar_url")))
        return "image/jpeg", b"MAXPIC", None

    set_account_avatar_fetcher(fake)
    try:
        r = c.get(f"/api/admin/accounts/{acc}/avatar")
    finally:
        set_account_avatar_fetcher(None)
    assert r.status_code == 200
    assert r.content == b"MAXPIC"
    assert calls == [("max", "9004444", "https://cdn.example/max.jpg")]


def test_account_actions_overrides_and_block():
    c, s = _client()
    acc = run(s.get_or_create_account("max", 800222, None))["id"]
    # переопределения
    r = c.post(f"/api/admin/accounts/{acc}/action",
               json={"action": "set_overrides", "rule_limit": 25, "price": 499, "traffic_limit": 1099511627776})
    assert r.status_code == 200 and r.json()["overrides"]["price"] == 499
    assert s.price_for(acc) == 499 and s.rule_limit_for(acc) == 25
    # снять цену
    c.post(f"/api/admin/accounts/{acc}/action", json={"action": "set_overrides", "price": None})
    assert s.price_for(acc) == config.PRICE_RUB
    # блокировка
    c.post(f"/api/admin/accounts/{acc}/action", json={"action": "block"})
    assert s.account_blocked(acc) is True
    c.post(f"/api/admin/accounts/{acc}/action", json={"action": "unblock"})
    assert s.account_blocked(acc) is False
    # неизвестное действие
    assert c.post(f"/api/admin/accounts/{acc}/action", json={"action": "boom"}).status_code == 400
    # аудит
    assert any(a.startswith("account:") for a in
               [i["action"] for i in c.get("/api/admin/audit").json()["items"]])


def test_account_grant_month_and_issue_code():
    c, s = _client()
    acc = run(s.get_or_create_account("max", 800333, None))["id"]
    assert s.subscription(acc).get("status") != "active"
    r = c.post(f"/api/admin/accounts/{acc}/action", json={"action": "grant_month"})
    assert r.status_code == 200 and r.json().get("until")
    assert s.subscription(acc)["status"] == "active"
    r2 = c.post(f"/api/admin/accounts/{acc}/action", json={"action": "issue_code"})
    code = r2.json().get("code")
    assert code and code in s.activation_codes_stats()["unused"]


def test_account_disable_subscription_action():
    c, s = _client()
    acc = run(s.get_or_create_account("max", 800334, None))["id"]
    run(s.set_subscription(acc, {
        "status": "active",
        "renew_at": "2033-05-18",
        "paid_until": 2000000000,
        "trial": True,
        "trial_used": True,
        "autopay": True,
        "payment_method_id": "pm_saved",
        "payment_method_title": "Карта •1234",
        "pending": {"kind": "purchase", "id": "p1", "autopay": True},
        "renew_attempts": 2,
        "renew_retry_at": 1999999999,
        "last_error": {"code": "old_error"},
    }))

    r = c.post(f"/api/admin/accounts/{acc}/action", json={"action": "disable_subscription"})

    assert r.status_code == 200, r.text
    body = r.json()
    assert body["disabled"] is True
    assert body["subscription"]["status"] == "inactive"
    assert body["subscription"]["autopay"] is False
    assert body["subscription"]["methodTitle"] is None
    assert body["subscription"]["paidUntil"] is None
    assert body["subscription"]["pendingKind"] is None
    sub = s.subscription(acc)
    assert sub["renew_at"] is None and sub["paid_until"] == 0
    assert sub["payment_method_id"] is None and sub["payment_method_title"] is None
    assert sub["pending"] is None and sub["last_error"] is None
    assert sub["renew_attempts"] == 0 and sub["renew_retry_at"] == 0
    assert sub["trial"] is False and sub["trial_used"] is True
    assert any(i["action"] == "account:disable_subscription"
               for i in c.get("/api/admin/audit").json()["items"])


def test_account_disable_autopay_keeps_paid_period():
    c, s = _client()
    acc = run(s.get_or_create_account("max", 800335, None))["id"]
    run(s.set_subscription(acc, {
        "status": "active",
        "renew_at": "2033-05-18",
        "paid_until": 2000000000,
        "trial": False,
        "trial_used": True,
        "autopay": True,
        "payment_method_id": "pm_saved",
        "payment_method_title": "Карта •1234",
        "pending": {"kind": "bind", "id": "pm_pending", "autopay": True},
        "renew_attempts": 2,
        "renew_retry_at": 1999999999,
        "last_error": {"code": "old_error"},
    }))

    r = c.post(f"/api/admin/accounts/{acc}/action", json={"action": "disable_autopay"})

    assert r.status_code == 200, r.text
    body = r.json()
    assert body["annulled"] is False
    assert body["autopay"] is False
    assert body["subscription"]["status"] == "active"
    assert body["subscription"]["paidUntil"] == 2000000000 * 1000
    assert body["subscription"]["autopay"] is False
    assert body["subscription"]["methodTitle"] is None
    assert body["subscription"]["pendingKind"] is None
    sub = s.subscription(acc)
    assert sub["status"] == "active" and sub["renew_at"] == "2033-05-18"
    assert sub["paid_until"] == 2000000000 and sub["trial"] is False
    assert sub["payment_method_id"] is None and sub["payment_method_title"] is None
    assert sub["pending"] is None and sub["last_error"] is None
    assert sub["renew_attempts"] == 0 and sub["renew_retry_at"] == 0
    assert any(i["action"] == "account:disable_autopay"
               for i in c.get("/api/admin/audit").json()["items"])


def test_account_disable_autopay_annuls_trial():
    c, s = _client()
    acc = run(s.get_or_create_account("max", 800336, None))["id"]
    run(s.set_subscription(acc, {
        "status": "active",
        "renew_at": "2033-05-18",
        "paid_until": 2000000000,
        "trial": True,
        "trial_used": True,
        "autopay": True,
        "payment_method_id": "pm_trial",
        "payment_method_title": "Карта •4321",
    }))

    before = int(time.time())
    r = c.post(f"/api/admin/accounts/{acc}/action", json={"action": "disable_autopay"})
    after = int(time.time())

    assert r.status_code == 200, r.text
    body = r.json()
    assert body["annulled"] is True
    assert body["subscription"]["status"] == "inactive"
    assert body["subscription"]["trial"] is False
    assert body["subscription"]["autopay"] is False
    sub = s.subscription(acc)
    assert sub["status"] == "inactive" and sub["trial"] is False
    assert sub["autopay"] is False and sub["payment_method_id"] is None
    assert before <= int(sub["paid_until"]) <= after
    assert sub["renew_at"] == time.strftime("%Y-%m-%d", time.gmtime(sub["paid_until"]))


def test_subscriptions_and_codes():
    c, s = _client()
    a1 = run(s.get_or_create_account("max", 800444, None))["id"]
    run(s.set_subscription(a1, {"status": "active"}))
    run(s.set_account_overrides(a1, {"price": 499}))
    run(s.get_or_create_account("tg", 800555, None))
    active = c.get("/api/admin/subscriptions", params={"status": "active"}).json()
    assert active["total"] == 1 and active["items"][0]["account_id"] == a1
    assert active["items"][0]["plan"] == "individual"
    assert active["items"][0]["planName"] == "Индивидуальный"
    assert active["items"][0]["price"] == 499
    gen = c.post("/api/admin/codes", json={"count": 3}).json()
    assert len(gen["codes"]) == 3
    code = gen["codes"][0]
    assert c.post(f"/api/admin/codes/{code}/action", json={"action": "revoke"}).status_code == 200
    stats = c.get("/api/admin/codes").json()
    assert stats["total"] >= 3
    assert code not in stats["unused"]
    assert stats["revoked"][0]["code"] == code
    assert run(s.claim_activation_code(code, a1)) == "unavailable"
    assert c.post(f"/api/admin/codes/{gen['codes'][1]}/action", json={"action": "boom"}).status_code == 400
