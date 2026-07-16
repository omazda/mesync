"""Lookup helpers for normalized local content logs.

These helpers do not call messenger APIs. They only read JSONL files that were
written when the bot originally received updates, so they are suitable as a
fallback where a platform cannot reread messages by id.
"""
from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import Any

log = logging.getLogger("control.content_lookup")


def _text_value(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value)
    return text if text.strip() else None


def _matches_tg_item(item: dict[str, Any], chat_s: str, mid_s: str) -> bool:
    if str(((item.get("chat") or {}).get("id"))) != chat_s:
        return False
    if str(item.get("message_id")) == mid_s:
        return True
    message_ids = item.get("message_ids")
    if isinstance(message_ids, list) and any(str(x) == mid_s for x in message_ids):
        return True
    parts = item.get("parts")
    if isinstance(parts, list):
        return any(isinstance(p, dict) and str(p.get("message_id")) == mid_s for p in parts)
    return False


def _item_text(item: dict[str, Any], mid_s: str) -> str:
    """Return normalized text/caption for a matched item, or "" for known textless media."""
    parts_out: list[str] = []
    seen: set[str] = set()

    def add(value: Any) -> None:
        text = _text_value(value)
        if text is None:
            return
        key = text.strip()
        if key in seen:
            return
        seen.add(key)
        parts_out.append(text)

    for key in ("text", "caption"):
        add(item.get(key))
    parts = item.get("parts")
    if isinstance(parts, list):
        matched = [p for p in parts
                   if isinstance(p, dict) and str(p.get("message_id")) == mid_s]
        rest = [p for p in parts if isinstance(p, dict) and p not in matched]
        for part in [*matched, *rest]:
            for key in ("text", "caption"):
                add(part.get(key))
    return "\n\n".join(parts_out) if parts_out else ""


def lookup_tg_content_text_sync(path: str | Path, chat_id: Any, mid: Any) -> str | None:
    """Return the last normalized Telegram text/caption for (chat_id, message_id).

    ``None`` means the message was not found in the local log. ``""`` means it was
    found, but the Telegram update had no text/caption (for example a media-only
    album), so reports can distinguish that from an unavailable message.
    """
    if chat_id is None or mid is None:
        return None
    chat_s = str(chat_id)
    mid_s = str(mid)
    found: str | None = None
    try:
        with Path(path).open("r", encoding="utf-8") as fh:
            for raw in fh:
                try:
                    item = json.loads(raw)
                except ValueError:
                    continue
                if not isinstance(item, dict) or not _matches_tg_item(item, chat_s, mid_s):
                    continue
                found = _item_text(item, mid_s)
    except FileNotFoundError:
        return None
    except OSError as exc:
        log.warning("content lookup: не удалось прочитать %s: %s", path, exc)
        return None
    return found


async def lookup_tg_content_text(path: str | Path, chat_id: Any, mid: Any) -> str | None:
    return await asyncio.to_thread(lookup_tg_content_text_sync, path, chat_id, mid)
