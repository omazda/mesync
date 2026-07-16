"""Webhook-режим Этапа 1: приём апдейтов через HTTPS POST от Telegram.

Рекомендованная схема: Telegram --HTTPS--> обратный прокси/туннель (валидный TLS)
--HTTP--> этот сервер локально. Либо прямой TLS — см. WEBHOOK_TLS_CERT/KEY.

Сервер быстро отвечает 200 и кладёт апдейт в очередь; единый воркер
последовательно обрабатывает их через общий UpdateRouter (порядок сохраняется).
Проверяется заголовок X-Telegram-Bot-Api-Secret-Token (см. setWebhook → secret_token,
docs/telegram/markdown/06-webhooks.md).
"""
from __future__ import annotations

import asyncio
import logging

from aiohttp import web

from .updates import UpdateRouter

log = logging.getLogger(__name__)

SECRET_HEADER = "X-Telegram-Bot-Api-Secret-Token"


class WebhookServer:
    def __init__(self, router: UpdateRouter, *, host: str, port: int, path: str,
                 secret: str | None, queue_max: int = 10000) -> None:
        self.router = router
        self.host = host
        self.port = port
        self.path = path or "/"
        self.secret = secret
        self._queue: asyncio.Queue = asyncio.Queue(maxsize=queue_max)
        self._worker: asyncio.Task | None = None
        self._runner: web.AppRunner | None = None
        self._stop = asyncio.Event()

    def request_stop(self) -> None:
        self._stop.set()

    async def _health(self, _request: web.Request) -> web.Response:
        return web.Response(text="ok")

    async def _handle(self, request: web.Request) -> web.Response:
        # Проверяем секрет — что запрос действительно от нашего вебхука.
        if self.secret and request.headers.get(SECRET_HEADER) != self.secret:
            log.warning("Webhook: неверный secret-заголовок от %s — отклонено", request.remote)
            return web.Response(status=403, text="forbidden")
        try:
            update = await request.json()
        except Exception:  # noqa: BLE001
            return web.Response(status=400, text="bad request")
        if not isinstance(update, dict):
            return web.Response(status=400, text="bad request")
        try:
            self._queue.put_nowait(update)
        except asyncio.QueueFull:
            log.error("Webhook: очередь переполнена — апдейт отброшен (Telegram повторит)")
            return web.Response(status=503, text="busy")
        return web.Response(text="ok")        # быстрый 200, не дожидаясь обработки

    async def _worker_loop(self) -> None:
        while True:
            update = await self._queue.get()
            try:
                await self.router.process(update)
            except Exception:  # noqa: BLE001
                log.exception("Webhook: ошибка обработки апдейта")
            finally:
                self._queue.task_done()

    async def serve(self, *, ssl_context=None) -> None:
        """Запустить сервер и работать до request_stop()."""
        app = web.Application()
        app.router.add_post(self.path, self._handle)
        app.router.add_get("/healthz", self._health)
        self._worker = asyncio.create_task(self._worker_loop())
        self._runner = web.AppRunner(app, access_log=None)
        await self._runner.setup()
        site = web.TCPSite(self._runner, self.host, self.port, ssl_context=ssl_context)
        await site.start()
        log.info("Webhook-сервер слушает %s:%d путь %s (TLS=%s)",
                 self.host, self.port, self.path, bool(ssl_context))
        await self._stop.wait()
        await self._shutdown()

    async def _shutdown(self) -> None:
        log.info("Webhook-сервер останавливается…")
        if self._runner is not None:        # перестаём принимать новые запросы
            await self._runner.cleanup()
            self._runner = None
        try:                                # дообрабатываем то, что уже в очереди
            await asyncio.wait_for(self._queue.join(), timeout=15)
        except asyncio.TimeoutError:
            log.warning("Webhook: не успели обработать всю очередь за 15с")
        if self._worker is not None:
            self._worker.cancel()
            try:
                await self._worker
            except asyncio.CancelledError:
                pass
            self._worker = None
