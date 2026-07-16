"""Бот MAX — entrypoint. Режим приёма выбирается config.MODE (polling|webhook).

- валидация токена через GET /me;
- отправка логов в MAX (оба режима);
- polling (GET /updates с marker) ИЛИ webhook (HTTPS-сервер + POST /subscriptions);
- корректная остановка по Ctrl+C / SIGTERM.
"""
from __future__ import annotations

import asyncio
import contextlib
import logging
import signal
from urllib.parse import urlsplit

from . import config
from .client import MaxClient, MaxError
from .logship import ChatRegistry, LogShipper
from .ownership import OwnershipManager
from .storage import Storage
from .updates import Stage1Poller, UpdateRouter
from .webhook import WebhookServer

log = logging.getLogger("max_sync")


def _setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s | %(message)s",
        datefmt="%H:%M:%S",
    )
    for noisy in ("httpx", "httpcore", "aiohttp.access", "aiohttp.server"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def _install_signals(callback) -> None:
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, callback)
        except NotImplementedError:
            pass


async def _run_polling(client: MaxClient, storage: Storage, registry: ChatRegistry,
                       ownership: OwnershipManager, bot_id: int | None) -> None:
    poller = Stage1Poller(
        client, storage, chat_registry=registry, ownership=ownership,
        update_types=config.UPDATE_TYPES,
        timeout=config.LONG_POLL_TIMEOUT, limit=config.GET_UPDATES_LIMIT,
        download_media=config.DOWNLOAD_MEDIA, max_download_bytes=config.MAX_DOWNLOAD_BYTES,
        mirror=config.MIRROR_TO_OWNER, bot_id=bot_id)
    run_task = asyncio.create_task(poller.run())
    _install_signals(run_task.cancel)
    try:
        await run_task
    except asyncio.CancelledError:
        log.info("Остановлено. marker сохранён.")


async def _run_webhook(client: MaxClient, storage: Storage, registry: ChatRegistry,
                       ownership: OwnershipManager, bot_id: int | None) -> None:
    if not config.WEBHOOK_URL:
        raise SystemExit("MAX_MODE=webhook, но MAX_WEBHOOK_URL не задан в .env")
    path = urlsplit(config.WEBHOOK_URL).path or "/"
    secret = config.webhook_secret()

    ssl_ctx = None
    if config.WEBHOOK_TLS_CERT and config.WEBHOOK_TLS_KEY:
        import ssl
        ssl_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ssl_ctx.load_cert_chain(config.WEBHOOK_TLS_CERT, config.WEBHOOK_TLS_KEY)

    async with UpdateRouter(
        client, storage, download_media=config.DOWNLOAD_MEDIA,
        max_download_bytes=config.MAX_DOWNLOAD_BYTES, chat_registry=registry,
        ownership=ownership, mirror=config.MIRROR_TO_OWNER, bot_id=bot_id,
    ) as router:
        server = WebhookServer(router, host=config.WEBHOOK_HOST, port=config.WEBHOOK_PORT,
                               path=path, secret=secret)
        # СНАЧАЛА связываем порт, ПОТОМ подписываемся — чтобы endpoint был доступен
        # к моменту TLS-валидации со стороны MAX.
        await server.start(ssl_context=ssl_ctx)
        res = await client.subscribe(config.WEBHOOK_URL, config.UPDATE_TYPES, secret=secret)
        log.info("POST /subscriptions: success=%s%s", res.get("success", res),
                 f" ({res.get('message')})" if res.get("message") else "")
        try:
            subs = await client.get_subscriptions()
            log.info("Текущие подписки: %s",
                     [s.get("url") for s in (subs.get("subscriptions") or [])])
        except MaxError as exc:
            log.warning("get_subscriptions не удался: %s", exc.description)
        _install_signals(server.request_stop)
        await server.wait()
    log.info("Webhook остановлен.")


async def _amain() -> None:
    config.require_token()
    storage = Storage(config.RAW_UPDATES_FILE, config.CONTENT_FILE,
                      config.MARKER_FILE, config.MEDIA_DIR)

    async with MaxClient(config.BOT_TOKEN, config.API_BASE) as client:
        try:
            me = await client.get_me()
        except MaxError as exc:
            raise SystemExit(f"Не удалось авторизоваться (GET /me): {exc}") from exc
        bot_id = me.get("user_id")
        log.info("Бот @%s (user_id=%s), токен=%s, режим=%s",
                 me.get("username"), bot_id, config.masked_token(), config.MODE)
        log.warning("Чтобы получать сообщения групп/каналов, бот должен быть АДМИНИСТРАТОРОМ "
                    "(см. docs/max/markdown/docs-api/methods/GET/updates.md).")

        registry = ChatRegistry(config.KNOWN_CHATS_FILE)
        ownership = OwnershipManager(client, config.OWNERSHIP_FILE, bot_id=bot_id,
                                     raw_updates_file=config.RAW_UPDATES_FILE)
        async with contextlib.AsyncExitStack() as stack:
            if config.LOG_TO_MESSENGER:
                shipper = await stack.enter_async_context(
                    LogShipper(client, registry, interval=config.LOG_SHIP_INTERVAL,
                               allowlist=config.LOG_CHAT_ALLOWLIST))
                level = getattr(logging, config.LOG_TO_MESSENGER_LEVEL, logging.INFO)
                handler = shipper.make_handler(level)
                mx_logger = logging.getLogger("max_sync")
                mx_logger.addHandler(handler)
                stack.callback(mx_logger.removeHandler, handler)
                log.info("Отправка логов в MAX включена (уровень %s, получателей: %d)",
                         config.LOG_TO_MESSENGER_LEVEL, len(shipper.recipients()))

            await stack.enter_async_context(ownership)
            log.info("Привязка чатов к пользователям (ownership) активна.")

            if config.MODE == "webhook":
                await _run_webhook(client, storage, registry, ownership, bot_id)
            else:
                await _run_polling(client, storage, registry, ownership, bot_id)


def main() -> None:
    _setup_logging()
    try:
        asyncio.run(_amain())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
