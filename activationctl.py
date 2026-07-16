#!/usr/bin/env python3
"""Управление кодами активации подписки (админ).

  .venv/bin/python activationctl.py gen [N]   # сгенерировать N кодов (по умолчанию 1)
  .venv/bin/python activationctl.py list      # сводка: свободные и использованные коды

Работает через админ-эндпоинты запущенного control-API (/api/admin/activation-codes),
поэтому коды сразу видны приложению — файл стора руками не трогаем. Адрес и ключ —
из .env (MESYNC_API_HOST/MESYNC_API_PORT, MESYNC_ADMIN_KEY).
"""
from __future__ import annotations

import asyncio
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent / "src"))

import httpx  # noqa: E402

from control import config  # noqa: E402


def _base_url() -> str:
    host = config.API_HOST if config.API_HOST not in ("0.0.0.0", "::") else "127.0.0.1"
    return f"http://{host}:{config.API_PORT}/api/admin/activation-codes"


async def run(cmd: str, count: int) -> None:
    if not config.ADMIN_KEY:
        print("MESYNC_ADMIN_KEY не задан в .env — админ-эндпоинты выключены.", file=sys.stderr)
        raise SystemExit(2)
    headers = {"X-Admin-Key": config.ADMIN_KEY}
    async with httpx.AsyncClient(timeout=30) as client:
        if cmd == "gen":
            resp = await client.post(_base_url(), json={"count": count}, headers=headers)
            resp.raise_for_status()
            codes = resp.json().get("codes") or []
            print(f"Сгенерировано кодов: {len(codes)}")
            for code in codes:
                print(code)
        elif cmd == "list":
            resp = await client.get(_base_url(), headers=headers)
            resp.raise_for_status()
            data = resp.json()
            print(f"Всего: {data.get('total', 0)}, свободных: {len(data.get('unused') or [])}, "
                  f"использованных: {len(data.get('used') or [])}")
            for code in data.get("unused") or []:
                print(f"  {code}")
            for rec in data.get("used") or []:
                print(f"  {rec.get('code')}  → {rec.get('used_by')} (ts={rec.get('used_at')})")
        else:
            print(__doc__)
            raise SystemExit(2)


def main() -> None:
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    count = int(sys.argv[2]) if len(sys.argv) > 2 else 1
    if cmd not in ("gen", "list"):
        print(__doc__)
        raise SystemExit(2)
    asyncio.run(run(cmd, count))


if __name__ == "__main__":
    main()
