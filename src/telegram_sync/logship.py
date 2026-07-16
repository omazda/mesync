"""Отправка логов бота в Telegram — пользователям, с которыми у бота есть чат.

Состав:
- ChatRegistry — персистентный реестр приватных чатов (chat_id == id пользователя),
  пополняется при входящих апдейтах из приватных чатов;
- TelegramLogHandler — logging.Handler, кладущий отформатированные строки лога в
  потокобезопасную очередь (сам ничего не шлёт и не блокирует);
- LogShipper — фоновая корутина: раз в interval секунд берёт накопленные строки,
  объединяет в сообщения (<= 4096 символов) и шлёт каждому получателю через
  sendMessage, уважая лимиты Bot API.

Бот может писать только тем, кто сам начал с ним диалог (ограничение Telegram),
поэтому получатели — это приватные чаты из ChatRegistry.

Защита от рекурсии: НЕ пересылаем записи логгеров сети/клиента
(httpx, httpcore, telegram_sync.client) и самого шиппера — иначе ошибка отправки
породила бы новый лог и зациклилась.
"""
from __future__ import annotations

import asyncio
import json
import logging
import queue
import sys
from pathlib import Path
from typing import Any, Callable

from .client import TelegramClient, TelegramError

# Логгеры, чьи записи НЕ пересылаем в Telegram (риск рекурсии/шума).
_IGNORED_PREFIXES = ("httpx", "httpcore", "telegram_sync.client", "telegram_sync.logship")

_MAX_MSG = 4000        # запас до лимита Bot API в 4096 символов
_MAX_QUEUE = 1000      # ограничение памяти очереди


class ChatRegistry:
    """Персистентный набор приватных чатов, с которыми у бота есть переписка."""

    def __init__(self, path: Path) -> None:
        self._path = Path(path)
        self._chats: dict[int, dict[str, Any]] = {}
        self._load()

    def _load(self) -> None:
        if not self._path.exists():
            return
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001 — битый файл не должен ронять бота
            return
        for item in data.get("private_chats", []):
            cid = item.get("chat_id")
            if cid is not None:
                self._chats[int(cid)] = item

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"private_chats": list(self._chats.values())}
        self._path.write_text(json.dumps(payload, ensure_ascii=False, indent=2),
                              encoding="utf-8")

    def add(self, chat_id: int, *, username: str | None = None,
            name: str | None = None) -> bool:
        """Добавить/обновить чат. Возвращает True, если чат новый."""
        cid = int(chat_id)
        is_new = cid not in self._chats
        rec = self._chats.get(cid, {"chat_id": cid})
        if username:
            rec["username"] = username
        if name:
            rec["name"] = name
        self._chats[cid] = rec
        if is_new or username or name:
            self._save()
        return is_new

    def remove(self, chat_id: int) -> None:
        if int(chat_id) in self._chats:
            del self._chats[int(chat_id)]
            self._save()

    def ids(self) -> list[int]:
        return list(self._chats.keys())


class TelegramLogHandler(logging.Handler):
    """Кладёт строки лога в очередь шиппера (синхронно, без блокировок и сети)."""

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
            return  # некому слать — не копим
        if self._q.qsize() >= _MAX_QUEUE:
            return  # защита памяти
        try:
            self._q.put_nowait(self.format(record))
        except Exception:  # noqa: BLE001 — логирование не должно падать
            pass


class LogShipper:
    """Фоновая корутина: периодически шлёт накопленные строки лога получателям."""

    def __init__(self, client: TelegramClient, registry: ChatRegistry, *,
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

    def make_handler(self, level: int) -> TelegramLogHandler:
        handler = TelegramLogHandler(self.queue, self.has_recipients)
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
        """Склеить строки в сообщения не длиннее _MAX_MSG символов."""
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
            for chat_id in recipients:
                await self._send(chat_id, batch)
                await asyncio.sleep(0.05)  # мягкий темп между чатами

    async def _send(self, chat_id: int, text: str) -> None:
        try:
            await self.client.call("sendMessage", {
                "chat_id": chat_id,
                "text": text,
                "disable_web_page_preview": True,
                "disable_notification": True,
            })
        except TelegramError as exc:
            # 403 — пользователь заблокировал бота; 400 — чат недоступен: прекращаем слать.
            if exc.error_code in (400, 403):
                self.registry.remove(chat_id)
            print(f"[logship] sendMessage -> {chat_id} не удалось: {exc}", file=sys.stderr)
        except Exception as exc:  # noqa: BLE001
            print(f"[logship] sendMessage -> {chat_id} ошибка: {exc}", file=sys.stderr)

    async def aclose(self) -> None:
        self._stopping.set()
        if self._task is not None:
            try:
                await self._flush()  # финальный сброс остатка
            except Exception:  # noqa: BLE001
                pass
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
