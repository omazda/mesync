"""Этап 1 — entrypoint. Режим приёма апдейтов выбирается config.MODE (polling|webhook).

- валидация токена через getMe;
- отправка логов в Telegram (оба режима);
- polling (getUpdates) ИЛИ webhook (HTTPS-сервер + setWebhook);
- корректная остановка по Ctrl+C / SIGTERM.
"""
from __future__ import annotations

import asyncio
import contextlib
import logging
import signal
from pathlib import Path
from urllib.parse import urlsplit

from . import config
from .client import TelegramClient, TelegramError
from .logship import ChatRegistry, LogShipper
from .ownership import OwnershipManager
from .storage import Storage
from .updates import Stage1Poller, UpdateRouter
from .webhook import WebhookServer

log = logging.getLogger("telegram_sync")


def _setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s | %(message)s",
        datefmt="%H:%M:%S",
    )
    # httpx/httpcore/aiohttp логируют URL/доступы — приглушаем (в URL есть токен).
    for noisy in ("httpx", "httpcore", "aiohttp.access", "aiohttp.server"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def _install_signals(callback) -> None:
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, callback)
        except NotImplementedError:  # на некоторых платформах недоступно
            pass


async def _run_polling(client: TelegramClient, storage: Storage, registry: ChatRegistry,
                       ownership: OwnershipManager) -> None:
    poller = Stage1Poller(
        client, storage, chat_registry=registry, ownership=ownership,
        allowed_updates=config.ALLOWED_UPDATES,
        timeout=config.LONG_POLL_TIMEOUT, limit=config.GET_UPDATES_LIMIT,
        download_media=config.DOWNLOAD_MEDIA, max_download_bytes=config.MAX_DOWNLOAD_BYTES,
        media_debounce=config.MEDIA_GROUP_DEBOUNCE, mirror=config.MIRROR_TO_OWNER)
    run_task = asyncio.create_task(poller.run())
    _install_signals(run_task.cancel)
    try:
        await run_task
    except asyncio.CancelledError:
        log.info("Остановлено. Буферизованные альбомы дособраны, offset сохранён.")


async def _run_webhook(client: TelegramClient, storage: Storage, registry: ChatRegistry,
                       ownership: OwnershipManager) -> None:
    if not config.WEBHOOK_URL:
        raise SystemExit("MODE=webhook, но WEBHOOK_URL не задан в .env")
    path = urlsplit(config.WEBHOOK_URL).path or "/"
    secret = config.webhook_secret()

    # Регистрируем вебхук в Telegram (это отключает getUpdates).
    params = {
        "url": config.WEBHOOK_URL,
        "allowed_updates": config.ALLOWED_UPDATES,
        "secret_token": secret,
        "max_connections": config.WEBHOOK_MAX_CONNECTIONS,
        "drop_pending_updates": False,
    }
    files = None
    if config.WEBHOOK_CERTIFICATE:
        files = {"certificate": ("cert.pem", Path(config.WEBHOOK_CERTIFICATE).read_bytes())}
    await client.call("setWebhook", params, files=files)
    info = await client.call("getWebhookInfo")
    log.info("setWebhook OK: url=%s, путь=%s, pending=%s, max_conn=%s",
             info.get("url"), path, info.get("pending_update_count"), info.get("max_connections"))
    if info.get("last_error_message"):
        log.warning("Webhook: последняя ошибка доставки от Telegram — %s", info.get("last_error_message"))

    ssl_ctx = None
    if config.WEBHOOK_TLS_CERT and config.WEBHOOK_TLS_KEY:
        import ssl
        ssl_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ssl_ctx.load_cert_chain(config.WEBHOOK_TLS_CERT, config.WEBHOOK_TLS_KEY)

    async with UpdateRouter(
        client, storage, download_media=config.DOWNLOAD_MEDIA,
        max_download_bytes=config.MAX_DOWNLOAD_BYTES,
        media_debounce=config.MEDIA_GROUP_DEBOUNCE, chat_registry=registry,
        ownership=ownership, mirror=config.MIRROR_TO_OWNER,
    ) as router:
        server = WebhookServer(router, host=config.WEBHOOK_HOST, port=config.WEBHOOK_PORT,
                               path=path, secret=secret)
        _install_signals(server.request_stop)
        await server.serve(ssl_context=ssl_ctx)
    log.info("Webhook остановлен.")


async def _amain() -> None:
    config.require_token()
    storage = Storage(config.RAW_UPDATES_FILE, config.CONTENT_FILE,
                      config.OFFSET_FILE, config.MEDIA_DIR)

    async with TelegramClient(config.BOT_TOKEN, config.API_BASE) as client:
        try:
            me = await client.get_me()
        except TelegramError as exc:
            raise SystemExit(f"Не удалось авторизоваться (getMe): {exc}") from exc
        log.info("Бот @%s (id=%s), токен=%s, режим=%s",
                 me.get("username"), me.get("id"), config.masked_token(), config.MODE)
        log.warning("Чтобы получать ВСЕ сообщения в группах, бот должен быть администратором "
                    "либо иметь отключённый Privacy Mode "
                    "(см. docs/telegram/markdown/02-features.md, раздел Privacy Mode).")

        registry = ChatRegistry(config.KNOWN_CHATS_FILE)
        ownership = OwnershipManager(client, config.OWNERSHIP_FILE, bot_id=me.get("id"),
                                     raw_updates_file=config.RAW_UPDATES_FILE,
                                     bot_can_read_all=bool(me.get("can_read_all_group_messages")))
        async with contextlib.AsyncExitStack() as stack:
            if config.LOG_TO_TELEGRAM:
                shipper = await stack.enter_async_context(
                    LogShipper(client, registry, interval=config.LOG_SHIP_INTERVAL,
                               allowlist=config.LOG_CHAT_ALLOWLIST))
                level = getattr(logging, config.LOG_TO_TELEGRAM_LEVEL, logging.INFO)
                handler = shipper.make_handler(level)
                tg_logger = logging.getLogger("telegram_sync")
                tg_logger.addHandler(handler)
                stack.callback(tg_logger.removeHandler, handler)
                log.info("Отправка логов в Telegram включена (уровень %s, получателей сейчас: %d)",
                         config.LOG_TO_TELEGRAM_LEVEL, len(shipper.recipients()))

            await stack.enter_async_context(ownership)
            log.info("Привязка чатов к пользователям (ownership) активна.")

            if config.MODE == "webhook":
                await _run_webhook(client, storage, registry, ownership)
            else:
                await _run_polling(client, storage, registry, ownership)


def main() -> None:
    _setup_logging()
    try:
        asyncio.run(_amain())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
