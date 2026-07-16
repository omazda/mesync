"""Сервисный лог-канал Telegram («Info - MeSync») — отчёты об ошибках для разработчиков.

Мы не храним сообщения пользователей на сервере, поэтому отчёт об ошибке доставки
обязан сам нести весь контекст для разбора: кто отправил (имя со ссылкой на профиль),
какое правило сработало («источник → приёмник»), само сообщение и текст ошибки.

Принципы:
- best-effort: сбой отправки отчёта НИКОГДА не ломает основной поток (все исключения
  гасятся внутри); при ошибке HTML-разметки отчёт повторяется плоским текстом;
- троттлинг: не больше `max_per_minute` отчётов в минуту (шторм ошибок не должен
  упереть бота в лимиты Bot API и утопить канал); подавленные считаются, и следующий
  пропущенный отчёт получает пометку «+N отчётов подавлено»;
- канал строго Telegram: id чата в config.SERVICE_LOG_CHAT_ID (пусто → лог выключен,
  все методы становятся no-op).

Формат сверен с docs/telegram/markdown/04-api-reference.md: sendMessage (text ≤ 4096
символов после парсинга entities, parse_mode=HTML, link_preview_options), HTML style
(<b>/<a>/<code>/<blockquote expandable>; &, <, > экранируются), ссылка tg://user?id=…
работает внутри inline-ссылки.
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

log = logging.getLogger("control.service_log")

# Бюджеты видимого текста (лимит sendMessage — 4096 символов ПОСЛЕ парсинга entities;
# теги в лимит не входят, поэтому считаем видимые части с запасом).
QUOTE_LIMIT = 2800     # цитата пересылаемого сообщения
ERROR_LIMIT = 400      # текст исключения
TOTAL_LIMIT = 4000     # весь отчёт (страховочная обрезка)


def _esc(s: Any) -> str:
    """Экранирование текста для Telegram HTML (по docs: &, <, > → entities)."""
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _cut(s: str, limit: int) -> str:
    if len(s) <= limit:
        return s
    return s[:limit].rstrip() + f"… (обрезано, всего {len(s)} символов)"


class ServiceLog:
    """Отправитель отчётов в служебный TG-канал. Все методы безопасны: не бросают."""

    def __init__(self, tg_client: Any = None, chat_id: Any = None, *,
                 max_per_minute: int = 20, clock=time.monotonic) -> None:
        self.tg_client = tg_client
        self.chat_id = str(chat_id).strip() if chat_id is not None else ""
        self.max_per_minute = max(1, int(max_per_minute))
        self._clock = clock
        self._window_start: float = 0.0
        self._window_count: int = 0
        self._suppressed: int = 0
        self._tasks: set[asyncio.Task] = set()

    @property
    def enabled(self) -> bool:
        return self.tg_client is not None and bool(self.chat_id)

    def submit(self, title: str, lines: list[str], *, quote: str | None = None,
               error: object | None = None) -> None:
        """Fire-and-forget вариант report(): создаёт фоновую задачу и не ждёт отправку —
        для мест, где нельзя задерживать ответ (например, HTTP-обработчик ошибок API).
        Ссылка на задачу хранится до завершения (иначе event loop может её потерять)."""
        if not self.enabled:
            return
        try:
            task = asyncio.get_running_loop().create_task(
                self.report(title, lines, quote=quote, error=error))
        except RuntimeError:                       # нет запущенного event loop
            return
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    # ---- троттлинг ----
    def _admit(self) -> int | None:
        """Пустить ли отчёт сейчас. None — подавить; иначе число подавленных с прошлого
        допущенного отчёта (для пометки «+N подавлено»)."""
        now = self._clock()
        if now - self._window_start >= 60.0:
            self._window_start = now
            self._window_count = 0
        if self._window_count >= self.max_per_minute:
            self._suppressed += 1
            return None
        self._window_count += 1
        skipped, self._suppressed = self._suppressed, 0
        return skipped

    # ---- отчёты ----
    async def report(self, title: str, lines: list[str], *, quote: str | None = None,
                     error: object | None = None) -> None:
        """Отправить отчёт. `title` — plain-заголовок; `lines` — ГОТОВЫЕ HTML-строки
        (данные в них вызывающий уже экранировал); `quote` — сырой текст сообщения
        (экранируется здесь, сворачивается в раскрываемую цитату); `error` — исключение
        или строка (экранируется здесь)."""
        if not self.enabled:
            return
        try:
            skipped = self._admit()
            if skipped is None:
                return
            parts = [f"🛑 <b>{_esc(title)}</b>"]
            if skipped:
                parts.append(f"⚠️ +{skipped} отчётов подавлено (лимит {self.max_per_minute}/мин)")
            parts.extend(ln for ln in lines if ln)
            if error is not None:
                err_text = f"{type(error).__name__}: {error}" if isinstance(error, BaseException) \
                    else str(error)
                parts.append(f"Ошибка: <code>{_esc(_cut(err_text, ERROR_LIMIT))}</code>")
            if quote:
                parts.append("Сообщение:")
                parts.append(f"<blockquote expandable>{_esc(_cut(quote, QUOTE_LIMIT))}</blockquote>")
            elif quote is not None:
                parts.append("Сообщение: (без текста)")
            html = "\n".join(parts)
            if len(html) > TOTAL_LIMIT + 1500:      # страховка: теги ~не больше 1500 символов
                html = html[:TOTAL_LIMIT + 1500]
            await self._send(html)
        except Exception:  # noqa: BLE001 — сервисный лог не должен ломать основной поток
            log.warning("отчёт в сервисный канал не отправлен", exc_info=True)

    async def _send(self, html: str) -> None:
        """sendMessage с HTML; при ошибке разметки (Bad Request на кривом entity) —
        повтор плоским текстом без тегов, чтобы отчёт не потерялся."""
        try:
            await self.tg_client.send_message(self.chat_id, html, parse_mode="HTML",
                                              disable_web_page_preview=True)
        except Exception:  # noqa: BLE001
            import re
            plain = re.sub(r"<[^>]+>", "", html)
            plain = (plain.replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&"))
            await self.tg_client.send_message(self.chat_id, plain, parse_mode=None,
                                              disable_web_page_preview=True)
