#!/usr/bin/env python3
"""Запуск бота MAX: python3 run_max.py

Приём событий из чатов/каналов MAX (см. src/max_sync/).
Токен берётся из .env (MAX_BOT_TOKEN).
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent / "src"))

from max_sync.main import main  # noqa: E402

if __name__ == "__main__":
    main()
