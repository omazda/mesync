#!/usr/bin/env python3
"""Запуск Этапа 1: python3 run_stage1.py

Получение апдейтов из всех чатов бота (см. src/telegram_sync/).
Токен берётся из .env (TELEGRAM_BOT_TOKEN).
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent / "src"))

from telegram_sync.main import main  # noqa: E402

if __name__ == "__main__":
    main()
