"""Конфигурация control-API. Переменные с префиксом MESYNC_; токены ботов
переиспользуем из max_sync/telegram_sync (их .env уже загружен теми пакетами).
"""
from __future__ import annotations

import os
import secrets
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[2]


def _load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_dotenv(ROOT / ".env")


def _env_float(name: str, default: float) -> float:
    """Число с плавающей точкой из env; пустое/некорректное значение → default
    (мисконфиг одной переменной не должен ронять импорт всего пакета)."""
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _env_int(name: str, default: int) -> int:
    """Целое из env; пустое/некорректное значение → default."""
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


# --- HTTP-сервер control-API ---
API_HOST: str = os.environ.get("MESYNC_API_HOST", "0.0.0.0")
API_PORT: int = int(os.environ.get("MESYNC_API_PORT", "8090"))

# --- Хранилище ---
DATA_DIR: Path = Path(os.environ.get("MESYNC_DATA_DIR", str(ROOT / "data" / "control")))
STATE_FILE: Path = DATA_DIR / "control.json"
# PostgreSQL включается либо единым DSN, либо набором отдельных параметров. Отдельные
# параметры удобнее для Docker Compose: пароль не нужно URL-кодировать. Пустой host/DSN
# сохраняет прежний файловый backend для локального запуска и тестов.
DATABASE_URL: str = os.environ.get("MESYNC_DATABASE_URL", "").strip()
POSTGRES_HOST: str = os.environ.get("MESYNC_POSTGRES_HOST", "").strip()
POSTGRES_PORT: int = _env_int("MESYNC_POSTGRES_PORT", 5432)
POSTGRES_DB: str = os.environ.get("MESYNC_POSTGRES_DB", "mesync").strip() or "mesync"
POSTGRES_USER: str = os.environ.get("MESYNC_POSTGRES_USER", "mesync").strip() or "mesync"
POSTGRES_PASSWORD: str = os.environ.get("MESYNC_POSTGRES_PASSWORD", "")

# --- Токены ботов (для проверки подписи и отправки OTP) ---
TELEGRAM_BOT_TOKEN: str = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
MAX_BOT_TOKEN: str = os.environ.get("MAX_BOT_TOKEN", "").strip()

# --- Публичная конфигурация ---
# Значения намеренно не содержат production-реквизитов по умолчанию. Backend подставляет
# их в frontend при запуске, поэтому один образ можно настраивать разными env-файлами.
def _http_url(value: str, default: str = "") -> str:
    candidate = str(value or "").strip().rstrip("/")
    try:
        parsed = urlsplit(candidate)
    except ValueError:
        return default
    return candidate if parsed.scheme in {"http", "https"} and parsed.netloc else default


def _asset_url(value: str) -> str:
    candidate = str(value or "").strip()
    if candidate.startswith("/") and not candidate.startswith("//"):
        return candidate
    return _http_url(candidate)


APP_URL: str = _http_url(
    os.environ.get("MESYNC_APP_URL", "http://localhost:8090"),
    "http://localhost:8090",
)
BOT_URLS: dict[str, str] = {
    "max": _http_url(os.environ.get("MESYNC_MAX_BOT_URL", "")),
    "tg": _http_url(os.environ.get("MESYNC_TG_BOT_URL", "")),
}


def _handle_from_url(value: str) -> str:
    try:
        segment = unquote(urlsplit(value).path.rstrip("/").rsplit("/", 1)[-1]).strip()
    except ValueError:
        return ""
    return f"@{segment.lstrip('@')}" if segment else ""


BOT_HANDLES: dict[str, str] = {m: _handle_from_url(url) for m, url in BOT_URLS.items()}

# --- Поддержка пользователей ---
SUPPORT_TG_URL: str = _http_url(os.environ.get("MESYNC_SUPPORT_TG_URL", ""))
SUPPORT_TG_HANDLE: str = _handle_from_url(SUPPORT_TG_URL)
SUPPORT_EMAIL: str = os.environ.get("MESYNC_SUPPORT_EMAIL", "").strip()

# --- Публичные реквизиты владельца текущего развёртывания ---
LEGAL_PROVIDER_NAME_RU: str = os.environ.get("MESYNC_LEGAL_PROVIDER_NAME_RU", "").strip()
LEGAL_PROVIDER_NAME_EN: str = os.environ.get("MESYNC_LEGAL_PROVIDER_NAME_EN", "").strip()
LEGAL_TAX_ID: str = os.environ.get("MESYNC_LEGAL_TAX_ID", "").strip()
LEGAL_REGISTRATION_ID: str = os.environ.get("MESYNC_LEGAL_REGISTRATION_ID", "").strip()

# --- Сервисный лог-канал (Telegram) ---
# Служебный TG-канал для отчётов об ошибках (сообщения пользователей не хранятся,
# поэтому отчёт несёт контекст сам: отправитель-ссылка, правило «источник → приёмник»,
# само сообщение, текст ошибки). Пусто → сервисный лог выключен.
SERVICE_LOG_CHAT_ID: str = os.environ.get("MESYNC_SERVICE_LOG_CHAT_ID", "").strip()
SERVICE_LOG_MAX_PER_MINUTE: int = int(os.environ.get("MESYNC_SERVICE_LOG_MAX_PER_MINUTE", "20"))

# --- Ownership-файлы обоих ботов (источник правды по привязкам чатов) ---
MAX_OWNERSHIP_FILE: Path = Path(os.environ.get("MAX_OWNERSHIP_FILE", str(ROOT / "data" / "max" / "ownership.json")))
TG_OWNERSHIP_FILE: Path = Path(os.environ.get("TG_OWNERSHIP_FILE", str(ROOT / "data" / "ownership.json")))
TG_CONTENT_FILE: Path = Path(os.environ.get("TG_CONTENT_FILE", str(TG_OWNERSHIP_FILE.parent / "content.jsonl")))

# --- Параметры продукта ---
BOT_NAME: str = os.environ.get("MESYNC_BOT_NAME", "MeSync").strip() or "MeSync"
BOT_AVATAR_URL: str = _asset_url(os.environ.get("MESYNC_BOT_AVATAR_URL", ""))

# --- Публичная посадочная страница ---
_default_landing_description = (
    f"{BOT_NAME} синхронизирует сообщения и посты между групповыми чатами и каналами "
    "MAX и Telegram, сохраняя форматирование, фото, видео и файлы.")
LANDING_DESCRIPTION: str = os.environ.get(
    "MESYNC_LANDING_DESCRIPTION", _default_landing_description,
).strip() or _default_landing_description
LANDING_OFFER_TITLE: str = os.environ.get(
    "MESYNC_LANDING_OFFER_TITLE", "7 дней бесплатно").strip()
LANDING_OFFER_TEXT: str = os.environ.get(
    "MESYNC_LANDING_OFFER_TEXT",
    "Новым пользователям после входа и подключения автопродления. Сейчас 0 ₽.",
).strip()
LANDING_ANALYTICS_NOTICE: str = os.environ.get(
    "MESYNC_LANDING_ANALYTICS_NOTICE",
    "Находясь на этом сайте, вы соглашаетесь на сбор аналитических данных.",
).strip()

# VK Ads использует публичный числовой ID Счётчика Mail (Top.Mail.Ru). Пустой или
# некорректный ID полностью отключает загрузку внешнего скрипта и отправку целей.
_vk_ads_pixel_id = os.environ.get("MESYNC_VK_ADS_PIXEL_ID", "").strip()
VK_ADS_PIXEL_ID: str = (
    _vk_ads_pixel_id if _vk_ads_pixel_id.isascii() and _vk_ads_pixel_id.isdigit() else "")
VK_ADS_UTM_SOURCE: str = os.environ.get(
    "MESYNC_VK_ADS_UTM_SOURCE", "vkads").strip() or "vkads"
VK_ADS_UTM_MEDIUM: str = os.environ.get(
    "MESYNC_VK_ADS_UTM_MEDIUM", "cpc").strip() or "cpc"

RULE_LIMIT: int = int(os.environ.get("MESYNC_RULE_LIMIT", "10"))
TRAFFIC_LIMIT_BYTES: int = int(os.environ.get("MESYNC_TRAFFIC_LIMIT_BYTES", str(500 * 1024 ** 3)))  # 0,5 ТБ
TOPUP_BYTES: int = int(os.environ.get("MESYNC_TOPUP_BYTES", str(100 * 1024 ** 3)))                   # 100 ГБ
TOPUP_PRICE_RUB: int = int(os.environ.get("MESYNC_TOPUP_PRICE_RUB", "100"))

# --- Перенос медиа между мессенджерами (кросс-мессенджер MAX↔TG) ---
# Потолок размера одного медиа при кросс-мессенджерном переносе через скачивание+
# перезагрузку (MAX→TG, TG→MAX). Внутри одного мессенджера (MAX→MAX, TG→TG) лимита нет —
# там переиспользуется token/file_id на стороне платформы, файл не перекачивается.
# По умолчанию = жёсткий предел ОБЛАЧНОГО Telegram Bot API (multipart-загрузка: 50 МБ
# на не-фото, сверено с docs/telegram/.../04-api-reference.md «Sending files»). С
# ЛОКАЛЬНЫМ Bot API сервером в режиме --local (TELEGRAM_API_BASE → свой сервер) Telegram
# принимает загрузку до 2000 МБ и отдаёт скачивание без лимита — тогда поднимите эту переменную
# (например, до 2_097_152_000 = 2000 МБ), и кросс-мессенджер будет ограничен ТОЛЬКО
# трафиком. См. deploy/telegram-bot-api/README.md.
TG_UPLOAD_MAX_BYTES: int = int(os.environ.get("MESYNC_TG_UPLOAD_MAX_BYTES", str(50 * 1024 * 1024)))


# Ожидание обработки вложения на стороне MAX (TG→MAX и MAX→MAX).
# Видео/аудио и крупные файлы MAX обрабатывает АСИНХРОННО уже ПОСЛЕ загрузки (docs-api
# POST/uploads → раздел «Обработка файлов»): если отправить сообщение с их token сразу,
# приходит ошибка `attachment.not.ready` (`errors.process.attachment.*.not_processed`).
# Документация прямо рекомендует: «повторите попытку через некоторое время, увеличивая
# интервал с каждой попыткой».
# Этот список — растущие паузы (в секундах) между повторами отправки. Используется двояко:
#   • при `attachment.not.ready` (MAX ещё обрабатывает медиа) повторяем БЕЗ ограничения по
#     времени — паузы растут по списку и далее держатся на последнем значении (опрос, пока MAX
#     не завершит обработку); цикл завершается ТОЛЬКО успехом («отправлено») или иной ошибкой;
#   • при транзиентных сбоях отправки (5xx сервера, сеть, неоднозначный ответ) даём ОГРАНИЧЕННОЕ
#     число повторов (= длина списка), затем деградируем до текста со ссылкой на оригинал.
# По умолчанию 2,4,8,16,30 (далее опрос обработки каждые 30 с). Переопределяется списком секунд
# через переменную MESYNC_MAX_ATTACH_RETRY_DELAYS (например, "2,4,8,16,30,60").
def _parse_delays(raw: str | None, default: tuple[float, ...]) -> tuple[float, ...]:
    if not raw:
        return default
    out: list[float] = []
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            value = float(part)
        except ValueError:
            continue
        if value >= 0:
            out.append(value)
    return tuple(out) if out else default


MAX_ATTACHMENT_RETRY_DELAYS: tuple[float, ...] = _parse_delays(
    os.environ.get("MESYNC_MAX_ATTACH_RETRY_DELAYS"), (2.0, 4.0, 8.0, 16.0, 30.0))

# --- Напоминания о незавершённой регистрации ---
# Пользователь мог открыть MAX-бота по deep link, но не завершить вход в mini-app.
# Напоминания идут только по registration_leads без подтверждённой identity.
REGISTRATION_REMINDER_DELAYS: tuple[float, ...] = _parse_delays(
    os.environ.get("MESYNC_REGISTRATION_REMINDER_DELAYS"), (1800.0, 86400.0))
# Период запуска воркера по wall-clock сетке от 00:00: 1800 = 00:00, 00:30, 01:00...
REGISTRATION_REMINDER_INTERVAL: float = _env_float("MESYNC_REGISTRATION_REMINDER_INTERVAL", 1800.0)
REGISTRATION_REMINDER_BATCH: int = _env_int("MESYNC_REGISTRATION_REMINDER_BATCH", 50)

PRICE_RUB: int = int(os.environ.get("MESYNC_PRICE_RUB", "299"))

# --- Яндекс Маркет: автоматическая выдача цифровых кодов (DBS / ACTIVATION_CODE) ---
# Главный выключатель интеграции. false отключает webhook и воркер, даже если все
# реквизиты ниже заполнены; уже выданные коды активации продолжают работать.
YANDEX_MARKET_ENABLED: bool = os.environ.get(
    "MESYNC_YANDEX_MARKET_ENABLED", "true").strip().lower() in {"1", "true", "yes", "on"}
# API-Key с доступом inventory-and-order-processing; пустой набор выключает воркер.
YANDEX_MARKET_API_BASE: str = os.environ.get(
    "MESYNC_YANDEX_MARKET_API_BASE", "https://api.partner.market.yandex.ru").rstrip("/")
YANDEX_MARKET_API_KEY: str = os.environ.get("MESYNC_YANDEX_MARKET_API_KEY", "").strip()
YANDEX_MARKET_BUSINESS_ID: int = _env_int("MESYNC_YANDEX_MARKET_BUSINESS_ID", 0)
YANDEX_MARKET_CAMPAIGN_ID: int = _env_int("MESYNC_YANDEX_MARKET_CAMPAIGN_ID", 0)
YANDEX_MARKET_SKU: str = os.environ.get(
    "MESYNC_YANDEX_MARKET_SKU", "MESYNC-SMART-1M").strip()
# Секретная часть URL уведомлений: /api/yandex-market/notifications/<secret>.
YANDEX_MARKET_WEBHOOK_SECRET: str = os.environ.get(
    "MESYNC_YANDEX_MARKET_WEBHOOK_SECRET", "").strip()
YANDEX_MARKET_ENFORCE_IP: bool = os.environ.get(
    "MESYNC_YANDEX_MARKET_ENFORCE_IP", "true").lower() in {"1", "true", "yes", "on"}
YANDEX_MARKET_TIMEOUT: float = _env_float("MESYNC_YANDEX_MARKET_TIMEOUT", 15.0)

# --- ЮKassa (приём платежей; сверено с docs/yookassa) ---
# Ключи магазина (Basic auth `shopId:секретный ключ`). Пусто → оплата выключена,
# /api/pay/* отвечает 503. НЕ путать с TELEGRAM_YOOKASSA_PROVIDER_TOKEN (Telegram Payments).
YOOKASSA_SHOP_ID: str = os.environ.get("YOOKASSA_SHOP_ID", "").strip()
YOOKASSA_SECRET_KEY: str = os.environ.get("YOOKASSA_SECRET_KEY", "").strip()
YOOKASSA_API_BASE: str = os.environ.get("YOOKASSA_BASE_URL", "https://api.yookassa.ru").strip()
# Страница «вернитесь в приложение» после привязки/оплаты на странице ЮKassa
# (redirect-сценарий нулевой привязки: docs/yookassa .../save-without-payment/bank-card.md).
PAY_RETURN_URL: str = os.environ.get(
    "MESYNC_PAY_RETURN_URL", f"{APP_URL}/pay-return.html").strip()
# Публичный адрес mini-app (кнопка «Открыть приложение» в приветствии бота) и
# раздел юридических документов (пользовательское соглашение + политика
# конфиденциальности, /legal/ с переключателем RU/EN; старый /terms.html — редирект).
TERMS_URL: str = os.environ.get("MESYNC_TERMS_URL", f"{APP_URL}/legal/?lang=ru").strip()
# Текущие юридические редакции. Frontend показывает interstitial до принятия именно этих
# версий; backend проверяет их перед оплатой, привязкой источников и созданием правил.
LEGAL_TERMS_VERSION: str = os.environ.get("MESYNC_LEGAL_TERMS_VERSION", "2026-07-08").strip()
LEGAL_PRIVACY_VERSION: str = os.environ.get("MESYNC_LEGAL_PRIVACY_VERSION", "2026-07-11").strip()
LEGAL_TERMS_URL: str = os.environ.get("MESYNC_LEGAL_TERMS_URL", f"{APP_URL}/legal/terms/?lang=ru").strip()
LEGAL_PRIVACY_URL: str = os.environ.get("MESYNC_LEGAL_PRIVACY_URL", f"{APP_URL}/legal/privacy/?lang=ru").strip()
YANDEX_MARKET_ACTIVATION_URL: str = os.environ.get(
    "MESYNC_YANDEX_MARKET_ACTIVATION_URL", f"{APP_URL}/ya_market").strip()
# Пробный период за привязку автоплатежа (дней) — только для новых пользователей.
TRIAL_DAYS: int = int(os.environ.get("MESYNC_TRIAL_DAYS", "7"))
# Окно ранней РУЧНОЙ оплаты (дней до истечения): без автопродления кнопка «Продлить»
# появляется заранее, месяц добавляется к дате истечения (дни не сгорают).
RENEW_WINDOW_DAYS: int = int(os.environ.get("MESYNC_RENEW_WINDOW_DAYS", "5"))
# Ретраи неудачного автопродления: каждые RENEW_RETRY_SECONDS, максимум RENEW_MAX_ATTEMPTS.
RENEW_RETRY_SECONDS: int = int(os.environ.get("MESYNC_RENEW_RETRY_SECONDS", str(4 * 3600)))
RENEW_MAX_ATTEMPTS: int = int(os.environ.get("MESYNC_RENEW_MAX_ATTEMPTS", "6"))
OTP_TTL: int = int(os.environ.get("MESYNC_OTP_TTL", "600"))            # 10 минут
OTP_RESEND: int = int(os.environ.get("MESYNC_OTP_RESEND", "59"))       # таймер повторной отправки
CODE_TTL: int = int(os.environ.get("MESYNC_CODE_TTL", "600"))         # код привязки источника, 10 минут

# --- Реестр отправленных ботом сообщений (защита от петли/самосинхронизации) ---
# Бот не синхронизирует сообщения, которые создал сам (по (messenger, chat_id, mid)). Реестр
# персистентный (переживает рестарты — ловит и поздние пересылки своих сообщений).
SENT_INDEX_FILE: Path = DATA_DIR / "sent_index.json"
SENT_INDEX_TTL: int = int(os.environ.get("MESYNC_SENT_INDEX_TTL", str(90 * 86400)))   # 90 дней
SENT_INDEX_MAX: int = int(os.environ.get("MESYNC_SENT_INDEX_MAX", "200000"))          # максимум записей

# --- Маппинг source↔target сообщений (для синхронизации правок/удалений) ---
MESSAGE_MAP_FILE: Path = DATA_DIR / "message_map.json"
MESSAGE_MAP_TTL: int = int(os.environ.get("MESYNC_MESSAGE_MAP_TTL", str(7 * 86400)))  # 7 дней
MESSAGE_MAP_MAX: int = int(os.environ.get("MESYNC_MESSAGE_MAP_MAX", "200000"))

# --- ИИ-модерация (MiniMax, Anthropic-совместимый API; сверено с docs/minimax) ---
# Ключ MiniMax (для Token Plan — Subscription Key). Пусто → ИИ-модерация выключена:
# classify() отвечает "unavailable", политику пропуска решает вызывающая сторона.
MODERATION_API_KEY: str = os.environ.get("MESYNC_MODERATION_API_KEY", "").strip()
MODERATION_BASE_URL: str = os.environ.get(
    "MESYNC_MODERATION_BASE_URL", "https://api.minimax.io/anthropic").strip()
# MiniMax-M3: thinking по умолчанию выключен → быстрый короткий ответ-вердикт.
MODERATION_MODEL: str = os.environ.get("MESYNC_MODERATION_MODEL", "MiniMax-M3").strip()
# Безопасный парс: пустое/некорректное значение не должно ронять импорт control-API.
MODERATION_TIMEOUT: float = _env_float("MESYNC_MODERATION_TIMEOUT", 45.0)
# Обрезка входного текста (лимиты платформ 4096/4000 — с запасом).
MODERATION_MAX_INPUT_CHARS: int = _env_int("MESYNC_MODERATION_MAX_INPUT", 6000)
# Температура классификатора: 0 → детерминированный вердикт (docs/minimax: диапазон [0,2]).
MODERATION_TEMPERATURE: float = _env_float("MESYNC_MODERATION_TEMPERATURE", 0.0)
# Потолок ответа модели: с запасом на короткий JSON-вердикт (reason ограничен промптом),
# чтобы JSON не обрывался на середине (иначе вердикт не распарсится).
MODERATION_MAX_TOKENS: int = _env_int("MESYNC_MODERATION_MAX_TOKENS", 512)
# Стоп-словарь (предфильтр перед ИИ; редактируемый YAML, горячая перезагрузка).
MODERATION_STOPLIST_FILE: str = os.environ.get(
    "MESYNC_MODERATION_STOPLIST", str(ROOT / "data" / "moderation" / "stoplist.yaml")).strip()
# Режим предотправочного гейта:
#   off     — гейт выключен (по умолчанию: без явного включения ничего не фильтруем);
#   shadow  — классифицируем подозрительные (хит стоп-словаря), нарушения ЛОГируем в
#             сервисный канал, но ДОСТАВЛЯЕМ (обкатка без риска для живого сервиса);
#   enforce — нарушения НЕ доставляются + уведомление владельцу.
# Валидация: неизвестное значение (опечатка) → "off" + предупреждение в лог, чтобы гейт не
# оказался ТИХО выключенным, когда оператор думает, что он включён.
_MODERATION_GATE_MODES = ("off", "shadow", "enforce")
MODERATION_GATE_MODE: str = os.environ.get("MESYNC_MODERATION_GATE_MODE", "off").strip().lower()
if MODERATION_GATE_MODE not in _MODERATION_GATE_MODES:
    import logging as _logging
    _logging.getLogger("control.config").warning(
        "MESYNC_MODERATION_GATE_MODE=%r не распознан (ожидается off/shadow/enforce) — гейт ВЫКЛЮЧЕН",
        MODERATION_GATE_MODE)
    MODERATION_GATE_MODE = "off"
# Кулдаун после исчерпания квоты окна Token Plan (2056): не долбим мёртвый API, пока окно
# не сбросится. classify() короткозамыкается на unavailable без запроса всё это время.
MODERATION_QUOTA_COOLDOWN: float = _env_float("MESYNC_MODERATION_QUOTA_COOLDOWN", 300.0)

# --- Жалобы на пересланный контент (этап 3): ссылка «Пожаловаться» + очередь обработки ---
# Функция целиком за флагом: пусто/false → в подпись копий ссылка НЕ добавляется, эндпоинт
# /api/report отвечает 503, воркер очереди не запускается (безопасный дефолт до готовности).
MODERATION_REPORTS_ENABLED: bool = os.environ.get(
    "MESYNC_MODERATION_REPORTS", "false").lower() in {"1", "true", "yes", "on"}
# Антиспам жалоб: не более N обращений за окно (секунд) на одного жалобщика (по его
# messenger-идентичности из подписанного initData). По образцу кодов активации.
MODERATION_REPORT_MAX: int = _env_int("MESYNC_MODERATION_REPORT_MAX", 3)
MODERATION_REPORT_WINDOW: int = _env_int("MESYNC_MODERATION_REPORT_WINDOW", 600)
# Потолок длины текста жалобы (свободное описание нарушения от жалобщика).
MODERATION_REPORT_MAX_DESC: int = _env_int("MESYNC_MODERATION_REPORT_MAX_DESC", 1000)
# Потолок текстового снимка исходного сообщения, который кладётся в message_map для жалоб
# на Telegram-only копии. Telegram Bot API не умеет перечитывать сообщение по chat_id/message_id,
# поэтому для таких жалоб нужен bounded snapshot того текста, который бот видел при доставке.
MODERATION_REPORT_TEXT_SNAPSHOT_LIMIT: int = _env_int(
    "MESYNC_MODERATION_REPORT_TEXT_SNAPSHOT_LIMIT", 4096)

# --- Безопасность ---
# Ключ машинных админ-эндпоинтов (X-Admin-Key) — генерация кодов активации из CLI и т.п.
# Пусто → эти эндпоинты выключены (503). НЕ для браузера (браузерная панель — по паролю ниже).
ADMIN_KEY: str = os.environ.get("MESYNC_ADMIN_KEY", "").strip()

# --- Браузерная админ-панель (этап 4) ---
# Один администратор, вход по паролю (cookie-сессия). Пусто → панель выключена:
# /api/admin/* отвечают 503, /admin не отдаётся. Пароль в UI/ответах API не показывается.
ADMIN_PASSWORD: str = os.environ.get("MESYNC_ADMIN_PASSWORD", "").strip()
ADMIN_SESSION_TTL: int = int(os.environ.get("MESYNC_ADMIN_SESSION_TTL", str(12 * 3600)))  # 12 ч
# Секрет для подписи JWT-сессий (стабилен между перезапусками).
SESSION_SECRET_FILE: Path = DATA_DIR / "session_secret"
SESSION_TTL: int = int(os.environ.get("MESYNC_SESSION_TTL", str(60 * 86400)))  # 60 дней
# Небезопасный режим: пропускать проверку подписи хоста (только для dev/демо).
AUTH_INSECURE: bool = os.environ.get("MESYNC_AUTH_INSECURE", "false").lower() in {"1", "true", "yes", "on"}

# CORS (для отладки фронта на другом origin)
CORS_ORIGINS: list[str] = [o.strip() for o in os.environ.get("MESYNC_CORS_ORIGINS", "*").split(",") if o.strip()]


def session_secret() -> str:
    explicit = os.environ.get("MESYNC_SESSION_SECRET", "").strip()
    if explicit:
        return explicit
    if SESSION_SECRET_FILE.exists():
        SESSION_SECRET_FILE.chmod(0o600)
        cached = SESSION_SECRET_FILE.read_text(encoding="utf-8").strip()
        if cached:
            return cached
    value = secrets.token_hex(32)
    SESSION_SECRET_FILE.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(
        SESSION_SECRET_FILE,
        os.O_WRONLY | os.O_CREAT | os.O_TRUNC,
        0o600,
    )
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as secret_file:
            fd = -1
            secret_file.write(value)
    finally:
        if fd >= 0:
            os.close(fd)
    return value
