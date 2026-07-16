#!/usr/bin/env python3
"""Управление Webhook-подписками MAX.

  python3 maxsubctl.py info     # список подписок (GET /subscriptions)
  python3 maxsubctl.py set      # подписаться на MAX_WEBHOOK_URL (POST /subscriptions)
  python3 maxsubctl.py delete   # отписаться от MAX_WEBHOOK_URL (DELETE /subscriptions)

Токен и настройки берутся из .env (MAX_*).
"""
import asyncio
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent / "src"))

from max_sync import config            # noqa: E402
from max_sync.client import MaxClient  # noqa: E402


async def run(cmd: str) -> None:
    config.require_token()
    async with MaxClient(config.BOT_TOKEN, config.API_BASE) as c:
        if cmd == "info":
            info = await c.get_subscriptions()
            print(json.dumps(info, ensure_ascii=False, indent=2))
        elif cmd == "delete":
            if not config.WEBHOOK_URL:
                raise SystemExit("MAX_WEBHOOK_URL не задан в .env")
            res = await c.unsubscribe(config.WEBHOOK_URL)
            print("DELETE /subscriptions ->", res, "(теперь доступен Long Polling)")
        elif cmd == "set":
            if not config.WEBHOOK_URL:
                raise SystemExit("MAX_WEBHOOK_URL не задан в .env")
            res = await c.subscribe(config.WEBHOOK_URL, config.UPDATE_TYPES,
                                    secret=config.webhook_secret())
            print(f"POST /subscriptions -> {res} (url={config.WEBHOOK_URL})")
        else:
            raise SystemExit("Использование: maxsubctl.py {info|set|delete}")


if __name__ == "__main__":
    asyncio.run(run(sys.argv[1] if len(sys.argv) > 1 else "info"))
