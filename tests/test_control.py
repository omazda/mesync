"""Тесты control-API: хранилище, безопасность, источники, правила, движок, API.

Запуск:  .venv/bin/python -m pytest tests/test_control.py -q
(PYTHONPATH=src; окружение настраивается ниже до импорта пакета control.)
"""
import asyncio
import hashlib
import hmac
import json
import logging
import os
import sys
import tempfile
import time
from pathlib import Path
from urllib.parse import urlencode

# --- окружение ДО импорта control (config читает env на уровне модуля) ---
_TMP = Path(tempfile.mkdtemp(prefix="ctl_test_"))
os.environ["MESYNC_DATA_DIR"] = str(_TMP / "control")
os.environ["MAX_OWNERSHIP_FILE"] = str(_TMP / "max_ownership.json")
os.environ["TG_OWNERSHIP_FILE"] = str(_TMP / "tg_ownership.json")
os.environ["MESYNC_AUTH_INSECURE"] = "1"
os.environ.setdefault("MESYNC_SESSION_SECRET", "test-secret")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "111:TESTTOKEN")
os.environ.setdefault("MAX_BOT_TOKEN", "maxtoken")
os.environ.setdefault("MESYNC_TG_BOT_URL", "https://t.me/test_mesync_bot")
os.environ.setdefault("MESYNC_MAX_BOT_URL", "https://max.ru/test_mesync_bot")

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from control import config, rules as rules_mod, security, sources as sources_mod  # noqa: E402
from control.integration import (  # noqa: E402
    RuleDispatcher, html_for_telegram, html_for_max, LINK_NOTE,
    FORWARDED_BUTTON_NOTICE, FORWARDED_BUTTON_PAYLOAD,
    _max_send_transient, _declared_size, _forward_html)
from control.message_map import MessageMap  # noqa: E402
from control.sent_index import SentIndex  # noqa: E402
from control.store import ControlStore  # noqa: E402

run = asyncio.run


def _fresh_sent_index(ttl=3600, max_entries=1000):
    return SentIndex(_TMP / f"sent_{time.time_ns()}.json", ttl_seconds=ttl, max_entries=max_entries)


def _fresh_store():
    p = _TMP / f"store_{time.time_ns()}.json"
    return ControlStore(p)


def _signed_max_contact(user_id, phone=None, auth_date=None):
    """Реальный контракт MAX requestContact даже при MESYNC_AUTH_INSECURE=1."""
    if phone is None:
        suffix = int("".join(ch for ch in str(user_id) if ch.isdigit()) or "0") % 1_000_000_000
        phone = f"79{suffix:09d}"
    phone = "".join(ch for ch in str(phone) if ch.isdigit())
    if auth_date is None:
        auth_date = int(time.time())
    msg = f"authDate={auth_date}\nphone={phone}\nuserId={user_id}"
    signature = hmac.new(config.MAX_BOT_TOKEN.encode(), msg.encode(), hashlib.sha256).hexdigest()
    return {"messenger": "max", "userId": user_id, "phone": phone,
            "authDate": auth_date, "hash": signature}


def _auth_contact(client, user_id, phone=None):
    return client.post("/api/auth/contact", json=_signed_max_contact(user_id, phone))


def _host_auth(user_id, messenger="max"):
    return {"messenger": messenger, "userId": user_id, "initData": ""}


def _signed_initdata(user_id, token):
    params = {"auth_date": str(int(time.time())),
              "user": json.dumps({"id": user_id}, separators=(",", ":"))}
    dcs = "\n".join(f"{key}={params[key]}" for key in sorted(params))
    secret = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
    params["hash"] = hmac.new(secret, dcs.encode(), hashlib.sha256).hexdigest()
    return urlencode(params)


def _accept_legal(client, headers):
    r = client.post("/api/legal/accept", json={
        "termsVersion": config.LEGAL_TERMS_VERSION,
        "privacyVersion": config.LEGAL_PRIVACY_VERSION,
        "source": "test",
    }, headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


def test_generated_session_secret_is_private_and_repairs_permissions(tmp_path, monkeypatch):
    secret_path = tmp_path / "control" / "session_secret"
    monkeypatch.delenv("MESYNC_SESSION_SECRET", raising=False)
    monkeypatch.setattr(config, "SESSION_SECRET_FILE", secret_path)

    generated = config.session_secret()
    assert len(generated) == 64
    assert secret_path.read_text(encoding="utf-8") == generated
    assert secret_path.stat().st_mode & 0o777 == 0o600

    secret_path.chmod(0o644)
    assert config.session_secret() == generated
    assert secret_path.stat().st_mode & 0o777 == 0o600


# ---------------- store ----------------
def test_account_create_and_identity_link():
    s = _fresh_store()
    a = run(s.get_or_create_account("max", 777, "+7 900 123-45-67"))
    assert a["phone"] == "79001234567"
    # та же идентичность → тот же аккаунт
    a2 = run(s.get_or_create_account("max", 777, None))
    assert a2["id"] == a["id"]
    # другой мессенджер с тем же номером БЕЗ подтверждения → отдельный аккаунт
    # (авто-слияние по неподтверждённому телефону убрано — защита от угона)
    a3 = run(s.get_or_create_account("tg", 555, "79001234567"))
    assert a3["id"] != a["id"]
    # явное связывание идентичностей (как после подтверждённого входа по номеру/OTP)
    run(s.link_identity("tg", 999, a["id"]))
    assert ("tg", "999") in set(s.identities_of(a["id"]))


def test_find_account_by_identity_no_create():
    s = _fresh_store()
    assert s.find_account_by_identity("max", 555) is None        # нет — и НЕ создаём
    assert len(s.table("accounts")) == 0
    acc = run(s.get_or_create_account("max", 555, None))
    assert s.find_account_by_identity("max", 555)["id"] == acc["id"]
    assert s.find_account_by_identity("tg", 555) is None          # другая identity — не находим


def test_registration_lead_tracks_payload_and_reminders():
    s = _fresh_store()
    lead = run(s.upsert_registration_lead(
        "max", 555, chat_id=555, payload="invite_source_1", user={"username": "test_user"},
        stage="started"))
    assert lead["last_payload"] == "invite_source_1"
    assert lead["payload_history"] == [{"payload": "invite_source_1", "ts": lead["last_seen_at"]}]
    assert lead["stage"] == "started" and lead["username"] == "test_user"

    due0 = run(s.due_registration_reminders("max", (1800, 86400),
                                            now=lead["first_seen_at"] + 1799))
    assert due0 == []
    due1 = run(s.due_registration_reminders("max", (1800, 86400),
                                            now=lead["first_seen_at"] + 1800))
    assert len(due1) == 1 and due1[0]["reminder_index"] == 0
    lead2 = run(s.mark_registration_reminder_sent("max", 555, 0,
                                                  now=lead["first_seen_at"] + 1801))
    assert lead2["stage"] == "reminded"
    assert lead2["reminders_sent"] == [{"index": 0, "ts": lead["first_seen_at"] + 1801}]
    assert run(s.due_registration_reminders("max", (1800, 86400),
                                            now=lead["first_seen_at"] + 2000)) == []
    due2 = run(s.due_registration_reminders("max", (1800, 86400),
                                            now=lead["first_seen_at"] + 86400))
    assert len(due2) == 1 and due2[0]["reminder_index"] == 1

    acc = run(s.confirm_identity_phone("max", 555, "+7 900 000-05-55"))
    assert run(s.due_registration_reminders("max", (1800, 86400),
                                            now=lead["first_seen_at"] + 90000)) == []
    registered = s.registration_lead("max", 555)
    assert registered["stage"] == "registered"
    assert registered["account_id"] == acc["id"]

    lead3 = run(s.upsert_registration_lead("max", 555, payload="invite_source_2", stage="started"))
    assert lead3["stage"] == "registered"                       # не откатываем stage назад
    assert [x["payload"] for x in lead3["payload_history"]] == ["invite_source_1", "invite_source_2"]


def test_registration_reminder_worker_marks_only_successful_send():
    from control.registration_reminders import RegistrationReminderWorker

    s = _fresh_store()
    lead = run(s.upsert_registration_lead("max", 555, chat_id=555, payload="invite"))
    sent = []

    async def send(item, index):
        sent.append((item["user_id"], index))
        return {"ok": True}

    worker = RegistrationReminderWorker(
        s, messenger="max", delays=(1800,), send=send, interval=5, clock=lambda: lead["first_seen_at"] + 1800)
    assert run(worker.tick()) == 1
    assert sent == [("555", 0)]
    assert s.registration_lead("max", 555)["reminders_sent"][0]["index"] == 0
    assert run(worker.tick()) == 0

    lead777 = run(s.upsert_registration_lead("max", 777, chat_id=777, payload="invite"))
    failures = []

    async def no_send(item, index):
        failures.append((item["user_id"], index))
        return None

    failed_worker = RegistrationReminderWorker(
        s, messenger="max", delays=(1800,), send=no_send, interval=5,
        clock=lambda: lead777["first_seen_at"] + 1800)
    assert run(failed_worker.tick()) == 0
    assert failures == [("777", 0)]
    assert "reminders_sent" not in s.registration_lead("max", 777)


def test_registration_reminder_worker_uses_wall_clock_slots():
    from control.registration_reminders import RegistrationReminderWorker

    s = _fresh_store()
    now = {"value": 0.0}

    async def send(_item, _index):
        return {"ok": True}

    worker = RegistrationReminderWorker(
        s, messenger="max", delays=(1800,), send=send, interval=1800,
        clock=lambda: now["value"])
    assert worker.seconds_until_next_slot(include_current=True) == 0
    assert worker.seconds_until_next_slot(include_current=False) == 1800
    now["value"] = 1
    assert worker.seconds_until_next_slot(include_current=True) == 1799
    now["value"] = 1799.5
    assert worker.seconds_until_next_slot(include_current=True) == 0.5
    now["value"] = 1800
    assert worker.seconds_until_next_slot(include_current=True) == 0
    assert worker.seconds_until_next_slot(include_current=False) == 1800
    now["value"] = 1810
    assert worker.seconds_until_next_slot(include_current=True) == 1790


def test_auth_silent_restores_existing_only():
    # Тихий вход по initData: восстанавливает сессию ВЕРНУВШЕГОСЯ пользователя (тот же аккаунт),
    # нового НЕ создаёт (exists:false → фронт покажет обычный вход). Так сессия переживает
    # перезагрузку без зависимости от localStorage.
    from fastapi.testclient import TestClient
    from control.api import create_app
    s = _fresh_store()
    c = TestClient(create_app(s))
    r0 = c.post("/api/auth/silent", json={"messenger": "max", "userId": 555})
    assert r0.status_code == 200 and r0.json() == {"exists": False}
    assert len(s.table("accounts")) == 0                          # тихий вход НИЧЕГО не создал
    legacy = run(s.get_or_create_account("max", 556, None))
    assert c.post("/api/auth/silent", json={"messenger": "max", "userId": 556}).json() == {"exists": False}
    legacy_h = {"Authorization": f"Bearer {security.make_session(legacy['id'])}"}
    assert c.get("/api/account", headers=legacy_h).status_code == 401  # старый no-phone токен закрыт
    r1 = _auth_contact(c, 555)
    acc_id = r1.json()["account"]["id"]                           # обычный вход создал аккаунт
    r2 = c.post("/api/auth/silent", json={"messenger": "max", "userId": 555})
    assert r2.status_code == 200 and r2.json()["exists"] is True and r2.json()["token"]
    assert r2.json()["account"]["id"] == acc_id                   # восстановлен ТОТ ЖЕ аккаунт
    H = {"Authorization": f"Bearer {r2.json()['token']}"}
    assert c.get("/api/account", headers=H).json()["id"] == acc_id  # токен валиден


def test_auth_contact_never_creates_without_confirmed_phone():
    from fastapi.testclient import TestClient
    from control.api import create_app

    s = _fresh_store()
    c = TestClient(create_app(s))
    missing = c.post("/api/auth/contact", json={"messenger": "max", "userId": 700})
    assert missing.status_code == 400 and missing.json()["detail"]["code"] == "contact_required"
    bad = c.post("/api/auth/contact", json={
        "messenger": "max", "userId": 700, "phone": "79000000700",
        "authDate": int(time.time()), "hash": "bad",
    })
    assert bad.status_code == 400 and bad.json()["detail"]["code"] == "bad_contact"
    tg_missing = c.post("/api/auth/contact", json={"messenger": "tg", "userId": 701})
    assert tg_missing.status_code == 409 and tg_missing.json()["detail"]["code"] == "contact_required"
    assert s.table("accounts") == {} and s.table("identities") == {}

    # После Telegram self-contact poller заранее фиксирует номер; HTTP лишь выдаёт сессию.
    confirmed = run(s.confirm_identity_phone("tg", 701, "+7 900 000-07-01"))
    tg_ok = c.post("/api/auth/contact", json={"messenger": "tg", "userId": 701})
    assert tg_ok.status_code == 200 and tg_ok.json()["account"]["id"] == confirmed["id"]


def test_max_contact_diagnostic_requires_signed_host_and_logs_safe_code(caplog):
    import httpx
    from control.api import create_app

    s = _fresh_store()
    app = create_app(s)
    uid = 703
    payload = {
        "messenger": "max",
        "userId": uid,
        "initData": _signed_initdata(uid, config.MAX_BOT_TOKEN),
        "errorCode": "client.request_phone.request_error",
        "platform": "android\nforged",
        "bridgeVersion": "26.2.8",
    }

    async def scenario():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            ok_response = await client.post("/api/auth/contact/diagnostic", json=payload)
            bad_response = await client.post(
                "/api/auth/contact/diagnostic", json={**payload, "initData": "broken"})
        return ok_response, bad_response

    old = config.AUTH_INSECURE
    config.AUTH_INSECURE = False
    try:
        with caplog.at_level(logging.WARNING, logger="control.api"):
            ok, bad = run(scenario())
        assert ok.status_code == 200 and ok.json() == {"ok": True}
        assert bad.status_code == 400 and bad.json()["detail"]["code"] == "bad_signature"
    finally:
        config.AUTH_INSECURE = old

    messages = [record.getMessage() for record in caplog.records
                if "MAX requestContact frontend diagnostic" in record.getMessage()]
    assert messages == [
        "MAX requestContact frontend diagnostic: "
        "code=client.request_phone.request_error platform=android_forged bridge_version=26.2.8"
    ]
    assert s.table("accounts") == {} and s.table("identities") == {}


def test_tg_auth_contact_waits_for_delayed_self_contact_update():
    import httpx
    from control.api import create_app

    s = _fresh_store()

    async def scenario():
        async def delayed_contact():
            await asyncio.sleep(0.15)
            return await s.confirm_identity_phone("tg", 702, "+7 900 000-07-02")

        task = asyncio.create_task(delayed_contact())
        transport = httpx.ASGITransport(app=create_app(s))
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/api/auth/contact", json={
                "messenger": "tg", "userId": 702, "contactShared": True,
            })
        confirmed = await task
        return response, confirmed

    response, confirmed = run(scenario())
    assert response.status_code == 200, response.text
    assert response.json()["account"]["id"] == confirmed["id"]


def test_otp_existing_account_links_current_identity_and_merges_legacy_duplicate():
    from fastapi.testclient import TestClient
    from control.api import create_app, set_notifier

    s = _fresh_store()
    phone = "79001234567"
    target = run(s.get_or_create_account("tg", 101, phone))["id"]
    legacy = run(s.get_or_create_account("max", 202, None))["id"]
    run(s.add_traffic(legacy, 1234))
    delivered = []

    async def notify(messenger, uid, text):
        delivered.append((messenger, str(uid), text))

    set_notifier(notify)
    try:
        c = TestClient(create_app(s))
        unknown = c.post("/api/auth/otp/request", json={
            **_host_auth(202), "phone": "+7 999 999-99-99",
        })
        assert unknown.status_code == 404
        assert "79999999999" not in s.table("otp")

        requested = c.post("/api/auth/otp/request", json={
            **_host_auth(202), "phone": "+7 900 123-45-67",
        })
        assert requested.status_code == 200 and delivered and delivered[0][:2] == ("tg", "101")
        code = s.table("otp")[phone]["code"]
        verified = c.post("/api/auth/otp/verify", json={
            **_host_auth(202), "phone": phone, "code": code,
        })
        assert verified.status_code == 200, verified.text
        assert verified.json()["account"]["id"] == target
        assert legacy not in s.table("accounts")
        assert {(m, u) for m, u in s.identities_of(target)} == {("tg", "101"), ("max", "202")}
        assert s.traffic(target)["used_bytes"] == 1234
        h = {"Authorization": f"Bearer {verified.json()['token']}"}
        assert c.get("/api/account", headers=h).status_code == 200
    finally:
        set_notifier(None)


def test_activation_code_format_and_normalize():
    # Формат кода XXXX-XXXX-XXXX ([A-Za-z0-9], регистрозависимый); нормализация ввода
    # терпима к пробелам и расстановке дефисов, но НЕ меняет регистр.
    import re
    from control.activation import generate_code, normalize_code
    for _ in range(50):
        assert re.fullmatch(r"[A-Za-z0-9]{4}-[A-Za-z0-9]{4}-[A-Za-z0-9]{4}", generate_code())
    assert len({generate_code() for _ in range(1000)}) == 1000   # без коллизий на выборке
    assert normalize_code("abcd1234WXYZ") == "abcd-1234-WXYZ"        # без дефисов
    assert normalize_code(" ab cd-1234 WX YZ ") == "abcd-1234-WXYZ"  # пробелы/дефисы где угодно
    assert normalize_code("ABCD-1234-wxyz") == "ABCD-1234-wxyz"      # регистр сохраняется
    for bad in ("", None, "abc", "abcd-1234-wxy", "abcd_1234_wxyz",
                "абвг-1234-wxyz", "abcd-1234-wxyz9"):
        assert normalize_code(bad) is None


def test_activation_store_use_once_and_case_sensitive():
    # Код одноразовый (атомарное «проверить и потратить» под локом стора) и регистрозависимый.
    s = _fresh_store()
    run(s.add_activation_codes(["AbCd-1234-WxYz"]))
    assert run(s.use_activation_code("abcd-1234-wxyz", "a1")) is False   # не тот регистр
    assert run(s.use_activation_code("AbCd-1234-WxYz", "a1")) is True
    assert run(s.use_activation_code("AbCd-1234-WxYz", "a2")) is False   # уже использован
    st = s.activation_codes_stats()
    assert st["total"] == 1 and st["unused"] == [] and st["used"][0]["used_by"] == "a1"


def test_activation_code_revoke_blocks_unused_code():
    from control.store import ACTIVATION_CODE_TTL

    s = _fresh_store()
    created = 1_600_000_000
    run(s.add_activation_codes(["AbCd-1234-WxYz"], created_at=created))
    revoked_at = created + 100
    assert run(s.revoke_activation_code("AbCd-1234-WxYz", now=revoked_at)) == "revoked"
    assert run(s.use_activation_code("AbCd-1234-WxYz", "a1")) is False
    st = s.activation_codes_stats()
    assert st["unused"] == [] and st["used"] == []
    assert st["revoked"] == [{
        "code": "AbCd-1234-WxYz",
        "created_at": created,
        "expires_at": created + ACTIVATION_CODE_TTL,
        "revoked_at": revoked_at,
    }]


def test_activation_code_expires_after_30_days_without_becoming_used():
    from control.store import ACTIVATION_CODE_TTL

    s = _fresh_store()
    created = 1_700_000_000
    code = "Old1-Code-0001"
    run(s.add_activation_codes([code], created_at=created))
    # До последней секунды код свободен; ровно на границе 30 суток — уже истёк.
    assert s.activation_codes_stats(now=created + ACTIVATION_CODE_TTL - 1)["unused"] == [code]
    assert run(s.claim_activation_code(
        code, "a1", now=created + ACTIVATION_CODE_TTL)) == "expired"
    stats = s.activation_codes_stats(now=created + ACTIVATION_CODE_TTL)
    assert stats["unused"] == [] and stats["used"] == []
    assert stats["expired"] == [{
        "code": code,
        "created_at": created,
        "expires_at": created + ACTIVATION_CODE_TTL,
    }]
    assert s.table("activation_codes")[code]["used_by"] is None

    # Записи, созданные до появления expires_at, получают тот же срок от created_at.
    legacy = "Old2-Code-0002"
    s.table("activation_codes")[legacy] = {
        "created_at": created, "used_by": None, "used_at": None,
    }
    assert run(s.claim_activation_code(
        legacy, "a2", now=created + ACTIVATION_CODE_TTL - 1)) == "used"
    assert s.table("activation_codes")[legacy]["expires_at"] == created + ACTIVATION_CODE_TTL


def test_activation_api_flow_rate_limit_and_admin():
    # Полный флоу: админ генерирует коды (X-Admin-Key), пользователь активирует —
    # месяц подписки БЕЗ привязки; лимит 3 ввода / 10 минут; повторный ввод кода — отказ;
    # активным подписка продлевается от даты истечения.
    from fastapi.testclient import TestClient
    from control import config
    from control.activation import Activation
    from control.api import create_app, set_activation
    from control.billing import add_month
    s = _fresh_store()
    t0 = 1_700_000_000.0
    t = {"now": t0}
    old_key = config.ADMIN_KEY
    config.ADMIN_KEY = "test-admin-key"
    set_activation(Activation(s, clock=lambda: t["now"]))
    try:
        c = TestClient(create_app(s))
        r = _auth_contact(c, 4242)
        H = {"Authorization": f"Bearer {r.json()['token']}"}
        _accept_legal(c, H)
        ADM = {"X-Admin-Key": "test-admin-key"}
        # Админ: без ключа/с неверным ключом — 401; с верным — коды нужного формата.
        assert c.post("/api/admin/activation-codes", json={"count": 2}).status_code == 401
        assert c.post("/api/admin/activation-codes", json={"count": 2},
                      headers={"X-Admin-Key": "wrong"}).status_code == 401
        codes = c.post("/api/admin/activation-codes", json={"count": 2}, headers=ADM).json()["codes"]
        assert len(codes) == 2 and all("-" in x for x in codes)
        # Активация требует сессию.
        assert c.post("/api/pay/activate", json={"code": codes[0]}).status_code == 401
        # Попытка 1: кривой формат → 400 (тоже расходует лимит — антиперебор).
        assert c.post("/api/pay/activate", json={"code": "не-код"}, headers=H).status_code == 400
        # Попытка 2: успех — подписка активна ровно на месяц, привязки/автоплатежа нет.
        r2 = c.post("/api/pay/activate", json={"code": codes[0]}, headers=H)
        assert r2.status_code == 200 and r2.json()["until"] == add_month(t0)
        sub = r2.json()["subscription"]
        assert sub["status"] == "active" and sub["autopay"] is False and sub["methodTitle"] is None
        # Попытка 3: тот же код повторно → уже использован.
        assert c.post("/api/pay/activate", json={"code": codes[0]}, headers=H).status_code == 404
        # Попытка 4 в те же 10 минут → 429 (лимит 3 ввода / 10 минут).
        assert c.post("/api/pay/activate", json={"code": codes[1]}, headers=H).status_code == 429
        # Окно истекло → второй код продлевает АКТИВНУЮ подписку от даты истечения.
        t["now"] = t0 + 601
        r5 = c.post("/api/pay/activate", json={"code": codes[1]}, headers=H)
        assert r5.status_code == 200 and r5.json()["until"] == add_month(add_month(t0))
        # Сводка админа: оба кода использованы.
        st = c.get("/api/admin/activation-codes", headers=ADM).json()
        assert st["total"] == 2 and len(st["used"]) == 2 and st["unused"] == []
        # Хук не подключён (set_activation(None)) → 503.
        set_activation(None)
        assert c.post("/api/pay/activate", json={"code": "AAAA-BBBB-CCCC"},
                      headers=H).status_code == 503
    finally:
        set_activation(None)
        config.ADMIN_KEY = old_key


def test_yandex_market_public_activation_by_phone_is_immediate_and_private():
    # Публичная форма не выдаёт сессию и не создаёт аккаунт: телефон выбирает уже
    # подтверждённый аккаунт, одноразовый код сразу добавляет месяц к текущему сроку.
    # Неизвестный номер и неверный код дают одинаковый ответ — без enumeration.
    from fastapi.testclient import TestClient
    from control import config
    from control.activation import Activation
    from control.api import create_app, set_activation
    from control.billing import add_month

    s = _fresh_store()
    t0 = 1_700_000_000.0
    acc = run(s.get_or_create_account("max", 99001, "79990000009"))
    current_until = add_month(t0)
    run(s.set_subscription(acc["id"], {
        "status": "active", "paid_until": current_until,
        "renew_at": "2023-12-14", "autopay": False,
    }))
    from control.store import ACTIVATION_CODE_TTL
    run(s.add_activation_codes(["YaMk-1234-AbCd", "Next-1234-Code"], created_at=int(t0)))
    run(s.add_activation_codes(["Old1-Code-0001"],
                               created_at=int(t0) - ACTIVATION_CODE_TTL))
    set_activation(Activation(s, clock=lambda: t0))
    try:
        c = TestClient(create_app(s))
        base = {
            "phone": "8 (999) 000-00-09",
            "code": "YaMk-1234-AbCd",
            "termsVersion": config.LEGAL_TERMS_VERSION,
            "privacyVersion": config.LEGAL_PRIVACY_VERSION,
        }

        # Без явного акцепта код не расходуется.
        denied = c.post("/api/market/activate", json=base)
        assert denied.status_code == 428
        assert s.activation_codes_stats(now=int(t0))["unused"] == ["Next-1234-Code", "YaMk-1234-AbCd"]

        # Неизвестный телефон и неверный код не позволяют узнать, существует ли аккаунт.
        missing = c.post("/api/market/activate", json={
            **base, "phone": "+7 900 000-00-01", "legalAccepted": True,
        })
        expired = c.post("/api/market/activate", json={
            **base, "code": "Old1-Code-0001", "legalAccepted": True,
        })
        wrong = c.post("/api/market/activate", json={
            **base, "code": "Nope-1234-Code", "legalAccepted": True,
        })
        assert missing.status_code == wrong.status_code == 404
        assert missing.json()["detail"] == wrong.json()["detail"]
        assert expired.status_code == 410
        assert expired.json()["detail"]["code"] == "code_expired"

        # Российский номер с ведущей 8 нормализуется; активной подписке месяц
        # добавляется немедленно к текущей дате окончания — ожидания окна продления нет.
        activated = c.post("/api/market/activate", json={**base, "legalAccepted": True})
        assert activated.status_code == 200
        assert activated.json()["until"] == add_month(current_until)
        assert "token" not in activated.json()
        sub = s.subscription(acc["id"])
        assert sub["status"] == "active" and sub["paid_until"] == add_month(current_until)
        account = s.account(acc["id"])
        assert account["legal_acceptance"]["source"] == "yandex_market"
        code_stats = s.activation_codes_stats(now=int(t0))
        assert code_stats["used"][0]["used_by"] == acc["id"]
        assert code_stats["expired"][0]["code"] == "Old1-Code-0001"

        # Канонический URL возвращает SPA; вариант со слешем убирает его, чтобы
        # относительные Vite-assets загружались от корня, а не /ya_market/assets/.
        page = c.get("/ya_market", follow_redirects=False)
        assert page.status_code == 200
        assert page.headers["content-type"].startswith("text/html")
        slash = c.get("/ya_market/", follow_redirects=False)
        assert slash.status_code == 308 and slash.headers["location"] == "/ya_market"
    finally:
        set_activation(None)


def test_account_ui_flags_endpoint_and_merge():
    # Одноразовые UI-флаги аккаунта (онбординг-подсказки): POST /api/account/flags
    # выставляет флаг из белого списка (идемпотентно), флаг виден в /api/account,
    # слияние аккаунтов сохраняет «видел» любой из половинок.
    from fastapi.testclient import TestClient
    from control.api import create_app
    s = _fresh_store()
    c = TestClient(create_app(s))
    r = _auth_contact(c, 555)
    acc_id = r.json()["account"]["id"]
    assert r.json()["account"]["uiFlags"] == {}
    H = {"Authorization": f"Bearer {r.json()['token']}"}
    # произвольный ключ отклоняется (клиент не пишет в аккаунт что попало)
    assert c.post("/api/account/flags", json={"flag": "hack"}, headers=H).status_code == 400
    assert c.post("/api/account/flags", json={}, headers=H).status_code == 400
    # выставление — отражается в ответе и в /api/account; повтор идемпотентен
    r2 = c.post("/api/account/flags", json={"flag": "sources_intro_seen"}, headers=H)
    assert r2.status_code == 200 and r2.json()["uiFlags"] == {"sources_intro_seen": True}
    r3 = c.post("/api/account/flags", json={"flag": "sources_intro_seen"}, headers=H)
    assert r3.status_code == 200 and r3.json()["uiFlags"] == {"sources_intro_seen": True}
    assert c.get("/api/account", headers=H).json()["uiFlags"] == {"sources_intro_seen": True}
    # без авторизации — 401
    assert c.post("/api/account/flags", json={"flag": "sources_intro_seen"}).status_code == 401
    # слияние: src с флагом → dst без флага: dst «видел»
    dst = run(s.get_or_create_account("tg", 999, None))
    assert run(s.merge_account(acc_id, dst["id"]))
    assert (s.account(dst["id"]).get("ui_flags") or {}).get("sources_intro_seen") is True


def test_legal_accept_endpoint_gate_and_reaccept_on_version_change():
    from fastapi.testclient import TestClient
    from control.api import create_app
    s = _fresh_store()
    c = TestClient(create_app(s))
    r = _auth_contact(c, 555)
    H = {"Authorization": f"Bearer {r.json()['token']}"}
    acc = c.get("/api/account", headers=H).json()
    assert acc["legal"]["accepted"] is False
    assert acc["legal"]["requiredTermsVersion"] == config.LEGAL_TERMS_VERSION

    assert c.post("/api/sources/code", json={"messenger": "max"}, headers=H).status_code == 428
    assert c.post("/api/pay/checkout", json={"mode": "pay"}, headers=H).status_code == 428
    assert c.post("/api/pay/activate", json={"code": "AAAA-BBBB-CCCC"}, headers=H).status_code == 428
    assert c.post("/api/legal/accept", json={"termsVersion": "2000-01-01"}, headers=H).status_code == 409

    accepted = _accept_legal(c, H)
    assert accepted["legal"]["accepted"] is True
    assert accepted["legal"]["termsVersion"] == config.LEGAL_TERMS_VERSION
    assert len(s.account(accepted["id"]).get("legal_history") or []) == 1
    assert c.post("/api/sources/code", json={"messenger": "max"}, headers=H).status_code == 200
    # После принятия legal-гейт пройден, и checkout падает уже на ожидаемую настройку биллинга.
    assert c.post("/api/pay/checkout", json={"mode": "pay"}, headers=H).status_code == 503

    old_terms, old_privacy = config.LEGAL_TERMS_VERSION, config.LEGAL_PRIVACY_VERSION
    try:
        config.LEGAL_TERMS_VERSION = "2099-01-01"
        stale = c.get("/api/account", headers=H).json()
        assert stale["legal"]["accepted"] is False
        assert stale["legal"]["requiredTermsVersion"] == "2099-01-01"
        assert c.post("/api/sources/code", json={"messenger": "max"}, headers=H).status_code == 428
        fresh = c.post("/api/legal/accept", json={
            "termsVersion": "2099-01-01",
            "privacyVersion": old_privacy,
            "source": "test",
        }, headers=H)
        assert fresh.status_code == 200 and fresh.json()["legal"]["accepted"] is True
    finally:
        config.LEGAL_TERMS_VERSION = old_terms
        config.LEGAL_PRIVACY_VERSION = old_privacy


def test_legal_accept_history_survives_account_merge():
    s = _fresh_store()
    a = run(s.get_or_create_account("max", 1, None))
    b = run(s.get_or_create_account("tg", 2, None))
    run(s.accept_legal(a["id"], terms_version="2026-01-01", privacy_version="2026-01-01", source="test"))
    run(s.accept_legal(b["id"], terms_version=config.LEGAL_TERMS_VERSION,
                       privacy_version=config.LEGAL_PRIVACY_VERSION, source="test"))
    assert run(s.merge_account(a["id"], b["id"]))
    merged = s.account(b["id"])
    hist = merged.get("legal_history") or []
    assert len(hist) >= 2
    assert merged["legal_acceptance"]["terms_version"] == config.LEGAL_TERMS_VERSION


def test_traffic_and_per_rule():
    s = _fresh_store()
    a = run(s.get_or_create_account("max", 1, None))
    run(s.add_traffic(a["id"], 1000, rule_id="rule_x"))
    run(s.add_traffic(a["id"], 500, rule_id="rule_x"))
    t = s.traffic(a["id"])
    assert t["used_bytes"] == 1500
    assert t["per_rule"]["rule_x"] == 1500


def test_codes_and_otp():
    s = _fresh_store()
    a = run(s.get_or_create_account("max", 1, "79990001122"))
    res = run(s.issue_code(a["id"], "max"))
    assert res["code"] in s.active_codes()
    consumed = run(s.consume_code(res["code"]))
    assert consumed["account_id"] == a["id"]
    assert res["code"] not in s.active_codes()
    rec = run(s.issue_otp("79990001122"))
    assert run(s.check_otp("79990001122", rec["code"])) is True
    assert run(s.check_otp("79990001122", "0000")) in (False, rec["code"] == "0000")


def test_code_multi_bind_not_consumed():
    # Одним кодом можно привязать несколько источников в пределах TTL — код НЕ потребляется.
    s = _fresh_store()
    a = run(s.get_or_create_account("max", 1, None))
    code = run(s.issue_code(a["id"], "max"))["code"]
    run(s.record_code_bind(code, "max:111"))
    run(s.record_code_bind(code, "max:222"))
    run(s.record_code_bind(code, "max:111"))  # дубль игнорируется
    assert code in s.active_codes()  # код всё ещё активен (многоразовый)
    assert s.active_codes()[code]["bound"] == ["max:111", "max:222"]


def test_mark_read_specific_ids():
    s = _fresh_store()
    a = run(s.get_or_create_account("max", 1, None))["id"]
    n1 = run(s.add_notification(a, type="bound", title="A"))
    n2 = run(s.add_notification(a, type="bound", title="B"))
    run(s.mark_read(a, [n1["id"]]))                 # «Скрыть» только одно
    by_id = {n["id"]: n["read"] for n in s.notifications_of(a)}
    assert by_id[n1["id"]] is True and by_id[n2["id"]] is False
    run(s.mark_read(a))                              # все
    assert all(n["read"] for n in s.notifications_of(a))


def test_code_one_per_account_any_messenger():
    # 1 активный код на аккаунт, НЕЗАВИСИМО от мессенджера — повторные выдачи возвращают тот же.
    s = _fresh_store()
    a = run(s.get_or_create_account("max", 1, None))["id"]
    c1 = run(s.issue_code(a, "max"))["code"]
    c2 = run(s.issue_code(a, "tg"))["code"]   # другой мессенджер
    c3 = run(s.issue_code(a))["code"]          # без мессенджера
    assert c1 == c2 == c3
    assert len([v for v in s.active_codes().values() if v.get("account_id") == a]) == 1
    b = run(s.get_or_create_account("tg", 2, None))["id"]
    assert run(s.issue_code(b))["code"] != c1  # у другого аккаунта — свой код


def test_extra_codes_provider_messenger_agnostic():
    from control.integration import make_extra_codes_provider
    s = _fresh_store()
    a = run(s.get_or_create_account("max", 1, None))["id"]
    code = run(s.issue_code(a))["code"]
    prov = make_extra_codes_provider(s)        # один провайдер для обоих ботов
    got = prov()
    assert code in got and got[code]["account_id"] == a


# ---------------- security ----------------
def test_telegram_initdata_roundtrip():
    token = "111:TESTTOKEN"
    params = {"auth_date": str(int(time.time())), "query_id": "abc", "user": '{"id":42,"first_name":"A"}'}
    dcs = "\n".join(f"{k}={params[k]}" for k in sorted(params))
    secret = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
    h = hmac.new(secret, dcs.encode(), hashlib.sha256).hexdigest()
    init = urlencode(params) + "&hash=" + h
    parsed = security.verify_telegram_initdata(init, token)
    assert parsed and parsed["user"]["id"] == 42
    # подделка хэша → None
    assert security.verify_telegram_initdata(urlencode(params) + "&hash=deadbeef", token) is None


def test_max_contact_hmac():
    token = "maxtoken"
    phone, auth_date, uid = "79001234567", 1700000000, 777
    msg = f"authDate={auth_date}\nphone={phone}\nuserId={uid}"
    expected = hmac.new(token.encode(), msg.encode(), hashlib.sha256).hexdigest()
    assert security.verify_max_contact(phone, auth_date, expected, uid, token) is True
    assert security.verify_max_contact(phone, auth_date, "nope", uid, token) is False


def test_max_contact_hmac_accepts_millisecond_authdate_for_freshness():
    from unittest.mock import patch

    token = "maxtoken"
    phone, uid = "79001234567", 777
    auth_ts = 1783966139
    auth_date_ms = str(auth_ts * 1000 + 939)
    msg = f"authDate={auth_date_ms}\nphone={phone}\nuserId={uid}"
    expected = hmac.new(token.encode(), msg.encode(), hashlib.sha256).hexdigest()
    with patch("control.security.time.time", return_value=auth_ts + 10):
        assert security.verify_max_contact(
            phone, auth_date_ms, expected, uid, token, max_age=86400) is True

    stale_ms = str((auth_ts - 90000) * 1000)
    stale_msg = f"authDate={stale_ms}\nphone={phone}\nuserId={uid}"
    stale_hash = hmac.new(token.encode(), stale_msg.encode(), hashlib.sha256).hexdigest()
    with patch("control.security.time.time", return_value=auth_ts):
        assert security.verify_max_contact(
            phone, stale_ms, stale_hash, uid, token, max_age=86400) is False


def test_auth_contact_production_signatures_required_end_to_end():
    from fastapi.testclient import TestClient
    from control.api import create_app

    s = _fresh_store()
    c = TestClient(create_app(s))
    uid, phone = 778, "79001234778"
    payload = _signed_max_contact(uid, phone, auth_date=str(int(time.time() * 1000)))
    payload["initData"] = _signed_initdata(uid, config.MAX_BOT_TOKEN)
    old = config.AUTH_INSECURE
    config.AUTH_INSECURE = False
    try:
        ok = c.post("/api/auth/contact", json=payload)
        assert ok.status_code == 200, ok.text
        forged = {**_signed_max_contact(779, "79001234779"),
                  "initData": payload["initData"] + "broken"}
        bad = c.post("/api/auth/contact", json=forged)
        assert bad.status_code == 400 and bad.json()["detail"]["code"] == "bad_signature"
        assert s.find_account_by_identity("max", 779) is None
    finally:
        config.AUTH_INSECURE = old


def test_max_initdata_same_algo_as_telegram():
    # MAX initData валидируется тем же алгоритмом → authenticate('max', ...) принимает
    # корректную подпись и отклоняет испорченную (вне AUTH_INSECURE — проверяется в e2e).
    token = "maxtoken"
    params = {"auth_date": str(int(time.time())), "user": '{"id":99}'}
    dcs = "\n".join(f"{k}={params[k]}" for k in sorted(params))
    secret = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
    h = hmac.new(secret, dcs.encode(), hashlib.sha256).hexdigest()
    init = urlencode(params) + "&hash=" + h
    parsed = security.verify_initdata(init, token)
    assert parsed and parsed["user"]["id"] == 99
    assert security.verify_initdata(urlencode(params) + "&hash=bad", token) is None


def test_jwt_session_roundtrip():
    tok = security.make_session("acc_42")
    assert security.decode_session(tok) == "acc_42"
    assert security.decode_session("garbage") is None


# ---------------- sources (через синтетический ownership) ----------------
def _write_ownership(path, owners):
    Path(path).write_text(json.dumps({"chats": {}, "owners": owners, "pending": {}}), encoding="utf-8")


def test_channel_bind_without_sender_attributed_to_account():
    # Канал: у поста нет отправителя (from=None). Привязка через mini-app должна
    # связаться с АККАУНТОМ напрямую и появиться в списке источников.
    from control.integration import make_extra_codes_provider, make_external_claim_cb
    s = _fresh_store()
    a = run(s.get_or_create_account("tg", 5, "79000000005"))["id"]
    code = run(s.issue_code(a))["code"]
    _write_ownership(config.TG_OWNERSHIP_FILE, {
        "-100500": {"user_id": None, "title": "Мой канал", "rights_ok": True, "type": "channel"},
    })
    marker = make_extra_codes_provider(s)()[code]          # {account_id}
    cb = make_external_claim_cb(s, "tg")
    run(cb(code, None, {"id": -100500, "title": "Мой канал", "type": "channel"}, marker))  # sender=None
    data = run(sources_mod.list_sources(s, a))
    src = next((x for x in data["sources"] if x["id"] == "tg:-100500"), None)
    assert src and src["type"] == "channel" and src["title"] == "Мой канал"
    assert run(sources_mod.owns_source(s, a, "tg:-100500")) is True


def test_orphan_channel_reattributed_on_repost():
    # Канал уже «осиротел» в ownership (owner=None, привязан до фикса). Повторная
    # отправка кода должна привязать его к аккаунту (а не упереться в «уже привязан»).
    from max_sync.ownership import OwnershipManager as MaxOwn
    from control.integration import make_extra_codes_provider, make_external_claim_cb
    s = _fresh_store()
    acc = run(s.get_or_create_account("max", 7, None))["id"]
    code = run(s.issue_code(acc))["code"]

    class FakeClient:
        async def get_chat(self, cid): return {"chat_id": cid, "type": "channel", "title": "Hello"}
        async def send_message(self, **k): return {"message": {"body": {"mid": "m1"}}}
        async def delete_message(self, mid): return {}

    mgr = MaxOwn(FakeClient(), _TMP / f"own_{time.time_ns()}.json", bot_id=1,
                 extra_codes_provider=make_extra_codes_provider(s),
                 on_external_claim=make_external_claim_cb(s, "max"))
    mgr._owners["-100777"] = {"user_id": None, "title": "Hello", "rights_ok": True}  # осиротевший канал
    run(mgr.on_chat_message({"chat_id": -100777, "chat_type": "channel", "sender_id": None, "text": f"код {code}"}))
    assert "max:-100777" in s.account_source_ids(acc)


def test_max_claim_probes_write_rights():
    # При привязке MAX право на ОТПРАВКУ проверяется тест-сообщением (шлём и сразу удаляем);
    # право на ЧТЕНИЕ НЕ запрашивается — оно доказано фактом получения кода. Нет права писать
    # → rights_ok=False, источник всё равно привязывается (помечен «нет прав»).
    from max_sync.ownership import OwnershipManager as MaxOwn
    from max_sync.client import MaxError
    from control.integration import make_extra_codes_provider, make_external_claim_cb
    s = _fresh_store()
    acc = run(s.get_or_create_account("max", 70, None))["id"]
    code = run(s.issue_code(acc))["code"]

    sent, deleted = [], []
    class WritableMax:
        async def get_chat(self, cid): return {"chat_id": cid, "type": "channel", "title": "Канал"}
        async def send_message(self, **k): sent.append(k); return {"message": {"body": {"mid": "mid1"}}}
        async def delete_message(self, mid): deleted.append(mid); return {}
    mgr = MaxOwn(WritableMax(), _TMP / f"own_{time.time_ns()}.json", bot_id=1,
                 extra_codes_provider=make_extra_codes_provider(s),
                 on_external_claim=make_external_claim_cb(s, "max"))
    run(mgr.on_chat_message({"chat_id": -100888, "chat_type": "channel", "sender_id": None, "text": code}))
    assert mgr._owners["-100888"]["rights_ok"] is True   # отправка прошла → право записи есть
    assert sent and deleted == ["mid1"]                  # тест-сообщение отправлено и удалено

    class NoWriteMax:
        async def get_chat(self, cid): return {"chat_id": cid, "type": "channel", "title": "Канал2"}
        async def send_message(self, **k): raise MaxError("POST messages", 403, "forbidden", "no rights")
        async def delete_message(self, mid): return {}
    mgr2 = MaxOwn(NoWriteMax(), _TMP / f"own_{time.time_ns()}.json", bot_id=1,
                  extra_codes_provider=make_extra_codes_provider(s),
                  on_external_claim=make_external_claim_cb(s, "max"))
    run(mgr2.on_chat_message({"chat_id": -100999, "chat_type": "channel", "sender_id": None, "text": code}))
    assert mgr2._owners["-100999"]["rights_ok"] is False  # отправка упала → нет права записи


def test_bind_notifier_called_on_claim():
    # При привязке источника шлём лаконичное сообщение в чат с ботом: группе — отправителю,
    # каналу (без отправителя) — идентичности аккаунта в этом мессенджере.
    from control.integration import make_external_claim_cb, make_extra_codes_provider
    s = _fresh_store()
    a = run(s.get_or_create_account("tg", 5, None))["id"]
    code = run(s.issue_code(a))["code"]
    sent = []
    async def fake_notify(messenger, uid, text): sent.append((messenger, str(uid), text))
    marker = make_extra_codes_provider(s)()[code]
    cb = make_external_claim_cb(s, "tg", fake_notify)
    run(cb(code, 5, {"id": -100, "title": "Группа", "type": "supergroup"}, marker))
    assert sent[-1] == ("tg", "5", "✅ Источник «Группа» привязан")
    run(cb(code, None, {"id": -200, "title": "Канал", "type": "channel"}, marker))  # канал, отправителя нет
    assert sent[-1] == ("tg", "5", "✅ Источник «Канал» привязан")


def test_unbind_notifies_chat_with_bot():
    # Отвязка источника в mini-app → лаконичное сообщение «отвязан» в чат с ботом.
    from fastapi.testclient import TestClient
    from control.api import create_app, set_source_notifier
    s = _fresh_store()
    a = run(s.get_or_create_account("tg", 5, "79000000005"))["id"]
    _write_ownership(config.TG_OWNERSHIP_FILE, {
        "-300": {"user_id": 5, "title": "Группа Х", "rights_ok": True, "type": "supergroup"},
    })
    run(s.add_account_source(a, "tg:-300"))
    sent = []
    async def cap(messenger, uid, text): sent.append((messenger, str(uid), text))
    set_source_notifier(cap)
    try:
        c = TestClient(create_app(s))
        H = {"Authorization": f"Bearer {security.make_session(a)}"}
        assert c.delete("/api/sources/tg:-300", headers=H).status_code == 200
    finally:
        set_source_notifier(None)
    assert sent and sent[-1] == ("tg", "5", "🗑 Источник «Группа Х» отвязан")


def test_delete_source_references_removes_rules_sources_codes_and_topics():
    # Общая очистка источника используется и API-удалением, и событием удаления бота.
    # Для базового TG-чата она удаляет также topic-источники/правила этого форума.
    s = _fresh_store()
    acc = run(s.get_or_create_account("tg", 5, None))["id"]
    run(s.add_account_source(acc, "tg:-100"))
    run(s.add_account_source(acc, "tg:-100:2"))
    run(s.add_account_source(acc, "max:9"))
    code = run(s.issue_code(acc))["code"]
    run(s.record_code_bind(code, "tg:-100:2"))
    run(s.set_source_info("tg:-100", title="Форум", photo_id="p1"))
    run(s.set_source_info("tg:-100:2", title="Тема", photo_id="p2"))
    r1 = run(s.add_rule({"account_id": acc, "a": {"messenger": "tg", "chat_id": "-100"},
                         "b": {"messenger": "max", "chat_id": "9"}, "dir": "to",
                         "status": "active"}))
    r2 = run(s.add_rule({"account_id": acc, "a": {"messenger": "tg", "chat_id": "-100",
                                                  "thread_id": "2"},
                         "b": {"messenger": "max", "chat_id": "9"}, "dir": "to",
                         "status": "active"}))
    keep = run(s.add_rule({"account_id": acc, "a": {"messenger": "max", "chat_id": "9"},
                           "b": {"messenger": "max", "chat_id": "10"}, "dir": "to",
                           "status": "active"}))
    cleanup = run(s.delete_source_references("tg", "-100"))
    assert set(cleanup["removed_rules"]) == {r1["id"], r2["id"]}
    assert s.rule(keep["id"]) is not None
    assert s.account_source_ids(acc) == ["max:9"]
    assert s.active_codes()[code]["bound"] == []
    assert s.cached_source_info("tg:-100") == {}
    assert s.cached_source_info("tg:-100:2") == {}


def test_max_hide_callback_deletes_message():
    from max_sync.updates import UpdateRouter as MaxRouter
    from max_sync.storage import Storage as MaxStorage
    calls = {}
    class FC:
        async def delete_message(self, mid): calls["del"] = mid
        async def answer_callback(self, cid, notification=None): calls["ans"] = cid
    st = MaxStorage(_TMP / "r.jsonl", _TMP / "c.jsonl", _TMP / "mk", _TMP / "med")
    r = MaxRouter(FC(), st, download_media=False, max_download_bytes=0)
    upd = {"update_type": "message_callback", "callback": {"callback_id": "cb1", "payload": "hide_msg"},
           "message": {"body": {"mid": "MID9"}}}
    run(r._handle_callback(upd))
    assert calls.get("del") == "MID9" and calls.get("ans") == "cb1"


def test_tg_forwarded_callback_button_answers_notice():
    from telegram_sync.updates import UpdateRouter as TgRouter
    from telegram_sync.storage import Storage as TgStorage
    calls = {}
    class FC:
        async def answer_callback_query(self, cid, text=None):
            calls["ans"] = (cid, text)
    st = TgStorage(_TMP / "tr.jsonl", _TMP / "tc.jsonl", _TMP / "toffset", _TMP / "tmed")
    r = TgRouter(FC(), st, download_media=False, max_download_bytes=0, media_debounce=0)
    upd = {"id": "cb2", "data": FORWARDED_BUTTON_PAYLOAD,
           "message": {"chat": {"id": 1}, "message_id": 2}}
    run(r._handle_callback(upd))
    assert calls.get("ans") == ("cb2", FORWARDED_BUTTON_NOTICE)


def test_tg_service_message_not_routed_to_rules():
    from telegram_sync.updates import UpdateRouter as TgRouter
    from telegram_sync.storage import Storage as TgStorage
    routed = []
    st = TgStorage(_TMP / f"svc_raw_{time.time_ns()}.jsonl",
                   _TMP / f"svc_content_{time.time_ns()}.jsonl",
                   _TMP / f"svc_offset_{time.time_ns()}",
                   _TMP / "svc_media")
    r = TgRouter(object(), st, download_media=False, max_download_bytes=0,
                 media_debounce=0, rule_router=lambda norm: routed.append(norm))
    run(r._handle_message({
        "update_kind": "message",
        "message_id": 10,
        "media_group_id": None,
        "date": 1,
        "chat": {"id": -100, "type": "supergroup", "title": "Группа"},
        "message_thread_id": None,
        "from": {"id": 5},
        "text": None,
        "media": [],
        "structured": None,
        "service": {"new_chat_members": [{"id": 6, "first_name": "Аня"}]},
        "raw": {},
    }))
    assert routed == []


def test_max_forwarded_callback_button_answers_notice():
    from max_sync.updates import UpdateRouter as MaxRouter
    from max_sync.storage import Storage as MaxStorage
    calls = {}
    class FC:
        async def answer_callback(self, cid, notification=None):
            calls["ans"] = (cid, notification)
    st = MaxStorage(_TMP / "mr.jsonl", _TMP / "mc.jsonl", _TMP / "mmarker", _TMP / "mmed")
    r = MaxRouter(FC(), st, download_media=False, max_download_bytes=0)
    upd = {"update_type": "message_callback",
           "callback": {"callback_id": "cb3", "payload": FORWARDED_BUTTON_PAYLOAD}}
    run(r._handle_callback(upd))
    assert calls.get("ans") == ("cb3", FORWARDED_BUTTON_NOTICE)


def test_service_messages_have_hide_button_except_greeting():
    """Все служебные сообщения бота в личке — с inline-кнопкой «Скрыть» (колбэк hide_msg,
    бот удаляет сообщение); исключение — приветствие HELP_TEXT (/start, /help): без кнопки.
    Проверяем ответы ownership (оба мессенджера) и make_notifier (OTP входа, биллинг)."""
    from max_sync.ownership import OwnershipManager as MaxOwn
    from telegram_sync.ownership import OwnershipManager as TgOwn
    from control.integration import make_notifier

    max_kb = [{"type": "inline_keyboard", "payload": {
        "buttons": [[{"type": "callback", "text": "Скрыть", "payload": "hide_msg"}]]}}]
    tg_kb = {"inline_keyboard": [[{"text": "Скрыть", "callback_data": "hide_msg"}]]}

    sent = []
    class FakeMax:
        async def send_message(self, **k): sent.append(k); return {"message": {"body": {"mid": "m1"}}}
    m = MaxOwn(FakeMax(), _TMP / f"own_{time.time_ns()}.json", bot_id=1)
    run(m.handle_command({"sender_id": 7, "text": "/claim"}))       # код привязки — с кнопкой
    assert sent[-1]["attachments"] == max_kb
    run(m.handle_command({"sender_id": 7, "text": "/start"}))       # приветствие — без кнопки
    assert sent[-1]["attachments"] is None

    tsent = []
    class FakeTg:
        async def call(self, method, params): tsent.append((method, params)); return {}
    t = TgOwn(FakeTg(), _TMP / f"town_{time.time_ns()}.json", bot_id=1)
    run(t.handle_command({"from": {"id": 5}, "chat": {"id": 5}, "text": "/claim"}))
    assert tsent[-1][1]["reply_markup"] == tg_kb
    run(t.handle_command({"from": {"id": 5}, "chat": {"id": 5}, "text": "/start"}))
    assert "reply_markup" not in tsent[-1][1]

    nsent = []
    class NMax:
        async def send_message(self, **k): nsent.append(("max", k)); return {}
    class NTg:
        async def send_message(self, chat_id, text, **k): nsent.append(("tg", k)); return {}
    notify = make_notifier(NMax(), NTg())
    run(notify("max", 7, "💳 Тест"))
    assert nsent[-1][1]["attachments"] == max_kb
    run(notify("tg", 5, "💳 Тест"))
    assert nsent[-1][1]["reply_markup"] == tg_kb


def test_sources_status_tg_group_ok_channel_needs_rights():
    # Отображение статуса по модели прав: TG-группа ок даже при старом rights_ok=False;
    # TG-канал без прав — err.
    s = _fresh_store()
    a = run(s.get_or_create_account("tg", 9, None))["id"]
    _write_ownership(config.TG_OWNERSHIP_FILE, {
        "-10": {"user_id": 9, "title": "Группа", "rights_ok": False, "type": "supergroup"},
        "-20": {"user_id": 9, "title": "Канал", "rights_ok": False, "type": "channel"},
    })
    by = {x["title"]: x for x in run(sources_mod.list_sources(s, a))["sources"]}
    assert by["Группа"]["status"] == "ok" and by["Группа"]["rightsOk"] is True
    assert by["Канал"]["status"] == "err" and by["Канал"]["rightsOk"] is False


def test_tg_rights_group_no_admin_channel_needs_post():
    from telegram_sync.ownership import _rights_ok_from as ok
    # Группа/супергруппа: особые права не нужны (участник — уже ок).
    assert ok({"status": "member"}, {"type": "supergroup"}) is True
    assert ok({"status": "member"}, {"type": "group"}) is True
    assert ok({"status": "administrator"}, {"type": "supergroup"}) is True
    assert ok({"status": "left"}, {"type": "supergroup"}) is False
    assert ok({"status": "kicked"}, {"type": "group"}) is False
    # Канал: нужен админ с правом публикации.
    assert ok({"status": "member"}, {"type": "channel"}) is False
    assert ok({"status": "administrator", "can_post_messages": False}, {"type": "channel"}) is False
    assert ok({"status": "administrator", "can_post_messages": True}, {"type": "channel"}) is True
    assert ok({"status": "creator"}, {"type": "channel"}) is True


def test_list_sources_over_ownership():
    s = _fresh_store()
    a = run(s.get_or_create_account("max", 777, None))
    _write_ownership(config.MAX_OWNERSHIP_FILE, {
        "100": {"user_id": 777, "title": "Новости", "rights_ok": True, "type": "channel"},
        "200": {"user_id": 999, "title": "Чужой", "rights_ok": True, "type": "channel"},  # не наш
    })
    data = run(sources_mod.list_sources(s, a["id"]))
    ids = {x["id"] for x in data["sources"]}
    assert ids == {"max:100"}
    assert data["sources"][0]["title"] == "Новости"
    assert run(sources_mod.owns_source(s, a["id"], "max:100")) is True
    assert run(sources_mod.owns_source(s, a["id"], "max:200")) is False


def test_tg_forum_topic_source_resolves_from_base_chat():
    # Topic-источник хранится как tg:<chat_id>:<message_thread_id>, но getChat/avatar/rights
    # остаются на базовом chat_id. В списке это отдельный источник с типом "topic".
    s = _fresh_store()
    a = run(s.get_or_create_account("tg", 777, None))
    run(s.add_account_source(a["id"], "tg:-100500:42"))
    _write_ownership(config.TG_OWNERSHIP_FILE, {
        "-100500": {"user_id": None, "title": "Форум", "rights_ok": True, "type": "supergroup"},
    })
    data = run(sources_mod.list_sources(s, a["id"]))
    assert [x["id"] for x in data["sources"]] == ["tg:-100500:42"]
    src = data["sources"][0]
    assert src["type"] == "topic"
    assert src["title"] == "Форум · тема 42"
    assert src["baseTitle"] == "Форум"
    assert src["topicTitle"] == "тема 42"
    assert src["status"] == "ok"


def test_owned_tg_forum_observed_topics_are_selectable():
    # Bot API не умеет перечислять темы форума; список строим из уже увиденных
    # message_thread_id/service-событий в Telegram content.jsonl.
    s = _fresh_store()
    acc = run(s.get_or_create_account("tg", 777, None))["id"]
    chat_id = "-100901"
    _write_ownership(config.TG_OWNERSHIP_FILE, {
        chat_id: {"user_id": 777, "title": "Привет", "rights_ok": True, "type": "supergroup"},
    })
    config.TG_CONTENT_FILE.parent.mkdir(parents=True, exist_ok=True)
    rows = [
        {
            "update_kind": "message", "message_id": 12, "date": 1,
            "chat": {"id": int(chat_id), "type": "supergroup", "title": "Привет", "is_forum": True},
            "message_thread_id": 12, "is_topic_message": True,
            "service": {"forum_topic_created": {"name": "Привет!", "icon_color": 13338331}},
        },
        {
            "update_kind": "message", "message_id": 13, "date": 2,
            "chat": {"id": int(chat_id), "type": "supergroup", "title": "Привет", "is_forum": True},
            "text": "сообщение в General",
        },
    ]
    config.TG_CONTENT_FILE.write_text(
        "\n".join(json.dumps(x, ensure_ascii=False) for x in rows) + "\n", encoding="utf-8")

    data = run(sources_mod.list_sources(s, acc))
    by = {x["id"]: x for x in data["sources"]}
    assert by[f"tg:{chat_id}:12"]["type"] == "topic"
    assert by[f"tg:{chat_id}:12"]["topicTitle"] == "Привет!"
    assert by[f"tg:{chat_id}:12"]["observedTopic"] is True
    assert by[f"tg:{chat_id}:12"]["deletable"] is False
    assert by[f"tg:{chat_id}:1"]["topicTitle"] == "General"
    assert run(sources_mod.owns_source(s, acc, f"tg:{chat_id}:12")) is True

    _write_ownership(config.MAX_OWNERSHIP_FILE, {
        "9001": {"user_id": None, "title": "MAX", "rights_ok": True, "type": "channel"},
    })
    run(s.add_account_source(acc, "max:9001"))
    rule = run(rules_mod.create_rule(s, acc, a_id="max:9001", b_id=f"tg:{chat_id}:12", direction="to"))
    assert rule["b"]["sourceId"] == f"tg:{chat_id}:12"
    assert rule["b"]["title"] == "Привет · Привет!"


# ---------------- rules: валидация и движок ----------------
def _account_with_two_sources():
    s = _fresh_store()
    a = run(s.get_or_create_account("max", 777, None))
    _write_ownership(config.MAX_OWNERSHIP_FILE, {
        "1": {"user_id": 777, "title": "A", "rights_ok": True, "type": "channel"},
        "2": {"user_id": 777, "title": "B", "rights_ok": True, "type": "channel"},
    })
    return s, a["id"]


def test_rule_validation():
    s, acc = _account_with_two_sources()
    # оба обязательны
    try:
        run(rules_mod.create_rule(s, acc, a_id="", b_id="max:2"))
        assert False
    except rules_mod.RuleError as e:
        assert e.code == "required"
    # одинаковые
    try:
        run(rules_mod.create_rule(s, acc, a_id="max:1", b_id="max:1"))
        assert False
    except rules_mod.RuleError as e:
        assert e.code == "same"
    # успешно
    r = run(rules_mod.create_rule(s, acc, a_id="max:1", b_id="max:2", direction="to"))
    assert r["status"] == "active"
    # дубль: A⇄B (перестановка) пересекается по потоку 1→2 с уже существующим A→B
    try:
        run(rules_mod.create_rule(s, acc, a_id="max:2", b_id="max:1"))
        assert False
    except rules_mod.RuleError as e:
        assert e.code == "dup"


def test_rule_can_target_tg_forum_topic():
    s = _fresh_store()
    acc = run(s.get_or_create_account("tg", 777, None))["id"]
    _write_ownership(config.MAX_OWNERSHIP_FILE, {
        "1": {"user_id": 777, "title": "MAX", "rights_ok": True, "type": "channel"},
    })
    _write_ownership(config.TG_OWNERSHIP_FILE, {
        "-100500": {"user_id": None, "title": "Форум", "rights_ok": True, "type": "supergroup"},
    })
    run(s.add_account_source(acc, "max:1"))
    run(s.add_account_source(acc, "tg:-100500:42"))
    rule = run(rules_mod.create_rule(s, acc, a_id="max:1", b_id="tg:-100500:42", direction="to"))
    assert rule["b"]["sourceId"] == "tg:-100500:42"
    assert rule["b"]["type"] == "topic"
    raw = s.rules_of(acc)[0]
    assert raw["b"] == {"messenger": "tg", "chat_id": "-100500", "thread_id": "42"}


def test_rule_numbering_on_create_monotonic_no_reuse():
    # Номер присваивается при создании (+1), монотонный и НЕ переиспользуется после удаления.
    s, acc = _account_with_two_sources()
    _add_owner(s, acc, "3", "C")
    r1 = run(rules_mod.create_rule(s, acc, a_id="max:1", b_id="max:2"))
    r2 = run(rules_mod.create_rule(s, acc, a_id="max:1", b_id="max:3"))
    assert (r1["number"], r2["number"]) == (1, 2)
    run(rules_mod.delete_rule(s, acc, r1["id"]))
    r3 = run(rules_mod.create_rule(s, acc, a_id="max:2", b_id="max:3"))
    assert r3["number"] == 3   # монотонно: номер удалённого правила не переиспользуется
    nums = [x["number"] for x in run(rules_mod.list_rules(s, acc))["rules"]]
    assert nums == [2, 3]      # список отсортирован по номеру


def test_rule_numbering_per_account_starts_at_one():
    # У каждого аккаунта своя независимая нумерация, начинается с 1.
    s = _fresh_store()
    a1 = run(s.get_or_create_account("max", 111, None))["id"]
    a2 = run(s.get_or_create_account("max", 222, None))["id"]
    _write_ownership(config.MAX_OWNERSHIP_FILE, {
        "1": {"user_id": 111, "title": "A", "rights_ok": True, "type": "channel"},
        "2": {"user_id": 111, "title": "B", "rights_ok": True, "type": "channel"},
        "3": {"user_id": 222, "title": "C", "rights_ok": True, "type": "channel"},
        "4": {"user_id": 222, "title": "D", "rights_ok": True, "type": "channel"},
    })
    r1 = run(rules_mod.create_rule(s, a1, a_id="max:1", b_id="max:2"))
    r2 = run(rules_mod.create_rule(s, a2, a_id="max:3", b_id="max:4"))
    assert r1["number"] == 1 and r2["number"] == 1


def test_rule_numbering_backfill_legacy_rules():
    # Правила, созданные ДО нумерации (без number), получают номера по времени создания.
    s, acc = _account_with_two_sources()
    _add_owner(s, acc, "3", "C")
    r1 = run(rules_mod.create_rule(s, acc, a_id="max:1", b_id="max:2"))
    r2 = run(rules_mod.create_rule(s, acc, a_id="max:1", b_id="max:3"))
    s.table("rules")[r1["id"]].pop("number", None)
    s.table("rules")[r2["id"]].pop("number", None)
    s.table("accounts")[acc].pop("rules_seq", None)
    lst = run(rules_mod.list_rules(s, acc))["rules"]   # list_rules бэкфиллит недостающие
    assert all(isinstance(x["number"], int) for x in lst)
    assert sorted(x["number"] for x in lst) == [1, 2]


def test_rule_per_direction_signature_create_and_targets():
    # Подпись раздельно по направлениям: A→B вкл., B→A выкл. Движок отдаёт подпись по потоку.
    s, acc = _account_with_two_sources()
    r = run(rules_mod.create_rule(s, acc, a_id="max:1", b_id="max:2",
                                  direction="both", sign_ab=True, sign_ba=False))
    assert r["signAB"] is True and r["signBA"] is False
    t_ab = rules_mod.targets_for(s, "max", "1")   # источник = a → поток A→B
    t_ba = rules_mod.targets_for(s, "max", "2")   # источник = b → поток B→A
    assert len(t_ab) == 1 and t_ab[0]["signature"] is True
    assert len(t_ba) == 1 and t_ba[0]["signature"] is False
    # независимое обновление направлений
    r2 = run(rules_mod.update_rule(s, acc, r["id"], {"signAB": False, "signBA": True}))
    assert r2["signAB"] is False and r2["signBA"] is True
    assert rules_mod.targets_for(s, "max", "1")[0]["signature"] is False
    assert rules_mod.targets_for(s, "max", "2")[0]["signature"] is True


def test_rule_signature_legacy_fallback_both_directions():
    # Старое единое поле signature применяется к ОБОИМ потокам (back-compat для старых правил).
    s, acc = _account_with_two_sources()
    rule = run(s.add_rule({"account_id": acc, "a": {"messenger": "max", "chat_id": "1"},
                           "b": {"messenger": "max", "chat_id": "2"}, "dir": "both",
                           "signature": True, "status": "active"}))
    lst = run(rules_mod.list_rules(s, acc))["rules"]
    leg = next(x for x in lst if x["id"] == rule["id"])
    assert leg["signAB"] is True and leg["signBA"] is True
    assert rules_mod.targets_for(s, "max", "1")[0]["signature"] is True
    assert rules_mod.targets_for(s, "max", "2")[0]["signature"] is True


def test_rule_limit_counts_only_active():
    s, acc = _account_with_two_sources()
    # создаём 10 активных правил между разными парами
    for i in range(3, 13):
        _add_owner(s, acc, str(i), f"S{i}")
    pairs = [("max:1", f"max:{i}") for i in range(3, 13)]  # 10 пар
    for a_id, b_id in pairs:
        run(rules_mod.create_rule(s, acc, a_id=a_id, b_id=b_id))
    lst = run(rules_mod.list_rules(s, acc))
    assert lst["activeCount"] == 10
    # 11-е → лимит
    try:
        run(rules_mod.create_rule(s, acc, a_id="max:1", b_id="max:2"))
        assert False
    except rules_mod.RuleError as e:
        assert e.code == "limit"
    # пауза одного освобождает слот (в лимит входят только активные)
    rid = lst["rules"][0]["id"]
    run(rules_mod.set_status(s, acc, rid, "paused"))
    lst2 = run(rules_mod.list_rules(s, acc))
    assert lst2["activeCount"] == 9


def _add_owner(store, acc, chat_id, title):
    data = json.loads(Path(config.MAX_OWNERSHIP_FILE).read_text())
    data["owners"][chat_id] = {"user_id": 777, "title": title, "rights_ok": True, "type": "channel"}
    Path(config.MAX_OWNERSHIP_FILE).write_text(json.dumps(data))


def test_targets_for_direction():
    s = _fresh_store()
    a = run(s.get_or_create_account("max", 1, None))
    run(s.add_rule({"account_id": a["id"], "a": {"messenger": "max", "chat_id": "1"},
                    "b": {"messenger": "tg", "chat_id": "2"}, "dir": "to", "status": "active"}))
    # dir=to: из A→ цель B; из B→ ничего
    assert [t["chat_id"] for t in rules_mod.targets_for(s, "max", "1")] == ["2"]
    assert rules_mod.targets_for(s, "tg", "2") == []


def test_targets_for_both_and_paused():
    s = _fresh_store()
    a = run(s.get_or_create_account("max", 1, None))
    r = run(s.add_rule({"account_id": a["id"], "a": {"messenger": "max", "chat_id": "1"},
                        "b": {"messenger": "tg", "chat_id": "2"}, "dir": "both", "status": "active"}))
    assert len(rules_mod.targets_for(s, "max", "1")) == 1
    assert len(rules_mod.targets_for(s, "tg", "2")) == 1
    run(s.update_rule(r["id"], {"status": "paused"}))
    assert rules_mod.targets_for(s, "max", "1") == []  # на паузе трафик не расходуется


# ---------------- dispatcher: гейтинг подписки и трафика ----------------
def test_dispatcher_decide_gating():
    s = _fresh_store()
    a = run(s.get_or_create_account("max", 1, None))
    acc = a["id"]
    run(s.add_rule({"account_id": acc, "a": {"messenger": "max", "chat_id": "1"},
                    "b": {"messenger": "tg", "chat_id": "2"}, "dir": "to", "status": "active"}))
    d = RuleDispatcher(s)
    # подписка не активна → нет целей
    assert d.decide("max", "1") == []
    # активна → есть цель, медиа разрешено
    run(s.set_subscription(acc, {"status": "active"}))
    dec = d.decide("max", "1")
    assert len(dec) == 1 and dec[0]["media_allowed"] is True
    # трафик исчерпан → цель есть, но media_allowed False (текст+ссылка)
    run(s.add_traffic(acc, config.TRAFFIC_LIMIT_BYTES))
    dec2 = d.decide("max", "1")
    assert len(dec2) == 1 and dec2[0]["media_allowed"] is False


def test_html_for_telegram():
    assert html_for_telegram("<mark>x</mark>") == "<b>x</b>"
    assert html_for_telegram("<h1>T</h1><b>k</b>") == "<b>T</b><b>k</b>"
    # упоминание MAX (max://user/…) Telegram не понимает → жирное имя; обычные ссылки целы
    assert html_for_telegram('<a href="max://user/77">Имя</a>') == "<b>Имя</b>"
    assert html_for_telegram('<a href="https://ya.ru">ya</a>') == '<a href="https://ya.ru">ya</a>'
    # tg://user в Telegram рабочая — НЕ трогаем
    assert html_for_telegram('<a href="tg://user?id=5">Кто</a>') == '<a href="tg://user?id=5">Кто</a>'


def test_html_for_max():
    # упоминание Telegram (tg://user?id=…) MAX не понимает → жирное имя; обычные ссылки целы
    assert html_for_max('<a href="tg://user?id=5">Имя</a>') == "<b>Имя</b>"
    assert html_for_max('<a href="https://ya.ru">ya</a>') == '<a href="https://ya.ru">ya</a>'
    # max://user в MAX рабочая (нативное упоминание) — НЕ трогаем
    assert html_for_max('<a href="max://user/77">Кто</a>') == '<a href="max://user/77">Кто</a>'


# ---------------- нормализация MAX: пересланный пост несёт контент в link.message ----------------
from max_sync import content as max_content  # noqa: E402
from telegram_sync import content as tg_content  # noqa: E402


def test_max_forward_surfaces_linked_content():
    # Пост канала MAX приходит форвардом: верхний body пуст, текст+медиа — в link.message.
    # Нормализатор обязан поднять их наверх (иначе медиа/текст теряются).
    msg = {
        "recipient": {"chat_id": -7, "chat_type": "channel"},
        "body": {"mid": "MID_TOP", "seq": 1, "text": ""},
        "link": {"type": "forward", "chat_id": -68,
                 "message": {"mid": "MID_ORIG", "text": "500 руб",
                             "attachments": [
                                 {"type": "image", "payload": {"token": "T1", "url": "https://i/1"}},
                                 {"type": "image", "payload": {"token": "T2", "url": "https://i/2"}}],
                             "markup": [{"from": 0, "length": 3, "type": "strong"}]}},
    }
    norm = max_content.normalize_message(msg, "message_created")
    assert norm["is_forward"] is True
    assert norm["mid"] == "MID_TOP"                      # mid — из полученного сообщения
    assert norm["text"] == "500 руб"                     # текст — из пересланного
    assert norm["markup"] == [{"from": 0, "length": 3, "type": "strong"}]
    assert [m["type"] for m in norm["media"]] == ["image", "image"]
    assert norm["media"][0]["url"] == "https://i/1" and norm["media"][0]["token"] == "T1"


def test_max_reply_keeps_own_body_not_quoted():
    # reply: контент — в своём body; цитата в link.message НЕ подставляется.
    msg = {
        "recipient": {"chat_id": -7, "chat_type": "chat"},
        "body": {"mid": "M", "text": "мой ответ"},
        "link": {"type": "reply", "message": {"text": "цитата", "attachments": [
            {"type": "image", "payload": {"token": "Z"}}]}},
    }
    norm = max_content.normalize_message(msg, "message_created")
    assert norm["is_forward"] is False
    assert norm["text"] == "мой ответ" and norm["media"] == []


def test_max_forward_with_comment_keeps_forwarded_media():
    # Форвард С КОММЕНТАРИЕМ: текст — свой (комментарий), но медиа пересланного НЕ теряется.
    msg = {
        "recipient": {"chat_id": -7, "chat_type": "channel"},
        "body": {"mid": "M", "text": "мой коммент"},
        "link": {"type": "forward", "message": {
            "text": "оригинал", "attachments": [{"type": "video", "payload": {"token": "T", "url": "https://v/1"}}]}},
    }
    norm = max_content.normalize_message(msg, "message_created")
    assert norm["is_forward"] is True
    assert norm["text"] == "мой коммент"                  # свой комментарий сохранён
    assert [m["type"] for m in norm["media"]] == ["video"]  # медиа пересланного не потеряно
    assert norm["media"][0]["url"] == "https://v/1"


def test_tg_normalize_extracts_reply_quote():
    # Telegram reply_to_message содержит исходный Message; выносим текст/автора/entities
    # в общее поле reply, чтобы RuleDispatcher мог встроить цитату при пересылке.
    raw = {"message_id": 2, "chat": {"id": -100, "type": "channel", "title": "Hellow"},
           "sender_chat": {"title": "Hellow"}, "date": 1, "text": "ответ",
           "reply_to_message": {"message_id": 1, "chat": {"id": -100, "type": "channel"},
                                "sender_chat": {"title": "Hellow"},
                                "text": "исходный текст",
                                "entities": [{"type": "bold", "offset": 0, "length": 8}]}}
    norm = tg_content.normalize_message(raw, "channel_post")
    assert norm["reply_to_message_id"] == 1
    assert norm["reply"] == {"text": "исходный текст",
                             "entities": [{"type": "bold", "offset": 0, "length": 8}],
                             "from": "Hellow"}


def test_tg_normalize_extracts_reply_caption_quote():
    # Если ответ был на медиа с caption, цитируем caption и caption_entities.
    raw = {"message_id": 2, "chat": {"id": -100, "type": "channel", "title": "Hellow"},
           "sender_chat": {"title": "Hellow"}, "date": 1, "text": "ответ",
           "reply_to_message": {"message_id": 1, "chat": {"id": -100, "type": "channel"},
                                "sender_chat": {"title": "Hellow"},
                                "caption": "подпись",
                                "caption_entities": [{"type": "italic", "offset": 0, "length": 7}],
                                "photo": [{"file_id": "p1", "file_unique_id": "u1"}]}}
    norm = tg_content.normalize_message(raw, "channel_post")
    assert norm["reply"] == {"text": "подпись",
                             "entities": [{"type": "italic", "offset": 0, "length": 7}],
                             "from": "Hellow"}


def test_tg_normalize_prefers_selected_reply_quote():
    # Telegram может прислать TextQuote, если пользователь ответил на выделенный фрагмент;
    # переносим именно этот фрагмент, а не весь исходный текст.
    raw = {"message_id": 2, "chat": {"id": -100, "type": "channel", "title": "Hellow"},
           "sender_chat": {"title": "Hellow"}, "date": 1, "text": "ответ",
           "reply_to_message": {"message_id": 1, "chat": {"id": -100, "type": "channel"},
                                "sender_chat": {"title": "Hellow"},
                                "text": "полный длинный исходный текст",
                                "entities": [{"type": "italic", "offset": 0, "length": 6}]},
           "quote": {"text": "исходный",
                     "entities": [{"type": "bold", "offset": 0, "length": 8}],
                     "position": 15}}
    norm = tg_content.normalize_message(raw, "channel_post")
    assert norm["reply"] == {"text": "исходный",
                             "entities": [{"type": "bold", "offset": 0, "length": 8}],
                             "from": "Hellow"}


def test_tg_normalize_preserves_inline_keyboard_markup():
    markup = {"inline_keyboard": [[
        {"text": "Открыть", "url": "https://example.com"},
        {"text": "Действие", "callback_data": "source-action"},
    ]]}
    raw = {"message_id": 3, "chat": {"id": -100, "type": "channel", "title": "Hellow"},
           "sender_chat": {"title": "Hellow"}, "date": 1, "text": "кнопки",
           "reply_markup": markup}
    norm = tg_content.normalize_message(raw, "channel_post")
    assert norm["reply_markup"] == markup


# ---------------- dispatcher e2e (fake-клиенты, маршрутизация/медиа/трафик) ----------------
from telegram_sync.client import UploadFile  # noqa: E402


class FakeMax:
    def __init__(self): self.sent = []; self.edits = []
    async def send_message(self, **kw): self.sent.append(kw)
    async def edit_message(self, message_id, *, text=None, attachments=None,
                           fmt=None, notify=None):
        self.edits.append({"message_id": message_id, "text": text, "fmt": fmt})


class FakeMaxDl(FakeMax):
    """MAX-клиент с download_bytes (для MAX→TG: качаем медиа из MAX по url)."""
    def __init__(self, blobs=None):
        super().__init__()
        self.blobs = blobs or {}        # url -> (bytes, content_type)
        self.downloaded = []
        self.max_bytes_seen = []        # переданные потолки размера (для проверки конфигурации)
    async def download_bytes(self, url, *, max_bytes=None):
        self.downloaded.append(url)
        self.max_bytes_seen.append(max_bytes)
        v = self.blobs[url]             # KeyError → имитирует сбой скачивания
        # blobs могут быть (bytes, ct) или (bytes, ct, filename) — нормализуем к 3-кортежу.
        return v if len(v) == 3 else (v[0], v[1], None)


class FakeTg:
    def __init__(self, fail_photo=False, fail_document=False, fail_group=False):
        self.sent = []; self.photos = []; self.videos = []; self.docs = []; self.audios = []; self.groups = []
        self.edits = []
        self.fail_photo = fail_photo; self.fail_document = fail_document; self.fail_group = fail_group
    async def send_message(self, chat_id, text, parse_mode=None, message_thread_id=None,
                           reply_markup=None, disable_web_page_preview=None):
        item = {"chat_id": chat_id, "text": text, "parse_mode": parse_mode,
                "message_thread_id": message_thread_id}
        if disable_web_page_preview is not None:
            item["disable_web_page_preview"] = disable_web_page_preview
        if reply_markup is not None:
            item["reply_markup"] = reply_markup
        self.sent.append(item)
    async def send_photo(self, chat_id, photo, caption=None, parse_mode=None,
                         message_thread_id=None, reply_markup=None):
        if self.fail_photo:
            raise RuntimeError("sendPhoto: webp not accepted")
        item = {"chat_id": chat_id, "photo": photo, "caption": caption,
                "parse_mode": parse_mode, "message_thread_id": message_thread_id}
        if reply_markup is not None:
            item["reply_markup"] = reply_markup
        self.photos.append(item)
    async def send_video(self, chat_id, video, caption=None, parse_mode=None,
                         message_thread_id=None, reply_markup=None):
        item = {"chat_id": chat_id, "video": video, "caption": caption,
                "message_thread_id": message_thread_id}
        if reply_markup is not None:
            item["reply_markup"] = reply_markup
        self.videos.append(item)
    async def send_audio(self, chat_id, audio, caption=None, parse_mode=None,
                         message_thread_id=None, reply_markup=None):
        item = {"chat_id": chat_id, "audio": audio, "caption": caption,
                "message_thread_id": message_thread_id}
        if reply_markup is not None:
            item["reply_markup"] = reply_markup
        self.audios.append(item)
    async def send_document(self, chat_id, document, caption=None, parse_mode=None,
                            message_thread_id=None, reply_markup=None):
        if self.fail_document:
            raise RuntimeError("sendDocument failed")
        item = {"chat_id": chat_id, "document": document, "caption": caption,
                "message_thread_id": message_thread_id}
        if reply_markup is not None:
            item["reply_markup"] = reply_markup
        self.docs.append(item)
    async def send_media_group(self, chat_id, media, message_thread_id=None):
        if self.fail_group:
            raise RuntimeError("sendMediaGroup: invalid")
        self.groups.append({"chat_id": chat_id, "media": media, "message_thread_id": message_thread_id})
    async def edit_message_text(self, chat_id, message_id, text, *, parse_mode=None,
                                reply_markup=None, disable_web_page_preview=None):
        self.edits.append({"chat_id": chat_id, "message_id": message_id,
                           "text": text, "parse_mode": parse_mode,
                           "disable_web_page_preview": disable_web_page_preview})
    async def edit_message_caption(self, chat_id, message_id, caption, *, parse_mode=None,
                                   reply_markup=None):
        self.edits.append({"chat_id": chat_id, "message_id": message_id,
                           "caption": caption, "parse_mode": parse_mode})


def _disp_store_with_rule(a_msgr, a_id, b_msgr, b_id, direction="both", active=True):
    s = _fresh_store()
    acc = run(s.get_or_create_account("max", 1, None))["id"]
    run(s.set_subscription(acc, {"status": "active" if active else "inactive"}))
    run(s.add_rule({"account_id": acc, "a": {"messenger": a_msgr, "chat_id": a_id},
                    "b": {"messenger": b_msgr, "chat_id": b_id}, "dir": direction, "status": "active"}))
    return s, acc


def test_dispatch_tg_to_max_preserves_inline_keyboard_buttons():
    s, _acc = _disp_store_with_rule("tg", "-100", "max", "200", "to")
    fm = FakeMax()
    d = RuleDispatcher(s, max_client=fm, tg_bot_id=999)
    run(d.on_tg_message({"chat": {"id": -100, "type": "channel", "title": "Hellow"},
                         "sender_chat": {"title": "Hellow"},
                         "message_id": 10, "from": None, "text": "кнопки", "media": [],
                         "reply_markup": {"inline_keyboard": [[
                             {"text": "Сайт", "url": "https://example.com"},
                             {"text": "Callback", "callback_data": "source-action"},
                         ]]}}))
    assert fm.sent == [{
        "chat_id": "200",
        "text": "кнопки",
        "attachments": [{"type": "inline_keyboard", "payload": {"buttons": [[
            {"type": "link", "text": "Сайт", "url": "https://example.com"},
            {"type": "callback", "text": "Callback", "payload": FORWARDED_BUTTON_PAYLOAD},
        ]]}}],
        "fmt": None,
        "disable_link_preview": True,
    }]


def test_dispatch_tg_service_message_is_skipped():
    # Telegram service Message (добавление/удаление пользователя, pin/topic/миграция и т.п.)
    # не должен пересылаться по правилам даже при прямом вызове dispatcher.
    s, _acc = _disp_store_with_rule("tg", "-100", "max", "200", "to")
    fm = FakeMax()
    d = RuleDispatcher(s, max_client=fm, tg_bot_id=999)
    run(d.on_tg_message({"chat": {"id": -100, "type": "supergroup", "title": "Группа"},
                         "from": {"id": 5}, "message_id": 10, "text": None, "media": [],
                         "service": {"left_chat_member": {"id": 6, "first_name": "Аня"}}}))
    assert fm.sent == []


def test_dispatch_max_to_tg_preserves_inline_keyboard_buttons():
    s, _acc = _disp_store_with_rule("max", "100", "tg", "200", "to")
    ft = FakeTg()
    d = RuleDispatcher(s, tg_client=ft)
    run(d.on_max_message({"chat_id": "100", "sender_id": 5, "chat_type": "chat",
                          "sender": {"first_name": "Оля"}, "text": "кнопки",
                          "markup": None, "media": [], "attachments": [{
                              "type": "inline_keyboard",
                              "raw": {"type": "inline_keyboard", "payload": {"buttons": [[
                                  {"type": "link", "text": "Сайт", "url": "https://example.com"},
                                  {"type": "callback", "text": "Callback", "payload": "source-action"},
                              ]]}}},
                          ]}))
    assert ft.sent == [{
        "chat_id": "200",
        "text": "кнопки",
        "parse_mode": None,
        "message_thread_id": None,
        "disable_web_page_preview": True,
        "reply_markup": {"inline_keyboard": [[
            {"text": "Сайт", "url": "https://example.com"},
            {"text": "Callback", "callback_data": FORWARDED_BUTTON_PAYLOAD},
        ]]},
    }]


def test_dispatch_max_to_max_clean_copy():
    s, acc = _disp_store_with_rule("max", "100", "max", "200", "to")
    fm = FakeMax()
    d = RuleDispatcher(s, max_client=fm)
    run(d.on_max_message({"chat_id": "100", "sender_id": 5, "chat_type": "chat", "sender": {"first_name": "Оля"},
                          "text": "привет", "markup": None,
                          "media": [{"type": "image", "token": "TOK", "file_size": 1000}]}))
    assert len(fm.sent) == 1 and fm.sent[0]["chat_id"] == "200"
    assert fm.sent[0]["attachments"] == [{"type": "image", "payload": {"token": "TOK"}}]
    assert s.traffic(acc)["used_bytes"] == 1000


def test_dispatch_tg_topic_routes_exact_topic_and_legacy_chat_rule():
    s = _fresh_store()
    acc = run(s.get_or_create_account("tg", 777, None))["id"]
    run(s.set_subscription(acc, {"status": "active"}))
    # Точное правило на тему 42.
    run(s.add_rule({"account_id": acc, "a": {"messenger": "tg", "chat_id": "-100500", "thread_id": "42"},
                    "b": {"messenger": "max", "chat_id": "200"}, "dir": "to", "status": "active"}))
    # Старое правило на весь чат должно продолжать видеть сообщения из любых тем.
    run(s.add_rule({"account_id": acc, "a": {"messenger": "tg", "chat_id": "-100500"},
                    "b": {"messenger": "max", "chat_id": "201"}, "dir": "to", "status": "active"}))
    fm = FakeMax()
    d = RuleDispatcher(s, max_client=fm)
    msg = {"chat": {"id": -100500, "type": "supergroup"}, "message_id": 10,
           "message_thread_id": 42, "is_topic_message": True, "from": {"id": 5}, "text": "из 42"}
    run(d.on_tg_message(msg))
    assert [x["chat_id"] for x in fm.sent] == ["200", "201"]

    fm.sent.clear()
    run(d.on_tg_message({**msg, "message_thread_id": 99, "text": "из 99"}))
    assert [x["chat_id"] for x in fm.sent] == ["201"]          # точная тема 42 не сработала


def test_dispatch_tg_general_topic_matches_no_thread_message():
    s = _fresh_store()
    acc = run(s.get_or_create_account("tg", 777, None))["id"]
    run(s.set_subscription(acc, {"status": "active"}))
    run(s.add_rule({"account_id": acc, "a": {"messenger": "tg", "chat_id": "-100902", "thread_id": "1"},
                    "b": {"messenger": "max", "chat_id": "200"}, "dir": "to", "status": "active"}))
    targets = rules_mod.targets_for(s, "tg", "-100902")
    assert [(x["messenger"], x["chat_id"]) for x in targets] == [("max", "200")]


def test_dispatch_max_to_tg_topic_sends_message_thread_id():
    s, acc = _disp_store_with_rule("max", "100", "tg", "-100500", "to")
    rid = s.rules_of(acc)[0]["id"]
    run(s.update_rule(rid, {"b": {"messenger": "tg", "chat_id": "-100500", "thread_id": "42"}}))
    ft = FakeTg()
    d = RuleDispatcher(s, tg_client=ft)
    run(d.on_max_message({"chat_id": "100", "sender_id": 5, "chat_type": "chat",
                          "sender": {"first_name": "О"}, "text": "в тему", "markup": None, "media": []}))
    assert ft.sent == [{"chat_id": "-100500", "text": "в тему", "parse_mode": None,
                        "message_thread_id": 42, "disable_web_page_preview": True}]


def test_dispatch_to_tg_general_topic_omits_message_thread_id():
    s, acc = _disp_store_with_rule("max", "100", "tg", "-100500", "to")
    rid = s.rules_of(acc)[0]["id"]
    run(s.update_rule(rid, {"b": {"messenger": "tg", "chat_id": "-100500", "thread_id": "1"}}))
    ft = FakeTg()
    d = RuleDispatcher(s, tg_client=ft)
    run(d.on_max_message({"chat_id": "100", "sender_id": 5, "chat_type": "chat",
                          "sender": {"first_name": "О"}, "text": "в General",
                          "markup": None, "media": []}))
    assert ft.sent == [{"chat_id": "-100500", "text": "в General", "parse_mode": None,
                        "message_thread_id": None, "disable_web_page_preview": True}]


def test_tg_channel_max_chat_bidirectional_text_and_echo_guard():
    """TG-канал и MAX-чат передают plain text в обе стороны без эха.

    Проверяем этот класс источников:
    у TG-канала нет персонального `from`, MAX-чат имеет отправителя, правило `both`,
    а собственные копии бота не должны запускать обратную пересылку.
    """
    s = _fresh_store()
    acc = "acc_bidirectional"
    s._data["accounts"][acc] = {"id": acc, "phone": "79990000009", "created_at": int(time.time())}
    s._data["identities"]["max:91000001"] = acc
    s._data["identities"]["tg:920000001"] = acc
    s._data["subscriptions"][acc] = {"status": "active"}
    s._data["traffic"][acc] = {"used_bytes": 0, "topup_bytes": 0, "period_start": int(time.time())}
    s._data["rules"]["rule_bidirectional"] = {
        "id": "rule_bidirectional",
        "account_id": acc,
        "a": {"messenger": "tg", "chat_id": "-1007000000001"},
        "b": {"messenger": "max", "chat_id": "-70000000000001"},
        "dir": "both",
        "status": "active",
    }

    class HookedMax(FakeMax):
        def __init__(self): super().__init__(); self.on_sent = None; self.seq = 0
        async def send_message(self, **kw):
            self.sent.append(kw)
            self.seq += 1
            res = {"message": {"recipient": {"chat_id": kw.get("chat_id")},
                               "body": {"mid": f"mid.MAXCOPY{self.seq}"}}}
            if self.on_sent:
                self.on_sent(res)
            return res

    class HookedTg(FakeTg):
        def __init__(self): super().__init__(); self.on_sent = None; self.seq = 0
        async def send_message(self, chat_id, text, parse_mode=None, message_thread_id=None,
                               disable_web_page_preview=None, **kw):
            await super().send_message(chat_id, text, parse_mode=parse_mode,
                                       message_thread_id=message_thread_id,
                                       disable_web_page_preview=disable_web_page_preview, **kw)
            self.seq += 1
            res = {"message_id": self.seq, "chat": {"id": chat_id}}
            if self.on_sent:
                self.on_sent(res)
            return res

    fm, ft, si = HookedMax(), HookedTg(), _fresh_sent_index()
    d = RuleDispatcher(s, max_client=fm, tg_client=ft,
                       max_bot_id=930000001, tg_bot_id=9400000001, sent_index=si)
    fm.on_sent = d.note_max_sent
    ft.on_sent = d.note_tg_sent

    run(d.on_tg_message({"chat": {"id": -1007000000001, "type": "channel", "title": "Test channel"},
                         "sender_chat": {"id": -1007000000001, "title": "Test channel", "type": "channel"},
                         "message_id": 10, "from": None, "text": "tg channel to max chat",
                         "media": []}))
    assert fm.sent == [{"chat_id": "-70000000000001", "text": "tg channel to max chat",
                        "attachments": None, "fmt": None, "disable_link_preview": True}]
    assert si.contains("max", "-70000000000001", "mid.MAXCOPY1")

    # Echo от MAX-копии не должен уйти назад в TG.
    run(d.on_max_message({"chat_id": "-70000000000001", "sender_id": 930000001,
                          "chat_type": "chat", "sender": {"user_id": 930000001, "is_bot": True},
                          "mid": "mid.MAXCOPY1", "text": "tg channel to max chat", "media": []}))
    assert ft.sent == []

    run(d.on_max_message({"chat_id": "-70000000000001", "sender_id": 91000001,
                          "chat_type": "chat", "sender": {"first_name": "Иван", "last_name": "Петров"},
                          "mid": "mid.USER1", "text": "max chat to tg channel", "media": []}))
    assert ft.sent == [{"chat_id": "-1007000000001", "text": "max chat to tg channel",
                        "parse_mode": None, "message_thread_id": None,
                        "disable_web_page_preview": True}]
    assert si.contains("tg", "-1007000000001", 1)

    # Echo от TG-канала после отправки ботом тоже игнорируется.
    run(d.on_tg_message({"chat": {"id": "-1007000000001", "type": "channel", "title": "Test channel"},
                         "message_id": 1, "from": None, "text": "max chat to tg channel",
                         "media": []}))
    assert len(fm.sent) == 1


def test_dispatch_max_delivery_error_notifies_once_keeps_rule():
    # Отправка в MAX упала (например, у бота нет прав) → правило НЕ отключаем; уведомляем
    # владельца ОДИН раз (до восстановления), после успешной доставки пометка сбрасывается.
    s, acc = _disp_store_with_rule("max", "100", "max", "200", "to")
    class FlakyMax(FakeMax):
        def __init__(self): super().__init__(); self.fail = True
        async def send_message(self, **kw):
            if self.fail:
                raise RuntimeError("403 нет прав на отправку")
            self.sent.append(kw)
    fm = FlakyMax()
    d = RuleDispatcher(s, max_client=fm)
    events = []
    async def cb(messenger, chat_id, account_id): events.append((messenger, chat_id, account_id))
    d.delivery_error_cb = cb
    msg = {"chat_id": "100", "sender_id": 5, "chat_type": "chat", "sender": {"first_name": "О"},
           "text": "x", "markup": None, "media": []}
    run(d.on_max_message(msg)); run(d.on_max_message(msg))
    assert events == [("max", "200", acc)]              # уведомили один раз, без спама
    assert s.rules_of(acc)[0]["status"] == "active"     # правило НЕ отключено
    fm.fail = False
    run(d.on_max_message(msg))                           # доставка прошла → пометка сброшена
    assert len(fm.sent) == 1
    fm.fail = True
    run(d.on_max_message(msg))                           # снова сбой → снова уведомление
    assert len(events) == 2


def test_set_rule_delivery_warn_idempotent():
    # Флаг предупреждения пишется на диск только при ИЗМЕНЕНии значения (безопасно звать
    # на каждое сообщение). Возвращает True, если значение поменялось.
    s = _fresh_store()
    acc = run(s.get_or_create_account("max", 1, None))["id"]
    rid = run(s.add_rule({"account_id": acc, "a": {"messenger": "max", "chat_id": "1"},
                          "b": {"messenger": "max", "chat_id": "2"}, "dir": "to", "status": "active"}))["id"]
    assert run(s.set_rule_delivery_warn(rid, True)) is True
    assert run(s.set_rule_delivery_warn(rid, True)) is False     # уже стоит — без записи
    assert s.rule(rid)["delivery_warn"] is True
    assert run(s.set_rule_delivery_warn(rid, False)) is True
    assert run(s.set_rule_delivery_warn(rid, False)) is False    # уже снято
    assert "delivery_warn" not in s.rule(rid)
    assert run(s.set_rule_delivery_warn("nope", True)) is False  # нет такого правила


_WARN_MSG = {"sender_id": 5, "chat_type": "chat", "sender": {"first_name": "О"},
             "text": "x", "markup": None, "media": []}


def _warn_dispatcher(s, fail_to=("200",)):
    """Диспетчер с MAX-клиентом, у которого отправка В чаты из (изменяемого) self.fail_set
    падает; остальные ок. Возвращает (d, refs_отправленных_уведомлений, refs_удалённых)."""
    class FM(FakeMax):
        def __init__(self): super().__init__(); self.fail_set = {str(x) for x in fail_to}
        async def send_message(self, **kw):
            if str(kw.get("chat_id")) in self.fail_set:
                raise RuntimeError("403 нет прав на отправку")
            self.sent.append(kw)

    d = RuleDispatcher(s, max_client=FM())
    sent_refs, cleared = [], []
    async def err_cb(m, c, a): sent_refs.append((m, c)); return {"mid": f"mid-{c}"}
    async def clr_cb(m, c, ref): cleared.append((m, c, ref))
    d.delivery_error_cb = err_cb
    d.delivery_clear_cb = clr_cb
    return d, sent_refs, cleared


def test_delivery_fail_then_success_clears_banner_and_deletes_chat_notice():
    # Сбой → баннер mini-app + уведомление в чат (ОДИН раз, повтор не дублируется). Успешная
    # доставка в этот чат → баннер гаснет И сообщение в чате удаляется (оба канала исчезают).
    s, acc = _disp_store_with_rule("max", "100", "max", "200", "to")
    rid = s.rules_of(acc)[0]["id"]
    d, sent_refs, cleared = _warn_dispatcher(s, fail_to=("200",))
    run(d.on_max_message({**_WARN_MSG, "chat_id": "100"}))      # сбой доставки в 200
    assert s.rule(rid)["delivery_warn"] is True                  # баннер
    assert sent_refs == [("max", "200")]                         # уведомление в чат — один раз
    run(d.on_max_message({**_WARN_MSG, "chat_id": "100"}))      # повтор сбоя — ничего нового
    assert sent_refs == [("max", "200")] and cleared == []
    d.max_client.fail_set.discard("200")                        # 200 снова принимает → доставка успешна
    run(d.on_max_message({**_WARN_MSG, "chat_id": "100"}))
    assert "delivery_warn" not in s.rule(rid)                    # баннер погас
    assert cleared == [("max", "200", {"mid": "mid-200"})]       # сообщение в чате удалено


def test_dismiss_chat_and_app_rearm_independently():
    # Скрытие в ЧАТЕ ре-армит только чат (следующий сбой шлёт уведомление снова), баннер не
    # трогает; скрытие в ПРИЛОЖЕНИИ ре-армит только баннер, уведомление в чат не дублирует.
    s, acc = _disp_store_with_rule("max", "100", "max", "200", "to")
    rid = s.rules_of(acc)[0]["id"]
    d, sent_refs, _ = _warn_dispatcher(s, fail_to=("200",))
    run(d.on_max_message({**_WARN_MSG, "chat_id": "100"}))      # сбой: баннер + 1 уведомление
    assert s.rule(rid)["delivery_warn"] is True and len(sent_refs) == 1
    run(d.on_max_message({**_WARN_MSG, "chat_id": "100"}))      # повтор: ничего
    assert len(sent_refs) == 1
    d.note_chat_warn_hidden("max", "200")                       # «Скрыть» В ЧАТЕ → ре-арм чата
    run(d.on_max_message({**_WARN_MSG, "chat_id": "100"}))
    assert len(sent_refs) == 2                                   # уведомление в чат пришло снова
    run(s.set_rule_delivery_warn(rid, False))                  # «Скрыть» В ПРИЛОЖЕНИИ → ре-арм баннера
    run(d.on_max_message({**_WARN_MSG, "chat_id": "100"}))
    assert s.rule(rid)["delivery_warn"] is True                  # баннер вернулся
    assert len(sent_refs) == 2                                   # а уведомление в чат НЕ продублировано


def test_bidirectional_success_one_side_keeps_banner():
    # Двустороннее правило max:100 ⇄ max:200. Доставка В 200 падает, В 100 — успешна: баннер
    # держится, пока 200 в сбое; гаснет только когда восстановятся ОБЕ стороны.
    s, acc = _disp_store_with_rule("max", "100", "max", "200", "both")
    rid = s.rules_of(acc)[0]["id"]
    d, _, _ = _warn_dispatcher(s, fail_to=("200",))
    run(d.on_max_message({**_WARN_MSG, "chat_id": "100"}))      # 100→200 падает → баннер
    assert s.rule(rid)["delivery_warn"] is True
    run(d.on_max_message({**_WARN_MSG, "chat_id": "200"}))      # 200→100 успех (другая цель)
    assert s.rule(rid)["delivery_warn"] is True                  # баннер ОСТАЁТСЯ (200 ещё в сбое)
    d.max_client.fail_set.discard("200")                        # 200 начинает принимать
    run(d.on_max_message({**_WARN_MSG, "chat_id": "100"}))      # 100→200 успех → нет сбойных целей
    assert "delivery_warn" not in s.rule(rid)                    # баннер гаснет


def test_rule_dismiss_warning_via_api_and_ownership():
    # Сквозной HTTP: list отдаёт deliveryWarn; POST /dismiss-warning снимает флаг; чужой
    # аккаунт скрыть не может (404).
    from fastapi.testclient import TestClient
    from control.api import create_app
    s = _fresh_store()
    _write_ownership(config.MAX_OWNERSHIP_FILE, {
        "1": {"user_id": 777, "title": "A", "rights_ok": True, "type": "channel"},
        "2": {"user_id": 777, "title": "B", "rights_ok": True, "type": "channel"},
    })
    c = TestClient(create_app(s))
    r = _auth_contact(c, 777, "79001234567")
    H = {"Authorization": f"Bearer {r.json()['token']}"}
    _accept_legal(c, H)
    rid = c.post("/api/rules", json={"aId": "max:1", "bId": "max:2", "dir": "to"}, headers=H).json()["rule"]["id"]
    run(s.set_rule_delivery_warn(rid, True))             # как поднял бы диспетчер при сбое
    assert c.get("/api/rules", headers=H).json()["rules"][0]["deliveryWarn"] is True
    dr = c.post(f"/api/rules/{rid}/dismiss-warning", headers=H)
    assert dr.status_code == 200, dr.text
    assert dr.json()["rule"]["deliveryWarn"] is False
    assert c.get("/api/rules", headers=H).json()["rules"][0]["deliveryWarn"] is False
    r2 = _auth_contact(c, 888, "79009998877")
    H2 = {"Authorization": f"Bearer {r2.json()['token']}"}
    run(s.set_rule_delivery_warn(rid, True))
    assert c.post(f"/api/rules/{rid}/dismiss-warning", headers=H2).status_code == 404


def test_dispatch_max_to_max_counts_traffic_via_content_length():
    # MAX→MAX: у реальных MAX-вложений НЕТ file_size в payload (только url/token) — раньше
    # трафик считался 0. Теперь размер берётся по Content-Length публичного url (HEAD, без
    # скачивания) и начисляется аккаунту-владельцу правила.
    s, acc = _disp_store_with_rule("max", "100", "max", "200", "to")

    class FakeMaxCL(FakeMax):
        def __init__(self): super().__init__(); self.head = []
        async def content_length(self, url): self.head.append(url); return 4242

    fm = FakeMaxCL()
    d = RuleDispatcher(s, max_client=fm)
    run(d.on_max_message({"chat_id": "100", "sender_id": 5, "chat_type": "channel", "sender": {},
                          "text": "", "markup": None,
                          "media": [{"type": "image", "token": "TOK", "url": "https://i.oneme.ru/x"}]}))
    assert fm.head == ["https://i.oneme.ru/x"]                  # размер узнали по url (HEAD)
    assert fm.sent[0]["attachments"] == [{"type": "image", "payload": {"token": "TOK"}}]
    assert s.traffic(acc)["used_bytes"] == 4242                 # начислено владельцу правила
    rid = next(iter(s.table("rules")))
    assert s.traffic(acc)["per_rule"][rid] == 4242


def test_dispatch_max_to_tg_uploads_photo():
    # MAX→TG: картинка скачивается из MAX по url и ЗАГРУЖАЕТСЯ в Telegram байтами
    # (UploadFile), а не передаётся ссылкой. Трафик — по фактически скачанным байтам.
    s, acc = _disp_store_with_rule("max", "100", "tg", "200", "both")
    ft = FakeTg()
    fm = FakeMaxDl({"https://i.oneme.ru/x": (b"IMGDATA1234", "image/webp")})
    d = RuleDispatcher(s, max_client=fm, tg_client=ft)
    run(d.on_max_message({"chat_id": "100", "sender_id": 5, "chat_type": "channel", "sender": {},
                          "text": "hi", "media": [{"type": "image", "url": "https://i.oneme.ru/x"}]}))
    assert fm.downloaded == ["https://i.oneme.ru/x"]
    assert len(ft.photos) == 1 and ft.photos[0]["chat_id"] == "200"
    up = ft.photos[0]["photo"]
    assert isinstance(up, UploadFile) and up.data == b"IMGDATA1234" and up.content_type == "image/webp"
    assert ft.photos[0]["caption"] == "hi"
    assert s.traffic(acc)["used_bytes"] == len(b"IMGDATA1234")


def test_dispatch_max_to_tg_uses_content_disposition_filename():
    # MAX не отдаёт имя файла в payload вложения (только url/token/fileId) — настоящее имя
    # приходит из Content-Disposition при скачивании. Оно должно стать именем документа в TG
    # (а не безликий «document.bin»), а octet-stream content-type — уточниться по расширению.
    s, acc = _disp_store_with_rule("max", "100", "tg", "200", "both")
    ft = FakeTg()
    fm = FakeMaxDl({"https://f/doc": (b"REPORTDATA", "application/octet-stream", "Отчёт 2026.pdf")})
    d = RuleDispatcher(s, max_client=fm, tg_client=ft)
    run(d.on_max_message({"chat_id": "100", "sender_id": 5, "chat_type": "channel", "sender": {},
                          "text": "", "media": [{"type": "file", "url": "https://f/doc"}]}))
    assert len(ft.docs) == 1
    up = ft.docs[0]["document"]
    assert isinstance(up, UploadFile) and up.filename == "Отчёт 2026.pdf"
    assert up.content_type == "application/pdf"     # octet-stream уточнён по расширению .pdf


def test_filename_from_content_disposition_parser():
    from max_sync.client import _filename_from_cd
    assert _filename_from_cd(None) is None
    assert _filename_from_cd("inline") is None
    assert _filename_from_cd('attachment; filename="a.mp4"') == "a.mp4"
    # filename* (RFC 5987) имеет приоритет и percent-декодируется по charset
    assert _filename_from_cd("attachment; filename=\"f.bin\"; "
                             "filename*=utf-8''%D0%9E%D1%82%D1%87%D1%91%D1%82.pdf") == "Отчёт.pdf"
    # basename: путь и backslash-пути вырезаются (без traversal)
    assert _filename_from_cd('attachment; filename="/etc/passwd"') == "passwd"
    assert _filename_from_cd('attachment; filename="..\\..\\x.exe"') == "x.exe"
    # percent-кодированные разделители RFC 5987 (charset%27%27…) тоже декодируются
    assert _filename_from_cd("attachment; filename*=UTF-8%27%27report.pdf") == "report.pdf"
    # bidi-управляющие (U+202E и пр.) удаляются — спуфинг расширения не проходит
    spoof = _filename_from_cd('attachment; filename="invoice‮gpj.exe"')
    assert "‮" not in spoof and spoof == "invoicegpj.exe"


def test_dispatch_max_to_tg_uploads_video_and_audio_and_file():
    # MAX→TG: video→sendVideo, audio→sendAudio, file→sendDocument — все байтами.
    for mtype, attr, url in [("video", "videos", "https://v/1"), ("audio", "audios", "https://a/1"),
                             ("file", "docs", "https://f/1")]:
        s, acc = _disp_store_with_rule("max", "100", "tg", "200", "both")
        ft = FakeTg()
        fm = FakeMaxDl({url: (b"BLOB" * 10, "application/octet-stream")})
        d = RuleDispatcher(s, max_client=fm, tg_client=ft)
        run(d.on_max_message({"chat_id": "100", "sender_id": 5, "chat_type": "channel", "sender": {},
                              "text": "", "media": [{"type": mtype, "url": url}]}))
        recs = getattr(ft, attr)
        assert len(recs) == 1, f"{mtype}: ожидался 1 вызов в {attr}, получено {recs}"
        assert s.traffic(acc)["used_bytes"] == 40


def test_dispatch_max_to_tg_photo_webp_falls_back_to_document():
    # sendPhoto отверг webp → файл не теряем: уходит документом.
    s, acc = _disp_store_with_rule("max", "100", "tg", "200", "both")
    ft = FakeTg(fail_photo=True)
    fm = FakeMaxDl({"https://i/x": (b"WEBPBYTES", "image/webp")})
    d = RuleDispatcher(s, max_client=fm, tg_client=ft)
    run(d.on_max_message({"chat_id": "100", "sender_id": 5, "chat_type": "channel", "sender": {},
                          "text": "cap", "media": [{"type": "image", "url": "https://i/x"}]}))
    assert ft.photos == [] and len(ft.docs) == 1
    assert isinstance(ft.docs[0]["document"], UploadFile) and ft.docs[0]["document"].data == b"WEBPBYTES"
    assert s.traffic(acc)["used_bytes"] == len(b"WEBPBYTES")


def test_dispatch_max_to_tg_album_as_media_group():
    # Альбом из двух картинок MAX с коротким текстом → один media group с caption.
    s, acc = _disp_store_with_rule("max", "100", "tg", "200", "both")
    ft = FakeTg()
    fm = FakeMaxDl({"https://i/a": (b"AAA", "image/jpeg"), "https://i/b": (b"BBBB", "image/jpeg")})
    d = RuleDispatcher(s, max_client=fm, tg_client=ft)
    run(d.on_max_message({"chat_id": "100", "sender_id": 5, "chat_type": "channel", "sender": {},
                          "text": "album", "media": [{"type": "image", "url": "https://i/a"},
                                                     {"type": "image", "url": "https://i/b"}]}))
    assert len(ft.groups) == 1 and len(ft.groups[0]["media"]) == 2
    g = ft.groups[0]["media"]
    assert g[0]["type"] == "photo" and isinstance(g[0]["media"], UploadFile)
    assert g[0]["caption"] == "album" and "caption" not in g[1]
    assert ft.sent == []
    assert s.traffic(acc)["used_bytes"] == len(b"AAA") + len(b"BBBB")


def test_dispatch_max_to_tg_mixed_photo_video_album_as_media_group():
    # MAX может прислать один media group из картинок и видео. Telegram sendMediaGroup
    # поддерживает смешанные photo+video, поэтому не дробим; короткий текст остаётся caption.
    s, acc = _disp_store_with_rule("max", "100", "tg", "200", "both")
    ft = FakeTg()
    fm = FakeMaxDl({
        "https://i/a": (b"AAA", "image/jpeg"),
        "https://v/b": (b"VIDEO", "video/mp4"),
    })
    d = RuleDispatcher(s, max_client=fm, tg_client=ft)
    run(d.on_max_message({"chat_id": "100", "sender_id": 5, "chat_type": "channel", "sender": {},
                          "text": "mixed", "media": [{"type": "image", "url": "https://i/a"},
                                                     {"type": "video", "url": "https://v/b"}]}))
    assert len(ft.groups) == 1 and len(ft.groups[0]["media"]) == 2
    g = ft.groups[0]["media"]
    assert [m["type"] for m in g] == ["photo", "video"]
    assert g[0]["caption"] == "mixed" and "caption" not in g[1]
    assert ft.photos == [] and ft.videos == []
    assert ft.sent == []
    assert s.traffic(acc)["used_bytes"] == len(b"AAA") + len(b"VIDEO")


def test_dispatch_max_to_tg_download_fail_falls_back_to_link():
    # Скачивание медиа из MAX не удалось → текст + ссылка (медиа не теряем молча),
    # трафик не списывается.
    s, acc = _disp_store_with_rule("max", "100", "tg", "200", "both")
    ft = FakeTg()
    fm = FakeMaxDl({})                      # пустой → download_bytes бросит KeyError
    d = RuleDispatcher(s, max_client=fm, tg_client=ft)
    run(d.on_max_message({"chat_id": "100", "sender_id": 5, "chat_type": "channel", "sender": {},
                          "text": "hi", "media": [{"type": "image", "url": "https://i/x"}]}))
    assert ft.photos == [] and len(ft.sent) == 1
    assert (f'<blockquote>{LINK_NOTE} в источнике "100" '
            'в мессенджере max.</blockquote>') in ft.sent[0]["text"]
    assert ft.sent[0]["parse_mode"] == "HTML"
    assert s.traffic(acc)["used_bytes"] == 0


def test_dispatch_max_to_tg_download_cap_is_configurable(monkeypatch):
    # Потолок скачивания MAX→TG берётся из config.TG_UPLOAD_MAX_BYTES (а не хардкод 50 МБ),
    # поэтому с локальным Bot API сервером его можно поднять до 2000 МБ → лимит снимается.
    monkeypatch.setattr(config, "TG_UPLOAD_MAX_BYTES", 2_097_152_000)
    s, acc = _disp_store_with_rule("max", "100", "tg", "200", "both")
    ft = FakeTg()
    fm = FakeMaxDl({"https://i/big": (b"BIGBLOB", "image/jpeg")})
    d = RuleDispatcher(s, max_client=fm, tg_client=ft)
    run(d.on_max_message({"chat_id": "100", "sender_id": 5, "chat_type": "channel", "sender": {},
                          "text": "", "media": [{"type": "image", "url": "https://i/big"}]}))
    assert fm.max_bytes_seen == [2_097_152_000]
    assert len(ft.photos) == 1 and isinstance(ft.photos[0]["photo"], UploadFile)


def test_dispatch_max_to_tg_long_text_sent_as_separate_message():
    # Подпись к медиа в Telegram ≤1024: длинный текст уходит ОТДЕЛЬНЫМ сообщением,
    # медиа — без подписи (ничего не теряем).
    s, acc = _disp_store_with_rule("max", "100", "tg", "200", "both")
    ft = FakeTg()
    fm = FakeMaxDl({"https://i/x": (b"PIC", "image/jpeg")})
    d = RuleDispatcher(s, max_client=fm, tg_client=ft)
    longtext = "А" * 1500
    run(d.on_max_message({"chat_id": "100", "sender_id": 5, "chat_type": "channel", "sender": {},
                          "text": longtext, "media": [{"type": "image", "url": "https://i/x"}]}))
    assert len(ft.photos) == 1 and ft.photos[0]["caption"] is None       # медиа без подписи
    assert len(ft.sent) == 1 and ft.sent[0]["text"] == longtext          # текст отдельно
    assert s.traffic(acc)["used_bytes"] == len(b"PIC")


def test_dispatch_max_to_tg_long_album_caption_sent_after_media_group():
    # Живой этап 4.6: длинный MAX-текст вместе с несколькими media не должен стать caption
    # media group — Telegram ограничивает caption 1024 UTF-16 юнитами. Сначала отправляем
    # альбом без подписи, затем полный текст отдельным сообщением.
    s, acc = _disp_store_with_rule("max", "100", "tg", "200", "both")
    ft = FakeTg()
    fm = FakeMaxDl({
        "https://i/a": (b"AA", "image/jpeg"),
        "https://i/b": (b"BBB", "image/jpeg"),
        "https://v/c": (b"VIDEO", "video/mp4"),
    })
    d = RuleDispatcher(s, max_client=fm, tg_client=ft)
    longtext = "Б" * 1500
    run(d.on_max_message({"chat_id": "100", "sender_id": 5, "chat_type": "channel", "sender": {},
                          "text": longtext, "media": [{"type": "image", "url": "https://i/a"},
                                                      {"type": "image", "url": "https://i/b"},
                                                      {"type": "video", "url": "https://v/c"}]}))
    assert len(ft.groups) == 1 and [m["type"] for m in ft.groups[0]["media"]] == [
        "photo", "photo", "video"]
    assert all("caption" not in m for m in ft.groups[0]["media"])
    assert ft.sent == [{"chat_id": "200", "text": longtext, "parse_mode": None,
                        "message_thread_id": None, "disable_web_page_preview": True}]
    assert ft.photos == [] and ft.videos == [] and ft.docs == []
    assert s.traffic(acc)["used_bytes"] == len(b"AA") + len(b"BBB") + len(b"VIDEO")


def test_dispatch_max_to_tg_partial_album_no_duplicate_link():
    # Смешанный альбом (фото+документ) шлётся поэлементно; документ падает. Уже отправленное
    # фото НЕ должно сопровождаться дублирующим текст+ссылкой; текст уходит после успешного фото.
    s, acc = _disp_store_with_rule("max", "100", "tg", "200", "both")
    ft = FakeTg(fail_document=True)
    fm = FakeMaxDl({"https://i/a": (b"PIC123", "image/jpeg"), "https://f/b": (b"DOCDATA", "application/pdf")})
    d = RuleDispatcher(s, max_client=fm, tg_client=ft)
    run(d.on_max_message({"chat_id": "100", "sender_id": 5, "chat_type": "channel", "sender": {},
                          "text": "cap", "media": [{"type": "image", "url": "https://i/a"},
                                                   {"type": "file", "url": "https://f/b"}]}))
    assert len(ft.photos) == 1 and ft.docs == []          # фото ушло, документ упал
    assert ft.photos[0]["caption"] is None
    assert ft.sent == [{"chat_id": "200", "text": "cap", "parse_mode": None,
                        "message_thread_id": None, "disable_web_page_preview": True}]
    assert s.traffic(acc)["used_bytes"] == len(b"PIC123")  # трафик только по отправленному


def test_dispatch_max_to_tg_same_type_documents_grouped():
    # Альбом из нескольких документов одного типа группируется в одну media group.
    s, acc = _disp_store_with_rule("max", "100", "tg", "200", "both")
    ft = FakeTg()
    fm = FakeMaxDl({"https://f/a": (b"AA", "application/pdf"), "https://f/b": (b"BB", "application/pdf")})
    d = RuleDispatcher(s, max_client=fm, tg_client=ft)
    run(d.on_max_message({"chat_id": "100", "sender_id": 5, "chat_type": "channel", "sender": {},
                          "text": "", "media": [{"type": "file", "url": "https://f/a"},
                                                {"type": "file", "url": "https://f/b"}]}))
    assert len(ft.groups) == 1 and [m["type"] for m in ft.groups[0]["media"]] == ["document", "document"]
    assert s.traffic(acc)["used_bytes"] == 4


def test_dispatch_max_to_tg_media_group_fail_falls_back_per_item():
    # sendMediaGroup упал → поэлементная отправка (медиа не теряется, без дубля).
    s, acc = _disp_store_with_rule("max", "100", "tg", "200", "both")
    ft = FakeTg(fail_group=True)
    fm = FakeMaxDl({"https://i/a": (b"AA", "image/jpeg"), "https://i/b": (b"BBB", "image/jpeg")})
    d = RuleDispatcher(s, max_client=fm, tg_client=ft)
    run(d.on_max_message({"chat_id": "100", "sender_id": 5, "chat_type": "channel", "sender": {},
                          "text": "cap", "media": [{"type": "image", "url": "https://i/a"},
                                                   {"type": "image", "url": "https://i/b"}]}))
    assert ft.groups == [] and len(ft.photos) == 2        # упали в поэлементную отправку
    assert ft.photos[0]["caption"] is None and ft.photos[1]["caption"] is None
    assert ft.sent == [{"chat_id": "200", "text": "cap", "parse_mode": None,
                        "message_thread_id": None, "disable_web_page_preview": True}]
    assert s.traffic(acc)["used_bytes"] == len(b"AA") + len(b"BBB")


def test_dispatch_max_to_tg_caption_length_in_utf16_units():
    # Лимит подписи Telegram — в UTF-16 юнитах. Текст из ASCII+эмодзи: code points ≤1024,
    # но UTF-16 >1024 → должен уйти ОТДЕЛЬНЫМ сообщением, иначе Telegram отверг бы подпись.
    s, acc = _disp_store_with_rule("max", "100", "tg", "200", "both")
    ft = FakeTg()
    fm = FakeMaxDl({"https://i/x": (b"PIC", "image/jpeg")})
    d = RuleDispatcher(s, max_client=fm, tg_client=ft)
    text = "a" * 1023 + "😀"                                 # 1024 code points, 1025 UTF-16 units
    run(d.on_max_message({"chat_id": "100", "sender_id": 5, "chat_type": "channel", "sender": {},
                          "text": text, "media": [{"type": "image", "url": "https://i/x"}]}))
    assert len(ft.photos) == 1 and ft.photos[0]["caption"] is None
    assert len(ft.sent) == 1 and ft.sent[0]["text"] == text


def test_dispatch_max_forward_post_media_reaches_tg_e2e():
    # Сквозной путь баг-репорта: пост MAX-канала приходит ФОРВАРДОМ (контент в link.message);
    # после нормализации медиа должно реально уйти в Telegram, а не превратиться в " ".
    s, acc = _disp_store_with_rule("max", "100", "tg", "200", "both")
    ft = FakeTg()
    fm = FakeMaxDl({"https://i/1": (b"PIC", "image/webp")})
    d = RuleDispatcher(s, max_client=fm, tg_client=ft)
    raw = {
        "recipient": {"chat_id": "100", "chat_type": "channel"},
        "body": {"mid": "TOP", "text": ""},
        "link": {"type": "forward", "message": {
            "mid": "ORIG", "text": "пост с фото",
            "attachments": [{"type": "image", "payload": {"token": "T", "url": "https://i/1"}}]}},
    }
    norm = max_content.normalize_message(raw, "message_created")
    run(d.on_max_message(norm))
    assert len(ft.photos) == 1 and isinstance(ft.photos[0]["photo"], UploadFile)
    assert ft.photos[0]["photo"].data == b"PIC" and ft.photos[0]["caption"] == "пост с фото"
    assert ft.sent == []                                # НЕ ушло пустым текстом
    assert s.traffic(acc)["used_bytes"] == len(b"PIC")


def test_dispatch_tg_to_max_media_becomes_unsupported_note():
    # TG→MAX без tg_client: медиа перенести нельзя → текст доставляется + строка
    # с новой подсказкой о полном сообщении. chat_id строковый (без -100) → ссылки нет.
    s, acc = _disp_store_with_rule("tg", "200", "max", "100", "both")
    fm = FakeMax()
    d = RuleDispatcher(s, max_client=fm, tg_bot_id=999)
    run(d.on_tg_message({"chat": {"id": "200", "type": "supergroup"}, "from": {"id": 5},
                         "text": "post", "media": [{"type": "photo", "file_id": "FID", "file_size": 3000}]}))
    assert len(fm.sent) == 1 and fm.sent[0]["attachments"] is None
    assert "post" in fm.sent[0]["text"]
    assert (f'<blockquote>{LINK_NOTE} в источнике "200" '
            'в мессенджере telegram.</blockquote>') in fm.sent[0]["text"]
    assert fm.sent[0]["fmt"] == "html"
    assert s.traffic(acc)["used_bytes"] == 0  # медиа не отправлено → трафик не учтён


def test_dispatch_tg_to_max_unsupported_appends_hyperlink_to_original():
    # Приватная супергруппа (id -100…) + message_id → строка-заметка с РАБОЧЕЙ
    # гиперссылкой t.me/c на оригинал, format=html.
    s, acc = _disp_store_with_rule("tg", "-1001234567890", "max", "100", "both")
    fm = FakeMax()
    d = RuleDispatcher(s, max_client=fm, tg_bot_id=999)
    run(d.on_tg_message({"chat": {"id": -1001234567890, "type": "supergroup", "title": "Hellow"}, "from": {"id": 5},
                         "message_id": 77, "text": "пост",
                         "media": [{"type": "document", "file_id": "FID", "file_size": 10}]}))
    assert len(fm.sent) == 1 and fm.sent[0]["attachments"] is None
    txt = fm.sent[0]["text"]
    assert (f'<blockquote>{LINK_NOTE} в источнике "<a href="https://t.me/c/1234567890/77">'
            'Hellow</a>" в мессенджере telegram.</blockquote>') in txt
    assert fm.sent[0]["fmt"] == "html"


def test_partial_delivery_note_is_under_signature_footer():
    s, acc = _disp_store_with_rule("tg", "-1001234567890", "max", "100", "both")
    run(s.update_rule(s.rules_of(acc)[0]["id"], {"signature": True}))
    fm = FakeMax()
    d = RuleDispatcher(s, max_client=fm, tg_bot_id=999)

    run(d.on_tg_message({"chat": {"id": -1001234567890, "type": "supergroup", "title": "Hellow"},
                         "from": {"id": 5, "first_name": "Иван"}, "message_id": 78,
                         "text": "пост",
                         "media": [{"type": "document", "file_id": "FID", "file_size": 10}]}))

    txt = fm.sent[0]["text"]
    assert txt.index("Автор <b>Иван</b>") < txt.index(LINK_NOTE)
    assert (f'<blockquote>{LINK_NOTE} в источнике "<a href="https://t.me/c/1234567890/78">'
            'Hellow</a>" в мессенджере telegram.</blockquote>') in txt
    assert fm.sent[0]["fmt"] == "html"


def test_dispatch_tg_to_tg_preserves_hyperlink():
    # TG→TG: гиперссылка (entity text_link) сохраняется как <a href> (parse_mode=HTML).
    s, acc = _disp_store_with_rule("tg", "200", "tg", "300", "both")
    ft = FakeTg()
    d = RuleDispatcher(s, tg_client=ft, tg_bot_id=999)
    run(d.on_tg_message({"chat": {"id": "200", "type": "supergroup"}, "from": {"id": 5},
                         "text": "see google",
                         "entities": [{"type": "text_link", "offset": 4, "length": 6,
                                       "url": "https://google.com"}], "media": []}))
    assert len(ft.sent) == 1 and ft.sent[0]["chat_id"] == "300"
    assert '<a href="https://google.com">google</a>' in ft.sent[0]["text"]
    assert ft.sent[0]["parse_mode"] == "HTML"


def test_dispatch_tg_to_tg_long_single_media_caption_sent_after_photo():
    # TG→TG: у sendPhoto caption максимум 1024 UTF-16 юнита. Длинный текст должен уйти
    # отдельным сообщением после фото, иначе Telegram отвергает фото и оно пропадает.
    s, acc = _disp_store_with_rule("tg", "200", "tg", "300", "both")
    ft = FakeTg()
    d = RuleDispatcher(s, tg_client=ft, tg_bot_id=999)
    longtext = "Модель Сириуса " + "А" * 1500

    run(d.on_tg_message({"chat": {"id": "200", "type": "supergroup"}, "from": {"id": 5},
                         "message_id": 177, "text": longtext,
                         "media": [{"type": "photo", "file_id": "FID", "file_size": 112131}]}))

    assert len(ft.photos) == 1 and ft.photos[0]["photo"] == "FID"
    assert ft.photos[0]["caption"] is None
    assert ft.sent == [{"chat_id": "300", "text": longtext, "parse_mode": None,
                        "message_thread_id": None, "disable_web_page_preview": True}]
    assert s.traffic(acc)["used_bytes"] == 112131


def test_dispatch_tg_to_max_preserves_hyperlink():
    # TG→MAX: гиперссылка сохраняется как <a href> с fmt=html.
    s, acc = _disp_store_with_rule("tg", "200", "max", "100", "both")
    fm = FakeMax()
    d = RuleDispatcher(s, max_client=fm, tg_bot_id=999)
    run(d.on_tg_message({"chat": {"id": "200", "type": "supergroup"}, "from": {"id": 5},
                         "text": "see google",
                         "entities": [{"type": "text_link", "offset": 4, "length": 6,
                                       "url": "https://google.com"}], "media": []}))
    assert len(fm.sent) == 1
    assert '<a href="https://google.com">google</a>' in fm.sent[0]["text"]
    assert fm.sent[0]["fmt"] == "html"


def test_dispatch_tg_to_max_preserves_code_entities():
    # TG→MAX: inline code и pre не должны теряться; pre отправляем блочным тегом.
    s, acc = _disp_store_with_rule("tg", "200", "max", "100", "both")
    fm = FakeMax()
    d = RuleDispatcher(s, max_client=fm, tg_bot_id=999)
    text = "inline: код\nblock: Привет"
    run(d.on_tg_message({"chat": {"id": "200", "type": "supergroup"}, "from": {"id": 5},
                         "text": text,
                         "entities": [{"type": "code", "offset": 8, "length": 3},
                                      {"type": "pre", "offset": 19, "length": 6}],
                         "media": []}))
    assert len(fm.sent) == 1
    assert "`<code>код</code>`" in fm.sent[0]["text"]
    assert "```\n<pre>Привет</pre>\n```" in fm.sent[0]["text"]
    assert fm.sent[0]["fmt"] == "html"


def test_dispatch_tg_to_tg_preserves_code_without_max_markers():
    # Видимый fallback с обратными кавычками нужен только для MAX-клиента; TG→TG оставляем
    # чистым HTML, чтобы Telegram сам отрисовал inline code/pre.
    s, acc = _disp_store_with_rule("tg", "200", "tg", "300", "both")
    ft = FakeTg()
    d = RuleDispatcher(s, tg_client=ft, tg_bot_id=999)
    text = "inline: код\nblock: Привет"
    run(d.on_tg_message({"chat": {"id": "200", "type": "supergroup"}, "from": {"id": 5},
                         "text": text,
                         "entities": [{"type": "code", "offset": 8, "length": 3},
                                      {"type": "pre", "offset": 19, "length": 6}],
                         "media": []}))
    assert len(ft.sent) == 1
    assert "<code>код</code>" in ft.sent[0]["text"]
    assert "<pre>Привет</pre>" in ft.sent[0]["text"]
    assert "`<code>" not in ft.sent[0]["text"] and "```" not in ft.sent[0]["text"]
    assert ft.sent[0]["parse_mode"] == "HTML"


def test_dispatch_max_to_tg_mention_becomes_bold():
    # MAX→TG: упоминание MAX (max://user/…) Telegram не понимает → жирное имя (имя не теряется).
    s, acc = _disp_store_with_rule("max", "100", "tg", "200", "both")
    ft = FakeTg()
    d = RuleDispatcher(s, tg_client=ft, max_bot_id=999)
    run(d.on_max_message({"chat_id": "100", "sender_id": 5, "chat_type": "channel", "sender": {},
                          "text": "Имя тут",
                          "markup": [{"type": "user_mention", "from": 0, "length": 3, "user_id": 77}],
                          "media": []}))
    assert len(ft.sent) == 1
    assert "<b>Имя</b>" in ft.sent[0]["text"]
    assert "max://" not in ft.sent[0]["text"]
    assert ft.sent[0]["parse_mode"] == "HTML"


def test_dispatch_tg_to_max_mention_becomes_bold():
    # TG→MAX: упоминание Telegram (tg://user?id=…) MAX не понимает → жирное имя (имя не теряется).
    s, acc = _disp_store_with_rule("tg", "200", "max", "100", "both")
    fm = FakeMax()
    d = RuleDispatcher(s, max_client=fm, tg_bot_id=999)
    run(d.on_tg_message({"chat": {"id": "200", "type": "supergroup"}, "from": {"id": 5},
                         "text": "Имя тут",
                         "entities": [{"type": "text_mention", "offset": 0, "length": 3,
                                       "user": {"id": 77}}], "media": []}))
    assert len(fm.sent) == 1
    assert "<b>Имя</b>" in fm.sent[0]["text"]
    assert "tg://" not in fm.sent[0]["text"]
    assert fm.sent[0]["fmt"] == "html"


def test_dispatch_max_to_max_keeps_native_mention():
    # MAX→MAX: «родное» упоминание max://user/… в MAX рабочее — НЕ трогаем (остаётся ссылкой).
    s, acc = _disp_store_with_rule("max", "100", "max", "200", "to")
    fm = FakeMax()
    d = RuleDispatcher(s, max_client=fm)
    run(d.on_max_message({"chat_id": "100", "sender_id": 5, "chat_type": "channel", "sender": {},
                          "text": "Имя тут",
                          "markup": [{"type": "user_mention", "from": 0, "length": 3, "user_id": 77}],
                          "media": []}))
    assert len(fm.sent) == 1
    assert '<a href="max://user/77">Имя</a>' in fm.sent[0]["text"]


def test_dispatch_tg_to_tg_keeps_native_mention():
    # TG→TG: упоминание tg://user?id=… в Telegram рабочее — НЕ трогаем (остаётся ссылкой).
    s, acc = _disp_store_with_rule("tg", "200", "tg", "300", "both")
    ft = FakeTg()
    d = RuleDispatcher(s, tg_client=ft, tg_bot_id=999)
    run(d.on_tg_message({"chat": {"id": "200", "type": "supergroup"}, "from": {"id": 5},
                         "text": "Имя тут",
                         "entities": [{"type": "text_mention", "offset": 0, "length": 3,
                                       "user": {"id": 77}}], "media": []}))
    assert len(ft.sent) == 1
    assert '<a href="tg://user?id=77">Имя</a>' in ft.sent[0]["text"]


def test_max_normalize_extracts_reply_quote():
    # MAX-ответ: тело — своё (не подменяется цитатой), а процитированный оригинал и автор
    # выносятся в поле reply (для встраивания цитаты при пересылке).
    raw = {"body": {"mid": "m1", "text": "мой ответ",
                    "markup": [{"from": 0, "length": 3, "type": "strong"}]},
           "recipient": {"chat_id": -100, "chat_type": "channel"},
           "sender": {"first_name": "Оля"},
           "link": {"type": "reply",
                    "message": {"mid": "m0", "text": "оригинал текст"},
                    "sender": {"first_name": "Иван", "last_name": "П"}}}
    n = max_content.normalize_message(raw, "message_created")
    assert n["text"] == "мой ответ" and n["is_forward"] is False
    assert n["reply"] == {"text": "оригинал текст", "markup": None, "from": "Иван П"}


def test_dispatch_max_to_tg_reply_renders_blockquote():
    # MAX→TG: процитированное сообщение (ответ) встраивается раскрываемой цитатой с автором,
    # а не теряется (раньше уходило только тело ответа).
    s, acc = _disp_store_with_rule("max", "100", "tg", "200", "both")
    ft = FakeTg()
    d = RuleDispatcher(s, tg_client=ft, max_bot_id=999)
    run(d.on_max_message({"chat_id": "100", "sender_id": 5, "chat_type": "channel", "sender": {},
                          "text": "Согласен", "markup": None, "media": [],
                          "reply": {"text": "Исходный вопрос", "markup": None, "from": "Иван"}}))
    assert len(ft.sent) == 1
    t = ft.sent[0]["text"]
    assert "<blockquote expandable><b>Иван</b>\nИсходный вопрос</blockquote>" in t
    assert t.rstrip().endswith("Согласен")
    assert ft.sent[0]["parse_mode"] == "HTML"


def test_dispatch_max_to_tg_reply_preserves_quote_formatting():
    # форматирование процитированного текста (markup MAX) сохраняется внутри цитаты
    s, acc = _disp_store_with_rule("max", "100", "tg", "200", "both")
    ft = FakeTg()
    d = RuleDispatcher(s, tg_client=ft, max_bot_id=999)
    run(d.on_max_message({"chat_id": "100", "sender_id": 5, "chat_type": "channel", "sender": {},
                          "text": "ответ", "media": [],
                          "reply": {"text": "жирный кусок", "from": None,
                                    "markup": [{"from": 0, "length": 6, "type": "strong"}]}}))
    assert "<blockquote expandable><b>жирный</b> кусок</blockquote>" in ft.sent[0]["text"]


def test_dispatch_max_to_tg_reply_no_quote_text_skips_blockquote():
    # если у процитированного нет текста (например, только медиа) — блок цитаты не добавляем,
    # и без иного форматирования сообщение остаётся чистым plain.
    s, acc = _disp_store_with_rule("max", "100", "tg", "200", "both")
    ft = FakeTg()
    d = RuleDispatcher(s, tg_client=ft, max_bot_id=999)
    run(d.on_max_message({"chat_id": "100", "sender_id": 5, "chat_type": "channel", "sender": {},
                          "text": "просто текст", "markup": None, "media": [],
                          "reply": {"text": "", "markup": None, "from": "Иван"}}))
    assert "blockquote" not in ft.sent[0]["text"]
    assert ft.sent[0]["text"] == "просто текст" and ft.sent[0]["parse_mode"] is None


def test_dispatch_tg_to_max_reply_renders_quote():
    # TG→MAX: reply_to_message после нормализации не должен теряться — цитата уходит
    # перед телом ответа, с форматированием исходного текста.
    s, acc = _disp_store_with_rule("tg", "200", "max", "100", "both")
    fm = FakeMax()
    d = RuleDispatcher(s, max_client=fm, tg_bot_id=999)
    run(d.on_tg_message({"chat": {"id": "200", "type": "channel", "title": "Hellow"},
                         "sender_chat": {"title": "Hellow"}, "from": None,
                         "text": "Привет", "media": [],
                         "reply": {"text": "исходный текст", "from": "Hellow",
                                   "entities": [{"type": "bold", "offset": 0, "length": 8}]}}))
    assert len(fm.sent) == 1
    txt = fm.sent[0]["text"]
    assert "<blockquote><b>Hellow</b>\n<b>исходный</b> текст</blockquote>" in txt
    assert txt.rstrip().endswith("Привет")
    assert fm.sent[0]["fmt"] == "html"


def test_dispatch_tg_to_max_uploads_media():
    # TG→MAX: медиа скачивается из Telegram и ЗАГРУЖАЕТСЯ в MAX (attachments с token),
    # а не превращается в ссылку. Трафик учитывается.
    s, acc = _disp_store_with_rule("tg", "200", "max", "100", "both")

    class FakeTgDl:
        def __init__(self): self.max_bytes_seen = []
        async def get_file(self, fid): return {"file_path": f"p/{fid}"}
        async def download_file_bytes(self, fp, *, max_bytes=None):
            self.max_bytes_seen.append(max_bytes); return (b"JPEGBYTES", "image/jpeg")

    class FakeMaxUp:
        def __init__(self): self.sent = []; self.uploaded = []
        async def upload_media(self, up_type, data, *, filename=None, content_type=None):
            self.uploaded.append((up_type, len(data))); return f"TOKEN_{up_type}"
        async def send_message(self, **kw): self.sent.append(kw)

    fm, ft = FakeMaxUp(), FakeTgDl()
    d = RuleDispatcher(s, max_client=fm, tg_client=ft, tg_bot_id=999)
    run(d.on_tg_message({"chat": {"id": "200", "type": "supergroup"}, "from": {"id": 5},
                         "text": "cap", "media": [{"type": "photo", "file_id": "FID", "file_size": 5000}]}))
    assert fm.uploaded == [("image", 9)]                       # тип image, скачано 9 байт
    assert ft.max_bytes_seen == [config.TG_UPLOAD_MAX_BYTES]    # потолок RAM проброшен (симметрия с MAX→TG)
    assert len(fm.sent) == 1
    assert fm.sent[0]["attachments"] == [{"type": "image", "payload": {"token": "TOKEN_image"}}]
    assert LINK_NOTE not in (fm.sent[0].get("text") or "")     # это медиа, не ссылка
    assert s.traffic(acc)["used_bytes"] == len(b"JPEGBYTES")    # трафик по фактически перенесённым байтам


def test_dispatch_tg_to_max_media_preserves_source_hyperlinks():
    # По требованию продукта TG→MAX media-caption сохраняет гиперссылки источника.
    # Preview подавляется MAX query-параметром, а не вырезанием <a href> из текста.
    s, _acc = _disp_store_with_rule("tg", "200", "max", "100", "both")

    class FakeTgDl:
        async def get_file(self, fid): return {"file_path": f"p/{fid}"}
        async def download_file_bytes(self, fp, *, max_bytes=None):
            return b"JPEGBYTES", "image/jpeg"

    class FakeMaxUp:
        def __init__(self): self.sent = []; self.edits = []
        async def upload_media(self, up_type, data, *, filename=None, content_type=None):
            return f"TOKEN_{up_type}"
        async def send_message(self, **kw):
            self.sent.append(kw)
            return {"message": {
                "body": {"mid": "mid.copy", "attachments": [{"type": "share"}]},
                "recipient": {"chat_id": "100"}}}
        async def edit_message(self, message_id, *, text=None, attachments=None,
                               fmt=None, notify=None):
            self.edits.append({"message_id": message_id, "text": text,
                               "attachments": attachments, "fmt": fmt})

    fm, ft = FakeMaxUp(), FakeTgDl()
    d = RuleDispatcher(s, max_client=fm, tg_client=ft, tg_bot_id=999)
    run(d.on_tg_message({
        "chat": {"id": "200", "type": "supergroup"},
        "from": {"id": 5},
        "text": "Смотрите видео",
        "entities": [{"type": "text_link", "offset": 9, "length": 5,
                      "url": "https://vkvideo.ru/video-1_2"}],
        "media": [{"type": "photo", "file_id": "FID", "file_size": 5000}],
    }))

    assert len(fm.sent) == 1
    assert fm.sent[0]["attachments"] == [{"type": "image", "payload": {"token": "TOKEN_image"}}]
    assert 'Смотрите <a href="https://vkvideo.ru/video-1_2">видео</a>' in fm.sent[0]["text"]
    assert fm.sent[0]["fmt"] == "html"
    assert fm.sent[0]["disable_link_preview"] is True
    assert fm.edits
    assert fm.edits[0]["attachments"] == [{"type": "image", "payload": {"token": "TOKEN_image"}}]
    assert 'Смотрите <a href="https://vkvideo.ru/video-1_2">видео</a>' in fm.edits[0]["text"]
    assert fm.edits[0]["fmt"] == "html"


def test_dispatch_tg_to_max_media_report_link_stays_html_link(monkeypatch):
    # MAX должен получать «Пожаловаться» так же, как Telegram: HTML-ссылкой в footer-е.
    monkeypatch.setattr(config, "MODERATION_REPORTS_ENABLED", True)
    s, _acc = _disp_store_with_rule("tg", "200", "max", "100", "both")

    class FakeTgDl:
        async def get_file(self, fid): return {"file_path": f"p/{fid}"}
        async def download_file_bytes(self, fp, *, max_bytes=None):
            return b"JPEGBYTES", "image/jpeg"

    class FakeMaxUp:
        def __init__(self): self.sent = []; self.edits = []
        async def upload_media(self, up_type, data, *, filename=None, content_type=None):
            return f"TOKEN_{up_type}"
        async def send_message(self, **kw):
            self.sent.append(kw)
            return {"message": {"body": {"mid": "mid.copy"}, "recipient": {"chat_id": "100"}}}
        async def edit_message(self, message_id, *, text=None, attachments=None,
                               fmt=None, notify=None):
            self.edits.append({"message_id": message_id, "text": text,
                               "attachments": attachments, "fmt": fmt})

    fm, ft = FakeMaxUp(), FakeTgDl()
    d = RuleDispatcher(s, max_client=fm, tg_client=ft, tg_bot_id=999)
    run(d.on_tg_message({
        "message_id": 10,
        "chat": {"id": "200", "type": "supergroup"},
        "from": {"id": 5, "username": "olig"},
        "text": "Смотрите видео",
        "entities": [{"type": "text_link", "offset": 9, "length": 5,
                      "url": "https://vkvideo.ru/video-1_2"}],
        "media": [{"type": "photo", "file_id": "FID", "file_size": 5000}],
    }))

    attachments = fm.sent[0]["attachments"]
    assert attachments == [{"type": "image", "payload": {"token": "TOKEN_image"}}]
    sent_text = fm.sent[0]["text"]
    assert 'Смотрите <a href="https://vkvideo.ru/video-1_2">видео</a>' in sent_text
    assert ">Пожаловаться</a>" in sent_text
    assert "startapp=" in sent_text
    old_report_url = sent_text.split('">Пожаловаться</a>')[0].rsplit('<a href="', 1)[1]
    assert fm.edits
    edited_text = fm.edits[0]["text"]
    new_report_url = edited_text.split('">Пожаловаться</a>')[0].rsplit('<a href="', 1)[1]
    assert new_report_url != old_report_url
    assert fm.edits[0]["attachments"] == [{"type": "image", "payload": {"token": "TOKEN_image"}}]
    assert fm.edits[0]["fmt"] == "html"


def test_dispatch_tg_album_to_max_splits_multiple_files():
    # MAX отвергает несколько file-вложений в одном сообщении (400/proto.payload). Telegram
    # альбом из документов отправляем по одному, а текст/подпись — после файлов.
    s, acc = _disp_store_with_rule("tg", "200", "max", "100", "both")
    blobs = {"F1": b"PDFDATA", "F2": b"JPG_AS_DOC"}

    class FakeTgDl:
        async def get_file(self, fid): return {"file_path": fid}
        async def download_file_bytes(self, fp, *, max_bytes=None):
            return blobs[fp], "application/octet-stream"

    class FakeMaxUp:
        def __init__(self): self.sent = []; self.uploaded = []
        async def upload_media(self, up_type, data, *, filename=None, content_type=None):
            self.uploaded.append((up_type, filename, content_type, len(data)))
            return f"TOKEN_{filename}"
        async def send_message(self, **kw):
            files = [a for a in (kw.get("attachments") or []) if a.get("type") == "file"]
            if len(files) > 1:
                raise _MaxErrLike(400, "proto.payload")
            self.sent.append(kw)

    fm, ft = FakeMaxUp(), FakeTgDl()
    d = RuleDispatcher(s, max_client=fm, tg_client=ft, tg_bot_id=999)
    run(d.on_tg_album({"chat": {"id": "200", "type": "channel", "title": "Hellow"},
                       "message_ids": [23, 24],
                       "caption": "album cap",
                       "media": [
                           {"type": "document", "file_id": "F1", "file_name": "Портфолио.pdf",
                            "mime_type": "application/pdf", "file_size": len(blobs["F1"])},
                           {"type": "document", "file_id": "F2", "file_name": "13.jpg",
                            "mime_type": "image/jpeg", "file_size": len(blobs["F2"])},
                       ]}))
    assert fm.uploaded == [
        ("file", "Портфолио.pdf", "application/pdf", len(blobs["F1"])),
        ("file", "13.jpg", "image/jpeg", len(blobs["F2"])),
    ]
    assert len(fm.sent) == 3
    assert fm.sent[0]["text"] is None
    assert fm.sent[1]["text"] is None
    assert fm.sent[2]["text"] == "album cap"
    assert fm.sent[0]["attachments"] == [{"type": "file", "payload": {"token": "TOKEN_Портфолио.pdf"}}]
    assert fm.sent[1]["attachments"] == [{"type": "file", "payload": {"token": "TOKEN_13.jpg"}}]
    assert fm.sent[2].get("attachments") is None
    assert LINK_NOTE not in "".join(x.get("text") or "" for x in fm.sent)
    assert s.traffic(acc)["used_bytes"] == len(blobs["F1"]) + len(blobs["F2"])


def test_dispatch_tg_album_to_max_splits_file_mixed_with_image():
    # Если среди MAX-вложений есть file, он должен уйти отдельным сообщением: иначе смешанные
    # Telegram-альбомы рискуют получить тот же 400/proto.payload на стороне MAX.
    s, acc = _disp_store_with_rule("tg", "200", "max", "100", "both")
    blobs = {"F1": b"PDF", "P1": b"IMG"}

    class FakeTgDl:
        async def get_file(self, fid): return {"file_path": fid}
        async def download_file_bytes(self, fp, *, max_bytes=None):
            return blobs[fp], "application/octet-stream"

    class FakeMaxUp:
        def __init__(self): self.sent = []; self.uploaded = []
        async def upload_media(self, up_type, data, *, filename=None, content_type=None):
            self.uploaded.append((up_type, filename, content_type, len(data)))
            return f"TOKEN_{up_type}_{filename}"
        async def send_message(self, **kw):
            atts = kw.get("attachments") or []
            if any(a.get("type") == "file" for a in atts) and len(atts) > 1:
                raise _MaxErrLike(400, "proto.payload")
            self.sent.append(kw)

    fm, ft = FakeMaxUp(), FakeTgDl()
    d = RuleDispatcher(s, max_client=fm, tg_client=ft, tg_bot_id=999)
    run(d.on_tg_album({"chat": {"id": "200", "type": "channel", "title": "Hellow"},
                       "message_ids": [25, 26],
                       "caption": "mixed cap",
                       "media": [
                           {"type": "document", "file_id": "F1", "file_name": "report.pdf",
                            "mime_type": "application/pdf", "file_size": len(blobs["F1"])},
                           {"type": "photo", "file_id": "P1", "file_size": len(blobs["P1"])},
                       ]}))
    assert fm.uploaded == [
        ("file", "report.pdf", "application/pdf", len(blobs["F1"])),
        ("image", "sticker.jpg", "image/jpeg", len(blobs["P1"])),
    ]
    assert len(fm.sent) == 3
    assert fm.sent[0]["text"] is None
    assert fm.sent[1]["text"] is None
    assert fm.sent[2]["text"] == "mixed cap"
    assert fm.sent[0]["attachments"] == [{"type": "file", "payload": {"token": "TOKEN_file_report.pdf"}}]
    assert fm.sent[1]["attachments"] == [{"type": "image", "payload": {"token": "TOKEN_image_sticker.jpg"}}]
    assert fm.sent[2].get("attachments") is None
    assert s.traffic(acc)["used_bytes"] == len(blobs["F1"]) + len(blobs["P1"])


def test_dispatch_tg_album_to_max_split_records_each_sent_mid():
    # Split-файлы должны пройти через on_sent по каждому POST /messages, иначе двустороннее
    # правило может снова увидеть собственный MAX-пост и запустить петлю.
    s, acc = _disp_store_with_rule("tg", "200", "max", "100", "both")
    blobs = {"F1": b"A", "F2": b"BB"}

    class FakeTgDl:
        async def get_file(self, fid): return {"file_path": fid}
        async def download_file_bytes(self, fp, *, max_bytes=None):
            return blobs[fp], "application/octet-stream"

    class HookedMax:
        def __init__(self): self.sent = []; self.on_sent = None; self.seq = 0
        async def upload_media(self, up_type, data, *, filename=None, content_type=None):
            return f"TOKEN_{filename}"
        async def send_message(self, **kw):
            self.seq += 1
            self.sent.append(kw)
            res = {"message": {"recipient": {"chat_id": kw.get("chat_id")},
                               "body": {"mid": f"mid.split.{self.seq}"}}}
            if self.on_sent:
                self.on_sent(res)
            return res

    fm, ft, si = HookedMax(), FakeTgDl(), _fresh_sent_index()
    d = RuleDispatcher(s, max_client=fm, tg_client=ft, tg_bot_id=999, sent_index=si)
    fm.on_sent = d.note_max_sent
    run(d.on_tg_album({"chat": {"id": "200", "type": "channel", "title": "Hellow"},
                       "message_ids": [40, 41],
                       "media": [
                           {"type": "document", "file_id": "F1", "file_name": "a.pdf",
                            "mime_type": "application/pdf", "file_size": len(blobs["F1"])},
                           {"type": "document", "file_id": "F2", "file_name": "b.pdf",
                            "mime_type": "application/pdf", "file_size": len(blobs["F2"])},
                       ]}))
    assert len(fm.sent) == 2
    assert si.contains("max", "100", "mid.split.1")
    assert si.contains("max", "100", "mid.split.2")


def test_dispatch_tg_album_to_max_split_counts_only_delivered_files():
    # Если один split-элемент не отправился и деградировал в ссылку, трафик списываем только за
    # реально доставленные вложения, а пользователю всё равно оставляем ссылку на полный пост.
    s, acc = _disp_store_with_rule("tg", "-1001234567890", "max", "100", "both")
    blobs = {"GOOD": b"GOODDATA", "BAD": b"BADDATA"}

    class FakeTgDl:
        async def get_file(self, fid): return {"file_path": fid}
        async def download_file_bytes(self, fp, *, max_bytes=None):
            return blobs[fp], "application/octet-stream"

    class PartlyFailingMax:
        def __init__(self): self.sent = []; self.att_attempts = []
        async def upload_media(self, up_type, data, *, filename=None, content_type=None):
            return f"TOKEN_{filename}"
        async def send_message(self, **kw):
            atts = kw.get("attachments") or []
            if atts:
                token = ((atts[0].get("payload") or {}).get("token"))
                self.att_attempts.append(token)
                if token == "TOKEN_bad.pdf":
                    raise _MaxErrLike(403, "file.rejected")
            self.sent.append(kw)

    fm, ft = PartlyFailingMax(), FakeTgDl()
    d = RuleDispatcher(s, max_client=fm, tg_client=ft, tg_bot_id=999)
    run(d.on_tg_album({"chat": {"id": -1001234567890, "type": "channel", "title": "Hellow"},
                       "message_ids": [50, 51],
                       "media": [
                           {"type": "document", "file_id": "GOOD", "file_name": "good.pdf",
                            "mime_type": "application/pdf", "file_size": len(blobs["GOOD"])},
                           {"type": "document", "file_id": "BAD", "file_name": "bad.pdf",
                            "mime_type": "application/pdf", "file_size": len(blobs["BAD"])},
                       ]}))
    assert fm.att_attempts == ["TOKEN_good.pdf", "TOKEN_bad.pdf"]
    assert len(fm.sent) == 2
    assert fm.sent[0]["attachments"] == [{"type": "file", "payload": {"token": "TOKEN_good.pdf"}}]
    assert fm.sent[1].get("attachments") is None
    assert (f'<blockquote>{LINK_NOTE} в источнике '
            '"<a href="https://t.me/c/1234567890/50">-1001234567890</a>" '
            'в мессенджере telegram.</blockquote>') in fm.sent[1]["text"]
    assert s.traffic(acc)["used_bytes"] == len(blobs["GOOD"])


def test_dispatch_tg_split_album_continuation_has_single_footer_in_tg():
    # Telegram режет >10 фото на соседние media_group_id. Footer должен появиться один раз:
    # не на полном chunk-е из 10 фото, а на последнем неполном chunk-е.
    s, _acc = _disp_store_with_rule("tg", "200", "tg", "300", "to")
    run(s.update_rule(s.rules_of(_acc)[0]["id"], {"sign_ab": True}))
    ft = FakeTg()
    d = RuleDispatcher(s, tg_client=ft, tg_bot_id=999)

    def chunk(ids):
        return {
            "chat": {"id": "200", "type": "supergroup", "title": "Src"},
            "date": 12345,
            "message_ids": ids,
            "caption": None,
            "entities": [],
            "media": [{"type": "photo", "file_id": f"F{i}"} for i in ids],
            "parts": [
                {"message_id": ids[0], "chat": {"id": "200", "type": "supergroup"},
                 "from": {"id": 42, "first_name": "Иван", "username": "ivan"}},
            ],
        }

    run(d.on_tg_album(chunk(list(range(1, 11)))))
    assert ft.sent == []
    run(d.on_tg_album(chunk([11, 12])))

    assert len(ft.groups) == 2
    assert [len(g["media"]) for g in ft.groups] == [10, 2]
    assert all("caption" not in item for g in ft.groups for item in g["media"])
    assert len(ft.sent) == 1
    assert '<a href="https://t.me/ivan">Иван</a>' in ft.sent[0]["text"]


def test_tg_split_album_continuation_maps_to_first_source_mid():
    # Continuation должен попадать в message_map под первый source mid: жалоба с единственной
    # ссылки тогда сможет скрыть все отправленные части.
    class DummyStore:
        def table(self, _name): return {}

    d = RuleDispatcher(DummyStore(), tg_bot_id=999)
    sender_part = {"from": {"id": 42, "first_name": "Иван"}}

    def chunk(ids):
        return {
            "chat": {"id": "200", "type": "supergroup"},
            "date": 12345,
            "message_ids": ids,
            "caption": None,
            "entities": [],
            "media": [{"type": "photo"} for _ in ids],
        }

    assert d._tg_album_continuation_root(chunk(list(range(1, 11))), sender_part) is None
    assert d._tg_album_continuation_root(chunk(list(range(11, 21))), sender_part) == 1
    assert d._tg_album_continuation_root(chunk([21, 22]), sender_part) == 1


def test_report_link_for_tg_album_continuation_uses_root_source_mid(monkeypatch):
    # Ссылка жалобы на последнем chunk-е должна указывать на root source mid, потому что
    # message_map складывает туда все отправленные части большого альбома.
    import control.integration as integration_mod

    monkeypatch.setattr(config, "MODERATION_REPORTS_ENABLED", True)
    seen = {}

    def fake_make_report_token(source_messenger, chat_id, source_mid, rule_id, **kw):
        seen["args"] = (source_messenger, chat_id, source_mid, rule_id, kw)
        return "tok"

    monkeypatch.setattr(integration_mod, "make_report_token", fake_make_report_token)
    monkeypatch.setattr(integration_mod, "report_deeplink",
                        lambda messenger, token: f"{messenger}:{token}")

    class DummyStore:
        def table(self, _name): return {}

    d = RuleDispatcher(DummyStore(), tg_bot_id=999)
    link = d._report_link(
        "tg",
        {"chat_id": "200", "message_id": 11, "_map_source_message_id": 1,
         "media": [{"type": "photo"}]},
        {"messenger": "max", "rule_id": "rule1"},
    )

    assert link == "max:tok"
    assert seen["args"][:4] == ("tg", "200", 1, "rule1")


def test_dispatch_tg_split_album_continuation_has_single_footer_in_max():
    # Та же защита для TG→MAX: полный chunk получает только изображения, footer остаётся один —
    # на последнем неполном chunk-е.
    s, acc = _disp_store_with_rule("tg", "200", "max", "100", "to")
    run(s.update_rule(s.rules_of(acc)[0]["id"], {"sign_ab": True}))

    class FakeTgDl:
        async def get_file(self, fid): return {"file_path": fid}
        async def download_file_bytes(self, fp, *, max_bytes=None):
            return f"IMG-{fp}".encode("ascii"), "image/jpeg"

    class FakeMaxUp:
        def __init__(self): self.sent = []; self.uploaded = []
        async def upload_media(self, up_type, data, *, filename=None, content_type=None):
            token = f"TOK_{len(self.uploaded)}"
            self.uploaded.append((up_type, token, len(data)))
            return token
        async def send_message(self, **kw): self.sent.append(kw)

    fm, ft = FakeMaxUp(), FakeTgDl()
    d = RuleDispatcher(s, max_client=fm, tg_client=ft, tg_bot_id=999)

    def chunk(ids):
        return {
            "chat": {"id": "200", "type": "supergroup", "title": "Src"},
            "date": 12345,
            "message_ids": ids,
            "caption": None,
            "entities": [],
            "media": [{"type": "photo", "file_id": f"F{i}", "file_size": 100} for i in ids],
            "parts": [
                {"message_id": ids[0], "chat": {"id": "200", "type": "supergroup"},
                 "from": {"id": 42, "first_name": "Иван", "username": "ivan"}},
            ],
        }

    run(d.on_tg_album(chunk(list(range(1, 11)))))
    run(d.on_tg_album(chunk([11, 12])))

    assert len(fm.sent) == 2
    assert fm.sent[0]["text"] is None
    assert "Автор" in fm.sent[1]["text"]
    assert [len(x["attachments"]) for x in fm.sent] == [10, 2]
    assert s.traffic(acc)["used_bytes"] == sum(size for _typ, _tok, size in fm.uploaded)


def test_dispatch_tg_to_max_static_sticker_uploads_as_image():
    # Статичный стикер (WebP) грузится в MAX как image (отрисуется картинкой) с именем
    # sticker.webp — а не безликим file.bin (раньше любой стикер шёл как file без имени).
    s, acc = _disp_store_with_rule("tg", "200", "max", "100", "both")

    class FakeTgDl:
        def __init__(self): self.fetched = []
        async def get_file(self, fid): self.fetched.append(fid); return {"file_path": f"p/{fid}"}
        async def download_file_bytes(self, fp, *, max_bytes=None):
            return (b"RIFF\x00\x00\x00\x00WEBPxxxx", "image/webp")

    class FakeMaxUp:
        def __init__(self): self.sent = []; self.uploaded = []
        async def upload_media(self, up_type, data, *, filename=None, content_type=None):
            self.uploaded.append((up_type, filename, content_type)); return "TOK"
        async def send_message(self, **kw): self.sent.append(kw)

    fm, ft = FakeMaxUp(), FakeTgDl()
    d = RuleDispatcher(s, max_client=fm, tg_client=ft, tg_bot_id=999)
    run(d.on_tg_message({"chat": {"id": "200", "type": "supergroup"}, "from": {"id": 5}, "text": "",
                         "media": [{"type": "sticker", "file_id": "STK", "is_animated": False,
                                    "is_video": False, "thumbnail_file_id": "THUMB", "file_size": 30000}]}))
    assert ft.fetched == ["STK"]                                 # качаем сам стикер (webp), не превью
    assert fm.uploaded == [("image", "sticker.webp", "image/webp")]
    assert fm.sent[0]["attachments"] == [{"type": "image", "payload": {"token": "TOK"}}]
    assert s.traffic(acc)["used_bytes"] == len(b"RIFF\x00\x00\x00\x00WEBPxxxx")   # фактические байты webp


def test_dispatch_tg_to_max_animated_sticker_converts_to_video():
    # Анимированный (TGS/Lottie) стикер конвертируется в mp4 и грузится как ВИДЕО MAX (анимация).
    # Конвертер замокан (реальный рендер требует ffmpeg/rlottie — проверяется вживую отдельно).
    from unittest.mock import AsyncMock, patch
    s, acc = _disp_store_with_rule("tg", "200", "max", "100", "both")

    class FakeTgDl:
        def __init__(self): self.fetched = []
        async def get_file(self, fid): self.fetched.append(fid); return {"file_path": f"p/{fid}"}
        async def download_file_bytes(self, fp, *, max_bytes=None):
            return (b"\x1f\x8b\x08TGSGZIP", "application/octet-stream")

    class FakeMaxUp:
        def __init__(self): self.sent = []; self.uploaded = []
        async def upload_media(self, up_type, data, *, filename=None, content_type=None):
            self.uploaded.append((up_type, filename, content_type, len(data))); return f"TOK_{up_type}"
        async def send_message(self, **kw): self.sent.append(kw)

    fm, ft = FakeMaxUp(), FakeTgDl()
    d = RuleDispatcher(s, max_client=fm, tg_client=ft, tg_bot_id=999)
    mp4 = b"\x00\x00\x00\x18ftypisomMP4PAYLOAD"
    with patch("control.integration.stickers.sticker_to_mp4", new=AsyncMock(return_value=mp4)):
        run(d.on_tg_message({"chat": {"id": "200", "type": "supergroup"}, "from": {"id": 5}, "text": "",
                             "media": [{"type": "sticker", "file_id": "STK", "is_animated": True,
                                        "is_video": False, "thumbnail_file_id": "THUMB", "file_size": 50000}]}))
    assert ft.fetched == ["STK"]                                  # качаем сам стикер (tgs), не превью
    assert fm.uploaded == [("video", "sticker.mp4", "video/mp4", len(mp4))]
    assert fm.sent[0]["attachments"] == [{"type": "video", "payload": {"token": "TOK_video"}}]
    assert s.traffic(acc)["used_bytes"] == len(mp4)              # трафик — по байтам mp4


def test_dispatch_tg_to_max_animated_sticker_falls_back_to_thumbnail_when_conversion_fails():
    # Конвертация в mp4 не удалась (нет тулинга/битый стикер) → грузим статичное ПРЕВЬЮ как image.
    from unittest.mock import AsyncMock, patch
    s, acc = _disp_store_with_rule("tg", "200", "max", "100", "both")

    class FakeTgDl:
        def __init__(self): self.fetched = []
        async def get_file(self, fid): self.fetched.append(fid); return {"file_path": f"p/{fid}"}
        async def download_file_bytes(self, fp, *, max_bytes=None):
            return (b"RIFF\x00\x00\x00\x00WEBPyyyy", "application/octet-stream")

    class FakeMaxUp:
        def __init__(self): self.sent = []; self.uploaded = []
        async def upload_media(self, up_type, data, *, filename=None, content_type=None):
            self.uploaded.append((up_type, filename, content_type)); return "TOK"
        async def send_message(self, **kw): self.sent.append(kw)

    fm, ft = FakeMaxUp(), FakeTgDl()
    d = RuleDispatcher(s, max_client=fm, tg_client=ft, tg_bot_id=999)
    with patch("control.integration.stickers.sticker_to_mp4", new=AsyncMock(return_value=None)):
        run(d.on_tg_message({"chat": {"id": "200", "type": "supergroup"}, "from": {"id": 5}, "text": "",
                             "media": [{"type": "sticker", "file_id": "STK", "is_animated": True,
                                        "is_video": False, "thumbnail_file_id": "THUMB", "file_size": 50000}]}))
    assert ft.fetched == ["STK", "THUMB"]                        # попытка сам стикер → затем превью
    assert fm.uploaded == [("image", "sticker.webp", "image/webp")]  # превью как image (webp по сигнатуре)
    assert fm.sent[0]["attachments"] == [{"type": "image", "payload": {"token": "TOK"}}]


def test_dispatch_tg_to_max_upload_fail_appends_full_source_note():
    # Если загрузка медиа в MAX не удалась (token=None) → текст + новая подсказка о полном сообщении.
    s, acc = _disp_store_with_rule("tg", "200", "max", "100", "both")

    class FakeTgDl:
        async def get_file(self, fid): return {"file_path": "p"}
        async def download_file_bytes(self, fp, *, max_bytes=None): return (b"X", "image/jpeg")

    class FakeMaxUp:
        def __init__(self): self.sent = []
        async def upload_media(self, *a, **kw): return None       # загрузка не дала token
        async def send_message(self, **kw): self.sent.append(kw)

    fm, ft = FakeMaxUp(), FakeTgDl()
    d = RuleDispatcher(s, max_client=fm, tg_client=ft, tg_bot_id=999)
    run(d.on_tg_message({"chat": {"id": "200", "type": "supergroup"}, "from": {"id": 5},
                         "text": "cap", "media": [{"type": "photo", "file_id": "FID", "file_size": 5000}]}))
    assert len(fm.sent) == 1 and fm.sent[0]["attachments"] is None
    assert (f'<blockquote>{LINK_NOTE} в источнике "200" '
            'в мессенджере telegram.</blockquote>') in fm.sent[0]["text"]
    assert fm.sent[0]["fmt"] == "html"
    assert s.traffic(acc)["used_bytes"] == 0


class _NotReadyError(RuntimeError):
    """Имитация MaxError с кодом attachment.not.ready (медиа ещё обрабатывается на стороне MAX)."""
    code = "attachment.not.ready"


def test_dispatch_tg_to_max_transient_send_fail_exhausts_budget_no_traffic():
    # Медиа скачано+загружено (token есть), но отправка падает ТРАНЗИЕНТНОЙ ошибкой (5xx) на
    # всех попытках → исчерпывается ограниченный бюджет повторов → деградация до текста, трафик
    # за НЕдоставленное медиа НЕ списывается. (not.ready ждали бы без лимита — здесь именно 5xx.)
    from unittest.mock import patch
    s, acc = _disp_store_with_rule("tg", "200", "max", "100", "both")

    class FakeTgDl:
        async def get_file(self, fid): return {"file_path": "p"}
        async def download_file_bytes(self, fp, *, max_bytes=None): return (b"DATA", "image/jpeg")

    class FakeMaxUp:
        def __init__(self): self.sent = []; self.att_attempts = 0
        async def upload_media(self, *a, **kw): return "TOK"
        async def send_message(self, **kw):
            if kw.get("attachments"):
                self.att_attempts += 1
                raise _MaxErrLike(503, None)   # временная ошибка сервера MAX на всех попытках
            self.sent.append(kw)

    fm, ft = FakeMaxUp(), FakeTgDl()
    d = RuleDispatcher(s, max_client=fm, tg_client=ft, tg_bot_id=999)

    async def _no_sleep(*a, **k): return None
    with patch("control.integration.asyncio.sleep", new=_no_sleep):
        run(d.on_tg_message({"chat": {"id": "200", "type": "supergroup"}, "from": {"id": 5},
                             "text": "cap", "media": [{"type": "photo", "file_id": "FID", "file_size": 5000}]}))
    assert s.traffic(acc)["used_bytes"] == 0     # вложение не ушло → трафик не списан
    assert len(fm.sent) == 1                       # текст всё же доставлен (со ссылкой на оригинал)
    # транзиентный бюджет ограничен: 1 первая попытка + len(delays) повторов.
    assert fm.att_attempts == len(config.MAX_ATTACHMENT_RETRY_DELAYS) + 1


def test_dispatch_tg_to_max_video_retries_until_processed():
    # ГЛАВНЫЙ кейс пользователя: видео из TG доходит до MAX-канала, а не теряется.
    # MAX обрабатывает свежезагруженное видео асинхронно: первые попытки отправки падают
    # attachment.not.ready, затем обработка завершается — отправка проходит с вложением,
    # трафик списывается. Бэкофф из config.MAX_ATTACHMENT_RETRY_DELAYS, паузы замоканы.
    from unittest.mock import patch
    s, acc = _disp_store_with_rule("tg", "200", "max", "100", "both")

    class FakeTgDl:
        async def get_file(self, fid): return {"file_path": "p"}
        async def download_file_bytes(self, fp, *, max_bytes=None): return (b"VIDEOBYTES", "video/mp4")

    class FakeMaxUp:
        def __init__(self): self.sent = []; self.att_attempts = 0
        async def upload_media(self, up_type, data, *, filename=None, content_type=None):
            return f"TOKEN_{up_type}"
        async def send_message(self, **kw):
            if kw.get("attachments"):
                self.att_attempts += 1
                if self.att_attempts <= 2:            # ещё обрабатывается — две неудачи
                    raise _NotReadyError("attachment.not.ready")
            self.sent.append(kw)                      # 3-я попытка проходит (с вложением)

    fm, ft = FakeMaxUp(), FakeTgDl()
    d = RuleDispatcher(s, max_client=fm, tg_client=ft, tg_bot_id=999)

    sleeps = []
    async def _rec_sleep(sec, *a, **k): sleeps.append(sec)
    with patch("control.integration.asyncio.sleep", new=_rec_sleep):
        run(d.on_tg_message({"chat": {"id": "200", "type": "supergroup"}, "from": {"id": 5},
                             "text": "video post", "media": [{"type": "video", "file_id": "V", "file_size": 7000}]}))
    assert fm.att_attempts == 3                                       # 2 «не готово» + 1 успех
    assert len(fm.sent) == 1                                          # ровно одно сообщение
    assert fm.sent[0]["attachments"] == [{"type": "video", "payload": {"token": "TOKEN_video"}}]
    assert LINK_NOTE not in (fm.sent[0].get("text") or "")           # видео доставлено, не ссылка
    assert s.traffic(acc)["used_bytes"] == len(b"VIDEOBYTES")        # трафик за доставленное видео (факт. байты)
    assert sleeps == list(config.MAX_ATTACHMENT_RETRY_DELAYS[:2])    # растущие паузы между повторами


def test_max_attach_retry_delays_parse():
    # Парсер бэкоффа из env: валидные значения, мусор отбрасывается, пусто/битое → дефолт.
    from control.config import _parse_delays
    dflt = (2.0, 4.0, 8.0)
    assert _parse_delays(None, dflt) == dflt
    assert _parse_delays("", dflt) == dflt
    assert _parse_delays("1, 2.5 , 5", dflt) == (1.0, 2.5, 5.0)
    assert _parse_delays("x, -3, 4", dflt) == (4.0,)               # нечисло и отрицательное отброшены
    assert _parse_delays("nope", dflt) == dflt                      # ничего валидного → дефолт


class _MaxErrLike(RuntimeError):
    """Имитация MaxError: несёт .code и .status_code (как реальный max_sync.client.MaxError)."""
    def __init__(self, status_code=None, code=None):
        super().__init__(f"[{status_code}/{code}]")
        self.status_code = status_code
        self.code = code


def test_max_send_transient_classifies_errors():
    # ТРАНЗИЕНТНЫЕ сбои (5xx/сеть/неоднозначный ответ) → ограниченное число повторов;
    # not.ready — НЕ транзиентный (его обрабатывает безлимитная ветка ожидания, не здесь);
    # постоянная 4xx с распознанным кодом → не повторяем (деградация сразу).
    assert _max_send_transient(_MaxErrLike(400, "attachment.not.ready")) is False   # processing, не transient
    assert _max_send_transient(_MaxErrLike(500, None)) is True                       # 5xx сервера
    assert _max_send_transient(_MaxErrLike(503, "service.unavailable")) is True      # 5xx с кодом
    assert _max_send_transient(_MaxErrLike(400, None)) is True                       # 4xx без кода (нераспарсено)
    assert _max_send_transient(RuntimeError("connect timeout")) is True              # сеть/таймаут: нет .status_code
    assert _max_send_transient(_MaxErrLike(403, "chat.forbidden")) is False          # постоянная 4xx
    assert _max_send_transient(_MaxErrLike(404, "chat.not.found")) is False          # постоянная 4xx


def test_dispatch_tg_to_max_video_survives_transient_5xx():
    # Видео НЕ теряется из-за временной 5xx/сетевой ошибки отправки: повторяем по бэкоффу,
    # на следующей попытке проходит. (До фикса retry срабатывал только на точный код
    # attachment.not.ready, а 5xx/сеть/нераспарсенный код шли мимо → видео терялось.)
    from unittest.mock import patch
    s, acc = _disp_store_with_rule("tg", "200", "max", "100", "both")

    class FakeTgDl:
        async def get_file(self, fid): return {"file_path": "p"}
        async def download_file_bytes(self, fp, *, max_bytes=None): return (b"VIDEOBYTES", "video/mp4")

    class FakeMaxUp:
        def __init__(self): self.sent = []; self.att_attempts = 0
        async def upload_media(self, up_type, data, *, filename=None, content_type=None):
            return f"TOKEN_{up_type}"
        async def send_message(self, **kw):
            if kw.get("attachments"):
                self.att_attempts += 1
                if self.att_attempts == 1:
                    raise _MaxErrLike(502, None)     # временная ошибка шлюза MAX (без кода)
            self.sent.append(kw)

    fm, ft = FakeMaxUp(), FakeTgDl()
    d = RuleDispatcher(s, max_client=fm, tg_client=ft, tg_bot_id=999)
    async def _no_sleep(*a, **k): return None
    with patch("control.integration.asyncio.sleep", new=_no_sleep):
        run(d.on_tg_message({"chat": {"id": "200", "type": "supergroup"}, "from": {"id": 5},
                             "text": "v", "media": [{"type": "video", "file_id": "V", "file_size": 4096}]}))
    assert fm.att_attempts == 2                                         # 1 сбой 5xx + 1 успех
    assert len(fm.sent) == 1
    assert fm.sent[0]["attachments"] == [{"type": "video", "payload": {"token": "TOKEN_video"}}]
    assert s.traffic(acc)["used_bytes"] == len(b"VIDEOBYTES")           # видео доставлено → трафик учтён (факт. байты)


def test_dispatch_tg_to_max_permanent_4xx_degrades_fast():
    # Постоянная 4xx с распознанным кодом (например, бот исключён из канала) НЕ ждёт весь
    # бюджет: одна попытка → деградация (без бессмысленной блокировки пайплайна на ~минуту).
    from unittest.mock import patch
    s, acc = _disp_store_with_rule("tg", "200", "max", "100", "both")

    class FakeTgDl:
        async def get_file(self, fid): return {"file_path": "p"}
        async def download_file_bytes(self, fp, *, max_bytes=None): return (b"DATA", "image/jpeg")

    class FakeMaxUp:
        def __init__(self): self.sent = []; self.att_attempts = 0
        async def upload_media(self, *a, **kw): return "TOK"
        async def send_message(self, **kw):
            if kw.get("attachments"):
                self.att_attempts += 1
                raise _MaxErrLike(403, "chat.forbidden")   # постоянная ошибка
            self.sent.append(kw)

    fm, ft = FakeMaxUp(), FakeTgDl()
    d = RuleDispatcher(s, max_client=fm, tg_client=ft, tg_bot_id=999)
    sleeps = []
    async def _rec_sleep(sec, *a, **k): sleeps.append(sec)
    with patch("control.integration.asyncio.sleep", new=_rec_sleep):
        run(d.on_tg_message({"chat": {"id": "200", "type": "supergroup"}, "from": {"id": 5},
                             "text": "x", "media": [{"type": "photo", "file_id": "FID", "file_size": 500}]}))
    assert fm.att_attempts == 1            # без ретраев — постоянная ошибка распознана
    assert sleeps == []                    # ни одной паузы (бюджет не тратится впустую)
    assert len(fm.sent) == 1               # деградировали до текста
    assert s.traffic(acc)["used_bytes"] == 0


def test_dispatch_tg_to_max_video_waits_beyond_budget():
    # Ключ требования заказчика: ожидание обработки БЕЗ ограничения по времени. MAX отвечает
    # attachment.not.ready МНОГО раз (больше длины списка пауз) — мы НЕ сдаёмся на «бюджете»,
    # ждём дальше и в итоге доставляем видео. Завершает цикл только успех.
    from unittest.mock import patch
    s, acc = _disp_store_with_rule("tg", "200", "max", "100", "both")
    n_delays = len(config.MAX_ATTACHMENT_RETRY_DELAYS)
    fails = n_delays + 3                                   # заведомо больше «бюджета»

    class FakeTgDl:
        async def get_file(self, fid): return {"file_path": "p"}
        async def download_file_bytes(self, fp, *, max_bytes=None): return (b"VID", "video/mp4")

    class FakeMaxUp:
        def __init__(self): self.sent = []; self.att_attempts = 0
        async def upload_media(self, up_type, data, *, filename=None, content_type=None):
            return f"TOKEN_{up_type}"
        async def send_message(self, **kw):
            if kw.get("attachments"):
                self.att_attempts += 1
                if self.att_attempts <= fails:
                    raise _NotReadyError("attachment.not.ready")   # ещё обрабатывается
            self.sent.append(kw)

    fm, ft = FakeMaxUp(), FakeTgDl()
    d = RuleDispatcher(s, max_client=fm, tg_client=ft, tg_bot_id=999)
    sleeps = []
    async def _rec_sleep(sec, *a, **k): sleeps.append(sec)
    with patch("control.integration.asyncio.sleep", new=_rec_sleep):
        run(d.on_tg_message({"chat": {"id": "200", "type": "supergroup"}, "from": {"id": 5},
                             "text": "v", "media": [{"type": "video", "file_id": "V", "file_size": 8000}]}))
    assert fm.att_attempts == fails + 1                   # ждали ВСЕ разы + финальный успех
    assert len(sleeps) == fails                            # пауза после каждого not.ready
    assert sleeps[-1] == config.MAX_ATTACHMENT_RETRY_DELAYS[-1]   # паузы упёрлись в последнее значение (плато)
    assert len(fm.sent) == 1
    assert fm.sent[0]["attachments"] == [{"type": "video", "payload": {"token": "TOKEN_video"}}]
    assert s.traffic(acc)["used_bytes"] == len(b"VID")    # видео доставлено → трафик учтён (факт. байты)


def test_dispatch_tg_to_max_oversized_media_not_downloaded():
    # Заказчик: медиа больше потолка кросс-мессенджерной передачи «даже не начинает загружаться».
    # file_size > TG_UPLOAD_MAX_BYTES → ни getFile, ни скачивания; в MAX уходит текст + ссылка
    # на оригинал; трафик не списывается.
    s, acc = _disp_store_with_rule("tg", "-1001234567890", "max", "100", "both")

    class FakeTgDl:
        def __init__(self): self.calls = []
        async def get_file(self, fid): self.calls.append(("get_file", fid)); return {"file_path": "p"}
        async def download_file_bytes(self, fp, *, max_bytes=None):
            self.calls.append(("download", fp)); return (b"X", "video/mp4")

    class FakeMaxUp:
        def __init__(self): self.sent = []; self.uploaded = []
        async def upload_media(self, *a, **kw): self.uploaded.append(a); return "TOK"
        async def send_message(self, **kw): self.sent.append(kw)

    fm, ft = FakeMaxUp(), FakeTgDl()
    d = RuleDispatcher(s, max_client=fm, tg_client=ft, tg_bot_id=999)
    big = config.TG_UPLOAD_MAX_BYTES + 1
    run(d.on_tg_message({"chat": {"id": -1001234567890, "type": "supergroup", "title": "Hellow"},
                         "from": {"id": 5},
                         "message_id": 9, "text": "клип",
                         "media": [{"type": "video", "file_id": "V", "file_size": big}]}))
    assert ft.calls == []                  # файл даже не запрашивали и не качали
    assert fm.uploaded == []               # в MAX ничего не грузили
    assert len(fm.sent) == 1 and fm.sent[0]["attachments"] is None
    assert "слишком большие" not in fm.sent[0]["text"]
    assert (f'<blockquote>{LINK_NOTE} в источнике "<a href="https://t.me/c/1234567890/9">'
            'Hellow</a>" в мессенджере telegram.</blockquote>') in fm.sent[0]["text"]
    assert s.traffic(acc)["used_bytes"] == 0


def test_dispatch_tg_to_max_oversized_and_unsupported_combined_note():
    # Из двух файлов один слишком большой, другой — запрещённый формат: пользовательский текст
    # всё равно остаётся единой новой подсказкой о полном сообщении в источнике.
    s, acc = _disp_store_with_rule("tg", "-1001234567890", "max", "100", "both")

    class FakeTgDl:
        async def get_file(self, fid): return {"file_path": f"p/{fid}"}
        async def download_file_bytes(self, fp, *, max_bytes=None): return (b"DATA", "application/x-rar")

    class FakeMaxUp:
        def __init__(self): self.sent = []
        async def upload_media(self, up_type, data, *, filename=None, content_type=None):
            raise RuntimeError("415 File extension is forbidden")   # формат не принят
        async def send_message(self, **kw): self.sent.append(kw)

    fm, ft = FakeMaxUp(), FakeTgDl()
    d = RuleDispatcher(s, max_client=fm, tg_client=ft, tg_bot_id=999)
    big = config.TG_UPLOAD_MAX_BYTES + 1
    run(d.on_tg_message({"chat": {"id": -1001234567890, "type": "supergroup", "title": "Hellow"},
                         "from": {"id": 5},
                         "message_id": 3, "text": "архивы",
                         "media": [{"type": "document", "file_id": "BIG", "file_size": big},
                                   {"type": "document", "file_id": "BAD", "file_size": 10}]}))
    txt = fm.sent[0]["text"]
    assert "превышают лимит размера" not in txt and "формат не поддерживается" not in txt
    assert (f'<blockquote>{LINK_NOTE} в источнике "<a href="https://t.me/c/1234567890/3">'
            'Hellow</a>" в мессенджере telegram.</blockquote>') in txt
    assert s.traffic(acc)["used_bytes"] == 0


def test_declared_size_extraction():
    assert _declared_size({"file_size": 123}) == 123
    assert _declared_size({"raw": {"file_size": 77}}) == 77
    assert _declared_size({}) is None
    assert _declared_size({"file_size": None, "raw": {}}) is None


def test_max_client_content_length_and_timeout_helpers():
    # Пре-флайт по Content-Length и снятый по умолчанию таймаут переноса медиа.
    import httpx
    from max_sync.client import _content_length_over, _parse_media_timeout, _media_timeout, _MEDIA_CONNECT_TIMEOUT
    cap = 2_097_152_000
    assert _content_length_over(httpx.Headers({"content-length": str(cap + 1)}), cap) is True
    assert _content_length_over(httpx.Headers({"content-length": str(cap)}), cap) is False
    assert _content_length_over(httpx.Headers({}), cap) is False                 # нет заголовка → решит поток
    assert _content_length_over(httpx.Headers({"content-length": "abc"}), cap) is False  # мусор
    assert _content_length_over(httpx.Headers({"content-length": str(cap + 1)}), None) is False  # без потолка
    # таймаут переноса: 0/пусто/мусор/None → снят (None); положительное число → возвращается.
    assert _parse_media_timeout(None) is None
    assert _parse_media_timeout("") is None
    assert _parse_media_timeout("0") is None
    assert _parse_media_timeout("-5") is None
    assert _parse_media_timeout("nan_text") is None
    assert _parse_media_timeout("600") == 600.0
    t = _media_timeout()
    # перенос (read/write) без лимита; connect и pool ограничены (очередь, не «время загрузки»).
    assert t.read is None and t.write is None
    assert t.connect == _MEDIA_CONNECT_TIMEOUT and t.pool == _MEDIA_CONNECT_TIMEOUT


def test_dispatch_tg_to_max_partial_delivers_supported_and_notes():
    # Из двух вложений MAX принимает фото и отвергает документ (запрещённое расширение):
    # доставляем фото + строку-ссылку на оригинал; трафик — только за доставленное фото.
    s, acc = _disp_store_with_rule("tg", "-1001234567890", "max", "100", "both")

    class FakeTgDl:
        async def get_file(self, fid): return {"file_path": f"p/{fid}"}
        async def download_file_bytes(self, fp, *, max_bytes=None): return (b"DATA", "image/jpeg")

    class FakeMaxUp:
        def __init__(self): self.sent = []
        async def upload_media(self, up_type, data, *, filename=None, content_type=None):
            if up_type == "file":
                raise RuntimeError("415 File extension is forbidden")
            return f"TOKEN_{up_type}"
        async def send_message(self, **kw): self.sent.append(kw)

    fm, ft = FakeMaxUp(), FakeTgDl()
    d = RuleDispatcher(s, max_client=fm, tg_client=ft, tg_bot_id=999)
    run(d.on_tg_message({"chat": {"id": -1001234567890, "type": "supergroup", "title": "Hellow"},
                         "from": {"id": 5},
                         "message_id": 5, "text": "t",
                         "media": [{"type": "photo", "file_id": "A", "file_size": 100},
                                   {"type": "document", "file_id": "B", "file_size": 9999}]}))
    assert len(fm.sent) == 1
    assert fm.sent[0]["attachments"] == [{"type": "image", "payload": {"token": "TOKEN_image"}}]
    assert (f'<blockquote>{LINK_NOTE} в источнике "<a href="https://t.me/c/1234567890/5">'
            'Hellow</a>" в мессенджере telegram.</blockquote>') in fm.sent[0]["text"]
    assert fm.sent[0]["fmt"] == "html"
    assert s.traffic(acc)["used_bytes"] == len(b"DATA")   # учтено только доставленное фото (факт. байты)


def test_dispatch_subscription_gate_blocks():
    s, acc = _disp_store_with_rule("max", "100", "tg", "200", "both", active=False)
    ft = FakeTg()
    d = RuleDispatcher(s, tg_client=ft)
    run(d.on_max_message({"chat_id": "100", "sender_id": 5, "chat_type": "channel", "sender": {}, "text": "x", "media": []}))
    assert ft.sent == [] and ft.photos == []


def test_dispatch_traffic_exhausted_drops_media():
    s, acc = _disp_store_with_rule("max", "100", "tg", "200", "both")
    run(s.add_traffic(acc, config.TRAFFIC_LIMIT_BYTES))
    ft = FakeTg()
    d = RuleDispatcher(s, tg_client=ft)
    run(d.on_max_message({"chat_id": "100", "sender_id": 5, "chat_type": "channel", "sender": {},
                          "text": "t", "media": [{"type": "image", "url": "https://m/i.jpg", "file_size": 9}]}))
    assert ft.photos == [] and len(ft.sent) == 1
    assert (f'<blockquote>{LINK_NOTE} в источнике "100" '
            'в мессенджере max.</blockquote>') in ft.sent[0]["text"]
    assert ft.sent[0]["parse_mode"] == "HTML"


def test_dispatch_echo_skipped():
    s, acc = _disp_store_with_rule("max", "100", "tg", "200", "both")
    ft = FakeTg()
    d = RuleDispatcher(s, tg_client=ft, max_bot_id=42)
    run(d.on_max_message({"chat_id": "100", "sender_id": 42, "chat_type": "channel", "sender": {}, "text": "echo", "media": []}))
    assert ft.sent == [] and ft.photos == []


def test_dispatch_signature_prefix_for_group():
    s, acc = _disp_store_with_rule("tg", "200", "max", "100", "both")
    # включаем подпись на правиле
    rid = s.rules_of(acc)[0]["id"]
    run(s.update_rule(rid, {"signature": True}))
    fm = FakeMax()
    d = RuleDispatcher(s, max_client=fm, tg_bot_id=999)
    run(d.on_tg_message({"chat": {"id": "200", "type": "supergroup"}, "from": {"id": 5, "first_name": "Пётр"},
                         "text": "сообщение", "media": []}))
    # Подпись внизу: текст, затем имя-ссылка на профиль.
    assert len(fm.sent) == 1
    txt = fm.sent[0]["text"]
    assert txt.startswith("сообщение")
    assert txt.endswith("</a>") or txt.endswith("</b>")
    assert "Пётр" in txt
    assert fm.sent[0]["fmt"] == "html"


def test_dispatch_signature_escapes_name_and_keeps_formatting():
    # Подпись + форматирование источника: имя со спецсимволами экранируется, гиперссылка
    # из источника сохраняется, & экранирован — HTML не ломается.
    s, acc = _disp_store_with_rule("tg", "200", "max", "100", "to")
    run(s.update_rule(s.rules_of(acc)[0]["id"], {"sign_ab": True}))
    fm = FakeMax()
    d = RuleDispatcher(s, max_client=fm, tg_bot_id=999)
    run(d.on_tg_message({"chat": {"id": "200", "type": "supergroup"}, "from": {"id": 5, "first_name": "A<b>"},
                         "text": "a & b",
                         "entities": [{"type": "text_link", "offset": 0, "length": 5, "url": "https://x/?u=1&v=2"}],
                         "media": []}))
    txt = fm.sent[0]["text"]
    assert "A&lt;b&gt;" in txt                             # имя экранировано
    assert "<a href=" in txt and "&amp;" in txt
    assert txt.endswith("</a>") or txt.endswith("</b>")  # подпись внизу
    assert fm.sent[0]["fmt"] == "html"


def test_dispatch_signature_for_tg_channel_uses_channel_name():
    # У поста КАНАЛА нет 'from' — подпись берётся из названия канала (sender_chat.title).
    s, acc = _disp_store_with_rule("tg", "200", "max", "100", "to")
    run(s.update_rule(s.rules_of(acc)[0]["id"], {"sign_ab": True}))
    fm = FakeMax()
    d = RuleDispatcher(s, max_client=fm, tg_bot_id=999)
    run(d.on_tg_message({"chat": {"id": "200", "type": "channel", "title": "Новости"}, "from": None,
                         "sender_chat": {"title": "Новости", "type": "channel"},
                         "text": "пост", "media": []}))
    assert len(fm.sent) == 1
    txt = fm.sent[0]["text"]
    assert txt.startswith("пост")
    assert "<b>Новости</b>" in txt
    assert fm.sent[0]["fmt"] == "html"


def test_dispatch_signature_for_tg_channel_prefers_author_signature():
    # Если у поста есть author_signature (подпись автора канала) — она в приоритете.
    s, acc = _disp_store_with_rule("tg", "200", "max", "100", "to")
    run(s.update_rule(s.rules_of(acc)[0]["id"], {"sign_ab": True}))
    fm = FakeMax()
    d = RuleDispatcher(s, max_client=fm, tg_bot_id=999)
    run(d.on_tg_message({"chat": {"id": "200", "type": "channel", "title": "Новости"}, "from": None,
                         "sender_chat": {"title": "Новости"}, "author_signature": "Редакция",
                         "text": "пост", "media": []}))
    assert "<b>Редакция</b>" in fm.sent[0]["text"]


def test_dispatch_signature_for_max_channel_uses_source_title():
    # У поста MAX-КАНАЛА нет отправителя — подпись = название источника из ownership (provider).
    s, acc = _disp_store_with_rule("max", "100", "tg", "200", "to")
    run(s.update_rule(s.rules_of(acc)[0]["id"], {"sign_ab": True}))
    ft = FakeTg()
    d = RuleDispatcher(s, tg_client=ft, max_bot_id=999)
    d.source_title = lambda m, cid: "Мой канал" if (m == "max" and str(cid) == "100") else None
    run(d.on_max_message({"chat_id": "100", "chat_type": "channel", "sender": {}, "sender_id": None,
                          "text": "пост", "media": []}))
    assert len(ft.sent) == 1
    txt = ft.sent[0]["text"]
    assert txt.startswith("пост")
    assert "<b>Мой канал</b>" in txt
    assert ft.sent[0]["parse_mode"] == "HTML"


def test_dispatch_signature_footer_with_tg_link():
    """Подпись снизу: имя — кликабельная ссылка tg://user?id=… (TG-отправитель без username)."""
    s, acc = _disp_store_with_rule("tg", "200", "max", "100", "to")
    run(s.update_rule(s.rules_of(acc)[0]["id"], {"sign_ab": True}))
    fm = FakeMax()
    d = RuleDispatcher(s, max_client=fm, tg_bot_id=999)
    run(d.on_tg_message({"chat": {"id": "200", "type": "supergroup"},
                         "from": {"id": 42, "first_name": "Иван"},
                         "text": "привет", "media": []}))
    txt = fm.sent[0]["text"]
    assert txt.startswith("привет")
    assert txt.endswith('<b>Иван</b>')
    assert fm.sent[0]["fmt"] == "html"


def test_dispatch_signature_footer_includes_source_title():
    """Подпись снизу: пустая строка и Автор <имя>; источник не выводится."""
    s, acc = _disp_store_with_rule("tg", "200", "max", "100", "to")
    run(s.update_rule(s.rules_of(acc)[0]["id"], {"sign_ab": True}))
    fm = FakeMax()
    d = RuleDispatcher(s, max_client=fm, tg_bot_id=999)
    d.source_title = lambda m, cid: "Группа & тема" if (m == "tg" and str(cid) == "200") else None
    run(d.on_tg_message({"chat": {"id": "200", "type": "supergroup"},
                         "from": {"id": 42, "first_name": "Иван"},
                         "text": "привет", "media": []}))
    txt = fm.sent[0]["text"]
    assert txt.startswith("привет")
    assert "\n\nАвтор <b>Иван</b>" in txt
    assert "-------------------" not in txt
    assert "переслано из" not in txt
    assert fm.sent[0]["fmt"] == "html"


def test_dispatch_signature_footer_has_blank_line_for_max():
    """Подпись в MAX отделена пустой строкой, без строки дефисов."""
    s, acc = _disp_store_with_rule("tg", "200", "max", "100", "to")
    run(s.update_rule(s.rules_of(acc)[0]["id"], {"sign_ab": True}))
    fm = FakeMax()
    d = RuleDispatcher(s, max_client=fm, tg_bot_id=999)
    longest = "x" * 32
    run(d.on_tg_message({"chat": {"id": "200", "type": "supergroup"},
                         "from": {"id": 42, "first_name": "Иван"},
                         "text": f"коротко\n{longest}", "media": []}))
    txt = fm.sent[0]["text"]
    assert "\n\nАвтор <b>Иван</b>" in txt
    assert "-------------------" not in txt
    assert "-" * len(longest) not in txt


def test_dispatch_signature_footer_has_blank_line_for_tg():
    """Та же подпись в Telegram: пустая строка, без строки дефисов."""
    s, acc = _disp_store_with_rule("max", "100", "tg", "200", "to")
    run(s.update_rule(s.rules_of(acc)[0]["id"], {"sign_ab": True}))
    ft = FakeTg()
    d = RuleDispatcher(s, tg_client=ft, max_bot_id=999)
    longest = "y" * 28
    run(d.on_max_message({"chat_id": "100", "chat_type": "chat",
                          "sender_id": 77, "sender": {"first_name": "Иван"},
                          "text": f"один\n{longest}", "media": []}))
    txt = ft.sent[0]["text"]
    assert "\n\nАвтор <b>Иван</b>" in txt
    assert "-------------------" not in txt
    assert "-" * len(longest) not in txt
    assert ft.sent[0]["parse_mode"] == "HTML"


def test_dispatch_signature_footer_with_tg_username_link():
    """Подпись снизу: TG-отправитель с username → ссылка https://t.me/<username>."""
    s, acc = _disp_store_with_rule("tg", "200", "tg", "300", "to")
    run(s.update_rule(s.rules_of(acc)[0]["id"], {"sign_ab": True}))
    ft = FakeTg()
    d = RuleDispatcher(s, tg_client=ft, tg_bot_id=999)
    run(d.on_tg_message({"chat": {"id": "200", "type": "supergroup"},
                         "from": {"id": 42, "first_name": "Иван", "username": "ivan"},
                         "text": "привет", "media": []}))
    txt = ft.sent[0]["text"]
    assert txt.startswith("привет")
    assert '<a href="https://t.me/ivan">Иван</a>' in txt


def test_dispatch_signature_tg_album_uses_part_sender_when_sent_separately():
    """Media-only альбом: footer отдельным сообщением, автор берётся из первой части."""
    s, acc = _disp_store_with_rule("tg", "200", "tg", "300", "to")
    run(s.update_rule(s.rules_of(acc)[0]["id"], {"sign_ab": True}))
    ft = FakeTg()
    d = RuleDispatcher(s, tg_client=ft, tg_bot_id=999)
    d.source_title = lambda m, cid: "Привет · тема 12" if m == "tg" else None
    run(d.on_tg_album({
        "chat": {"id": "200", "type": "supergroup", "title": "Привет"},
        "message_thread_id": 12,
        "message_ids": [10, 11],
        "caption": None,
        "entities": [],
        "media": [{"type": "photo", "file_id": "F1"}, {"type": "photo", "file_id": "F2"}],
        "parts": [
            {"message_id": 10, "chat": {"id": "200", "type": "supergroup", "title": "Привет"},
             "from": {"id": 42, "first_name": "Иван", "username": "ivan"}},
            {"message_id": 11, "chat": {"id": "200", "type": "supergroup", "title": "Привет"},
             "from": {"id": 42, "first_name": "Иван", "username": "ivan"}},
        ],
    }))
    assert len(ft.groups) == 1
    assert all("caption" not in m for m in ft.groups[0]["media"])
    assert len(ft.sent) == 1
    txt = ft.sent[0]["text"]
    assert '<a href="https://t.me/ivan">Иван</a>' in txt
    assert "Привет · тема 12" not in txt
    assert ft.sent[0]["parse_mode"] == "HTML"


def test_dispatch_signature_tg_album_with_text_stays_one_album_caption():
    """Текстовый альбом: короткий caption вместе с footer остаётся в media group."""
    s, acc = _disp_store_with_rule("tg", "200", "tg", "300", "to")
    run(s.update_rule(s.rules_of(acc)[0]["id"], {"sign_ab": True}))
    ft = FakeTg()
    d = RuleDispatcher(s, tg_client=ft, tg_bot_id=999)
    d.source_title = lambda m, cid: "Привет · тема 12" if m == "tg" else None
    run(d.on_tg_album({
        "chat": {"id": "200", "type": "supergroup", "title": "Привет"},
        "message_thread_id": 12,
        "message_ids": [10, 11],
        "caption": "альбом",
        "entities": [],
        "media": [{"type": "photo", "file_id": "F1"}, {"type": "photo", "file_id": "F2"}],
        "parts": [
            {"message_id": 10, "chat": {"id": "200", "type": "supergroup", "title": "Привет"},
             "from": {"id": 42, "first_name": "Иван", "username": "ivan"}},
            {"message_id": 11, "chat": {"id": "200", "type": "supergroup", "title": "Привет"},
             "from": {"id": 42, "first_name": "Иван", "username": "ivan"}},
        ],
    }))
    assert len(ft.groups) == 1
    media = ft.groups[0]["media"]
    assert media[0]["caption"].startswith("альбом")
    assert '<a href="https://t.me/ivan">Иван</a>' in media[0]["caption"]
    assert "caption" not in media[1]
    assert ft.sent == []


def test_dispatch_signature_footer_with_max_link():
    """Подпись снизу: MAX-отправитель → ссылка max://user/<id> (внутри MAX работает)."""
    s, acc = _disp_store_with_rule("max", "100", "max", "200", "to")
    run(s.update_rule(s.rules_of(acc)[0]["id"], {"sign_ab": True}))
    fm = FakeMax()
    d = RuleDispatcher(s, max_client=fm, max_bot_id=999)
    run(d.on_max_message({"chat_id": "100", "chat_type": "chat",
                          "sender_id": 77, "sender": {"first_name": "Иван", "username": "ivan"},
                          "text": "тест", "media": []}))
    txt = fm.sent[0]["text"]
    assert txt.startswith("тест")
    assert '<a href="max://user/77">Иван</a>' in txt


def test_dispatch_signature_cross_platform_link_becomes_bold():
    """Кросс-платформа: max://user → жирное имя в TG (схема не работает)."""
    s, acc = _disp_store_with_rule("max", "100", "tg", "200", "to")
    run(s.update_rule(s.rules_of(acc)[0]["id"], {"sign_ab": True}))
    ft = FakeTg()
    d = RuleDispatcher(s, tg_client=ft, max_bot_id=999)
    run(d.on_max_message({"chat_id": "100", "chat_type": "chat",
                          "sender_id": 77, "sender": {"first_name": "Иван"},
                          "text": "кросс", "media": []}))
    txt = ft.sent[0]["text"]
    assert txt.startswith("кросс")
    assert '<b>Иван</b>' in txt
    assert "max://" not in txt


def test_dispatch_tg_forward_from_channel_has_no_visible_attribution():
    # TG→TG: forward_origin используется для служебной логики, но видимую строку
    # «Переслано из …» в копию больше не добавляем.
    s, acc = _disp_store_with_rule("tg", "200", "tg", "300", "both")
    ft = FakeTg()
    d = RuleDispatcher(s, tg_client=ft, tg_bot_id=999)
    run(d.on_tg_message({"chat": {"id": "200", "type": "supergroup"}, "from": {"id": 5},
                         "text": "репост", "media": [],
                         "forward_origin": {"type": "channel", "chat": {"title": "Канал Дурова"}, "message_id": 7}}))
    assert len(ft.sent) == 1 and ft.sent[0]["chat_id"] == "300"
    assert ft.sent[0]["text"] == "репост"
    assert "Переслано из" not in ft.sent[0]["text"]
    assert ft.sent[0]["parse_mode"] is None


def test_dispatch_tg_forward_from_user_has_no_visible_attribution():
    # TG→MAX: имя из forward_origin больше не выводится в тексте копии.
    s, acc = _disp_store_with_rule("tg", "200", "max", "100", "both")
    fm = FakeMax()
    d = RuleDispatcher(s, max_client=fm, tg_bot_id=999)
    run(d.on_tg_message({"chat": {"id": "200", "type": "supergroup"}, "from": {"id": 5},
                         "text": "текст", "media": [],
                         "forward_origin": {"type": "user", "sender_user": {"first_name": "Иван", "last_name": "Петров"}}}))
    assert len(fm.sent) == 1
    assert fm.sent[0]["text"] == "текст"
    assert "Переслано из" not in fm.sent[0]["text"]
    assert fm.sent[0]["fmt"] is None


def test_dispatch_tg_forward_hidden_user_name_not_visible():
    # forward_origin hidden_user не выводится в видимом тексте.
    s, acc = _disp_store_with_rule("tg", "200", "tg", "300", "both")
    ft = FakeTg()
    d = RuleDispatcher(s, tg_client=ft, tg_bot_id=999)
    run(d.on_tg_message({"chat": {"id": "200", "type": "supergroup"}, "from": {"id": 5},
                         "text": "x", "media": [],
                         "forward_origin": {"type": "hidden_user", "sender_user_name": "A<b>&Co"}}))
    assert ft.sent[0]["text"] == "x"
    assert "A&lt;b&gt;&amp;Co" not in ft.sent[0]["text"]


def test_dispatch_max_forward_from_user_has_no_visible_attribution():
    # MAX→MAX: реальный форвард ОТ ПОЛЬЗОВАТЕЛЯ не получает видимую строку «Переслано из …».
    s, acc = _disp_store_with_rule("max", "100", "max", "200", "to")
    fm = FakeMax()
    d = RuleDispatcher(s, max_client=fm)
    run(d.on_max_message({"chat_id": "100", "sender_id": 5, "chat_type": "chat", "sender": {},
                          "text": "пересланное", "media": [], "is_forward": True,
                          "link": {"type": "forward", "chat_id": -68,
                                   "sender": {"first_name": "Галина", "last_name": "", "name": "Галина"}}}))
    assert len(fm.sent) == 1
    assert fm.sent[0]["text"] == "пересланное"
    assert "Переслано из" not in fm.sent[0]["text"]
    assert fm.sent[0]["fmt"] is None


def test_dispatch_max_channel_own_post_not_attributed():
    # КРИТИЧНО (защита от регресса): пост MAX-КАНАЛА тоже приходит как link.type=forward, но
    # БЕЗ link.sender — его НЕЛЬЗЯ помечать «переслано», иначе каждый пост канала получит
    # ложную атрибуцию. Должен уйти чистым plain, без строки «Переслано из».
    s, acc = _disp_store_with_rule("max", "100", "max", "200", "to")
    fm = FakeMax()
    d = RuleDispatcher(s, max_client=fm)
    run(d.on_max_message({"chat_id": "100", "sender_id": None, "chat_type": "channel", "sender": {},
                          "text": "обычный пост канала", "media": [], "is_forward": True,
                          "link": {"type": "forward", "chat_id": "100"}}))   # тот же чат, без sender
    assert len(fm.sent) == 1
    assert "Переслано из" not in (fm.sent[0]["text"] or "")
    assert fm.sent[0]["text"] == "обычный пост канала" and fm.sent[0]["fmt"] is None


def test_dispatch_tg_forward_album_has_no_visible_attribution():
    # Пересланный АЛЬБОМ (on_tg_album): forward_origin не попадает в видимую подпись,
    # короткий caption остаётся внутри media group.
    s, acc = _disp_store_with_rule("tg", "200", "tg", "300", "both")
    ft = FakeTg()
    d = RuleDispatcher(s, tg_client=ft, tg_bot_id=999)
    run(d.on_tg_album({
        "chat": {"id": "200", "type": "supergroup"}, "message_ids": [10, 11],
        "caption": "альбом", "entities": [],
        "media": [{"type": "photo", "file_id": "F1"}, {"type": "photo", "file_id": "F2"}],
        "parts": [{"forward_origin": {"type": "channel", "chat": {"title": "Канал Дурова"}}}],
    }))
    assert len(ft.groups) == 1
    assert ft.groups[0]["media"][0]["caption"] == "альбом"
    assert "caption" not in ft.groups[0]["media"][1]
    assert ft.sent == []


def test_dispatch_forward_keeps_signature_footer_without_attribution():
    # При включённой подписи пересланное сообщение получает обычный footer автора,
    # но не получает строку «Переслано из …».
    s, acc = _disp_store_with_rule("tg", "200", "tg", "300", "both")
    run(s.update_rule(s.rules_of(acc)[0]["id"], {"signature": True}))
    ft = FakeTg()
    d = RuleDispatcher(s, tg_client=ft, tg_bot_id=999)
    run(d.on_tg_message({"chat": {"id": "200", "type": "supergroup"},
                         "from": {"id": 5, "first_name": "Вася"},
                         "text": "тело", "media": [],
                         "forward_origin": {"type": "channel", "chat": {"title": "Канал"}}}))
    txt = ft.sent[0]["text"]
    assert txt.startswith("тело")
    assert "Автор <a href=\"tg://user?id=5\">Вася</a>" in txt
    assert "Переслано из" not in txt
    assert "-------------------" not in txt
    assert ft.sent[0]["parse_mode"] == "HTML"


def test_dispatch_tg_skip_message_forwarded_from_this_bot():
    # Пользователь переслал в группу сообщение, отправленное ЭТИМ ботом
    # (forward_origin.sender_user.id == tg_bot_id) → не синхронизируем собственный контент бота.
    s, acc = _disp_store_with_rule("tg", "200", "tg", "300", "both")
    ft = FakeTg()
    d = RuleDispatcher(s, tg_client=ft, tg_bot_id=999)
    run(d.on_tg_message({"chat": {"id": "200", "type": "supergroup"}, "from": {"id": 5},
                         "text": "эхо бота", "media": [],
                         "forward_origin": {"type": "user",
                                            "sender_user": {"id": 999, "first_name": "MeSync"}}}))
    assert ft.sent == [] and ft.groups == []


def test_dispatch_tg_general_forward_from_this_bot_skipped():
    # Даже в General (message_thread_id отсутствует) пересланное пользователем сообщение,
    # исходно отправленное ботом, не должно уходить дальше.
    s = _fresh_store()
    acc = run(s.get_or_create_account("tg", 777, None))["id"]
    run(s.set_subscription(acc, {"status": "active"}))
    run(s.add_rule({"account_id": acc,
                    "a": {"messenger": "tg", "chat_id": "-1004367421030", "thread_id": "12"},
                    "b": {"messenger": "tg", "chat_id": "-1004367421030", "thread_id": "1"},
                    "dir": "both", "status": "active"}))
    ft = FakeTg()
    d = RuleDispatcher(s, tg_client=ft, tg_bot_id=999)
    run(d.on_tg_message({"chat": {"id": -1004367421030, "type": "supergroup",
                                  "title": "Привет", "is_forum": True},
                         "message_id": 154, "from": {"id": 5}, "text": "из General",
                         "forward_origin": {"type": "user",
                                            "sender_user": {"id": 999, "first_name": "MeSync"}}}))
    assert ft.sent == [] and ft.groups == []


def test_dispatch_tg_forward_from_other_user_not_skipped():
    # Форвард от ДРУГОГО пользователя (id ≠ бот) — синхронизируем как обычно, но без видимой атрибуции.
    s, acc = _disp_store_with_rule("tg", "200", "tg", "300", "both")
    ft = FakeTg()
    d = RuleDispatcher(s, tg_client=ft, tg_bot_id=999)
    run(d.on_tg_message({"chat": {"id": "200", "type": "supergroup"}, "from": {"id": 5},
                         "text": "текст", "media": [],
                         "forward_origin": {"type": "user",
                                            "sender_user": {"id": 7, "first_name": "Иван"}}}))
    assert len(ft.sent) == 1 and ft.sent[0]["text"] == "текст"


def test_dispatch_max_skip_message_forwarded_from_this_bot():
    # MAX: пользователь переслал сообщение этого бота (link.sender.user_id == max_bot_id) → пропуск.
    s, acc = _disp_store_with_rule("max", "100", "max", "200", "to")
    fm = FakeMax()
    d = RuleDispatcher(s, max_client=fm, max_bot_id=999)
    run(d.on_max_message({"chat_id": "100", "sender_id": 5, "chat_type": "chat", "sender": {},
                          "text": "эхо бота", "media": [], "is_forward": True,
                          "link": {"type": "forward", "chat_id": -68,
                                   "sender": {"user_id": 999, "first_name": "MeSync"}}}))
    assert fm.sent == []


def test_dispatch_max_channel_post_not_skipped_as_bot_forward():
    # Защита от регресса: пост MAX-КАНАЛА (is_forward без link.sender) НЕ должен ложно
    # считаться «форвардом от бота» — должен дойти.
    s, acc = _disp_store_with_rule("max", "100", "max", "200", "to")
    fm = FakeMax()
    d = RuleDispatcher(s, max_client=fm, max_bot_id=999)
    run(d.on_max_message({"chat_id": "100", "sender_id": None, "chat_type": "channel", "sender": {},
                          "text": "пост канала", "media": [], "is_forward": True,
                          "link": {"type": "forward", "chat_id": "100"}}))
    assert len(fm.sent) == 1 and fm.sent[0]["text"] == "пост канала"


def test_dispatch_tg_album_skip_forwarded_from_this_bot():
    # Пересланный пользователем альбом сообщений этого бота тоже не синхронизируем.
    s, acc = _disp_store_with_rule("tg", "200", "tg", "300", "both")
    ft = FakeTg()
    d = RuleDispatcher(s, tg_client=ft, tg_bot_id=999)
    run(d.on_tg_album({
        "chat": {"id": "200", "type": "supergroup"}, "message_ids": [10, 11],
        "caption": "альбом", "entities": [],
        "media": [{"type": "photo", "file_id": "F1"}, {"type": "photo", "file_id": "F2"}],
        "parts": [{"forward_origin": {"type": "user", "sender_user": {"id": 999}}}],
    }))
    assert ft.groups == [] and ft.sent == []


def test_source_title_provider_and_title_of():
    # OwnershipManager.title_of: owners → chats фоллбэк, ключ по str(chat_id);
    # make_source_title_provider маршрутизирует по мессенджеру и безопасен при None.
    from control.integration import make_source_title_provider
    from max_sync.ownership import OwnershipManager as MaxOwn
    from telegram_sync.ownership import OwnershipManager as TgOwn
    mx = MaxOwn(None, Path(tempfile.mkdtemp()) / "o.json")
    mx._owners = {"100": {"title": "MAX-канал"}}
    mx._chats = {"101": {"title": "MAX-чат"}}        # нет владельца → берётся из _chats
    tg = TgOwn(None, Path(tempfile.mkdtemp()) / "o.json")
    tg._chats = {"200": {"title": "TG-канал"}}
    assert mx.title_of("100") == "MAX-канал"
    assert mx.title_of(101) == "MAX-чат"             # int chat_id → str-ключ
    assert mx.title_of("999") is None
    assert tg.title_of(200) == "TG-канал"
    prov = make_source_title_provider(mx, tg)
    assert prov("max", "100") == "MAX-канал"
    assert prov("tg", 200) == "TG-канал"
    assert prov("max", "999") is None
    assert prov("xx", "1") is None                   # неизвестный мессенджер
    assert make_source_title_provider(None, None)("max", "1") is None


# ---------------- API smoke (FastAPI TestClient) ----------------
def test_api_flow():
    from fastapi.testclient import TestClient
    from control.api import create_app
    s = _fresh_store()
    _write_ownership(config.MAX_OWNERSHIP_FILE, {
        "1": {"user_id": 777, "title": "A", "rights_ok": True, "type": "channel"},
        "2": {"user_id": 777, "title": "B", "rights_ok": True, "type": "channel"},
    })
    app = create_app(s)
    c = TestClient(app)
    # вход (insecure): создаётся аккаунт с identity max:777
    r = _auth_contact(c, 777, "79001234567")
    assert r.status_code == 200, r.text
    token = r.json()["token"]
    H = {"Authorization": f"Bearer {token}"}
    _accept_legal(c, H)
    # без токена — 401
    assert c.get("/api/sources").status_code == 401
    # источники
    src = c.get("/api/sources", headers=H).json()
    assert {x["id"] for x in src["sources"]} == {"max:1", "max:2"}
    source_detail = c.get("/api/sources/max:1", headers=H)
    assert source_detail.status_code == 200
    assert source_detail.json()["id"] == "max:1"
    # подписка по умолчанию неактивна → активируем напрямую для теста правил
    run(s.set_subscription(r.json()["account"]["id"], {"status": "active"}))
    # правило
    cr = c.post("/api/rules", json={"aId": "max:1", "bId": "max:2", "dir": "to", "signature": False}, headers=H)
    assert cr.status_code == 200, cr.text
    rid = cr.json()["rule"]["id"]
    assert c.get("/api/rules", headers=H).json()["activeCount"] == 1
    # пауза/возобновление
    assert c.post(f"/api/rules/{rid}/pause", headers=H).status_code == 200
    assert c.get("/api/rules", headers=H).json()["activeCount"] == 0
    assert c.post(f"/api/rules/{rid}/resume", headers=H).status_code == 200
    assert c.get("/api/rules", headers=H).json()["activeCount"] == 1
    # трафик
    tr = c.get("/api/traffic", headers=H).json()
    assert tr["limitBytes"] == config.TRAFFIC_LIMIT_BYTES and tr["percent"] == 0
    # код привязки + многоразовая привязка (несколько источников одним кодом)
    code = c.post("/api/sources/code", json={"messenger": "max"}, headers=H).json()
    assert len(code["code"]) == 4 and code["botHandle"]
    run(s.record_code_bind(code["code"], "max:1"))
    run(s.record_code_bind(code["code"], "max:2"))
    pend = c.get("/api/sources/pending", headers=H).json()
    assert pend["status"] == "listening" and pend["code"] == code["code"]
    assert {x["id"] for x in pend["bound"]} == {"max:1", "max:2"}
    # удаление правила
    assert c.delete(f"/api/rules/{rid}", headers=H).status_code == 200
    # уведомления
    notification = run(s.add_notification(
        r.json()["account"]["id"], type="bound", title="Источник привязан"))
    notifications = c.get("/api/notifications", headers=H).json()
    assert notifications["unread"] == 1
    marked = c.post("/api/notifications/read", json={"ids": [notification["id"]]}, headers=H)
    assert marked.status_code == 200 and marked.json()["ok"] is True
    assert c.get("/api/notifications", headers=H).json()["unread"] == 0


# ---------------- аватары источников ----------------
def test_avatar_endpoint_serves_bytes_and_caches():
    # Эндпоинт отдаёт байты фото от fetcher и кэширует (fetcher зовётся один раз).
    from fastapi.testclient import TestClient
    from control.api import create_app, set_avatar_fetcher
    s = _fresh_store()
    a = run(s.get_or_create_account("tg", 71, None))["id"]
    _write_ownership(config.TG_OWNERSHIP_FILE, {
        "-7001": {"user_id": 71, "title": "Чат", "rights_ok": True, "type": "supergroup"},
    })
    calls = []
    async def fake(messenger, chat_id):
        calls.append((messenger, chat_id))
        return ("image/png", b"PNGBYTES")
    set_avatar_fetcher(fake)
    try:
        c = TestClient(create_app(s))
        tok = security.make_avatar_token(a, "tg:-7001")
        r = c.get(f"/api/sources/tg:-7001/avatar?t={tok}")
        assert r.status_code == 200, r.text
        assert r.content == b"PNGBYTES"
        assert r.headers["content-type"] == "image/png"
        assert "max-age" in r.headers.get("cache-control", "")
        # второй запрос — из кэша, fetcher больше не вызывается
        r2 = c.get(f"/api/sources/tg:-7001/avatar?t={tok}")
        assert r2.status_code == 200 and r2.content == b"PNGBYTES"
        assert calls == [("tg", "-7001")]
    finally:
        set_avatar_fetcher(None)


def test_avatar_endpoint_404_and_negative_cache():
    # Нет фото у чата → 404; негативный результат кэшируется (fetcher один раз).
    from fastapi.testclient import TestClient
    from control.api import create_app, set_avatar_fetcher
    s = _fresh_store()
    a = run(s.get_or_create_account("tg", 72, None))["id"]
    _write_ownership(config.TG_OWNERSHIP_FILE, {
        "-7002": {"user_id": 72, "title": "Чат", "rights_ok": True, "type": "supergroup"},
    })
    calls = []
    async def fake(messenger, chat_id):
        calls.append(chat_id); return None
    set_avatar_fetcher(fake)
    try:
        c = TestClient(create_app(s))
        tok = security.make_avatar_token(a, "tg:-7002")
        assert c.get(f"/api/sources/tg:-7002/avatar?t={tok}").status_code == 404
        assert c.get(f"/api/sources/tg:-7002/avatar?t={tok}").status_code == 404
        assert calls == ["-7002"]  # негативный кэш: второй раз не дёргали
    finally:
        set_avatar_fetcher(None)


def test_avatar_endpoint_token_scope():
    # Узкий токен аватара: без токена — 401; битый — 401; СЕССИОННЫЙ токен не подходит
    # (aud≠avatar) — 401; токен, выданный для ДРУГОГО источника — 404 (привязан к src).
    from fastapi.testclient import TestClient
    from control.api import create_app, set_avatar_fetcher
    s = _fresh_store()
    a = run(s.get_or_create_account("tg", 73, None))["id"]
    _write_ownership(config.TG_OWNERSHIP_FILE, {
        "-7003": {"user_id": 73, "title": "Мой", "rights_ok": True, "type": "supergroup"},
    })
    async def fake(messenger, chat_id):
        return ("image/jpeg", b"X")
    set_avatar_fetcher(fake)
    try:
        c = TestClient(create_app(s))
        assert c.get("/api/sources/tg:-7003/avatar").status_code == 401                       # нет токена
        assert c.get("/api/sources/tg:-7003/avatar?t=bad").status_code == 401                  # битый
        sess = security.make_session(a)
        assert c.get(f"/api/sources/tg:-7003/avatar?t={sess}").status_code == 401              # это сессия, не avatar
        other = security.make_avatar_token(a, "tg:-9999")
        assert c.get(f"/api/sources/tg:-7003/avatar?t={other}").status_code == 404             # токен для другого src
        good = security.make_avatar_token(a, "tg:-7003")
        assert c.get(f"/api/sources/tg:-7003/avatar?t={good}").status_code == 200              # верный токен
    finally:
        set_avatar_fetcher(None)


def test_titles_auto_pulled_and_cached():
    # Названия источников подтягиваются из мессенджера (свежие) и кэшируются.
    s = _fresh_store()
    a = run(s.get_or_create_account("tg", 80, None))["id"]
    _write_ownership(config.TG_OWNERSHIP_FILE, {
        "-8001": {"user_id": 80, "title": "Старое имя", "rights_ok": True, "type": "supergroup"},
    })
    calls = []
    async def provider(messenger, chat_id):
        calls.append((messenger, chat_id))
        return {"title": "Новое имя", "icon_url": None, "photo_id": None}
    data = run(sources_mod.list_sources(s, a, title_provider=provider))
    src = next(x for x in data["sources"] if x["id"] == "tg:-8001")
    assert src["title"] == "Новое имя"          # подтянули свежее
    assert calls == [("tg", "-8001")]
    # повторный вызов в пределах TTL — из кэша, provider не дёргаем
    data2 = run(sources_mod.list_sources(s, a, title_provider=provider))
    assert next(x for x in data2["sources"] if x["id"] == "tg:-8001")["title"] == "Новое имя"
    assert calls == [("tg", "-8001")]           # не вырос → кэш сработал


def test_string_provider_backcompat_keeps_avatar():
    # Легаси-провайдер, вернувший строку-название: имя обновляется, аватар НЕ затирается
    # в None и в кэш аватара не пишется None (защитная back-compat ветка _refresh_chat_info).
    s = _fresh_store()
    a = run(s.get_or_create_account("tg", 82, None))["id"]
    _write_ownership(config.TG_OWNERSHIP_FILE, {
        "-8003": {"user_id": 82, "title": "Старое", "rights_ok": True, "type": "supergroup"},
    })
    async def strprovider(messenger, chat_id):
        return "Новое имя"
    data = run(sources_mod.list_sources(s, a, title_provider=strprovider))
    src = next(x for x in data["sources"] if x["id"] == "tg:-8003")
    assert src["title"] == "Новое имя"                                        # имя обновилось
    assert src["avatar"] and "/api/sources/tg:-8003/avatar" in src["avatar"]  # аватар не затёрт


def test_title_refresh_best_effort_on_error():
    # Ошибка получения названия → остаётся сохранённое при привязке.
    s = _fresh_store()
    a = run(s.get_or_create_account("tg", 81, None))["id"]
    _write_ownership(config.TG_OWNERSHIP_FILE, {
        "-8002": {"user_id": 81, "title": "Имя из привязки", "rights_ok": True, "type": "supergroup"},
    })
    async def boom(messenger, chat_id):
        raise RuntimeError("getChat 403")
    data = run(sources_mod.list_sources(s, a, title_provider=boom))
    src = next(x for x in data["sources"] if x["id"] == "tg:-8002")
    assert src["title"] == "Имя из привязки"


def test_session_and_avatar_tokens_do_not_cross():
    # decode_session отвергает avatar-токен; decode_avatar_token отвергает сессию.
    av = security.make_avatar_token("acc_x", "tg:-1")
    se = security.make_session("acc_x")
    account_av = security.make_account_avatar_token("acc_x")
    assert security.decode_session(av) is None
    assert security.decode_avatar_token(se) is None
    assert security.decode_session(account_av) is None
    assert security.decode_avatar_token(account_av) is None
    assert security.decode_account_avatar_token(av) is None
    assert security.decode_account_avatar_token(se) is None
    assert security.decode_session(se) == "acc_x"
    assert security.decode_avatar_token(av) == ("acc_x", "tg:-1")
    assert security.decode_account_avatar_token(account_av) == "acc_x"


def test_avatar_versioned_immutable_cache():
    # Версионный запрос (?v=), совпадающий с актуальным photo_id источника, адресуется по
    # содержимому: тот же v — fetcher один раз и immutable-кэш; сменилось фото (новый
    # photo_id → новый v) — fetcher зовётся снова (свежая загрузка).
    from fastapi.testclient import TestClient
    from control.api import create_app, set_avatar_fetcher
    s = _fresh_store()
    a = run(s.get_or_create_account("tg", 74, None))["id"]
    _write_ownership(config.TG_OWNERSHIP_FILE, {
        "-7004": {"user_id": 74, "title": "Чат", "rights_ok": True, "type": "supergroup"},
    })
    run(s.set_source_info("tg:-7004", photo_id="AAA"))   # актуальная версия фото
    calls = []
    async def fake(messenger, chat_id):
        calls.append(chat_id); return ("image/jpeg", b"V" + bytes([len(calls)]), None)
    set_avatar_fetcher(fake)
    try:
        c = TestClient(create_app(s))
        tok = security.make_avatar_token(a, "tg:-7004")
        r = c.get(f"/api/sources/tg:-7004/avatar?t={tok}&v=AAA")
        assert r.status_code == 200, r.text
        assert "immutable" in r.headers.get("cache-control", "")
        c.get(f"/api/sources/tg:-7004/avatar?t={tok}&v=AAA")     # тот же v → из кэша
        assert calls == ["-7004"]
        run(s.set_source_info("tg:-7004", photo_id="BBB"))       # фото сменилось → новый photo_id
        c.get(f"/api/sources/tg:-7004/avatar?t={tok}&v=BBB")     # новый v → загрузка заново
        assert calls == ["-7004", "-7004"]
    finally:
        set_avatar_fetcher(None)


def test_avatar_forged_version_served_non_immutable():
    # Произвольный/устаревший v (≠ актуальному photo_id) НЕ помечается immutable и не
    # порождает версионную immutable-запись — обслуживается как невёрсионный (короткий кэш).
    from fastapi.testclient import TestClient
    from control.api import create_app, set_avatar_fetcher
    s = _fresh_store()
    a = run(s.get_or_create_account("tg", 75, None))["id"]
    _write_ownership(config.TG_OWNERSHIP_FILE, {
        "-7005": {"user_id": 75, "title": "Чат", "rights_ok": True, "type": "supergroup"},
    })
    run(s.set_source_info("tg:-7005", photo_id="REAL"))
    async def fake(messenger, chat_id):
        return ("image/jpeg", b"IMG", "REAL")
    set_avatar_fetcher(fake)
    try:
        c = TestClient(create_app(s))
        tok = security.make_avatar_token(a, "tg:-7005")
        r = c.get(f"/api/sources/tg:-7005/avatar?t={tok}&v=FORGED")     # подделанный v
        assert r.status_code == 200
        assert "immutable" not in r.headers.get("cache-control", "")
        assert "max-age=3600" in r.headers.get("cache-control", "")
        r2 = c.get(f"/api/sources/tg:-7005/avatar?t={tok}&v=REAL")      # корректный v
        assert "immutable" in r2.headers.get("cache-control", "")
    finally:
        set_avatar_fetcher(None)


def test_avatar_version_bytes_mismatch_not_pinned_immutable():
    # Гонка версия↔байты: v совпадает с known, но фото уже сменилось — fetcher вернул
    # ДРУГУЮ фактическую версию. Ответ НЕ immutable (под ключ запрошенной версии чужие
    # байты не пинятся на год).
    from fastapi.testclient import TestClient
    from control.api import create_app, set_avatar_fetcher
    s = _fresh_store()
    a = run(s.get_or_create_account("tg", 76, None))["id"]
    _write_ownership(config.TG_OWNERSHIP_FILE, {
        "-7006": {"user_id": 76, "title": "Чат", "rights_ok": True, "type": "supergroup"},
    })
    run(s.set_source_info("tg:-7006", photo_id="A"))
    async def fake(messenger, chat_id):
        return ("image/jpeg", b"NEWPHOTO", "B")   # фактически уже фото B
    set_avatar_fetcher(fake)
    try:
        c = TestClient(create_app(s))
        tok = security.make_avatar_token(a, "tg:-7006")
        r = c.get(f"/api/sources/tg:-7006/avatar?t={tok}&v=A")
        assert r.status_code == 200 and r.content == b"NEWPHOTO"
        assert "immutable" not in r.headers.get("cache-control", "")
    finally:
        set_avatar_fetcher(None)


def test_avatar_versioned_eviction_keeps_only_latest():
    # При записи новой версии старые версионные файлы этого источника удаляются (диск
    # не растёт на каждую историческую версию фото).
    import control.avatars as av
    d = _TMP / f"avdir_{time.time_ns()}"
    old = av.CACHE_DIR
    av.CACHE_DIR = d
    try:
        av._write_versioned("tg:-900", av._cache_id("tg:-900", "V1"), "image/jpeg", b"one")
        av._write_versioned("tg:-900", av._cache_id("tg:-900", "V2"), "image/jpeg", b"two")
        imgs = [p.name for p in d.glob("*.img")]
        assert any("V2" in n for n in imgs)
        assert not any("V1" in n for n in imgs)   # старая версия вычищена
    finally:
        av.CACHE_DIR = old


def test_hybrid_avatar_urls_max_direct_tg_versioned():
    # Гибрид: MAX-источник получает ПРЯМОЙ icon.url; Telegram — прокси-URL с версией
    # (?v=<photo_id>). Источники без фото → avatar=None (фронт покажет значок).
    s = _fresh_store()
    a = run(s.get_or_create_account("max", 91, None))["id"]
    run(s.link_identity("tg", 92, a))
    _write_ownership(config.MAX_OWNERSHIP_FILE, {
        "100": {"user_id": 91, "title": "MAX-канал", "rights_ok": True, "type": "channel"},
        "200": {"user_id": 91, "title": "MAX без фото", "rights_ok": True, "type": "channel"},
    })
    _write_ownership(config.TG_OWNERSHIP_FILE, {
        "-300": {"user_id": 92, "title": "TG-группа", "rights_ok": True, "type": "supergroup"},
        "-400": {"user_id": 92, "title": "TG без фото", "rights_ok": True, "type": "supergroup"},
    })
    async def provider(messenger, chat_id):
        if messenger == "max" and chat_id == "100":
            return {"title": "MAX-канал", "icon_url": "https://cdn.max.ru/icon/abc.jpg", "photo_id": None}
        if messenger == "tg" and chat_id == "-300":
            return {"title": "TG-группа", "icon_url": None, "photo_id": "PHOTOUID9"}
        return {"title": None, "icon_url": None, "photo_id": None}  # без фото
    data = run(sources_mod.list_sources(s, a, title_provider=provider))
    by = {x["id"]: x for x in data["sources"]}
    assert by["max:100"]["avatar"] == "https://cdn.max.ru/icon/abc.jpg"      # MAX — прямая ссылка
    assert by["max:200"]["avatar"] is None                                   # MAX без фото — значок
    tgav = by["tg:-300"]["avatar"]
    assert tgav.startswith("/api/sources/tg:-300/avatar?") and "v=PHOTOUID9" in tgav  # TG — версионный прокси
    assert by["tg:-400"]["avatar"] is None                                   # TG без фото — значок


# ---------------- слияние аккаунтов / отвязка ----------------
def test_merge_account_moves_identities_and_sources():
    s = _fresh_store()
    dst = run(s.get_or_create_account("tg", 800, "79990001122"))["id"]
    src = run(s.get_or_create_account("max", 900, None))["id"]
    run(s.add_account_source(src, "max:-111"))
    assert run(s.merge_account(src, dst)) is True
    assert s.account(src) is None                           # src удалён
    assert ("max", "900") in set(s.identities_of(dst))      # идентичность перенесена
    assert "max:-111" in s.account_source_ids(dst)          # источник перенесён
    assert run(s.merge_account(src, dst)) is False          # src больше нет
    assert run(s.merge_account(dst, dst)) is False          # сам в себя — нет


def test_merge_account_sums_per_rule_traffic():
    # Трафик суммируется ВКЛЮЧАЯ разбивку per_rule (иначе перенесённые правила теряли бы
    # историю, а сумма per_rule не сходилась бы с used_bytes).
    s = _fresh_store()
    dst = run(s.get_or_create_account("tg", 801, "79990002233"))["id"]
    src = run(s.get_or_create_account("max", 901, None))["id"]
    run(s.add_traffic(dst, 100, rule_id="r1"))
    run(s.add_traffic(src, 200, rule_id="r2"))
    assert run(s.merge_account(src, dst)) is True
    t = s._data["traffic"][dst]
    assert t["used_bytes"] == 300
    assert t["per_rule"].get("r1") == 100 and t["per_rule"].get("r2") == 200


def test_merge_account_keeps_later_active_subscription():
    # При обеих активных подписках берём с более поздним renew_at (ISO-дата, строка —
    # не int! это всплыло на живой миграции). Не теряем оплаченный период.
    s = _fresh_store()
    dst = run(s.get_or_create_account("tg", 802, "79990003344"))["id"]
    src = run(s.get_or_create_account("max", 902, None))["id"]
    run(s.set_subscription(dst, {"status": "active", "renew_at": "2026-07-01"}))
    run(s.set_subscription(src, {"status": "active", "renew_at": "2027-01-01"}))
    assert run(s.merge_account(src, dst)) is True
    assert s._data["subscriptions"][dst]["renew_at"] == "2027-01-01"


def test_auth_contact_auto_merges_by_confirmed_phone():
    # Регресс старого flow: он уже успел создать два no-phone аккаунта.
    # После TG self-contact MAX-вход с тем же ПОДТВЕРЖДЁННЫМ номером вливает свой legacy-
    # дубль в старший TG-аккаунт и сохраняет его активную подписку.
    from fastapi.testclient import TestClient
    from control.api import create_app
    s = _fresh_store()
    tg_acc = run(s.get_or_create_account("tg", 920000001, None))["id"]
    s.table("accounts")[tg_acc]["created_at"] = int(time.time()) - 60
    run(s.set_subscription(tg_acc, {"status": "active", "renew_at": "2026-07-20"}))
    run(s.confirm_identity_phone("tg", 920000001, "79990000009"))
    c = TestClient(create_app(s))
    phone, uid, auth_date = "79990000009", 91000001, int(time.time())
    max_legacy = run(s.get_or_create_account("max", uid, None))["id"]
    msg = f"authDate={auth_date}\nphone={phone}\nuserId={uid}"
    sig = hmac.new("maxtoken".encode(), msg.encode(), hashlib.sha256).hexdigest()
    r = c.post("/api/auth/contact", json={"messenger": "max", "userId": uid, "phone": phone,
                                          "authDate": auth_date, "hash": sig})
    assert r.status_code == 200, r.text
    assert r.json()["account"]["id"] == tg_acc              # legacy-дубль влился в старший TG
    assert max_legacy not in s.table("accounts")
    assert ("max", "91000001") in set(s.identities_of(tg_acc))
    assert ("tg", "920000001") in set(s.identities_of(tg_acc))
    assert s.subscription(tg_acc)["status"] == "active"
    assert sum(1 for a in s._data["accounts"].values() if a.get("phone") == "79990000009") == 1
    # без валидного hash (неподтверждённый номер) — ни аккаунта, ни сессии.
    r2 = c.post("/api/auth/contact", json={"messenger": "max", "userId": 70707, "phone": phone})
    assert r2.status_code == 400 and r2.json()["detail"]["code"] == "contact_required"
    assert s.find_account_by_identity("max", 70707) is None


def test_delete_source_unbinds_removes_from_list():
    # Отвязка через _source_unbinder удаляет запись ownership → источник исчезает из списка
    # (раньше delete_source чистил только account_sources и источник «оставался»).
    import json as _json
    from fastapi.testclient import TestClient
    from control.api import create_app, set_source_unbinder
    s = _fresh_store()
    a = run(s.get_or_create_account("max", 91000001, "79990000009"))["id"]
    _write_ownership(config.MAX_OWNERSHIP_FILE, {
        "-70000000000002": {"user_id": 91000001, "title": "Канал", "rights_ok": True, "type": "channel"},
    })
    calls = []
    async def unbinder(messenger, chat_id):
        calls.append((messenger, chat_id))
        p = Path(config.MAX_OWNERSHIP_FILE)
        d = _json.loads(p.read_text()); d["owners"].pop(str(chat_id), None)
        p.write_text(_json.dumps(d))
    set_source_unbinder(unbinder)
    try:
        c = TestClient(create_app(s))
        H = {"Authorization": f"Bearer {security.make_session(a)}"}
        assert any(x["id"] == "max:-70000000000002" for x in c.get("/api/sources", headers=H).json()["sources"])
        rd = c.delete("/api/sources/max:-70000000000002", headers=H)
        assert rd.status_code == 200, rd.text
        assert calls == [("max", "-70000000000002")]
        assert not any(x["id"] == "max:-70000000000002" for x in c.get("/api/sources", headers=H).json()["sources"])
    finally:
        set_source_unbinder(None)


def test_tg_download_file_bytes_reads_local_path_with_cap():
    # Локальный Bot API сервер (--local) отдаёт в getFile АБСОЛЮТНЫЙ путь → клиент читает файл
    # с диска (не по HTTP) и соблюдает потолок размера (защита RAM на крупных файлах).
    from telegram_sync.client import TelegramClient
    with tempfile.TemporaryDirectory() as root:
        path = Path(root) / "local.bin"
        path.write_bytes(b"LOCALDATA")
        c = TelegramClient("tok", local_file_root=root)
        data, _ct = run(c.download_file_bytes(str(path)))  # absolute → диск, без сети
        assert data == b"LOCALDATA"
        raised = False
        try:
            run(c.download_file_bytes(str(path), max_bytes=3))  # потолок 3 < 9 → отказ
        except ValueError:
            raised = True
        assert raised, "ожидался ValueError при превышении потолка размера"


def test_tg_download_file_copies_local_path_inside_root():
    from telegram_sync.client import TelegramClient

    with tempfile.TemporaryDirectory() as base:
        root = Path(base) / "bot"
        source = root / "photos" / "avatar.jpg"
        source.parent.mkdir(parents=True)
        source.write_bytes(b"LOCAL-AVATAR")
        destination = Path(base) / "copied" / "avatar.jpg"

        written = run(TelegramClient("tok", local_file_root=root).download_file(
            str(source), destination))

        assert written == len(b"LOCAL-AVATAR")
        assert destination.read_bytes() == b"LOCAL-AVATAR"


def test_tg_relative_file_path_still_downloads_over_http():
    import httpx
    from telegram_sync.client import TelegramClient

    with tempfile.TemporaryDirectory() as base:
        destination = Path(base) / "cloud" / "avatar.jpg"
        seen_paths = []

        def handle(request):
            seen_paths.append(request.url.path)
            return httpx.Response(200, content=b"CLOUD-AVATAR")

        async def scenario():
            client = TelegramClient("tok", "https://telegram.test")
            client._client = httpx.AsyncClient(transport=httpx.MockTransport(handle))
            try:
                return await client.download_file("photos/avatar.jpg", destination)
            finally:
                await client.aclose()

        written = run(scenario())
        assert written == len(b"CLOUD-AVATAR")
        assert destination.read_bytes() == b"CLOUD-AVATAR"
        assert seen_paths == ["/file/bottok/photos/avatar.jpg"]


def test_tg_source_and_account_avatar_fetchers_read_local_api_files():
    from control.integration import make_account_avatar_fetcher, make_avatar_fetcher
    from telegram_sync.client import TelegramClient

    with tempfile.TemporaryDirectory() as base:
        root = Path(base) / "bot"
        source_path = root / "photos" / "source.jpg"
        account_path = root / "profile_photos" / "account.png"
        source_path.parent.mkdir(parents=True)
        account_path.parent.mkdir(parents=True)
        source_data = b"\xff\xd8\xffSOURCE"
        account_data = b"\x89PNG\r\n\x1a\nACCOUNT"
        source_path.write_bytes(source_data)
        account_path.write_bytes(account_data)

        class LocalAvatarTelegram(TelegramClient):
            async def get_chat(self, chat_id):
                assert str(chat_id) == "-100500"
                return {"photo": {
                    "small_file_id": "source-file",
                    "small_file_unique_id": "source-version",
                }}

            async def get_user_profile_photos(self, user_id, *, offset=0, limit=1):
                assert str(user_id) == "700"
                assert offset == 0 and limit == 1
                return {"photos": [[
                    {"file_id": "small", "file_unique_id": "small-version",
                     "width": 64, "height": 64},
                    {"file_id": "account-file", "file_unique_id": "account-version",
                     "width": 320, "height": 320},
                ]]}

            async def get_file(self, file_id):
                paths = {
                    "source-file": source_path,
                    "account-file": account_path,
                }
                return {"file_path": str(paths[file_id])}

        client = LocalAvatarTelegram("tok", local_file_root=root)
        source = run(make_avatar_fetcher(tg_client=client)("tg", "-100500"))
        account = run(make_account_avatar_fetcher(tg_client=client)("tg", "700", {}))

        assert source == ("image/jpeg", source_data, "source-version")
        assert account == ("image/png", account_data, "account-version")


def test_max_source_and_account_avatar_fetchers_use_http_cdn_only():
    from control.integration import make_account_avatar_fetcher, make_avatar_fetcher

    webp_data = b"RIFF\x10\x00\x00\x00WEBPVP8 "

    class AvatarMax:
        def __init__(self):
            self.downloads = []

        async def get_chat(self, chat_id):
            assert str(chat_id) == "500"
            return {"icon": {"url": "https://cdn.max.test/source.webp"}}

        async def download_bytes(self, url, *, max_bytes=None):
            self.downloads.append((url, max_bytes))
            return webp_data, "application/octet-stream", len(webp_data)

    client = AvatarMax()
    source_fetcher = make_avatar_fetcher(max_client=client)
    account_fetcher = make_account_avatar_fetcher(max_client=client)

    source = run(source_fetcher("max", "500"))
    unsafe = run(account_fetcher("max", "700", {"full_avatar_url": "file:///etc/passwd"}))
    account = run(account_fetcher("max", "700", {
        "avatar_url": "https://cdn.max.test/small.webp",
        "full_avatar_url": "https://cdn.max.test/full.webp",
    }))

    assert source == ("image/webp", webp_data, None)
    assert unsafe is None
    assert account == ("image/webp", webp_data, None)
    assert client.downloads == [
        ("https://cdn.max.test/source.webp", None),
        ("https://cdn.max.test/full.webp", 5 * 1024 * 1024),
    ]


def test_tg_local_file_error_does_not_expose_token_path():
    from telegram_sync.client import TelegramClient

    secret_path = "/var/lib/telegram-bot-api/123456:SECRET/photos/missing.jpg"
    try:
        run(TelegramClient("123456:SECRET").download_file_bytes(secret_path))
    except RuntimeError as exc:
        assert str(exc) == "Файл локального Telegram Bot API недоступен"
        assert "SECRET" not in repr(exc)
    else:
        raise AssertionError("недоступный local Bot API path должен завершаться ошибкой")


def test_tg_local_file_path_cannot_escape_configured_root():
    from telegram_sync.client import TelegramClient

    with tempfile.TemporaryDirectory() as base:
        base_path = Path(base)
        root = base_path / "bot"
        root.mkdir()
        outside = base_path / "private.txt"
        outside.write_bytes(b"PRIVATE")
        (root / "escape").symlink_to(outside)
        client = TelegramClient("tok", local_file_root=root)

        for candidate in (outside, root / ".." / "private.txt", root / "escape"):
            try:
                run(client.download_file_bytes(str(candidate)))
            except RuntimeError as exc:
                assert str(exc) == "Файл локального Telegram Bot API недоступен"
                assert str(outside) not in repr(exc)
            else:
                raise AssertionError("выход за local_file_root должен быть запрещён")

        dest = root / "copy.bin"
        try:
            run(client.download_file(str(outside), dest))
        except RuntimeError:
            pass
        else:
            raise AssertionError("download_file не должен копировать файл вне root")
        assert not dest.exists()


# ---------------- реестр «своих» сообщений (защита от петли/самосинхронизации) ----------------
def test_sent_index_remember_contains_evict_persist():
    p = _TMP / f"sent_{time.time_ns()}.json"
    si = SentIndex(p, ttl_seconds=3600, max_entries=2)
    si.remember("tg", 555, 10)
    si.remember("tg", 555, 11)
    assert si.contains("tg", 555, 10) and si.contains("tg", 555, 11)
    assert not si.contains("tg", 555, 99)          # неизвестный id
    assert not si.contains("max", 555, 10)         # другой мессенджер — не путаем
    si.remember("tg", 555, 12)                      # превышен max=2 → вытесняется старейший (10)
    assert not si.contains("tg", 555, 10)
    assert si.contains("tg", 555, 11) and si.contains("tg", 555, 12)
    run(si.flush())                                 # сброс на диск
    si2 = SentIndex(p, ttl_seconds=3600, max_entries=10)
    si2.load()
    assert si2.contains("tg", 555, 11) and si2.contains("tg", 555, 12)   # пережило «рестарт»


def test_sent_index_ttl_expiry():
    # Запись со старой меткой времени отбрасывается по TTL при загрузке; свежая — остаётся.
    p = _TMP / f"sent_{time.time_ns()}.json"
    p.write_text(json.dumps({"items": {"max:-7:mid.OLD": time.time() - 100000,
                                       "max:-7:mid.NEW": time.time()}}), encoding="utf-8")
    si = SentIndex(p, ttl_seconds=3600, max_entries=10)
    si.load()
    assert not si.contains("max", -7, "mid.OLD")   # протухло (старше TTL) → отброшено
    assert si.contains("max", -7, "mid.NEW")       # свежее → осталось


def test_note_sent_records_ids():
    si = _fresh_sent_index()
    d = RuleDispatcher(_fresh_store(), sent_index=si)
    # Telegram: одиночное сообщение и медиагруппа (список Message).
    d.note_tg_sent({"message_id": 42, "chat": {"id": 555}})
    assert si.contains("tg", 555, 42)
    d.note_tg_sent([{"message_id": 1, "chat": {"id": 9}}, {"message_id": 2, "chat": {"id": 9}}])
    assert si.contains("tg", 9, 1) and si.contains("tg", 9, 2)
    # MAX: POST /messages → {"message": Message} (mid в body.mid, чат в recipient.chat_id).
    d.note_max_sent({"message": {"recipient": {"chat_id": -7}, "body": {"mid": "mid.Z"}}})
    assert si.contains("max", -7, "mid.Z")
    d.note_max_sent({})            # без message — не падаем, ничего не пишем
    d.note_tg_sent(None)


def test_skip_own_max_channel_post_via_registry():
    # Свой пост MAX-канала возвращается боту как forward (link.chat_id+message.mid = оригинал,
    # link.sender отсутствует — сверено на живом сырьё). По реестру это «своё» → НЕ синхронизируем
    # (иначе при правиле A⇄B копия ушла бы обратно — петля).
    s, acc = _disp_store_with_rule("max", "100", "tg", "200", "both")
    fm, ft = FakeMax(), FakeTg()
    si = _fresh_sent_index()
    si.remember("max", "100", "mid.OWN")            # бот ранее отправил этот пост в чат 100
    d = RuleDispatcher(s, max_client=fm, tg_client=ft, sent_index=si)
    own = {"chat_id": "100", "sender_id": None, "chat_type": "channel", "sender": {},
           "mid": "envelope-1", "is_forward": True, "text": "пост",
           "link": {"type": "forward", "chat_id": "100", "message": {"mid": "mid.OWN"}}, "media": []}
    run(d.on_max_message(own))
    assert ft.sent == [] and fm.sent == []          # не ушло никуда

    # Чужой пост (mid не из реестра) — синхронизируется как обычно.
    other = dict(own)
    other["link"] = {"type": "forward", "chat_id": "100", "message": {"mid": "mid.OTHER"}}
    run(d.on_max_message(other))
    assert len(ft.sent) == 1 and ft.sent[0]["chat_id"] == "200"


def test_skip_own_tg_post_direct_and_forwarded():
    # (1) Свой пост TG-канала возвращается тем же (chat_id, message_id) → по реестру «своё».
    s, acc = _disp_store_with_rule("tg", 555, "max", "200", "both")
    fm, ft = FakeMax(), FakeTg()
    si = _fresh_sent_index()
    si.remember("tg", 555, 42)
    d = RuleDispatcher(s, max_client=fm, tg_client=ft, sent_index=si)
    run(d.on_tg_message({"chat": {"id": 555, "type": "channel"}, "message_id": 42, "text": "post"}))
    assert fm.sent == []                            # своё → не синхронизируем

    run(d.on_tg_message({"chat": {"id": 555, "type": "channel"}, "message_id": 43, "text": "post"}))
    assert len(fm.sent) == 1                         # чужой message_id → синхронизируем


def test_skip_forwarded_bot_channel_post_tg():
    # Пользователь переслал в группу-источник пост, который БОТ создал в TG-канале:
    # forward_origin.type=="channel" несёт исходные chat.id+message_id → распознаём по реестру.
    s, acc = _disp_store_with_rule("tg", "777", "max", "200", "both")
    fm, ft = FakeMax(), FakeTg()
    si = _fresh_sent_index()
    si.remember("tg", 555, 42)                       # бот создал пост 42 в канале 555
    d = RuleDispatcher(s, max_client=fm, tg_client=ft, sent_index=si)
    base = {"chat": {"id": "777", "type": "supergroup"}, "message_id": 99, "text": "переслал"}
    fwd_own = dict(base, forward_origin={"type": "channel", "chat": {"id": 555}, "message_id": 42})
    run(d.on_tg_message(fwd_own))
    assert fm.sent == []                             # оригинал создан ботом → не синхронизируем

    fwd_other = dict(base, forward_origin={"type": "channel", "chat": {"id": 555}, "message_id": 43})
    run(d.on_tg_message(fwd_other))
    assert len(fm.sent) == 1                          # чужой оригинал → синхронизируем


def test_skip_own_tg_album():
    # Альбом, отправленный этим ботом (sendMediaGroup), возвращается своими message_ids.
    s, acc = _disp_store_with_rule("tg", 555, "max", "200", "both")
    fm, ft = FakeMax(), FakeTg()
    si = _fresh_sent_index()
    si.remember("tg", 555, 70); si.remember("tg", 555, 71)
    d = RuleDispatcher(s, max_client=fm, tg_client=ft, sent_index=si)
    album = {"chat": {"id": 555, "type": "supergroup"}, "message_ids": [70, 71],
             "parts": [{"message_id": 70}, {"message_id": 71}], "caption": "альбом", "media": []}
    run(d.on_tg_album(album))
    assert fm.sent == [] and len(ft.groups) == 0     # свой альбом → не синхронизируем

    album2 = {"chat": {"id": 555, "type": "supergroup"}, "message_ids": [80, 81],
              "parts": [{"message_id": 80}, {"message_id": 81}], "caption": "чужой", "media": []}
    run(d.on_tg_album(album2))
    assert len(fm.sent) == 1                          # чужой альбом → синхронизируем (текст без медиа)


def test_bidirectional_loop_is_broken_by_registry():
    # Сквозной сценарий петли A⇄B: сообщение из A копируется в B; копия в B (как пост канала)
    # возвращается боту — и НЕ уходит обратно в A, потому что хук записал её в реестр.
    s, acc = _disp_store_with_rule("max", "100", "max", "200", "both")

    class HookedMax(FakeMax):
        """Как настоящий клиент: после отправки дёргает on_sent с {"message": Message}."""
        def __init__(self): super().__init__(); self.on_sent = None
        async def send_message(self, **kw):
            self.sent.append(kw)
            res = {"message": {"recipient": {"chat_id": kw.get("chat_id")}, "body": {"mid": "mid.COPY"}}}
            if self.on_sent:
                self.on_sent(res)
            return res

    fm = HookedMax()
    si = _fresh_sent_index()
    d = RuleDispatcher(s, max_client=fm, sent_index=si)
    fm.on_sent = d.note_max_sent                     # проводка как в run_app

    # 1) пользователь пишет в A(100) → бот копирует в B(200), запоминает (max,200,mid.COPY)
    run(d.on_max_message({"chat_id": "100", "sender_id": 5, "chat_type": "chat",
                          "sender": {"first_name": "U"}, "mid": "mid.USER", "text": "привет", "media": []}))
    assert len(fm.sent) == 1 and fm.sent[0]["chat_id"] == "200"
    assert si.contains("max", "200", "mid.COPY")

    # 2) копия в B возвращается боту постом канала (forward link на оригинал в 200) →
    #    распознаётся как «своя» → НЕ уходит обратно в A. Без реестра был бы 2-й send в 100.
    echo = {"chat_id": "200", "sender_id": None, "chat_type": "channel", "sender": {},
            "mid": "envelope-2", "is_forward": True, "text": "привет", "media": [],
            "link": {"type": "forward", "chat_id": "200", "message": {"mid": "mid.COPY"}}}
    run(d.on_max_message(echo))
    assert len(fm.sent) == 1                          # по-прежнему один send — петля разорвана


# ---------------- уникальность правил: по направлению + глобально (между пользователями) ----------------
def test_rule_directed_flows_coexist_same_account():
    # У ОДНОГО аккаунта A→B и B→A — РАЗНЫЕ правила, сосуществуют (нет общего потока).
    s, acc = _account_with_two_sources()
    r1 = run(rules_mod.create_rule(s, acc, a_id="max:1", b_id="max:2", direction="to"))   # 1→2
    r2 = run(rules_mod.create_rule(s, acc, a_id="max:1", b_id="max:2", direction="from"))  # 2→1
    assert r1["status"] == "active" and r2["status"] == "active"
    assert r1["id"] != r2["id"]
    # тот же поток 1→2, но выраженный как (max:2,max:1,from) → дубль у себя
    try:
        run(rules_mod.create_rule(s, acc, a_id="max:2", b_id="max:1", direction="from"))   # = 1→2
        assert False
    except rules_mod.RuleError as e:
        assert e.code == "dup"


def test_rule_uniqueness_is_global_across_users():
    # Источник может быть привязан к нескольким пользователям. Проверка уникальности —
    # глобальная и по направлению.
    s, acc1 = _account_with_two_sources()                       # acc1 (user 777) владеет max:1, max:2
    run(rules_mod.create_rule(s, acc1, a_id="max:1", b_id="max:2", direction="to"))   # acc1: 1→2
    # второй пользователь с теми же источниками (общий источник)
    acc2 = run(s.get_or_create_account("max", 888, None))["id"]
    run(s.add_account_source(acc2, "max:1"))
    run(s.add_account_source(acc2, "max:2"))
    assert run(sources_mod.owns_source(s, acc2, "max:1"))       # источник доступен второму
    # acc2: B→A (2→1) — нет общего потока с acc1 (1→2) → РАЗРЕШЕНО
    r = run(rules_mod.create_rule(s, acc2, a_id="max:1", b_id="max:2", direction="from"))
    assert r["status"] == "active"
    # acc2: A→B (1→2) — такой поток уже есть у acc1 → дубль ДРУГОГО пользователя
    try:
        run(rules_mod.create_rule(s, acc2, a_id="max:1", b_id="max:2", direction="to"))
        assert False
    except rules_mod.RuleError as e:
        assert e.code == "dup_other"
        assert "другого пользователя" in e.message


def test_rule_update_direction_conflict_is_checked():
    # Смена направления не должна создавать дубль (глобально). acc1: 1→2; acc2: 2→1.
    # acc2 меняет своё правило на A→B (1→2) → конфликт с acc1.
    s, acc1 = _account_with_two_sources()
    run(rules_mod.create_rule(s, acc1, a_id="max:1", b_id="max:2", direction="to"))    # acc1: 1→2
    acc2 = run(s.get_or_create_account("max", 999, None))["id"]
    run(s.add_account_source(acc2, "max:1"))
    run(s.add_account_source(acc2, "max:2"))
    r2 = run(rules_mod.create_rule(s, acc2, a_id="max:1", b_id="max:2", direction="from"))  # acc2: 2→1
    # acc2 меняет from→to (теперь 1→2) → пересекается с acc1 → dup_other
    try:
        run(rules_mod.update_rule(s, acc2, r2["id"], {"dir": "to"}))
        assert False
    except rules_mod.RuleError as e:
        assert e.code == "dup_other"
    # смена на both у acc2 (2→1 + 1→2) тоже пересекается с acc1 (1→2) → dup_other
    try:
        run(rules_mod.update_rule(s, acc2, r2["id"], {"dir": "both"}))
        assert False
    except rules_mod.RuleError as e:
        assert e.code == "dup_other"
    # та же смена dir на собственном правиле без пересечений проходит (acc2 остаётся from)
    ok = run(rules_mod.update_rule(s, acc2, r2["id"], {"dir": "from"}))
    assert ok["dir"] == "from"


def test_rule_update_changes_source():
    # Регрессия на баг «редактирование правила не меняет источник». Смена источника при
    # update_rule персистится, только если переданы a_id/b_id (snake_case). Раньше фронт
    # S10.save их не отправлял (слал лишь {dir, signAB, signBA}) → смена источника молча
    # терялась. Тест фиксирует контракт, на который теперь опирается исправленный фронт.
    s = _fresh_store()
    acc = run(s.get_or_create_account("max", 777, None))["id"]
    _write_ownership(config.MAX_OWNERSHIP_FILE, {
        "1": {"user_id": 777, "title": "A", "rights_ok": True, "type": "channel"},
        "2": {"user_id": 777, "title": "B", "rights_ok": True, "type": "channel"},
        "3": {"user_id": 777, "title": "C", "rights_ok": True, "type": "channel"},
    })
    rid = run(rules_mod.create_rule(s, acc, a_id="max:1", b_id="max:2", direction="to"))["id"]
    # 1) Нагрузка, которую теперь шлёт исправленный S10.save: a_id/b_id + dir.
    out = run(rules_mod.update_rule(s, acc, rid, {"a_id": "max:1", "b_id": "max:3", "dir": "both"}))
    assert out["b"]["sourceId"] == "max:3" and out["b"]["title"] == "C" and out["dir"] == "both"
    assert s.rule(rid)["b"] == {"messenger": "max", "chat_id": "3"}      # персистентно на диске
    # 2) Старая (баговая) нагрузка без a_id/b_id источники НЕ меняет — документируем контракт.
    out2 = run(rules_mod.update_rule(s, acc, rid, {"dir": "to"}))
    assert out2["a"]["sourceId"] == "max:1" and out2["b"]["sourceId"] == "max:3"
    # 3) Источник вне владения аккаунта игнорируется (гейт owns_source) — без ошибки и смены.
    out3 = run(rules_mod.update_rule(s, acc, rid, {"b_id": "max:999"}))
    assert out3["b"]["sourceId"] == "max:3"


def test_rule_patch_changes_source_via_api():
    # Сквозной HTTP-путь PATCH /api/rules/{id} — ровно тот формат, что шлёт исправленный
    # фронт при редактировании (a_id/b_id/dir/signAB/signBA).
    from fastapi.testclient import TestClient
    from control.api import create_app
    s = _fresh_store()
    _write_ownership(config.MAX_OWNERSHIP_FILE, {
        "1": {"user_id": 777, "title": "A", "rights_ok": True, "type": "channel"},
        "2": {"user_id": 777, "title": "B", "rights_ok": True, "type": "channel"},
        "3": {"user_id": 777, "title": "C", "rights_ok": True, "type": "channel"},
    })
    c = TestClient(create_app(s))
    r = _auth_contact(c, 777, "79001234567")
    token = r.json()["token"]; H = {"Authorization": f"Bearer {token}"}
    _accept_legal(c, H)
    run(s.set_subscription(r.json()["account"]["id"], {"status": "active"}))
    rid = c.post("/api/rules", json={"aId": "max:1", "bId": "max:2", "dir": "to", "signature": False},
                 headers=H).json()["rule"]["id"]
    pr = c.patch(f"/api/rules/{rid}",
                 json={"a_id": "max:1", "b_id": "max:3", "dir": "both", "signAB": True, "signBA": False},
                 headers=H)
    assert pr.status_code == 200, pr.text
    assert pr.json()["rule"]["b"]["sourceId"] == "max:3" and pr.json()["rule"]["dir"] == "both"
    lst = c.get("/api/rules", headers=H).json()["rules"]
    assert lst[0]["b"]["sourceId"] == "max:3" and lst[0]["b"]["title"] == "C"


def test_rule_endpoints_include_avatar_url():
    # Эндпоинты правила несут avatar (прокси-URL фото) — чтобы страница правил показывала
    # настоящие аватарки источников, как на странице «Источники».
    s, acc = _account_with_two_sources()
    r = run(rules_mod.create_rule(s, acc, a_id="max:1", b_id="max:2", direction="to"))
    for ep in (r["a"], r["b"]):
        assert isinstance(ep.get("avatar"), str) and ep["avatar"].startswith("/api/sources/")
    lst = run(rules_mod.list_rules(s, acc))           # и в списке тоже
    assert lst["rules"][0]["a"]["avatar"].startswith("/api/sources/")


# ---------------- проактивное отслеживание прав Telegram (my_chat_member) ----------------
class _FakeTgOwnClient:
    """Минимальный TG-клиент для OwnershipManager: фиксирует вызовы call() (sendMessage и т.п.)."""
    def __init__(self): self.calls = []
    async def call(self, method, params): self.calls.append((method, params)); return {}


def test_tg_topic_external_claim_binds_topic_not_whole_supergroup():
    from control.integration import make_external_claim_cb, make_extra_codes_provider
    from telegram_sync.ownership import OwnershipManager

    class TopicClient(_FakeTgOwnClient):
        async def call(self, method, params):
            self.calls.append((method, params))
            if method == "getChat":
                return {"id": -100500, "type": "supergroup", "title": "Форум", "is_forum": True}
            if method == "getChatMember":
                return {"status": "member"}
            return {}

    s = _fresh_store()
    acc = run(s.get_or_create_account("tg", 777, None))["id"]
    code = run(s.issue_code(acc, "tg"))["code"]
    path = _TMP / f"tgown_topic_{time.time_ns()}.json"
    mgr = OwnershipManager(TopicClient(), path, bot_id=42,
                           extra_codes_provider=make_extra_codes_provider(s),
                           on_external_claim=make_external_claim_cb(s, "tg"))
    run(mgr.on_chat_message({"chat": {"id": -100500, "type": "supergroup", "title": "Форум"},
                             "from": {"id": 777}, "text": code,
                             "message_thread_id": 42, "is_topic_message": True}))
    assert s.account_source_ids(acc) == ["tg:-100500:42"]
    data = json.loads(path.read_text())
    assert data["owners"]["-100500"]["user_id"] is None       # whole forum не выдан как источник
    # list_sources читает ГЛОБАЛЬНЫЙ config.TG_OWNERSHIP_FILE (а не path менеджера этого теста);
    # раньше тест полагался на записи -100500, оставленные в нём БОЛЕЕ РАННИМИ тестами, и падал
    # изолированно/при изменении набора. Делаем самодостаточным — как соседний topic-тест.
    _write_ownership(config.TG_OWNERSHIP_FILE, {
        "-100500": {"user_id": None, "title": "Форум", "rights_ok": True, "type": "supergroup"},
    })
    sources = run(sources_mod.list_sources(s, acc))["sources"]
    assert [x["id"] for x in sources] == ["tg:-100500:42"]


def test_rule_roles_directions():
    from control.rules import rule_roles
    a = {"messenger": "tg", "chat_id": "100"}
    b = {"messenger": "max", "chat_id": "200"}
    assert rule_roles({"a": a, "b": b, "dir": "to"}, "tg:100") == {"source"}    # a→b: a читаем
    assert rule_roles({"a": a, "b": b, "dir": "to"}, "max:200") == {"target"}   # a→b: в b пишем
    assert rule_roles({"a": a, "b": b, "dir": "from"}, "tg:100") == {"target"}  # b→a: в a пишем
    assert rule_roles({"a": a, "b": b, "dir": "from"}, "max:200") == {"source"}
    assert rule_roles({"a": a, "b": b, "dir": "both"}, "tg:100") == {"source", "target"}
    assert rule_roles({"a": a, "b": b, "dir": "both"}, "max:200") == {"source", "target"}
    assert rule_roles({"a": a, "b": b, "dir": "both"}, "tg:999") == set()       # не участвует
    assert rule_roles({"a": None, "b": b, "dir": "both"}, "max:200") == set()   # неполное правило
    topic = {"messenger": "tg", "chat_id": "100", "thread_id": "42"}
    assert rule_roles({"a": topic, "b": b, "dir": "to"}, "tg:100") == {"source"}      # права чата
    assert rule_roles({"a": topic, "b": b, "dir": "to"}, "tg:100:42") == {"source"}   # точная тема
    assert rule_roles({"a": topic, "b": b, "dir": "to"}, "tg:100:99") == set()


def test_tg_bot_can_read_write_and_reason():
    from telegram_sync.ownership import (_bot_can_read as cr, _bot_can_write as cw,
                                         _missing_rights_reason as reason)
    # Канал: читать может только админ; писать — админ с can_post (или creator).
    assert cr({"status": "administrator"}, "channel") is True
    assert cr({"status": "creator"}, "channel") is True
    assert cr({"status": "member"}, "channel") is False        # не админ → постов не получает
    assert cr({"status": "left"}, "channel") is False
    assert cw({"status": "administrator", "can_post_messages": True}, "channel") is True
    assert cw({"status": "administrator", "can_post_messages": False}, "channel") is False
    assert cw({"status": "creator"}, "channel") is True
    # Группа: читать может участник; писать — любой неограниченный; ограничение снимает запись.
    assert cr({"status": "member"}, "supergroup") is True
    assert cw({"status": "member"}, "supergroup") is True
    assert cw({"status": "administrator"}, "group") is True
    assert cw({"status": "restricted", "can_send_messages": False}, "supergroup") is False
    assert cw({"status": "restricted", "can_send_messages": True}, "supergroup") is True
    assert cw({"status": "kicked"}, "group") is False
    # Причина (что вернуть): канал без админки / канал-админ без поста / группа.
    assert "администратор" in reason({"status": "member"}, "channel", read=False, write=False)
    assert "Публикация" in reason({"status": "administrator", "can_post_messages": False},
                                  "channel", read=True, write=False)
    assert "отправлять" in reason({"status": "restricted", "can_send_messages": False},
                                  "supergroup", read=True, write=False)


def test_tg_observe_rights_change_calls_hook_without_disabling_source():
    # my_chat_member: бота понизили с админа канала до участника → зовём on_rights_change
    # (read=write=False, причина про админ-права), но rights_ok НЕ трогаем (источник не отключаем).
    from telegram_sync.ownership import OwnershipManager
    path = _TMP / f"tgown_{time.time_ns()}.json"
    calls = []
    async def hook(chat_id, can_read, can_write, reason): calls.append((chat_id, can_read, can_write, reason))
    mgr = OwnershipManager(_FakeTgOwnClient(), path, bot_id=42, on_rights_change=hook)
    mgr._owners["-100"] = {"user_id": 7, "title": "Канал", "rights_ok": True, "type": "channel"}
    upd = {"my_chat_member": {
        "chat": {"id": -100, "type": "channel", "title": "Канал"},
        "old_chat_member": {"user": {"id": 42}, "status": "administrator", "can_post_messages": True},
        "new_chat_member": {"user": {"id": 42}, "status": "member"}}}
    run(mgr.observe(upd))
    assert len(calls) == 1
    cid, can_read, can_write, reason = calls[0]
    assert cid == "-100" and can_read is False and can_write is False and "администратор" in reason
    assert mgr._owners["-100"]["rights_ok"] is True            # источник НЕ отключён
    # member→member: значимые способности не изменились → хук не зовём (без шума)
    run(mgr.observe({"my_chat_member": {
        "chat": {"id": -100, "type": "channel", "title": "Канал"},
        "old_chat_member": {"user": {"id": 42}, "status": "member"},
        "new_chat_member": {"user": {"id": 42}, "status": "member"}}}))
    assert len(calls) == 1


def test_tg_observe_left_unbinds_and_skips_rights_hook():
    # Удаление бота (kicked) — отдельная ветка: привязка снимается, «меня удалили», хук смены прав
    # НЕ зовётся (это не изменение прав, а выход из чата).
    from telegram_sync.ownership import OwnershipManager
    path = _TMP / f"tgown_{time.time_ns()}.json"
    calls = []
    async def hook(*a): calls.append(a)
    client = _FakeTgOwnClient()
    mgr = OwnershipManager(client, path, bot_id=42, on_rights_change=hook)
    mgr._owners["-100"] = {"user_id": 7, "title": "Канал", "rights_ok": True, "type": "channel"}
    run(mgr.observe({"my_chat_member": {
        "chat": {"id": -100, "type": "channel", "title": "Канал"},
        "old_chat_member": {"user": {"id": 42}, "status": "administrator", "can_post_messages": True},
        "new_chat_member": {"user": {"id": 42}, "status": "kicked"}}}))
    assert "-100" not in mgr._owners and calls == []
    assert any(m == "sendMessage" for m, _ in client.calls)    # уведомили «меня удалили»


def test_tg_bot_removed_cleans_sources_and_rules():
    from telegram_sync.ownership import OwnershipManager
    s, acc = _disp_store_with_rule("tg", "-100", "max", "200", "to")
    run(s.add_account_source(acc, "tg:-100"))
    removed = []
    async def on_removed(chat_id, title=None):
        removed.append((chat_id, title))
        await s.delete_source_references("tg", chat_id)
    client = _FakeTgOwnClient()
    mgr = OwnershipManager(client, _TMP / f"tgown_{time.time_ns()}.json",
                           bot_id=42, on_removed=on_removed)
    mgr._owners["-100"] = {"user_id": 7, "title": "Канал", "rights_ok": True, "type": "channel"}
    mgr._chats["-100"] = {"type": "channel", "title": "Канал"}
    run(mgr.observe({"my_chat_member": {
        "chat": {"id": -100, "type": "channel", "title": "Канал"},
        "old_chat_member": {"user": {"id": 42}, "status": "administrator", "can_post_messages": True},
        "new_chat_member": {"user": {"id": 42}, "status": "kicked"}}}))
    assert removed == [("-100", "Канал")]
    assert s.rules_of(acc) == []
    assert "tg:-100" not in s.account_source_ids(acc)


def test_max_bot_removed_cleans_sources_and_rules():
    from max_sync.ownership import OwnershipManager as MaxOwn
    s, acc = _disp_store_with_rule("max", "100", "tg", "200", "to")
    run(s.add_account_source(acc, "max:100"))
    removed = []
    async def on_removed(chat_id, title=None):
        removed.append((chat_id, title))
        await s.delete_source_references("max", chat_id)
    class Client:
        async def send_message(self, **_kw): return {"message": {"body": {"mid": "m1"}}}
    mgr = MaxOwn(Client(), _TMP / f"maxown_{time.time_ns()}.json",
                 bot_id=1, on_removed=on_removed)
    mgr._owners["100"] = {"user_id": 7, "title": "MAX-чат", "rights_ok": True, "type": "chat"}
    mgr._chats["100"] = {"type": "chat", "title": "MAX-чат"}
    run(mgr.observe({"update_type": "bot_removed", "chat_id": 100}))
    assert removed == [("100", "MAX-чат")]
    assert s.rules_of(acc) == []
    assert "max:100" not in s.account_source_ids(acc)


def test_tg_rights_change_source_read_loss_raises_and_clears():
    # Правило tg:100 (источник-канал) → max:200. Бот потерял право ЧИТАТЬ tg:100 → баннер у
    # правила + уведомление владельцу ОДИН раз (дедуп); вернули права → баннер гаснет, сообщение
    # удаляется. Тот же двухканальный warning, что и в MAX, источник/правило не отключаем.
    s, acc = _disp_store_with_rule("tg", "100", "max", "200", "to")
    rid = s.rules_of(acc)[0]["id"]
    d = RuleDispatcher(s)
    notices, cleared = [], []
    async def warn_cb(chat_id, account_id, reason):
        notices.append((chat_id, account_id, reason)); return {"mid": f"m{chat_id}"}
    async def clr_cb(m, c, ref): cleared.append((m, c, ref))
    d.tg_rights_warn_cb = warn_cb
    d.delivery_clear_cb = clr_cb
    run(d.on_tg_rights_change("100", can_read=False, can_write=True, reason="права администратора канала"))
    assert s.rule(rid)["delivery_warn"] is True
    assert notices == [("100", acc, "права администратора канала")]
    run(d.on_tg_rights_change("100", can_read=False, can_write=True, reason="права администратора канала"))
    assert len(notices) == 1                                    # повтор — без дубля
    run(d.on_tg_rights_change("100", can_read=True, can_write=True, reason=""))
    assert "delivery_warn" not in s.rule(rid)                   # права вернули → баннер погас
    assert cleared == [("tg", "100", {"mid": "m100"})]          # сообщение в чате удалено


def test_tg_rights_change_target_write_loss():
    # Правило max:100 → tg:200 (приёмник-канал). Потеря права ПИСАТЬ (can_write=False) поднимает
    # warning; восстановление — гасит. Чтение приёмника не важно (роль target).
    s, acc = _disp_store_with_rule("max", "100", "tg", "200", "to")
    rid = s.rules_of(acc)[0]["id"]
    d = RuleDispatcher(s)
    notices = []
    async def warn_cb(chat_id, account_id, reason): notices.append(chat_id); return {"mid": "x"}
    d.tg_rights_warn_cb = warn_cb
    run(d.on_tg_rights_change("200", can_read=True, can_write=False, reason="право «Публикация сообщений»"))
    assert s.rule(rid)["delivery_warn"] is True and notices == ["200"]
    run(d.on_tg_rights_change("200", can_read=True, can_write=True, reason=""))
    assert "delivery_warn" not in s.rule(rid)


def test_tg_rights_change_rearm_after_hide():
    # «Скрыть» уведомления в чате ре-армит чат-канал: следующее событие потери прав шлёт снова.
    s, acc = _disp_store_with_rule("tg", "100", "max", "200", "to")
    d = RuleDispatcher(s)
    notices = []
    async def warn_cb(chat_id, account_id, reason): notices.append(chat_id); return {"mid": "x"}
    d.tg_rights_warn_cb = warn_cb
    run(d.on_tg_rights_change("100", can_read=False, can_write=True, reason="r"))
    run(d.on_tg_rights_change("100", can_read=False, can_write=True, reason="r"))
    assert len(notices) == 1                                    # дедуп
    d.note_chat_warn_hidden("tg", "100")                        # «Скрыть» в чате → ре-арм
    run(d.on_tg_rights_change("100", can_read=False, can_write=True, reason="r"))
    assert len(notices) == 2                                    # пришло снова


def test_tg_rights_change_no_rules_is_noop():
    # Чат не участвует ни в одном правиле → ни баннера, ни уведомления (нечего синхронизировать).
    s, acc = _disp_store_with_rule("tg", "100", "max", "200", "to")
    d = RuleDispatcher(s)
    notices = []
    async def warn_cb(chat_id, account_id, reason): notices.append(chat_id); return {"mid": "x"}
    d.tg_rights_warn_cb = warn_cb
    run(d.on_tg_rights_change("777", can_read=False, can_write=False, reason="r"))
    assert notices == [] and all("delivery_warn" not in r for r in s.table("rules").values())


def test_reactive_tg_delivery_failure_warns():
    # Реактивный путь для TG-приёмника (как в MAX): отправка падает → баннер + уведомление,
    # правило НЕ отключаем. «если отправка не удалась — просим проверить права».
    s, acc = _disp_store_with_rule("max", "100", "tg", "200", "to")
    rid = s.rules_of(acc)[0]["id"]
    class FlakyTg(FakeTg):
        async def send_message(self, chat_id, text, parse_mode=None, **kw):
            raise RuntimeError("403 bot can't post")
    d = RuleDispatcher(s, tg_client=FlakyTg())
    events = []
    async def err_cb(m, c, a): events.append((m, c)); return {"mid": "x"}
    d.delivery_error_cb = err_cb
    run(d.on_max_message({"chat_id": "100", "sender_id": 5, "chat_type": "chat",
                          "sender": {"first_name": "О"}, "text": "x", "markup": None, "media": []}))
    assert events == [("tg", "200")]                            # уведомили о сбое доставки в TG
    assert s.rule(rid)["delivery_warn"] is True                 # баннер поднят
    assert s.rules_of(acc)[0]["status"] == "active"             # правило НЕ отключено


# --- миграция группа→супергруппа (Telegram сменил chat_id) ---

class _MigrateErr(RuntimeError):
    """Имитация TelegramError при отправке в чат, повышенный до супергруппы: Bot API кладёт
    новый id в parameters.migrate_to_chat_id (дакт-тайпинг по .parameters в _tg_migrated_to)."""
    def __init__(self, new_id):
        super().__init__("group chat was upgraded to a supergroup chat")
        self.parameters = {"migrate_to_chat_id": new_id}


def test_store_migrate_tg_endpoint():
    # Перепривязка endpoint'ов правил tg:old→tg:new:1; MAX и несовпадающие — не трогаем;
    # идемпотентно. Обычная группа после повышения до forum-супергруппы становится General-темой.
    s, acc = _disp_store_with_rule("max", "100", "tg", "-5464813148", "both")
    rid = s.rules_of(acc)[0]["id"]
    run(s.add_account_source(acc, "tg:-5464813148"))
    run(s.add_account_source(acc, "tg:-5464813148:42"))
    code = run(s.issue_code(acc, "tg"))["code"]
    run(s.record_code_bind(code, "tg:-5464813148:42"))
    run(s.set_source_info("tg:-5464813148", title="Старый"))
    affected = run(s.migrate_tg_endpoint("-5464813148", "-1004367421030"))
    assert affected == [rid]
    assert s.rule(rid)["b"]["chat_id"] == "-1004367421030"      # tg-endpoint переписан
    assert s.rule(rid)["b"]["thread_id"] == "1"                 # выбран первый топик General
    assert s.rule(rid)["a"] == {"messenger": "max", "chat_id": "100"}   # MAX не тронут
    assert "tg:-1004367421030" in s.account_source_ids(acc)
    assert "tg:-1004367421030:42" in s.account_source_ids(acc)
    assert "tg:-1004367421030:42" in s.active_codes()[code]["bound"]
    assert s.cached_source_info("tg:-1004367421030")["title"] == "Старый"
    assert run(s.migrate_tg_endpoint("-5464813148", "-1004367421030")) == []  # повтор — no-op
    assert run(s.migrate_tg_endpoint("999", "888")) == []       # нет такого id — никого


def test_tg_chat_migrated_rekeys_warn_state_and_rules():
    # on_tg_chat_migrated: правило перепривязано + состояние warning'а (живое сообщение в чате и
    # реестр сбойных целей) перенесено со старого ключа на новый — иначе баннер не погас бы.
    s, acc = _disp_store_with_rule("max", "100", "tg", "200", "to")
    rid = s.rules_of(acc)[0]["id"]
    d = RuleDispatcher(s)
    d._warn_notice[("tg", "200")] = {"mid": "m200"}             # как будто слали уведомление в чат
    d._rule_fail_dests[rid] = {("tg", "200")}                   # и подняли баннер по этой цели
    run(d.on_tg_chat_migrated("200", "-1009"))
    assert s.rule(rid)["b"]["chat_id"] == "-1009"               # правило указывает на супергруппу
    assert s.rule(rid)["b"]["thread_id"] == "1"                 # и только на первый топик General
    assert ("tg", "200") not in d._warn_notice and d._warn_notice[("tg", "-1009:1")] == {"mid": "m200"}
    assert d._rule_fail_dests[rid] == {("tg", "-1009:1")}       # ключ цели переключён на General
    note = s.notifications_of(acc)[0]
    assert note["type"] == "rules" and note["link"] == {"screen": "rules"}
    assert "General" in note["subtitle"] and str(s.rule(rid)["number"]) in note["subtitle"]


def test_reactive_tg_migration_self_heal_and_retry():
    # Сообщение MAX→TG: первая отправка в старый id падает «upgraded to supergroup», диспетчер
    # перепривязывает правило/владение (chat_migrated_cb) и ПОВТОРЯЕТ на новый id — без warning'а.
    s, acc = _disp_store_with_rule("max", "100", "tg", "200", "to")
    rid = s.rules_of(acc)[0]["id"]
    class MigratingTg(FakeTg):
        async def send_message(self, chat_id, text, parse_mode=None, message_thread_id=None,
                               **kw):
            if str(chat_id) == "200":
                raise _MigrateErr("-1009")                      # старый id → ошибка миграции
            return await super().send_message(chat_id, text, parse_mode=parse_mode,
                                              message_thread_id=message_thread_id, **kw)
    d = RuleDispatcher(s, tg_client=MigratingTg())
    migrated = []
    async def coord(old_id, new_id):
        migrated.append((old_id, new_id)); await d.on_tg_chat_migrated(old_id, new_id)
    d.chat_migrated_cb = coord
    err = []
    async def err_cb(m, c, a): err.append((m, c)); return {"mid": "x"}
    d.delivery_error_cb = err_cb
    run(d.on_max_message({"chat_id": "100", "sender_id": 5, "chat_type": "chat",
                          "sender": {"first_name": "О"}, "text": "привет", "markup": None, "media": []}))
    assert migrated == [("200", "-1009")]                       # миграция применена один раз
    assert s.rule(rid)["b"]["chat_id"] == "-1009"               # правило перепривязано на новый id
    assert s.rule(rid)["b"]["thread_id"] == "1"
    assert [x["chat_id"] for x in d.tg_client.sent] == ["-1009"]  # доставлено в супергруппу
    assert [x["message_thread_id"] for x in d.tg_client.sent] == [None]
    assert "delivery_warn" not in s.rule(rid) and err == []     # повтор удался → ни баннера, ни тревоги


def test_ownership_migrate_chat_moves_owner_idempotent():
    from telegram_sync.ownership import OwnershipManager
    path = _TMP / f"tgown_{time.time_ns()}.json"
    mgr = OwnershipManager(_FakeTgOwnClient(), path, bot_id=42)
    mgr._owners["-5464813148"] = {"user_id": 7, "title": "Привет", "rights_ok": True, "type": "group"}
    mgr._chats["-5464813148"] = {"type": "group", "title": "Привет"}
    assert run(mgr.migrate_chat("-5464813148", "-1004367421030")) is True
    assert "-5464813148" not in mgr._owners and "-5464813148" not in mgr._chats
    assert mgr._owners["-1004367421030"]["user_id"] == 7 and mgr._owners["-1004367421030"]["rights_ok"] is True
    assert mgr._owners["-1004367421030"]["type"] == "supergroup"
    assert mgr._owners["-1004367421030"]["is_forum"] is True
    assert mgr._chats["-1004367421030"]["type"] == "supergroup"
    assert mgr._chats["-1004367421030"]["is_forum"] is True
    assert run(mgr.migrate_chat("-5464813148", "-1004367421030")) is False    # повтор — no-op


def test_ownership_observe_migration_signal_calls_hook():
    # Сервисное сообщение миграции в observe → хук-координатор (old, new). Оба сигнала: из старой
    # группы (migrate_to_chat_id) и из новой супергруппы (migrate_from_chat_id).
    from telegram_sync.ownership import OwnershipManager
    path = _TMP / f"tgown_{time.time_ns()}.json"
    calls = []
    async def hook(old_id, new_id): calls.append((old_id, new_id))
    mgr = OwnershipManager(_FakeTgOwnClient(), path, bot_id=42, on_chat_migrated=hook)
    run(mgr.observe({"message": {"chat": {"id": -5464813148, "type": "group"},
                                 "migrate_to_chat_id": -1004367421030}}))
    run(mgr.observe({"message": {"chat": {"id": -1004367421030, "type": "supergroup"},
                                 "migrate_from_chat_id": -5464813148}}))
    assert calls == [("-5464813148", "-1004367421030"), ("-5464813148", "-1004367421030")]
    # обычное сообщение без миграции — хук не зовём
    run(mgr.observe({"message": {"chat": {"id": -1004367421030, "type": "supergroup"}, "text": "hi"}}))
    assert len(calls) == 2


# ---- MessageMap ----
def _fresh_message_map(ttl=3600, max_entries=10000):
    return MessageMap(_TMP / f"mm_{time.time_ns()}.json", ttl_seconds=ttl, max_entries=max_entries)


def test_message_map_record_and_lookup():
    mm = _fresh_message_map()
    mm.record("max", "100", "mid1", "tg", "200", "42", text="привет")
    assert mm.lookup("max", "100", "mid1") == [("tg", "200", "42")]
    assert mm.lookup("max", "100", "missing") == []
    assert mm.text_snapshot("max", "100", "mid1") == "привет"
    assert mm.text_snapshot("tg", "200", "42") == "привет"


def test_message_map_one_to_many():
    mm = _fresh_message_map()
    mm.record("tg", "-100", "10", "max", "200", "m1")
    mm.record("tg", "-100", "10", "max", "300", "m2")
    targets = mm.lookup("tg", "-100", "10")
    assert len(targets) == 2
    assert ("max", "200", "m1") in targets
    assert ("max", "300", "m2") in targets


def test_message_map_persistence():
    path = _TMP / f"mm_persist_{time.time_ns()}.json"
    mm = MessageMap(path, ttl_seconds=3600, max_entries=10000)
    mm.record("max", "100", "mid1", "tg", "200", "42", text="сохранённый текст")
    run(mm.flush())
    mm2 = MessageMap(path, ttl_seconds=3600, max_entries=10000)
    mm2.load()
    assert mm2.lookup("max", "100", "mid1") == [("tg", "200", "42")]
    assert mm2.text_snapshot("max", "100", "mid1") == "сохранённый текст"


def test_message_map_ttl_expiry():
    mm = _fresh_message_map(ttl=1)
    mm.record("max", "100", "mid1", "tg", "200", "42")
    import time as t
    t.sleep(1.1)
    assert mm.lookup("max", "100", "mid1") == []


# ---- баг-фикс: MAX→TG медиа + inline keyboard ----
def test_dispatch_max_to_tg_single_media_preserves_inline_keyboard():
    """MAX сообщение с одним фото и inline-кнопкой → кнопка не теряется."""
    s, _acc = _disp_store_with_rule("max", "100", "tg", "200", "to")
    ft = FakeTg()
    fm = FakeMaxDl(blobs={"https://i.ok.ru/photo.jpg": (b"\xff\xd8\xff", "image/jpeg")})
    d = RuleDispatcher(s, tg_client=ft, max_client=fm)
    d._UploadFile = lambda data, filename=None, content_type=None: data
    run(d.on_max_message({"chat_id": "100", "sender_id": 5, "chat_type": "chat",
                          "sender": {"first_name": "Оля"}, "text": "фото с кнопкой",
                          "markup": None, "media": [{"type": "image", "url": "https://i.ok.ru/photo.jpg"}],
                          "attachments": [
                              {"type": "image", "raw": {"type": "image", "payload": {"url": "https://i.ok.ru/photo.jpg"}}},
                              {"type": "inline_keyboard", "raw": {"type": "inline_keyboard",
                                  "payload": {"buttons": [[{"type": "link", "text": "Сайт", "url": "https://ex.com"}]]}}}
                          ]}))
    assert len(ft.photos) == 1
    assert "reply_markup" in ft.photos[0]
    kb = ft.photos[0]["reply_markup"]["inline_keyboard"]
    assert kb[0][0]["text"] == "Сайт"
    assert kb[0][0]["url"] == "https://ex.com"


# ---- маппинг сообщений при доставке ----
def test_message_map_recorded_on_delivery():
    """При доставке сообщения маппинг source→target записывается автоматически."""
    s, _acc = _disp_store_with_rule("max", "100", "tg", "200", "to")
    ft = FakeTg()
    mm = _fresh_message_map()
    d = RuleDispatcher(s, tg_client=ft, message_map=mm)
    # Имитируем on_sent: FakeTg не зовёт _fire_sent, поэтому подключим хук вручную.
    _orig_send = ft.send_message
    async def _send_with_hook(chat_id, text, **kw):
        await _orig_send(chat_id, text, **kw)
        d.note_tg_sent({"chat": {"id": int(chat_id)}, "message_id": 42})
    ft.send_message = _send_with_hook

    run(d.on_max_message({"chat_id": "100", "mid": "m555", "sender_id": 5, "chat_type": "chat",
                          "sender": {"first_name": "Оля"}, "text": "привет",
                          "markup": None, "media": [], "attachments": []}))
    targets = mm.lookup("max", "100", "m555")
    assert len(targets) == 1
    assert targets[0] == ("tg", "200", "42")
    assert mm.text_snapshot("max", "100", "m555") == "привет"


# ---- синхронизация правок ----
def test_edit_sync_max_to_tg():
    """Правка сообщения MAX → editMessageText на TG-копии."""
    s, _acc = _disp_store_with_rule("max", "100", "tg", "200", "to")
    ft = FakeTg()
    mm = _fresh_message_map()
    mm.record("max", "100", "m1", "tg", "200", "42")
    d = RuleDispatcher(s, tg_client=ft, message_map=mm)
    run(d.on_max_edit({"chat_id": "100", "mid": "m1", "sender_id": 5, "chat_type": "chat",
                       "sender": {"first_name": "Оля"}, "text": "исправлено",
                       "markup": None, "media": [], "attachments": []}))
    assert len(ft.edits) == 1
    assert ft.edits[0]["chat_id"] == "200"
    assert ft.edits[0]["message_id"] == "42"
    assert ft.edits[0]["text"] == "исправлено"


def test_edit_sync_tg_to_max():
    """Правка сообщения TG → edit_message на MAX-копии."""
    s, _acc = _disp_store_with_rule("tg", "-100", "max", "200", "to")
    fm = FakeMax()
    mm = _fresh_message_map()
    mm.record("tg", "-100", "10", "max", "200", "m42")
    d = RuleDispatcher(s, max_client=fm, message_map=mm)
    run(d.on_tg_edit({"chat": {"id": -100, "type": "channel"}, "message_id": 10,
                      "from": {"id": 5}, "text": "new text", "text_kind": "text",
                      "entities": [], "media": []}))
    assert len(fm.edits) == 1
    assert fm.edits[0]["message_id"] == "m42"
    assert fm.edits[0]["text"] == "new text"


def test_edit_sync_tg_to_tg():
    """Правка TG-сообщения → editMessageText на TG-копии."""
    s, _acc = _disp_store_with_rule("tg", "-100", "tg", "-200", "to")
    ft = FakeTg()
    mm = _fresh_message_map()
    mm.record("tg", "-100", "10", "tg", "-200", "55")
    d = RuleDispatcher(s, tg_client=ft, message_map=mm)
    run(d.on_tg_edit({"chat": {"id": -100, "type": "channel"}, "message_id": 10,
                      "from": {"id": 5}, "text": "upd", "text_kind": "text",
                      "entities": [], "media": []}))
    assert len(ft.edits) == 1
    assert ft.edits[0]["message_id"] == "55"
    assert ft.edits[0]["text"] == "upd"


def test_edit_sync_caption_tg_to_tg():
    """Правка caption в TG → editMessageCaption."""
    s, _acc = _disp_store_with_rule("tg", "-100", "tg", "-200", "to")
    ft = FakeTg()
    mm = _fresh_message_map()
    mm.record("tg", "-100", "10", "tg", "-200", "55")
    d = RuleDispatcher(s, tg_client=ft, message_map=mm)
    run(d.on_tg_edit({"chat": {"id": -100, "type": "channel"}, "message_id": 10,
                      "from": {"id": 5}, "text": "new cap", "text_kind": "caption",
                      "entities": [], "media": [{"type": "photo"}]}))
    assert len(ft.edits) == 1
    assert "caption" in ft.edits[0]
    assert ft.edits[0]["caption"] == "new cap"


def test_edit_sync_skips_own_messages():
    """Правка СВОЕГО сообщения (бота) не вызывает цикл."""
    s, _acc = _disp_store_with_rule("max", "100", "tg", "200", "to")
    ft = FakeTg()
    mm = _fresh_message_map()
    si = _fresh_sent_index()
    si.remember("max", "100", "m1")
    mm.record("max", "100", "m1", "tg", "200", "42")
    d = RuleDispatcher(s, tg_client=ft, message_map=mm, sent_index=si)
    run(d.on_max_edit({"chat_id": "100", "mid": "m1", "sender_id": 5, "chat_type": "chat",
                       "sender": {"first_name": "Bot"}, "text": "edit",
                       "markup": None, "media": [], "attachments": []}))
    assert len(ft.edits) == 0


def test_edit_sync_no_mapping_no_crash():
    """Правка сообщения без маппинга — молча пропускается."""
    s, _acc = _disp_store_with_rule("max", "100", "tg", "200", "to")
    ft = FakeTg()
    mm = _fresh_message_map()
    d = RuleDispatcher(s, tg_client=ft, message_map=mm)
    run(d.on_max_edit({"chat_id": "100", "mid": "unknown", "sender_id": 5, "chat_type": "chat",
                       "sender": {"first_name": "Оля"}, "text": "x",
                       "markup": None, "media": [], "attachments": []}))
    assert len(ft.edits) == 0


# ---- дополнительные тесты: edge-кейсы ----

def test_edit_sync_max_to_max():
    """Правка MAX-сообщения → edit_message на MAX-копии (MAX→MAX правило)."""
    s, _acc = _disp_store_with_rule("max", "100", "max", "200", "to")
    fm = FakeMax()
    mm = _fresh_message_map()
    mm.record("max", "100", "m1", "max", "200", "m42")
    d = RuleDispatcher(s, max_client=fm, message_map=mm)
    run(d.on_max_edit({"chat_id": "100", "mid": "m1", "sender_id": 5, "chat_type": "chat",
                       "sender": {"first_name": "Оля"}, "text": "new max text",
                       "markup": None, "media": [], "attachments": []}))
    assert len(fm.edits) == 1
    assert fm.edits[0]["message_id"] == "m42"
    assert fm.edits[0]["text"] == "new max text"


def test_edit_sync_one_to_many():
    """Одно исходное сообщение → несколько копий → правка применяется ко всем."""
    s, _acc = _disp_store_with_rule("max", "100", "tg", "200", "to")
    ft = FakeTg()
    mm = _fresh_message_map()
    mm.record("max", "100", "m1", "tg", "200", "42")
    mm.record("max", "100", "m1", "tg", "300", "55")
    d = RuleDispatcher(s, tg_client=ft, message_map=mm)
    run(d.on_max_edit({"chat_id": "100", "mid": "m1", "sender_id": 5, "chat_type": "chat",
                       "sender": {"first_name": "Оля"}, "text": "both targets",
                       "markup": None, "media": [], "attachments": []}))
    assert len(ft.edits) == 2
    edited_ids = {e["message_id"] for e in ft.edits}
    assert edited_ids == {"42", "55"}


def test_edit_sync_with_formatting():
    """Правка MAX с форматированием → HTML сохраняется в editMessageText."""
    s, _acc = _disp_store_with_rule("max", "100", "tg", "200", "to")
    ft = FakeTg()
    mm = _fresh_message_map()
    mm.record("max", "100", "m1", "tg", "200", "42")
    d = RuleDispatcher(s, tg_client=ft, message_map=mm)
    run(d.on_max_edit({"chat_id": "100", "mid": "m1", "sender_id": 5, "chat_type": "chat",
                       "sender": {"first_name": "Оля"}, "text": "жирный текст",
                       "markup": [{"type": "strong", "from": 0, "length": 6}],
                       "media": [], "attachments": []}))
    assert len(ft.edits) == 1
    assert ft.edits[0]["parse_mode"] == "HTML"
    assert "<b>" in ft.edits[0]["text"] or "<strong>" in ft.edits[0]["text"]


def test_edit_sync_tg_with_entities():
    """Правка TG с entities (bold) → HTML сохраняется в edit."""
    s, _acc = _disp_store_with_rule("tg", "-100", "tg", "-200", "to")
    ft = FakeTg()
    mm = _fresh_message_map()
    mm.record("tg", "-100", "10", "tg", "-200", "55")
    d = RuleDispatcher(s, tg_client=ft, message_map=mm)
    run(d.on_tg_edit({"chat": {"id": -100, "type": "channel"}, "message_id": 10,
                      "from": {"id": 5}, "text": "bold text", "text_kind": "text",
                      "entities": [{"type": "bold", "offset": 0, "length": 4}],
                      "media": []}))
    assert len(ft.edits) == 1
    assert ft.edits[0]["parse_mode"] == "HTML"
    assert "<b>" in ft.edits[0]["text"]


def test_edit_sync_tg_caption_to_max():
    """Правка caption TG-медиа → edit_message на MAX (caption→text)."""
    s, _acc = _disp_store_with_rule("tg", "-100", "max", "200", "to")
    fm = FakeMax()
    mm = _fresh_message_map()
    mm.record("tg", "-100", "10", "max", "200", "m42")
    d = RuleDispatcher(s, max_client=fm, message_map=mm)
    run(d.on_tg_edit({"chat": {"id": -100, "type": "channel"}, "message_id": 10,
                      "from": {"id": 5}, "text": "new caption", "text_kind": "caption",
                      "entities": [], "media": [{"type": "photo"}]}))
    assert len(fm.edits) == 1
    assert fm.edits[0]["message_id"] == "m42"
    assert fm.edits[0]["text"] == "new caption"


def test_edit_sync_skips_own_tg_message():
    """Правка СВОЕГО TG-сообщения (бот) не вызывает цикл."""
    s, _acc = _disp_store_with_rule("tg", "-100", "max", "200", "to")
    fm = FakeMax()
    mm = _fresh_message_map()
    si = _fresh_sent_index()
    si.remember("tg", -100, 10)
    mm.record("tg", "-100", "10", "max", "200", "m42")
    d = RuleDispatcher(s, max_client=fm, message_map=mm, sent_index=si)
    run(d.on_tg_edit({"chat": {"id": -100, "type": "channel"}, "message_id": 10,
                      "from": {"id": 5}, "text": "edit",
                      "entities": [], "media": []}))
    assert len(fm.edits) == 0


def test_edit_sync_partial_failure_continues():
    """Если редактирование одной копии сбоит, остальные всё равно редактируются."""
    s, _acc = _disp_store_with_rule("max", "100", "tg", "200", "to")
    ft = FakeTg()
    fm = FakeMax()
    mm = _fresh_message_map()
    mm.record("max", "100", "m1", "tg", "200", "42")
    mm.record("max", "100", "m1", "max", "300", "m55")
    d = RuleDispatcher(s, tg_client=ft, max_client=fm, message_map=mm)
    _orig = ft.edit_message_text
    async def _fail_once(*a, **kw):
        raise RuntimeError("TG edit failed")
    ft.edit_message_text = _fail_once
    run(d.on_max_edit({"chat_id": "100", "mid": "m1", "sender_id": 5, "chat_type": "chat",
                       "sender": {"first_name": "Оля"}, "text": "partial",
                       "markup": None, "media": [], "attachments": []}))
    assert len(fm.edits) == 1
    assert fm.edits[0]["message_id"] == "m55"


def test_message_map_eviction():
    """При превышении max_entries старые записи вытесняются."""
    mm = _fresh_message_map(max_entries=3)
    mm.record("max", "100", "m1", "tg", "200", "1")
    mm.record("max", "100", "m2", "tg", "200", "2")
    mm.record("max", "100", "m3", "tg", "200", "3")
    assert len(mm) == 3
    mm.record("max", "100", "m4", "tg", "200", "4")
    assert len(mm) == 3
    assert mm.lookup("max", "100", "m1") == []
    assert mm.lookup("max", "100", "m4") == [("tg", "200", "4")]


def test_message_map_reverse_lookup():
    """reverse_lookup находит ключ source по target."""
    mm = _fresh_message_map()
    mm.record("max", "100", "m1", "tg", "200", "42")
    assert mm.reverse_lookup("tg", "200", "42") == "max:100:m1"
    assert mm.reverse_lookup("tg", "200", "999") is None


def test_message_map_record_none_mid_ignored():
    """record с None mid — молча игнорируется, не крашится."""
    mm = _fresh_message_map()
    mm.record("max", "100", None, "tg", "200", "42")
    mm.record("max", "100", "m1", "tg", "200", None)
    assert len(mm) == 0


def test_edit_sync_no_message_map_noop():
    """Если message_map=None, правки молча игнорируются."""
    s, _acc = _disp_store_with_rule("max", "100", "tg", "200", "to")
    ft = FakeTg()
    d = RuleDispatcher(s, tg_client=ft, message_map=None)
    run(d.on_max_edit({"chat_id": "100", "mid": "m1", "sender_id": 5, "chat_type": "chat",
                       "sender": {"first_name": "Оля"}, "text": "x",
                       "markup": None, "media": [], "attachments": []}))
    assert len(ft.edits) == 0
    run(d.on_tg_edit({"chat": {"id": -100, "type": "channel"}, "message_id": 10,
                      "from": {"id": 5}, "text": "x", "text_kind": "text",
                      "entities": [], "media": []}))
    assert len(ft.edits) == 0


def test_pending_map_source_is_task_local():
    """ContextVar _pending_map_source изолирован между asyncio-задачами."""
    from src.control.integration import _pending_map_source
    results = []
    async def task_a():
        _pending_map_source.set(("max", "100", "m1"))
        await asyncio.sleep(0.05)
        results.append(("a", _pending_map_source.get(None)))
    async def task_b():
        await asyncio.sleep(0.01)
        results.append(("b_before", _pending_map_source.get(None)))
        _pending_map_source.set(("tg", "200", "10"))
        await asyncio.sleep(0.05)
        results.append(("b_after", _pending_map_source.get(None)))
    async def main():
        await asyncio.gather(
            asyncio.create_task(task_a()),
            asyncio.create_task(task_b()),
        )
    run(main())
    a_val = [v for k, v in results if k == "a"][0]
    b_before = [v for k, v in results if k == "b_before"][0]
    b_after = [v for k, v in results if k == "b_after"][0]
    assert a_val == ("max", "100", "m1"), f"task_a saw wrong value: {a_val}"
    assert b_before is None, f"task_b should not see task_a's value: {b_before}"
    assert b_after == ("tg", "200", "10")


# ---------------- сервисный лог-канал (отчёты об ошибках, канал «Info - MeSync») ----------------
from control.service_log import ServiceLog  # noqa: E402


class FakeSvcTg:
    """Фейковый TG-клиент для сервисного канала: полная сигнатура send_message клиента
    (parse_mode, disable_web_page_preview)."""
    def __init__(self, fail_html=False, fail_all=False):
        self.sent = []
        self.fail_html = fail_html
        self.fail_all = fail_all
    async def send_message(self, chat_id, text, *, parse_mode="HTML",
                           disable_web_page_preview=None, **kw):
        if self.fail_all or (self.fail_html and parse_mode == "HTML"):
            raise RuntimeError("svc send failed")
        self.sent.append({"chat_id": chat_id, "text": text, "parse_mode": parse_mode,
                          "preview_off": disable_web_page_preview})


def test_service_log_report_sends_html_to_channel():
    tg = FakeSvcTg()
    svc = ServiceLog(tg, "-1003417920162")
    run(svc.report("Ошибка доставки", ["Правило №1: TG «A» → MAX «B»"],
                   quote="привет <мир>", error=RuntimeError("boom & bang")))
    assert len(tg.sent) == 1
    rep = tg.sent[0]
    assert rep["chat_id"] == "-1003417920162"
    assert rep["parse_mode"] == "HTML"
    assert rep["preview_off"] is True
    assert "<b>Ошибка доставки</b>" in rep["text"]
    assert "Правило №1: TG «A» → MAX «B»" in rep["text"]
    # цитата и ошибка экранированы для Telegram HTML
    assert "<blockquote expandable>привет &lt;мир&gt;</blockquote>" in rep["text"]
    assert "RuntimeError: boom &amp; bang" in rep["text"]


def test_service_log_disabled_is_noop():
    tg = FakeSvcTg()
    run(ServiceLog(tg, "").report("Т", ["x"]))           # нет chat_id
    run(ServiceLog(None, "-1").report("Т", ["x"]))        # нет клиента
    assert tg.sent == []


def test_service_log_send_failure_swallowed():
    svc = ServiceLog(FakeSvcTg(fail_all=True), "-1")
    run(svc.report("Т", ["x"], error=RuntimeError("e")))  # не должно бросить


def test_service_log_html_error_falls_back_to_plain():
    tg = FakeSvcTg(fail_html=True)
    svc = ServiceLog(tg, "-1")
    run(svc.report("Заголовок", ['<a href="https://t.me/u">Имя</a>'], quote="текст <x>"))
    assert len(tg.sent) == 1
    rep = tg.sent[0]
    assert rep["parse_mode"] is None                      # повтор плоским текстом
    assert "<b>" not in rep["text"] and "<a href" not in rep["text"]
    assert "Имя" in rep["text"] and "Заголовок" in rep["text"]
    assert "текст <x>" in rep["text"]                     # entities разэкранированы обратно


def test_service_log_throttle_suppresses_and_marks():
    now = [1000.0]
    tg = FakeSvcTg()
    svc = ServiceLog(tg, "-1", max_per_minute=2, clock=lambda: now[0])
    async def scenario():
        for i in range(5):
            await svc.report(f"Отчёт {i}", [])
        now[0] += 61
        await svc.report("Отчёт после паузы", [])
    run(scenario())
    assert len(tg.sent) == 3                              # 2 в первом окне + 1 во втором
    assert "+3 отчётов подавлено" in tg.sent[2]["text"]   # три подавленных помечены


def test_service_log_submit_fire_and_forget():
    tg = FakeSvcTg()
    svc = ServiceLog(tg, "-1")
    async def scenario():
        svc.submit("Фон", ["строка"])
        assert svc._tasks                                  # задача создана
        await asyncio.gather(*svc._tasks)
    run(scenario())
    assert len(tg.sent) == 1 and "Фон" in tg.sent[0]["text"]


def test_dispatch_failure_reports_to_service_log():
    """Сбой доставки по правилу → отчёт в сервисный канал: правило «источник → приёмник»,
    отправитель ссылкой, само сообщение, текст ошибки."""
    s, _acc = _disp_store_with_rule("tg", "-100", "max", "200", "to")

    class FailMax(FakeMax):
        async def send_message(self, **kw):
            raise RuntimeError("max is down")

    svc_tg = FakeSvcTg()
    d = RuleDispatcher(s, max_client=FailMax(), tg_bot_id=999)
    d.service_log = ServiceLog(svc_tg, "-1003417920162")
    run(d.on_tg_message({"chat": {"id": -100, "type": "channel", "title": "Hellow"},
                         "message_id": 10,
                         "from": {"id": 42, "first_name": "Иван", "username": "ivan"},
                         "text": "пропавшее сообщение", "media": []}))
    assert len(svc_tg.sent) == 1
    text = svc_tg.sent[0]["text"]
    assert "Ошибка доставки" in text
    assert "Правило №1: TG «-100» → MAX «200»" in text     # titles нет → chat_id
    assert '<a href="https://t.me/ivan">Иван</a>' in text  # имя пользователя ссылкой
    assert "<blockquote expandable>пропавшее сообщение</blockquote>" in text
    assert "max is down" in text
    # предупреждение пользователю (баннер mini-app) продолжает работать как раньше
    assert s.rule(list(s.table("rules"))[0]).get("delivery_warn") is True


def test_dispatch_failure_report_uses_source_titles_and_media_note():
    s, _acc = _disp_store_with_rule("max", "100", "tg", "-200", "to")

    class FailTg(FakeTg):
        async def send_message(self, *a, **kw):
            raise RuntimeError("tg unavailable")

    svc_tg = FakeSvcTg()
    d = RuleDispatcher(s, tg_client=FailTg(), max_bot_id=777)
    d.service_log = ServiceLog(svc_tg, "-1")
    d.source_title = lambda m, cid: {"100": "Meat", "-200": "Hellow"}.get(str(cid))
    run(d.on_max_message({"chat_id": 100, "chat_type": "chat", "mid": "m1",
                          "sender_id": 5, "sender": {"first_name": "Ира", "username": "ira"},
                          "text": "фото", "attachments": [{"type": "image"}],
                          "media": [{"type": "image", "url": "http://x/1.jpg"}]}))
    assert len(svc_tg.sent) == 1
    text = svc_tg.sent[0]["text"]
    assert "MAX «Meat» → TG «Hellow»" in text
    # MAX-отправитель: без ссылки (схема max:// в Telegram не валидна), имя + id текстом
    assert "<b>Ира</b> (MAX id <code>5</code> @ira)" in text
    assert "max://" not in text
    assert "Медиа: image×1" in text


def test_edit_sync_failure_reports_to_service_log():
    s, _acc = _disp_store_with_rule("tg", "-100", "max", "200", "to")
    mm = MessageMap(_TMP / f"mm_svc_{time.time_ns()}.json")

    class FailMax(FakeMax):
        async def edit_message(self, *a, **kw):
            raise RuntimeError("edit rejected")

    svc_tg = FakeSvcTg()
    d = RuleDispatcher(s, max_client=FailMax(), tg_bot_id=999, message_map=mm)
    d.service_log = ServiceLog(svc_tg, "-1")
    mm.record("tg", "-100", "10", "max", "200", "m77")
    run(d.on_tg_edit({"chat": {"id": -100, "type": "channel"}, "message_id": 10,
                      "from": {"id": 42, "first_name": "Иван"},
                      "text": "исправленный текст", "entities": [], "media": []}))
    assert len(svc_tg.sent) == 1
    text = svc_tg.sent[0]["text"]
    assert "Ошибка синхронизации правки" in text
    assert "TG «-100» → MAX «200»" in text
    assert "исправленный текст" in text
    assert "edit rejected" in text


def test_api_unhandled_error_returns_friendly_stub_and_reports():
    """Необработанное исключение в API → пользователю дружелюбная заглушка (не сырой
    Internal Server Error), отчёт уходит в сервисный лог."""
    from fastapi.testclient import TestClient
    from control.api import create_app, set_service_log

    class StubSvc:
        def __init__(self): self.calls = []
        def submit(self, title, lines, **kw): self.calls.append((title, lines, kw))

    s = _fresh_store()
    app = create_app(s)
    stub = StubSvc()
    set_service_log(stub)
    try:
        c = TestClient(app, raise_server_exceptions=False)
        token = _auth_contact(c, 555).json()["token"]
        s.notifications_of = lambda acc_id: (_ for _ in ()).throw(RuntimeError("db exploded"))
        r = c.get("/api/notifications", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 500
        detail = r.json()["detail"]
        assert detail["code"] == "internal"
        assert detail["message"] == "Что-то пошло не так. Попробуйте ещё раз чуть позже."
        assert "Internal Server Error" not in r.text
        assert len(stub.calls) == 1
        title, lines, kw = stub.calls[0]
        assert title == "Ошибка control-API"
        assert any("GET /api/notifications" in ln for ln in lines)
        assert isinstance(kw.get("error"), RuntimeError)
    finally:
        set_service_log(None)


def test_stage1_pollers_accept_rule_edit_router():
    """Регрессия деплоя этапа 8: Stage1Poller ОБОИХ ботов должен принимать rule_edit_router
    (run_app.py передаёт его при старте; отсутствие параметра валило сервис при запуске)."""
    import inspect
    from telegram_sync.updates import Stage1Poller as TgPoller
    from max_sync.updates import Stage1Poller as MaxPoller
    assert "rule_edit_router" in inspect.signature(TgPoller.__init__).parameters
    assert "rule_edit_router" in inspect.signature(MaxPoller.__init__).parameters
    # и параметр реально прокидывается во внутренний UpdateRouter
    tg_src = inspect.getsource(TgPoller.__init__)
    assert "rule_edit_router=rule_edit_router" in tg_src


# ---------------- управление трафиком: гейт, пороги, докупка, учёт, API ----------------
def test_traffic_notify_warn80_and_exhausted_once_with_real_subtitle():
    """Пороговые уведомления: 80% — один раз, 100% — один раз, subtitle из фактического
    лимита; флаги персистентны (переживают рестарт стора — нет дублей после перезапуска)."""
    s, acc = _disp_store_with_rule("max", "100", "tg", "200", "to")
    d = RuleDispatcher(s)
    run(s.add_traffic(acc, int(config.TRAFFIC_LIMIT_BYTES * 0.85), rule_id="r"))
    run(d._maybe_traffic_notify(acc))
    run(d._maybe_traffic_notify(acc))                       # повтор — без дубля
    notes = s.notifications_of(acc)
    assert sum("80%" in n["title"] for n in notes) == 1
    # добор до 100% → «исчерпан», тоже один раз
    run(s.add_traffic(acc, config.TRAFFIC_LIMIT_BYTES, rule_id="r"))
    run(d._maybe_traffic_notify(acc))
    run(d._maybe_traffic_notify(acc))
    notes = s.notifications_of(acc)
    exhausted = [n for n in notes if n["title"] == "Медиа-трафик исчерпан"]
    assert len(exhausted) == 1
    assert exhausted[0]["subtitle"] == "0,5 ТБ из 0,5 ТБ"   # дефолтный лимит — как в тарифе
    # флаги ДОЛЖНЫ пережить рестарт: новый стор с того же файла не шлёт дубли
    s2 = ControlStore(s.path)
    d2 = RuleDispatcher(s2)
    run(d2._maybe_traffic_notify(acc))
    assert len([n for n in s2.notifications_of(acc)
                if n["title"] == "Медиа-трафик исчерпан"]) == 1


def test_traffic_gate_closes_for_max_target_with_link_fallback():
    """Исчерпанный трафик, цель MAX: медиа не переносится, уходит текст+ссылка на оригинал,
    трафик не начисляется."""
    s, acc = _disp_store_with_rule("tg", "-100", "max", "200", "to")
    run(s.add_traffic(acc, config.TRAFFIC_LIMIT_BYTES))     # ровно лимит → гейт закрыт
    fm = FakeMax()
    d = RuleDispatcher(s, max_client=fm, tg_bot_id=999)
    run(d.on_tg_message({"chat": {"id": -100, "type": "channel", "title": "Hellow"},
                         "message_id": 7, "from": {"id": 5, "first_name": "Оля"},
                         "text": "с фото",
                         "media": [{"type": "photo", "file_id": "F1", "file_size": 1000}]}))
    assert len(fm.sent) == 1
    assert fm.sent[0].get("attachments") in (None, [])       # медиа не отправлялось
    assert (f'<blockquote>{LINK_NOTE} в источнике "<a href="https://t.me/c//7">'
            'Hellow</a>" в мессенджере telegram.</blockquote>') in fm.sent[0]["text"]
    assert fm.sent[0]["fmt"] == "html"
    assert s.traffic(acc)["used_bytes"] == config.TRAFFIC_LIMIT_BYTES  # ничего не добавилось


def test_traffic_topup_reopens_media_gate_and_spends_only_over_monthly_limit():
    """Докупка (add_topup) — бессрочный остаток: гейт снова открыт, но месячный лимит
    не увеличивается, а пакет тратится только на новые байты сверх месячной квоты."""
    s, acc = _disp_store_with_rule("max", "100", "tg", "200", "to")
    run(s.add_traffic(acc, config.TRAFFIC_LIMIT_BYTES))     # исчерпано
    d0 = RuleDispatcher(s)
    assert d0.decide("max", "100")[0]["media_allowed"] is False
    run(s.add_topup(acc, 10_000))                            # докупили
    et = s.effective_traffic(acc)
    assert et["limit"] == config.TRAFFIC_LIMIT_BYTES
    assert et["topup"] == 10_000
    assert et["media_allowed"] == 1
    d = RuleDispatcher(s, tg_client=FakeTg(),
                       max_client=FakeMaxDl({"https://i/x": (b"PICDATA", "image/jpeg")}))
    assert d.decide("max", "100")[0]["media_allowed"] is True
    run(d.on_max_message({"chat_id": "100", "sender_id": 5, "chat_type": "channel", "sender": {},
                          "text": "", "media": [{"type": "image", "url": "https://i/x"}]}))
    assert s.traffic(acc)["used_bytes"] == config.TRAFFIC_LIMIT_BYTES + len(b"PICDATA")
    assert s.traffic(acc)["topup_bytes"] == 10_000 - len(b"PICDATA")


def test_traffic_topup_is_not_spent_before_monthly_limit_and_survives_reset():
    s, acc = _disp_store_with_rule("max", "100", "tg", "200", "to")
    run(s.set_account_overrides(acc, {"traffic_limit": 1000}))
    run(s.add_topup(acc, 300))
    run(s.add_traffic(acc, 900))
    assert s.traffic(acc)["topup_bytes"] == 300
    assert RuleDispatcher(s).decide("max", "100")[0]["media_allowed"] is True
    run(s.add_traffic(acc, 100))
    assert s.traffic(acc)["topup_bytes"] == 300
    run(s.add_traffic(acc, 125))
    assert s.traffic(acc)["topup_bytes"] == 175
    run(s.reset_traffic(acc))
    tr = s.traffic(acc)
    assert tr["used_bytes"] == 0
    assert tr["topup_bytes"] == 175
    assert tr.get("per_rule") in (None, {})


def test_dispatch_tg_to_tg_counts_declared_file_size():
    """TG→TG: медиа переиспользует file_id (байты через нас не идут), но трафик считается
    по заявленному file_size — как и в остальных направлениях."""
    s, acc = _disp_store_with_rule("tg", "-100", "tg", "-200", "to")
    ft = FakeTg()
    d = RuleDispatcher(s, tg_client=ft, tg_bot_id=999)
    run(d.on_tg_message({"chat": {"id": -100, "type": "channel", "title": "A"},
                         "message_id": 1, "from": {"id": 5, "first_name": "И"},
                         "text": "п",
                         "media": [{"type": "photo", "file_id": "FID", "file_size": 1234}]}))
    assert len(ft.photos) == 1 and ft.photos[0]["photo"] == "FID"
    assert s.traffic(acc)["used_bytes"] == 1234
    rid = next(iter(s.table("rules")))
    assert s.traffic(acc)["per_rule"][rid] == 1234


def test_api_traffic_view_percent_per_rule_and_reset_on_buy():
    """GET /api/traffic: percent от месячного лимита, perRule с названием «A ⇄ B»;
    покупка подписки обнуляет счётчики периода, но не сжигает add-on остаток."""
    from fastapi.testclient import TestClient
    from control.api import create_app, set_billing
    s = _fresh_store()
    app = create_app(s)
    c = TestClient(app)
    token = _auth_contact(c, 314).json()["token"]
    H = {"Authorization": f"Bearer {token}"}
    _accept_legal(c, H)
    acc = c.get("/api/account", headers=H).json()["id"]
    run(s.set_subscription(acc, {"status": "active", "renew_at": "2026-07-31"}))
    _write_ownership(config.MAX_OWNERSHIP_FILE, {
        "1": {"user_id": 314, "title": "Чат А", "rights_ok": True, "type": "chat"},
        "2": {"user_id": 314, "title": "Чат Б", "rights_ok": True, "type": "chat"},
    })
    rid = c.post("/api/rules", json={"aId": "max:1", "bId": "max:2", "dir": "to"},
                 headers=H).json()["rule"]["id"]
    half = config.TRAFFIC_LIMIT_BYTES // 2
    run(s.add_traffic(acc, half, rule_id=rid))
    run(s.add_topup(acc, config.TRAFFIC_LIMIT_BYTES))        # бессрочный add-on, лимит не меняет
    tr = c.get("/api/traffic", headers=H).json()
    assert tr["usedBytes"] == half
    assert tr["limitBytes"] == config.TRAFFIC_LIMIT_BYTES
    assert tr["topupBytes"] == config.TRAFFIC_LIMIT_BYTES
    assert tr["overageBytes"] == 0
    assert tr["mediaAllowed"] is True
    assert tr["percent"] == 50
    assert tr["resetAt"] == "2026-07-31"
    assert tr["perRule"] == [{"ruleId": rid, "title": "Чат А ⇄ Чат Б", "bytes": half}]
    # percent не превышает 100 даже при переборе, add-on уходит только на превышение
    run(s.add_traffic(acc, config.TRAFFIC_LIMIT_BYTES * 4))
    over = c.get("/api/traffic", headers=H).json()
    assert over["percent"] == 100
    assert over["topupBytes"] == 0
    assert over["mediaAllowed"] is False
    # новый add-on перед продлением не должен сгореть при месячном reset
    run(s.add_topup(acc, 123_456))
    # покупка подписки (реальный флоу: /api/pay/checkout + успешный платёж ЮKassa)
    # → новый период, счётчики обнулены
    run(s.set_subscription(acc, {"status": "inactive", "paid_until": 0}))
    yk = FakeYK()
    set_billing(Billing(s, yk, price_rub=299, trial_days=7, return_url="https://x/r"))
    try:
        r = c.post("/api/pay/checkout", json={"mode": "pay", "autopay": False}, headers=H).json()
        yk.complete_payment(r["paymentId"], ok=True, saved=False)
        assert c.get("/api/pay/status", headers=H).json()["state"] == "succeeded"
    finally:
        set_billing(None)
    tr2 = c.get("/api/traffic", headers=H).json()
    assert tr2["usedBytes"] == 0 and tr2["percent"] == 0 and tr2["perRule"] == []
    assert tr2["limitBytes"] == config.TRAFFIC_LIMIT_BYTES
    assert tr2["topupBytes"] == 123_456                       # add-on не имеет срока действия


def test_traffic_notify_fires_via_delivery_path():
    """Порог пересекается реальной доставкой (не прямым вызовом _maybe_traffic_notify):
    уведомление появляется сразу после начисления за медиа. Лимит на время теста —
    маленький (реальные 0,5 ТБ в память не аллоцировать)."""
    s, acc = _disp_store_with_rule("max", "100", "tg", "200", "to")
    orig_limit = config.TRAFFIC_LIMIT_BYTES
    config.TRAFFIC_LIMIT_BYTES = 1000
    try:
        run(s.add_traffic(acc, 790))
        big = b"X" * 20                                       # 790+20 = 81% лимита
        ft = FakeTg()
        fm = FakeMaxDl({"https://i/big": (big, "image/jpeg")})
        d = RuleDispatcher(s, max_client=fm, tg_client=ft)
        run(d.on_max_message({"chat_id": "100", "sender_id": 5, "chat_type": "channel",
                              "sender": {}, "text": "",
                              "media": [{"type": "image", "url": "https://i/big"}]}))
        assert len(ft.photos) == 1
        assert any("80%" in n["title"] for n in s.notifications_of(acc))
    finally:
        config.TRAFFIC_LIMIT_BYTES = orig_limit


# ---------------- уведомления в оба мессенджера (MAX + Telegram) ----------------
def test_bind_notifies_both_messengers_when_two_linked():
    """«Источник привязан» приходит в ОБА мессенджера, если у аккаунта привязаны и MAX, и TG;
    в мессенджере привязки приоритетен отправитель кода."""
    from control.integration import make_external_claim_cb, make_extra_codes_provider
    s = _fresh_store()
    a = run(s.get_or_create_account("tg", 5, "79000000005"))["id"]
    run(s.link_identity("max", 77, a))                       # второй мессенджер привязан
    code = run(s.issue_code(a))["code"]
    sent = []
    async def fake_notify(messenger, uid, text): sent.append((messenger, str(uid), text))
    marker = make_extra_codes_provider(s)()[code]
    cb = make_external_claim_cb(s, "tg", fake_notify)
    run(cb(code, 5, {"id": -100, "title": "Группа", "type": "supergroup"}, marker))
    by_msngr = {m: (uid, text) for m, uid, text in sent}
    assert by_msngr["tg"] == ("5", "✅ Источник «Группа» привязан")
    assert by_msngr["max"] == ("77", "✅ Источник «Группа» привязан")


def test_bind_notify_includes_sender_messenger_for_fresh_identity():
    """Отправитель кода в группе ещё не был identity аккаунта: его identity связывается ДО
    уведомления, поэтому сообщение уходит и ему (в мессенджер привязки), и в другой мессенджер."""
    from control.integration import make_external_claim_cb, make_extra_codes_provider
    s = _fresh_store()
    a = run(s.get_or_create_account("max", 77, None))["id"]   # аккаунт создан из MAX
    code = run(s.issue_code(a))["code"]
    sent = []
    async def fake_notify(messenger, uid, text): sent.append((messenger, str(uid)))
    marker = make_extra_codes_provider(s)()[code]
    cb = make_external_claim_cb(s, "tg", fake_notify)         # код прислали в TG-группу
    run(cb(code, 555, {"id": -100, "title": "Гр", "type": "supergroup"}, marker))
    assert set(sent) == {("tg", "555"), ("max", "77")}
    assert ("tg", "555") in {(m, u) for m, u in s.identities_of(a)}


def test_unbind_notifies_both_messengers():
    """«Источник отвязан» приходит в оба привязанных мессенджера."""
    from fastapi.testclient import TestClient
    from control.api import create_app, set_source_notifier
    s = _fresh_store()
    a = run(s.get_or_create_account("tg", 5, "79000000005"))["id"]
    run(s.link_identity("max", 77, a))
    _write_ownership(config.TG_OWNERSHIP_FILE, {
        "-300": {"user_id": 5, "title": "Группа Х", "rights_ok": True, "type": "supergroup"},
    })
    run(s.add_account_source(a, "tg:-300"))
    sent = []
    async def cap(messenger, uid, text): sent.append((messenger, str(uid), text))
    set_source_notifier(cap)
    try:
        c = TestClient(create_app(s))
        H = {"Authorization": f"Bearer {security.make_session(a)}"}
        assert c.delete("/api/sources/tg:-300", headers=H).status_code == 200
    finally:
        set_source_notifier(None)
    assert {(m, u) for m, u, _t in sent} == {("tg", "5"), ("max", "77")}
    assert all(t == "🗑 Источник «Группа Х» отвязан" for _m, _u, t in sent)


def test_warn_notice_refs_list_cleared_on_recovery_and_on_hide():
    """Уведомление о сбое хранится списком ссылок (по одному сообщению на мессенджер):
    при восстановлении доставки clear-колбэк получает ВЕСЬ список; «Скрыть» в одном
    мессенджере чистит и копии в других (fire-and-forget задача диспетчера)."""
    s, acc = _disp_store_with_rule("max", "100", "tg", "200", "to")
    d = RuleDispatcher(s)
    refs = [{"messenger": "tg", "chat": 5, "mid": 11},
            {"messenger": "max", "mid": "m22"}]
    cleared = []
    async def clear_cb(messenger, chat_id, ref): cleared.append((messenger, str(chat_id), ref))
    d.delivery_clear_cb = clear_cb
    key = ("tg", "200")
    # 1) восстановление доставки: _clear_chat_notice передаёт список целиком
    d._warn_notice[key] = refs
    run(d._clear_chat_notice(key))
    assert cleared == [("tg", "200", refs)] and key not in d._warn_notice
    # 2) «Скрыть»: note_chat_warn_hidden внутри работающего loop чистит остальные копии
    cleared.clear()
    async def scenario():
        d._warn_notice[key] = refs
        d.note_chat_warn_hidden("tg", "200")
        assert key not in d._warn_notice                     # ре-арм произошёл сразу
        await asyncio.gather(*d._bg_tasks)                   # дождаться фоновой чистки
    run(scenario())
    assert cleared == [("tg", "200", refs)]


# ---------------- биллинг подписки (ЮKassa) ----------------
from control.billing import Billing, BillingError, add_month  # noqa: E402


class FakeYK:
    """Фейковый клиент ЮKassa: create/get платежей и нулевых привязок в памяти."""

    def __init__(self):
        self.enabled = True
        self.payments: dict = {}
        self.methods: dict = {}
        self.created: list = []           # журнал create_* вызовов
        self.recurring_outcome = "succeeded"   # статус автоплатежа сразу при создании
        self.cancel_reason = "insufficient_funds"
        self._n = 0

    async def create_payment(self, *, amount_rub, description, metadata=None,
                             save_payment_method=None, payment_method_id=None,
                             embedded=False, idempotence_key=None):
        self._n += 1
        pid = f"pay_{self._n}"
        pay = {"id": pid, "status": "pending", "metadata": metadata or {},
               "amount": {"value": f"{amount_rub}.00", "currency": "RUB"}}
        if embedded:
            pay["confirmation"] = {"type": "embedded", "confirmation_token": f"ct_{pid}"}
        if payment_method_id:  # автоплатёж завершается сразу (как в реальном API)
            pay["status"] = self.recurring_outcome
            if self.recurring_outcome == "succeeded":
                pay["payment_method"] = {"type": "bank_card", "id": payment_method_id,
                                         "saved": True, "title": "Bank card *4444"}
            elif self.recurring_outcome == "canceled":
                pay["cancellation_details"] = {"party": "yoo_money", "reason": self.cancel_reason}
        self.created.append(("payment", {"amount": amount_rub, "save": save_payment_method,
                                         "pm": payment_method_id, "idem": idempotence_key,
                                         "embedded": embedded, "description": description,
                                         "metadata": metadata or {}}))
        self.payments[pid] = pay
        return dict(pay)

    async def get_payment(self, pid):
        return dict(self.payments[pid])

    async def create_payment_method(self, *, type_, return_url, metadata=None,
                                    idempotence_key=None):
        self._n += 1
        mid = f"pm_{self._n}"
        pm = {"id": mid, "type": type_, "status": "pending", "saved": False,
              "metadata": metadata or {},
              "confirmation": {"type": "redirect",
                               "confirmation_url": f"https://yk.example/bind/{mid}"}}
        self.methods[mid] = pm
        self.created.append(("method", {"type": type_, "return_url": return_url}))
        return dict(pm)

    async def get_payment_method(self, mid):
        return dict(self.methods[mid])

    # тестовые ручки
    def complete_binding(self, mid, ok=True):
        m = self.methods[mid]
        m["status"] = "active" if ok else "inactive"
        m["saved"] = ok
        m["title"] = "Bank card *4444"

    def complete_payment(self, pid, ok=True, saved=False):
        p = self.payments[pid]
        p["status"] = "succeeded" if ok else "canceled"
        if ok:
            p["payment_method"] = ({"type": "bank_card", "id": "pm_saved_1", "saved": True,
                                    "title": "Bank card *4444"} if saved
                                   else {"type": "bank_card", "id": "x", "saved": False})
        else:
            p["cancellation_details"] = {"party": "yoo_money", "reason": "general_decline"}


def _billing_env(*, trial_days=7, max_attempts=3):
    s = _fresh_store()
    acc = run(s.get_or_create_account("max", 777, "79001234567"))["id"]
    yk = FakeYK()
    notes: list = []

    async def notify(a, title, subtitle=None):
        notes.append((a, title, subtitle))

    t = {"now": 1_800_000_000.0}
    b = Billing(s, yk, price_rub=299, trial_days=trial_days, return_url="https://x/return",
                renew_retry_seconds=4 * 3600, renew_max_attempts=max_attempts,
                notify=notify, clock=lambda: t["now"])
    return s, acc, yk, b, notes, t


def test_billing_early_renew_window():
    # Ранняя РУЧНАЯ оплата: без автопродления доступна в последние 5 дней до истечения,
    # месяц добавляется К ДАТЕ ИСТЕЧЕНИЯ (оплаченные дни не сгорают); раньше окна — 409;
    # с включённым автопродлением — 409 «списание произойдёт в момент истечения».
    from control.billing import BillingError, add_month
    s, acc, yk, b, notes, t = _billing_env()
    until0 = int(t["now"] + 6 * 86400)
    run(s.set_subscription(acc, {"status": "active", "autopay": False,
                                 "payment_method_id": None, "paid_until": until0}))
    try:
        run(b.start_checkout(acc, "pay", autopay=False))     # 6 дней до истечения — рано
        assert False, "ожидался BillingError"
    except BillingError as e:
        assert e.status == 409 and "за 5 дней" in e.message
    t["now"] += 2 * 86400                                    # осталось 4 дня — окно открыто
    res = run(b.start_checkout(acc, "pay", autopay=False))
    assert res["kind"] == "payment"
    yk.complete_payment(res["paymentId"])
    assert run(b.check_pending(acc)) == "succeeded"
    sub = s.subscription(acc)
    assert sub["paid_until"] == add_month(until0)            # от даты истечения, не от «сейчас»
    assert sub["status"] == "active" and sub["autopay"] is False
    assert any(n[1].startswith("Подписка продлена до") for n in notes)
    # С автопродлением ранняя оплата не нужна и запрещена.
    run(s.set_subscription(acc, {"autopay": True, "payment_method_id": "pm_x",
                                 "paid_until": int(t["now"] + 2 * 86400)}))
    try:
        run(b.start_checkout(acc, "pay", autopay=False))
        assert False, "ожидался BillingError"
    except BillingError as e:
        assert e.status == 409 and "в момент истечения" in e.message


def test_billing_bind_in_window_hides_button_and_notifies():
    # Пользователь в окне ранней оплаты вместо оплаты ПРИВЯЗЫВАЕТ автопродление:
    # canRenewEarly гаснет (кнопка «Продлить» скрывается), уведомление явно говорит,
    # что списание произойдёт в момент истечения подписки.
    from control.api import _subscription_view
    s, acc, yk, b, notes, t = _billing_env()
    # _subscription_view считает окно по РЕАЛЬНЫМ часам — держим фейковые часы рядом.
    t["now"] = time.time()
    until0 = int(t["now"] + 3 * 86400)
    run(s.set_subscription(acc, {"status": "active", "autopay": False,
                                 "payment_method_id": None, "paid_until": until0}))
    assert _subscription_view(s.subscription(acc))["canRenewEarly"] is True
    res = run(b.start_checkout(acc, "bind", method="bank_card"))
    yk.complete_binding(res["paymentMethodId"])
    assert run(b.check_pending(acc)) == "succeeded"
    sub = s.subscription(acc)
    assert sub["autopay"] is True and sub["paid_until"] == until0   # дата истечения не менялась
    assert _subscription_view(sub)["canRenewEarly"] is False        # кнопка скрыта
    bind_note = next(n for n in notes if n[1] == "Автопродление включено")
    assert "в момент истечения" in bind_note[2]


def test_subscription_view_can_renew_early_bounds():
    # canRenewEarly: только активная подписка БЕЗ автопродления в последние 5 дней.
    # canActivateCode: то же окно, но независимо от автопродления.
    from control.api import _subscription_view
    now = time.time()
    base = {"status": "active", "autopay": False, "paid_until": now + 4 * 86400}
    view = _subscription_view(base)
    assert view["canRenewEarly"] is True
    assert view["canActivateCode"] is True
    far = _subscription_view({**base, "paid_until": now + 6 * 86400})
    assert far["canRenewEarly"] is False
    assert far["canActivateCode"] is False
    autopay = _subscription_view({**base, "autopay": True})
    assert autopay["canRenewEarly"] is False
    assert autopay["canActivateCode"] is True
    inactive = _subscription_view({**base, "status": "inactive"})
    assert inactive["canRenewEarly"] is False
    assert inactive["canActivateCode"] is False
    expired = _subscription_view({**base, "paid_until": now - 10})
    assert expired["canRenewEarly"] is False
    assert expired["canActivateCode"] is False
    free = _subscription_view(base, price=0)
    assert free["price"] == 0 and free["plan"] == "individual"


def test_subscription_view_marks_individual_tariff_and_effective_terms():
    from fastapi.testclient import TestClient
    from control.api import create_app
    from control import security
    s = _fresh_store()
    acc = run(s.get_or_create_account("max", 779, "79001112234"))["id"]
    run(s.set_account_overrides(acc, {
        "rule_limit": 25,
        "price": 499,
        "traffic_limit": 1024 ** 4,
    }))
    c = TestClient(create_app(s))
    h = {"Authorization": f"Bearer {security.make_session(acc)}"}

    v = c.get("/api/subscription", headers=h).json()
    assert v["plan"] == "individual"
    assert v["planName"] == "Индивидуальный"
    assert v["isIndividual"] is True
    assert v["price"] == 499
    assert v["ruleLimit"] == 25
    assert v["trafficLimitBytes"] == 1024 ** 4
    assert v["trafficLimitText"] == "1 ТБ"
    assert "До 25 правил пересылки" in v["perks"]
    assert "1 ТБ медиа-трафика за месяц" in v["perks"]


def test_billing_trial_binding_activates_trial():
    s, acc, yk, b, notes, t = _billing_env()
    run(s.add_traffic(acc, 12345))
    res = run(b.start_checkout(acc, "trial", method="bank_card"))
    assert res["kind"] == "binding" and res["confirmationUrl"].startswith("https://yk.example/")
    assert run(b.check_pending(acc)) == "pending"           # пользователь ещё на странице ЮKassa
    yk.complete_binding(res["paymentMethodId"])
    assert run(b.check_pending(acc)) == "succeeded"
    sub = s.subscription(acc)
    assert sub["status"] == "active" and sub["trial"] and sub["trial_used"] and sub["autopay"]
    assert sub["payment_method_id"] == res["paymentMethodId"]
    assert sub["paid_until"] == int(t["now"] + 7 * 86400)
    assert s.traffic(acc)["used_bytes"] == 0                # новый период — трафик обнулён
    assert any("Пробный период" in n[1] for n in notes)
    assert run(b.check_pending(acc)) == "none"              # идемпотентно: pending снят


def test_billing_trial_rules():
    s, acc, yk, b, notes, t = _billing_env()
    # неподдерживаемый способ нулевой привязки (только карта и СБП — docs/yookassa)
    try:
        run(b.start_checkout(acc, "trial", method="sberbank"))
        assert False, "ожидали BillingError"
    except BillingError as e:
        assert e.code == "bad_method"
    # повторный триал запрещён
    run(s.set_subscription(acc, {"trial_used": True}))
    try:
        run(b.start_checkout(acc, "trial"))
        assert False, "ожидали BillingError"
    except BillingError as e:
        assert e.code == "trial_used"


def test_billing_purchase_with_autopay_saves_method():
    s, acc, yk, b, notes, t = _billing_env()
    run(s.add_traffic(acc, 777))
    res = run(b.start_checkout(acc, "pay", autopay=True))
    assert res["kind"] == "payment" and res["confirmationToken"].startswith("ct_")
    kind, args = yk.created[-1]
    assert kind == "payment" and args["save"] is True and args["embedded"]
    yk.complete_payment(res["paymentId"], ok=True, saved=True)
    assert run(b.check_pending(acc)) == "succeeded"
    sub = s.subscription(acc)
    assert sub["status"] == "active" and not sub["trial"] and sub["autopay"]
    assert sub["payment_method_id"] == "pm_saved_1"
    assert sub["paid_until"] == add_month(t["now"])         # ровно +1 месяц
    assert s.traffic(acc)["used_bytes"] == 0
    # повторная покупка при активной подписке запрещена (продление только в момент истечения)
    try:
        run(b.start_checkout(acc, "pay"))
        assert False, "ожидали BillingError"
    except BillingError as e:
        assert e.code == "already_active"


def test_billing_individual_tariff_description_and_amount():
    s, acc, yk, b, notes, t = _billing_env()
    run(s.set_account_overrides(acc, {"price": 499, "rule_limit": 25}))

    res = run(b.start_checkout(acc, "pay", autopay=False))
    assert res["kind"] == "payment"
    created = yk.created[-1][1]
    assert created["amount"] == 499
    assert "Индивидуальный" in created["description"]
    assert "Smart" not in created["description"]


def test_billing_purchase_without_autopay_no_binding():
    s, acc, yk, b, notes, t = _billing_env()
    res = run(b.start_checkout(acc, "pay", autopay=False))
    assert yk.created[-1][1]["save"] is False               # платёж без сохранения способа
    yk.complete_payment(res["paymentId"], ok=True, saved=False)
    assert run(b.check_pending(acc)) == "succeeded"
    sub = s.subscription(acc)
    assert sub["status"] == "active" and not sub["autopay"]
    assert sub["payment_method_id"] is None and sub["trial_used"]


def test_billing_purchase_failed():
    s, acc, yk, b, notes, t = _billing_env()
    res = run(b.start_checkout(acc, "pay", autopay=True))
    yk.complete_payment(res["paymentId"], ok=False)
    assert run(b.check_pending(acc)) == "failed"
    sub = s.subscription(acc)
    assert sub["status"] == "inactive" and sub["pending"] is None and sub["last_error"]


def test_billing_reuses_pending_purchase_until_last_three_minutes():
    s, acc, yk, b, notes, t = _billing_env()
    res1 = run(b.start_checkout(acc, "pay", autopay=True))
    pending = s.subscription(acc)["pending"]
    expires_at = pending["expires_at"]
    assert res1["reused"] is False and pending["id"] == res1["paymentId"]
    run(b.cancel_pending(acc))                              # закрыли окно, объект ЮKassa жив
    assert s.subscription(acc)["pending"]["id"] == res1["paymentId"]
    res2 = run(b.start_checkout(acc, "pay", autopay=True))
    assert res2["reused"] is True
    assert res2["paymentId"] == res1["paymentId"]
    assert res2["confirmationToken"] == res1["confirmationToken"]
    assert len([c for c in yk.created if c[0] == "payment"]) == 1
    t["now"] = expires_at - 179                             # последние 3 минуты: можно перевыпустить
    res3 = run(b.start_checkout(acc, "pay", autopay=True))
    assert res3["reused"] is False and res3["paymentId"] != res1["paymentId"]
    assert len([c for c in yk.created if c[0] == "payment"]) == 2


def test_billing_scenario_switch_replaces_pending_immediately():
    """Живой кейс: случайно выпустили платёжку, сняли галочку автопродления —
    новая платёжка выписывается сразу, без «подождите» (409 checkout_pending убран)."""
    s, acc, yk, b, notes, t = _billing_env()
    # оплата с автопродлением → передумал: оплата без автопродления
    res1 = run(b.start_checkout(acc, "pay", autopay=True))
    run(b.cancel_pending(acc))                              # закрыл окно, объект ЮKassa жив
    res2 = run(b.start_checkout(acc, "pay", autopay=False))
    assert res2["reused"] is False and res2["paymentId"] != res1["paymentId"]
    assert yk.created[-1][1]["save"] is False               # новый платёж — без привязки
    p = s.subscription(acc)["pending"]
    assert p["id"] == res2["paymentId"] and p["autopay"] is False
    # привязка триала → передумал: разовая оплата без привязки
    s2, acc2, yk2, b2, notes2, t2 = _billing_env()
    res3 = run(b2.start_checkout(acc2, "trial", method="bank_card"))
    res4 = run(b2.start_checkout(acc2, "pay", autopay=False))
    assert res4["kind"] == "payment" and res4["reused"] is False
    assert s2.subscription(acc2)["pending"]["id"] == res4["paymentId"]
    # поздний успех брошенной привязки вебхук игнорирует (id ≠ текущий pending)
    yk2.complete_binding(res3["paymentMethodId"])
    run(b2.webhook("payment_method.active", {"id": res3["paymentMethodId"]}))
    sub2 = s2.subscription(acc2)
    assert sub2["payment_method_id"] is None
    assert sub2["pending"]["id"] == res4["paymentId"] and sub2["status"] == "inactive"


def test_billing_reuses_pending_binding_until_last_three_minutes():
    s, acc, yk, b, notes, t = _billing_env()
    res1 = run(b.start_checkout(acc, "trial", method="bank_card"))
    pending = s.subscription(acc)["pending"]
    expires_at = pending["expires_at"]
    assert res1["reused"] is False and pending["id"] == res1["paymentMethodId"]
    run(b.cancel_pending(acc))                              # редирект закрыли, привязка ещё pending
    res2 = run(b.start_checkout(acc, "trial", method="bank_card"))
    assert res2["reused"] is True
    assert res2["paymentMethodId"] == res1["paymentMethodId"]
    assert res2["confirmationUrl"] == res1["confirmationUrl"]
    assert len([c for c in yk.created if c[0] == "method"]) == 1
    t["now"] = expires_at - 179                             # последние 3 минуты: можно начать заново
    res3 = run(b.start_checkout(acc, "trial", method="bank_card"))
    assert res3["reused"] is False and res3["paymentMethodId"] != res1["paymentMethodId"]
    assert len([c for c in yk.created if c[0] == "method"]) == 2


def test_billing_autopay_disable_on_trial_annuls():
    s, acc, yk, b, notes, t = _billing_env()
    res = run(b.start_checkout(acc, "trial"))
    yk.complete_binding(res["paymentMethodId"])
    run(b.check_pending(acc))
    out = run(b.set_autopay(acc, False))
    assert out["annulled"] is True
    sub = s.subscription(acc)
    assert sub["status"] == "inactive" and not sub["trial"] and not sub["autopay"]
    assert sub["payment_method_id"] is None and sub["trial_used"]      # триал сгорел
    assert sub["paid_until"] == int(t["now"])
    assert any("Пробный период завершён" in n[1] for n in notes)


def test_billing_autopay_disable_on_paid_keeps_period():
    s, acc, yk, b, notes, t = _billing_env()
    res = run(b.start_checkout(acc, "pay", autopay=True))
    yk.complete_payment(res["paymentId"], ok=True, saved=True)
    run(b.check_pending(acc))
    until = s.subscription(acc)["paid_until"]
    out = run(b.set_autopay(acc, False))
    assert out["annulled"] is False
    sub = s.subscription(acc)
    assert sub["status"] == "active" and sub["paid_until"] == until
    assert not sub["autopay"] and sub["payment_method_id"] is None


def test_billing_autopay_enable_requires_binding():
    s, acc, yk, b, notes, t = _billing_env()
    try:
        run(b.set_autopay(acc, True))
        assert False, "ожидали BillingError"
    except BillingError as e:
        assert e.code == "need_bind"


def test_billing_renewal_at_expiry_seamless():
    s, acc, yk, b, notes, t = _billing_env()
    res = run(b.start_checkout(acc, "pay", autopay=True))
    yk.complete_payment(res["paymentId"], ok=True, saved=True)
    run(b.check_pending(acc))
    old_until = s.subscription(acc)["paid_until"]
    t["now"] = old_until + 5                                # момент истечения
    run(b.tick())
    sub = s.subscription(acc)
    assert sub["status"] == "active"
    assert sub["paid_until"] == add_month(old_until)        # бесшовно от даты истечения
    kind, args = yk.created[-1]
    assert args["pm"] == "pm_saved_1" and args["idem"].startswith("renew:")
    assert s.traffic(acc)["used_bytes"] == 0
    assert any("продлена" in n[1] for n in notes)


def test_billing_renewal_failure_retries_then_stops():
    s, acc, yk, b, notes, t = _billing_env(max_attempts=2)
    res = run(b.start_checkout(acc, "pay", autopay=True))
    yk.complete_payment(res["paymentId"], ok=True, saved=True)
    run(b.check_pending(acc))
    yk.recurring_outcome = "canceled"
    t["now"] = s.subscription(acc)["paid_until"] + 5
    run(b.tick())
    sub = s.subscription(acc)
    n_payments = len([c for c in yk.created if c[0] == "payment"])
    assert sub["status"] == "inactive" and sub["renew_attempts"] == 1
    assert sub["renew_retry_at"] == int(t["now"] + 4 * 3600)
    assert any("Не удалось продлить" in n[1] for n in notes)
    run(b.tick())                                           # до retry_at — без новых списаний
    assert len([c for c in yk.created if c[0] == "payment"]) == n_payments
    t["now"] = sub["renew_retry_at"] + 1                    # пришло время ретрая
    run(b.tick())
    sub = s.subscription(acc)
    assert sub["renew_attempts"] == 2 and sub["renew_retry_at"] == 0   # лимит исчерпан
    assert any("Автопродление остановлено" in n[1] for n in notes)
    run(b.tick())                                           # больше не пробуем
    assert s.subscription(acc)["renew_attempts"] == 2


def test_billing_renewal_permission_revoked_drops_binding():
    s, acc, yk, b, notes, t = _billing_env()
    res = run(b.start_checkout(acc, "pay", autopay=True))
    yk.complete_payment(res["paymentId"], ok=True, saved=True)
    run(b.check_pending(acc))
    yk.recurring_outcome = "canceled"
    yk.cancel_reason = "permission_revoked"
    t["now"] = s.subscription(acc)["paid_until"] + 5
    run(b.tick())
    sub = s.subscription(acc)
    assert sub["status"] == "inactive" and not sub["autopay"]
    assert sub["payment_method_id"] is None                 # привязку удалили у себя (docs)
    assert any("отозвано" in (n[2] or "") for n in notes)


def test_billing_expiry_without_autopay_deactivates():
    s, acc, yk, b, notes, t = _billing_env()
    res = run(b.start_checkout(acc, "pay", autopay=False))
    yk.complete_payment(res["paymentId"], ok=True, saved=False)
    run(b.check_pending(acc))
    t["now"] = s.subscription(acc)["paid_until"] + 5
    run(b.tick())
    sub = s.subscription(acc)
    assert sub["status"] == "inactive"
    assert any("истекла" in n[1] for n in notes)


def test_billing_webhook_applies_pending_by_refetch():
    s, acc, yk, b, notes, t = _billing_env()
    res = run(b.start_checkout(acc, "pay", autopay=True))
    yk.complete_payment(res["paymentId"], ok=True, saved=True)
    # телу вебхука не доверяем — биллинг перечитывает платёж из API по id
    run(b.webhook("payment.succeeded", {"id": res["paymentId"], "status": "хакер"}))
    assert s.subscription(acc)["status"] == "active"
    # чужой/неизвестный объект — молча игнорируется
    yk.payments["pay_evil"] = {"id": "pay_evil", "status": "succeeded",
                               "metadata": {"account_id": "acc_нет_такого"}}
    run(b.webhook("payment.succeeded", {"id": "pay_evil"}))


def test_billing_traffic_topup_payment_adds_timeless_extra_traffic():
    s, acc, yk, b, notes, t = _billing_env()
    paid_until = int(t["now"] + 10 * 86400)
    run(s.set_subscription(acc, {"status": "active", "paid_until": paid_until,
                                 "renew_at": "2027-01-25"}))
    run(s.add_traffic(acc, 1234, rule_id="r1"))

    res = run(b.start_traffic_topup(acc))
    assert res["kind"] == "payment"
    assert res["purpose"] == "traffic_topup"
    assert res["topupBytes"] == config.TOPUP_BYTES
    created = yk.created[-1][1]
    assert created["amount"] == config.TOPUP_PRICE_RUB
    assert created["save"] is False
    assert created["embedded"] is True
    assert created["metadata"]["kind"] == "traffic_topup"
    assert created["metadata"]["topup_bytes"] == str(config.TOPUP_BYTES)

    yk.complete_payment(res["paymentId"], ok=True, saved=False)
    assert run(b.check_pending(acc)) == "succeeded"
    tr = s.traffic(acc)
    assert tr["used_bytes"] == 1234
    assert tr["per_rule"] == {"r1": 1234}
    assert tr["topup_bytes"] == config.TOPUP_BYTES
    assert s.subscription(acc)["paid_until"] == paid_until
    assert any(n[1] == "Добавочный трафик начислен" for n in notes)


def test_billing_traffic_topup_reuses_pending_and_blocks_other_checkout():
    s, acc, yk, b, notes, t = _billing_env()
    run(s.set_subscription(acc, {"status": "active",
                                 "paid_until": int(t["now"] + 10 * 86400)}))
    first = run(b.start_traffic_topup(acc))
    second = run(b.start_traffic_topup(acc))
    assert second["paymentId"] == first["paymentId"]
    assert second["reused"] is True
    try:
        run(b.start_checkout(acc, "pay", autopay=False))
        assert False, "ожидался BillingError"
    except BillingError as e:
        assert e.code == "payment_pending"


def test_billing_add_month_clamps():
    import datetime as _dt
    jan31 = _dt.datetime(2026, 1, 31, tzinfo=_dt.timezone.utc).timestamp()
    feb = _dt.datetime.fromtimestamp(add_month(jan31), _dt.timezone.utc)
    assert (feb.month, feb.day) == (2, 28)
    dec15 = _dt.datetime(2026, 12, 15, tzinfo=_dt.timezone.utc).timestamp()
    jan = _dt.datetime.fromtimestamp(add_month(dec15), _dt.timezone.utc)
    assert (jan.year, jan.month, jan.day) == (2027, 1, 15)


def test_api_pay_endpoints_and_view():
    from fastapi.testclient import TestClient
    from control.api import create_app, set_billing
    from control import security
    s = _fresh_store()
    acc = run(s.get_or_create_account("max", 778, "79001112233"))["id"]
    yk = FakeYK()
    b = Billing(s, yk, price_rub=299, trial_days=7, return_url="https://x/r")
    set_billing(b)
    try:
        c = TestClient(create_app(s))
        tok = security.make_session(acc)
        h = {"Authorization": f"Bearer {tok}"}
        _accept_legal(c, h)
        # subscription view несёт поля биллинга
        v = c.get("/api/subscription", headers=h).json()
        assert v["price"] == 299 and v["trialUsed"] is False and v["payEnabled"] is True
        # старой демо-покупки больше нет
        assert c.post("/api/subscription/buy", headers=h).status_code in (404, 405)
        # checkout триала → confirmationUrl; вебхук ЮKassa публичный (без сессии)
        r = c.post("/api/pay/checkout", json={"mode": "trial", "method": "bank_card"}, headers=h).json()
        assert r["kind"] == "binding" and r["confirmationUrl"]
        yk.complete_binding(r["paymentMethodId"])
        assert c.post("/api/pay/webhook",
                      json={"event": "payment_method.active", "object": {"id": r["paymentMethodId"]}}).json()["ok"]
        st = c.get("/api/pay/status", headers=h).json()
        assert st["subscription"]["status"] == "active" and st["subscription"]["trial"] is True
        # пакет трафика оплачивается тем же виджетом, но начисляет add-on, не меняя подписку
        top = c.post("/api/traffic/topup", headers=h).json()
        assert top["kind"] == "payment" and top["purpose"] == "traffic_topup"
        assert top["topupBytes"] == config.TOPUP_BYTES
        yk.complete_payment(top["paymentId"])
        st2 = c.get("/api/pay/status", headers=h).json()
        assert st2["state"] == "succeeded"
        assert st2["traffic"]["topupBytes"] == config.TOPUP_BYTES
        assert s.traffic(acc)["topup_bytes"] == config.TOPUP_BYTES
        # отключение автоплатежа у триала → аннулирование
        out = c.post("/api/pay/autopay", json={"enabled": False}, headers=h).json()
        assert out["annulled"] is True and out["subscription"]["status"] == "inactive"
        # Отмена без активного pending идемпотентна и возвращает актуальную подписку.
        canceled = c.post("/api/pay/cancel", headers=h)
        assert canceled.status_code == 200 and canceled.json()["ok"] is True
        assert canceled.json()["subscription"]["status"] == "inactive"
    finally:
        set_billing(None)


def test_billing_tick_migrates_legacy_active_subscription():
    """Активная подписка до-биллинговой эпохи (renew_at есть, paid_until нет):
    tick НЕ гасит её, а выставляет paid_until по renew_at."""
    s, acc, yk, b, notes, t = _billing_env()
    run(s.set_subscription(acc, {"status": "active", "renew_at": "2026-07-14", "paid_until": 0}))
    run(b.tick())
    sub = s.subscription(acc)
    assert sub["status"] == "active"
    import datetime as _dt
    assert sub["paid_until"] == int(_dt.datetime(2026, 7, 14, tzinfo=_dt.timezone.utc).timestamp())
    assert notes == []                                       # никаких «подписка истекла»


def test_billing_yk_errors_become_user_messages():
    """403 recurring от ЮKassa (магазин без автоплатежей) → человеческий BillingError,
    а не 500; 404 по pending-объекту сбрасывает оформление, 5xx — ждём дальше."""
    from control.yookassa import YooKassaError
    s, acc, yk, b, notes, t = _billing_env()

    async def forbid(**kw):
        raise YooKassaError(403, "forbidden",
                            "This store can't make recurring payments. Contact your manager")
    yk.create_payment_method = forbid
    yk.create_payment = forbid
    for mode, kw in (("trial", {}), ("pay", {"autopay": True})):
        try:
            run(b.start_checkout(acc, mode, **kw))
            assert False, "ожидали BillingError"
        except BillingError as e:
            assert e.code == "recurring_unavailable" and "автоплатеж" in e.message.lower()
    # pending: 404 → failed и сброс; 5xx → всё ещё pending
    run(s.set_subscription(acc, {"pending": {"kind": "purchase", "id": "gone", "autopay": True,
                                             "created_at": int(t["now"])}}))
    async def missing(pid):
        raise YooKassaError(404, "not_found", "no such payment")
    yk.get_payment = missing
    assert run(b.check_pending(acc)) == "failed"
    assert s.subscription(acc)["pending"] is None
    run(s.set_subscription(acc, {"pending": {"kind": "purchase", "id": "p1", "autopay": True,
                                             "created_at": int(t["now"])}}))
    async def flaky(pid):
        raise YooKassaError(500, "internal_server_error", "try later")
    yk.get_payment = flaky
    assert run(b.check_pending(acc)) == "pending"
    assert s.subscription(acc)["pending"] is not None


def test_billing_unbind_when_inactive_clears_method():
    """Отвязка способа оплаты доступна и при НЕАКТИВНОЙ подписке (например, в ретраях
    неудачного продления) — требование ЮKassa: пользователь отвязывает карту сам."""
    s, acc, yk, b, notes, t = _billing_env()
    run(s.set_subscription(acc, {"status": "inactive", "autopay": True,
                                 "payment_method_id": "pm_x", "payment_method_title": "Карта •1234",
                                 "renew_attempts": 2, "renew_retry_at": int(t["now"] + 3600)}))
    out = run(b.set_autopay(acc, False))
    assert out["annulled"] is False
    sub = s.subscription(acc)
    assert sub["payment_method_id"] is None and sub["payment_method_title"] is None
    assert not sub["autopay"] and sub["status"] == "inactive"
    run(b.tick())                                            # ретраи списаний больше не идут
    assert not [c for c in yk.created if c[0] == "payment"]


# ---------------- приветствие в личке с ботом ----------------
class _NullStorage:
    async def append_raw(self, *a, **k): pass
    async def append_content(self, *a, **k): pass


def test_tg_dm_welcome_on_any_private_message():
    """Любое сообщение в личке TG → dm_welcome; группа/канал и сообщения ботов — нет;
    /claim уходит в ownership (у него свой ответ), /start получает приветствие."""
    from telegram_sync.updates import UpdateRouter as TgRouter
    got, claimed = [], []

    class _Own:
        async def handle_command(self, norm): claimed.append(norm.get("text"))
        async def on_chat_message(self, norm): pass

    async def welcome(norm): got.append((norm.get("chat") or {}).get("id"))
    r = TgRouter(None, _NullStorage(), download_media=False, max_download_bytes=0,
                 media_debounce=0.1, mirror=False, ownership=_Own(), dm_welcome=welcome)

    def _msg(chat_type, text, chat_id=5, is_bot=False):
        return {"chat": {"id": chat_id, "type": chat_type}, "message_id": 1,
                "from": {"id": 9, "is_bot": is_bot}, "text": text, "media": []}
    run(r._handle_message(_msg("private", "привет")))
    run(r._handle_message(_msg("private", "/start")))
    run(r._handle_message(_msg("private", "")))              # медиа/пустой текст — тоже
    assert got == [5, 5, 5]
    run(r._handle_message(_msg("group", "привет", chat_id=-1)))     # группы — молчим
    run(r._handle_message(_msg("channel", "пост", chat_id=-2)))
    run(r._handle_message(_msg("private", "эхо", is_bot=True)))     # боты — молчим
    assert got == [5, 5, 5]
    run(r._handle_message(_msg("private", "/claim")))        # /claim → старый ответ с кодом
    assert claimed == ["/claim"] and got == [5, 5, 5]


def test_max_dm_welcome_on_any_dialog_message():
    """Любое сообщение в диалоге MAX → dm_welcome; групповой чат и свои сообщения — нет;
    диплинк ?start=... (bot_started) тоже приветствует; /claim уходит в ownership;
    сбой приветствия не роняет обработку."""
    from max_sync.updates import UpdateRouter as MaxRouter
    got, claimed = [], []

    class _Own:
        async def handle_command(self, norm): claimed.append(norm.get("text"))
        async def on_chat_message(self, norm): pass

    async def welcome(norm): got.append(norm.get("sender_id"))
    r = MaxRouter(None, _NullStorage(), download_media=False, max_download_bytes=0,
                  mirror=False, bot_id=1000, ownership=_Own(), dm_welcome=welcome)

    def _msg(chat_type, text, sender=7):
        return {"chat_type": chat_type, "chat_id": 42, "mid": "m1", "sender_id": sender,
                "text": text, "media": []}
    run(r._handle_message(_msg("dialog", "привет")))
    run(r._handle_message(_msg("dialog", "/start")))
    assert got == [7, 7]
    run(r._handle_event({"update_type": "bot_started", "chat_id": 8,
                         "user": {"user_id": 8}, "payload": "web"}))
    assert got == [7, 7, 8]
    run(r._handle_message(_msg("chat", "в группе")))          # группа — молчим
    run(r._handle_message(_msg("dialog", "своё", sender=1000)))     # сам бот — молчим
    assert got == [7, 7, 8]
    run(r._handle_message(_msg("dialog", "/claim")))
    assert claimed == ["/claim"] and got == [7, 7, 8]

    async def broken(norm): raise RuntimeError("welcome down")
    r.dm_welcome = broken
    run(r._handle_message(_msg("dialog", "не падаем")))       # исключение проглочено
    run(r._handle_event({"update_type": "bot_started", "chat_id": 9,
                         "user": {"user_id": 9}, "payload": "web"}))


def test_stage1_pollers_pass_dm_welcome_to_router():
    """Регрессия провала деплоя приветствия в MAX: Stage1Poller обязан ПРОКИНУТЬ
    dm_welcome в UpdateRouter (параметр в сигнатуре без передачи → welcome молча
    не работает, а /start отвечает старым HELP_TEXT)."""
    from max_sync.updates import Stage1Poller as MaxPoller
    from telegram_sync.updates import Stage1Poller as TgPoller

    async def welcome(norm):  # pragma: no cover — важна только идентичность
        pass
    async def contact(user_id, phone):  # pragma: no cover — важна только идентичность
        pass

    mp = MaxPoller(None, None, update_types=[], timeout=1, limit=1,
                   download_media=False, max_download_bytes=0,
                   dm_welcome=welcome)
    assert mp.router.dm_welcome is welcome
    tp = TgPoller(None, None, allowed_updates=[], timeout=1, limit=1,
                  download_media=False, max_download_bytes=0, media_debounce=0.1,
                  dm_welcome=welcome, contact_cb=contact)
    assert tp.router.dm_welcome is welcome
    assert tp.router.contact_cb is contact


def test_dm_contact_message_deleted_and_no_welcome():
    """Сообщение с контактом в личке (шеринг номера при входе) немедленно удаляется
    ботом из чата и НЕ получает приветствия — в обоих мессенджерах."""
    from telegram_sync.updates import UpdateRouter as TgRouter
    from max_sync.updates import UpdateRouter as MaxRouter
    got, deleted, confirmed = [], [], []

    class _TgCli:
        async def delete_message(self, chat_id, mid): deleted.append(("tg", chat_id, mid))

    class _MaxCli:
        async def delete_message(self, mid): deleted.append(("max", mid))

    async def welcome(norm): got.append(norm)
    async def contact(user_id, phone): confirmed.append((str(user_id), phone))

    r = TgRouter(_TgCli(), _NullStorage(), download_media=False, max_download_bytes=0,
                 media_debounce=0.1, mirror=False, dm_welcome=welcome, contact_cb=contact)
    run(r._handle_message({"chat": {"id": 5, "type": "private"}, "message_id": 42,
                           "from": {"id": 9}, "text": None, "media": [],
                           "structured": {"contact": {"user_id": 9,
                                                        "phone_number": "+79990000009"}}}))
    assert deleted == [("tg", 5, 42)] and got == []
    assert confirmed == [("9", "+79990000009")]

    # Пересланный/чужой контакт удаляем, но никогда не используем как подтверждение входа.
    run(r._handle_message({"chat": {"id": 5, "type": "private"}, "message_id": 43,
                           "from": {"id": 9}, "text": None, "media": [],
                           "structured": {"contact": {"user_id": 10,
                                                        "phone_number": "+79000000010"}}}))
    assert deleted[-1] == ("tg", 5, 43) and confirmed == [("9", "+79990000009")]

    class _MaxStorage:
        def __init__(self): self.content = []
        async def append_content(self, item): self.content.append(item)

    max_store = _MaxStorage()
    m = MaxRouter(_MaxCli(), max_store, download_media=False, max_download_bytes=0,
                  mirror=False, bot_id=1000, dm_welcome=welcome)
    run(m._handle_message({"chat_type": "dialog", "chat_id": 42, "mid": "m77", "sender_id": 7,
                           "text": None, "media": [],
                           "attachments": [{"type": "contact", "vcf_info": "BEGIN:VCARD",
                                            "raw": {"payload": {"vcf_info": "BEGIN:VCARD"}}}]}))
    assert deleted == [("tg", 5, 42), ("tg", 5, 43), ("max", "m77")] and got == []
    assert max_store.content == []                             # PII-контакт не логируем
