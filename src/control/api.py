"""FastAPI-приложение control-API mini-app.

Эндпоинты (префикс /api) повторяют контракт фронтенда (web/src/api/client.js):
  POST /api/auth/contact            — вход по подтверждённому номеру (подпись хоста)
  POST /api/auth/contact/diagnostic — временный журнал ошибки MAX requestContact
  POST /api/auth/otp/request        — запрос кода входа на другой номер
  POST /api/auth/otp/verify         — подтверждение кода входа
  GET  /api/account                 — текущий аккаунт
  POST /api/legal/accept            — явный акцепт текущих legal-редакций
  GET  /api/subscription            — статус тарифа
  POST /api/pay/checkout            — начать оформление (триал-привязка / оплата виджетом)
  GET  /api/pay/status              — дожать незавершённую оплату/привязку (поллинг)
  POST /api/pay/cancel              — сбросить незавершённое оформление
  POST /api/pay/autopay             — включить/отключить автоплатёж
  POST /api/pay/webhook             — уведомления ЮKassa (без авторизации, верификация
                                      повторным чтением объекта из API ЮKassa)
  POST /api/pay/activate            — активировать подписку кодом (месяц без привязки карты)
  POST /api/market/activate         — публичная активация кода Яндекс Маркета по телефону
  POST /api/yandex-market/notifications/{secret}/notification — API-уведомления Маркета
  POST /api/admin/activation-codes  — сгенерировать коды активации (X-Admin-Key)
  GET  /api/admin/activation-codes  — сводка по кодам: свободные/использованные (X-Admin-Key)
  POST /api/admin/backup            — скачать логический снимок control-store (admin-cookie)
  POST /api/admin/backup/validate   — проверить снимок перед восстановлением (admin-cookie)
  POST /api/admin/backup/restore    — подготовить снимок и перезапустить сервис (admin-cookie)
  GET  /api/sources                 — список источников (поверх ownership)
  POST /api/sources/code            — выдать код привязки нового источника
  GET  /api/sources/pending         — статус текущей привязки (поллинг)
  GET  /api/sources/{id}            — детальный источник
  GET  /api/sources/{id}/avatar     — фото чата/канала (узкий токен в ?t=, версия в ?v=)
  DELETE /api/sources/{id}          — удалить источник (бот выйдет из чата)
  GET/POST/PATCH/DELETE /api/rules… — правила
  GET  /api/traffic                 — расход трафика
  POST /api/traffic/topup           — оплатить пакет добавочного трафика
  GET  /api/notifications           — история уведомлений
  POST /api/notifications/read      — отметить прочитанными

Отправка кодов/уведомлений в мессенджеры и фактическая привязка/выход выполняются
ботами; api опирается на общий ControlStore и ownership-файлы. Оркестратор
(run_app.py) внедряет хук доставки (set_notifier) и хук выхода из чата.
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
import ipaddress
import secrets
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional
from urllib.parse import urlencode

from fastapi import Cookie, Depends, FastAPI, Header, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from . import avatars as avatars_mod, config, rules as rules_mod, security, sources as sources_mod, tariffs
from .public_config import public_config_script, render_public_html
from .rules import RuleError
from .source_ids import make_source_id, parse_source_id
from .store import BACKUP_MAX_BYTES, ControlStore

log = logging.getLogger("control.api")


class RuntimeConfigStaticFiles(StaticFiles):
    """Render public deployment data only when an HTML file is requested."""

    async def get_response(self, path: str, scope: dict[str, Any]) -> Response:
        response = await super().get_response(path, scope)
        response_path = str(getattr(response, "path", ""))
        if scope.get("method") == "GET" and response_path.endswith(".html"):
            source = await asyncio.to_thread(
                Path(response_path).read_text, encoding="utf-8")
            return HTMLResponse(
                render_public_html(source),
                headers={"Cache-Control": "no-store"},
            )
        return response

# Белый список одноразовых UI-флагов аккаунта (POST /api/account/flags):
# клиент не может писать в аккаунт произвольные ключи.
ACCOUNT_UI_FLAGS = {"sources_intro_seen"}

# Хуки, внедряемые оркестратором (опциональны в standalone-режиме):
#   notifier(messenger, user_id, text) -> awaitable  — доставка OTP/сообщений в мессенджер
#   chat_leaver(messenger, chat_id) -> awaitable      — выход бота из чата при удалении источника
#   source_unbinder(messenger, chat_id) -> awaitable  — ПОЛНАЯ отвязка (удалить ownership + выйти)
_notifier: Optional[Callable[..., Any]] = None
_chat_leaver: Optional[Callable[..., Any]] = None
_source_unbinder: Optional[Callable[..., Any]] = None
# source_notifier(messenger, user_id, text) — лаконичное сообщение в чат с ботом + «Скрыть».
_source_notifier: Optional[Callable[..., Any]] = None
# avatar_fetcher(messenger, chat_id) -> (content_type, bytes)|None — фото чата/канала.
_avatar_fetcher: Optional[Callable[..., Any]] = None
# account_avatar_fetcher(messenger, user_id, profile) -> (content_type, bytes, version)|None.
_account_avatar_fetcher: Optional[Callable[..., Any]] = None
# chat_info_provider(messenger, chat_id) -> {title, icon_url, photo_id}|None — свежие
# название и идентификатор аватара чата/канала (MAX icon.url, Telegram small_file_unique_id).
_chat_info_provider: Optional[Callable[..., Any]] = None
# service_log (control.service_log.ServiceLog) — отчёты об ошибках в служебный TG-канал.
_service_log: Optional[Any] = None
# restart_handler() планирует штатную остановку полного run_app после staging restore.
_restart_handler: Optional[Callable[[], Any]] = None


def set_notifier(fn: Callable[..., Any] | None) -> None:
    global _notifier
    _notifier = fn


def set_chat_leaver(fn: Callable[..., Any] | None) -> None:
    global _chat_leaver
    _chat_leaver = fn


def set_source_unbinder(fn: Callable[..., Any] | None) -> None:
    global _source_unbinder
    _source_unbinder = fn


def set_source_notifier(fn: Callable[..., Any] | None) -> None:
    global _source_notifier
    _source_notifier = fn


def set_avatar_fetcher(fn: Callable[..., Any] | None) -> None:
    global _avatar_fetcher
    _avatar_fetcher = fn


def set_account_avatar_fetcher(fn: Callable[..., Any] | None) -> None:
    global _account_avatar_fetcher
    _account_avatar_fetcher = fn


def set_chat_info_provider(fn: Callable[..., Any] | None) -> None:
    global _chat_info_provider
    _chat_info_provider = fn


def set_service_log(sl: Any | None) -> None:
    global _service_log
    _service_log = sl


def set_restart_handler(fn: Callable[[], Any] | None) -> None:
    global _restart_handler
    _restart_handler = fn


async def notify_rule_hold_change(store: ControlStore, rule: dict[str, Any], *, held: bool) -> None:
    """Persist + DM notification for moderation hold/unhold.

    Best-effort: admin action must not fail if a messenger notification cannot be delivered.
    """
    acc_id = rule.get("account_id")
    if not acc_id:
        return
    number = rule.get("number")
    label = f"Правило №{number}" if number is not None else "Правило"
    if held:
        title = "Правило остановлено модерацией"
        subtitle = f"{label}: пересылка временно приостановлена."
        dm_text = f"🛡 {subtitle} Проверьте источник и дождитесь снятия ограничения."
    else:
        title = "Ограничение правила снято"
        subtitle = f"{label}: пересылка снова работает."
        dm_text = f"✅ {subtitle}"
    try:
        await store.add_notification(
            acc_id, type="rules", title=title, subtitle=subtitle,
            link={"screen": "rules", "ruleId": rule.get("id")})
    except Exception:  # noqa: BLE001
        log.warning("rule hold: notification store failed for %s", rule.get("id"),
                    exc_info=True)
    if _source_notifier is None:
        return
    for m, uid in store.identities_by_messenger(acc_id).items():
        try:
            await _source_notifier(m, uid, dm_text)
        except Exception:  # noqa: BLE001
            log.warning("rule hold: messenger notification failed for %s (%s)",
                        rule.get("id"), m, exc_info=True)


async def set_rule_moderation_hold(store: ControlStore, rule_id: str,
                                   held: bool) -> dict[str, Any] | None:
    before = store.rule(rule_id)
    if before is None:
        return None
    changed = bool(before.get("moderation_hold")) != held
    updated = await store.update_rule(rule_id, {"moderation_hold": held})
    if updated is not None and changed:
        await notify_rule_hold_change(store, updated, held=held)
    return updated


# billing (control.billing.Billing) — оплата подписки через ЮKassa (ставится в run_app).
_billing: Optional[Any] = None


def set_billing(b: Any | None) -> None:
    global _billing
    _billing = b


# activation (control.activation.Activation) — коды активации подписки (ставится в run_app).
_activation: Optional[Any] = None


def set_activation(a: Any | None) -> None:
    global _activation
    _activation = a


# Автоматическая выдача кодов цифровых заказов Яндекс Маркета (ставится в run_app).
_yandex_market: Optional[Any] = None


def set_yandex_market(handler: Any | None) -> None:
    global _yandex_market
    _yandex_market = handler


# reports (control.reports.Reports) — жалобы на пересланный контент (ставится в run_app).
_reports: Optional[Any] = None


def set_reports(r: Any | None) -> None:
    global _reports
    _reports = r


# settings (control.settings.Settings) — runtime-настройки админ-панели (ставится в run_app).
_settings: Optional[Any] = None


def set_settings(s: Any | None) -> None:
    global _settings
    _settings = s


# health (control.health.BotHealth) — живость ботов для ops-обзора (ставится в run_app).
_health: Optional[Any] = None


def set_health(h: Any | None) -> None:
    global _health
    _health = h


# broadcaster (control.broadcasts.Broadcaster) — воркер рассылок в личку (ставится в run_app).
_broadcaster: Optional[Any] = None


def set_broadcaster(b: Any | None) -> None:
    global _broadcaster
    _broadcaster = b


# Анти-брутфорс входа в панель: не более _ADMIN_MAX_FAILS неудач за окно на один IP.
_admin_login_fails: dict[str, list[float]] = {}
_ADMIN_MAX_FAILS = 10
_ADMIN_FAIL_WINDOW = 300
_ADMIN_FAIL_MAX_KEYS = 4096   # предел размера словаря (защита от накопления ключей)


def _client_ip(request: Request) -> str:
    """Реальный адрес клиента. За ЕДИНСТВЕННЫМ доверенным прокси (Caddy) это ПОСЛЕДНИЙ хоп
    X-Forwarded-For: Caddy дописывает реальный peer СПРАВА, а левые значения подделывает
    сам клиент. Брать левый нельзя — иначе троттлинг/аудит доверяют подделке. Нет XFF
    (прямое подключение) → адрес соединения."""
    xff = request.headers.get("x-forwarded-for")
    if xff:
        parts = [p.strip() for p in xff.split(",") if p.strip()]
        if parts:
            return parts[-1]
    return request.client.host if request.client else "?"


def _external_request_is_https(request: Request) -> bool:
    """Определить публичную схему для Secure-cookie за доверенным reverse proxy.

    Gateway всегда перезаписывает X-Forwarded-Proto внешней схемой. Для прямого локального
    запуска заголовка нет и используется реальная схема ASGI-запроса.
    """
    forwarded = request.headers.get("x-forwarded-proto")
    if forwarded:
        values = [value.strip().lower() for value in forwarded.split(",") if value.strip()]
        if values:
            return values[-1] == "https"
    return request.url.scheme.lower() == "https"


_YANDEX_MARKET_NETWORKS = tuple(ipaddress.ip_network(cidr) for cidr in (
    "5.45.207.0/25",
    "141.8.142.0/25",
    "5.255.253.0/25",
))


def _yandex_market_ip_allowed(request: Request) -> bool:
    """Проверить опубликованные Маркетом диапазоны отправителей API-уведомлений."""
    if not config.YANDEX_MARKET_ENFORCE_IP:
        return True
    try:
        address = ipaddress.ip_address(_client_ip(request))
    except ValueError:
        return False
    return any(address in network for network in _YANDEX_MARKET_NETWORKS)


def _yandex_market_response() -> dict[str, str]:
    return {
        "version": "1.0.0",
        "name": f"{config.BOT_NAME} Yandex Market digital delivery",
        "time": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }


def _admin_throttle_check(ip: str) -> None:
    now = time.time()
    # Ограничение роста: подчищаем протухшие/пустые ключи, если словарь разросся.
    if len(_admin_login_fails) > _ADMIN_FAIL_MAX_KEYS:
        for k in [k for k, v in _admin_login_fails.items()
                  if not v or now - v[-1] >= _ADMIN_FAIL_WINDOW]:
            _admin_login_fails.pop(k, None)
    fails = [t for t in _admin_login_fails.get(ip, ()) if now - t < _ADMIN_FAIL_WINDOW]
    if fails:
        _admin_login_fails[ip] = fails
    else:
        _admin_login_fails.pop(ip, None)   # не храним пустые ключи
    if len(fails) >= _ADMIN_MAX_FAILS:
        raise HTTPException(status_code=429, detail={
            "code": "too_many_attempts", "message": "Слишком много попыток. Попробуйте позже."})


def _admin_throttle_fail(ip: str) -> None:
    _admin_login_fails.setdefault(ip, []).append(time.time())


async def _read_backup_upload(request: Request) -> bytes:
    declared = request.headers.get("content-length")
    if declared:
        try:
            if int(declared) > BACKUP_MAX_BYTES:
                raise HTTPException(status_code=413, detail={
                    "code": "backup_too_large",
                    "message": "Файл резервной копии превышает допустимые 50 МБ.",
                })
        except ValueError:
            pass
    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > BACKUP_MAX_BYTES:
            raise HTTPException(status_code=413, detail={
                "code": "backup_too_large",
                "message": "Файл резервной копии превышает допустимые 50 МБ.",
            })
    if not body:
        raise HTTPException(status_code=400, detail={
            "code": "empty_backup", "message": "Выберите файл резервной копии."})
    return bytes(body)


def create_app(store: ControlStore | None = None) -> FastAPI:
    owns_store = store is None
    store = store or ControlStore()

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        # В полном run_app store уже запущен и start() идемпотентен. Standalone-ASGI
        # получает тот же PostgreSQL lifecycle без отдельной bootstrap-команды.
        await store.start()
        try:
            yield
        finally:
            if owns_store:
                await store.close()

    app = FastAPI(
        title=f"{config.BOT_NAME} control API", version="0.1.0", lifespan=lifespan)
    app.state.store = store
    app.add_middleware(
        CORSMiddleware, allow_origins=config.CORS_ORIGINS or ["*"],
        allow_credentials=False, allow_methods=["*"], allow_headers=["*"],
    )

    @app.exception_handler(Exception)
    async def unhandled_error(request, exc):
        # Заглушка для пользователя вместо сырого «Internal Server Error»: фронт покажет
        # человеческое сообщение из detail.message. Подробности — в журнал и в сервисный
        # TG-канал (fire-and-forget: HTTP-ответ отправку отчёта не ждёт).
        import html as _html
        from fastapi.responses import JSONResponse
        log.exception("Необработанная ошибка API: %s %s", request.method, request.url.path)
        if _service_log is not None:
            _service_log.submit(
                "Ошибка control-API",
                [f"Запрос: <code>{_html.escape(f'{request.method} {request.url.path}')}</code>"],
                error=exc)
        return JSONResponse(status_code=500, content={"detail": {
            "code": "internal",
            "message": "Что-то пошло не так. Попробуйте ещё раз чуть позже."}})

    async def current_account(authorization: str = Header(default="")) -> str:
        token = authorization[7:].strip() if authorization.lower().startswith("bearer ") else ""
        acc_id = security.decode_session(token) if token else None
        account = store.account(acc_id) if acc_id else None
        # Legacy-токены аккаунтов, созданных старым fallback без requestContact, больше не
        # являются авторизацией. Пользователь должен подтвердить номер либо войти по OTP.
        if not account or not _auth_phone(account.get("phone")):
            raise HTTPException(status_code=401, detail={"code": "unauthorized", "message": "Требуется вход"})
        return acc_id

    Acc = Depends(current_account)

    def _legal_is_current(account: dict[str, Any] | None) -> bool:
        legal = (account or {}).get("legal_acceptance")
        if not isinstance(legal, dict):
            return False
        return (legal.get("terms_version") == config.LEGAL_TERMS_VERSION
                and legal.get("privacy_version") == config.LEGAL_PRIVACY_VERSION)

    def _require_legal(acc_id: str) -> None:
        if _legal_is_current(store.account(acc_id)):
            return
        raise HTTPException(status_code=428, detail={
            "code": "legal_required",
            "message": "Примите актуальные условия и политику конфиденциальности, чтобы продолжить."})

    # Публичная форма Яндекс Маркета не выдаёт сессию и не принимает неподтверждённый
    # номер как новую идентичность. Код — bearer-secret, а телефон лишь выбирает уже
    # существующий аккаунт. Два лимита закрывают перебор как одного номера, так и
    # множества номеров с одного адреса; состояние локально экземпляру приложения.
    market_activation_attempts: dict[str, list[float]] = {}
    market_activation_window = 600
    market_activation_max_keys = 4096

    def _market_phone(raw: Any) -> str | None:
        digits = "".join(ch for ch in str(raw or "") if ch.isdigit())
        if len(digits) == 10:
            digits = "7" + digits
        elif len(digits) == 11 and digits.startswith("8"):
            digits = "7" + digits[1:]
        return digits if 11 <= len(digits) <= 15 else None

    def _market_activation_attempt(key: str, limit: int) -> None:
        now = time.time()
        if len(market_activation_attempts) > market_activation_max_keys:
            for old_key in [k for k, values in market_activation_attempts.items()
                            if not values or now - values[-1] >= market_activation_window]:
                market_activation_attempts.pop(old_key, None)
            while len(market_activation_attempts) > market_activation_max_keys:
                market_activation_attempts.pop(next(iter(market_activation_attempts)))
        attempts = [ts for ts in market_activation_attempts.get(key, ())
                    if now - ts < market_activation_window]
        if len(attempts) >= limit:
            market_activation_attempts[key] = attempts
            raise HTTPException(status_code=429, detail={
                "code": "too_many_attempts",
                "message": "Слишком много попыток. Попробуйте снова через 10 минут."})
        market_activation_attempts[key] = [*attempts, now]

    async def current_admin(mesync_admin: str = Cookie(default="")) -> bool:
        # Браузерная панель: доступ по cookie-сессии администратора (вход по паролю).
        if not config.ADMIN_PASSWORD or not security.decode_admin_session(mesync_admin):
            raise HTTPException(status_code=401, detail={
                "code": "unauthorized", "message": "Требуется вход администратора."})
        return True

    AdminAuth = Depends(current_admin)

    def _authenticated_launch(body: dict[str, Any]) -> tuple[str, Any, dict[str, Any]]:
        """Проверить подписанный запуск mini-app и вернуть messenger/user id."""
        raw_messenger = str(body.get("messenger") or "").strip().lower()
        if raw_messenger in ("tg", "telegram"):
            messenger = "tg"
        elif raw_messenger == "max":
            messenger = "max"
        else:
            raise HTTPException(status_code=400, detail={
                "code": "bad_messenger", "message": "Не удалось определить мессенджер."})
        validated = security.authenticate(messenger, str(body.get("initData") or ""))
        if validated is None:
            raise HTTPException(status_code=400, detail={
                "code": "bad_signature",
                "message": "Не удалось подтвердить данные запуска. Перезапустите приложение из бота и попробуйте снова."})
        user = validated.get("user") if isinstance(validated.get("user"), dict) else {}
        user_id = user.get("id") or body.get("userId")
        if user_id is None and config.AUTH_INSECURE:
            user_id = "dev"
        if user_id is None:
            raise HTTPException(status_code=400, detail={
                "code": "no_user", "message": "Не удалось определить пользователя. Откройте приложение из бота."})
        return messenger, user_id, user

    def _authenticated_identity(body: dict[str, Any]) -> tuple[str, Any]:
        messenger, user_id, _user = _authenticated_launch(body)
        return messenger, user_id

    def _auth_phone(raw: Any) -> str | None:
        digits = "".join(ch for ch in str(raw or "") if ch.isdigit())
        return digits if 11 <= len(digits) <= 15 else None

    def _diagnostic_token(raw: Any, default: str, limit: int) -> str:
        """Однострочное ASCII-значение для журнала без возможности log injection."""
        value = str(raw or "").strip()
        safe = "".join(
            ch if ch.isascii() and (ch.isalnum() or ch in "._:-") else "_"
            for ch in value)
        return safe[:limit] or default

    # ----------------------- AUTH -----------------------
    @app.post("/api/auth/contact/diagnostic")
    async def auth_contact_diagnostic(body: dict[str, Any]) -> dict[str, bool]:
        """Временная диагностика отказов MAX Bridge без телефона и contact payload."""
        messenger, _user_id = _authenticated_identity(body)
        if messenger != "max":
            raise HTTPException(status_code=400, detail={
                "code": "max_only", "message": "Диагностика доступна только в MAX."})
        error_code = _diagnostic_token(
            body.get("errorCode"), "client.request_phone.unknown_error", 128)
        platform = _diagnostic_token(body.get("platform"), "unknown", 24)
        bridge_version = _diagnostic_token(body.get("bridgeVersion"), "unknown", 32)
        log.warning(
            "MAX requestContact frontend diagnostic: code=%s platform=%s bridge_version=%s",
            error_code, platform, bridge_version)
        return {"ok": True}

    @app.post("/api/auth/contact")
    async def auth_contact(body: dict[str, Any]) -> dict[str, Any]:
        messenger, user_id, user = _authenticated_launch(body)
        if messenger == "max":
            # MAX возвращает подписанную тройку. Отсутствие ЛЮБОГО поля или неверный HMAC
            # означает отказ: аккаунт и сессию не создаём даже в AUTH_INSECURE.
            phone = _auth_phone(body.get("phone"))
            auth_date = body.get("authDate")
            hash_hex = str(body.get("hash") or "")
            if not phone or auth_date in (None, "") or not hash_hex:
                raise HTTPException(status_code=400, detail={
                    "code": "contact_required",
                    "message": "Подтвердите номер телефона и повторите попытку."})
            if not security.verify_max_contact(
                    phone, auth_date, hash_hex, user_id, config.MAX_BOT_TOKEN, max_age=86400):
                raise HTTPException(status_code=400, detail={
                    "code": "bad_contact",
                    "message": "Не удалось подтвердить номер. Перезапустите приложение из бота и попробуйте снова."})
            account = await store.confirm_identity_phone("max", user_id, phone)
        else:
            # Telegram WebApp сообщает callback-у только boolean. Сам номер приходит боту
            # отдельным private Message.contact и принимается poller-ом лишь как self-contact.
            # Апдейт может слегка отстать от HTTP, поэтому после успешного callback ждём его
            # ограниченное время; без подтверждённого номера ничего не создаём и не выдаём.
            account = store.find_account_by_identity("tg", user_id)
            if not account or not _auth_phone(account.get("phone")):
                if body.get("contactShared") is True:
                    for _ in range(50):
                        await asyncio.sleep(0.1)
                        account = store.find_account_by_identity("tg", user_id)
                        if account and _auth_phone(account.get("phone")):
                            break
                if not account or not _auth_phone(account.get("phone")):
                    raise HTTPException(status_code=409, detail={
                        "code": "contact_required",
                        "message": "Не удалось получить подтверждённый номер. Повторите попытку или войдите по другому номеру."})
        await store.update_identity_profile(messenger, user_id, user)
        account = store.account(account["id"]) or account
        return {"token": security.make_session(account["id"]), "account": _account_view(account)}

    @app.post("/api/auth/silent")
    async def auth_silent(body: dict[str, Any]) -> dict[str, Any]:
        # Тихое восстановление сессии при запуске mini-app: по подписанному initData находим
        # СУЩЕСТВУЮЩИЙ аккаунт (БЕЗ создания) и выдаём токен. Если аккаунта ещё нет —
        # {exists:false}, фронт покажет обычный экран входа (онбординг новых не меняется).
        # Так сессия переживает перезагрузку даже без localStorage (в вебвью MAX он может не
        # сохраняться) — initData есть при каждом запуске.
        messenger, user_id, user = _authenticated_launch(body)
        account = store.find_account_by_identity(messenger, user_id)
        if account is None or not _auth_phone(account.get("phone")):
            return {"exists": False}
        await store.update_identity_profile(messenger, user_id, user)
        account = store.account(account["id"]) or account
        return {"token": security.make_session(account["id"]),
                "account": _account_view(account), "exists": True}

    @app.post("/api/auth/otp/request")
    async def otp_request(body: dict[str, Any]) -> dict[str, Any]:
        _authenticated_identity(body)  # OTP доступен только из валидно запущенной mini-app.
        phone = _auth_phone(body.get("phone"))
        if not phone:
            raise HTTPException(status_code=400, detail={
                "code": "bad_phone", "message": "Введите номер в международном формате."})
        # Доставка кода: в мессенджер/аккаунт, где этот номер уже авторизован.
        acc = store.find_account_by_phone(phone)
        if not acc:
            # Неизвестный номер не создаёт ни аккаунт, ни OTP-запись.
            raise HTTPException(status_code=404, detail={
                "code": "not_found", "message": "Аккаунт с таким номером не найден."})
        rec = await store.issue_otp(phone)
        delivered = False
        if _notifier:
            for messenger, uid in store.identities_of(acc["id"]):
                try:
                    await _notifier(messenger, uid, f"Код для входа в {config.BOT_NAME}: {rec['code']}\nДействует 10 минут.")
                    delivered = True
                except Exception:  # noqa: BLE001
                    log.warning("OTP-доставка не удалась messenger=%s uid=%s", messenger, uid)
        if not delivered:
            # Номер и одноразовый код не пишем в журнал даже в dev-режиме.
            log.info("OTP создан, но доставка недоступна%s",
                     " (dev-режим)" if config.AUTH_INSECURE else "")
        return {"ok": True, "resendAfter": config.OTP_RESEND, "expiresIn": config.OTP_TTL}

    @app.post("/api/auth/otp/verify")
    async def otp_verify(body: dict[str, Any]) -> dict[str, Any]:
        messenger, user_id, user = _authenticated_launch(body)
        phone = _auth_phone(body.get("phone"))
        if not phone:
            raise HTTPException(status_code=400, detail={
                "code": "bad_phone", "message": "Введите номер в международном формате."})
        code = str(body.get("code") or "")
        acc = store.find_account_by_phone(phone)
        if not acc:
            raise HTTPException(status_code=404, detail={"code": "not_found", "message": "Аккаунт с таким номером не найден."})
        if not await store.check_otp(phone, code):
            raise HTTPException(status_code=400, detail={"code": "bad_code", "message": "Неверный код. Проверьте сообщение и введите код ещё раз."})
        account = await store.link_identity_to_account(messenger, user_id, acc["id"])
        await store.update_identity_profile(messenger, user_id, user)
        account = store.account(account["id"]) or account
        return {"token": security.make_session(account["id"]), "account": _account_view(account)}

    @app.get("/api/account")
    async def get_account(acc_id: str = Acc) -> dict[str, Any]:
        return _account_view(store.account(acc_id))

    @app.post("/api/account/flags")
    async def set_account_flag(body: dict[str, Any], acc_id: str = Acc) -> dict[str, Any]:
        # Одноразовые UI-флаги аккаунта (показанные подсказки). Хранятся на сервере,
        # а не в localStorage: в вебвью MAX localStorage не переживает перезагрузку.
        flag = str(body.get("flag") or "")
        if flag not in ACCOUNT_UI_FLAGS:
            raise HTTPException(status_code=400, detail={
                "code": "bad_flag", "message": "Неизвестный флаг."})
        return _account_view(await store.mark_account_flag(acc_id, flag))

    @app.post("/api/legal/accept")
    async def accept_legal(body: dict[str, Any] | None = None, acc_id: str = Acc) -> dict[str, Any]:
        body = body or {}
        terms_version = str(body.get("termsVersion") or config.LEGAL_TERMS_VERSION)
        privacy_version = str(body.get("privacyVersion") or config.LEGAL_PRIVACY_VERSION)
        if (terms_version != config.LEGAL_TERMS_VERSION
                or privacy_version != config.LEGAL_PRIVACY_VERSION):
            raise HTTPException(status_code=409, detail={
                "code": "legal_version_mismatch",
                "message": "Редакция документов изменилась. Обновите экран и примите актуальную версию."})
        messenger = str(body.get("messenger") or "").strip().lower()
        if messenger not in ("max", "tg"):
            messenger = None
        accepted = await store.accept_legal(
            acc_id, terms_version=terms_version, privacy_version=privacy_version,
            source=str(body.get("source") or "miniapp"),
            messenger=messenger, user_id=body.get("userId"))
        return _account_view(accepted)

    # ----------------------- SUBSCRIPTION -----------------------
    def _subscription_for_account(acc_id: str) -> dict[str, Any]:
        return _subscription_view(
            store.subscription(acc_id),
            price=store.price_for(acc_id),
            rule_limit=store.rule_limit_for(acc_id),
            traffic_limit=store.traffic_limit_for(acc_id),
        )

    @app.get("/api/subscription")
    async def get_subscription(acc_id: str = Acc) -> dict[str, Any]:
        return _subscription_for_account(acc_id)

    # ----------------------- ОПЛАТА (ЮKassa) -----------------------
    def _billing_or_503() -> Any:
        if _billing is None or not _billing.enabled:
            raise HTTPException(status_code=503, detail={
                "code": "pay_unavailable",
                "message": "Оплата временно недоступна. Попробуйте позже."})
        return _billing

    def _billing_http(e: Any) -> HTTPException:
        return HTTPException(status_code=e.status, detail={"code": e.code, "message": e.message})

    @app.post("/api/pay/checkout")
    async def pay_checkout(body: dict[str, Any], acc_id: str = Acc) -> dict[str, Any]:
        from .billing import BillingError
        _require_legal(acc_id)
        b = _billing_or_503()
        mode = str(body.get("mode") or "pay")
        method = str(body.get("method") or "bank_card")
        autopay = bool(body.get("autopay", True))
        try:
            res = await b.start_checkout(acc_id, mode, method=method, autopay=autopay)
        except BillingError as e:
            raise _billing_http(e)
        res["subscription"] = _subscription_for_account(acc_id)
        return res

    @app.get("/api/pay/status")
    async def pay_status(acc_id: str = Acc) -> dict[str, Any]:
        from .billing import BillingError
        b = _billing_or_503()
        try:
            state = await b.check_pending(acc_id)
        except BillingError as e:
            raise _billing_http(e)
        return {"state": state,
                "subscription": _subscription_for_account(acc_id),
                "traffic": await _traffic_view(store, acc_id)}

    @app.post("/api/pay/cancel")
    async def pay_cancel(acc_id: str = Acc) -> dict[str, Any]:
        b = _billing_or_503()
        await b.cancel_pending(acc_id)
        return {"ok": True, "subscription": _subscription_for_account(acc_id)}

    @app.post("/api/pay/autopay")
    async def pay_autopay(body: dict[str, Any], acc_id: str = Acc) -> dict[str, Any]:
        from .billing import BillingError
        if bool(body.get("enabled")):
            _require_legal(acc_id)
        b = _billing_or_503()
        try:
            res = await b.set_autopay(acc_id, bool(body.get("enabled")))
        except BillingError as e:
            raise _billing_http(e)
        res["subscription"] = _subscription_for_account(acc_id)
        return res

    @app.post("/api/pay/webhook")
    async def pay_webhook(body: dict[str, Any] | None = None) -> dict[str, Any]:
        # Публичный (без сессии): ЮKassa шлёт {event, object}. Телу не доверяем —
        # billing перечитывает объект из API по id (см. Billing.webhook). Отвечаем
        # 200 всегда, иначе ЮKassa будет повторять доставку.
        if _billing is not None and isinstance(body, dict):
            event = str(body.get("event") or "")
            obj = body.get("object")
            if event and isinstance(obj, dict):
                try:
                    await _billing.webhook(event, obj)
                except Exception:  # noqa: BLE001
                    log.warning("pay/webhook: сбой обработки", exc_info=True)
        return {"ok": True}

    # ----------------------- КОДЫ АКТИВАЦИИ -----------------------
    @app.post("/api/pay/activate")
    async def pay_activate(body: dict[str, Any], acc_id: str = Acc) -> dict[str, Any]:
        # Код даёт месяц подписки БЕЗ привязки карты — работает и при выключенной
        # ЮKassa (не требует _billing_or_503). Лимит 3 ввода / 10 минут — в Activation.
        from .activation import ActivationError
        _require_legal(acc_id)
        if _activation is None:
            raise HTTPException(status_code=503, detail={
                "code": "activation_unavailable",
                "message": "Активация кодом временно недоступна."})
        try:
            res = await _activation.activate(acc_id, body.get("code"))
        except ActivationError as e:
            raise HTTPException(status_code=e.status,
                                detail={"code": e.code, "message": e.message})
        return {"ok": True, "until": res["until"],
                "subscription": _subscription_for_account(acc_id)}

    @app.post("/api/market/activate")
    async def market_activate(body: dict[str, Any] | None, request: Request) -> dict[str, Any]:
        """Активировать код Яндекс Маркета по телефону существующего аккаунта.

        Эндпоинт намеренно не создаёт аккаунт и не выдаёт JWT: произвольный введённый
        номер не является доказательством владения им. Одноразовый код немедленно
        добавляет месяц к текущей дате окончания через общий Activation.activate().
        """
        body = body or {}
        if not bool(body.get("legalAccepted")):
            raise HTTPException(status_code=428, detail={
                "code": "legal_required",
                "message": "Примите условия использования и политику конфиденциальности."})
        terms_version = str(body.get("termsVersion") or config.LEGAL_TERMS_VERSION)
        privacy_version = str(body.get("privacyVersion") or config.LEGAL_PRIVACY_VERSION)
        if (terms_version != config.LEGAL_TERMS_VERSION
                or privacy_version != config.LEGAL_PRIVACY_VERSION):
            raise HTTPException(status_code=409, detail={
                "code": "legal_version_mismatch",
                "message": "Редакция документов изменилась. Обновите страницу и попробуйте снова."})

        phone = _market_phone(body.get("phone"))
        if phone is None:
            raise HTTPException(status_code=400, detail={
                "code": "bad_phone",
                "message": "Введите номер телефона в международном формате."})

        from .activation import ActivationError, normalize_code
        code = normalize_code(body.get("code"))
        if code is None:
            raise HTTPException(status_code=400, detail={
                "code": "bad_code_format",
                "message": "Введите код в формате XXXX-XXXX-XXXX."})
        _market_activation_attempt(f"ip:{_client_ip(request)}", 20)
        _market_activation_attempt(f"phone:{phone}", 5)

        if _activation is None:
            raise HTTPException(status_code=503, detail={
                "code": "activation_unavailable",
                "message": "Активация временно недоступна. Попробуйте позже."})

        account = store.find_account_by_phone(phone)
        generic_error = {
            "code": "activation_failed",
            "message": ("Не удалось активировать подписку. Проверьте номер и код. "
                        f"Если аккаунта ещё нет, сначала откройте {config.BOT_NAME} в MAX или Telegram "
                        "и войдите по этому номеру."),
        }
        if account is None:
            raise HTTPException(status_code=404, detail=generic_error)
        try:
            result = await _activation.activate(account["id"], code)
        except ActivationError as exc:
            if exc.code == "code_not_found":
                raise HTTPException(status_code=404, detail=generic_error) from exc
            raise HTTPException(status_code=exc.status, detail={
                "code": exc.code, "message": exc.message}) from exc

        await store.accept_legal(
            account["id"], terms_version=terms_version, privacy_version=privacy_version,
            source="yandex_market")
        return {
            "ok": True,
            "until": result["until"],
            "subscription": _subscription_for_account(account["id"]),
        }

    # В кабинете задаётся БАЗОВЫЙ URL интеграции, а Маркет сам добавляет к нему
    # `/notification`. Вариант без суффикса оставляем для совместимости и ручного smoke.
    @app.post("/api/yandex-market/notifications/{webhook_secret}/notification")
    @app.post("/api/yandex-market/notifications/{webhook_secret}")
    async def yandex_market_notification(webhook_secret: str, body: dict[str, Any] | None,
                                         request: Request) -> dict[str, str]:
        """Принять API-уведомление Маркета и быстро положить заказ в очередь.

        Защита двойная: непубличный URL-secret и обязательные официальные IP-диапазоны.
        Сетевые запросы к Partner API здесь не выполняются — это делает воркер.
        """
        if not config.YANDEX_MARKET_ENABLED:
            raise HTTPException(status_code=503, detail={
                "code": "market_integration_disabled",
                "message": "Интеграция Яндекс Маркета отключена.",
            })
        expected = config.YANDEX_MARKET_WEBHOOK_SECRET
        if not expected:
            raise HTTPException(status_code=503, detail={
                "code": "market_integration_disabled",
                "message": "Интеграция Яндекс Маркета не настроена.",
            })
        if not secrets.compare_digest(webhook_secret, expected):
            raise HTTPException(status_code=401, detail={
                "code": "bad_webhook_secret", "message": "Неверный адрес уведомлений."})
        if not _yandex_market_ip_allowed(request):
            raise HTTPException(status_code=403, detail={
                "code": "bad_source_ip", "message": "Источник уведомления не разрешён."})
        if not isinstance(body, dict) or not str(body.get("notificationType") or "").strip():
            raise HTTPException(status_code=400, detail={
                "code": "bad_notification", "message": "Некорректное уведомление."})
        if _yandex_market is None:
            raise HTTPException(status_code=503, detail={
                "code": "market_integration_unavailable",
                "message": "Обработчик Яндекс Маркета не запущен.",
            })
        try:
            await _yandex_market.handle_notification(body)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail={
                "code": "bad_notification", "message": str(exc)[:300]}) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=503, detail={
                "code": "market_integration_disabled", "message": str(exc)[:300]}) from exc
        return _yandex_market_response()

    # ----------------------- АДМИН -----------------------
    def _require_admin(x_admin_key: str) -> None:
        # Ключ — MESYNC_ADMIN_KEY из .env; не задан → админ-эндпоинты выключены.
        import secrets as _secrets
        if not config.ADMIN_KEY:
            raise HTTPException(status_code=503, detail={
                "code": "admin_disabled", "message": "Админ-доступ не настроен."})
        if not _secrets.compare_digest(x_admin_key or "", config.ADMIN_KEY):
            raise HTTPException(status_code=401, detail={
                "code": "bad_admin_key", "message": "Неверный админ-ключ."})

    @app.post("/api/admin/activation-codes")
    async def admin_generate_codes(body: dict[str, Any],
                                   x_admin_key: str = Header(default="")) -> dict[str, Any]:
        _require_admin(x_admin_key)
        if _activation is None:
            raise HTTPException(status_code=503, detail={
                "code": "activation_unavailable", "message": "Активация не подключена."})
        codes = await _activation.generate(int(body.get("count") or 1))
        return {"codes": codes}

    @app.get("/api/admin/activation-codes")
    async def admin_list_codes(x_admin_key: str = Header(default="")) -> dict[str, Any]:
        _require_admin(x_admin_key)
        return store.activation_codes_stats()

    # ----------------------- ЖАЛОБЫ НА КОНТЕНТ (модерация, этап 3) -----------------------
    def _reports_enabled_or_503() -> None:
        reports_on = config.MODERATION_REPORTS_ENABLED
        if _settings is not None:
            try:
                reports_on = bool(_settings.get("moderation_reports_enabled"))
            except Exception:  # noqa: BLE001
                pass
        if not reports_on or _reports is None:
            raise HTTPException(status_code=503, detail={
                "code": "reports_disabled", "message": "Модерация временно недоступна."})

    @app.post("/api/report/check")
    async def check_report(body: dict[str, Any]) -> dict[str, Any]:
        # Preflight для mini-app: до показа формы убеждаемся, что ссылка валидна и бот всё ещё
        # обслуживает Telegram-группу, где находится копия сообщения.
        from .reports import ReportError
        _reports_enabled_or_503()
        try:
            return await _reports.check(body.get("token"))
        except ReportError as e:
            raise HTTPException(status_code=e.status,
                                detail={"code": e.code, "message": e.message})

    @app.post("/api/report")
    async def submit_report(body: dict[str, Any]) -> dict[str, Any]:
        # Публичный (без сессии): жалобщик — читатель в чужом чате/канале, чаще НЕ клиент
        # MeSync. Аутентификация — по подписанному initData запуска mini-app (доказывает
        # реальный запуск из бота) → идентичность только для антиспама; аккаунт НЕ создаём.
        from .reports import ReportError
        _reports_enabled_or_503()
        messenger = "tg" if str(body.get("messenger")) in ("tg", "telegram") else "max"
        validated = security.authenticate(messenger, str(body.get("initData") or ""))
        if validated is None:
            raise HTTPException(status_code=400, detail={
                "code": "bad_signature",
                "message": "Не удалось подтвердить запуск. Откройте ссылку заново из мессенджера."})
        user = validated.get("user") if isinstance(validated.get("user"), dict) else {}
        user_id = user.get("id") or body.get("userId")
        if user_id is None and config.AUTH_INSECURE:
            user_id = "dev"
        if user_id is None:
            raise HTTPException(status_code=400, detail={
                "code": "no_user", "message": "Не удалось определить пользователя."})
        try:
            res = await _reports.submit(body.get("token"), body.get("text"),
                                        reporter=f"{messenger}:{user_id}")
        except ReportError as e:
            raise HTTPException(status_code=e.status, detail={"code": e.code, "message": e.message})
        return {"ok": True, "id": res.get("id")}

    # ----------------------- БРАУЗЕРНАЯ АДМИН-ПАНЕЛЬ (этап 4) -----------------------
    @app.post("/api/admin/login")
    async def admin_login(body: dict[str, Any], request: Request, response: Response) -> dict[str, Any]:
        ip = _client_ip(request)
        _admin_throttle_check(ip)
        # Единый 401 и для выключенной панели (пустой пароль → verify=False), и для неверного
        # пароля — не раскрываем анонимному пробберу, настроена ли панель на этом инстансе.
        if not security.verify_admin_password(str(body.get("password") or "")):
            _admin_throttle_fail(ip)
            if config.ADMIN_PASSWORD:   # неудачный вход при включённой панели — в аудит
                await store.add_audit(action="login_failed", ip=ip)
            raise HTTPException(status_code=401, detail={
                "code": "bad_password", "message": "Неверный пароль."})
        _admin_login_fails.pop(ip, None)
        # Secure следует ФАКТИЧЕСКОЙ внешней схеме: через production Caddy/gateway это HTTPS,
        # а чистый локальный Docker quick start доступен по HTTP и тоже должен сохранять
        # сессию. HttpOnly защищает от JS, SameSite=strict — от cross-site CSRF.
        response.set_cookie("mesync_admin", security.make_admin_session(), httponly=True,
                            secure=_external_request_is_https(request), samesite="strict",
                            max_age=config.ADMIN_SESSION_TTL, path="/")
        await store.add_audit(action="login", ip=ip)
        return {"ok": True}

    @app.post("/api/admin/logout")
    async def admin_logout(request: Request, response: Response,
                           _: bool = AdminAuth) -> dict[str, Any]:
        response.delete_cookie("mesync_admin", path="/")
        await store.add_audit(action="logout", ip=_client_ip(request))
        return {"ok": True}

    @app.get("/api/admin/me")
    async def admin_me(_: bool = AdminAuth) -> dict[str, Any]:
        return {"ok": True}

    @app.get("/api/admin/settings")
    async def admin_get_settings(_: bool = AdminAuth) -> dict[str, Any]:
        if _settings is None:
            raise HTTPException(status_code=503, detail={
                "code": "settings_unavailable", "message": "Настройки недоступны."})
        return {"settings": _settings.all()}

    @app.put("/api/admin/settings")
    async def admin_put_settings(body: dict[str, Any], request: Request,
                                 _: bool = AdminAuth) -> dict[str, Any]:
        from .settings import SettingsError
        if _settings is None:
            raise HTTPException(status_code=503, detail={
                "code": "settings_unavailable", "message": "Настройки недоступны."})
        body = body or {}
        # Фаза 1: валидируем ВСЕ ключи/значения БЕЗ записи — иначе валидная правка применилась
        # бы, а на битом ключе запрос упал бы с 400, оставив частичное состояние без аудита.
        try:
            for k, v in body.items():
                _settings.validate(k, v)
        except SettingsError as e:
            raise HTTPException(status_code=400, detail={
                "code": "bad_setting", "message": e.message})
        # Фаза 2: применяем и собираем изменения (все ключи уже валидны).
        changed: dict[str, Any] = {}
        for k, v in body.items():
            old = _settings.get(k)
            applied = await _settings.set(k, v)
            if old != applied:
                changed[k] = {"from": old, "to": applied}
        if changed:
            await store.add_audit(action="settings", details=changed, ip=_client_ip(request))
        return {"settings": _settings.all()}

    @app.get("/api/admin/audit")
    async def admin_audit(_: bool = AdminAuth) -> dict[str, Any]:
        return {"items": store.audit_list(limit=200)}

    @app.post("/api/admin/backup")
    async def admin_backup(request: Request, _: bool = AdminAuth) -> Response:
        if not await store.healthcheck():
            raise HTTPException(status_code=503, detail={
                "code": "backup_unavailable",
                "message": "База данных недоступна. Резервная копия не создана.",
            })
        await store.add_audit(
            action="database:backup",
            details={"backend": store.backend},
            ip=_client_ip(request),
        )
        data = await store.export_backup()
        filename = datetime.now(timezone.utc).strftime(
            "mesync-control-backup-%Y%m%d-%H%M%SZ.json")
        return Response(content=data, media_type="application/json", headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-store, no-cache, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
            "X-Content-Type-Options": "nosniff",
            "X-MeSync-Backup-SHA256": hashlib.sha256(data).hexdigest(),
        })

    @app.post("/api/admin/backup/validate")
    async def admin_backup_validate(request: Request,
                                    _: bool = AdminAuth) -> dict[str, Any]:
        raw = await _read_backup_upload(request)
        try:
            summary = await store.inspect_backup(raw)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail={
                "code": "invalid_backup", "message": str(exc)}) from exc
        return {"ok": True, "summary": summary}

    @app.post("/api/admin/backup/restore", status_code=202)
    async def admin_backup_restore(
            request: Request,
            x_mesync_backup_sha256: str = Header(default=""),
            x_mesync_restore_confirm: str = Header(default=""),
            _: bool = AdminAuth) -> dict[str, Any]:
        if x_mesync_restore_confirm.lower() != "restore":
            raise HTTPException(status_code=400, detail={
                "code": "restore_confirmation_required",
                "message": "Восстановление не подтверждено.",
            })
        raw = await _read_backup_upload(request)
        try:
            summary = await store.stage_restore(
                raw,
                expected_sha256=x_mesync_backup_sha256,
                ip=_client_ip(request),
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail={
                "code": "invalid_backup", "message": str(exc)}) from exc

        restart_scheduled = False
        if _restart_handler is not None:
            try:
                _restart_handler()
                restart_scheduled = True
            except Exception:  # noqa: BLE001
                log.exception("Не удалось запланировать рестарт после restore %s",
                              summary["restoreId"])
        return {
            "ok": True,
            "summary": summary,
            "restartScheduled": restart_scheduled,
            "previousBackup": store.restore_previous_path.name,
        }

    # ----------------------- АДМИН: OPS / НАБЛЮДАЕМОСТЬ (этап 4.5) -----------------------
    @app.get("/api/admin/ops")
    async def admin_ops(_: bool = AdminAuth) -> dict[str, Any]:
        """Единый снимок состояния сервиса для «Сводки»: живость ботов, очередь жалоб,
        агрегатные метрики, лента событий. Всё — дешёвые in-memory чтения (без сети и без
        обхода по аккаунтам); при отсутствии инжектов возвращаем частичный ответ + 200,
        чтобы дашборд деградировал мягко, а не падал."""
        now = int(time.time())
        day = now - 86400
        accts = store.table("accounts")
        reps = store.table("reports")
        codes = store.activation_codes_stats()
        return {
            "ts": now,
            "bots": _health.snapshot() if _health else {},
            "queues": {"reports": _reports.stats() if _reports else None,
                       "broadcast": _broadcaster.stats() if _broadcaster else None},
            "paymentsPaused": bool(_settings.get("payments_paused")) if _settings else None,
            "metrics": {
                "accounts": len(accts),
                "accounts24h": sum(1 for a in accts.values() if int(a.get("created_at", 0)) >= day),
                "subs": {"active": store.subscriptions_page(status="active", limit=1)["total"],
                         "inactive": store.subscriptions_page(status="inactive", limit=1)["total"]},
                "rules": len(store.table("rules")),
                "traffic": store.traffic_page(limit=1)["totals"],
                "codes": {"total": codes["total"], "unused": len(codes["unused"]),
                          "used": len(codes["used"]), "expired": len(codes["expired"]),
                          "revoked": len(codes.get("revoked") or [])},
                "reports": {"queued": len(store.queued_report_ids()),
                            "error": store.reports_page(status="error", limit=1)["total"],
                            "violation": store.reports_page(verdict="violation", limit=1)["total"],
                            "last24h": sum(1 for r in reps.values() if int(r.get("ts", 0)) >= day)},
                "audit": len(store.table("admin_audit")),
            },
            "events": store.events_list(limit=20),
        }

    # ----------------------- АДМИН: РАССЫЛКИ В ЛИЧКУ (этап 4.6) -----------------------
    _BC_AUDIENCE = ("all", "active", "trial")
    _BC_MESSENGER = ("both", "max", "tg")

    def _bc_scope(body: dict[str, Any]) -> tuple[str, str, str | None]:
        audience = str(body.get("audience") or "all")
        messenger = str(body.get("messenger") or "both")
        if audience not in _BC_AUDIENCE or messenger not in _BC_MESSENGER:
            raise HTTPException(status_code=400, detail={
                "code": "bad_request", "message": "Некорректная аудитория/мессенджер."})
        return audience, messenger, (None if messenger == "both" else messenger)

    @app.post("/api/admin/broadcasts/preview")
    async def admin_bc_preview(body: dict[str, Any], _: bool = AdminAuth) -> dict[str, Any]:
        audience, _m, mscope = _bc_scope(body)
        recips = store.build_broadcast_recipients(messenger=mscope, audience=audience)
        return {"count": len(recips)}

    @app.post("/api/admin/broadcasts")
    async def admin_bc_create(body: dict[str, Any], request: Request,
                              _: bool = AdminAuth) -> dict[str, Any]:
        text = str(body.get("text") or "").strip()
        if not text:
            raise HTTPException(status_code=400, detail={
                "code": "bad_request", "message": "Текст рассылки пуст."})
        if body.get("confirm") is not True:
            raise HTTPException(status_code=400, detail={
                "code": "confirm_required", "message": "Требуется подтверждение отправки."})
        if _broadcaster is None:
            raise HTTPException(status_code=503, detail={
                "code": "broadcaster_unavailable", "message": "Рассыльщик недоступен."})
        if store.active_broadcast_ids():   # быстрый путь (без построения снимка)
            raise HTTPException(status_code=409, detail={
                "code": "broadcast_active", "message": "Уже идёт другая рассылка. Дождитесь завершения."})
        audience, messenger, mscope = _bc_scope(body)
        recips = store.build_broadcast_recipients(messenger=mscope, audience=audience)
        if not recips:
            raise HTTPException(status_code=400, detail={
                "code": "no_recipients", "message": "Нет адресатов под выбранные условия."})
        # АТОМАРНО: под локом стора ещё раз проверяем «нет активной» и вставляем — иначе два
        # одновременных POST могли бы пройти лишённую блокировки проверку выше (TOCTOU).
        rec = await store.add_broadcast({"text": text, "audience": audience, "messenger": messenger,
                                         "recipients": recips, "total": len(recips)}, if_idle=True)
        if rec is None:
            raise HTTPException(status_code=409, detail={
                "code": "broadcast_active", "message": "Уже идёт другая рассылка. Дождитесь завершения."})
        _broadcaster.enqueue(rec["id"])
        await store.add_audit(action="broadcast_create", target=rec["id"],
                              details={"audience": audience, "messenger": messenger,
                                       "total": len(recips), "text": text[:200]},
                              ip=_client_ip(request))
        return {"broadcast": {k: v for k, v in rec.items() if k != "recipients"}}

    @app.get("/api/admin/broadcasts")
    async def admin_bc_list(limit: int = 50, offset: int = 0,
                            _: bool = AdminAuth) -> dict[str, Any]:
        return store.broadcasts_page(limit=limit, offset=offset)

    @app.get("/api/admin/broadcasts/{bid}")
    async def admin_bc_detail(bid: str, _: bool = AdminAuth) -> dict[str, Any]:
        rec = store.get_broadcast(bid)
        if rec is None:
            raise HTTPException(status_code=404, detail={
                "code": "not_found", "message": "Рассылка не найдена."})
        return {"broadcast": {k: v for k, v in rec.items() if k != "recipients"}}

    @app.post("/api/admin/broadcasts/{bid}/action")
    async def admin_bc_action(bid: str, body: dict[str, Any], request: Request,
                              _: bool = AdminAuth) -> dict[str, Any]:
        rec = store.get_broadcast(bid)
        if rec is None:
            raise HTTPException(status_code=404, detail={
                "code": "not_found", "message": "Рассылка не найдена."})
        if str(body.get("action") or "") != "cancel":
            raise HTTPException(status_code=400, detail={
                "code": "bad_action", "message": "Неизвестное действие."})
        if rec.get("status") in ("pending", "running"):
            # снимаем снимок recipients (резюме уже не будет) — экономим размер стора
            await store.update_broadcast(bid, {"status": "canceled", "recipients": []})
            await store.add_audit(action="broadcast_cancel", target=bid, ip=_client_ip(request))
        upd = store.get_broadcast(bid)
        return {"ok": True, "broadcast": {k: v for k, v in (upd or {}).items() if k != "recipients"}}

    # ----------------------- АДМИН: МОДЕРАЦИЯ (этап 4.2) -----------------------
    @app.get("/api/admin/moderation/reports")
    async def admin_mod_reports(status: str = "", verdict: str = "", category: str = "",
                                limit: int = 50, offset: int = 0,
                                _: bool = AdminAuth) -> dict[str, Any]:
        return store.reports_page(status=status or None, verdict=verdict or None,
                                  category=category or None, limit=limit, offset=offset)

    @app.get("/api/admin/moderation/reports/{report_id}")
    async def admin_mod_report(report_id: str, _: bool = AdminAuth) -> dict[str, Any]:
        rec = store.report(report_id)
        if rec is None:
            raise HTTPException(status_code=404, detail={
                "code": "not_found", "message": "Жалоба не найдена."})
        return {"report": rec}

    _MOD_STORE_ACTIONS = {
        "dismiss", "hold_rule", "unhold_rule", "block_account", "unblock_account",
        "mute_rule", "unmute_rule", "override",
    }
    _MOD_IO_ACTIONS = {"hide_copies", "delete_copies", "reclassify"}

    @app.post("/api/admin/moderation/reports/{report_id}/action")
    async def admin_mod_action(report_id: str, body: dict[str, Any], request: Request,
                               _: bool = AdminAuth) -> dict[str, Any]:
        rec = store.report(report_id)
        if rec is None:
            raise HTTPException(status_code=404, detail={
                "code": "not_found", "message": "Жалоба не найдена."})
        action = str(body.get("action") or "")
        rule_id, acc_id = rec.get("rule_id"), rec.get("account_id")
        result: dict[str, Any] = {}

        def _no_target(msg: str):
            return HTTPException(status_code=400, detail={"code": "no_target", "message": msg})

        _RULE_PATCH = {"mute_rule": {"report_muted": True},
                       "unmute_rule": {"report_muted": False}}
        if action == "dismiss":
            # status=done — иначе воркер переобработает жалобу и перезатрёт решение оператора.
            await store.update_report(report_id, {"reviewed": True, "status": "done"})
        elif action in ("hold_rule", "unhold_rule"):
            if not rule_id:
                raise _no_target("У жалобы нет привязанного правила.")
            if await set_rule_moderation_hold(store, rule_id, action == "hold_rule") is None:
                raise _no_target("Правило не найдено (удалено).")
        elif action in _RULE_PATCH:
            if not rule_id:
                raise _no_target("У жалобы нет привязанного правила.")
            if await store.update_rule(rule_id, _RULE_PATCH[action]) is None:
                raise _no_target("Правило не найдено (удалено).")
        elif action in ("block_account", "unblock_account"):
            if not acc_id:
                raise _no_target("У жалобы нет привязанного аккаунта.")
            if not await store.set_account_blocked(acc_id, action == "block_account"):
                raise _no_target("Аккаунт не найден.")
        elif action == "override":
            v = str(body.get("verdict") or "")
            if v not in ("ok", "violation", "unsure"):
                raise HTTPException(status_code=400, detail={
                    "code": "bad_verdict", "message": "Недопустимый вердикт."})
            await store.update_report(report_id, {
                "verdict": v, "category": str(body.get("category") or ""),
                "reviewed": True, "status": "done",   # фиксируем — воркер не переобработает
                "reason": "ручной вердикт администратора"})
        elif action in _MOD_IO_ACTIONS:
            if _reports is None:
                raise HTTPException(status_code=503, detail={
                    "code": "moderation_unavailable", "message": "Модерация недоступна."})
            if action in ("hide_copies", "delete_copies"):
                hidden = await _reports.admin_delete_copies(report_id)
                result["hidden"] = hidden
                result["deleted"] = hidden  # legacy response field for existing admin clients
            else:
                result["verdict"] = await _reports.admin_reclassify(report_id)
        else:
            raise HTTPException(status_code=400, detail={
                "code": "bad_action", "message": "Неизвестное действие."})
        await store.add_audit(action=f"moderation:{action}", target=report_id,
                              details={"rule": rule_id, "account": acc_id, **result},
                              ip=_client_ip(request))
        return {"ok": True, "report": store.report(report_id), **result}

    @app.post("/api/admin/moderation/classify")
    async def admin_mod_classify(body: dict[str, Any], _: bool = AdminAuth) -> dict[str, Any]:
        if _reports is None:
            raise HTTPException(status_code=503, detail={
                "code": "moderation_unavailable", "message": "Модерация недоступна."})
        return await _reports.classify_test(body.get("text"))

    @app.get("/api/admin/moderation/stoplist")
    async def admin_get_stoplist(_: bool = AdminAuth) -> dict[str, Any]:
        from pathlib import Path as _Path
        p = _Path(config.MODERATION_STOPLIST_FILE)
        try:
            text = p.read_text(encoding="utf-8") if p.exists() else ""
        except OSError:
            text = ""
        return {"text": text, "path": str(p)}

    @app.put("/api/admin/moderation/stoplist")
    async def admin_put_stoplist(body: dict[str, Any], request: Request,
                                 _: bool = AdminAuth) -> dict[str, Any]:
        from pathlib import Path as _Path
        text = str(body.get("text") or "")
        try:
            import yaml
            parsed = yaml.safe_load(text)
        except Exception:  # noqa: BLE001
            raise HTTPException(status_code=400, detail={
                "code": "bad_yaml", "message": "Не удалось разобрать YAML — проверьте синтаксис."})
        # НЕ даём затереть словарь пустышкой (пустой текст/скаляр/список парсятся без ошибки,
        # но обнулили бы весь предфильтр — это и был инцидент). Требуем непустую мапу категорий.
        if not isinstance(parsed, dict) or not parsed:
            raise HTTPException(status_code=400, detail={
                "code": "empty_stoplist",
                "message": "Словарь пуст или не является YAML-мапой категорий — сохранение отменено."})
        p = _Path(config.MODERATION_STOPLIST_FILE)
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(text, encoding="utf-8")
        except OSError:
            raise HTTPException(status_code=500, detail={
                "code": "write_failed", "message": "Не удалось сохранить словарь."})
        await store.add_audit(action="moderation:stoplist",
                              details={"bytes": len(text)}, ip=_client_ip(request))
        return {"ok": True}

    # ----------------------- АДМИН: АККАУНТЫ + БИЛЛИНГ (этап 4.3) -----------------------
    @app.get("/api/admin/accounts")
    async def admin_accounts(q: str = "", limit: int = 50, offset: int = 0,
                             _: bool = AdminAuth) -> dict[str, Any]:
        page = store.accounts_page(q=q, limit=limit, offset=offset)
        for a in page["items"]:
            aid = a["id"]
            a["subscription"] = store.subscription(aid).get("status")
            a["blocked"] = bool(a.get("blocked"))
            a["rulesCount"] = len(store.rules_of(aid))
            a["overrides"] = {"rule_limit": a.get("rule_limit"), "price": a.get("price"),
                              "traffic_limit": a.get("traffic_limit")}
            a["profile"] = _admin_account_profile(aid)
        return page

    def _account_avatar_choice(acc_id: str) -> tuple[str, str, dict[str, Any]] | None:
        identities = store.identities_by_messenger(acc_id)
        profiles = (store.account(acc_id) or {}).get("profiles") or {}
        max_uid = identities.get("max")
        if max_uid is not None:
            max_profile = profiles.get(f"max:{max_uid}") if isinstance(profiles, dict) else None
            if isinstance(max_profile, dict) and (
                    max_profile.get("avatar_url") or max_profile.get("full_avatar_url")):
                return "max", str(max_uid), dict(max_profile)
        tg_uid = identities.get("tg")
        if tg_uid is not None:
            tg_profile = profiles.get(f"tg:{tg_uid}") if isinstance(profiles, dict) else None
            return "tg", str(tg_uid), dict(tg_profile) if isinstance(tg_profile, dict) else {}
        return None

    def _direct_http_url(value: Any) -> str | None:
        url = str(value or "").strip()
        return url if url.lower().startswith(("https://", "http://")) else None

    def _account_direct_avatar_url(acc_id: str) -> str | None:
        choice = _account_avatar_choice(acc_id)
        if not choice:
            return None
        messenger, _user_id, profile = choice
        if messenger != "max":
            return None
        return _direct_http_url(profile.get("full_avatar_url")) or _direct_http_url(profile.get("avatar_url"))

    def _admin_account_profile(acc_id: str) -> dict[str, Any]:
        profile = store.account_profile_summary(acc_id)
        if profile.get("hasAvatar"):
            direct = _account_direct_avatar_url(acc_id)
            if direct:
                profile["avatar"] = direct
            else:
                version = profile.get("avatarVersion") or int(time.time())
                query = {"t": security.make_account_avatar_token(acc_id), "v": version}
                profile["avatar"] = f"/api/admin/accounts/{acc_id}/avatar?{urlencode(query)}"
        return profile

    @app.get("/api/admin/accounts/{acc_id}/avatar")
    async def admin_account_avatar(acc_id: str, t: str = "",
                                   mesync_admin: str = Cookie(default="")) -> Response:
        token_acc = security.decode_account_avatar_token(t) if t else None
        admin_ok = bool(config.ADMIN_PASSWORD and security.decode_admin_session(mesync_admin))
        if token_acc and token_acc != acc_id:
            raise HTTPException(status_code=404, detail={
                "code": "not_found", "message": "Аккаунт не найден."})
        if token_acc != acc_id and not admin_ok:
            raise HTTPException(status_code=401, detail={
                "code": "unauthorized", "message": "Требуется вход"})
        if store.account(acc_id) is None:
            raise HTTPException(status_code=404, detail={
                "code": "not_found", "message": "Аккаунт не найден."})
        choice = _account_avatar_choice(acc_id)
        if choice is None or _account_avatar_fetcher is None:
            raise HTTPException(status_code=404, detail={
                "code": "no_avatar", "message": "Аватарка аккаунта не найдена."})
        messenger, user_id, profile = choice
        try:
            res = await _account_avatar_fetcher(messenger, user_id, profile)
        except Exception:  # noqa: BLE001
            log.warning("account avatar fetch failed acc=%s messenger=%s", acc_id, messenger, exc_info=True)
            res = None
        if not res:
            raise HTTPException(status_code=404, detail={
                "code": "no_avatar", "message": "Аватарка аккаунта не найдена."})
        ct, data = res[0] or "image/jpeg", res[1]
        headers = {"Cache-Control": "private, max-age=3600"}
        return Response(content=data, media_type=ct, headers=headers)

    @app.get("/api/admin/accounts/{acc_id}")
    async def admin_account_detail(acc_id: str, _: bool = AdminAuth) -> dict[str, Any]:
        a = store.account(acc_id)
        if a is None:
            raise HTTPException(status_code=404, detail={
                "code": "not_found", "message": "Аккаунт не найден."})
        since = int(time.time()) - 24 * 3600
        return {
            "account": a,
            "profile": _admin_account_profile(acc_id),
            "identities": store.identities_of(acc_id),
            "subscription": _subscription_for_account(acc_id),
            "traffic": await _traffic_view(store, acc_id),
            "rules": (await rules_mod.list_rules(store, acc_id)),
            "sources": store.account_source_ids(acc_id),
            "blocked": store.account_blocked(acc_id),
            "overrides": {
                "rule_limit": a.get("rule_limit"), "price": a.get("price"),
                "traffic_limit": a.get("traffic_limit"),
                "effective": {"rule_limit": store.rule_limit_for(acc_id),
                              "price": store.price_for(acc_id),
                              "traffic_limit": store.traffic_limit_for(acc_id)},
            },
            "strikes24h": len(store.reports_since(acc_id, since, verdict="violation")),
        }

    @app.post("/api/admin/accounts/{acc_id}/action")
    async def admin_account_action(acc_id: str, body: dict[str, Any], request: Request,
                                   _: bool = AdminAuth) -> dict[str, Any]:
        if store.account(acc_id) is None:
            raise HTTPException(status_code=404, detail={
                "code": "not_found", "message": "Аккаунт не найден."})
        action = str(body.get("action") or "")
        result: dict[str, Any] = {}
        if action == "block":
            await store.set_account_blocked(acc_id, True)
        elif action == "unblock":
            await store.set_account_blocked(acc_id, False)
        elif action == "reset_traffic":
            await store.reset_traffic(acc_id)
        elif action == "disable_subscription":
            sub = await store.disable_subscription(acc_id)
            result["subscription"] = _subscription_for_account(acc_id)
            result["disabled"] = sub.get("status") == "inactive"
        elif action == "disable_autopay":
            sub, annulled = await store.disable_autopay(acc_id)
            result["subscription"] = _subscription_for_account(acc_id)
            result["autopay"] = bool(sub.get("autopay"))
            result["annulled"] = annulled
        elif action == "set_overrides":
            patch: dict[str, Any] = {}
            try:
                for k in ("rule_limit", "price", "traffic_limit"):
                    if k in body:
                        v = body[k]
                        if v in (None, ""):
                            patch[k] = None
                        else:
                            iv = int(v)
                            patch[k] = max(1, iv) if k == "rule_limit" else max(0, iv)
            except (TypeError, ValueError):
                raise HTTPException(status_code=400, detail={
                    "code": "bad_override", "message": "Числовое значение недопустимо."})
            await store.set_account_overrides(acc_id, patch)
            result["overrides"] = {"rule_limit": store.rule_limit_for(acc_id),
                                   "price": store.price_for(acc_id),
                                   "traffic_limit": store.traffic_limit_for(acc_id)}
        elif action in ("grant_month", "issue_code"):
            if _activation is None:
                raise HTTPException(status_code=503, detail={
                    "code": "activation_unavailable", "message": "Активация недоступна."})
            if action == "grant_month":
                result = dict(await _activation.grant_month(acc_id))
            else:
                codes = await _activation.generate(1)
                result["code"] = codes[0] if codes else None
        else:
            raise HTTPException(status_code=400, detail={
                "code": "bad_action", "message": "Неизвестное действие."})
        await store.add_audit(action=f"account:{action}", target=acc_id,
                              details={k: v for k, v in body.items() if k != "action"},
                              ip=_client_ip(request))
        return {"ok": True, **result}

    @app.get("/api/admin/subscriptions")
    async def admin_subscriptions(status: str = "", limit: int = 50, offset: int = 0,
                                  _: bool = AdminAuth) -> dict[str, Any]:
        return store.subscriptions_page(status=status or None, limit=limit, offset=offset)

    @app.post("/api/admin/codes")
    async def admin_codes_generate(body: dict[str, Any], request: Request,
                                   _: bool = AdminAuth) -> dict[str, Any]:
        if _activation is None:
            raise HTTPException(status_code=503, detail={
                "code": "activation_unavailable", "message": "Активация недоступна."})
        codes = await _activation.generate(int(body.get("count") or 1))
        await store.add_audit(action="codes:generate", details={"count": len(codes)},
                              ip=_client_ip(request))
        return {"codes": codes}

    @app.get("/api/admin/codes")
    async def admin_codes_list(_: bool = AdminAuth) -> dict[str, Any]:
        return store.activation_codes_stats()

    @app.post("/api/admin/codes/{code}/action")
    async def admin_code_action(code: str, body: dict[str, Any], request: Request,
                                _: bool = AdminAuth) -> dict[str, Any]:
        action = str(body.get("action") or "")
        if action != "revoke":
            raise HTTPException(status_code=400, detail={
                "code": "bad_action", "message": "Неизвестное действие."})
        result = await store.revoke_activation_code(code)
        if result == "not_found":
            raise HTTPException(status_code=404, detail={
                "code": "not_found", "message": "Код не найден."})
        if result == "used":
            raise HTTPException(status_code=409, detail={
                "code": "code_used", "message": "Код уже использован."})
        if result == "expired":
            raise HTTPException(status_code=409, detail={
                "code": "code_expired", "message": "Код уже истёк."})
        if result == "already_revoked":
            return {"ok": True, "status": result}
        await store.add_audit(action="codes:revoke", target=code[:4],
                              details={"code_prefix": code[:4]},
                              ip=_client_ip(request))
        return {"ok": True, "status": result}

    # ----------------------- 4.4: ПРАВИЛА / ИСТОЧНИКИ / ТРАФИК (глобальные обзоры) -----------------------
    @app.get("/api/admin/rules")
    async def admin_rules(q: str = "", account_id: str = "", status: str = "",
                          messenger: str = "", source_id: str = "", limit: int = 100,
                          offset: int = 0, _: bool = AdminAuth) -> dict[str, Any]:
        return await rules_mod.admin_rules_page(
            store, q=q, account_id=account_id or None, status=status or None,
            messenger=messenger or None, source_id=source_id or None, limit=limit, offset=offset)

    @app.get("/api/admin/rules/{rule_id}")
    async def admin_rule_detail(rule_id: str, _: bool = AdminAuth) -> dict[str, Any]:
        view = await rules_mod.admin_rule_view(store, rule_id)
        if view is None:
            raise HTTPException(status_code=404, detail={
                "code": "not_found", "message": "Правило не найдено."})
        acc_id = view.get("account_id")
        per_rule = int((store.traffic(acc_id).get("per_rule") or {}).get(rule_id, 0))
        return {"rule": view, "account": {"id": acc_id, "phone": view.get("phone")},
                "perRuleBytes": per_rule}

    _RULE_ADMIN_PATCH = {"mute_rule": {"report_muted": True},
                         "unmute_rule": {"report_muted": False}}

    @app.post("/api/admin/rules/{rule_id}/action")
    async def admin_rule_action(rule_id: str, body: dict[str, Any], request: Request,
                                _: bool = AdminAuth) -> dict[str, Any]:
        r = store.rule(rule_id)
        if r is None:
            raise HTTPException(status_code=404, detail={
                "code": "not_found", "message": "Правило не найдено."})
        acc_id = r.get("account_id")
        action = str(body.get("action") or "")
        result: dict[str, Any] = {}
        try:
            # pause/resume/delete/dismiss идут через rules_mod с acc_id владельца — чтобы
            # сохранить проверки владения и конфликтов; hold/mute — безопасный патч напрямую.
            if action == "pause":
                result["rule"] = await rules_mod.set_status(
                    store, acc_id, rule_id, "paused", allow_moderation_hold=True)
            elif action == "resume":
                result["rule"] = await rules_mod.set_status(
                    store, acc_id, rule_id, "active", allow_moderation_hold=True)
            elif action == "delete":
                await rules_mod.delete_rule(store, acc_id, rule_id)
            elif action == "dismiss_warning":
                result["rule"] = await rules_mod.dismiss_warning(
                    store, acc_id, rule_id, allow_moderation_hold=True)
            elif action in ("hold_rule", "unhold_rule"):
                result["rule"] = await set_rule_moderation_hold(store, rule_id, action == "hold_rule")
            elif action in _RULE_ADMIN_PATCH:
                await store.update_rule(rule_id, _RULE_ADMIN_PATCH[action])
            else:
                raise HTTPException(status_code=400, detail={
                    "code": "bad_action", "message": "Неизвестное действие."})
        except RuleError as e:
            raise HTTPException(status_code=e.status, detail={"code": e.code, "message": e.message})
        await store.add_audit(action=f"rule:{action}", target=rule_id,
                              details={"account_id": acc_id}, ip=_client_ip(request))
        return {"ok": True, **result}

    @app.get("/api/admin/sources")
    async def admin_sources(q: str = "", messenger: str = "", status: str = "",
                            limit: int = 100, offset: int = 0, _: bool = AdminAuth) -> dict[str, Any]:
        return await sources_mod.admin_list_sources(
            store, q=q, messenger=messenger or None, status=status or None,
            limit=limit, offset=offset)

    @app.get("/api/admin/traffic")
    async def admin_traffic(sort: str = "used", min_percent: int = 0, state: str = "",
                            limit: int = 100,
                            offset: int = 0, _: bool = AdminAuth) -> dict[str, Any]:
        return store.traffic_page(sort=sort, min_percent=min_percent or None,
                                  state=state or None, limit=limit, offset=offset)

    @app.post("/api/admin/traffic/{acc_id}/action")
    async def admin_traffic_action(acc_id: str, body: dict[str, Any], request: Request,
                                   _: bool = AdminAuth) -> dict[str, Any]:
        if store.account(acc_id) is None:
            raise HTTPException(status_code=404, detail={
                "code": "not_found", "message": "Аккаунт не найден."})
        if str(body.get("action") or "") != "reset_traffic":
            raise HTTPException(status_code=400, detail={
                "code": "bad_action", "message": "Неизвестное действие."})
        await store.reset_traffic(acc_id)
        await store.add_audit(action="traffic:reset", target=acc_id, ip=_client_ip(request))
        return {"ok": True}

    # ----------------------- SOURCES -----------------------
    @app.get("/api/sources")
    async def get_sources(acc_id: str = Acc) -> dict[str, Any]:
        return await sources_mod.list_sources(store, acc_id, title_provider=_chat_info_provider)

    @app.post("/api/sources/code")
    async def create_source_code(body: dict[str, Any], acc_id: str = Acc) -> dict[str, Any]:
        _require_legal(acc_id)
        messenger = "tg" if str(body.get("messenger")) in ("tg", "telegram") else "max"
        res = await store.issue_code(acc_id, messenger)
        # Единый источник хэндлов — config.BOT_HANDLES.
        return {"code": res["code"], "expiresAt": res["expires_at"] * 1000,
                "botHandle": config.BOT_HANDLES[messenger]}

    @app.get("/api/sources/pending")
    async def get_pending(acc_id: str = Acc) -> dict[str, Any]:
        # Код привязки многоразовый в пределах TTL: возвращаем активный код аккаунта и
        # ВСЕ источники, привязанные им за сессию. Когда код истечёт — status=idle.
        codes = store.active_codes()
        mine = [(c, v) for c, v in codes.items() if v.get("account_id") == acc_id]
        if not mine:
            return {"status": "idle"}
        code, rec = mine[0]
        bound: list[dict[str, Any]] = []
        for sid in (rec.get("bound") or []):
            src = await sources_mod.resolve_source(store, sid)
            if src:
                bound.append(src)
        return {"status": "listening", "code": code, "bound": bound,
                "expiresAt": int(rec.get("expires_at", 0)) * 1000}

    @app.get("/api/sources/{source_id:path}/avatar")
    async def get_source_avatar(source_id: str, t: str = "", v: str = "") -> Response:
        # Фото грузится тегом <img>, который не умеет слать заголовок Authorization,
        # поэтому токен едет в query (?t=). Это УЗКИЙ токен аватара (aud=avatar,
        # привязан к источнику, TTL 1 ч), выданный в /api/sources — не сессия. Его
        # привязка к источнику и есть авторизация: выдаётся только для своих источников.
        # v — версия фото (Telegram small_file_unique_id): делает URL и кэш адресуемыми
        # по содержимому, поэтому совпавший версионный ответ помечаем immutable (меняется
        # фото → меняется v → меняется URL → кэш сам инвалидируется).
        decoded = security.decode_avatar_token(t) if t else None
        if not decoded:
            raise HTTPException(status_code=401, detail={"code": "unauthorized", "message": "Требуется вход"})
        acc_id, token_src = decoded
        if token_src != source_id or store.account(acc_id) is None:
            raise HTTPException(status_code=404, detail={"code": "not_found", "message": "Источник не найден"})
        # v принимаем ТОЛЬКО если совпадает с актуальным photo_id источника. Это отсекает
        # произвольные/устаревшие v: иначе клиент с валидным токеном плодил бы вечные
        # версионные записи на диске (переполнение) и амплифицировал бы запросы к
        # мессенджеру. Чужой/старый v → обслуживаем как невёрсионный (короткий кэш).
        parsed_src = parse_source_id(source_id)
        cache_source_id = make_source_id(parsed_src["messenger"], parsed_src["chat_id"]) if parsed_src else source_id
        known = store.cached_source_info(cache_source_id).get("photo_id")
        version = v if (v and known and v == known) else None
        res = await avatars_mod.get_avatar(source_id, _avatar_fetcher, version=version)
        if not res:
            raise HTTPException(status_code=404, detail={"code": "no_photo", "message": "Нет фото"})
        data, content_type, exact = res
        cache = "public, max-age=31536000, immutable" if (version and exact) else "public, max-age=3600"
        return Response(content=data, media_type=content_type,
                        headers={"Cache-Control": cache})

    @app.get("/api/sources/{source_id:path}")
    async def get_source(source_id: str, acc_id: str = Acc) -> dict[str, Any]:
        if not await sources_mod.owns_source(store, acc_id, source_id):
            raise HTTPException(status_code=404, detail={"code": "not_found", "message": "Источник не найден"})
        src = await sources_mod.resolve_source(store, source_id)
        rules = (await rules_mod.list_rules(store, acc_id))["rules"]
        src["usedInRules"] = sum(1 for r in rules if source_id in (r["a"]["sourceId"], r["b"]["sourceId"]))
        return src

    @app.delete("/api/sources/{source_id:path}")
    async def delete_source(source_id: str, acc_id: str = Acc) -> dict[str, Any]:
        if not await sources_mod.owns_source(store, acc_id, source_id):
            raise HTTPException(status_code=404, detail={"code": "not_found", "message": "Источник не найден"})
        parsed = parse_source_id(source_id)
        if not parsed:
            raise HTTPException(status_code=404, detail={"code": "not_found", "message": "Источник не найден"})
        # Название до удаления — для текста уведомления об отвязке.
        src = await sources_mod.resolve_source(store, source_id)
        title = (src or {}).get("title") or source_id
        messenger, chat_id, thread_id = parsed["messenger"], parsed["chat_id"], parsed.get("thread_id")

        # Удаляем правила, account-bound источники, pending-коды и source_meta с этим
        # endpoint. Для базовой TG-супергруппы метод чистит и topic-источники.
        await store.delete_source_references(messenger, chat_id, thread_id)
        # ПОЛНАЯ отвязка у бота: удалить запись ownership (иначе источник остаётся в
        # списке — list_sources читает ownership.json) + бот выходит из чата. Фоллбэк на
        # старый chat_leaver, если unbinder не внедрён (standalone/тесты).
        # Topic-источник — часть супергруппы: при удалении НЕ выходим из всего чата.
        if thread_id is None and _source_unbinder:
            try:
                await _source_unbinder(messenger, chat_id)
            except Exception:  # noqa: BLE001
                log.warning("source_unbinder не удался для %s", source_id)
        elif thread_id is None and _chat_leaver:
            try:
                await _chat_leaver(messenger, chat_id)
            except Exception:  # noqa: BLE001
                log.warning("chat_leaver не удался для %s", source_id)
        # Лаконичное уведомление об отвязке в чат с ботом + «Скрыть» — во ВСЕ привязанные
        # мессенджеры аккаунта (если привязаны оба).
        if _source_notifier:
            for m, uid in store.identities_by_messenger(acc_id).items():
                try:
                    await _source_notifier(m, uid, f"🗑 Источник «{title}» отвязан")
                except Exception:  # noqa: BLE001
                    log.warning("source_notifier (unbind) сбой для %s (%s)", source_id, m)
        return {"ok": True}

    # ----------------------- RULES -----------------------
    @app.get("/api/rules")
    async def get_rules(acc_id: str = Acc) -> dict[str, Any]:
        return await rules_mod.list_rules(store, acc_id)

    @app.post("/api/rules")
    async def create_rule(body: dict[str, Any], acc_id: str = Acc) -> dict[str, Any]:
        _require_legal(acc_id)
        try:
            _sig = bool(body.get("signature"))   # back-compat: единое поле → оба направления
            rule = await rules_mod.create_rule(
                store, acc_id, a_id=str(body.get("aId") or ""), b_id=str(body.get("bId") or ""),
                direction=str(body.get("dir") or "both"),
                sign_ab=bool(body.get("signAB", _sig)), sign_ba=bool(body.get("signBA", _sig)))
        except RuleError as e:
            raise HTTPException(status_code=e.status, detail={"code": e.code, "message": e.message})
        return {"rule": rule}

    @app.patch("/api/rules/{rule_id}")
    async def patch_rule(rule_id: str, body: dict[str, Any], acc_id: str = Acc) -> dict[str, Any]:
        _require_legal(acc_id)
        try:
            rule = await rules_mod.update_rule(store, acc_id, rule_id, body)
        except RuleError as e:
            raise HTTPException(status_code=e.status, detail={"code": e.code, "message": e.message})
        return {"rule": rule}

    @app.post("/api/rules/{rule_id}/pause")
    async def pause_rule(rule_id: str, acc_id: str = Acc) -> dict[str, Any]:
        return {"rule": await _set_status(store, acc_id, rule_id, "paused")}

    @app.post("/api/rules/{rule_id}/resume")
    async def resume_rule(rule_id: str, acc_id: str = Acc) -> dict[str, Any]:
        _require_legal(acc_id)
        return {"rule": await _set_status(store, acc_id, rule_id, "active")}

    @app.delete("/api/rules/{rule_id}")
    async def remove_rule(rule_id: str, acc_id: str = Acc) -> dict[str, Any]:
        try:
            await rules_mod.delete_rule(store, acc_id, rule_id)
        except RuleError as e:
            raise HTTPException(status_code=e.status, detail={"code": e.code, "message": e.message})
        return {"ok": True}

    @app.post("/api/rules/{rule_id}/dismiss-warning")
    async def dismiss_rule_warning(rule_id: str, acc_id: str = Acc) -> dict[str, Any]:
        try:
            rule = await rules_mod.dismiss_warning(store, acc_id, rule_id)
        except RuleError as e:
            raise HTTPException(status_code=e.status, detail={"code": e.code, "message": e.message})
        return {"rule": rule}

    # ----------------------- TRAFFIC -----------------------
    @app.get("/api/traffic")
    async def get_traffic(acc_id: str = Acc) -> dict[str, Any]:
        return await _traffic_view(store, acc_id)

    @app.post("/api/traffic/topup")
    async def topup(acc_id: str = Acc) -> dict[str, Any]:
        from .billing import BillingError
        _require_legal(acc_id)
        b = _billing_or_503()
        try:
            res = await b.start_traffic_topup(acc_id)
        except BillingError as e:
            raise _billing_http(e)
        res["traffic"] = await _traffic_view(store, acc_id)
        return res

    # ----------------------- NOTIFICATIONS -----------------------
    @app.get("/api/notifications")
    async def get_notifications(acc_id: str = Acc) -> dict[str, Any]:
        items = store.notifications_of(acc_id)
        return {"items": items, "unread": sum(1 for n in items if not n.get("read"))}

    @app.post("/api/notifications/read")
    async def read_notifications(body: dict[str, Any] | None = None, acc_id: str = Acc) -> dict[str, Any]:
        ids = body.get("ids") if isinstance(body, dict) else None
        await store.mark_read(acc_id, ids)
        return {"ok": True}

    @app.get("/api/health")
    async def health(response: Response) -> dict[str, Any]:
        ready = await store.healthcheck()
        if not ready:
            response.status_code = 503
        return {"ok": ready, "ts": int(time.time()), "storage": store.backend}

    # Отдельный публичный URL активации. Возвращаем тот же SPA-index, а frontend
    # выбирает экран по pathname. Канонический путь без завершающего слеша важен:
    # Vite base='./' тогда загружает assets от корня, а не из /ya_market/assets/.
    @app.get("/api/public-config.js", include_in_schema=False)
    async def frontend_public_config() -> Response:
        return Response(
            content=public_config_script(),
            media_type="application/javascript",
            headers={"Cache-Control": "no-store"},
        )

    @app.get("/ya_market", include_in_schema=False)
    async def yandex_market_activation_page() -> HTMLResponse:
        index = config.ROOT / "web" / "dist" / "index.html"
        if not index.is_file():
            raise HTTPException(status_code=503, detail={
                "code": "frontend_unavailable",
                "message": "Страница активации временно недоступна."})
        source = await asyncio.to_thread(index.read_text, encoding="utf-8")
        return HTMLResponse(
            render_public_html(source),
            headers={"Cache-Control": "no-store"},
        )

    @app.get("/ya_market/", include_in_schema=False)
    async def yandex_market_activation_page_slash() -> RedirectResponse:
        return RedirectResponse(url="/ya_market", status_code=308)

    # Короткая ссылка рекламной посадочной. Сохраняем click/campaign-параметры,
    # но источник и канал задаём серверной конфигурацией, чтобы их нельзя было подменить.
    @app.get("/vk", include_in_schema=False)
    @app.get("/vk/", include_in_schema=False)
    async def vk_ads_landing(request: Request) -> RedirectResponse:
        preserved = [
            (key, value)
            for key, value in request.query_params.multi_items()
            if key not in {"utm_source", "utm_medium"}
        ]
        preserved.extend((("utm_source", config.VK_ADS_UTM_SOURCE),
                          ("utm_medium", config.VK_ADS_UTM_MEDIUM)))
        return RedirectResponse(url=f"/?{urlencode(preserved)}", status_code=302)

    # Браузерная админ-панель — отдельный SPA на /admin. Монтируется ДО catch-all
    # «/», иначе mini-app проглотил бы /admin/*. Собирается в admin/dist.
    admin_dist = config.ROOT / "admin" / "dist"
    if admin_dist.is_dir():
        app.mount("/admin", StaticFiles(directory=str(admin_dist), html=True), name="adminapp")
        log.info("Статика админ-панели: %s", admin_dist)

    # Раздача собранного фронта mini-app (web/dist). Монтируется ПОСЛЕ /api-роутов,
    # поэтому /api/* всегда обрабатывается API, а всё остальное — статикой SPA.
    dist = config.ROOT / "web" / "dist"
    if dist.is_dir():
        app.mount("/", RuntimeConfigStaticFiles(directory=str(dist), html=True), name="webapp")
        log.info("Статика mini-app: %s", dist)
    else:
        log.warning("web/dist не найден — фронт не раздаётся (соберите: cd web && npm run build)")

    return app


# ----------------------- сериализация -----------------------
def _account_view(a: dict[str, Any] | None) -> dict[str, Any]:
    if not a:
        return {}
    return {"id": a["id"], "phone": a.get("phone"), "createdAt": (a.get("created_at") or 0) * 1000,
            "uiFlags": dict(a.get("ui_flags") or {}), "legal": _legal_view(a)}


def _legal_view(a: dict[str, Any]) -> dict[str, Any]:
    accepted = a.get("legal_acceptance")
    if not isinstance(accepted, dict):
        accepted = {}
    terms_ok = accepted.get("terms_version") == config.LEGAL_TERMS_VERSION
    privacy_ok = accepted.get("privacy_version") == config.LEGAL_PRIVACY_VERSION
    accepted_at = int(accepted.get("accepted_at") or 0)
    return {
        "accepted": bool(terms_ok and privacy_ok),
        "acceptedAt": accepted_at * 1000 or None,
        "termsVersion": accepted.get("terms_version"),
        "privacyVersion": accepted.get("privacy_version"),
        "requiredTermsVersion": config.LEGAL_TERMS_VERSION,
        "requiredPrivacyVersion": config.LEGAL_PRIVACY_VERSION,
        "termsUrl": config.LEGAL_TERMS_URL,
        "privacyUrl": config.LEGAL_PRIVACY_URL,
    }


def _subscription_view(sub: dict[str, Any], price: int | None = None,
                       rule_limit: int | None = None,
                       traffic_limit: int | None = None) -> dict[str, Any]:
    pending = sub.get("pending") or {}
    now = time.time()
    paid_until = float(sub.get("paid_until") or 0)
    in_renew_window = bool(sub.get("status") == "active"
                           and now < paid_until <= now + config.RENEW_WINDOW_DAYS * 86400)
    # Ранняя ручная оплата: активная подписка БЕЗ автопродления в последние
    # RENEW_WINDOW_DAYS дней — фронт показывает кнопку «Продлить» (S11).
    can_renew_early = bool(in_renew_window and not sub.get("autopay"))
    eff_price = int(price) if price is not None else config.PRICE_RUB
    eff_rule_limit = int(rule_limit) if rule_limit is not None else config.RULE_LIMIT
    eff_traffic_limit = int(traffic_limit) if traffic_limit is not None else config.TRAFFIC_LIMIT_BYTES
    individual = tariffs.is_individual(
        price=eff_price,
        rule_limit=eff_rule_limit,
        traffic_limit=eff_traffic_limit,
    )
    return {
        "status": sub.get("status", "inactive"),
        "plan": tariffs.plan_id(individual, str(sub.get("plan") or tariffs.SMART_PLAN)),
        "planName": tariffs.plan_name(individual),
        "isIndividual": individual,
        "price": eff_price,   # персональная цена аккаунта (4.3); 0 ₽ — валидный override
        "currency": "₽",
        "ruleLimit": eff_rule_limit,
        "trafficLimitBytes": eff_traffic_limit,
        "trafficLimitText": tariffs.fmt_bytes_ru(eff_traffic_limit),
        "canRenewEarly": can_renew_early,
        "canActivateCode": in_renew_window,
        "renewAt": sub.get("renew_at"),
        "paidUntil": int(sub.get("paid_until") or 0) * 1000 or None,
        "trial": bool(sub.get("trial")),
        "trialUsed": bool(sub.get("trial_used")),
        "trialDays": config.TRIAL_DAYS,
        "autopay": bool(sub.get("autopay")),
        "methodTitle": sub.get("payment_method_title"),
        "pendingKind": pending.get("kind"),
        "lastError": sub.get("last_error"),
        "payEnabled": bool(_billing is not None and _billing.enabled),
        "perks": tariffs.perks(rule_limit=eff_rule_limit, traffic_limit=eff_traffic_limit),
    }


async def _traffic_view(store: ControlStore, acc_id: str) -> dict[str, Any]:
    t = store.traffic(acc_id)
    et = store.effective_traffic(acc_id)   # единая формула monthly/add-on/percent (этап 4.4)
    sub = store.subscription(acc_id)
    per_rule_raw = t.get("per_rule", {}) or {}
    rules = (await rules_mod.list_rules(store, acc_id))["rules"]
    titles = {r["id"]: f"{r['a']['title']} ⇄ {r['b']['title']}" for r in rules}
    per_rule = [{"ruleId": rid, "title": titles.get(rid, "Правило"), "bytes": int(b)}
                for rid, b in per_rule_raw.items() if int(b) > 0]
    return {
        "usedBytes": et["used"],
        "limitBytes": et["limit"],
        "topupBytes": et["topup"],
        "topupPackageBytes": config.TOPUP_BYTES,
        "topupPackagePrice": config.TOPUP_PRICE_RUB,
        "topupPayEnabled": bool(_billing is not None and getattr(_billing, "accepting_payments", False)),
        "includedRemainingBytes": et["included_remaining"],
        "overageBytes": et["overage"],
        "mediaAllowed": bool(et["media_allowed"]),
        "resetAt": sub.get("renew_at"),
        "percent": et["percent"],
        "perRule": per_rule,
    }


async def _set_status(store: ControlStore, acc_id: str, rule_id: str, status: str) -> dict[str, Any]:
    try:
        return await rules_mod.set_status(store, acc_id, rule_id, status)
    except RuleError as e:
        raise HTTPException(status_code=e.status, detail={"code": e.code, "message": e.message})
