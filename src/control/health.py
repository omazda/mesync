"""Живость ботов (этап 4.5, ops-наблюдаемость).

Только IN-MEMORY: поллеры на каждом цикле long-poll отмечают last_poll_ts через лёгкий
прокси `_Chan` (без знания о реестре и без I/O). Писать это в ControlStore нельзя — каждая
мутация стора вызывает полный дамп control.json (`_save`), а поллеры крутятся каждые
несколько секунд → усиление записи. Сброс при рестарте — это КОРРЕКТНО: новый процесс =
новое состояние живости (событие о падении переживает рестарт отдельно — через events-кольцо).

Состояние выводится по свежести last_poll_ts (порог = poll_timeout + запас), а не по «процесс
жив»: MAX никогда не роняет процесс на ошибке API (sleep-5-continue) → замирание ловится по
свежести; Telegram при не-409 роняет задачу → процесс перезапускается systemd.
"""
from __future__ import annotations

import time
from dataclasses import dataclass

# Сетевой запас поверх таймаута long-poll: пустой ответ приходит примерно раз в poll_timeout,
# поэтому «протухшим» считаем, если успешного опроса не было дольше poll_timeout + запас.
_SLACK = 20
_DEGRADED_ERRORS = 1   # хотя бы одна ошибка подряд при ещё свежем последнем успехе → degraded


@dataclass
class BotStat:
    messenger: str
    bot_id: object = None
    username: str | None = None
    started_at: float | None = None      # wall-время старта поллера
    poll_timeout: int = 30
    last_poll_ts: float | None = None     # каждый успешный возврат get_updates (в т.ч. пустой)
    last_update_ts: float | None = None   # когда реально пришёл апдейт
    consecutive_errors: int = 0
    last_error_ts: float | None = None
    last_error: str | None = None


class _Chan:
    """Непрозрачный прокси, который держит поллер: только пишет метки, ничего не знает о реестре."""

    def __init__(self, stat: BotStat) -> None:
        self._s = stat

    def poll(self) -> None:
        self._s.last_poll_ts = time.time()
        self._s.consecutive_errors = 0

    def update(self) -> None:
        self._s.last_update_ts = time.time()

    def error(self, exc: BaseException) -> None:
        s = self._s
        s.consecutive_errors += 1
        s.last_error_ts = time.time()
        s.last_error = f"{type(exc).__name__}: {exc}"[:200]


class BotHealth:
    """Реестр живости обоих ботов. Инжектится в admin-API через set_health()."""

    def __init__(self) -> None:
        self._bots: dict[str, BotStat] = {}

    def mark_started(self, messenger: str, *, bot_id=None, username=None,
                     poll_timeout: int = 30) -> None:
        self._bots[messenger] = BotStat(messenger, bot_id, username, time.time(),
                                        int(poll_timeout))

    def channel(self, messenger: str) -> _Chan:
        stat = self._bots.get(messenger)
        if stat is None:
            stat = self._bots[messenger] = BotStat(messenger)
        return _Chan(stat)

    def _state(self, s: BotStat, now: float) -> str:
        stale_after = s.poll_timeout + _SLACK
        if s.started_at is None:
            return "offline"                       # токен не задан / поллер не стартовал
        if s.last_poll_ts is None:                 # успешного опроса ещё не было
            if (now - s.started_at) > stale_after:
                return "stalled"                    # давно стартовал, а опрос так и не прошёл
            # Ещё в grace-окне, но уже сыпятся ошибки (напр. активен Webhook) → не «online».
            return "degraded" if s.consecutive_errors >= _DEGRADED_ERRORS else "online"
        if (now - s.last_poll_ts) > stale_after:
            return "stalled"                        # давно не было успешного опроса
        if s.consecutive_errors >= _DEGRADED_ERRORS:
            return "degraded"                       # свежий успех, но последние попытки с ошибками
        return "online"

    def snapshot(self) -> dict[str, dict]:
        now = time.time()
        out: dict[str, dict] = {}
        for m, s in self._bots.items():
            out[m] = {
                "state": self._state(s, now),
                "username": s.username,
                "botId": s.bot_id,
                "startedAt": s.started_at,
                "lastPollTs": s.last_poll_ts,
                "lastUpdateTs": s.last_update_ts,
                "consecutiveErrors": s.consecutive_errors,
                "lastError": s.last_error,
                "lastErrorTs": s.last_error_ts,
                "staleAfter": s.poll_timeout + _SLACK,
            }
        return out
