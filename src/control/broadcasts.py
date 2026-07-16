"""Рассылки в ЛИЧНЫЕ чаты пользователей с ботом (этап 4.6).

Однопоточный резюмируемый воркер (по образцу control.reports.Reports): очередь держит
только id рассылок, тело и прогресс — в сторе. На каждом получателе шлём через ИНЖЕКТИРОВАННЫЙ
notifier_fn(messenger, user_id, text) — тот же примитив, что биллинг/модерация используют для
личных уведомлений. Получатели берутся из снимка identities (пользователь), поэтому доставка
идёт ТОЛЬКО в личный чат: в источники/каналы/группы рассылка попасть НЕ может конструктивно —
здесь нет ни одного пути через chat_id источника, rules или account_sources.

Троттлинг: клиенты реагируют на 429 только постфактум (retry_after), поэтому воркер сам
выдерживает темп `broadcast_rate_limit` сообщений/с (settings-store, потолок = лимит MAX ~30rps).
Курсор чекпойнтится не на каждой отправке (иначе полный дамп control.json на каждое сообщение),
а раз в CHECKPOINT — так рестарт переотправит максимум последнюю недописанную пачку.
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Awaitable, Callable

log = logging.getLogger("broadcasts")

_CHECKPOINT = 100   # как часто персистить курсор/счётчики (компромисс дубли↔амплификация записи)


class Broadcaster:
    def __init__(self, store: Any, *,
                 send: Callable[..., Awaitable[Any]],
                 settings: Any = None,
                 clock: Callable[[], float] = time.time,
                 checkpoint: int = _CHECKPOINT) -> None:
        self.store = store
        self._send = send                 # notifier_fn(messenger, user_id, text) — только личка
        self._settings = settings
        self.clock = clock
        self._checkpoint = max(1, int(checkpoint))
        self._queue: "asyncio.Queue[str]" = asyncio.Queue()
        self._enqueued: set[str] = set()
        # ops-состояние (in-memory, «с момента запуска»).
        self._current: str | None = None
        self._inflight = False
        self._sent_total = 0
        self._error_total = 0
        self._last_ts: float | None = None

    def _enqueue(self, bid: str) -> None:
        if bid in self._enqueued:
            return
        self._enqueued.add(bid)
        self._queue.put_nowait(bid)

    def enqueue(self, bid: str) -> None:
        """Поставить новую рассылку в очередь (из API-обработчика после add_broadcast)."""
        self._enqueue(bid)

    def load_pending(self) -> int:
        """Восстановить незавершённые рассылки в очередь при старте (резюме по курсору)."""
        ids = self.store.active_broadcast_ids()
        for bid in ids:
            self._enqueue(bid)
        if ids:
            log.info("рассылки: восстановлено из стора в очередь: %d", len(ids))
        return len(ids)

    def _rate(self) -> int:
        try:
            return int(self._settings.get("broadcast_rate_limit")) if self._settings else 20
        except Exception:  # noqa: BLE001
            return 20

    async def run(self) -> None:
        log.info("рассылки: воркер запущен")
        while True:
            bid = await self._queue.get()
            self._enqueued.discard(bid)
            self._current = bid
            self._inflight = True
            try:
                await self._process(bid)
            except asyncio.CancelledError:
                raise
            except Exception:  # noqa: BLE001 — одна рассылка не должна ронять воркер
                self._error_total += 1
                log.warning("рассылка %s: сбой", bid, exc_info=True)
                try:
                    await self.store.update_broadcast(bid, {"status": "failed", "recipients": []})
                except Exception:  # noqa: BLE001
                    pass
            finally:
                self._inflight = False
                self._current = None
                self._queue.task_done()

    def stats(self) -> dict[str, Any]:
        return {
            "running": True,
            "current": self._current,
            "inflight": self._inflight,
            "sentTotal": self._sent_total,       # с момента запуска
            "errorTotal": self._error_total,
            "lastTs": self._last_ts,
            "persistedActive": len(self.store.active_broadcast_ids()),
        }

    async def _process(self, bid: str) -> None:
        rec = self.store.get_broadcast(bid)
        if rec is None or rec.get("status") in ("done", "canceled", "failed"):
            return  # идемпотентность (рестарт / повторная постановка)
        if rec.get("status") == "pending":
            await self.store.update_broadcast(bid, {"status": "running", "started_at": int(self.clock())})
        recips = rec.get("recipients") or []
        text = rec.get("text") or ""
        i = int(rec.get("cursor", 0))
        sent = int(rec.get("sent", 0))
        failed = int(rec.get("failed", 0))
        last_error = rec.get("last_error")

        while i < len(recips):
            _acc_id, m, uid = recips[i]
            try:
                res = await self._send(m, uid, text)   # ИНВАРИАНТ: (m,uid) — личный чат пользователя
                if res is None:
                    # notifier вернул None = клиент этого мессенджера не сконфигурирован →
                    # доставки НЕ было, считаем неудачей (иначе «100% доставлено» при 0 отправок).
                    failed += 1
                    self._error_total += 1
                    last_error = "client_absent"
                else:
                    sent += 1
                    self._sent_total += 1
                    self._last_ts = self.clock()
            except asyncio.CancelledError:
                await self.store.update_broadcast(bid, {"cursor": i, "sent": sent, "failed": failed})
                raise
            except Exception as e:  # noqa: BLE001 — доставка одному не должна валить рассылку
                failed += 1
                self._error_total += 1
                last_error = repr(e)[:200]
            i += 1
            if i % self._checkpoint == 0 or i == len(recips):
                await self.store.update_broadcast(bid, {
                    "cursor": i, "sent": sent, "failed": failed, "last_error": last_error})
                cur = self.store.get_broadcast(bid)
                if cur is not None and cur.get("status") == "canceled":
                    return  # отмена учитывается на границе чекпойнта (уже отправленное не вернуть)
            # темп читаем каждую итерацию — смена broadcast_rate_limit действует на лету
            await asyncio.sleep(1.0 / max(1, self._rate()))

        # На финале снимаем тяжёлый снимок recipients: он больше не нужен (резюме невозможно),
        # иначе бы навсегда лежал в control.json и пересериализовывался на каждую запись стора.
        await self.store.update_broadcast(bid, {
            "status": "done", "finished_at": int(self.clock()), "recipients": [],
            "cursor": i, "sent": sent, "failed": failed, "last_error": last_error})
        try:
            await self.store.add_event(kind="broadcast",
                                       title=f"Рассылка завершена: {sent}/{rec.get('total', len(recips))}",
                                       detail={"id": bid, "sent": sent, "failed": failed})
        except Exception:  # noqa: BLE001
            pass
