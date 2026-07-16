"""Персистентный реестр id сообщений, СОЗДАННЫХ ботом, — чтобы бот никогда не реагировал
(не синхронизировал) на собственные сообщения.

Зачем: при двунаправленном правиле (A→B и B→A) копия, которую бот публикует в B, не
должна уйти обратно в A (петля). Эхо-защита по `sender_id == bot_id` работает только в
группах — у постов КАНАЛОВ отправителя нет. Поэтому ведём реестр: ключ —
`(messenger, chat_id, mid)` каждого отправленного ботом сообщения. Любое входящее
сообщение, чей (chat_id, mid) — наш, пропускается; так же распознаётся пересланный
пользователем пост, который изначально создал бот (по оригиналу пересылки).

Проверка в горячем пути (`contains`) — синхронная по in-memory индексу. На диск
сбрасывается атомарно (tmp+replace), с дебаунсом, поэтому реестр переживает рестарты
(ловит и поздние пересылки своих сообщений). Ограничен TTL и максимальным размером.
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from collections import OrderedDict
from pathlib import Path
from typing import Any

log = logging.getLogger("control.sent_index")


class SentIndex:
    """Реестр «своих» сообщений: messenger:chat_id:mid -> время записи (для TTL)."""

    def __init__(self, path: str | Path, *, ttl_seconds: int, max_entries: int) -> None:
        self.path = Path(path)
        self.ttl = max(0, int(ttl_seconds))
        self.max_entries = max(1, int(max_entries))
        self._d: "OrderedDict[str, float]" = OrderedDict()
        self._dirty = False
        self._lock = asyncio.Lock()

    @staticmethod
    def _key(messenger: str, chat_id: Any, mid: Any) -> str:
        return f"{messenger}:{chat_id}:{mid}"

    # ---- загрузка/проверка/запись ----
    def load(self) -> None:
        """Прочитать индекс с диска (на старте), отбросив протухшее по TTL."""
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return
        except (ValueError, OSError) as exc:
            log.warning("sent_index: не удалось прочитать %s: %s", self.path, exc)
            return
        items = raw.get("items") if isinstance(raw, dict) else None
        if not isinstance(items, dict):
            return
        now = time.time()
        live = [(k, t) for k, t in items.items()
                if isinstance(t, (int, float)) and (self.ttl == 0 or now - t < self.ttl)]
        live.sort(key=lambda kt: kt[1])           # по времени: старые раньше
        for k, t in live[-self.max_entries:]:     # не больше лимита (оставляем свежие)
            self._d[k] = float(t)

    def contains(self, messenger: str, chat_id: Any, mid: Any) -> bool:
        """True, если (messenger, chat_id, mid) — сообщение, отправленное ботом."""
        if mid is None or chat_id is None:
            return False
        k = self._key(messenger, chat_id, mid)
        t = self._d.get(k)
        if t is None:
            return False
        if self.ttl and time.time() - t >= self.ttl:
            self._d.pop(k, None)                  # лениво вычищаем протухшее
            self._dirty = True
            return False
        return True

    def remember(self, messenger: str, chat_id: Any, mid: Any) -> None:
        """Запомнить отправленное ботом сообщение (синхронно, без блокировок)."""
        if mid is None or chat_id is None:
            return
        k = self._key(messenger, chat_id, mid)
        self._d[k] = time.time()
        self._d.move_to_end(k)
        while len(self._d) > self.max_entries:
            self._d.popitem(last=False)           # вытесняем старейшее (FIFO)
        self._dirty = True

    # ---- персистентность ----
    def _save_sync(self, items: dict[str, float]) -> None:
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps({"items": items}, ensure_ascii=False), encoding="utf-8")
        tmp.replace(self.path)

    async def flush(self) -> None:
        """Сбросить индекс на диск, если были изменения (атомарно)."""
        if not self._dirty:
            return
        async with self._lock:
            if not self._dirty:
                return
            self._dirty = False
            snapshot = dict(self._d)              # копия в event loop (без гонки с remember)
            try:
                await asyncio.to_thread(self._save_sync, snapshot)
            except OSError as exc:
                self._dirty = True                # не записалось — попробуем в следующий раз
                log.warning("sent_index: не удалось записать %s: %s", self.path, exc)

    async def run(self, interval: float = 10.0) -> None:
        """Фоновый дебаунс-сброс: пишем на диск не чаще раза в `interval`, только при изменениях.
        На отмене (остановка приложения) делает финальный сброс."""
        try:
            while True:
                await asyncio.sleep(interval)
                await self.flush()
        except asyncio.CancelledError:
            await self.flush()
            raise
