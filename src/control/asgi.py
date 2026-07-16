"""ASGI-точка входа control-API для uvicorn/gunicorn.

Запуск (standalone, без ботов):
    PYTHONPATH=src .venv/bin/uvicorn control.asgi:app --host 0.0.0.0 --port 8090

Полный режим (боты + API в одном процессе) — см. run_app.py.
"""
from __future__ import annotations

from .api import create_app

app = create_app()
