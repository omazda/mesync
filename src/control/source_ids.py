"""Helpers for source identifiers used by the control API.

Public source id format:
- "<messenger>:<chat_id>" for regular MAX/TG chats and channels;
- "tg:<chat_id>:<message_thread_id>" for a Telegram forum topic.

The Telegram chat id stays separate from the topic id: Bot API methods still receive
chat_id=<chat_id> and message_thread_id=<message_thread_id>.
"""
from __future__ import annotations

from typing import Any


def _norm_thread_id(thread_id: Any) -> str | None:
    if thread_id is None:
        return None
    tid = str(thread_id).strip()
    return tid or None


def make_source_id(messenger: str, chat_id: Any, thread_id: Any | None = None) -> str:
    base = f"{messenger}:{chat_id}"
    tid = _norm_thread_id(thread_id)
    if messenger == "tg" and tid is not None:
        return f"{base}:{tid}"
    return base


def make_chat_key(chat_id: Any, thread_id: Any | None = None) -> str:
    tid = _norm_thread_id(thread_id)
    return f"{chat_id}:{tid}" if tid is not None else str(chat_id)


def parse_chat_key(key: Any) -> tuple[str, str | None]:
    parts = str(key).split(":", 1)
    return parts[0], parts[1] if len(parts) == 2 and parts[1] else None


def parse_source_id(source_id: str) -> dict[str, str] | None:
    parts = str(source_id or "").split(":")
    if len(parts) not in (2, 3):
        return None
    messenger = parts[0]
    if messenger not in ("max", "tg") or not parts[1]:
        return None
    if messenger != "tg" and len(parts) == 3:
        return None
    out = {"messenger": messenger, "chat_id": parts[1]}
    if len(parts) == 3:
        if not parts[2]:
            return None
        out["thread_id"] = parts[2]
    return out


def endpoint_source_id(ep: dict[str, Any]) -> str:
    return make_source_id(ep["messenger"], ep["chat_id"], ep.get("thread_id"))


def endpoint_chat_key(ep: dict[str, Any]) -> str:
    return make_chat_key(ep["chat_id"], ep.get("thread_id") if ep.get("messenger") == "tg" else None)


def telegram_thread_param(thread_id: Any) -> int | str | None:
    tid = _norm_thread_id(thread_id)
    if tid is None:
        return None
    try:
        return int(tid)
    except ValueError:
        return tid


def telegram_send_thread_param(thread_id: Any) -> int | str | None:
    """Bot API send* parameter for a Telegram topic target.

    Internally we use thread_id="1" as a stable source id for the General topic,
    because incoming General messages often arrive without message_thread_id. For
    sending, Telegram routes to General when message_thread_id is omitted; sending
    message_thread_id=1 can fail with "message thread not found" in real forums.
    """
    tid = _norm_thread_id(thread_id)
    if tid == "1":
        return None
    return telegram_thread_param(tid)


def topic_title(base_title: Any, thread_id: Any, topic_name: Any | None = None) -> str:
    base = str(base_title or "").strip()
    suffix = str(topic_name or "").strip()
    if not suffix:
        suffix = "General" if str(thread_id) == "1" else f"тема {thread_id}"
    return f"{base} · {suffix}" if base else suffix
