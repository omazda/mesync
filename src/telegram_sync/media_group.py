"""Сборка альбомов (медиагрупп) с гарантией ПРАВИЛЬНОГО ПОРЯДКА медиафайлов.

В Telegram альбом приходит несколькими отдельными апдейтами: каждое сообщение
несёт один медиафайл и общий media_group_id. Правильный порядок файлов в
альбоме = по возрастанию message_id (так их и отображает клиент).

Части одного альбома могут прийти в разных ответах getUpdates, поэтому
буферизуем их по media_group_id и собираем после короткого окна "тишины"
(debounce), сортируя по message_id. Фоновая корутина-«подметальщик» выпускает
готовые альбомы вовремя, даже если новых апдейтов нет.
"""
from __future__ import annotations

import asyncio
from typing import Any, Awaitable, Callable

AlbumHandler = Callable[[dict[str, Any]], Awaitable[None]]


def build_album(media_group_id: str, parts: list[dict[str, Any]]) -> dict[str, Any]:
    """Собрать альбом из частей. parts уже отсортированы по message_id."""
    ordered_media: list[dict[str, Any]] = []
    for part in parts:
        for media in part.get("media", []):
            item = dict(media)
            item["album_order"] = len(ordered_media)      # глобальный порядок в альбоме
            item["source_message_id"] = part.get("message_id")
            ordered_media.append(item)

    first = parts[0]
    # Подпись и форматирование альбома обычно прикреплены к одной из частей.
    caption = next((p["text"] for p in parts if p.get("text")), None)
    entities = next((p["entities"] for p in parts if p.get("entities")), [])

    return {
        "kind": "album",
        "media_group_id": media_group_id,
        "update_kind": first.get("update_kind"),
        "chat": first.get("chat"),
        "message_thread_id": first.get("message_thread_id"),
        "is_topic_message": first.get("is_topic_message"),
        "from": first.get("from"),
        "sender_chat": first.get("sender_chat"),
        "date": first.get("date"),
        "message_ids": [p.get("message_id") for p in parts],  # в правильном порядке
        "caption": caption,
        "entities": entities,
        "media_count": len(ordered_media),
        "media": ordered_media,        # <-- медиафайлы В ПРАВИЛЬНОМ ПОРЯДКЕ
        "parts": parts,                # исходные части (с сырым JSON), ничего не теряем
    }


class MediaGroupAggregator:
    """Буферизует части альбомов и выпускает собранные альбомы в правильном порядке."""

    def __init__(self, on_album: AlbumHandler, *, debounce: float = 2.0,
                 sweep_interval: float = 0.5) -> None:
        self._on_album = on_album
        self._debounce = debounce
        self._sweep_interval = sweep_interval
        self._groups: dict[str, dict[str, Any]] = {}
        self._lock = asyncio.Lock()
        self._sweeper: asyncio.Task[None] | None = None
        self._stopping = asyncio.Event()

    async def __aenter__(self) -> "MediaGroupAggregator":
        self._sweeper = asyncio.create_task(self._sweep_loop())
        return self

    async def __aexit__(self, *_exc: object) -> None:
        await self.aclose()

    async def add(self, norm_message: dict[str, Any]) -> None:
        """Добавить часть альбома (нормализованное сообщение с media_group_id)."""
        gid = norm_message.get("media_group_id")
        if not gid:
            raise ValueError("add() ожидает сообщение с media_group_id")
        deadline = asyncio.get_running_loop().time() + self._debounce
        async with self._lock:
            group = self._groups.setdefault(gid, {"parts": []})
            group["parts"].append(norm_message)
            group["deadline"] = deadline  # сбрасываем окно при каждой новой части

    async def _sweep_loop(self) -> None:
        try:
            while not self._stopping.is_set():
                await asyncio.sleep(self._sweep_interval)
                await self._flush_due()
        except asyncio.CancelledError:
            pass

    async def _flush_due(self, *, force: bool = False) -> None:
        now = asyncio.get_running_loop().time()
        ready: list[tuple[str, dict[str, Any]]] = []
        async with self._lock:
            for gid, group in list(self._groups.items()):
                if force or now >= group.get("deadline", 0):
                    ready.append((gid, group))
                    del self._groups[gid]
        for gid, group in ready:
            parts = sorted(group["parts"], key=lambda m: (m.get("message_id") or 0))
            await self._on_album(build_album(gid, parts))

    async def flush_all(self) -> None:
        """Принудительно собрать все буферизованные альбомы (например, при остановке)."""
        await self._flush_due(force=True)

    async def aclose(self) -> None:
        self._stopping.set()
        if self._sweeper is not None:
            self._sweeper.cancel()
            try:
                await self._sweeper
            except asyncio.CancelledError:
                pass
            self._sweeper = None
        await self.flush_all()
