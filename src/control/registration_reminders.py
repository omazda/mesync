"""Follow-up напоминания лидам, которые открыли бота, но не завершили регистрацию."""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Awaitable, Callable

log = logging.getLogger("registration_reminders")


class RegistrationReminderWorker:
    def __init__(self, store: Any, *,
                 messenger: str,
                 delays: tuple[float, ...] | list[float],
                 send: Callable[[dict[str, Any], int], Awaitable[Any]],
                 interval: float = 1800.0,
                 batch_limit: int = 50,
                 clock: Callable[[], float] = time.time) -> None:
        self.store = store
        self.messenger = str(messenger)
        self.delays = tuple(float(d) for d in delays if float(d) >= 0)
        self._send = send
        self.interval = max(5.0, float(interval))
        self.batch_limit = max(1, int(batch_limit))
        self.clock = clock
        self.sent_total = 0
        self.error_total = 0
        self.last_ts: float | None = None

    def seconds_until_next_slot(self, *, include_current: bool = True) -> float:
        """Сколько спать до следующего запуска на сетке от 00:00.

        При периоде 1800 слоты: 00:00, 00:30, 01:00... Если процесс стартует ровно
        на слоте, первый проход можно выполнить сразу; после прохода следующий сон
        всегда ведёт к следующему слоту, а не к tight loop на той же секунде.
        """
        period = max(1.0, self.interval)
        now = max(0.0, float(self.clock()))
        elapsed = now % period
        epsilon = 0.001
        if elapsed <= epsilon or period - elapsed <= epsilon:
            return 0.0 if include_current else period
        return period - elapsed

    async def tick(self) -> int:
        due = await self.store.due_registration_reminders(
            self.messenger, self.delays, now=int(self.clock()), limit=self.batch_limit)
        sent = 0
        for lead in due:
            user_id = lead.get("user_id")
            idx = int(lead.get("reminder_index", 0))
            if user_id is None:
                continue
            try:
                res = await self._send(lead, idx)
                if res is None:
                    self.error_total += 1
                    continue
                await self.store.mark_registration_reminder_sent(
                    self.messenger, user_id, idx, now=int(self.clock()))
                self.sent_total += 1
                self.last_ts = self.clock()
                sent += 1
            except asyncio.CancelledError:
                raise
            except Exception:  # noqa: BLE001
                self.error_total += 1
                log.warning("напоминание регистрации не отправлено: messenger=%s user_id=%s",
                            self.messenger, user_id, exc_info=True)
        return sent

    async def run(self) -> None:
        log.info("напоминания регистрации: воркер запущен (%s, delays=%s, period=%ds)",
                 self.messenger, ",".join(str(int(d)) for d in self.delays),
                 int(self.interval))
        first = True
        while True:
            wait = self.seconds_until_next_slot(include_current=first)
            first = False
            if wait > 0:
                await asyncio.sleep(wait)
            await self.tick()
