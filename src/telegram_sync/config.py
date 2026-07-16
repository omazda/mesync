"""Конфигурация Этапа 1: загрузка настроек из окружения / .env.

Токен НИКОГДА не хардкодится в коде — только переменная окружения
TELEGRAM_BOT_TOKEN или файл .env (он в .gitignore).
"""
from __future__ import annotations

import os
from pathlib import Path

# Корень репозитория: src/telegram_sync/config.py -> ../../ == корень
ROOT = Path(__file__).resolve().parents[2]


def _load_dotenv(path: Path) -> None:
    """Минимальный загрузчик .env без внешних зависимостей.

    Реальные переменные окружения имеют приоритет над значениями из .env.
    """
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_dotenv(ROOT / ".env")

# --- Токен и Bot API ---
BOT_TOKEN: str = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
API_BASE: str = os.environ.get("TELEGRAM_API_BASE", "https://api.telegram.org").rstrip("/")

# --- Long polling (см. docs/telegram/markdown/04-api-reference.md -> getUpdates) ---
LONG_POLL_TIMEOUT: int = int(os.environ.get("LONG_POLL_TIMEOUT", "30"))
GET_UPDATES_LIMIT: int = int(os.environ.get("GET_UPDATES_LIMIT", "100"))

# Все типы апдейтов (поля объекта Update) — чтобы достать АБСОЛЮТНО ВЕСЬ контент.
# По умолчанию getUpdates НЕ присылает chat_member / message_reaction /
# message_reaction_count, поэтому перечисляем явно.
ALLOWED_UPDATES: list[str] = [
    "message", "edited_message", "channel_post", "edited_channel_post",
    "business_connection", "business_message", "edited_business_message",
    "deleted_business_messages", "guest_message",
    "message_reaction", "message_reaction_count",
    "inline_query", "chosen_inline_result", "callback_query",
    "shipping_query", "pre_checkout_query", "purchased_paid_media",
    "poll", "poll_answer",
    "my_chat_member", "chat_member", "chat_join_request",
    "chat_boost", "removed_chat_boost", "managed_bot",
]

# --- Медиагруппы (альбомы) ---
# Части альбома приходят отдельными апдейтами с общим media_group_id; правильный
# порядок = по возрастанию message_id. Ждём это число секунд "тишины" по группе
# перед сборкой (части могут прийти в разных ответах getUpdates).
MEDIA_GROUP_DEBOUNCE: float = float(os.environ.get("MEDIA_GROUP_DEBOUNCE", "2.0"))

# --- Скачивание медиа ---
DOWNLOAD_MEDIA: bool = os.environ.get("DOWNLOAD_MEDIA", "true").lower() in {"1", "true", "yes", "on"}
# Облачный Bot API качает файлы размером до 20 МБ (getFile). С ЛОКАЛЬНЫМ Bot API сервером
# (TELEGRAM_API_BASE → свой сервер) лимита скачивания нет — поднимите эту переменную
# (например, MAX_DOWNLOAD_BYTES=2097152000), чтобы архивировать/переносить крупные файлы.
MAX_DOWNLOAD_BYTES: int = int(os.environ.get("MAX_DOWNLOAD_BYTES", str(20 * 1024 * 1024)))

# --- Синхронизация: репост сообщений/постов привязанного чата в личку владельца ---
MIRROR_TO_OWNER: bool = os.environ.get("MIRROR_TO_OWNER", "true").lower() in {"1", "true", "yes", "on"}

# --- Хранилище ---
DATA_DIR: Path = Path(os.environ.get("DATA_DIR", str(ROOT / "data")))
RAW_UPDATES_FILE: Path = DATA_DIR / "updates.jsonl"
CONTENT_FILE: Path = DATA_DIR / "content.jsonl"
OFFSET_FILE: Path = DATA_DIR / "offset"
MEDIA_DIR: Path = DATA_DIR / "media"
KNOWN_CHATS_FILE: Path = DATA_DIR / "known_chats.json"
OWNERSHIP_FILE: Path = DATA_DIR / "ownership.json"

# --- Отправка логов в Telegram (пользователям, с которыми у бота есть чат) ---
LOG_TO_TELEGRAM: bool = os.environ.get("LOG_TO_TELEGRAM", "true").lower() in {"1", "true", "yes", "on"}
LOG_TO_TELEGRAM_LEVEL: str = os.environ.get("LOG_TO_TELEGRAM_LEVEL", "INFO").upper()
# Как часто отправлять накопленные строки лога (сек) — троттлинг под лимиты Bot API.
LOG_SHIP_INTERVAL: float = float(os.environ.get("LOG_SHIP_INTERVAL", "2.0"))


def _parse_ids(raw: str) -> list[int]:
    out: list[int] = []
    for part in raw.replace(";", ",").split(","):
        part = part.strip()
        if not part:
            continue
        try:
            out.append(int(part))
        except ValueError:
            pass
    return out


# Необязательный список chat_id-получателей логов (через запятую).
# Пусто = все известные приватные чаты бота.
LOG_CHAT_ALLOWLIST: list[int] = _parse_ids(os.environ.get("LOG_CHAT_ALLOWLIST", ""))

# --- Режим приёма апдейтов: polling | webhook ---
MODE: str = os.environ.get("MODE", "polling").strip().lower()

# --- Webhook (см. docs/telegram/markdown/06-webhooks.md) ---
# Публичный HTTPS-URL, на который Telegram шлёт апдейты (локальный путь берётся из него).
WEBHOOK_URL: str = os.environ.get("WEBHOOK_URL", "").strip()
WEBHOOK_HOST: str = os.environ.get("WEBHOOK_HOST", "0.0.0.0")
WEBHOOK_PORT: int = int(os.environ.get("WEBHOOK_PORT", "8443"))
WEBHOOK_MAX_CONNECTIONS: int = int(os.environ.get("WEBHOOK_MAX_CONNECTIONS", "40"))
WEBHOOK_SECRET_FILE: Path = DATA_DIR / "webhook_secret"
# Прямой TLS (если бот сам терминирует HTTPS, без обратного прокси):
WEBHOOK_TLS_CERT: str = os.environ.get("WEBHOOK_TLS_CERT", "").strip()
WEBHOOK_TLS_KEY: str = os.environ.get("WEBHOOK_TLS_KEY", "").strip()
# Публичный сертификат для загрузки в Telegram (для self-signed) — параметр certificate:
WEBHOOK_CERTIFICATE: str = os.environ.get("WEBHOOK_CERTIFICATE", "").strip()


def masked_token() -> str:
    """Токен для логов: виден только числовой id бота, секрет скрыт."""
    if not BOT_TOKEN:
        return "<НЕ ЗАДАН>"
    return f"{BOT_TOKEN.split(':', 1)[0]}:***"


def require_token() -> str:
    if not BOT_TOKEN:
        raise SystemExit(
            "TELEGRAM_BOT_TOKEN не задан. Укажите его в .env или переменной окружения."
        )
    return BOT_TOKEN


def webhook_secret() -> str:
    """Секрет для заголовка X-Telegram-Bot-Api-Secret-Token.

    Берётся из WEBHOOK_SECRET, иначе генерируется и сохраняется в data/ (стабилен
    между перезапусками). Символы token_urlsafe (A-Z a-z 0-9 _ -) допустимы в Bot API.
    """
    explicit = os.environ.get("WEBHOOK_SECRET", "").strip()
    if explicit:
        return explicit
    if WEBHOOK_SECRET_FILE.exists():
        cached = WEBHOOK_SECRET_FILE.read_text(encoding="utf-8").strip()
        if cached:
            return cached
    import secrets
    value = secrets.token_urlsafe(32)
    WEBHOOK_SECRET_FILE.parent.mkdir(parents=True, exist_ok=True)
    WEBHOOK_SECRET_FILE.write_text(value, encoding="utf-8")
    return value
