"""Интеграция control-API с ботами MAX/Telegram (для оркестратора run_app.py).

Содержит:
- RuleDispatcher — движок синхронизации по правилам: на входящее сообщение в
  привязанном источнике вычисляет цели (rules.targets_for), проверяет гейт
  подписки и остаток трафика, отправляет чистую копию в целевые источники,
  учитывает трафик и пишет уведомления о порогах;
- фабрики хуков для OwnershipManager (коды mini-app) и для api (доставка OTP,
  выход из чата).

Все сетевые вызовы — async. Кросс-мессенджер медиа (MAX↔TG) переносится РЕАЛЬНО, через
скачивание+перезагрузку (токены вложений между платформами не переносимы): TG→MAX —
скачать из Telegram и загрузить в MAX (token), MAX→TG — скачать из MAX и загрузить в
Telegram байтами (multipart). Если скачать/загрузить не удалось или исчерпан трафик —
медиа заменяется ссылкой на оригинал (паритет с поведением «без медиа → ссылка»).
"""
from __future__ import annotations

import asyncio
import contextvars
import logging
import mimetypes
import re
from typing import Any, Callable

from . import config, rules as rules_mod, stickers
from .reports import make_report_token, report_deeplink
from .source_ids import (make_chat_key, make_source_id, parse_chat_key,
                         telegram_send_thread_param, topic_title)
from .store import ControlStore

log = logging.getLogger("control.integration")

LINK_NOTE = "Полное сообщение можно увидеть"
_MESSENGER_NOTE_LABEL = {"max": "max", "tg": "telegram"}
BOT_HANDLES = config.BOT_HANDLES   # единый источник (см. control.config)
# Подпись «Пожаловаться» в копии: ссылка на mini-app с жалобой (модерация, этап 3).
REPORT_LABEL = "Пожаловаться"
FORWARDED_BUTTON_PAYLOAD = "mesync:button_unavailable"
FORWARDED_BUTTON_NOTICE = "Действие кнопки доступно только в исходном сообщении."

_pending_map_source: contextvars.ContextVar[tuple[str, str, str] | None] = \
    contextvars.ContextVar("_pending_map_source", default=None)
_pending_map_text: contextvars.ContextVar[str | None] = \
    contextvars.ContextVar("_pending_map_text", default=None)


# ---------------- конвертация форматирования для Telegram ----------------
_TG_UNSUPPORTED = re.compile(r"</?(?:mark|h1)>")


# Упоминания пользователей кросс-платформенно не кликабельны: ссылка MAX (max://user/…)
# не работает в Telegram, а tg://user?id=… — в MAX (проверено вживую: чужая схема молча
# отбрасывается, и упоминание теряет любое выделение). Поэтому при доставке В ДРУГОЙ
# мессенджер такую ссылку заменяем на жирный текст — имя сохраняется и визуально выделено.
# Ссылки внутри своего мессенджера (MAX→MAX max://, TG→TG tg://) не трогаем: там схема рабочая.
_SCHEME_LINK_RE = {
    "max": re.compile(r'<a href="max://[^"]*">(.*?)</a>', re.DOTALL),
    "tg": re.compile(r'<a href="tg://[^"]*">(.*?)</a>', re.DOTALL),
}


def _strip_scheme_links(html: str, scheme: str) -> str:
    """Заменить <a href="<scheme>://…">X</a> на <b>X</b> (схема не работает в целевом
    мессенджере). Остальные ссылки (http/https и «родная» схема цели) сохраняются."""
    return _SCHEME_LINK_RE[scheme].sub(r"<b>\1</b>", html)


def html_for_telegram(html: str) -> str:
    """Привести наш HTML (из markup MAX) к подмножеству, понятному Telegram.

    MAX-конвертер может выдавать <mark> и <h1>, которых нет в Telegram HTML —
    заменяем открывающие на <b>, закрывающие на </b> (выделение сохраняется).
    Упоминания MAX (max://user/…) Telegram не понимает — заменяем на жирное имя.
    """
    if not html:
        return html
    html = html.replace("<mark>", "<b>").replace("</mark>", "</b>")
    html = html.replace("<h1>", "<b>").replace("</h1>", "</b>")
    html = _strip_scheme_links(html, "max")
    return html


def html_for_max(html: str) -> str:
    """Привести наш HTML (из entities Telegram) к понятному MAX подмножеству.

    Упоминания Telegram (tg://user?id=…) MAX не понимает — заменяем на жирное имя
    (проверено вживую: MAX молча отбрасывает чужую схему). Базовые теги (<b>/<i>/<u>/<s>/
    <code>/<pre>/<a href=http…>/<blockquote>) MAX принимает как есть.
    """
    if not html:
        return html
    html = _strip_scheme_links(html, "tg")
    return html


def _tg_code_markers_for_max(html: str) -> str:
    """Сделать Telegram code/pre визуально заметными в MAX-клиентах.

    MAX API принимает <code>/<pre> и возвращает markup=monospaced, но некоторые клиенты
    отображают его почти как обычный текст. Для TG→MAX добавляем текстовые маркеры,
    при этом оставляем HTML-теги, чтобы серверное formatting/markup не терялось.
    """
    if not html:
        return html
    return (html
            .replace("<pre>", "```\n<pre>")
            .replace("</pre>", "</pre>\n```")
            .replace("<code>", "`<code>")
            .replace("</code>", "</code>`"))


def _esc_html(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _esc_attr(s: str) -> str:
    """Экранирование значения HTML-атрибута (href) — дополнительно к _esc_html кавычки."""
    return _esc_html(s).replace('"', "&quot;")


def _sender_link(source_messenger: str, sender_id: Any, username: str | None) -> str | None:
    """URL профиля отправителя на его родной платформе."""
    if sender_id is None:
        return None
    if source_messenger == "tg":
        if username:
            return f"https://t.me/{username}"
        return f"tg://user?id={sender_id}"
    if source_messenger == "max":
        return f"max://user/{sender_id}"
    return None


_SIGNATURE_SEPARATOR_CHAR = "-"
_SIGNATURE_SEPARATOR_MIN = 19
# У Bot API/MAX API нет понятия ширины строки: перенос зависит от клиента и экрана.
# Держим практический потолок, чтобы разделитель оставался одной строкой в обычных клиентах.
_SIGNATURE_SEPARATOR_MAX = 64


def _signature_separator(*chunks: str | None) -> str:
    """Разделитель под самый длинный видимый ряд исходного сообщения, но в одну строку."""
    longest = 0
    for chunk in chunks:
        if not chunk:
            continue
        for line in str(chunk).splitlines():
            longest = max(longest, len(line.rstrip()))
    size = min(max(longest, _SIGNATURE_SEPARATOR_MIN), _SIGNATURE_SEPARATOR_MAX)
    return _SIGNATURE_SEPARATOR_CHAR * size


def _reply_quote_plain(quote: dict[str, Any] | None) -> str:
    if not quote:
        return ""
    parts = [str(p) for p in (quote.get("from"), quote.get("text")) if p]
    return "\n".join(parts)


def _footer_html(name: str | None, name_link: str | None, source_name: str | None,
                 report_link: str | None, separator: str) -> str:
    """Подпись внизу копии: «Автор <имя>» + «Пожаловаться»."""
    parts: list[str] = []
    if name:
        esc = _esc_html(name)
        author = f'<a href="{_esc_attr(name_link)}">{esc}</a>' if name_link else f"<b>{esc}</b>"
        parts.append(f"Автор {author}")
    if report_link:
        parts.append(f'<a href="{_esc_attr(report_link)}">{REPORT_LABEL}</a>')
    return ("\n\n" + " · ".join(parts)) if parts else ""


def _footer_plain(name: str | None, source_name: str | None, has_report: bool,
                  separator: str) -> str:
    """Видимая длина футера (подпись + «Пожаловаться») — для лимита caption Telegram."""
    parts: list[str] = []
    if name:
        parts.append(f"Автор {name}")
    if has_report:
        parts.append(REPORT_LABEL)
    return ("\n\n" + " · ".join(parts)) if parts else ""


# Метки мессенджеров в отчётах сервисного лога.
_MSN_LABEL = {"tg": "TG", "max": "MAX"}


def _svc_media_note(f: dict[str, Any]) -> str | None:
    """Короткая сводка медиа сообщения для отчёта сервисного лога: «photo×2, video×1».
    Считаем по нормализованному media; если его нет (MAX без скачивания) — по attachments
    (служебные inline_keyboard не считаем). None — сообщение без медиа."""
    kinds: dict[str, int] = {}
    items = f.get("media") or []
    if not items:
        items = [a for a in (f.get("attachments") or [])
                 if a.get("type") not in ("inline_keyboard",)]
    for m in items:
        k = str(m.get("type") or m.get("kind") or "media")
        kinds[k] = kinds.get(k, 0) + 1
    if not kinds:
        return None
    return ", ".join(f"{k}×{n}" for k, n in kinds.items())


# Legacy helpers for old forward attribution tests/history. New outgoing copies do not render
# «Переслано из …»; forward metadata remains internal for loop protection and diagnostics.
_FWD_PREFIX = "↪️ Переслано из «"
_FWD_SUFFIX = "»"


def _forward_html(name: str) -> str:
    """HTML-строка legacy-атрибуции форварда + пустая строка перед телом."""
    return f"{_FWD_PREFIX}<b>{_esc_html(name)}</b>{_FWD_SUFFIX}\n\n"


def _forward_plain(name: str) -> str:
    """Видимая (без тегов) legacy-атрибуция форварда."""
    return f"{_FWD_PREFIX}{name}{_FWD_SUFFIX}\n\n"


def _tg_forward_name(origin: dict[str, Any] | None) -> str | None:
    """Имя первоисточника форварда из Telegram `forward_origin` (объект MessageOrigin) или None.

    Сверено с docs/telegram/.../04-api-reference.md (MessageOrigin): user → имя `sender_user`;
    hidden_user → `sender_user_name`; chat → `sender_chat.title`; channel → `chat.title`.
    forward_origin есть ТОЛЬКО у настоящих форвардов (собственные посты канала его не имеют),
    поэтому ложных пометок нет."""
    if not isinstance(origin, dict):
        return None
    t = origin.get("type")
    if t == "user":
        u = origin.get("sender_user") or {}
        return " ".join(p for p in (u.get("first_name"), u.get("last_name")) if p) \
            or u.get("username") or None
    if t == "hidden_user":
        return origin.get("sender_user_name") or None
    if t == "chat":
        return (origin.get("sender_chat") or {}).get("title") or None
    if t == "channel":
        return (origin.get("chat") or {}).get("title") or None
    return None


def _max_forward_name(norm: dict[str, Any]) -> str | None:
    """Имя первоисточника форварда для MAX — ТОЛЬКО когда у `link` есть `sender` (реальный
    форвард от пользователя). Важно: посты MAX-канала тоже приходят боту как link.type=forward
    (контент в link.message), но БЕЗ sender — их помечать нельзя, иначе каждый пост канала
    получил бы ложную пометку (проверено на реальном сырьё). Форвард из ДРУГОГО канала MAX
    отдаёт лишь link.chat_id без названия → имени нет → пропускаем."""
    if not norm.get("is_forward"):
        return None
    sender = (norm.get("link") or {}).get("sender") or {}
    if not sender:
        return None
    return " ".join(p for p in (sender.get("first_name"), sender.get("last_name")) if p) \
        or sender.get("name") or sender.get("username") or None


def _report_has_media(f: dict[str, Any]) -> bool:
    """Есть ли в исходном сообщении контент, который ИИ-текстом не проверит.

    Inline keyboard — не медиа; реальные вложения уже нормализуются в `media`, но оставляем
    fallback на `attachments` для MAX raw/link-сценариев.
    """
    media = f.get("media")
    if isinstance(media, list) and any(isinstance(m, dict) for m in media):
        return True
    attachments = f.get("attachments")
    if not isinstance(attachments, list):
        return False
    return any(isinstance(a, dict) and a.get("type") != "inline_keyboard" for a in attachments)


def _tg_migrated_to(exc: Exception) -> Any | None:
    """Если это ошибка Bot API «group chat was upgraded to a supergroup chat», вернуть НОВЫЙ
    chat_id супергруппы — Telegram кладёт его в `parameters.migrate_to_chat_id` ответа (сверено с
    docs/telegram ResponseParameters.migrate_to_chat_id). Иначе None. Duck-typing по `.parameters`,
    чтобы не зависеть жёстко от класса TelegramError."""
    params = getattr(exc, "parameters", None)
    if isinstance(params, dict):
        return params.get("migrate_to_chat_id")
    return None


def _tg_forward_from_bot(origin: dict[str, Any] | None, bot_id: Any) -> bool:
    """True, если пользователь переслал сообщение, исходно отправленное ЭТИМ Telegram-ботом.

    Это намеренно гасится как собственный контент бота: даже если действие сделал пользователь,
    источник оригинала — bot user, и повторная синхронизация может выглядеть как реакция бота
    на своё же сообщение.
    """
    if not isinstance(origin, dict) or bot_id is None:
        return False
    if origin.get("type") == "user":
        return (origin.get("sender_user") or {}).get("id") == bot_id
    return False


def _max_forward_from_bot(norm: dict[str, Any], bot_id: Any) -> bool:
    """True, если пересланное сообщение MAX исходно отправлено ЭТИМ БОТОМ (защита от петли).
    У реального форварда от пользователя автор оригинала — в link.sender (объект User с
    user_id; сверено с docs/max Message.link=LinkedMessage, sender=User). Посты канала тоже
    приходят как forward, но БЕЗ sender → user_id=None ≠ bot_id, ложных срабатываний нет."""
    if bot_id is None or not norm.get("is_forward"):
        return False
    sender = (norm.get("link") or {}).get("sender") or {}
    return sender.get("user_id") == bot_id


def _tg_message_link(chat: dict[str, Any] | None, message_id: Any) -> str | None:
    """Публичная ссылка на сообщение Telegram (для гиперссылки «оригинал»), или None.

    Публичный чат с username → https://t.me/<username>/<id>; приватные супергруппа/канал
    (id вида -100…) → https://t.me/c/<id без -100>/<id>. У обычных групп и ЛС постоянных
    ссылок на сообщение нет — возвращаем None (тогда заметка будет без гиперссылки)."""
    chat = chat or {}
    if not message_id:
        return None
    username = chat.get("username")
    if username:
        return f"https://t.me/{username}/{message_id}"
    cid, ctype = chat.get("id"), chat.get("type")
    if ctype in ("supergroup", "channel") and isinstance(cid, int):
        s = str(cid)
        if s.startswith("-100"):
            return f"https://t.me/c/{s[4:]}/{message_id}"
    return None


# Тип Telegram MessageEntity → наш markup-тип (markup_to_html понимает их и даёт HTML,
# валидный и для Telegram, и для MAX). Гиперссылки (text_link/text_mention) → ссылка.
_TG_ENTITY_TYPE = {
    "bold": "strong", "italic": "emphasized", "underline": "underline",
    "strikethrough": "strikethrough", "code": "monospaced", "pre": "preformatted",
    "blockquote": "quote", "expandable_blockquote": "quote",
}


def tg_entities_to_html(text: str, entities: list[dict[str, Any]] | None,
                        markup_to_html) -> tuple[str, bool]:
    """Telegram MessageEntity[] → (html, has_formatting).

    Офсеты Telegram — в UTF-16 code units (как markup MAX), поэтому переиспользуем
    markup_to_html, преобразовав сущности в markup-форму. Сохраняет гиперссылки
    (text_link → <a href>, text_mention → tg://user) и базовое форматирование;
    неизвестные типы (url/mention/hashtag/spoiler/custom_emoji) → текст как есть
    (URL Telegram распознаёт автоматически, текст не теряется)."""
    markup: list[dict[str, Any]] = []
    for e in entities or []:
        if not isinstance(e, dict):
            continue
        off, ln, et = e.get("offset"), e.get("length"), e.get("type")
        if not isinstance(off, int) or not isinstance(ln, int) or ln <= 0:
            continue
        if et == "text_link" and e.get("url"):
            markup.append({"type": "link", "from": off, "length": ln, "url": e["url"]})
        elif et == "text_mention" and (e.get("user") or {}).get("id") is not None:
            markup.append({"type": "link", "from": off, "length": ln,
                           "url": f"tg://user?id={e['user']['id']}"})
        elif et in _TG_ENTITY_TYPE:
            markup.append({"type": _TG_ENTITY_TYPE[et], "from": off, "length": ln})
    return markup_to_html(text, markup)


def _chunk_buttons(buttons: list[dict[str, Any]], max_per_row: int) -> list[list[dict[str, Any]]]:
    return [buttons[i:i + max_per_row] for i in range(0, len(buttons), max_per_row)]


def _tg_button_url(button: dict[str, Any]) -> str | None:
    """URL-представление Telegram-кнопки, если оно есть и переносимо."""
    if button.get("url"):
        return str(button["url"])
    login_url = button.get("login_url")
    if isinstance(login_url, dict) and login_url.get("url"):
        return str(login_url["url"])
    web_app = button.get("web_app")
    if isinstance(web_app, dict) and web_app.get("url"):
        return str(web_app["url"])
    return None


def _tg_reply_markup_to_max_attachment(reply_markup: dict[str, Any] | None) -> dict[str, Any] | None:
    """Telegram InlineKeyboardMarkup -> MAX inline_keyboard attachment.

    Callback/служебные Telegram-кнопки нельзя честно выполнить в MAX от имени исходного бота,
    поэтому переносим их как видимые no-op callback-кнопки с понятным ответом на нажатие.
    URL/login/web_app кнопки сохраняем как настоящие ссылки.
    """
    if not isinstance(reply_markup, dict):
        return None
    rows = reply_markup.get("inline_keyboard")
    if not isinstance(rows, list):
        return None
    out_rows: list[list[dict[str, Any]]] = []
    for row in rows[:30]:
        if not isinstance(row, list):
            continue
        converted: list[dict[str, Any]] = []
        has_link = False
        for button in row:
            if not isinstance(button, dict):
                continue
            text = button.get("text")
            if not text:
                continue
            url = _tg_button_url(button)
            if url:
                converted.append({"type": "link", "text": str(text), "url": url})
                has_link = True
            else:
                converted.append({"type": "callback", "text": str(text),
                                  "payload": FORWARDED_BUTTON_PAYLOAD})
        if converted:
            out_rows.extend(_chunk_buttons(converted, 3 if has_link else 7))
            if len(out_rows) >= 30:
                out_rows = out_rows[:30]
                break
    if not out_rows:
        return None
    return {"type": "inline_keyboard", "payload": {"buttons": out_rows}}


def _max_inline_keyboard_attachment(attachments: list[dict[str, Any]] | None) -> dict[str, Any] | None:
    """Вернуть MAX inline_keyboard attachment из нормализованных вложений, если он есть."""
    for att in attachments or []:
        if not isinstance(att, dict) or att.get("type") != "inline_keyboard":
            continue
        raw = att.get("raw") if isinstance(att.get("raw"), dict) else None
        payload = (raw or att).get("payload")
        buttons = payload.get("buttons") if isinstance(payload, dict) else None
        if isinstance(buttons, list) and buttons:
            return {"type": "inline_keyboard", "payload": {"buttons": buttons}}
    return None


def _max_inline_keyboard_to_tg_reply_markup(attachments: list[dict[str, Any]] | None
                                            ) -> dict[str, Any] | None:
    """MAX inline_keyboard attachment -> Telegram InlineKeyboardMarkup."""
    max_keyboard = _max_inline_keyboard_attachment(attachments)
    payload = (max_keyboard or {}).get("payload")
    rows = payload.get("buttons") if isinstance(payload, dict) else None
    if not isinstance(rows, list):
        return None
    out_rows: list[list[dict[str, Any]]] = []
    for row in rows:
        if not isinstance(row, list):
            continue
        converted: list[dict[str, Any]] = []
        for button in row:
            if not isinstance(button, dict):
                continue
            text = button.get("text")
            if not text:
                continue
            url = button.get("url")
            if button.get("type") == "link" and url:
                converted.append({"text": str(text), "url": str(url)})
            else:
                converted.append({"text": str(text), "callback_data": FORWARDED_BUTTON_PAYLOAD})
        if converted:
            out_rows.extend(_chunk_buttons(converted, 8))
    if not out_rows:
        return None
    return {"inline_keyboard": out_rows}


def _tg_reply_markup_for_tg(reply_markup: dict[str, Any] | None) -> dict[str, Any] | None:
    """Telegram InlineKeyboardMarkup для повторной отправки ботом.

    URL-кнопки сохраняются. Все действия, которые должны прийти исходному боту
    (callback_data, switch_inline, pay, copy_text и т.п.), заменяются на безопасный no-op.
    """
    max_keyboard = _tg_reply_markup_to_max_attachment(reply_markup)
    if max_keyboard is None:
        return None
    return _max_inline_keyboard_to_tg_reply_markup([{"type": "inline_keyboard", "raw": max_keyboard}])


# Тип медиа Telegram → тип загрузки MAX (POST /uploads?type=…). Остальное → file.
# Стикеры здесь НЕ маппятся напрямую — у них особый план загрузки (см. _tg_upload_plan:
# статичный webp → image, анимированный/видео → превью-image; "sticker" оставлен как
# безопасный фоллбэк, если когда-то план вернёт его в общую ветку).
_TG_MEDIA_TO_MAX_UPLOAD = {
    "photo": "image", "image": "image",
    "video": "video", "video_note": "video", "animation": "video",
    "audio": "audio", "voice": "audio",
    "document": "file", "sticker": "file", "live_photo": "image",
}

# Расширение по типу загрузки MAX — для имени файла, если у TG-медиа его нет.
_MAX_UPLOAD_EXT = {"image": "jpg", "video": "mp4", "audio": "ogg", "file": "bin"}

# Тип медиа MAX → способ отправки в Telegram (метод и тип InputMedia для альбома).
_MAX_TO_TG_KIND = {"image": "photo", "video": "video", "audio": "audio", "file": "document"}
# Расширение имени файла по типу отправки Telegram (если у MAX-медиа нет имени).
_TG_KIND_EXT = {"photo": "jpg", "video": "mp4", "audio": "mp3", "document": "bin"}
_MAX_ATT_BYTES = "_mesync_bytes"
# Потолок скачивания медиа из MAX для загрузки в Telegram — конфигурируемый
# (config.TG_UPLOAD_MAX_BYTES). По умолчанию = multipart-лимит ОБЛАЧНОГО Telegram (50 МБ);
# с локальным Bot API сервером поднимается до 2000 МБ (см. config). Что не влезло —
# деградирует до текст+ссылки (файл не теряется).
# Лимит подписи к медиа в Telegram (символов); текст длиннее шлём отдельным сообщением.
_TG_CAPTION_LIMIT = 1024


# ---------------- извлечение полей из нормализованного сообщения ----------------
def _max_fields(norm: dict[str, Any]) -> dict[str, Any]:
    sender = norm.get("sender") or {}
    name = " ".join(p for p in (sender.get("first_name"), sender.get("last_name")) if p) \
        or sender.get("username") or None
    return {
        "chat_id": norm.get("chat_id"),
        "mid": norm.get("mid"),
        "sender_id": norm.get("sender_id"),
        "sender_username": sender.get("username"),
        "is_group": norm.get("chat_type") == "chat",
        "sender_name": name,
        "forward_from": _max_forward_name(norm),
        "reply": norm.get("reply"),
        "text": norm.get("text"),
        "markup": norm.get("markup"),
        "attachments": norm.get("attachments") or [],
        "media": norm.get("media") or [],
        "url": norm.get("url") or (norm.get("raw") or {}).get("url"),
    }


def _tg_sender(norm: dict[str, Any]) -> tuple[dict[str, Any], str | None]:
    chat = norm.get("chat") or {}
    frm = norm.get("from") or {}
    name = " ".join(p for p in (frm.get("first_name"), frm.get("last_name")) if p) \
        or frm.get("username") or None
    if not name:
        # Пост канала / отправлено от имени чата: персонального отправителя нет — подписываем
        # именем автора поста (author_signature) либо названием канала (sender_chat/chat title).
        name = norm.get("author_signature") or (norm.get("sender_chat") or {}).get("title") \
            or chat.get("title")
    return frm, name


def _tg_fields(norm: dict[str, Any]) -> dict[str, Any]:
    chat = norm.get("chat") or {}
    frm, name = _tg_sender(norm)
    return {
        "chat_id": chat.get("id"),
        "source_name": chat.get("title"),
        "message_id": norm.get("message_id"),
        "thread_id": norm.get("message_thread_id"),
        "sender_id": frm.get("id"),
        "sender_username": frm.get("username"),
        "is_group": chat.get("type") in ("group", "supergroup"),
        "sender_name": name,
        "forward_from": _tg_forward_name(norm.get("forward_origin")),
        "reply": norm.get("reply"),
        "text": norm.get("text") or norm.get("caption"),
        "text_kind": norm.get("text_kind"),
        "entities": norm.get("entities") or [],
        "reply_markup": norm.get("reply_markup"),
        "media": norm.get("media") or [],
        "url": _tg_message_link(chat, norm.get("message_id")),
    }


def _utf16_len(s: str) -> int:
    """Длина строки в UTF-16 code units — как Telegram считает caption/text (а не в
    code points: эмодзи/символы вне BMP занимают 2 юнита). Сверено с офсетами markup."""
    return len(s.encode("utf-16-le")) // 2


def _tg_album_caption_ok(send_text: str | None, original_text: str | None,
                         *, reply_markup: Any = None) -> bool:
    """Можно ли оставить текст caption у Telegram media group, не дробя пост на два.

    Если исходного текста нет, а `send_text` состоит только из footer-а (Автор/Пожаловаться),
    держим прежнее поведение: медиа отдельно, footer отдельным сообщением после альбома.
    """
    if not send_text or not original_text or not str(original_text).strip():
        return False
    if reply_markup is not None:
        return False  # sendMediaGroup не поддерживает inline keyboard на группе
    return _utf16_len(str(send_text)) <= _TG_CAPTION_LIMIT


def _media_bytes(media: list[dict[str, Any]]) -> int:
    total = 0
    for m in media or []:
        size = m.get("file_size") or (m.get("raw") or {}).get("file_size")
        if isinstance(size, (int, float)):
            total += int(size)
    return total


def _fmt_bytes_ru(n: int) -> str:
    """Объём по-русски для уведомлений о трафике: «0,5 ТБ», «100 ГБ», «37 МБ». ТБ — от
    ~0,45 ТиБ: дефолтный лимит 500 ГиБ ≈ 0,488 ТиБ должен показываться «0,5 ТБ», как
    в описании тарифа."""
    tb = n / 1024 ** 4
    if tb >= 0.45:
        s = f"{tb:.1f}".rstrip("0").rstrip(".")
        return f"{s.replace('.', ',')} ТБ"
    gb = n / 1024 ** 3
    if gb >= 1:
        s = f"{gb:.1f}".rstrip("0").rstrip(".")
        return f"{s.replace('.', ',')} ГБ"
    return f"{max(1, round(n / 1024 ** 2))} МБ"


def _declared_size(m: dict[str, Any]) -> int | None:
    """Заявленный размер медиа в байтах (если источник его сообщает) — для пре-флайт-проверки
    «не качать заведомо слишком большой файл». Telegram кладёт file_size почти всегда; у
    MAX-вложений размера в payload нет (тогда None → проверяем по Content-Length при скачивании)."""
    size = m.get("file_size") or (m.get("raw") or {}).get("file_size")
    return int(size) if isinstance(size, (int, float)) else None


def _max_public_attachment(att: dict[str, Any]) -> dict[str, Any]:
    """Attachment для MAX API без внутренних полей учёта."""
    return {k: v for k, v in att.items() if k != _MAX_ATT_BYTES}


def _max_att_bytes(att: dict[str, Any]) -> int:
    n = att.get(_MAX_ATT_BYTES)
    return int(n) if isinstance(n, (int, float)) and n > 0 else 0


def _max_needs_file_split(atts: list[dict[str, Any]]) -> bool:
    """MAX возвращает 400/proto.payload, если file-вложение не единственное в сообщении."""
    return any(a.get("type") == "file" for a in atts) and len(atts) > 1


def _max_has_media_attachment(atts: list[dict[str, Any]] | None) -> bool:
    return any(isinstance(a, dict) and a.get("type") != "inline_keyboard" for a in (atts or []))


def _max_sent_attachment_types(sent: Any) -> list[str]:
    out: list[str] = []
    for item in RuleDispatcher._sent_items(sent):
        if not isinstance(item, dict):
            continue
        msg = item.get("message") if isinstance(item.get("message"), dict) else item
        body = (msg or {}).get("body") or {}
        for att in body.get("attachments") or []:
            if isinstance(att, dict) and att.get("type"):
                out.append(str(att["type"]))
    return out


def _max_send_transient(exc: Exception) -> bool:
    """ТРАНЗИЕНТНЫЙ ли это сбой отправки в MAX (НЕ «ещё обрабатывается» — тот обрабатывается
    отдельной, безлимитной по времени веткой). Транзиентные → ограниченное число повторов,
    затем деградация. Сигналы:
      • HTTP 5xx — временная ошибка сервера MAX;
      • нет status_code — сетевой сбой/таймаут httpx (HTTP-ответа не было; MaxClient уже
        исчерпал свои ретраи и пробросил исключение без .code/.status_code);
      • code == None — тело ответа MAX не распозналось (мог быть инфраструктурный 4xx или
        нераспарсенный not.ready) → даём ограниченный шанс, а не теряем медиа молча.
    Явная 4xx с РАСПОЗНАННЫМ кодом (бот исключён и т.п.) — ПОСТОЯННАЯ ошибка, не повторяем."""
    status = getattr(exc, "status_code", None)
    if isinstance(status, int) and status >= 500:
        return True
    if status is None:
        return True
    return getattr(exc, "code", None) is None


class RuleDispatcher:
    def __init__(self, store: ControlStore, *, max_client=None, tg_client=None,
                 max_bot_id: Any = None, tg_bot_id: Any = None,
                 sent_index=None, message_map=None, settings=None) -> None:
        self.store = store
        # Runtime-настройки админ-панели (settings-store): режим гейта модерации и вкл/выкл
        # жалоб читаются отсюда с фолбэком на config. None → только config.
        self.settings = settings
        self.max_client = max_client
        self.tg_client = tg_client
        self.bot_ids = {"max": max_bot_id, "tg": tg_bot_id}
        # Реестр сообщений, СОЗДАННЫХ ботом (messenger, chat_id, mid) — чтобы не синхронизировать
        # свои же сообщения (петля двунаправленного правила; свой пост канала, у которого нет
        # sender_id; пересланный пользователем пост, созданный ботом). См. control.sent_index.
        self.sent_index = sent_index
        self.message_map = message_map
        # Провайдер названия источника (messenger, chat_id)->title|None — для подписи постов
        # КАНАЛОВ, у которых в сообщении нет имени отправителя (выставляется в run_app).
        self.source_title = None
        # Хуки уведомления о сбое доставки (ставятся в run_app):
        #   delivery_error_cb(messenger, chat_id, account_id) -> ref|None — ОТПРАВИТЬ владельцу
        #     «не удалось отправить, проверьте права» (+ inline-кнопка «Скрыть»); вернуть ссылку
        #     на отправленное сообщение (для будущего удаления) либо None.
        #   delivery_clear_cb(messenger, chat_id, ref) — УДАЛИТЬ это сообщение (при успехе доставки).
        # None → молча.
        self.delivery_error_cb: Callable[..., Any] | None = None
        self.delivery_clear_cb: Callable[..., Any] | None = None
        # Проактивное уведомление о ПОТЕРЕ прав в TG-чате (из my_chat_member, см. on_tg_rights_change):
        #   tg_rights_warn_cb(chat_id, account_id, reason) -> ref|None — ОТПРАВИТЬ владельцу «изъято
        #   право <reason>, верните его» (+ кнопка «Скрыть», ре-армящая эту цель). Снимается тем же
        #   delivery_clear_cb. None → молча. Текст отличается от реактивного (там «проверьте права»).
        self.tg_rights_warn_cb: Callable[..., Any] | None = None
        # Координатор миграции группа→супергруппа (ставится в run_app): помимо правил/warning'а
        # (это делает on_tg_chat_migrated) переносит ещё и ВЛАДЕНИЕ (ownership) на новый id.
        # Зовётся из реактивного self-heal в _route. None → миграцию правит только сам диспетчер.
        self.chat_migrated_cb: Callable[..., Any] | None = None
        # --- ИИ-модерация (предотправочный гейт по стоп-словарю; этап 2) ---
        # Стоп-словарь — дешёвый предфильтр: хит → синхронная ИИ-проверка → решение.
        # Режим/файл — из config; при MODERATION_GATE_MODE="off" гейт полностью выключен.
        # moderation_block_cb(messenger, chat_id, account_ids, category, reason) — уведомить
        #   владельца «сообщение не переслано модерацией» (ставится в run_app; None → молча).
        try:
            from .stoplist import StopList
            from .moderation import get_moderation_ai
            self._stoplist: Any = StopList(config.MODERATION_STOPLIST_FILE)
            self._moderation: Any = get_moderation_ai()
        except Exception:  # noqa: BLE001 — модерация не должна ронять диспетчер
            log.warning("модерация: инициализация не удалась — гейт выключен", exc_info=True)
            self._stoplist = None
            self._moderation = None
        self.moderation_block_cb: Callable[..., Any] | None = None
        # Сервисный лог-канал (control.service_log.ServiceLog, ставится в run_app): отчёты об
        # ошибках доставки/правок для разработчиков — отправитель (ссылкой), правило
        # «источник → приёмник», само сообщение, текст ошибки. None → без отчётов.
        self.service_log: Any = None
        # Состояние «инцидента доставки» — ДВА независимых канала уведомления (чат + mini-app):
        #   _warn_notice[(messenger, chat_id)] — живое сообщение-уведомление в ЧАТЕ по этой цели
        #     (ref от delivery_error_cb). Присутствие ключа = уведомление показано → повторно НЕ
        #     слать. Снимается при успехе (сообщение удаляется) или когда пользователь нажал
        #     «Скрыть» в чате (note_chat_warn_hidden) — тогда следующий сбой пришлёт заново.
        #   _rule_fail_dests[rule_id] — какие цели правила сейчас в сбое; баннер mini-app гаснет,
        #     когда множество пустеет (корректно для двусторонних правил: успех одной стороны не
        #     гасит предупреждение о сбое другой).
        #   _warned_rules — правила с поднятым флагом баннера (чтобы гасить при успехе без обращения
        #     к стору на каждое сообщение); инициализируется из стора → переживает рестарт.
        self._warn_notice: dict[tuple[str, str], Any] = {}
        self._rule_fail_dests: dict[str, set[tuple[str, str]]] = {}
        self._warned_rules: set[str] = {
            rid for rid, r in store.table("rules").items() if r.get("delivery_warn")}
        # Фоновые задачи диспетчера (fire-and-forget), держим ссылки до завершения.
        self._bg_tasks: set[asyncio.Task] = set()
        # Telegram сам режет большие альбомы на media_group по 10 элементов. Чтобы footer
        # (Автор/Пожаловаться) не повторялся на каждом куске, запоминаем предыдущий полный chunk.
        self._tg_album_chunk_state: dict[tuple[str, str, str, str], dict[str, Any]] = {}
        # lazy-импорт хелперов чистой копии MAX (есть только в окружении с max_sync)
        try:
            from max_sync.updates import markup_to_html, _rebuild_attachments
            self._markup_to_html = markup_to_html
            self._rebuild_attachments = _rebuild_attachments
        except Exception:  # noqa: BLE001
            self._markup_to_html = None
            self._rebuild_attachments = None
        # UploadFile — для загрузки медиа MAX в Telegram байтами (multipart).
        try:
            from telegram_sync.client import UploadFile
            self._UploadFile = UploadFile
        except Exception:  # noqa: BLE001
            self._UploadFile = None

    # ---- реестр «своих» сообщений (защита от петли/самосинхронизации) ----
    def note_tg_sent(self, result: Any) -> None:
        """Запомнить отправленное ботом сообщение Telegram (хук client.on_sent). Результат —
        объект Message (sendMessage/Photo/…) или список (sendMediaGroup); у каждого есть
        chat.id + message_id (сверено с docs/telegram 04-api-reference: объект Message)."""
        items = result if isinstance(result, list) else [result]
        for m in items:
            if not isinstance(m, dict):
                continue
            tgt_chat = (m.get("chat") or {}).get("id")
            tgt_mid = m.get("message_id")
            if self.sent_index is not None:
                self.sent_index.remember("tg", tgt_chat, tgt_mid)
            src = _pending_map_source.get(None)
            if self.message_map is not None and src is not None:
                src_msn, src_chat, src_mid = src
                self.message_map.record(
                    src_msn, src_chat, src_mid, "tg", tgt_chat, tgt_mid,
                    text=_pending_map_text.get(None))

    def note_max_sent(self, result: Any) -> None:
        """Запомнить отправленное ботом сообщение MAX (хук client.on_sent). Результат POST
        /messages — {"message": Message}; mid в body.mid, чат в recipient.chat_id (сверено с
        docs/max objects/Message + методом POST/messages)."""
        if not isinstance(result, dict):
            return
        msg = result.get("message")
        if isinstance(msg, dict):
            tgt_chat = (msg.get("recipient") or {}).get("chat_id")
            tgt_mid = (msg.get("body") or {}).get("mid")
            if self.sent_index is not None:
                self.sent_index.remember("max", tgt_chat, tgt_mid)
            src = _pending_map_source.get(None)
            if self.message_map is not None and src is not None:
                src_msn, src_chat, src_mid = src
                self.message_map.record(
                    src_msn, src_chat, src_mid, "max", tgt_chat, tgt_mid,
                    text=_pending_map_text.get(None))

    def _is_own(self, messenger: str, chat_id: Any, mid: Any) -> bool:
        return self.sent_index is not None and self.sent_index.contains(messenger, chat_id, mid)

    def _tg_msg_is_own(self, chat_id: Any, message_id: Any, forward_origin: Any) -> bool:
        """True, если это сообщение Telegram создано ботом: либо прямой (chat_id, message_id) из
        реестра, либо пользователь переслал созданный ботом ПОСТ КАНАЛА — у MessageOriginChannel
        есть исходные chat+message_id (сверено с docs/telegram MessageOrigin)."""
        if self._is_own("tg", chat_id, message_id):
            return True
        o = forward_origin or {}
        if o.get("type") == "channel":
            return self._is_own("tg", (o.get("chat") or {}).get("id"), o.get("message_id"))
        return False

    def _max_msg_is_own(self, norm: dict[str, Any]) -> bool:
        """True, если это сообщение MAX создано ботом: прямой (chat_id, mid) из реестра ИЛИ
        пересылка/пост канала — оригинал в link.chat_id+link.message.mid (сверено на живом
        сырьё data/max/updates.jsonl: forward несёт chat_id и message.mid оригинала)."""
        if self._is_own("max", norm.get("chat_id"), norm.get("mid")):
            return True
        link = norm.get("link") or {}
        if link.get("type") == "forward":
            return self._is_own("max", link.get("chat_id"), (link.get("message") or {}).get("mid"))
        return False

    # ---- чистая логика принятия решения (тестируется) ----
    def decide(self, source_messenger: str, chat_id: Any,
               thread_id: Any | None = None) -> list[dict[str, Any]]:
        """Цели доставки с учётом гейта подписки и остатка трафика."""
        out: list[dict[str, Any]] = []
        for t in rules_mod.targets_for(self.store, source_messenger, chat_id, thread_id):
            acc = t["account_id"]
            if self.store.subscription(acc).get("status") != "active":
                continue  # подписка не активна → пересылка остановлена
            if self.store.account_blocked(acc):
                continue  # аккаунт заблокирован администратором (модерация)
            hold_rule = self.store.rule(t.get("rule_id"))
            if hold_rule and hold_rule.get("moderation_hold"):
                continue  # правило на модерационной паузе (moderation_hold, не пользовательский paused)
            et = self.store.effective_traffic(acc)
            t = dict(t)
            t["media_allowed"] = bool(et.get("media_allowed"))
            out.append(t)
        return out

    # ---- точки входа для роутеров ботов ----
    async def on_max_message(self, norm: dict[str, Any]) -> None:
        if _max_forward_from_bot(norm, self.bot_ids.get("max")):
            return  # пользователь переслал сообщение этого бота → не синхронизируем (защита от петли)
        if self._max_msg_is_own(norm):
            return  # сообщение создано ЭТИМ ботом (реестр) → не синхронизируем (петля/свой пост канала)
        await self._route("max", _max_fields(norm))

    async def on_tg_message(self, norm: dict[str, Any]) -> None:
        if norm.get("service"):
            return  # служебные Message (join/leave/pin/topic/миграция) не пересылаем по правилам
        f = _tg_fields(norm)
        if f["sender_id"] is not None and f["sender_id"] == self.bot_ids.get("tg"):
            return
        if _tg_forward_from_bot(norm.get("forward_origin"), self.bot_ids.get("tg")):
            return  # пользователь переслал сообщение этого бота → не синхронизируем (свой контент)
        if self._tg_msg_is_own((norm.get("chat") or {}).get("id"), norm.get("message_id"),
                               norm.get("forward_origin")):
            return  # сообщение создано ЭТИМ ботом (реестр) → не синхронизируем (петля/свой пост канала)
        await self._route("tg", f)

    async def on_tg_album(self, album: dict[str, Any]) -> None:
        chat = album.get("chat") or {}
        mids = album.get("message_ids") or []
        parts = album.get("parts") or []
        if parts and _tg_forward_from_bot(parts[0].get("forward_origin"), self.bot_ids.get("tg")):
            return  # пересланный альбом сообщений этого бота → не синхронизируем (свой контент)
        # Альбом, СОЗДАННЫЙ этим ботом (sendMediaGroup) или пересланный пользователем пост-альбом
        # бота: каждая часть несёт свой message_id/forward_origin — достаточно совпадения любой.
        if any(self._tg_msg_is_own(chat.get("id"), p.get("message_id"), p.get("forward_origin"))
               for p in parts) or any(self._is_own("tg", chat.get("id"), mid) for mid in mids):
            return  # сообщение создано ЭТИМ ботом (реестр) → не синхронизируем (петля/свой пост канала)
        sender_part = parts[0] if parts and isinstance(parts[0], dict) else album
        frm, name = _tg_sender(sender_part)
        continuation_root_mid = self._tg_album_continuation_root(album, sender_part)
        caption = album.get("caption")
        caption_entities = album.get("caption_entities") or album.get("entities") or []
        media_count = int(album.get("media_count") or len(album.get("media") or []))
        has_caption = bool(caption and str(caption).strip())
        # Для текстовых альбомов continuation не должен повторять исходный caption/footer.
        # Для пустых больших альбомов footer ставим только на последний неполный chunk:
        # Telegram режет их по 10, а полный chunk может оказаться не последним.
        suppress_footer = (continuation_root_mid is not None) if has_caption else media_count == 10
        f = {"chat_id": chat.get("id"), "sender_id": frm.get("id"),
             "sender_username": frm.get("username"),
             "message_id": mids[0] if mids else None,
             "_map_source_message_id": continuation_root_mid,
             "is_group": chat.get("type") in ("group", "supergroup"),
             "thread_id": album.get("message_thread_id"),
             "sender_name": name,
             "forward_from": _tg_forward_name(parts[0].get("forward_origin")) if parts else None,
             "text": None if suppress_footer else caption,
             "entities": [] if suppress_footer else caption_entities,
             "media": album.get("media") or [],
             "url": _tg_message_link(chat, mids[0] if mids else None),
             "_suppress_footer": suppress_footer}
        await self._route("tg", f)

    def _tg_album_continuation_root(self, album: dict[str, Any],
                                    sender_part: dict[str, Any]) -> int | None:
        """Вернуть root message_id, если это следующий chunk большого Telegram-альбома.

        Bot API не даёт общего идентификатора для пользовательского альбома >10 элементов:
        Telegram присылает соседние media_group_id. Считаем продолжением только строгий случай:
        тот же чат/тема/отправитель/секунда, предыдущий chunk был полным (10), а message_id идут
        подряд. Копии continuation надо записывать в message_map под source первого chunk-а, чтобы
        жалоба с единственного footer-а могла скрыть все части.
        """
        mids: list[int] = []
        for raw_mid in album.get("message_ids") or []:
            try:
                mids.append(int(raw_mid))
            except (TypeError, ValueError):
                pass
        if not mids:
            return None
        chat = album.get("chat") or {}
        sender = sender_part.get("from") if isinstance(sender_part, dict) else None
        sender_chat = sender_part.get("sender_chat") if isinstance(sender_part, dict) else None
        sender_id = (sender or {}).get("id") or (sender_chat or {}).get("id") \
            or (sender_chat or {}).get("title") or ""
        key = (
            str(chat.get("id")),
            str(album.get("message_thread_id") or ""),
            str(sender_id),
            str(album.get("date") or ""),
        )
        first_mid, last_mid = min(mids), max(mids)
        caption = album.get("caption") or ""
        entities = album.get("caption_entities") or album.get("entities") or []
        prev = self._tg_album_chunk_state.get(key)
        continuation = bool(
            prev
            and prev.get("media_count") == 10
            and first_mid == int(prev.get("last_mid", -10_000)) + 1
            and prev.get("caption") == caption
            and prev.get("entities") == entities
        )
        root_mid = int(prev.get("root_mid", first_mid)) if prev else first_mid
        self._tg_album_chunk_state[key] = {
            "last_mid": last_mid,
            "root_mid": root_mid,
            "media_count": int(album.get("media_count") or len(album.get("media") or [])),
            "caption": caption,
            "entities": entities,
        }
        while len(self._tg_album_chunk_state) > 128:
            self._tg_album_chunk_state.pop(next(iter(self._tg_album_chunk_state)), None)
        return root_mid if continuation else None

    async def _route(self, source_messenger: str, f: dict[str, Any]) -> None:
        if f.get("sender_id") is not None and f["sender_id"] == self.bot_ids.get(source_messenger):
            return  # эхо-защита: не синхронизируем свои сообщения
        chat_id = f.get("chat_id")
        if chat_id is None:
            return
        f["source_messenger"] = source_messenger
        if self.source_title is not None:
            try:
                source_key = make_chat_key(chat_id, f.get("thread_id")) \
                    if source_messenger == "tg" else chat_id
                source_name = self.source_title(source_messenger, source_key) or f.get("source_name") or None
                f["source_name"] = source_name
                if not f.get("sender_name"):
                    f["sender_name"] = source_name
            except Exception:  # noqa: BLE001
                pass
        targets = self.decide(source_messenger, str(chat_id), f.get("thread_id"))
        if not targets:
            return
        # Модерация ДО установки _pending_map_source: её админ-отправки (отчёт/уведомление)
        # не должны попасть в message_map как «цели» этого сообщения (иначе правка источника
        # их перезапишет). В enforce нарушение не доставляем и в маппинг не пишем.
        accounts = sorted({t.get("account_id") for t in targets if t.get("account_id")})
        if await self._moderation_blocks(source_messenger, chat_id, f.get("text"), accounts):
            return
        src_mid = f.get("mid") if source_messenger == "max" else (
            f.get("_map_source_message_id") or f.get("message_id"))
        src_token = text_token = None
        if self.message_map is not None and src_mid is not None:
            src_token = _pending_map_source.set((source_messenger, str(chat_id), str(src_mid)))
            text_token = _pending_map_text.set(f.get("text"))
        try:
            for t in targets:
                await self._deliver_to_target(source_messenger, f, t, allow_migrate=True)
        finally:
            if src_token is not None:
                _pending_map_source.reset(src_token)
            if text_token is not None:
                _pending_map_text.reset(text_token)

    def _gate_mode(self) -> str:
        """Режим гейта модерации: runtime-оверрайд из settings-store, иначе дефолт config."""
        if self.settings is not None:
            try:
                return self.settings.get("moderation_gate_mode")
            except Exception:  # noqa: BLE001
                pass
        return config.MODERATION_GATE_MODE

    def _reports_on(self) -> bool:
        """Включены ли жалобы читателей: runtime-оверрайд из settings-store, иначе config."""
        if self.settings is not None:
            try:
                return bool(self.settings.get("moderation_reports_enabled"))
            except Exception:  # noqa: BLE001
                pass
        return config.MODERATION_REPORTS_ENABLED

    def _ai_moderation_on(self) -> bool:
        """Включена ли ИИ-классификация: runtime-оверрайд из settings-store."""
        if self.settings is not None:
            try:
                return bool(self.settings.get("moderation_ai_enabled"))
            except Exception:  # noqa: BLE001
                pass
        return True

    async def _moderation_blocks(self, source_messenger: str, chat_id: Any,
                                 text: Any, account_ids: list[str]) -> bool:
        """Предотправочная модерация текста. Классифицирует ОДИН раз. Возвращает True, только
        если контент НЕ надо пропагировать (нарушение в режиме enforce). Используется и при
        первичной отправке (_route), и при синхронизации правок. Никогда не бросает — fail-open."""
        mode = self._gate_mode()
        if (mode not in ("shadow", "enforce") or not self._ai_moderation_on()
                or self._stoplist is None or self._moderation is None):
            return False
        try:
            if not text or not str(text).strip():
                return False  # медиа без текста — этап 2 работает по тексту (caption учитывается)
            if not self._moderation.enabled:
                return False  # ИИ выключен → предфильтр без арбитра не блокирует
            hits = self._stoplist.match(str(text))
            hits.discard("profanity")  # мат не эскалирует к ИИ и не блокирует
            if not hits:
                return False  # чистое сообщение — доставляем мгновенно (подавляющее большинство)
            verdict = await self._moderation.classify(str(text))
            if not verdict.is_violation:
                return False  # ok/unsure/unavailable → доставляем (fail-open)
            blocked = (mode == "enforce")
            await self._on_moderation_block(source_messenger, chat_id, account_ids, verdict,
                                            sorted(hits), text=str(text), blocked=blocked)
            return blocked
        except Exception:  # noqa: BLE001 — гейт никогда не роняет пересылку
            log.warning("модерация-гейт: сбой (fail-open)", exc_info=True)
            return False

    async def _on_moderation_block(self, source_messenger: str, chat_id: Any,
                                   account_ids: list[str], verdict: Any,
                                   hit_categories: list[str], *, text: str, blocked: bool) -> None:
        """Реакция на нарушение: всегда — отчёт оператору (сервисный канал); при реальной
        блокировке (enforce) — уведомление владельцу(ам). Ошибки глотаем (не роняем гейт)."""
        cat = verdict.category or (hit_categories[0] if hit_categories else "other")
        reason = verdict.reason or "нарушение правил"
        # 1) Отчёт оператору сервиса (наблюдаемость в обоих режимах). ServiceLog.report
        # экранирует title/quote/error, но НЕ строки lines — экранируем динамику сами.
        svc = self.service_log
        if svc is not None:
            try:
                action = "ЗАБЛОКИРОВАНО" if blocked else "shadow (доставлено)"
                await svc.report(
                    f"🛡 Модерация: {action}",
                    [f"Источник: {_esc_html(source_messenger)} chat={_esc_html(str(chat_id))}",
                     f"Категория: {_esc_html(cat)} (стоп-словарь: {_esc_html(', '.join(hit_categories))})",
                     f"Причина ИИ: {_esc_html(reason)}",
                     f"Аккаунты: {_esc_html(', '.join(account_ids)) or '—'}"],
                    quote=str(text or "")[:400])
            except Exception:  # noqa: BLE001
                log.warning("модерация: отчёт в сервисный канал не удался", exc_info=True)
        # 2) Уведомление владельцу — только при фактической блокировке.
        if blocked and self.moderation_block_cb is not None:
            try:
                await self.moderation_block_cb(source_messenger, chat_id,
                                               account_ids, cat, reason)
            except Exception:  # noqa: BLE001
                log.warning("модерация: уведомление владельцу не удалось", exc_info=True)

    def _target_key(self, t: dict[str, Any]) -> tuple[str, str]:
        return (t["messenger"], make_chat_key(
            t["chat_id"], t.get("thread_id") if t.get("messenger") == "tg" else None))

    async def _deliver_to_target(self, source_messenger: str, f: dict[str, Any],
                                 t: dict[str, Any], *, allow_migrate: bool) -> None:
        """Доставка в одну цель с учётом трафика и warning'а. При ошибке «группа повышена до
        супергруппы» (Telegram сменил id) — перепривязываем чат и ОДИН раз повторяем на новый id
        (self-heal: правило/владение чинятся сами, даже если сервисный сигнал миграции был пропущен)."""
        key = self._target_key(t)
        try:
            used = await self._deliver(source_messenger, f, t)
        except Exception as exc:  # noqa: BLE001
            new_id = _tg_migrated_to(exc) if t.get("messenger") == "tg" else None
            if allow_migrate and new_id is not None and str(new_id) != str(t["chat_id"]):
                log.info("rule %s: TG-цель %s повышена до супергруппы %s — перепривязка и повтор",
                         t.get("rule_id"), t["chat_id"], new_id)
                await self._apply_chat_migration(t["chat_id"], new_id)
                retry_target = {**t, "chat_id": str(new_id)}
                if retry_target.get("messenger") == "tg" and retry_target.get("thread_id") is None:
                    retry_target["thread_id"] = "1"
                await self._deliver_to_target(source_messenger, f, retry_target,
                                              allow_migrate=False)   # один повтор, без рекурсии
                return
            log.warning("rule %s доставка не удалась", t.get("rule_id"), exc_info=True)
            # Отчёт разработчикам в сервисный лог-канал: сообщения не хранятся, поэтому
            # весь контекст (отправитель, правило, само сообщение, ошибка) едет в отчёте.
            await self._svc_delivery_error(source_messenger, f, t, exc)
            # Правило НЕ отключаем — реагируем на сбой реактивно (см. _on_delivery_fail).
            await self._on_delivery_fail(t["rule_id"], key, t.get("account_id"))
        else:
            if used:
                await self.store.add_traffic(t["account_id"], used, rule_id=t["rule_id"])
                await self._maybe_traffic_notify(t["account_id"])
            # Доставка в этот чат прошла → гасим оба уведомления по нему (см. _on_delivery_ok).
            await self._on_delivery_ok(t["rule_id"], key)

    async def _apply_chat_migration(self, old_chat_id: Any, new_chat_id: Any) -> None:
        """Применить миграцию группа→супергруппа: владение (через chat_migrated_cb, если задан) +
        правила/warning (on_tg_chat_migrated). Если координатор не задан — правим хотя бы правила."""
        if self.chat_migrated_cb is not None:
            try:
                await self.chat_migrated_cb(old_chat_id, new_chat_id)
                return
            except Exception:  # noqa: BLE001
                log.warning("chat_migrated_cb сбой %s→%s", old_chat_id, new_chat_id, exc_info=True)
        await self.on_tg_chat_migrated(old_chat_id, new_chat_id)

    # ---- общие примитивы warning'а (используются и реактивным сбоем, и проактивной сменой прав) ----
    async def _raise_banner(self, rule_id: str, key: tuple[str, str]) -> None:
        """Пометить цель/endpoint `key` проблемной у правила и поднять флаг баннера mini-app
        (идемпотентно: если уже поднят — записи на диск не будет; если был скрыт — поднимется
        снова = «поступает новое»)."""
        self._rule_fail_dests.setdefault(rule_id, set()).add(key)
        try:
            await self.store.set_rule_delivery_warn(rule_id, True)
            self._warned_rules.add(rule_id)
        except Exception:  # noqa: BLE001
            log.warning("set delivery_warn failed", exc_info=True)

    async def _lower_banner(self, rule_id: str, key: tuple[str, str]) -> None:
        """Снять пометку `key` у правила; погасить баннер, ТОЛЬКО если других проблемных
        целей/endpoint'ов у правила не осталось (двусторонние правила: успех/восстановление одной
        стороны не гасит предупреждение о другой)."""
        s = self._rule_fail_dests.get(rule_id)
        if s is not None:
            s.discard(key)
            if not s:
                self._rule_fail_dests.pop(rule_id, None)
        if rule_id in self._warned_rules and not self._rule_fail_dests.get(rule_id):
            try:
                await self.store.set_rule_delivery_warn(rule_id, False)
                self._warned_rules.discard(rule_id)
            except Exception:  # noqa: BLE001
                log.warning("clear delivery_warn failed", exc_info=True)

    async def _send_chat_notice(self, key: tuple[str, str], send) -> None:
        """Отправить уведомление в чат по цели `key` ОДИН раз (дедуп по ключу). `send` — корутина
        без аргументов, возвращающая ref на отправленное сообщение (для удаления) либо None. Ключ
        РЕЗЕРВИРУЕМ синхронно ДО await — иначе два параллельных события на одну цель продублировали
        бы уведомление. Ключ остаётся даже при ошибке отправки (ref None) — чтобы не спамить."""
        if key not in self._warn_notice and send is not None:
            self._warn_notice[key] = None
            try:
                self._warn_notice[key] = await send()
            except Exception:  # noqa: BLE001
                log.warning("chat warn notice failed", exc_info=True)

    async def _clear_chat_notice(self, key: tuple[str, str]) -> None:
        """Удалить живое уведомление в чате по цели `key` (если есть)."""
        notice = self._warn_notice.pop(key, None)
        if notice and self.delivery_clear_cb is not None:
            try:
                await self.delivery_clear_cb(key[0], key[1], notice)
            except Exception:  # noqa: BLE001
                log.warning("delivery_clear_cb failed", exc_info=True)

    async def _on_delivery_fail(self, rule_id: str, key: tuple[str, str], account_id: Any) -> None:
        """Сбой доставки в цель `key=(messenger, chat_id)`. Два независимых канала уведомления:
        баннер в mini-app (per-rule флаг) и сообщение в чате с владельцем (per-цель). Каждое —
        ОДИН раз, пока не скрыто/не восстановлено; «Скрыть» в любом из каналов ре-армит ровно его."""
        await self._raise_banner(rule_id, key)
        cb = self.delivery_error_cb
        if cb is not None:
            await self._send_chat_notice(key, lambda: cb(key[0], key[1], account_id))

    async def _on_delivery_ok(self, rule_id: str, key: tuple[str, str]) -> None:
        """Успешная доставка в цель `key` → гасим оба уведомления по этому чату: удаляем
        сообщение в чате (если живое) и снимаем баннер правила, если у него больше нет сбойных целей."""
        await self._clear_chat_notice(key)               # доступность чата — общая для всех правил
        await self._lower_banner(rule_id, key)
        if key[0] == "tg":
            chat_part, thread_part = parse_chat_key(key[1])
            if thread_part is not None:
                base_key = ("tg", chat_part)
                await self._clear_chat_notice(base_key)
                await self._lower_banner(rule_id, base_key)

    async def on_tg_rights_change(self, chat_id: Any, can_read: bool, can_write: bool,
                                  reason: str) -> None:
        """Проактивная реакция на изменение прав бота в TG-чате (из my_chat_member). Источник/
        правило НЕ отключаем — поднимаем ТОТ ЖЕ warning, что и при сбое доставки (баннер mini-app +
        сообщение владельцу), для всех правил, где этот чат затронут потерей права:
          • чат-ИСТОЧНИК и бот больше не может ЧИТАТЬ (not can_read), либо
          • чат-ПРИЁМНИК и бот больше не может ПИСАТЬ (not can_write).
        Когда права вернули (для всех ролей чата во всех правилах) — warning гаснет. Состояние
        общее с реактивным путём: если этот чат — приёмник, ключ совпадает, дублей нет; «Скрыть» и
        успешная доставка работают единообразно. Решение по каждому правилу stateless (из текущих
        can_read/can_write), поэтому переживает рестарт и не даёт ложных срабатываний."""
        cid = str(chat_id)
        sid = f"tg:{cid}"
        key = ("tg", cid)
        any_affected = False
        account_id: Any = None
        for r in list(self.store.table("rules").values()):
            roles = rules_mod.rule_roles(r, sid)
            if not roles:
                continue
            affected = ("source" in roles and not can_read) or ("target" in roles and not can_write)
            if affected:
                any_affected = True
                account_id = account_id or r.get("account_id")
                await self._raise_banner(r["id"], key)
            else:
                await self._lower_banner(r["id"], key)     # для этого правила право снова в порядке
        if any_affected:
            cb = self.tg_rights_warn_cb
            if cb is not None:
                await self._send_chat_notice(key, lambda: cb(cid, account_id, reason))
        else:
            await self._clear_chat_notice(key)             # права восстановлены для всех правил чата

    async def on_tg_chat_migrated(self, old_chat_id: Any, new_chat_id: Any) -> list[str]:
        """TG-чат сменил id (группа повышена до супергруппы). Перепривязываем endpoint'ы правил
        old→new в сторе и переносим состояние warning'а (живое сообщение в чате + реестр сбойных
        целей) на новый ключ — чтобы доставка, баннер и проактивные права заработали под новым id,
        а ранее поднятый баннер/сообщение корректно погасли при первой успешной доставке. Владение
        (ownership) переносит координатор в run_app. Идемпотентно. Возвращает id затронутых правил."""
        old_s, new_s = str(old_chat_id), str(new_chat_id)
        if old_s == new_s:
            return []
        affected = await self.store.migrate_tg_endpoint(old_chat_id, new_chat_id)
        # Живое уведомление в чате по старой цели → на новый ключ (иначе при восстановлении доставки
        # на новый id оно не найдётся и не удалится). setdefault — не затирать уже существующее.
        for key in list(self._warn_notice.keys()):
            if key[0] != "tg":
                continue
            chat_part, thread_part = parse_chat_key(key[1])
            if str(chat_part) == old_s:
                migrated_thread = thread_part if thread_part is not None else "1"
                self._warn_notice.setdefault(("tg", make_chat_key(new_s, migrated_thread)),
                                             self._warn_notice.pop(key))
        # Реестр сбойных целей: старый ключ → новый (иначе _lower_banner по новому id не очистит
        # множество и баннер mini-app не погаснет после успешной доставки на супергруппу).
        for dests in self._rule_fail_dests.values():
            for key in list(dests):
                if key[0] != "tg":
                    continue
                chat_part, thread_part = parse_chat_key(key[1])
                if str(chat_part) == old_s:
                    dests.discard(key)
                    migrated_thread = thread_part if thread_part is not None else "1"
                    dests.add(("tg", make_chat_key(new_s, migrated_thread)))
        if affected:
            log.info("TG-чат %s повышен до супергруппы %s: перепривязано правил=%d",
                     old_chat_id, new_chat_id, len(affected))
            await self._notify_tg_migration(affected)
        return affected

    async def _notify_tg_migration(self, rule_ids: list[str]) -> None:
        """Показать в mini-app, что Telegram-группа стала супергруппой и правило было
        автоматически переведено на первую тему General. Дедуп опирается на idempotency
        migrate_tg_endpoint: повторная миграция не вернёт rule_ids."""
        for rule_id in rule_ids:
            r = self.store.rule(rule_id)
            if not r or not r.get("account_id"):
                continue
            number = r.get("number")
            label = f"Правило №{number}" if number is not None else "Правило"
            try:
                await self.store.add_notification(
                    r["account_id"],
                    type="rules",
                    title="Группа Telegram стала супергруппой",
                    subtitle=f"{label}: выбрана первая тема General",
                    link={"screen": "rules"},
                )
            except Exception:  # noqa: BLE001
                log.warning("migration notification failed", exc_info=True)

    def note_chat_warn_hidden(self, messenger: str, chat_id: Any) -> None:
        """Пользователь нажал «Скрыть» на сообщении-уведомлении В ЧАТЕ (колбэк hide_warn). Само
        нажатое сообщение удаляет обработчик колбэка; здесь ре-армим ЧАТ-канал по этой цели —
        чтобы следующий сбой прислал уведомление заново. Уведомление рассылается во все
        мессенджеры аккаунта, поэтому копии в ДРУГИХ мессенджерах убираем тоже (fire-and-forget;
        повторное удаление уже нажатого сообщения безопасно — clear-колбэк гасит ошибки).
        Баннер mini-app (другой канал) не трогаем."""
        notice = self._warn_notice.pop((messenger, str(chat_id)), None)
        if notice and self.delivery_clear_cb is not None:
            try:
                task = asyncio.get_running_loop().create_task(
                    self._clear_hidden_notice(messenger, str(chat_id), notice))
            except RuntimeError:            # вне event loop (тесты/остановка) — просто ре-арм
                return
            self._bg_tasks.add(task)
            task.add_done_callback(self._bg_tasks.discard)

    async def _clear_hidden_notice(self, messenger: str, chat_id: str, notice: Any) -> None:
        try:
            await self.delivery_clear_cb(messenger, chat_id, notice)
        except Exception:  # noqa: BLE001
            log.warning("очистка скрытого уведомления не удалась", exc_info=True)

    # ---- отчёты в сервисный лог-канал (для разработчиков; пользователю не видны) ----
    def _svc_title(self, messenger: str, chat_key: Any) -> str:
        """Название чата для отчёта: из ownership (source_title), иначе сам id."""
        title = None
        if self.source_title is not None:
            try:
                title = self.source_title(messenger, chat_key)
            except Exception:  # noqa: BLE001
                title = None
        return str(title) if title else str(chat_key)

    def _svc_rule_line(self, rule_id: Any, source_messenger: str,
                       f: dict[str, Any], t: dict[str, Any]) -> str:
        """Строка правила «источник → приёмник» (HTML): TG «Hellow» → MAX «Meat»."""
        src_key = make_chat_key(f.get("chat_id"), f.get("thread_id")) \
            if source_messenger == "tg" else f.get("chat_id")
        tgt_key = make_chat_key(t.get("chat_id"), t.get("thread_id")) \
            if t.get("messenger") == "tg" else t.get("chat_id")
        src = (f'{_MSN_LABEL.get(source_messenger, source_messenger)} '
               f'«{_esc_html(self._svc_title(source_messenger, src_key))}»')
        tgt = (f'{_MSN_LABEL.get(t.get("messenger"), t.get("messenger"))} '
               f'«{_esc_html(self._svc_title(t.get("messenger"), tgt_key))}»')
        rule = self.store.rule(rule_id) if rule_id else None
        number = (rule or {}).get("number")
        label = f"Правило №{number}" if number is not None else "Правило"
        return f"{label}: {src} → {tgt}"

    def _svc_sender_html(self, source_messenger: str, f: dict[str, Any]) -> str:
        """Отправитель для отчёта: TG — имя-ссылка (t.me/username или tg://user?id=…, обе
        работают в Telegram HTML); MAX — жирное имя + id текстом (схема max:// в Telegram
        не валидна — Bot API отклонил бы такую ссылку)."""
        name = f.get("sender_name") or "—"
        esc_name = _esc_html(name)
        if source_messenger == "tg":
            link = _sender_link("tg", f.get("sender_id"), f.get("sender_username"))
            if link:
                return f'<a href="{_esc_attr(link)}">{esc_name}</a>'
            return f"<b>{esc_name}</b>"
        if source_messenger == "max" and f.get("sender_id") is not None:
            uname = f" @{f['sender_username']}" if f.get("sender_username") else ""
            return (f"<b>{esc_name}</b> (MAX id <code>{_esc_html(str(f['sender_id']))}</code>"
                    f"{_esc_html(uname)})")
        return f"<b>{esc_name}</b>"

    async def _svc_delivery_error(self, source_messenger: str, f: dict[str, Any],
                                  t: dict[str, Any], exc: BaseException, *,
                                  kind: str = "Ошибка доставки") -> None:
        """Отчёт об ошибке доставки/правки в сервисный лог-канал. Best-effort: любой сбой
        формирования/отправки отчёта гасится здесь и не влияет на основной поток."""
        svc = self.service_log
        if svc is None or not getattr(svc, "enabled", False):
            return
        try:
            lines = [self._svc_rule_line(t.get("rule_id"), source_messenger, f, t),
                     f"Отправитель: {self._svc_sender_html(source_messenger, f)}"]
            media = _svc_media_note(f)
            if media:
                lines.append(f"Медиа: {_esc_html(media)}")
            if f.get("url"):
                lines.append(f'<a href="{_esc_attr(str(f["url"]))}">Оригинал сообщения</a>')
            if t.get("account_id"):
                lines.append(f"Аккаунт: <code>{_esc_html(str(t['account_id']))}</code>")
            await svc.report(kind, lines, quote=f.get("text") or "", error=exc)
        except Exception:  # noqa: BLE001
            log.warning("отчёт сервисного лога не сформирован", exc_info=True)

    async def _deliver(self, source_messenger: str, f: dict[str, Any], t: dict[str, Any]) -> int:
        """Доставить сообщение в одну цель. Возвращает учтённые байты медиа.

        Медиа по направлениям: MAX→MAX — чистая копия (переиспользуем token);
        TG→TG — переиспользуем file_id; MAX→TG — скачиваем из MAX и грузим в Telegram
        байтами; TG→MAX — скачиваем из Telegram и грузим в MAX (token).
        Трафик учитывается только когда медиа реально отправлено и разрешено.
        """
        media = f.get("media") or []
        media_allowed = bool(t.get("media_allowed", True))
        # Подпись работает и в группах, и в каналах: нужен лишь включённый по направлению флаг
        # и имя отправителя (имя участника группы либо имя/название автора канала).
        suppress_footer = bool(f.get("_suppress_footer"))
        signature = bool(t.get("signature")) and f.get("sender_name") and not suppress_footer
        sig_name = f["sender_name"] if signature else None
        report_link = None if suppress_footer else self._report_link(source_messenger, f, t)
        if t["messenger"] == "max":
            return await self._deliver_max(source_messenger, f, t, sig_name, media,
                                           media_allowed, report_link)
        return await self._deliver_tg(source_messenger, f, t, sig_name, media,
                                      media_allowed, report_link)

    def _report_link(self, source_messenger: str, f: dict[str, Any],
                     t: dict[str, Any], *, copy_messenger: str | None = None,
                     copy_chat_id: Any = None, copy_mid: Any = None,
                     copy_mids: list[Any] | tuple[Any, ...] | None = None,
                     copy_thread_id: Any = None) -> str | None:
        """Диплинк «Пожаловаться» для копии этого сообщения (на площадке читателя = цели).
        Токен кодирует координаты ИСХОДНОГО сообщения + rule_id, а после отправки может быть
        обновлён координатами самой копии. None — если функция выключена/нет id/сбой.
        Не роняет доставку."""
        if not self._reports_on():
            return None
        src_mid = f.get("mid") if source_messenger == "max" else (
            f.get("_map_source_message_id") or f.get("message_id"))
        chat_id = f.get("chat_id")
        if src_mid is None or chat_id is None:
            return None
        try:
            token = make_report_token(
                source_messenger, chat_id, src_mid, t.get("rule_id"),
                copy_messenger=copy_messenger, copy_chat_id=copy_chat_id,
                copy_mid=copy_mid, copy_mids=copy_mids, copy_thread_id=copy_thread_id,
                has_media=_report_has_media(f))
            return report_deeplink(t["messenger"], token)
        except Exception:  # noqa: BLE001 — ссылка жалобы не должна ронять пересылку
            log.warning("жалоба: не построить ссылку", exc_info=True)
            return None

    def _report_link_for_sent_copy(self, source_messenger: str, f: dict[str, Any],
                                   t: dict[str, Any], *, copy_chat_id: Any,
                                   copy_mid: Any,
                                   copy_mids: list[Any] | tuple[Any, ...] | None = None) -> str | None:
        return self._report_link(
            source_messenger, f, t,
            copy_messenger=t.get("messenger"),
            copy_chat_id=copy_chat_id,
            copy_mid=copy_mid,
            copy_mids=copy_mids,
            copy_thread_id=t.get("thread_id"))

    @staticmethod
    def _sent_items(result: Any) -> list[Any]:
        if result is None:
            return []
        out: list[Any] = []
        stack = list(result) if isinstance(result, list) else [result]
        while stack:
            item = stack.pop(0)
            if isinstance(item, list):
                stack = list(item) + stack
            else:
                out.append(item)
        return out

    @staticmethod
    def _copy_mids_for_chat(locs: list[tuple[Any, Any]], copy_chat: Any,
                            copy_mid: Any) -> list[Any]:
        out: list[Any] = []
        seen: set[tuple[str, str]] = set()
        for chat_id, mid in [(copy_chat, copy_mid), *locs]:
            if mid is None or str(chat_id) != str(copy_chat):
                continue
            key = (str(chat_id), str(mid))
            if key in seen:
                continue
            seen.add(key)
            out.append(mid)
        return out

    @staticmethod
    def _tg_sent_locations(result: Any, fallback_chat: Any) -> list[tuple[Any, Any]]:
        locs: list[tuple[Any, Any]] = []
        for msg in RuleDispatcher._sent_items(result):
            if not isinstance(msg, dict):
                continue
            mid = msg.get("message_id")
            if mid is None:
                continue
            chat_id = (msg.get("chat") or {}).get("id", fallback_chat)
            locs.append((chat_id, mid))
        return locs

    @staticmethod
    def _tg_sent_location(result: Any, fallback_chat: Any) -> tuple[Any, Any] | None:
        locs = RuleDispatcher._tg_sent_locations(result, fallback_chat)
        return locs[0] if locs else None

    @staticmethod
    def _max_sent_locations(result: Any, fallback_chat: Any) -> list[tuple[Any, Any]]:
        locs: list[tuple[Any, Any]] = []
        for item in RuleDispatcher._sent_items(result):
            if not isinstance(item, dict):
                continue
            msg = item.get("message") if isinstance(item.get("message"), dict) else item
            body = (msg or {}).get("body") or {}
            mid = body.get("mid")
            if mid is None:
                continue
            chat_id = ((msg or {}).get("recipient") or {}).get("chat_id", fallback_chat)
            locs.append((chat_id, mid))
        return locs

    @staticmethod
    def _max_sent_location(result: Any, fallback_chat: Any) -> tuple[Any, Any] | None:
        locs = RuleDispatcher._max_sent_locations(result, fallback_chat)
        return locs[0] if locs else None

    async def _refresh_tg_report_link(self, source_messenger: str, f: dict[str, Any],
                                      t: dict[str, Any], *, old_link: str | None,
                                      sent: Any, text: str | None, parse_mode: str | None,
                                      is_caption: bool = False,
                                      reply_markup: dict[str, Any] | None = None,
                                      all_sent: Any = None) -> None:
        """После send Telegram уже вернул message_id; best-effort обновляем ссылку так, чтобы
        токен содержал координаты самой копии. Сбой edit не должен ломать доставку."""
        if not old_link or not text or self.tg_client is None:
            return
        loc = self._tg_sent_location(sent, t.get("chat_id"))
        if loc is None:
            return
        copy_chat, copy_mid = loc
        locs = self._tg_sent_locations(all_sent if all_sent is not None else sent, copy_chat)
        copy_mids = self._copy_mids_for_chat(locs, copy_chat, copy_mid)
        new_link = self._report_link_for_sent_copy(source_messenger, f, t,
                                                   copy_chat_id=copy_chat, copy_mid=copy_mid,
                                                   copy_mids=copy_mids)
        if not new_link or new_link == old_link:
            return
        updated = text.replace(old_link, new_link)
        if updated == text:
            return
        try:
            if is_caption:
                await self.tg_client.edit_message_caption(
                    copy_chat, copy_mid, updated, parse_mode=parse_mode,
                    reply_markup=reply_markup)
            else:
                await self.tg_client.edit_message_text(
                    copy_chat, copy_mid, updated, parse_mode=parse_mode,
                    reply_markup=reply_markup, disable_web_page_preview=True)
        except Exception:  # noqa: BLE001
            log.warning("жалоба: не обновить TG-ссылку координатами копии", exc_info=True)

    async def _refresh_max_report_link(self, source_messenger: str, f: dict[str, Any],
                                       t: dict[str, Any], *, old_link: str | None,
                                       sent: Any, text: str | None, fmt: str | None,
                                       all_sent: Any = None,
                                       attachments: list[dict[str, Any]] | None = None) -> bool:
        """Best-effort post-send refresh для MAX-сообщения: в токен добавляется mid копии."""
        if not old_link or self.max_client is None:
            return False
        loc = self._max_sent_location(sent, t.get("chat_id"))
        if loc is None:
            return False
        copy_chat, copy_mid = loc
        locs = self._max_sent_locations(all_sent if all_sent is not None else sent, copy_chat)
        copy_mids = self._copy_mids_for_chat(locs, copy_chat, copy_mid)
        new_link = self._report_link_for_sent_copy(source_messenger, f, t,
                                                   copy_chat_id=copy_chat, copy_mid=copy_mid,
                                                   copy_mids=copy_mids)
        if not new_link or new_link == old_link:
            return False
        updated = text.replace(old_link, new_link) if text else text
        if not text or updated == text:
            return False
        try:
            await self.max_client.edit_message(
                copy_mid,
                text=updated,
                attachments=([_max_public_attachment(a) for a in attachments]
                             if _max_has_media_attachment(attachments) else None),
                fmt=fmt)
            return True
        except Exception:  # noqa: BLE001
            log.warning("жалоба: не обновить MAX-ссылку координатами копии", exc_info=True)
            return False

    async def _repair_max_media_after_send(self, sent: Any, text: str | None, fmt: str | None,
                                           attachments: list[dict[str, Any]] | None) -> None:
        """MAX может заменить image/video attachment на share-preview из HTML-ссылки.

        Live-проверка показала: POST /messages с media+HTML-link иногда возвращает только
        `share`, даже при `disable_link_preview=false`. PUT /messages с тем же HTML-текстом и
        исходными attachments восстанавливает image/video и сохраняет markup-ссылки.
        """
        if self.max_client is None or not _max_has_media_attachment(attachments):
            return
        types = _max_sent_attachment_types(sent)
        expected = {str(a.get("type")) for a in (attachments or [])
                    if isinstance(a, dict) and a.get("type") != "inline_keyboard"}
        if "share" not in types and expected.intersection(types):
            return
        loc = self._max_sent_location(sent, None)
        if loc is None:
            return
        _copy_chat, copy_mid = loc
        try:
            await self.max_client.edit_message(
                copy_mid,
                text=text,
                attachments=[_max_public_attachment(a) for a in attachments],
                fmt=fmt)
        except Exception:  # noqa: BLE001
            log.warning("MAX: не удалось восстановить media после link-preview", exc_info=True)

    def _with_link(self, text: str | None, f: dict[str, Any],
                   fmt: str | None = None) -> tuple[str, str | None]:
        return self._append_link_note(text, fmt, f)

    def _full_source_note(self, f: dict[str, Any], *, html: bool) -> str:
        source_name = str(f.get("source_name") or f.get("chat_id") or "источник")
        messenger = _MESSENGER_NOTE_LABEL.get(str(f.get("source_messenger") or ""),
                                              str(f.get("source_messenger") or ""))
        link = f.get("url")
        if html:
            name = _esc_html(source_name)
            if link:
                name = f'<a href="{_esc_attr(str(link))}">{name}</a>'
            return (f'{_esc_html(LINK_NOTE)} в источнике "{name}" '
                    f'в мессенджере {_esc_html(messenger)}.')
        return f'{LINK_NOTE} в источнике "{source_name}" в мессенджере {messenger}.'

    def _append_link_note(self, send_text: str | None, fmt: str | None,
                          f: dict[str, Any]) -> tuple[str, str | None]:
        """Добавить единую строку о неполной доставке.

        Если есть ссылка на оригинал — делаем кликабельным название источника и переводим
        сообщение в format=html. Старые варианты вроде «ТУТ» и отдельных причин пропуска
        в пользовательский текст больше не добавляются. Сама строка полного источника
        отправляется цитатой в Telegram и MAX.
        """
        body = (send_text or "") if fmt == "html" else _esc_html(send_text or "")
        line = f"<blockquote>{self._full_source_note(f, html=True)}</blockquote>"
        return ((body + "\n\n" + line) if body else line), "html"

    def _fmt_html(self, source_messenger: str, text: str, *,
                  markup: Any = None, entities: Any = None) -> tuple[str, bool]:
        """(html, has_fmt) для текста с форматированием источника. MAX → из markup;
        Telegram → из entities (сохраняет гиперссылки text_link). Без конвертера или без
        форматирования — ("", False), тогда отправляем как есть (plain)."""
        if not text or self._markup_to_html is None:
            return "", False
        if source_messenger == "max" and markup:
            return self._markup_to_html(text, markup)
        if source_messenger == "tg" and entities:
            return tg_entities_to_html(text, entities, self._markup_to_html)
        return "", False

    def _source_html(self, source_messenger: str, f: dict[str, Any], text: str) -> tuple[str, bool]:
        """HTML с форматированием исходного сообщения, или ("", False)."""
        return self._fmt_html(source_messenger, text,
                              markup=f.get("markup"), entities=f.get("entities"))

    def _reply_quote_html(self, source_messenger: str, quote: dict[str, Any] | None,
                          *, for_tg: bool) -> str:
        """HTML процитированного сообщения (ответ/reply) как blockquote перед телом, или "".

        MAX отдаёт ответ как link.type=="reply": оригинал в link.message, его автор в
        link.sender (сверено вживую) — раньше эта цитата ТЕРЯЛАСЬ при пересылке. Теперь
        вставляем её цитатой: имя автора жирным + текст оригинала (с сохранённым
        форматированием). В Telegram — раскрываемая цитата (expandable_blockquote, длинная
        сворачивается). MAX тег <blockquote> сам не рисует (игнорирует), но автор+текст
        остаются читаемыми. Имена/текст экранируются конвертерами."""
        if not quote:
            return ""
        qtext = (quote.get("text") or "").strip()
        if not qtext:
            return ""
        qh, qfmt = self._fmt_html(source_messenger, qtext,
                                  markup=quote.get("markup"), entities=quote.get("entities"))
        qbody = qh if qfmt else _esc_html(qtext)
        qbody = html_for_telegram(qbody) if for_tg else html_for_max(qbody)
        if not for_tg and source_messenger == "tg":
            qbody = _tg_code_markers_for_max(qbody)
        qname = quote.get("from")
        prefix = f"<b>{_esc_html(qname)}</b>\n" if qname else ""
        tag = "<blockquote expandable>" if for_tg else "<blockquote>"
        return f"{tag}{prefix}{qbody}</blockquote>\n"

    def _compose_text(self, source_messenger: str, f: dict[str, Any], sig_name: str | None,
                      *, for_tg: bool, report_link: str | None = None) -> tuple[str | None, str | None]:
        """Собрать текст с подписью, ссылкой «Пожаловаться» и цитатой ответа.
        Возвращает (text, fmt): fmt='html', если есть подпись/жалоба/цитата ИЛИ
        форматирование источника; иначе (None) — чистый plain. Подпись отправителя — внизу,
        имя-ссылка на профиль; следом «Пожаловаться» (если модерация-жалобы включены).
        Для Telegram html приводится к подмножеству (чужие схемы → жирное имя)."""
        text = f.get("text") or ""
        reply = f.get("reply")
        quote_html = self._reply_quote_html(source_messenger, reply, for_tg=for_tg)
        html, has_fmt = self._source_html(source_messenger, f, text)
        show_sig = bool(sig_name)
        if not show_sig and not has_fmt and not quote_html and not report_link:
            return (text or None), None
        body = html if has_fmt else _esc_html(text)
        if not for_tg:
            if source_messenger == "tg":
                body = _tg_code_markers_for_max(body)
        name_link = (_sender_link(source_messenger, f.get("sender_id"), f.get("sender_username"))
                     if show_sig else None)
        source_name = f.get("source_name") if show_sig else None
        separator = _signature_separator(_reply_quote_plain(reply), text)
        footer = _footer_html(
            sig_name if show_sig else None, name_link, source_name, report_link, separator)
        composed = quote_html + body + footer
        composed = html_for_telegram(composed) if for_tg else html_for_max(composed)
        return (composed or None), "html"

    def _tg_upload_plan(self, m: dict[str, Any]) -> tuple[str, Any, str, str | None]:
        """План загрузки одного TG-медиа в MAX: (up_type, file_id, filename, content_type).

        Стикеры — особый случай. У MAX при загрузке нет типа «стикер», но он нативно
        отрисовывает изображения (его CDN сам отдаёт картинки как image/webp, а загрузка
        webp как type=image возвращает валидный token — проверено вживую). Поэтому:
          • статичный стикер (WebP) → грузим как image → отрисуется картинкой;
          • анимированный (.tgs/Lottie) и видео-стикер (.webm) MAX воспроизвести не может —
            вместо самого файла грузим его статичное ПРЕВЬЮ (thumbnail, webp/jpg) как image,
            чтобы пользователь видел картинку стикера, а не безликий «file.bin»
            (content-type/расширение превью уточняем по байтам после скачивания → ct=None);
          • если превью нет — отдаём исходный файл с корректным расширением (.tgs/.webm).
        Раньше ЛЮБОЙ стикер шёл как file без имени (у Sticker нет file_name) → MAX
        показывал «file.bin»."""
        raw = m.get("raw") or {}
        if m.get("type") == "sticker":
            is_anim = bool(m.get("is_animated") or raw.get("is_animated"))
            is_video = bool(m.get("is_video") or raw.get("is_video"))
            if not is_anim and not is_video:
                # Статичный стикер бывает WebP ИЛИ PNG (docs/telegram Sticker) — тип/имя уточним
                # по сигнатуре байтов (ct=None → ветка определения ниже).
                return "image", m.get("file_id") or raw.get("file_id"), "sticker.webp", None
            thumb_id = m.get("thumbnail_file_id") or (raw.get("thumbnail") or {}).get("file_id")
            if thumb_id:
                return "image", thumb_id, "sticker.webp", None
            ext = "tgs" if is_anim else "webm"
            return ("file", m.get("file_id") or raw.get("file_id"), f"sticker.{ext}",
                    "application/gzip" if is_anim else "video/webm")
        up_type = _TG_MEDIA_TO_MAX_UPLOAD.get(m.get("type"), "file")
        file_id = m.get("file_id") or raw.get("file_id")
        name = m.get("file_name") or f"file.{_MAX_UPLOAD_EXT.get(up_type, 'bin')}"
        return up_type, file_id, name, m.get("mime_type")

    async def _tg_animated_sticker_to_max(self, m: dict[str, Any]) -> tuple[dict[str, Any] | None, int]:
        """Анимированный (TGS/Lottie) или видео (WebM) стикер → mp4 → загрузка в MAX как видео.

        Возвращает (attachment, учтённые_байты) при успехе или (None, 0) при любой неудаче —
        тогда вызывающий падает на статичное превью (thumbnail-картинку). Трафик считаем по
        фактически загруженным байтам mp4. Скачиваем САМ стикер (tgs/webm), не превью."""
        raw = m.get("raw") or {}
        file_id = m.get("file_id") or raw.get("file_id")
        if file_id is None or self.tg_client is None or self.max_client is None:
            return None, 0
        size = _declared_size(m)
        if size is not None and size > config.TG_UPLOAD_MAX_BYTES:
            return None, 0
        try:
            info = await self.tg_client.get_file(file_id)
            file_path = info.get("file_path")
            if not file_path:
                return None, 0
            data, _ct = await self.tg_client.download_file_bytes(
                file_path, max_bytes=config.TG_UPLOAD_MAX_BYTES)
            mp4 = await stickers.sticker_to_mp4(
                data,
                is_animated=bool(m.get("is_animated") or raw.get("is_animated")),
                is_video=bool(m.get("is_video") or raw.get("is_video")))
            if not mp4:
                return None, 0
            token = await self.max_client.upload_media(
                "video", mp4, filename="sticker.mp4", content_type="video/mp4")
        except Exception:  # noqa: BLE001
            log.warning("TG→MAX: анимированный стикер не сконвертирован/не загружен — фоллбэк на превью",
                        exc_info=True)
            return None, 0
        if not token:
            return None, 0
        return {"type": "video", "payload": {"token": token}}, len(mp4)

    async def _tg_media_to_max(self, media: list[dict[str, Any]]
                               ) -> tuple[list[dict[str, Any]], int, int, int]:
        """Скачать каждое TG-медиа и загрузить в MAX. Возвращает (attachments, учтённые_байты,
        n_неподдерживаемых, n_слишком_больших). РАЗДЕЛЯЕМ причины пропуска: формат не принят MAX
        (запрещённое расширение — 415 «File extension is forbidden») → n_неподдерживаемых;
        файл крупнее потолка передачи → n_слишком_больших (это вопрос РАЗМЕРА, а не формата).
        Поддерживаемое доставляем (частичный успех); вызывающий добавит корректную пометку со
        ссылкой на оригинал. На ОБЛАЧНОМ Telegram getFile отдаёт файлы ≤20 МБ; с локальным
        Bot API сервером лимит скачивания снят (MAX принимает до 4 ГБ)."""
        out: list[dict[str, Any]] = []
        used, unsupported, oversized = 0, 0, 0
        if self.tg_client is None or self.max_client is None:
            return out, used, len(media), oversized
        for m in media:
            # Анимированный/видео-стикер → конвертируем в mp4 и шлём как видео MAX (анимация).
            # Не удалось (нет тулинга/битый/ошибка) → падаем на статичное превью (общий путь ниже).
            if m.get("type") == "sticker" and (m.get("is_animated") or (m.get("raw") or {}).get("is_animated")
                                               or m.get("is_video") or (m.get("raw") or {}).get("is_video")):
                att, n = await self._tg_animated_sticker_to_max(m)
                if att is not None:
                    out.append({**att, _MAX_ATT_BYTES: n})
                    used += n
                    continue
            up_type, file_id, name, ct = self._tg_upload_plan(m)
            if not file_id:
                unsupported += 1
                continue
            # Пре-флайт по размеру: файл крупнее потолка кросс-мессенджерной передачи НЕ качаем
            # вовсе (заказчик: «больше 2 ГБ даже не начинали загружаться»). Это «слишком большой»,
            # а НЕ «не поддерживается» — учитываем отдельно (oversized), ниже даст корректную
            # пометку + ссылку на оригинал. Telegram сообщает file_size почти всегда.
            size = _declared_size(m)
            if size is not None and size > config.TG_UPLOAD_MAX_BYTES:
                log.info("TG→MAX: медиа %s ~%d Б > лимита %d — слишком большое (ссылка на оригинал)",
                         m.get("type"), size, config.TG_UPLOAD_MAX_BYTES)
                oversized += 1
                continue
            try:
                info = await self.tg_client.get_file(file_id)
                file_path = info.get("file_path")
                if not file_path:
                    unsupported += 1
                    continue
                # Тот же конфиг-потолок, что и для MAX→TG — оба направления ограничены одним
                # knob, без него крупный файл (локальный Bot API сервер) залил бы всю RAM.
                data, dl_ct = await self.tg_client.download_file_bytes(
                    file_path, max_bytes=config.TG_UPLOAD_MAX_BYTES)
                # Стикер/превью (ct=None): уточняем тип и расширение по сигнатуре байтов
                # (статичный стикер — webp/png; превью анимированного/видео — webp/jpg).
                if up_type == "image" and ct is None:
                    ct = _image_content_type(data, dl_ct)
                    ext = {"image/jpeg": "jpg", "image/png": "png",
                           "image/gif": "gif", "image/webp": "webp"}.get(ct, "webp")
                    name = f"sticker.{ext}"
                token = await self.max_client.upload_media(
                    up_type, data, filename=name, content_type=ct)
            except ValueError as e:
                # потоковый потолок размера сработал (file_size не был заявлен заранее) —
                # это «слишком большой», а не «не поддерживается».
                if "лимит размера" in str(e):
                    oversized += 1
                else:
                    unsupported += 1
                log.warning("TG→MAX: не перенесли медиа (%s): %s", m.get("type"), e)
                continue
            except Exception:  # noqa: BLE001
                log.warning("TG→MAX: не удалось перенести медиа (%s)", m.get("type"), exc_info=True)
                unsupported += 1
                continue
            if not token:
                unsupported += 1
                continue
            out.append({"type": up_type, "payload": {"token": token}, _MAX_ATT_BYTES: len(data)})
            used += len(data)       # фактически перенесённые байты (точнее source file_size)
        return out, used, unsupported, oversized

    async def _max_media_size(self, media: list[dict[str, Any]]) -> int:
        """Суммарный размер MAX-вложений в байтах — для учёта трафика MAX→MAX (token
        переиспользуется, файл НЕ качаем). У MAX-медиа нет file_size в payload, поэтому размер
        берём по Content-Length публичного url (HEAD, без скачивания тела). Фоллбэк: file_size,
        если вдруг есть; иначе этот файл в трафик не попадает (0 по нему) — доставка не страдает."""
        total = 0
        for m in media or []:
            size = _declared_size(m)
            if size is None and self.max_client is not None:
                url = m.get("url") or (m.get("raw") or {}).get("url")
                if url:
                    try:
                        size = await self.max_client.content_length(url)
                    except Exception:  # noqa: BLE001 — размер не критичен для доставки
                        log.warning("MAX→MAX: не удалось узнать размер медиа для трафика", exc_info=True)
                        size = None
            if isinstance(size, int):
                total += size
        return total

    async def _deliver_max(self, source_messenger, f, t, sig_name, media, media_allowed,
                           report_link=None) -> int:
        if self.max_client is None:
            return 0
        send_text, fmt = self._compose_text(source_messenger, f, sig_name, for_tg=False,
                                            report_link=report_link)
        keyboard_att = (_tg_reply_markup_to_max_attachment(f.get("reply_markup"))
                        if source_messenger == "tg"
                        else _max_inline_keyboard_attachment(f.get("attachments")))
        attachments, used, note_in_text = None, 0, False
        if media and not media_allowed:
            # Трафик исчерпан → текст + ссылка на оригинал.
            send_text, fmt = self._with_link(send_text, f, fmt)
        elif media and source_messenger == "max" and self._rebuild_attachments:
            # MAX→MAX — чистая копия (переиспользуем token входящих).
            attachments = self._rebuild_attachments(media)      # None → невосстановимо
            if attachments is not None:
                used = await self._max_media_size(media)         # размер по Content-Length url
            else:
                send_text, fmt = self._with_link(send_text, f, fmt)
        elif media and source_messenger == "tg":
            # TG→MAX — скачиваем из Telegram и грузим в MAX. Поддерживаемое доставляем;
            # если перенесено не всё — добавляем единую строку, где посмотреть полный оригинал.
            atts, used, unsupported, oversized = await self._tg_media_to_max(media)
            if unsupported or oversized:
                send_text, fmt = self._append_link_note(send_text, fmt, f)
                note_in_text = True
            attachments = (atts or None)
        elif media:
            # Источник без доступного переноса медиа → текст + ссылка на оригинал.
            send_text, fmt = self._with_link(send_text, f, fmt)
        if keyboard_att is not None:
            attachments = [*(attachments or []), keyboard_att]
        if attachments and _max_needs_file_split(attachments):
            # MAX принимает file attachment только как единственное вложение сообщения.
            # Telegram-альбомы могут прийти как document/file части вместе с другими медиа,
            # поэтому сначала отправляем вложения, а текст/подпись — отдельным сообщением после.
            return await self._max_send_split_attachments(
                t["chat_id"], send_text, fmt, f, attachments, note_in_text=note_in_text,
                source_messenger=source_messenger, target=t, report_link=report_link)
        delivered = await self._max_send_with_retry(
            t["chat_id"], send_text, attachments, fmt, f, note_in_text=note_in_text,
            source_messenger=source_messenger, target=t, report_link=report_link)
        return used if delivered else 0

    async def _max_send_split_attachments(self, chat_id, text, fmt, f,
                                          atts: list[dict[str, Any]], *,
                                          note_in_text: bool = False,
                                          source_messenger: str | None = None,
                                          target: dict[str, Any] | None = None,
                                          report_link: str | None = None) -> int:
        """Отправить MAX-вложения, когда одно сообщение не может вместить все файлы.

        Текст/подпись отправляем последним отдельным сообщением, чтобы footer не оказался под
        первым файлом при догрузке остальных вложений.
        """
        delivered = 0
        sent_results: list[Any] = []
        file_atts = [a for a in atts if a.get("type") == "file"]
        keyboard_atts = [a for a in atts if a.get("type") == "inline_keyboard"]
        other_atts = [a for a in atts if a.get("type") not in ("file", "inline_keyboard")]
        for att in file_atts:
            ok = await self._max_send_with_retry(
                chat_id, None, [_max_public_attachment(att)], None, f,
                note_in_text=False, source_messenger=None, target=None, report_link=None,
                sent_results=sent_results)
            if ok:
                delivered += _max_att_bytes(att)
        if other_atts:
            ok = await self._max_send_with_retry(
                chat_id, None, [_max_public_attachment(a) for a in other_atts], None, f,
                note_in_text=False, source_messenger=None, target=None, report_link=None,
                sent_results=sent_results)
            if ok:
                delivered += sum(_max_att_bytes(a) for a in other_atts)
        if text or keyboard_atts:
            await self._max_send_with_retry(
                chat_id, text, keyboard_atts or None, fmt, f, note_in_text=note_in_text,
                source_messenger=source_messenger, target=target, report_link=report_link,
                sent_results=sent_results)
        return delivered

    async def _max_send_with_retry(self, chat_id, text, attachments, fmt, f,
                                   *, note_in_text: bool = False,
                                   source_messenger: str | None = None,
                                   target: dict[str, Any] | None = None,
                                   report_link: str | None = None,
                                   sent_results: list[Any] | None = None) -> bool:
        """Отправка в MAX с ожиданием обработки вложения. Свежезагруженное видео/аудио/крупный
        файл MAX обрабатывает АСИНХРОННО уже после загрузки (docs-api POST/uploads → «Обработка
        файлов»): отправка сообщения с его token сразу падает `attachment.not.ready`.

        Политика (по требованию заказчика): пока MAX отвечает `attachment.not.ready` — ждём и
        повторяем БЕЗ ограничения по времени (паузы растут по config.MAX_ATTACHMENT_RETRY_DELAYS
        и далее держатся на последнем значении — опрос обработки). Цикл завершается ТОЛЬКО когда
        вложение реально отправлено («отправлено») ИЛИ MAX вернул иную ошибку. Транзиентные сбои
        (5xx/сеть/неоднозначный ответ) получают ОГРАНИЧЕННОЕ число повторов (= длина списка пауз),
        затем — деградация. Постоянная ошибка → деградация сразу.

        Возвращает True, если вложения РЕАЛЬНО отправлены; False — если деградировали до текста
        без вложений (тогда трафик за медиа учитывать НЕ нужно). note_in_text=True — ссылка на
        оригинал уже в тексте (TG→MAX частичный перенос), второй раз её не добавляем."""
        if not attachments:
            # без вложений ждать нечего — обычная отправка (ошибку пробрасываем как раньше).
            sent = await self.max_client.send_message(chat_id=chat_id, text=text,
                                                      attachments=None, fmt=fmt,
                                                      disable_link_preview=True)
            if sent_results is not None:
                sent_results.append(sent)
            if source_messenger and target is not None:
                refreshed = await self._refresh_max_report_link(
                    source_messenger, f, target, old_link=report_link, sent=sent,
                    text=text, fmt=fmt, all_sent=sent_results)
                if not refreshed:
                    await self._repair_max_media_after_send(sent, text, fmt, attachments)
            else:
                await self._repair_max_media_after_send(sent, text, fmt, attachments)
            return False
        delays = config.MAX_ATTACHMENT_RETRY_DELAYS or (30.0,)
        transient_budget = len(delays)     # повторы для НЕ-processing транзиентных сбоев
        proc_waits = 0                     # ожидания обработки — без верхнего предела
        while True:
            try:
                sent = await self.max_client.send_message(chat_id=chat_id, text=text,
                                                          attachments=[_max_public_attachment(a)
                                                                       for a in attachments],
                                                          fmt=fmt, disable_link_preview=True)
                if sent_results is not None:
                    sent_results.append(sent)
                if source_messenger and target is not None:
                    refreshed = await self._refresh_max_report_link(
                        source_messenger, f, target, old_link=report_link, sent=sent,
                        text=text, fmt=fmt, all_sent=sent_results, attachments=attachments)
                    if not refreshed:
                        await self._repair_max_media_after_send(sent, text, fmt, attachments)
                else:
                    await self._repair_max_media_after_send(sent, text, fmt, attachments)
                return True
            except Exception as exc:  # noqa: BLE001
                code = getattr(exc, "code", None)
                if code == "attachment.not.ready":
                    # MAX ещё обрабатывает медиа → ждём без лимита по времени (пауза растёт и
                    # упирается в последнее значение списка). Завершит цикл только успех/ошибка.
                    delay = delays[min(proc_waits, len(delays) - 1)]
                    if proc_waits == 0 or proc_waits % 20 == 0:
                        log.info("MAX: вложение ещё обрабатывается — ждём без лимита "
                                 "(ожидание #%d, пауза %sс)", proc_waits + 1, delay)
                    proc_waits += 1
                    await asyncio.sleep(delay)
                    continue
                if _max_send_transient(exc) and transient_budget > 0:
                    delay = delays[len(delays) - transient_budget]
                    transient_budget -= 1
                    log.info("MAX: транзиентный сбой отправки (%s) — повтор через %sс",
                             code or type(exc).__name__, delay)
                    await asyncio.sleep(delay)
                    continue
                # постоянная ошибка ИЛИ исчерпан бюджет транзиентных повторов → деградация ниже.
                log.warning("MAX: вложение не отправилось (%s) — текст+ссылка",
                            code or type(exc).__name__, exc_info=True)
                break
        if note_in_text:
            degraded, degraded_fmt = text, fmt
        else:
            degraded, degraded_fmt = self._with_link(text, f, fmt)
        sent = await self.max_client.send_message(chat_id=chat_id, text=degraded, fmt=degraded_fmt,
                                                  disable_link_preview=True)
        if sent_results is not None:
            sent_results.append(sent)
        if source_messenger and target is not None:
            refreshed = await self._refresh_max_report_link(
                source_messenger, f, target, old_link=report_link, sent=sent,
                text=degraded, fmt=degraded_fmt, all_sent=sent_results)
            if not refreshed:
                await self._repair_max_media_after_send(sent, degraded, degraded_fmt, None)
        else:
            await self._repair_max_media_after_send(sent, degraded, degraded_fmt, None)
        return False

    async def _deliver_tg(self, source_messenger, f, t, sig_name, media, media_allowed,
                          report_link=None) -> int:
        if self.tg_client is None:
            return 0
        thread_id = telegram_send_thread_param(t.get("thread_id"))
        text = f.get("text") or ""
        send_text, fmt = self._compose_text(source_messenger, f, sig_name, for_tg=True,
                                            report_link=report_link)
        parse_mode = "HTML" if fmt == "html" else None
        reply_markup = (_max_inline_keyboard_to_tg_reply_markup(f.get("attachments"))
                        if source_messenger == "max"
                        else _tg_reply_markup_for_tg(f.get("reply_markup")))
        if media_allowed and media:
            if source_messenger == "tg":
                # TG→TG — переиспользуем file_id (без перезагрузки байтов).
                try:
                    caption_fits = bool(
                        send_text and _utf16_len(str(send_text)) <= _TG_CAPTION_LIMIT
                    )
                    caption_in_album = bool(
                        len(media) > 1
                        and _tg_album_caption_ok(send_text, text, reply_markup=reply_markup)
                    )
                    text_after_media = bool(
                        send_text and (
                            (len(media) == 1 and not caption_fits)
                            or (len(media) > 1 and not caption_in_album)
                        )
                    )
                    media_caption = send_text if (
                        (len(media) == 1 and caption_fits) or caption_in_album
                    ) else None
                    sent, used, sent_result = await self._tg_send_from_tg(
                        t["chat_id"], thread_id, media,
                        media_caption,
                        parse_mode,
                        reply_markup=reply_markup if not text_after_media else None)
                    if sent:
                        if text_after_media:
                            kw = {"message_thread_id": thread_id} if thread_id is not None else {}
                            if reply_markup is not None:
                                kw["reply_markup"] = reply_markup
                            sent_text = await self.tg_client.send_message(
                                t["chat_id"], send_text, parse_mode=parse_mode,
                                disable_web_page_preview=True, **kw)
                            await self._refresh_tg_report_link(
                                source_messenger, f, t, old_link=report_link, sent=sent_text,
                                text=send_text, parse_mode=parse_mode,
                                reply_markup=kw.get("reply_markup"),
                                all_sent=[sent_text, sent_result])
                        else:
                            await self._refresh_tg_report_link(
                                source_messenger, f, t, old_link=report_link, sent=sent_result,
                                text=send_text, parse_mode=parse_mode, is_caption=bool(send_text),
                                reply_markup=reply_markup)
                        return used
                except Exception:  # noqa: BLE001 — не теряем сообщение: текст+ссылка
                    log.warning("TG→TG: медиа не ушло — деградирую до текст+ссылки", exc_info=True)
            else:
                # MAX→TG — скачиваем из MAX и грузим в Telegram байтами (по URL Telegram не
                # принял бы webp-картинки и не-PDF/ZIP документы — см. _max_media_to_tg).
                prepared = await self._max_media_to_tg(media)
                if prepared is not None:
                    show_sig = bool(sig_name)
                    quote_plain = _reply_quote_plain(f.get("reply"))
                    separator = _signature_separator(quote_plain, text)
                    footer_plain = _footer_plain(
                        sig_name if show_sig else None,
                        f.get("source_name") if show_sig else None,
                        bool(report_link),
                        separator)
                    fits = _utf16_len(quote_plain + text + footer_plain) <= _TG_CAPTION_LIMIT
                    single_media = len(prepared) == 1
                    # sendMediaGroup не поддерживает reply_markup → для media group
                    # с reply_markup выносим текст в отдельное сообщение, чтобы прицепить кнопки.
                    if reply_markup is not None and not single_media and fits and send_text:
                        fits = False
                    kinds = {p["kind"] for p in prepared}
                    groupable = self._UploadFile is not None and len(prepared) > 1 and (
                        kinds <= {"photo", "video"} or len(kinds) == 1)
                    caption_in_album = bool(
                        groupable and len(prepared) <= 10
                        and _tg_album_caption_ok(send_text, text, reply_markup=reply_markup)
                    )
                    cap = send_text if (
                        send_text and fits and (single_media or caption_in_album)
                    ) else None
                    used, sent_result, media_caption_sent = await self._tg_send_uploaded(
                        t["chat_id"], thread_id, prepared, cap, parse_mode,
                        reply_markup=reply_markup if single_media else None)
                    if used > 0:
                        if media_caption_sent:
                            await self._refresh_tg_report_link(
                                source_messenger, f, t, old_link=report_link, sent=sent_result,
                                text=cap, parse_mode=parse_mode, is_caption=True,
                                reply_markup=reply_markup if single_media else None)
                        if send_text and not media_caption_sent:
                            try:
                                kw = {"message_thread_id": thread_id} if thread_id is not None else {}
                                if reply_markup is not None and not single_media:
                                    kw["reply_markup"] = reply_markup
                                sent_text = await self.tg_client.send_message(
                                    t["chat_id"], send_text, parse_mode=parse_mode,
                                    disable_web_page_preview=True, **kw)
                                await self._refresh_tg_report_link(
                                    source_messenger, f, t, old_link=report_link,
                                    sent=sent_text, text=send_text, parse_mode=parse_mode,
                                    reply_markup=kw.get("reply_markup"),
                                    all_sent=[sent_text, sent_result])
                            except Exception:  # noqa: BLE001
                                log.warning("MAX→TG: текст к медиа не отправлен", exc_info=True)
                        return used
                    # used == 0 → ничего не отправилось → ниже текст+ссылка (медиа не потеряем)
        if media:
            send_text, fmt = self._with_link(send_text, f, fmt)
            parse_mode = "HTML" if fmt == "html" else None
        kw = {"message_thread_id": thread_id} if thread_id is not None else {}
        if reply_markup is not None:
            kw["reply_markup"] = reply_markup
        sent = await self.tg_client.send_message(t["chat_id"], send_text or " ",
                                                 parse_mode=parse_mode,
                                                 disable_web_page_preview=True, **kw)
        await self._refresh_tg_report_link(source_messenger, f, t, old_link=report_link,
                                           sent=sent, text=send_text or " ",
                                           parse_mode=parse_mode, reply_markup=reply_markup)
        return 0

    async def _tg_send_from_tg(self, chat_id, thread_id, media, send_text, parse_mode,
                              *, reply_markup=None) -> tuple[bool, int, Any]:
        """TG→TG: отправить медиа, переиспользуя file_id. (sent, учтённые_байты);
        sent=False → нечего отправить (нет file_id) → вызывающий деградирует до текст+ссылки."""
        refs = [(m.get("file_id") or (m.get("raw") or {}).get("file_id"), m.get("type")) for m in media]
        if len(media) == 1 and refs[0][0]:
            ref, tp = refs[0]
            cap = send_text or None
            kw = {"message_thread_id": thread_id} if thread_id is not None else {}
            if reply_markup is not None:
                kw["reply_markup"] = reply_markup
            if tp in ("photo", "image"):
                sent = await self.tg_client.send_photo(chat_id, ref, caption=cap,
                                                       parse_mode=parse_mode, **kw)
            elif tp == "video":
                sent = await self.tg_client.send_video(chat_id, ref, caption=cap,
                                                       parse_mode=parse_mode, **kw)
            else:
                sent = await self.tg_client.send_document(chat_id, ref, caption=cap,
                                                          parse_mode=parse_mode, **kw)
            return True, _media_bytes(media), sent
        if len(media) > 1 and all(r for r, _ in refs):
            group = []
            for i, (ref, tp) in enumerate(refs):
                item = {"type": "photo" if tp in ("photo", "image") else "video" if tp == "video" else "document",
                        "media": ref}
                if i == 0 and send_text:
                    item["caption"] = send_text
                    if parse_mode:
                        item["parse_mode"] = parse_mode
                group.append(item)
            kw = {"message_thread_id": thread_id} if thread_id is not None else {}
            sent = await self.tg_client.send_media_group(chat_id, group, **kw)
            return True, _media_bytes(media), sent
        return False, 0, None

    async def _max_media_to_tg(self, media: list[dict[str, Any]]) -> list[dict[str, Any]] | None:
        """Скачать каждое MAX-медиа в байты для загрузки в Telegram. None, если ХОТЯ БЫ
        одно не удалось (тогда фоллбэк на текст+ссылку — ничего не теряем). У MAX-вложения
        есть прямой публичный url (i.oneme.ru / okcdn); качаем сами, т.к. Telegram по URL
        webp-картинки/не-PDF-документы не примет. Возвращает [{kind, data, name, ct}]."""
        if self.max_client is None:
            return None
        out: list[dict[str, Any]] = []
        for m in media:
            url = m.get("url")
            if not url:
                return None
            kind = _MAX_TO_TG_KIND.get(m.get("type"), "document")
            try:
                data, ct, cd_name = await self.max_client.download_bytes(
                    url, max_bytes=config.TG_UPLOAD_MAX_BYTES)
            except Exception:  # noqa: BLE001
                log.warning("MAX→TG: не удалось скачать медиа (%s)", m.get("type"), exc_info=True)
                return None
            # Настоящее имя файла MAX отдаёт ТОЛЬКО в Content-Disposition (в payload вложения
            # его нет — лишь url/token/fileId), иначе пришёл бы безликий «document.bin».
            name = cd_name or m.get("name") or f"{kind}.{_TG_KIND_EXT.get(kind, 'bin')}"
            # CDN MAX часто отдаёт content-type=application/octet-stream — уточняем тип по имени
            # (расширению), чтобы Telegram корректно показал/проиграл файл.
            if (not ct or ct == "application/octet-stream") and name:
                guessed, _ = mimetypes.guess_type(name)
                if guessed:
                    ct = guessed
            out.append({"kind": kind, "data": data, "name": name, "ct": ct})
        return out

    async def _tg_send_uploaded(self, chat_id, thread_id, prepared: list[dict[str, Any]],
                                send_text, parse_mode, *, reply_markup=None) -> tuple[int, Any, bool]:
        """Отправить скачанные MAX-медиа в Telegram, загружая байтами. BEST-EFFORT: возвращает
        сумму байт РЕАЛЬНО отправленного (0 — ничего не ушло, вызывающий деградирует до
        текст+ссылки), все Message-результаты успешных send* и флаг, был ли caption реально
        прикреплён к медиа. Не бросает исключений наверх (частичный успех не должен порождать
        дубль текст+ссылки и терять учёт трафика). Если caption передан для успешной группы
        или одиночного медиа, он ставится к первому успешному элементу; если группа упала и
        ушла поэлементно, caption откладывается — вызывающий отправит текст отдельно.

        reply_markup передаётся только для одиночных элементов (sendMediaGroup не поддерживает).

        Группировка в альбом (sendMediaGroup, 2-10 элементов): фото+видео можно вместе;
        аудио и документы — только однородной группой своего типа (док sendMediaGroup).
        Иначе/при сбое группы — поэлементно (порядок сохраняется)."""
        used = 0
        cap_pending = send_text or None     # подпись ждёт первого успешного элемента
        caption_sent = False
        caption_deferred = False
        sent_results: list[Any] = []

        def remember(sent: Any) -> None:
            if isinstance(sent, list):
                sent_results.extend(sent)
            elif sent is not None:
                sent_results.append(sent)

        async def _send_group(chunk: list[dict[str, Any]], caption) -> Any:
            group = []
            for i, p in enumerate(chunk):
                item = {"type": p["kind"],
                        "media": self._UploadFile(p["data"], filename=p["name"], content_type=p["ct"])}
                if i == 0 and caption:
                    item["caption"] = caption
                    if parse_mode:
                        item["parse_mode"] = parse_mode
                group.append(item)
            kw = {"message_thread_id": thread_id} if thread_id is not None else {}
            return await self.tg_client.send_media_group(chat_id, group, **kw)

        kinds = {p["kind"] for p in prepared}
        groupable = self._UploadFile is not None and len(prepared) > 1 and (
            kinds <= {"photo", "video"} or len(kinds) == 1)
        if groupable:
            ok_all = True
            for chunk in [prepared[i:i + 10] for i in range(0, len(prepared), 10)]:
                if len(chunk) == 1:                       # остаток в 1 элемент — не группа
                    try:
                        caption = None if caption_deferred else cap_pending
                        sent = await self._tg_send_one(chunk[0], chat_id, thread_id,
                                                       caption=caption,
                                                       parse_mode=parse_mode)
                        remember(sent)
                        used += len(chunk[0]["data"])
                        if caption:
                            caption_sent = True
                            cap_pending = None
                    except Exception:  # noqa: BLE001
                        log.warning("MAX→TG: элемент (%s) не отправлен", chunk[0].get("kind"), exc_info=True)
                        ok_all = False
                    continue
                try:
                    sent = await _send_group(chunk, cap_pending)
                    remember(sent)
                    used += sum(len(p["data"]) for p in chunk)
                    if cap_pending:
                        caption_sent = True
                    cap_pending = None
                except Exception:  # noqa: BLE001
                    log.info("MAX→TG: media group не прошла — отправляю поэлементно", exc_info=True)
                    ok_all = False
                    if cap_pending:
                        caption_deferred = True
                    for p in chunk:                       # фоллбэк: поэлементно
                        try:
                            sent = await self._tg_send_one(p, chat_id, thread_id,
                                                           caption=None if caption_deferred else cap_pending,
                                                           parse_mode=parse_mode)
                            remember(sent)
                            used += len(p["data"])
                            if cap_pending and not caption_deferred:
                                caption_sent = True
                                cap_pending = None
                        except Exception:  # noqa: BLE001
                            log.warning("MAX→TG: элемент (%s) не отправлен", p.get("kind"), exc_info=True)
            return used, sent_results, caption_sent
        # одиночный элемент или несовместимые типы — поэлементно
        rm_pending = reply_markup
        for p in prepared:
            try:
                sent = await self._tg_send_one(p, chat_id, thread_id, caption=cap_pending,
                                               parse_mode=parse_mode, reply_markup=rm_pending)
                remember(sent)
                used += len(p["data"])
                if cap_pending:
                    caption_sent = True
                cap_pending = None; rm_pending = None
            except Exception:  # noqa: BLE001
                log.warning("MAX→TG: элемент (%s) не отправлен", p.get("kind"), exc_info=True)
        return used, sent_results, caption_sent

    async def _tg_send_one(self, p: dict[str, Any], chat_id, thread_id, *, caption, parse_mode,
                           reply_markup=None) -> Any:
        """Отправить одно скачанное медиа байтами нужным методом. Для photo при отказе
        Telegram (например webp) — фоллбэк на документ (файл не теряем). Бросает исключение,
        только если и фоллбэк не прошёл (ловит вызывающий best-effort цикл)."""
        senders = {"photo": self.tg_client.send_photo, "video": self.tg_client.send_video,
                   "audio": self.tg_client.send_audio, "document": self.tg_client.send_document}
        primary = senders.get(p["kind"], self.tg_client.send_document)
        kw = {"message_thread_id": thread_id} if thread_id is not None else {}
        if reply_markup is not None:
            kw["reply_markup"] = reply_markup
        try:
            return await primary(chat_id, self._UploadFile(p["data"], filename=p["name"], content_type=p["ct"]),
                                 caption=caption, parse_mode=parse_mode, **kw)
        except Exception:  # noqa: BLE001
            if p["kind"] == "document":
                raise
            log.info("MAX→TG: %s не принят Telegram — отправляю документом", p["kind"], exc_info=True)
        return await self.tg_client.send_document(
            chat_id, self._UploadFile(p["data"], filename=p["name"], content_type=p["ct"]),
            caption=caption, parse_mode=parse_mode, **kw)

    async def _maybe_traffic_notify(self, acc_id: str) -> None:
        tr = self.store.traffic(acc_id)
        # Порог = месячный лимит аккаунта (индивидуальный оверрайд или дефолт).
        # Добавочный трафик не расширяет этот лимит: он хранится бессрочным остатком и
        # тратится только после превышения месячной квоты.
        et = self.store.effective_traffic(acc_id)
        limit = int(et.get("limit", 0))
        used = int(et.get("used", 0))
        if limit <= 0:
            return
        pct = used / limit
        flags = tr.get("_notified") or []
        if pct >= 1.0 and not bool(et.get("media_allowed")) and "exhausted" not in flags:
            # subtitle — из ФАКТИЧЕСКОГО месячного лимита (env/индивидуальный override меняют его;
            # раньше текст «0,5 ТБ из 0,5 ТБ» был захардкожен).
            await self.store.add_notification(acc_id, type="traffic",
                title="Медиа-трафик исчерпан",
                subtitle=f"{_fmt_bytes_ru(limit)} из {_fmt_bytes_ru(limit)}",
                link={"screen": "traffic"})
            await self.store.mark_traffic_flag(acc_id, "exhausted")
        elif pct >= 0.8 and "warn80" not in flags:
            await self.store.add_notification(acc_id, type="traffic",
                title="Использовано больше 80% трафика", link={"screen": "traffic"})
            await self.store.mark_traffic_flag(acc_id, "warn80")

    # ---- синхронизация правок (Этап 8) ----
    async def on_max_edit(self, norm: dict[str, Any]) -> None:
        """Правка сообщения в MAX → найти копии по маппингу и отредактировать."""
        if self.message_map is None:
            return
        if self._max_msg_is_own(norm):
            return
        f = _max_fields(norm)
        src_chat = f.get("chat_id")
        src_mid = f.get("mid")
        if src_chat is None or src_mid is None:
            return
        targets = self.message_map.lookup("max", str(src_chat), str(src_mid))
        if not targets:
            return
        text = f.get("text") or ""
        # Модерация правок: enforce не должен пропускать запрещёнку через РЕДАКТИРОВАНИЕ
        # (чистое прошло, потом отредактировали в нарушение). account_ids — из текущих правил.
        live = self.decide("max", str(src_chat), f.get("thread_id"))
        if not live:
            return  # источник без активных целей (правило на moderation_hold / аккаунт заблокирован)
        accounts = sorted({t.get("account_id") for t in live if t.get("account_id")})
        if await self._moderation_blocks("max", src_chat, text, accounts):
            return  # запрещённая правка не пропагируется в цели
        html, has_fmt = self._source_html("max", f, text)
        edited = 0
        for tgt_msn, tgt_chat, tgt_mid in targets:
            try:
                if tgt_msn == "tg":
                    await self._edit_tg(tgt_chat, tgt_mid, text, html if has_fmt else None)
                elif tgt_msn == "max":
                    await self._edit_max(tgt_mid, text, html if has_fmt else None)
                edited += 1
            except Exception as exc:  # noqa: BLE001
                log.warning("edit sync MAX→%s mid=%s не удался", tgt_msn, tgt_mid, exc_info=True)
                await self._svc_delivery_error(
                    "max", f, {"messenger": tgt_msn, "chat_id": tgt_chat}, exc,
                    kind="Ошибка синхронизации правки")
        if edited:
            self.message_map.update_text("max", str(src_chat), str(src_mid), text)

    async def on_tg_edit(self, norm: dict[str, Any]) -> None:
        """Правка сообщения в Telegram → найти копии по маппингу и отредактировать."""
        if self.message_map is None:
            return
        chat = norm.get("chat") or {}
        chat_id = chat.get("id")
        message_id = norm.get("message_id")
        if self._tg_msg_is_own(chat_id, message_id, norm.get("forward_origin")):
            return
        if chat_id is None or message_id is None:
            return
        targets = self.message_map.lookup("tg", str(chat_id), str(message_id))
        if not targets:
            return
        text = norm.get("text") or norm.get("caption") or ""
        # Модерация правок (см. on_max_edit): enforce блокирует пропагацию запрещённой правки.
        live = self.decide("tg", str(chat_id), norm.get("message_thread_id"))
        if not live:
            return  # источник без активных целей (правило на moderation_hold / аккаунт заблокирован)
        accounts = sorted({t.get("account_id") for t in live if t.get("account_id")})
        if await self._moderation_blocks("tg", chat_id, text, accounts):
            return
        text_kind = norm.get("text_kind")
        entities = norm.get("entities") or []
        html, has_fmt = self._fmt_html("tg", text, entities=entities)
        edited = 0
        for tgt_msn, tgt_chat, tgt_mid in targets:
            try:
                if tgt_msn == "tg":
                    await self._edit_tg(tgt_chat, tgt_mid, text, html if has_fmt else None,
                                        is_caption=(text_kind == "caption"))
                elif tgt_msn == "max":
                    await self._edit_max(tgt_mid, text, html if has_fmt else None)
                edited += 1
            except Exception as exc:  # noqa: BLE001
                log.warning("edit sync TG→%s mid=%s не удался", tgt_msn, tgt_mid, exc_info=True)
                await self._svc_delivery_error(
                    "tg", _tg_fields(norm), {"messenger": tgt_msn, "chat_id": tgt_chat}, exc,
                    kind="Ошибка синхронизации правки")
        if edited:
            self.message_map.update_text("tg", str(chat_id), str(message_id), text)

    async def _edit_tg(self, chat_id, message_id, text: str,
                       html: str | None, *, is_caption: bool = False) -> None:
        if self.tg_client is None:
            return
        body = html_for_telegram(html) if html else text
        pm = "HTML" if html else None
        if is_caption:
            await self.tg_client.edit_message_caption(chat_id, message_id, body, parse_mode=pm)
        else:
            await self.tg_client.edit_message_text(chat_id, message_id, body, parse_mode=pm,
                                                   disable_web_page_preview=True)

    async def _edit_max(self, message_id, text: str, html: str | None) -> None:
        if self.max_client is None:
            return
        body = html_for_max(html) if html else text
        fmt = "html" if html else None
        await self.max_client.edit_message(message_id, text=body, fmt=fmt)


# ---------------- фабрики хуков для оркестратора ----------------
def make_extra_codes_provider(store: ControlStore, messenger: str | None = None) -> Callable[[], dict[str, Any]]:
    """Провайдер активных кодов mini-app. Код привязки — ОБЩИЙ для аккаунта,
    независимо от мессенджера: оба бота (MAX и Telegram) принимают любой активный
    код аккаунта. Мессенджер привязки определяется тем, какой бот получил код."""
    def provider() -> dict[str, Any]:
        return {code: {"account_id": v.get("account_id")}
                for code, v in store.active_codes().items()}
    return provider


def make_source_notifier(max_client=None, tg_client=None):
    """Лаконичное сообщение в чат с ботом + inline-кнопка «Скрыть» (бот удаляет это сообщение
    по колбэку). hide_payload — данные кнопки: «hide_msg» (просто удалить — привязка/отвязка)
    либо «hide_warn:<messenger>:<chat_id>» (удалить + ре-армить уведомление о сбое доставки по
    цели). Возвращает результат отправки (для извлечения id сообщения) либо None, если клиента нет."""
    async def notify(messenger: str, user_id: Any, text: str, *, hide_payload: str = "hide_msg"):
        if messenger == "max" and max_client is not None:
            return await max_client.send_message(user_id=user_id, text=text, attachments=[{
                "type": "inline_keyboard",
                "payload": {"buttons": [[{"type": "callback", "text": "Скрыть", "payload": hide_payload}]]}}])
        if messenger == "tg" and tg_client is not None:
            return await tg_client.send_message(user_id, text, parse_mode=None,
                reply_markup={"inline_keyboard": [[{"text": "Скрыть", "callback_data": hide_payload}]]})
        return None
    return notify


def make_external_claim_cb(store: ControlStore, messenger: str, notifier=None):
    async def cb(code: str, sender_uid: Any, full_chat: dict[str, Any], marker: dict[str, Any]) -> None:
        acc_id = marker.get("account_id")
        chat_id = full_chat.get("chat_id") if full_chat.get("chat_id") is not None else full_chat.get("id")
        thread_id = full_chat.get("message_thread_id") if messenger == "tg" else None
        source_id = make_source_id(messenger, chat_id, thread_id) if chat_id is not None else None
        # Код НЕ потребляем — многоразовый в пределах 10 минут (несколько чатов одним кодом).
        if source_id:
            await store.record_code_bind(code, source_id)
        # Если отправитель известен (группы) — связываем его идентичность ДО уведомления,
        # чтобы «привязан» ушёл во все мессенджеры аккаунта, включая мессенджер отправителя.
        if acc_id and sender_uid is not None:
            await store.link_identity(messenger, sender_uid, acc_id)
        if acc_id and source_id:
            # Привязываем источник к АККАУНТУ напрямую — работает и для каналов, где у
            # поста нет отправителя (from), поэтому привязать к messenger-пользователю нельзя.
            await store.add_account_source(acc_id, source_id)
            base_title = full_chat.get("title") or chat_id
            title = topic_title(base_title, thread_id) if thread_id is not None else base_title
            await store.add_notification(acc_id, type="bound",
                title=f"Источник «{title}» привязан",
                subtitle=f"{'MAX' if messenger == 'max' else 'TG'}",
                link={"screen": "sources"})
            # Лаконичное уведомление в ЧАТ С БОТОМ — во ВСЕ привязанные мессенджеры аккаунта
            # (если привязаны оба). В мессенджере привязки приоритетен отправитель кода.
            if notifier is not None:
                recipients = store.identities_by_messenger(acc_id)
                if sender_uid is not None:
                    recipients[messenger] = sender_uid
                for m, uid in recipients.items():
                    try:
                        await notifier(m, uid, f"✅ Источник «{title}» привязан")
                    except Exception:  # noqa: BLE001
                        log.warning("source notifier сбой (%s)", m, exc_info=True)
    return cb


def make_chat_info_provider(max_client=None, tg_client=None):
    """Свежая инфа о чате/канале из мессенджера для списка источников: название + аватар.
    Возвращает dict {title, icon_url, photo_id} (любое поле может быть None) либо None
    при ошибке/отсутствии клиента.

    - title    — Telegram Chat.title / MAX Chat.title (авто-обновление имён).
    - icon_url — ТОЛЬКО MAX: публичный Chat.icon.url; отдаём фронту ПРЯМОЙ ссылкой
                 (в Telegram прямой ссылки нет — файл подписан токеном бота).
    - photo_id — ТОЛЬКО Telegram: ChatPhoto.small_file_unique_id; он «supposed to be the
                 same over time» и меняется ⇔ меняется фото, поэтому используется как
                 версия в URL аватара для авто-инвалидации кэша (content-addressing).
    Поля сверены с docs/telegram (Chat.title, ChatPhoto) и docs/max (Chat.title, Chat.icon)."""
    async def fetch(messenger: str, chat_id: Any) -> dict[str, Any] | None:
        if messenger == "tg":
            chat_id, _thread_id = parse_chat_key(chat_id)
        if messenger == "tg" and tg_client is not None:
            chat = await tg_client.get_chat(chat_id)
            if not chat:
                return None
            photo = chat.get("photo") or {}
            return {"title": chat.get("title"),
                    "photo_id": photo.get("small_file_unique_id"),
                    "icon_url": None}
        if messenger == "max" and max_client is not None:
            chat = await max_client.get_chat(chat_id)
            if not chat:
                return None
            url = ((chat.get("icon") or {}).get("url"))
            # icon.url едет прямо в браузер — отдаём только http(s) (отсекаем file:/data:/…).
            if url and not str(url).lower().startswith(("https://", "http://")):
                url = None
            return {"title": chat.get("title"), "icon_url": url, "photo_id": None}
        return None
    return fetch


def _image_content_type(data: bytes, header_ct: str | None) -> str:
    """Надёжный image/* content-type: Telegram отдаёт файлы как application/octet-stream,
    поэтому если заголовок не image/* — определяем тип по сигнатуре байтов (default JPEG)."""
    if header_ct and header_ct.lower().startswith("image/"):
        return header_ct.split(";")[0].strip()
    if data[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if data[:6] in (b"GIF87a", b"GIF89a"):
        return "image/gif"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return "image/jpeg"


def make_avatar_fetcher(max_client=None, tg_client=None):
    """Получить фото чата/канала как (content_type, bytes, version) или None, если фото нет.

    version = фактический идентификатор скачанного фото: Telegram small_file_unique_id
    (для сверки с запрошенной версией в get_avatar — чтобы под ключ версии A не попали
    байты фото B при смене фото между вызовами getChat), у MAX — None.
    Telegram: getChat → photo.small_file_id → getFile → скачать (ссылка подписана
    токеном, поэтому тянем на бэкенде). MAX: getChat → icon.url (публичный URL).
    Сигнатуры сверены с docs/telegram (ChatPhoto, getFile) и docs/max (Chat.icon).
    Исключения пробрасываем — вызывающий (avatars.get_avatar) отдаст устаревший кэш.
    """
    async def fetch(messenger: str, chat_id: Any):
        if messenger == "tg":
            chat_id, _thread_id = parse_chat_key(chat_id)
        if messenger == "tg" and tg_client is not None:
            chat = await tg_client.get_chat(chat_id)
            photo = (chat or {}).get("photo") or {}
            file_id = photo.get("small_file_id")
            if not file_id:
                return None
            info = await tg_client.get_file(file_id)
            file_path = info.get("file_path")
            if not file_path:
                return None
            data, ct = await tg_client.download_file_bytes(file_path)
            return (_image_content_type(data, ct), data, photo.get("small_file_unique_id"))
        if messenger == "max" and max_client is not None:
            chat = await max_client.get_chat(chat_id)
            url = ((chat or {}).get("icon") or {}).get("url")
            # icon.url приходит от платформы MAX (CDN), но качаем только по http(s) —
            # отсекаем неожиданные схемы (file:/data:/…) на стороне сервера.
            if not url or not str(url).lower().startswith(("https://", "http://")):
                return None
            data, ct, _ = await max_client.download_bytes(url)
            return (_image_content_type(data, ct), data, None)
        return None
    return fetch


def make_account_avatar_fetcher(max_client=None, tg_client=None):
    """Получить аватар пользователя аккаунта как (content_type, bytes, version) или None.

    MAX: используем avatar_url/full_avatar_url из сохранённого профиля UserWithPhoto
    (docs/max: UserWithPhoto.avatar_url/full_avatar_url). Telegram: getUserProfilePhotos →
    PhotoSize.file_id → getFile → скачать файл (docs/telegram: UserProfilePhotos, getFile).
    """
    async def fetch(messenger: str, user_id: Any, profile: dict[str, Any] | None = None):
        profile = profile or {}
        if messenger == "max" and max_client is not None:
            url = profile.get("full_avatar_url") or profile.get("avatar_url")
            if not url or not str(url).lower().startswith(("https://", "http://")):
                return None
            data, ct, _ = await max_client.download_bytes(str(url), max_bytes=5 * 1024 * 1024)
            return (_image_content_type(data, ct), data, None)
        if messenger == "tg" and tg_client is not None:
            photos = await tg_client.get_user_profile_photos(user_id, limit=1)
            rows = photos.get("photos") if isinstance(photos, dict) else None
            if not rows:
                return None
            sizes = rows[0] if isinstance(rows[0], list) else []
            if not sizes:
                return None
            best = max(sizes, key=lambda p: int((p or {}).get("width", 0)) * int((p or {}).get("height", 0)))
            file_id = best.get("file_id")
            if not file_id:
                return None
            info = await tg_client.get_file(file_id)
            file_path = info.get("file_path")
            if not file_path:
                return None
            data, ct = await tg_client.download_file_bytes(file_path, max_bytes=5 * 1024 * 1024)
            return (_image_content_type(data, ct), data, best.get("file_unique_id"))
        return None
    return fetch


def make_notifier(max_client=None, tg_client=None):
    """Служебные сообщения в чат с ботом (OTP входа, события биллинга). Как и остальные
    сервисные сообщения бота (кроме приветствия) — с inline-кнопкой «Скрыть»,
    поэтому просто переиспользуем make_source_notifier."""
    return make_source_notifier(max_client, tg_client)


def make_source_title_provider(max_own=None, tg_own=None):
    """Провайдер названия источника по (messenger, chat_id) для подписи копий.

    Берёт title из ownership бота (in-memory, без сети): сначала владелец, затем
    реестр чатов. None — если название неизвестно.
    """
    def title(messenger: str, chat_id: Any) -> str | None:
        own = max_own if messenger == "max" else tg_own if messenger == "tg" else None
        if own is None:
            return None
        try:
            base_id, thread_id = parse_chat_key(chat_id) if messenger == "tg" else (chat_id, None)
            base_title = own.title_of(base_id)
            return topic_title(base_title, thread_id) if thread_id is not None else base_title
        except Exception:  # noqa: BLE001
            return None
    return title


def make_chat_leaver(max_client=None, tg_client=None):
    async def leave(messenger: str, chat_id: Any) -> None:
        if messenger == "max" and max_client is not None:
            await max_client.leave_chat(chat_id)
        elif messenger == "tg" and tg_client is not None:
            await tg_client.leave_chat(chat_id)
    return leave


def make_source_unbinder(max_own=None, tg_own=None):
    """Полная отвязка источника при удалении из mini-app: удаляет запись из ownership
    бота (источник СРАЗУ исчезает из списка) И бот выходит из чата. Идёт через
    OwnershipManager.unbind обоих ботов — поэтому MAX и Telegram ведут себя одинаково
    (раньше delete_source лишь просил бота выйти и полагался на асинхронную чистку,
    которая для MAX-каналов не срабатывала → источник «оставался»)."""
    async def unbind(messenger: str, chat_id: Any) -> None:
        if messenger == "max" and max_own is not None:
            await max_own.unbind(chat_id)
        elif messenger == "tg" and tg_own is not None:
            await tg_own.unbind(chat_id)
    return unbind
