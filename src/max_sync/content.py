"""Извлечение контента из событий MAX (объект Update и вложенный Message).

Принцип тот же, что в telegram_sync.content: ничего не теряем — сырой JSON всегда
кладётся в поле raw, а удобные поля выносим наверх. В MAX одно сообщение может нести
СРАЗУ НЕСКОЛЬКО вложений (body.attachments[]), поэтому понятия «альбом из отдельных
сообщений», как в Telegram, здесь нет — каждое message_created самодостаточно.

Структура события сверена с docs/max/ (objects/Update, objects/Message,
docs/chatbots/bots-coding/* — message.recipient.chat_id, message.body.mid).
"""
from __future__ import annotations

from typing import Any

# Типы чатов MAX (Chat.type / recipient.chat_type).
GROUP_LIKE_TYPES = {"chat", "channel"}     # групповой чат и канал
DIALOG_TYPE = "dialog"                      # личный диалог с ботом

# Поля payload вложений, которые удобно вынести в метаданные (без потери raw).
_ATTACH_META_KEYS = ("url", "token", "code", "vcf_info", "lat", "lon", "mid", "name")


def is_group_like(chat_type: str | None) -> bool:
    return chat_type in GROUP_LIKE_TYPES


def extract_attachments(body: dict[str, Any]) -> list[dict[str, Any]]:
    """Вложения сообщения в порядке массива. Клавиатуру (inline_keyboard) тоже
    сохраняем, но помечаем — её не считаем «медиа»."""
    out: list[dict[str, Any]] = []
    for i, a in enumerate(body.get("attachments") or []):
        if not isinstance(a, dict):
            continue
        payload = a.get("payload") if isinstance(a.get("payload"), dict) else {}
        entry: dict[str, Any] = {"type": a.get("type"), "order_index": i}
        for k in _ATTACH_META_KEYS:
            if k in payload:
                entry[k] = payload[k]
        entry["raw"] = a
        out.append(entry)
    return out


def media_attachments(attachments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Только медиа-вложения (без клавиатур)."""
    return [a for a in attachments if a.get("type") != "inline_keyboard"]


def _content_source(body: dict[str, Any], link: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    """Откуда брать контент (текст/markup/вложения) сообщения.

    В MAX пересланный пост несёт контент во вложенном `link.message`, а верхний `body`
    при этом обычно пуст (док Message: «body может быть null, если сообщение содержит
    только пересланное сообщение» — сверено с docs/max/.../objects/Message.md и живым
    сырьём: forward-пост канала отдаёт text="" без attachments, реальные текст+медиа в
    link.message). Но MAX допускает и форвард С КОММЕНТАРИЕМ/своими вложениями (свой body
    непуст). Чтобы ничего не терять, для forward берём НЕДОСТАЮЩЕЕ из link.message: текст
    (+markup) — из своего body, если есть, иначе из пересланного; вложения — из своего
    body, если есть, иначе из пересланного. Для reply контент в своём body — link лишь
    цитата, её не подставляем. Возвращает (источник_контента, is_forward)."""
    if link.get("type") == "forward" and isinstance(link.get("message"), dict):
        fwd = link["message"]
        src = dict(body)
        if not (body.get("text") or "").strip() and fwd.get("text"):
            src["text"] = fwd.get("text")
            src["markup"] = fwd.get("markup")     # markup парно с текстом (офсеты UTF-16)
        if not body.get("attachments") and fwd.get("attachments"):
            src["attachments"] = fwd.get("attachments")
        return src, True
    return body, False


def _reply_quote(link: dict[str, Any]) -> dict[str, Any] | None:
    """Процитированное сообщение для ОТВЕТА (reply): текст+markup оригинала и имя его автора.

    MAX отдаёт ответ как link.type=="reply" с оригиналом во вложенном link.message и автором
    оригинала в link.sender (сверено вживую: GET /messages reply-сообщения). Для forward не
    вызывается (там контент подставляется в _content_source). Возвращает {text, markup, from}
    или None (если это не reply либо у оригинала нет текста)."""
    if link.get("type") != "reply" or not isinstance(link.get("message"), dict):
        return None
    qm = link["message"]
    qtext = qm.get("text")
    if not (qtext and str(qtext).strip()):
        return None
    snd = link.get("sender") or {}
    name = " ".join(p for p in (snd.get("first_name"), snd.get("last_name")) if p) \
        or snd.get("name") or snd.get("username") or None
    return {"text": qtext, "markup": qm.get("markup"), "from": name}


def normalize_message(message: dict[str, Any], update_type: str) -> dict[str, Any]:
    """Нормализовать объект Message (из message_created/message_edited)."""
    body = message.get("body") if isinstance(message.get("body"), dict) else {}
    recipient = message.get("recipient") if isinstance(message.get("recipient"), dict) else {}
    sender = message.get("sender") if isinstance(message.get("sender"), dict) else {}
    link = message.get("link") if isinstance(message.get("link"), dict) else {}
    # Контент пересланного поста лежит в link.message (верхний body пуст) — см. _content_source.
    src, is_forward = _content_source(body, link)
    attachments = extract_attachments(src)
    return {
        "update_type": update_type,
        "mid": body.get("mid"),             # mid/seq — всегда из ПОЛУЧЕННОГО сообщения
        "seq": body.get("seq"),             # (для эхо-защиты и нативного forward по mid)
        "chat_id": recipient.get("chat_id"),
        "chat_type": recipient.get("chat_type"),
        "recipient_user_id": recipient.get("user_id"),
        "sender": sender,
        "sender_id": sender.get("user_id"),
        "timestamp": message.get("timestamp"),
        "text": src.get("text"),
        "markup": src.get("markup"),        # форматирование (entities, офсеты в UTF-16)
        "attachments": attachments,
        "media": media_attachments(attachments),
        "is_forward": is_forward,
        "reply": _reply_quote(link),    # процитированное сообщение (ответ), иначе None
        "link": link or None,
        "url": message.get("url"),
        "raw": message,
    }


def message_summary(norm: dict[str, Any]) -> str:
    """Краткое человекочитаемое описание сообщения для логов."""
    parts: list[str] = [f"[{norm.get('chat_type')}:{norm.get('chat_id')}] mid={norm.get('mid')}"]
    if norm.get("is_forward"):
        parts.append("fwd")
    snd = norm.get("sender") or {}
    who = snd.get("username") or snd.get("first_name") or snd.get("user_id")
    if who:
        parts.append(f"from={who}")
    media = norm.get("media") or []
    if media:
        types = ",".join(str(m.get("type")) for m in media)
        parts.append(f"media[{len(media)}]:{types}")
    if norm.get("link"):
        parts.append("link:" + str((norm["link"] or {}).get("type")))
    if norm.get("text"):
        flat = str(norm["text"]).replace("\n", " ")
        parts.append(f'"{flat[:60]}"' + ("…" if len(norm["text"]) > 60 else ""))
    return " ".join(str(p) for p in parts)


def update_summary(update: dict[str, Any]) -> str:
    ut = update.get("update_type", "unknown")
    bits = [ut]
    if update.get("chat_id") is not None:
        bits.append(f"chat_id={update.get('chat_id')}")
    u = update.get("user") or {}
    if u.get("user_id") is not None:
        bits.append(f"user={u.get('username') or u.get('first_name') or u.get('user_id')}")
    return " ".join(bits)


def chats_in_update(update: dict[str, Any]) -> list[dict[str, Any]]:
    """Все групповые чаты/каналы, встретившиеся в апдейте (для реестра ownership).

    Возвращает [{chat_id, type, title?}]. Источники chat_id:
    - message.recipient (message_created/edited/removed-варианты);
    - chat_id верхнего уровня (bot_added/bot_removed/user_added/user_removed/
      chat_title_changed) — тип определяется по is_channel.
    """
    out: list[dict[str, Any]] = []
    msg = update.get("message")
    if isinstance(msg, dict):
        rcp = msg.get("recipient") or {}
        if rcp.get("chat_id") is not None and is_group_like(rcp.get("chat_type")):
            out.append({"chat_id": rcp.get("chat_id"), "type": rcp.get("chat_type")})
    if update.get("chat_id") is not None:
        ctype = "channel" if update.get("is_channel") else "chat"
        rec = {"chat_id": update.get("chat_id"), "type": ctype}
        title = update.get("title")
        if title:
            rec["title"] = title
        out.append(rec)
    return out


def dialogs_in_update(update: dict[str, Any]) -> list[tuple[Any, dict[str, Any]]]:
    """[(user_id, user)] для диалогов, которым бот может писать (логи, ответы).

    Это отправители сообщений в личных диалогах и пользователь из bot_started.
    """
    out: list[tuple[Any, dict[str, Any]]] = []
    msg = update.get("message")
    if isinstance(msg, dict):
        rcp = msg.get("recipient") or {}
        snd = msg.get("sender") or {}
        if rcp.get("chat_type") == DIALOG_TYPE and snd.get("user_id") is not None:
            out.append((snd.get("user_id"), snd))
    if update.get("update_type") == "bot_started":
        u = update.get("user") or {}
        if u.get("user_id") is not None:
            out.append((u.get("user_id"), u))
    return out
