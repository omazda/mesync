"""Тесты фундамента админ-панели (этап 4.1): вход по паролю, сессия, settings-store,
аудит, приостановка приёма платежей.

Запуск:  .venv/bin/python -m pytest tests/test_admin.py -q
"""
import asyncio
import hashlib
import json
import os
import re
import sys
import tempfile
import time
from pathlib import Path

_TMP = Path(tempfile.mkdtemp(prefix="admin_test_"))
os.environ.setdefault("MESYNC_DATA_DIR", str(_TMP / "control"))
os.environ.setdefault("MESYNC_SESSION_SECRET", "test-secret")
os.environ.setdefault("MESYNC_AUTH_INSECURE", "1")     # cookie без Secure → ходит по HTTP в тестах
os.environ.setdefault("MESYNC_ADMIN_PASSWORD", "s3cret-pw")
# Значения токенов должны совпадать с тем, что ждут другие тест-файлы: config читает env
# при ПЕРВОМ импорте (этот файл алфавитно первый), и подпись контакта в test_control
# проверяется именно этим MAX_BOT_TOKEN. Иначе рассинхрон ломает чужой тест.
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "111:TESTTOKEN")
os.environ.setdefault("MAX_BOT_TOKEN", "maxtoken")
os.environ.setdefault("MESYNC_TG_BOT_URL", "https://t.me/test_mesync_bot")
os.environ.setdefault("MESYNC_MAX_BOT_URL", "https://max.ru/test_mesync_bot")

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from control import config  # noqa: E402
from control.billing import Billing, BillingError  # noqa: E402
from control.settings import Settings  # noqa: E402
from control.store import ControlStore  # noqa: E402

run = asyncio.run
PW = "s3cret-pw"


def _client():
    from fastapi.testclient import TestClient
    from control.api import create_app, set_settings
    s = ControlStore(_TMP / f"api_{time.time_ns()}.json")
    set_settings(Settings(s))
    return TestClient(create_app(s)), s


# ---------------- вход / сессия ----------------
def test_login_and_session_lifecycle():
    c, _ = _client()
    assert c.get("/api/admin/me").status_code == 401           # без cookie — нельзя
    assert c.post("/api/admin/login", json={"password": "nope"}).status_code == 401
    r = c.post("/api/admin/login", json={"password": PW})
    assert r.status_code == 200 and r.json()["ok"] is True
    assert c.get("/api/admin/me").status_code == 200           # cookie сессии выдан
    c.post("/api/admin/logout")
    assert c.get("/api/admin/me").status_code == 401           # cookie снят


def test_admin_cookie_secure_follows_external_request_scheme():
    from control import api as api_mod

    api_mod._admin_login_fails.clear()
    c, _ = _client()

    local = c.post("/api/admin/login", json={"password": PW})
    local_attrs = {part.strip().lower() for part in local.headers["set-cookie"].split(";")[1:]}
    assert "secure" not in local_attrs
    assert "httponly" in local_attrs and "samesite=strict" in local_attrs

    proxied = c.post("/api/admin/login", json={"password": PW},
                     headers={"x-forwarded-proto": "https"})
    proxied_attrs = {part.strip().lower() for part in proxied.headers["set-cookie"].split(";")[1:]}
    assert "secure" in proxied_attrs
    assert "httponly" in proxied_attrs and "samesite=strict" in proxied_attrs


def test_login_uniform_when_disabled():
    # Выключенная панель отвечает тем же 401 bad_password, что и неверный пароль —
    # не раскрываем анониму, настроена ли панель (info-disclosure из ревью).
    from control import api as api_mod
    old = config.ADMIN_PASSWORD
    config.ADMIN_PASSWORD = ""
    api_mod._admin_login_fails.clear()
    try:
        c, _ = _client()
        r = c.post("/api/admin/login", json={"password": "x"})
        assert r.status_code == 401 and r.json()["detail"]["code"] == "bad_password"
        assert c.get("/api/admin/me").status_code == 401
    finally:
        config.ADMIN_PASSWORD = old
        api_mod._admin_login_fails.clear()


def test_client_ip_uses_rightmost_hop():
    # За единственным доверенным Caddy реальный клиент — ПОСЛЕДНИЙ хоп XFF (левые подделывает
    # клиент). Иначе троттлинг/аудит доверяли бы подделке.
    from control.api import _client_ip

    class _C:
        def __init__(self, host): self.host = host

    class _Req:
        def __init__(self, xff, host="9.9.9.9"):
            self.headers = {"x-forwarded-for": xff} if xff else {}
            self.client = _C(host)

    assert _client_ip(_Req("1.1.1.1, 2.2.2.2")) == "2.2.2.2"
    assert _client_ip(_Req(None, "5.5.5.5")) == "5.5.5.5"


def test_login_throttle_blocks_after_max_fails():
    from control import api as api_mod
    api_mod._admin_login_fails.clear()
    c, _ = _client()
    try:
        for _ in range(api_mod._ADMIN_MAX_FAILS):
            assert c.post("/api/admin/login", json={"password": "wrong"}).status_code == 401
        assert c.post("/api/admin/login", json={"password": "wrong"}).status_code == 429
        assert c.post("/api/admin/login", json={"password": PW}).status_code == 429  # лимит бьёт и верный
    finally:
        api_mod._admin_login_fails.clear()


def test_admin_endpoints_require_auth():
    c, _ = _client()
    for path in ("/api/admin/settings", "/api/admin/audit", "/api/admin/me"):
        assert c.get(path).status_code == 401
    assert c.post("/api/admin/backup").status_code == 401
    assert c.post("/api/admin/backup/validate", content=b"{}").status_code == 401
    assert c.post("/api/admin/backup/restore", content=b"{}").status_code == 401


def test_admin_database_backup_download_is_complete_and_audited():
    c, s = _client()
    c.post("/api/admin/login", json={"password": PW})
    account = run(s.get_or_create_account("max", 701, "79990000701"))

    response = c.post("/api/admin/backup")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")
    assert response.headers["cache-control"] == "no-store, no-cache, must-revalidate"
    assert response.headers["pragma"] == "no-cache"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert re.fullmatch(
        r'attachment; filename="mesync-control-backup-\d{8}-\d{6}Z\.json"',
        response.headers["content-disposition"],
    )
    assert response.headers["x-mesync-backup-sha256"] == hashlib.sha256(
        response.content).hexdigest()
    assert response.content.endswith(b"\n")
    assert PW.encode() not in response.content

    payload = json.loads(response.content)
    assert set(payload) == set(s._data)
    assert payload["accounts"][account["id"]]["phone"] == "79990000701"
    assert any(rec.get("action") == "database:backup"
               for rec in payload["admin_audit"].values())
    assert s.audit_list()[0]["action"] == "database:backup"
    assert s.audit_list()[0]["details"] == {"backend": "json"}


def test_admin_database_backup_refuses_unhealthy_store():
    c, s = _client()
    c.post("/api/admin/login", json={"password": PW})

    async def unhealthy():
        return False

    s.healthcheck = unhealthy
    response = c.post("/api/admin/backup")
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "backup_unavailable"
    assert all(rec.get("action") != "database:backup" for rec in s.audit_list())


def test_admin_database_restore_validates_stages_and_requests_restart(tmp_path):
    from control.api import set_restart_handler

    c, live = _client()
    c.post("/api/admin/login", json={"password": PW})
    old = run(live.get_or_create_account("max", 801, "79990000801"))

    source = ControlStore(tmp_path / "restore-source.json")
    new = run(source.get_or_create_account("tg", 802, "79990000802"))
    raw = run(source.export_backup())

    invalid = c.post("/api/admin/backup/validate", content=b"{broken",
                     headers={"Content-Type": "application/json"})
    assert invalid.status_code == 400
    assert invalid.json()["detail"]["code"] == "invalid_backup"

    checked = c.post("/api/admin/backup/validate", content=raw,
                     headers={"Content-Type": "application/json"})
    assert checked.status_code == 200
    summary = checked.json()["summary"]
    assert summary["counts"]["accounts"] == 1
    assert summary["tables"] == 18

    unconfirmed = c.post("/api/admin/backup/restore", content=raw)
    assert unconfirmed.status_code == 400
    assert unconfirmed.json()["detail"]["code"] == "restore_confirmation_required"

    restarts = []
    set_restart_handler(lambda: restarts.append(True))
    try:
        restored = c.post("/api/admin/backup/restore", content=raw, headers={
            "Content-Type": "application/json",
            "X-MeSync-Backup-SHA256": summary["sha256"],
            "X-MeSync-Restore-Confirm": "restore",
        })
    finally:
        set_restart_handler(None)

    assert restored.status_code == 202
    assert restored.json()["restartScheduled"] is True
    assert restored.json()["previousBackup"] == live.restore_previous_path.name
    assert restarts == [True]
    assert live.account(old["id"]) is not None
    assert live.account(new["id"]) is None
    assert live.restore_pending_path.exists()

    # Имитируем следующий старт процесса: только теперь снимок становится активным.
    after_restart = ControlStore(live.path)
    run(after_restart.start())
    assert after_restart.account(old["id"]) is None
    assert after_restart.account(new["id"])["phone"] == "79990000802"
    assert any(rec.get("action") == "database:restore"
               for rec in after_restart.table("admin_audit").values())


# ---------------- settings-store + аудит ----------------
def test_settings_get_put_and_audit():
    c, _ = _client()
    c.post("/api/admin/login", json={"password": PW})
    assert c.get("/api/admin/settings").json()["settings"]["payments_paused"] is False
    r = c.put("/api/admin/settings", json={"payments_paused": True})
    assert r.status_code == 200 and r.json()["settings"]["payments_paused"] is True
    assert c.get("/api/admin/settings").json()["settings"]["payments_paused"] is True   # персист
    aud = c.get("/api/admin/audit").json()["items"]
    assert aud and aud[0]["action"] == "settings"
    assert aud[0]["details"]["payments_paused"] == {"from": False, "to": True}


def test_settings_moderation_switches_and_audit():
    c, _ = _client()
    c.post("/api/admin/login", json={"password": PW})
    r = c.put("/api/admin/settings", json={
        "moderation_reports_enabled": False,
        "moderation_ai_enabled": False,
        "moderation_gate_mode": "off",
    })
    assert r.status_code == 200
    st = r.json()["settings"]
    assert st["moderation_reports_enabled"] is False
    assert st["moderation_ai_enabled"] is False
    assert st["moderation_gate_mode"] == "off"
    aud = c.get("/api/admin/audit").json()["items"]
    assert aud and aud[0]["action"] == "settings"
    assert aud[0]["details"]["moderation_ai_enabled"]["to"] is False


def test_settings_reject_unknown_key():
    c, _ = _client()
    c.post("/api/admin/login", json={"password": PW})
    assert c.put("/api/admin/settings", json={"unknown_flag": 1}).status_code == 400


def test_settings_put_is_atomic_on_bad_key():
    # Смешанный запрос (валидный + битый ключ) → 400 И валидная правка НЕ применилась.
    c, _ = _client()
    c.post("/api/admin/login", json={"password": PW})
    assert c.get("/api/admin/settings").json()["settings"]["payments_paused"] is False
    r = c.put("/api/admin/settings", json={"payments_paused": True, "typo_key": 1})
    assert r.status_code == 400
    assert c.get("/api/admin/settings").json()["settings"]["payments_paused"] is False


def test_login_and_logout_audited():
    from control import api as api_mod
    api_mod._admin_login_fails.clear()
    c, _ = _client()
    c.post("/api/admin/login", json={"password": PW})
    c.post("/api/admin/logout")
    c.post("/api/admin/login", json={"password": PW})   # заново, чтобы прочитать аудит
    actions = [i["action"] for i in c.get("/api/admin/audit").json()["items"]]
    assert "login" in actions and "logout" in actions
    api_mod._admin_login_fails.clear()


def test_settings_effective_value_over_default():
    s = ControlStore(_TMP / f"s_{time.time_ns()}.json")
    st = Settings(s)
    assert st.get("payments_paused") is False        # дефолт
    run(s.set_setting("payments_paused", True))
    assert st.get("payments_paused") is True          # оверрайд
    # битый оверрайд (неверный тип, но JSON-сериализуемый) → fail-safe дефолт
    run(s.set_setting("payments_paused", {"bad": 1}))
    assert st.get("payments_paused") is False


# ---------------- приостановка приёма платежей ----------------
class FakeYk:
    enabled = True

    def __init__(self):
        self.calls = []

    async def create_payment(self, *a, **k):
        self.calls.append("create_payment")
        return {"id": "p1", "status": "pending", "confirmation": {"confirmation_token": "t"}}

    async def create_payment_method(self, *a, **k):
        self.calls.append("create_payment_method")
        return {"id": "pm1", "confirmation": {"confirmation_url": "u"}}

    async def get_payment(self, *a, **k):
        self.calls.append("get_payment"); return {"status": "pending"}

    async def get_payment_method(self, *a, **k):
        self.calls.append("get_payment_method"); return {"status": "pending"}


def test_payments_pause_blocks_checkout_and_tick():
    async def scenario():
        s = ControlStore(_TMP / f"b_{time.time_ns()}.json")
        acc = (await s.get_or_create_account("max", 1, None))["id"]
        st = Settings(s)
        yk = FakeYk()
        b = Billing(s, yk, price_rub=299, trial_days=7, return_url="u",
                    paused_provider=lambda: st.get("payments_paused"))
        # не на паузе → оформление доходит до создания платежа
        await b.start_checkout(acc, "pay", autopay=False)
        assert "create_payment" in yk.calls
        # ставим на паузу
        await s.set_setting("payments_paused", True)
        yk.calls.clear()
        try:
            await b.start_checkout(acc, "pay", autopay=False)
            assert False, "ожидался BillingError 503"
        except BillingError as e:
            assert e.status == 503 and e.code == "payments_paused"
        assert yk.calls == []          # до ЮKassa не дошли
        await b.tick()
        assert yk.calls == []          # фоновый цикл на паузе ничего не списывает
    run(scenario())
