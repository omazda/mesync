"""Webhook-режим: приём событий MAX через HTTPS POST на /subscriptions-endpoint.

Схема (как у telegram_sync): MAX --HTTPS--> обратный прокси (валидный TLS, порт 443)
--HTTP--> этот сервер локально. MAX требует HTTPS на порту 443 и сертификат от
доверенного CA (см. docs/max/markdown/docs-api/methods/POST/subscriptions.md).

Сервер быстро отвечает 200 и кладёт событие в очередь; единый воркер
последовательно обрабатывает их через общий UpdateRouter (порядок сохраняется).
Проверяется заголовок X-Max-Bot-Api-Secret (значение secret из POST /subscriptions).
"""
from __future__ import annotations

import asyncio
import logging

from aiohttp import web

from .updates import UpdateRouter

log = logging.getLogger(__name__)

SECRET_HEADER = "X-Max-Bot-Api-Secret"


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
            log.error("Webhook: очередь переполнена — событие отброшено (MAX повторит)")
            return web.Response(status=503, text="busy")
        return web.Response(text="ok")        # быстрый 200, не дожидаясь обработки

    async def _worker_loop(self) -> None:
        while True:
            update = await self._queue.get()
            try:
                await self.router.process(update)
            except Exception:  # noqa: BLE001
                log.exception("Webhook: ошибка обработки события")
            finally:
                self._queue.task_done()

    async def start(self, *, ssl_context=None) -> None:
        """Поднять сервер и СВЯЗАТЬ порт (не блокирует). Вызвать ДО подписки,
        чтобы endpoint был доступен к моменту TLS-валидации со стороны MAX."""
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

    async def wait(self) -> None:
        """Блокироваться до request_stop(), затем корректно остановиться."""
        await self._stop.wait()
        await self._shutdown()

    async def serve(self, *, ssl_context=None) -> None:
        """Удобный вариант: start() + wait() одним вызовом."""
        await self.start(ssl_context=ssl_context)
        await self.wait()

    async def _shutdown(self) -> None:
        log.info("Webhook-сервер останавливается…")
        if self._runner is not None:
            await self._runner.cleanup()
            self._runner = None
        try:
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
