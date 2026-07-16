"""Безопасность control-API: проверка подписи хоста и JWT-сессии.

Проверки подписи хоста (источники — наш конспект docs/research и docs/max,
docs/telegram):
- Telegram Mini Apps initData: secret = HMAC_SHA256(key="WebAppData", msg=bot_token);
  ожидаемый hash = HMAC_SHA256(key=secret, msg=data_check_string), где
  data_check_string — отсортированные строки "k=v" (кроме hash), склеенные \n.
- MAX requestContact() в mini-app: {phone, authDate, hash};
  hash = HMAC_SHA256(key=bot_token, msg="authDate=..\nphone=..\nuserId=.."),
  phone без "+".

В dev/демо (MESYNC_AUTH_INSECURE=1, mock-контакт или пустой токен бота) проверка
подписи пропускается — это явно прокомментировано и не должно использоваться в prod.
"""
from __future__ import annotations

import hashlib
import hmac
import logging
import math
import time
from typing import Any
from urllib.parse import parse_qsl

import jwt

from . import config

log = logging.getLogger("control.security")


# ---------------- JWT-сессии ----------------
def make_session(account_id: str) -> str:
    payload = {"sub": account_id, "iat": int(time.time()), "exp": int(time.time()) + config.SESSION_TTL}
    return jwt.encode(payload, config.session_secret(), algorithm="HS256")


def decode_session(token: str) -> str | None:
    try:
        data = jwt.decode(token, config.session_secret(), algorithms=["HS256"],
                          options={"verify_aud": False})
        # Сессионный токен — без aud. Токены с aud (например, avatar) сессией не считаем.
        if data.get("aud"):
            return None
        return data.get("sub")
    except Exception:  # noqa: BLE001
        return None


# ---------------- Админ-сессия браузерной панели ----------------
# Один администратор, вход по паролю (config.ADMIN_PASSWORD). Сессия — JWT с aud="admin"
# (тот же session_secret; decode_session отвергает токены с aud, поэтому админ-сессия НЕ
# считается пользовательской и наоборот). Живёт в HttpOnly-cookie.
def make_admin_session() -> str:
    now = int(time.time())
    payload = {"sub": "admin", "aud": "admin", "iat": now, "exp": now + config.ADMIN_SESSION_TTL}
    return jwt.encode(payload, config.session_secret(), algorithm="HS256")


def decode_admin_session(token: str) -> bool:
    if not token:
        return False
    try:
        data = jwt.decode(token, config.session_secret(), algorithms=["HS256"], audience="admin")
    except Exception:  # noqa: BLE001
        return False
    return data.get("sub") == "admin"


def verify_admin_password(password: str) -> bool:
    """Сравнение пароля с config.ADMIN_PASSWORD в постоянное время. Пустой конфиг → всегда False
    (панель выключена)."""
    if not config.ADMIN_PASSWORD:
        return False
    return hmac.compare_digest(str(password or ""), config.ADMIN_PASSWORD)


# ---------------- Токены аватаров (узкие, короткоживущие) ----------------
# Фото грузится тегом <img>, который не шлёт заголовки, поэтому токен едет в URL
# (?t=) и может попасть в логи прокси. Чтобы утечка не давала полноправную сессию,
# для аватара выпускаем ОТДЕЛЬНЫЙ токен: source-avatar привязан к конкретному
# источнику (aud=avatar), account-avatar — к аккаунту (aud=account_avatar). Оба живут
# 1 час и выдаются только из уже аутентифицированных ответов API.
AVATAR_TTL: int = 3600


def make_avatar_token(account_id: str, source_id: str) -> str:
    now = int(time.time())
    payload = {"sub": account_id, "src": source_id, "aud": "avatar", "iat": now, "exp": now + AVATAR_TTL}
    return jwt.encode(payload, config.session_secret(), algorithm="HS256")


def decode_avatar_token(token: str) -> tuple[str, str] | None:
    """Вернуть (account_id, source_id) из токена аватара или None."""
    try:
        data = jwt.decode(token, config.session_secret(), algorithms=["HS256"], audience="avatar")
    except Exception:  # noqa: BLE001
        return None
    sub, src = data.get("sub"), data.get("src")
    return (sub, src) if sub and src else None


def make_account_avatar_token(account_id: str) -> str:
    """Узкий токен для загрузки аватара аккаунта из админки через <img src>."""
    now = int(time.time())
    payload = {"sub": account_id, "aud": "account_avatar", "iat": now, "exp": now + AVATAR_TTL}
    return jwt.encode(payload, config.session_secret(), algorithm="HS256")


def decode_account_avatar_token(token: str) -> str | None:
    """Вернуть account_id из токена аватара аккаунта или None."""
    try:
        data = jwt.decode(token, config.session_secret(), algorithms=["HS256"], audience="account_avatar")
    except Exception:  # noqa: BLE001
        return None
    sub = data.get("sub")
    return str(sub) if sub else None


# ---------------- Telegram initData ----------------
def verify_telegram_initdata(init_data_raw: str, bot_token: str) -> dict[str, Any] | None:
    """Проверить подпись initData. Возвращает разобранные поля (с user) или None."""
    if not init_data_raw or not bot_token:
        return None
    try:
        pairs = dict(parse_qsl(init_data_raw, keep_blank_values=True))
    except Exception:  # noqa: BLE001
        return None
    received = pairs.pop("hash", None)
    if not received:
        return None
    data_check_string = "\n".join(f"{k}={pairs[k]}" for k in sorted(pairs))
    secret = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    expected = hmac.new(secret, data_check_string.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, received):
        return None
    # auth_date не слишком старый (24 ч) — защита от реиграния.
    try:
        if pairs.get("auth_date") and time.time() - int(pairs["auth_date"]) > 86400:
            return None
    except ValueError:
        pass
    out = dict(pairs)
    if "user" in out:
        try:
            import json
            out["user"] = json.loads(out["user"])
        except Exception:  # noqa: BLE001
            pass
    return out


# MAX mini-app initData использует ТОТ ЖЕ алгоритм валидации, что и Telegram
# (secret_key = HMAC_SHA256("WebAppData", BOT_TOKEN); hash = hex(HMAC(secret, launch_params))),
# где launch_params — отсортированные key=value (без hash), склеенные \n. Сверено с
# docs/max/markdown/docs/webapps/validation.md.
verify_initdata = verify_telegram_initdata


def _auth_date_seconds(auth_date: Any) -> float | None:
    """Вернуть authDate в секундах только для проверки свежести.

    MAX Bridge документирует поле как timestamp, а живой `requestContact()` сейчас
    возвращает 13-значные миллисекунды. HMAC считается по исходной строке authDate,
    поэтому нормализовать можно только значение для replay-window.
    """
    try:
        ts = float(str(auth_date).strip())
    except (TypeError, ValueError):
        return None
    if not math.isfinite(ts) or ts <= 0:
        return None
    if ts >= 1_000_000_000_000:
        ts /= 1000.0
    return ts


def parse_initdata(init_data_raw: str) -> dict[str, Any]:
    """Разобрать initData БЕЗ проверки подписи (для dev/AUTH_INSECURE/пустого токена)."""
    try:
        pairs = dict(parse_qsl(init_data_raw or "", keep_blank_values=True))
    except Exception:  # noqa: BLE001
        return {}
    pairs.pop("hash", None)
    if "user" in pairs:
        try:
            import json
            pairs["user"] = json.loads(pairs["user"])
        except Exception:  # noqa: BLE001
            pass
    return pairs


def authenticate(messenger: str, init_data: str) -> dict[str, Any] | None:
    """Аутентифицировать запуск mini-app по initData (Telegram tg / MAX max).

    Возвращает разобранные параметры запуска (с полем user) при валидной подписи,
    иначе None. В dev-режиме (MESYNC_AUTH_INSECURE=1 или пустой токен бота) подпись
    не проверяется — это явно прокомментировано и не для prod.
    """
    token = config.TELEGRAM_BOT_TOKEN if messenger == "tg" else config.MAX_BOT_TOKEN
    if config.AUTH_INSECURE:
        return parse_initdata(init_data)
    if not token:
        log.warning("authenticate(%s): токен бота пуст — dev-обход подписи", messenger)
        return parse_initdata(init_data)
    return verify_initdata(init_data, token)


# ---------------- MAX requestContact ----------------
def verify_max_contact(phone: str, auth_date: Any, hash_hex: str, user_id: Any, bot_token: str,
                       *, max_age: int | None = None) -> bool:
    """Проверка номера из window.WebApp.requestContact() (опционально).

    Формат сверен с docs/max/markdown/docs/webapps/bridge.md: hash =
    HMAC_SHA256(botToken, "authDate=..\nphone=..\nuserId=..") — пары key=value
    в алфавитном порядке (authDate, phone, userId), склеенные \n; phone без '+'.

    max_age (сек) — если задан, отвергаем устаревший authDate (защита от replay
    перехваченной тройки {phone,authDate,hash}); как в verify_telegram_initdata.
    """
    if not bot_token or not hash_hex:
        return False
    if max_age is not None:
        auth_ts = _auth_date_seconds(auth_date)
        if auth_ts is None or abs(time.time() - auth_ts) > max_age:
            return False
    phone_d = "".join(ch for ch in str(phone) if ch.isdigit())
    msg = f"authDate={auth_date}\nphone={phone_d}\nuserId={user_id}"
    expected = hmac.new(bot_token.encode(), msg.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, str(hash_hex))


# ---------------- Единая точка входа авторизации по контакту ----------------
def verify_contact(*, messenger: str, phone: str, auth_date: Any, hash_hex: str,
                   user_id: Any, init_data: str = "", mock: bool = False) -> bool:
    """True, если подпись валидна (или включён dev-обход).

    ВАЖНО: флаг `mock` из тела запроса в проде ИГНОРИРУЕТСЯ — обход подписи возможен
    ТОЛЬКО при MESYNC_AUTH_INSECURE=1 (dev/демо). Иначе любой клиент мог бы войти
    под произвольным userId, прислав mock=true. В браузер-демо реальный backend не
    вызывается (фронт работает на встроенном mock), поэтому ничего не ломается.
    """
    if config.AUTH_INSECURE:
        return True
    _ = mock  # намеренно не используется в проде
    if messenger == "tg":
        token = config.TELEGRAM_BOT_TOKEN
        if not token:
            log.warning("verify_contact: TELEGRAM_BOT_TOKEN пуст — dev-обход")
            return True
        # Если есть initData — это надёжная аутентификация пользователя Telegram.
        if init_data and verify_telegram_initdata(init_data, token) is not None:
            return True
        return False
    if messenger == "max":
        token = config.MAX_BOT_TOKEN
        if not token:
            log.warning("verify_contact: MAX_BOT_TOKEN пуст — dev-обход")
            return True
        return verify_max_contact(phone, auth_date, hash_hex, user_id, token)
    return False
