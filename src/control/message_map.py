"""Персистентный маппинг source ↔ target сообщений.

Хранит соответствие «исходное сообщение → список его копий в целевых чатах».
Нужен для синхронизации правок и удалений: при изменении оригинала бот ищет
по маппингу свои копии и редактирует/удаляет их.

Ключ записи: (messenger, chat_id, mid).
Значение: список (tgt_messenger, tgt_chat_id, tgt_mid).

Персистентность — атомарный JSON-файл (tmp + rename), с дебаунсом (как SentIndex).
TTL + max_entries: старые записи вытесняются по времени и по размеру.
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from collections import OrderedDict
from pathlib import Path
from typing import Any

from . import config

log = logging.getLogger("control.message_map")


class MessageMap:
    def __init__(self, path: str | Path, *, ttl_seconds: int = 604800,
                 max_entries: int = 200_000,
                 text_limit: int | None = None) -> None:
        self.path = Path(path)
        self.ttl = max(0, int(ttl_seconds))
        self.max_entries = max(1, int(max_entries))
        limit = config.MODERATION_REPORT_TEXT_SNAPSHOT_LIMIT if text_limit is None else text_limit
        self.text_limit = max(0, int(limit))
        self._fwd: "OrderedDict[str, _Entry]" = OrderedDict()
        self._rev: dict[str, str] = {}
        self._dirty = False
        self._lock = asyncio.Lock()

    @staticmethod
    def _key(messenger: str, chat_id: Any, mid: Any) -> str:
        return f"{messenger}:{chat_id}:{mid}"

    def _text(self, value: Any) -> str | None:
        if value is None or self.text_limit <= 0:
            return None
        text = str(value)
        if len(text) > self.text_limit:
            return text[:self.text_limit]
        return text

    def _drop_entry(self, k: str, entry: "_Entry") -> None:
        self._fwd.pop(k, None)
        for t in entry.targets:
            self._rev.pop(self._key(*t), None)

    def _live_entry(self, k: str) -> "_Entry | None":
        entry = self._fwd.get(k)
        if entry is None:
            return None
        if self.ttl and time.time() - entry.ts >= self.ttl:
            self._drop_entry(k, entry)
            self._dirty = True
            return None
        return entry

    def load(self) -> None:
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return
        except (ValueError, OSError) as exc:
            log.warning("message_map: не удалось прочитать %s: %s", self.path, exc)
            return
        items = raw.get("items") if isinstance(raw, dict) else None
        if not isinstance(items, dict):
            return
        now = time.time()
        live = []
        for k, v in items.items():
            if not isinstance(v, dict):
                continue
            ts = v.get("ts")
            if not isinstance(ts, (int, float)):
                continue
            if self.ttl and now - ts >= self.ttl:
                continue
            targets = v.get("targets")
            if not isinstance(targets, list):
                continue
            text = self._text(v.get("text")) if isinstance(v.get("text"), str) else None
            live.append((k, ts, targets, text))
        live.sort(key=lambda x: x[1])
        for k, ts, targets, text in live[-self.max_entries:]:
            entry = _Entry(
                ts=ts,
                targets=[tuple(t) for t in targets if isinstance(t, list) and len(t) == 3],
                text=text)
            self._fwd[k] = entry
            for t in entry.targets:
                self._rev[self._key(*t)] = k

    def record(self, src_messenger: str, src_chat_id: Any, src_mid: Any,
               tgt_messenger: str, tgt_chat_id: Any, tgt_mid: Any, *,
               text: Any = None) -> None:
        if src_mid is None or tgt_mid is None:
            return
        src_key = self._key(src_messenger, src_chat_id, src_mid)
        tgt_tuple = (tgt_messenger, str(tgt_chat_id), str(tgt_mid))
        entry = self._fwd.get(src_key)
        if entry is None:
            entry = _Entry(ts=time.time(), targets=[], text=None)
            self._fwd[src_key] = entry
        if tgt_tuple not in entry.targets:
            entry.targets.append(tgt_tuple)
        new_text = self._text(text)
        if new_text is not None:
            entry.text = new_text
        entry.ts = time.time()
        self._fwd.move_to_end(src_key)
        tgt_key = self._key(*tgt_tuple)
        self._rev[tgt_key] = src_key
        while len(self._fwd) > self.max_entries:
            old_k, old_e = self._fwd.popitem(last=False)
            for t in old_e.targets:
                self._rev.pop(self._key(*t), None)
        self._dirty = True

    def update_text(self, messenger: str, chat_id: Any, mid: Any, text: Any) -> None:
        """Обновить текстовый снимок source-сообщения без изменения списка целей."""
        if mid is None:
            return
        k = self._key(messenger, chat_id, mid)
        entry = self._live_entry(k)
        if entry is None:
            return
        entry.text = self._text(text)
        entry.ts = time.time()
        self._fwd.move_to_end(k)
        self._dirty = True

    def text_snapshot(self, messenger: str, chat_id: Any, mid: Any) -> str | None:
        """Вернуть сохранённый текст source-сообщения.

        Если передали координаты target-копии, пытаемся через reverse map найти source.
        Пустую строку считаем отсутствием текста для целей модерации жалоб.
        """
        if mid is None:
            return None
        k = self._key(messenger, chat_id, mid)
        entry = self._live_entry(k)
        if entry is None:
            src_key = self._rev.get(k)
            entry = self._live_entry(src_key) if src_key else None
        if entry is None or not entry.text or not str(entry.text).strip():
            return None
        return entry.text

    def lookup(self, messenger: str, chat_id: Any, mid: Any) -> list[tuple[str, str, str]]:
        if mid is None:
            return []
        k = self._key(messenger, chat_id, mid)
        entry = self._live_entry(k)
        if entry is None:
            return []
        return list(entry.targets)

    def reverse_lookup(self, tgt_messenger: str, tgt_chat_id: Any,
                       tgt_mid: Any) -> str | None:
        """По target mid найти ключ source (для дедупа эхо-правок)."""
        return self._rev.get(self._key(tgt_messenger, tgt_chat_id, tgt_mid))

    def _save_sync(self, data: dict) -> None:
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        tmp.replace(self.path)

    async def flush(self) -> None:
        if not self._dirty:
            return
        async with self._lock:
            if not self._dirty:
                return
            self._dirty = False
            snapshot = {}
            for k, e in self._fwd.items():
                item = {"ts": e.ts, "targets": [list(t) for t in e.targets]}
                if e.text is not None:
                    item["text"] = e.text
                snapshot[k] = item
            try:
                await asyncio.to_thread(self._save_sync, {"items": snapshot})
            except OSError as exc:
                self._dirty = True
                log.warning("message_map: не удалось записать %s: %s", self.path, exc)

    async def run(self, interval: float = 10.0) -> None:
        try:
            while True:
                await asyncio.sleep(interval)
                await self.flush()
        except asyncio.CancelledError:
            await self.flush()
            raise

    def __len__(self) -> int:
        return len(self._fwd)


class _Entry:
    __slots__ = ("ts", "targets", "text")

    def __init__(self, ts: float, targets: list[tuple], text: str | None = None) -> None:
        self.ts = ts
        self.targets = targets
        self.text = text
