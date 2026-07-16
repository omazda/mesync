"""Отправка логов бота в MAX — пользователям, у кого есть диалог с ботом.

Состав (аналог telegram_sync.logship):
- ChatRegistry — персистентный реестр диалогов (user_id), пополняется из входящих
  событий диалогов;
- MaxLogHandler — logging.Handler, кладёт строки лога в потокобезопасную очередь;
- LogShipper — фоновая корутина: батчит строки (<= 4000 символов) и шлёт каждому
  получателю через POST /messages (user_id), уважая лимиты.

Бот может писать только тем, кто начал с ним диалог. Защита от рекурсии: НЕ
пересылаем записи логгеров сети/клиента (httpx, httpcore, max_sync.client) и
самого шиппера.
"""
from __future__ import annotations

import asyncio
import json
import logging
import queue
import sys
from pathlib import Path
from typing import Any, Callable

from .client import MaxClient, MaxError

_IGNORED_PREFIXES = ("httpx", "httpcore", "max_sync.client", "max_sync.logship")

_MAX_MSG = 4000        # лимит текста сообщения MAX — 4000 символов
_MAX_QUEUE = 1000


class ChatRegistry:
    """Персистентный набор диалогов (user_id), которым бот может писать."""

    def __init__(self, path: Path) -> None:
        self._path = Path(path)
        self._chats: dict[int, dict[str, Any]] = {}
        self._load()

    def _load(self) -> None:
        if not self._path.exists():
            return
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            return
        for item in data.get("dialogs", []):
            cid = item.get("user_id")
            if cid is not None:
                self._chats[int(cid)] = item

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"dialogs": list(self._chats.values())}
        self._path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def add(self, user_id: int, *, username: str | None = None,
            name: str | None = None) -> bool:
        cid = int(user_id)
        is_new = cid not in self._chats
        rec = self._chats.get(cid, {"user_id": cid})
        if username:
            rec["username"] = username
        if name:
            rec["name"] = name
        self._chats[cid] = rec
        if is_new or username or name:
            self._save()
        return is_new

    def remove(self, user_id: int) -> None:
        if int(user_id) in self._chats:
            del self._chats[int(user_id)]
            self._save()

    def ids(self) -> list[int]:
        return list(self._chats.keys())


class MaxLogHandler(logging.Handler):
    """Кладёт строки лога в очередь шиппера (синхронно, без сети)."""

    def __init__(self, q: "queue.SimpleQueue[str]",
                 has_recipients: Callable[[], bool]) -> None:
        super().__init__()
        self._q = q
        self._has_recipients = has_recipients

    def emit(self, record: logging.LogRecord) -> None:
        name = record.name
        if any(name == p or name.startswith(p + ".") for p in _IGNORED_PREFIXES):
            return
        if not self._has_recipients():
            return
        if self._q.qsize() >= _MAX_QUEUE:
            return
        try:
            self._q.put_nowait(self.format(record))
        except Exception:  # noqa: BLE001
            pass


class LogShipper:
    """Фоновая корутина: периодически шлёт накопленные строки лога получателям."""

    def __init__(self, client: MaxClient, registry: ChatRegistry, *,
                 interval: float = 2.0, allowlist: list[int] | None = None) -> None:
        self.client = client
        self.registry = registry
        self.interval = interval
        self.allowlist = allowlist or []
        self.queue: "queue.SimpleQueue[str]" = queue.SimpleQueue()
        self._task: asyncio.Task[None] | None = None
        self._stopping = asyncio.Event()

    def recipients(self) -> list[int]:
        return list(self.allowlist) if self.allowlist else self.registry.ids()

    def has_recipients(self) -> bool:
        return bool(self.recipients())

    def make_handler(self, level: int) -> MaxLogHandler:
        handler = MaxLogHandler(self.queue, self.has_recipients)
        handler.setLevel(level)
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s", "%H:%M:%S"))
        return handler

    async def __aenter__(self) -> "LogShipper":
        self._task = asyncio.create_task(self._run())
        return self

    async def __aexit__(self, *_exc: object) -> None:
        await self.aclose()

    async def _run(self) -> None:
        try:
            while not self._stopping.is_set():
                await asyncio.sleep(self.interval)
                await self._flush()
        except asyncio.CancelledError:
            pass

    def _drain(self) -> list[str]:
        lines: list[str] = []
        while True:
            try:
                lines.append(self.queue.get_nowait())
            except queue.Empty:
                break
        return lines

    @staticmethod
    def _batch(lines: list[str]) -> list[str]:
        batches: list[str] = []
        cur = ""
        for raw in lines:
            line = raw if len(raw) <= _MAX_MSG else raw[:_MAX_MSG - 1] + "…"
            if cur and len(cur) + 1 + len(line) > _MAX_MSG:
                batches.append(cur)
                cur = line
            else:
                cur = line if not cur else cur + "\n" + line
        if cur:
            batches.append(cur)
        return batches

    async def _flush(self) -> None:
        lines = self._drain()
        if not lines:
            return
        recipients = self.recipients()
        if not recipients:
            return
        for batch in self._batch(lines):
            for user_id in recipients:
                await self._send(user_id, batch)
                await asyncio.sleep(0.05)

    async def _send(self, user_id: int, text: str) -> None:
        try:
            await self.client.send_message(user_id=user_id, text=text,
                                           notify=False, disable_link_preview=True)
        except MaxError as exc:
            if exc.status_code in (400, 403, 404):
                self.registry.remove(user_id)
            print(f"[logship] send -> {user_id} не удалось: {exc}", file=sys.stderr)
        except Exception as exc:  # noqa: BLE001
            print(f"[logship] send -> {user_id} ошибка: {exc}", file=sys.stderr)

    async def aclose(self) -> None:
        self._stopping.set()
        if self._task is not None:
            try:
                await self._flush()
            except Exception:  # noqa: BLE001
                pass
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
