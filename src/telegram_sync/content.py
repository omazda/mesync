"""Извлечение АБСОЛЮТНО ВСЕГО контента из сообщений Telegram.

Принцип: ничего не теряем. Каждый Message нормализуется в удобную структуру,
но исходный JSON всегда кладётся в поле raw. Медиа извлекаются с полными
метаданными. Порядок медиафайлов ВНУТРИ альбома обеспечивает media_group.py
(сортировка частей по message_id); порядок нескольких медиа внутри одного
сообщения (paid_media) сохраняется по индексу массива.

Поля сверены с docs/telegram/markdown/04-api-reference.md (объект Message).
"""
from __future__ import annotations

from typing import Any

# Поля Message, несущие один прикреплённый файл. Сообщение Telegram несёт
# НЕ БОЛЕЕ ОДНОГО такого медиа (поэтому при поиске берём первое совпадение).
# animation-сообщения для совместимости также содержат document — animation
# идёт раньше, поэтому document не задвоится.
_SINGLE_FILE_MEDIA: list[tuple[str, str]] = [
    ("photo", "photo"),
    ("animation", "animation"),
    ("video", "video"),
    ("video_note", "video_note"),
    ("audio", "audio"),
    ("voice", "voice"),
    ("sticker", "sticker"),
    ("live_photo", "live_photo"),
    ("document", "document"),
]

# Структурированный контент без файла.
_STRUCTURED = ["contact", "location", "venue", "poll", "dice", "game",
               "invoice", "story", "checklist"]

# Поля-сервисные события (service messages) — их тоже нельзя терять.
_SERVICE_FIELDS = [
    "new_chat_members", "left_chat_member", "new_chat_title", "new_chat_photo",
    "delete_chat_photo", "group_chat_created", "supergroup_chat_created",
    "channel_chat_created", "message_auto_delete_timer_changed",
    "migrate_to_chat_id", "migrate_from_chat_id", "pinned_message",
    "successful_payment", "refunded_payment", "users_shared", "chat_shared",
    "write_access_allowed", "proximity_alert_triggered", "boost_added",
    "chat_background_set", "forum_topic_created", "forum_topic_edited",
    "forum_topic_closed", "forum_topic_reopened", "general_forum_topic_hidden",
    "general_forum_topic_unhidden", "giveaway_created", "giveaway",
    "giveaway_winners", "giveaway_completed", "video_chat_scheduled",
    "video_chat_started", "video_chat_ended", "video_chat_participants_invited",
    "web_app_data", "gift", "unique_gift", "connected_website", "passport_data",
]

# Поля Update, несущие объект Message (в порядке проверки).
MESSAGE_UPDATE_FIELDS = [
    "message", "edited_message", "channel_post", "edited_channel_post",
    "business_message", "edited_business_message", "guest_message",
]


def best_photo_size(photo: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Крупнейший размер фото — по площади width*height (массив PhotoSize)."""
    if not photo:
        return None
    return max(photo, key=lambda p: int(p.get("width", 0)) * int(p.get("height", 0)))


def _file_descriptor(media_type: str, obj: Any) -> dict[str, Any]:
    """Единый дескриптор медиа с доступными метаданными."""
    desc: dict[str, Any] = {"type": media_type}
    if media_type == "photo":
        sizes = obj if isinstance(obj, list) else []
        primary = best_photo_size(sizes) or {}
        desc.update({
            "file_id": primary.get("file_id"),
            "file_unique_id": primary.get("file_unique_id"),
            "file_size": primary.get("file_size"),
            "width": primary.get("width"),
            "height": primary.get("height"),
            "sizes": sizes,  # все размеры — ничего не теряем
        })
        return desc
    o = obj if isinstance(obj, dict) else {}
    for key in ("file_id", "file_unique_id", "file_size", "file_name",
                "mime_type", "width", "height", "duration", "length",
                "performer", "title", "emoji", "is_animated", "is_video"):
        if key in o:
            desc[key] = o[key]
    thumb = o.get("thumbnail") or o.get("thumb")
    if isinstance(thumb, dict):
        desc["thumbnail_file_id"] = thumb.get("file_id")
    desc["raw"] = o
    return desc


def extract_media(message: dict[str, Any]) -> list[dict[str, Any]]:
    """Медиафайлы сообщения в правильном порядке.

    Обычно 0 или 1 элемент (одно сообщение несёт одно медиа). paid_media может
    содержать несколько элементов — сохраняем их порядок по индексу массива.
    Порядок МЕЖДУ сообщениями альбома обеспечивает media_group.py (по message_id).
    """
    media: list[dict[str, Any]] = []

    paid = message.get("paid_media")
    if isinstance(paid, dict) and isinstance(paid.get("paid_media"), list):
        for i, item in enumerate(paid["paid_media"]):
            entry: dict[str, Any] = {"type": "paid_media", "order_index": i,
                                     "star_count": paid.get("star_count"), "raw": item}
            if isinstance(item, dict):
                if item.get("photo"):
                    entry["photo"] = _file_descriptor("photo", item["photo"])
                if item.get("video"):
                    entry["video"] = _file_descriptor("video", item["video"])
            media.append(entry)

    for field, mtype in _SINGLE_FILE_MEDIA:
        if message.get(field):
            media.append(_file_descriptor(mtype, message[field]))
            break  # сообщение несёт не более одного такого медиа

    for i, item in enumerate(media):
        item.setdefault("order_index", i)
    return media


def _sender_name(message: dict[str, Any]) -> str | None:
    frm = message.get("from") or {}
    name = " ".join(p for p in (frm.get("first_name"), frm.get("last_name")) if p) \
        or frm.get("username") or None
    if name:
        return name
    return message.get("author_signature") or (message.get("sender_chat") or {}).get("title")


def _reply_quote(message: dict[str, Any] | None,
                 text_quote: dict[str, Any] | None = None) -> dict[str, Any] | None:
    """Сжать reply_to_message Telegram в цитату для кросс-мессенджерной пересылки.

    Bot API кладёт в reply_to_message исходный Message без дальнейших вложенных reply. Нам
    нужен только текст/подпись и entities; если пользователь выделил конкретную цитату,
    Bot API кладёт её в поле quote (TextQuote) — тогда берём именно её. Медиа без caption
    цитатой не показываем.
    """
    if not isinstance(message, dict):
        return None
    qtext: str | None = None
    entities: list[dict[str, Any]] = []
    if isinstance(text_quote, dict) and text_quote.get("text"):
        qtext = text_quote.get("text")
        entities = text_quote.get("entities") or []
    if qtext is None:
        text = message.get("text")
        caption = message.get("caption")
        qtext = text if text is not None else caption
        entities = message.get("entities") or message.get("caption_entities") or []
    if not qtext:
        return None
    return {
        "text": qtext,
        "entities": entities,
        "from": _sender_name(message),
    }


def normalize_message(message: dict[str, Any], update_kind: str) -> dict[str, Any]:
    """Нормализовать Message, сохранив сырой JSON и весь контент."""
    text = message.get("text")
    caption = message.get("caption")
    entities = message.get("entities") or message.get("caption_entities") or []
    chat = message.get("chat", {})

    service = {k: message[k] for k in _SERVICE_FIELDS if k in message}
    structured = {k: message[k] for k in _STRUCTURED if k in message}

    return {
        "update_kind": update_kind,
        "message_id": message.get("message_id"),
        "media_group_id": message.get("media_group_id"),
        "date": message.get("date"),
        "edit_date": message.get("edit_date"),
        "chat": {
            "id": chat.get("id"),
            "type": chat.get("type"),
            "title": chat.get("title"),
            "username": chat.get("username"),
            "is_forum": chat.get("is_forum"),
        },
        "message_thread_id": message.get("message_thread_id"),
        "is_topic_message": message.get("is_topic_message"),
        "from": message.get("from"),
        "sender_chat": message.get("sender_chat"),
        "author_signature": message.get("author_signature"),
        "via_bot": message.get("via_bot"),
        "forward_origin": message.get("forward_origin"),
        "reply_to_message_id": (message.get("reply_to_message") or {}).get("message_id"),
        "reply": _reply_quote(message.get("reply_to_message"), message.get("quote")),
        "text": text if text is not None else caption,
        "text_kind": "text" if text is not None else ("caption" if caption is not None else None),
        "entities": entities,
        "reply_markup": message.get("reply_markup"),
        "has_media_spoiler": message.get("has_media_spoiler", False),
        "media": extract_media(message),
        "structured": structured or None,
        "service": service or None,
        "raw": message,
    }


def message_summary(norm: dict[str, Any]) -> str:
    """Краткое человекочитаемое описание сообщения для логов."""
    chat = norm["chat"]
    who = chat.get("title") or chat.get("username") or chat.get("id")
    parts: list[str] = [f"[{chat.get('type')}:{who}] msg#{norm['message_id']}"]
    if norm.get("media_group_id"):
        parts.append(f"album={norm['media_group_id']}")
    if norm["media"]:
        types = ",".join(str(m["type"]) for m in norm["media"])
        parts.append(f"media[{len(norm['media'])}]:{types}")
    if norm.get("structured"):
        parts.append("+" + ",".join(norm["structured"].keys()))
    if norm.get("service"):
        parts.append("service:" + ",".join(norm["service"].keys()))
    if norm["text"]:
        flat = norm["text"].replace("\n", " ")
        parts.append(f'"{flat[:60]}"' + ("…" if len(norm["text"]) > 60 else ""))
    return " ".join(str(p) for p in parts)


# Поля Update, у которых есть объект chat (для определения приватных чатов).
_CHAT_BEARING_FIELDS = [
    "message", "edited_message", "channel_post", "edited_channel_post",
    "business_message", "edited_business_message", "guest_message",
    "my_chat_member", "chat_member", "chat_join_request",
    "message_reaction", "message_reaction_count",
]


def private_chats_in_update(update: dict[str, Any]) -> list[tuple[Any, dict[str, Any] | None]]:
    """Вернуть [(chat_id, from_user)] для приватных чатов, встретившихся в апдейте.

    «Приватный чат» (chat.type == 'private') = диалог бота с пользователем,
    значит боту в него можно писать (например, слать логи).
    """
    found: list[tuple[Any, dict[str, Any] | None]] = []
    for field in _CHAT_BEARING_FIELDS:
        obj = update.get(field)
        if isinstance(obj, dict):
            chat = obj.get("chat")
            if isinstance(chat, dict) and chat.get("type") == "private":
                found.append((chat.get("id"), obj.get("from")))
    cq = update.get("callback_query")
    if isinstance(cq, dict):
        msg = cq.get("message")
        chat = msg.get("chat") if isinstance(msg, dict) else None
        if isinstance(chat, dict) and chat.get("type") == "private":
            found.append((chat.get("id"), cq.get("from")))
    return found


def chats_in_update(update: dict[str, Any]) -> list[dict[str, Any]]:
    """Все объекты chat, встречающиеся в апдейте (любого типа)."""
    chats: list[dict[str, Any]] = []
    for field in _CHAT_BEARING_FIELDS:
        obj = update.get(field)
        if isinstance(obj, dict) and isinstance(obj.get("chat"), dict):
            chats.append(obj["chat"])
    cq = update.get("callback_query")
    if isinstance(cq, dict) and isinstance(cq.get("message"), dict) \
            and isinstance(cq["message"].get("chat"), dict):
        chats.append(cq["message"]["chat"])
    return chats
