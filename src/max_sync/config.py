"""Конфигурация бота MAX: загрузка настроек из окружения / .env.

Токен НИКОГДА не хардкодится — только переменная окружения MAX_BOT_TOKEN
или файл .env (он в .gitignore). Все переменные этого бота имеют префикс MAX_,
чтобы не пересекаться с настройками telegram_sync в общем .env.

Сверено с docs/max/ (база API `platform-api.max.ru`, авторизация заголовком
`Authorization: <token>`, Webhook через POST /subscriptions, секрет в заголовке
`X-Max-Bot-Api-Secret`).
"""
from __future__ import annotations

import os
from pathlib import Path

# Корень репозитория: src/max_sync/config.py -> ../../ == корень
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


def _flag(name: str, default: str = "true") -> bool:
    return os.environ.get(name, default).lower() in {"1", "true", "yes", "on"}


# --- Токен и Bot API ---
BOT_TOKEN: str = os.environ.get("MAX_BOT_TOKEN", "").strip()
# Базовый домен Bot API MAX (см. docs/max/markdown/docs-api.md).
API_BASE: str = os.environ.get("MAX_API_BASE", "https://platform-api.max.ru").rstrip("/")

# --- Long polling (GET /updates; см. docs/max/markdown/docs-api/methods/GET/updates.md) ---
# timeout [0..90], limit [1..1000].
LONG_POLL_TIMEOUT: int = int(os.environ.get("MAX_LONG_POLL_TIMEOUT", "90"))
GET_UPDATES_LIMIT: int = int(os.environ.get("MAX_GET_UPDATES_LIMIT", "100"))

# Все типы событий MAX (поле update_type объекта Update) — чтобы получить ВСЁ.
# Источник: docs/max/markdown/docs-api/objects/Update.md.
UPDATE_TYPES: list[str] = [
    "bot_added", "bot_removed", "bot_started", "bot_stopped",
    "chat_title_changed",
    "dialog_cleared", "dialog_muted", "dialog_unmuted", "dialog_removed",
    "message_created", "message_edited", "message_removed", "message_callback",
    "user_added", "user_removed",
]

# --- Скачивание медиа (best-effort: у входящих вложений MAX может быть прямой url) ---
DOWNLOAD_MEDIA: bool = _flag("MAX_DOWNLOAD_MEDIA", "false")
MAX_DOWNLOAD_BYTES: int = int(os.environ.get("MAX_DOWNLOAD_BYTES", str(50 * 1024 * 1024)))

# --- Синхронизация: репост сообщений/постов привязанного чата в личку владельца ---
# В MAX нет copyMessage, поэтому репост идёт нативной пересылкой
# (NewMessageLink type=forward, mid). См. updates.py.
MIRROR_TO_OWNER: bool = _flag("MAX_MIRROR_TO_OWNER", "true")

# --- Хранилище (отдельный каталог, чтобы не пересекаться с telegram_sync) ---
DATA_DIR: Path = Path(os.environ.get("MAX_DATA_DIR", str(ROOT / "data" / "max")))
RAW_UPDATES_FILE: Path = DATA_DIR / "updates.jsonl"
CONTENT_FILE: Path = DATA_DIR / "content.jsonl"
MARKER_FILE: Path = DATA_DIR / "marker"
MEDIA_DIR: Path = DATA_DIR / "media"
KNOWN_CHATS_FILE: Path = DATA_DIR / "known_chats.json"
OWNERSHIP_FILE: Path = DATA_DIR / "ownership.json"

# --- Отправка логов в MAX (пользователям, у кого есть диалог с ботом) ---
LOG_TO_MESSENGER: bool = _flag("MAX_LOG_TO_MESSENGER", "true")
LOG_TO_MESSENGER_LEVEL: str = os.environ.get("MAX_LOG_LEVEL", "INFO").upper()
LOG_SHIP_INTERVAL: float = float(os.environ.get("MAX_LOG_SHIP_INTERVAL", "2.0"))


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


# Необязательный список user_id-получателей логов. Пусто = все известные диалоги.
LOG_CHAT_ALLOWLIST: list[int] = _parse_ids(os.environ.get("MAX_LOG_CHAT_ALLOWLIST", ""))

# --- Режим приёма событий: polling | webhook ---
MODE: str = os.environ.get("MAX_MODE", "polling").strip().lower()

# --- Webhook (см. docs/max/markdown/docs-api/methods/POST/subscriptions.md) ---
# Публичный HTTPS-URL (порт всегда 443, валидный CA-сертификат). Локальный путь
# берётся из этого URL. Запросы MAX приходят на него POST-ом с объектом Update.
WEBHOOK_URL: str = os.environ.get("MAX_WEBHOOK_URL", "").strip()
WEBHOOK_HOST: str = os.environ.get("MAX_WEBHOOK_HOST", "0.0.0.0")
WEBHOOK_PORT: int = int(os.environ.get("MAX_WEBHOOK_PORT", "8089"))
WEBHOOK_SECRET_FILE: Path = DATA_DIR / "webhook_secret"
# Прямой TLS (если бот сам терминирует HTTPS, без обратного прокси):
WEBHOOK_TLS_CERT: str = os.environ.get("MAX_WEBHOOK_TLS_CERT", "").strip()
WEBHOOK_TLS_KEY: str = os.environ.get("MAX_WEBHOOK_TLS_KEY", "").strip()


def masked_token() -> str:
    """Токен для логов: видно только хвост, секрет скрыт."""
    if not BOT_TOKEN:
        return "<НЕ ЗАДАН>"
    return f"***{BOT_TOKEN[-4:]}" if len(BOT_TOKEN) > 4 else "***"


def require_token() -> str:
    if not BOT_TOKEN:
        raise SystemExit(
            "MAX_BOT_TOKEN не задан. Укажите его в .env или переменной окружения."
        )
    return BOT_TOKEN


def webhook_secret() -> str:
    """Секрет для заголовка X-Max-Bot-Api-Secret.

    Берётся из MAX_WEBHOOK_SECRET, иначе генерируется и сохраняется в data/max/
    (стабилен между перезапусками). Допустимый формат secret — ^[a-zA-Z0-9_-]{5,256}$;
    используем hex, чтобы гарантированно попасть в разрешённые символы.
    """
    explicit = os.environ.get("MAX_WEBHOOK_SECRET", "").strip()
    if explicit:
        return explicit
    if WEBHOOK_SECRET_FILE.exists():
        cached = WEBHOOK_SECRET_FILE.read_text(encoding="utf-8").strip()
        if cached:
            return cached
    import secrets
    value = secrets.token_hex(24)
    WEBHOOK_SECRET_FILE.parent.mkdir(parents=True, exist_ok=True)
    WEBHOOK_SECRET_FILE.write_text(value, encoding="utf-8")
    return value
