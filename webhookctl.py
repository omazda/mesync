#!/usr/bin/env python3
"""Управление вебхуком Telegram.

  python3 webhookctl.py info     # текущий статус вебхука (getWebhookInfo)
  python3 webhookctl.py set      # установить вебхук из .env (WEBHOOK_URL)
  python3 webhookctl.py delete   # снять вебхук (вернуться к polling)

Токен и настройки берутся из .env.
"""
import asyncio
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent / "src"))

from telegram_sync import config            # noqa: E402
from telegram_sync.client import TelegramClient  # noqa: E402


async def run(cmd: str) -> None:
    config.require_token()
    async with TelegramClient(config.BOT_TOKEN, config.API_BASE) as c:
        if cmd == "info":
            info = await c.call("getWebhookInfo")
            print(json.dumps(info, ensure_ascii=False, indent=2))
        elif cmd == "delete":
            ok = await c.call("deleteWebhook", {"drop_pending_updates": False})
            print("deleteWebhook ->", ok, "(теперь снова доступен polling)")
        elif cmd == "set":
            if not config.WEBHOOK_URL:
                raise SystemExit("WEBHOOK_URL не задан в .env")
            from urllib.parse import urlsplit
            files = None
            if config.WEBHOOK_CERTIFICATE:
                files = {"certificate": ("cert.pem",
                                         pathlib.Path(config.WEBHOOK_CERTIFICATE).read_bytes())}
            ok = await c.call("setWebhook", {
                "url": config.WEBHOOK_URL,
                "allowed_updates": config.ALLOWED_UPDATES,
                "secret_token": config.webhook_secret(),
                "max_connections": config.WEBHOOK_MAX_CONNECTIONS,
            }, files=files)
            print(f"setWebhook -> {ok} (url={config.WEBHOOK_URL}, путь={urlsplit(config.WEBHOOK_URL).path})")
        else:
            raise SystemExit("Использование: webhookctl.py {info|set|delete}")


if __name__ == "__main__":
    asyncio.run(run(sys.argv[1] if len(sys.argv) > 1 else "info"))
