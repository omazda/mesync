"""Коды активации подписки (формат XXXX-XXXX-XXXX, X ∈ [A-Za-z0-9], регистрозависимо).

Код действует 30 суток с момента генерации и одноразово активирует подписку Smart
ровно на 1 календарный месяц БЕЗ
привязки способа оплаты (промо, партнёры, подарки, компенсации):
  - подписка активна → месяц добавляется К текущей дате истечения;
  - неактивна/истекла → месяц от «сейчас», статус active.
Привязку/автопродление активация не трогает (autopay остаётся как был);
trial снимается — подписка держится на коде, а не на привязке (отключение
автоплатежа не аннулирует оплаченный кодом месяц). Трафик обновляется, как
при любой оплате месяца.

Антиперебор: максимум ATTEMPTS_MAX попыток ввода (любых, включая неверные)
за ATTEMPTS_WINDOW секунд на аккаунт; при 62¹² ≈ 3·10²¹ комбинаций подбор
кода бессмыслен. Счётчик in-memory — рестарт процесса окно сбрасывает,
но перебор через рестарты невозможен по построению.

Генерация — только администратором: эндпоинты /api/admin/activation-codes
(заголовок X-Admin-Key = MESYNC_ADMIN_KEY из .env) либо tools/gen_activation_codes.py.
"""
from __future__ import annotations

import asyncio
import logging
import re
import secrets
import string
import time
from typing import Any, Awaitable, Callable

from . import tariffs
from .billing import _date_ru, _date_str, add_month
from .store import ACTIVATION_CODE_TTL

log = logging.getLogger("control.activation")


def _plan_title(store: Any, acc_id: str) -> str:
    try:
        return tariffs.payment_title(store.has_individual_tariff(acc_id))
    except Exception:  # noqa: BLE001
        return tariffs.payment_title(False)

CODE_ALPHABET = string.ascii_uppercase + string.ascii_lowercase + string.digits  # 62 символа
CODE_GROUPS = 3
CODE_GROUP_LEN = 4
ATTEMPTS_MAX = 3          # не больше 3 вводов кода…
ATTEMPTS_WINDOW = 600     # …за 10 минут (на аккаунт)
GENERATE_MAX = 1000       # потолок одной генерации (админ)
CODE_TTL_DAYS = ACTIVATION_CODE_TTL // 86400

_CODE_CHARS = re.compile(rf"^[A-Za-z0-9]{{{CODE_GROUPS * CODE_GROUP_LEN}}}$")


class ActivationError(Exception):
    def __init__(self, status: int, code: str, message: str):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message


def generate_code() -> str:
    """Криптослучайный код XXXX-XXXX-XXXX."""
    return "-".join(
        "".join(secrets.choice(CODE_ALPHABET) for _ in range(CODE_GROUP_LEN))
        for _ in range(CODE_GROUPS))


def normalize_code(raw: Any) -> str | None:
    """Пользовательский ввод → канонический вид XXXX-XXXX-XXXX (регистр СОХРАНЯЕТСЯ —
    код регистрозависимый). Терпимы к пробелам и расстановке дефисов; не код → None."""
    s = "".join(ch for ch in str(raw or "") if not ch.isspace() and ch != "-")
    if not _CODE_CHARS.match(s):
        return None
    return "-".join(s[i:i + CODE_GROUP_LEN]
                    for i in range(0, CODE_GROUPS * CODE_GROUP_LEN, CODE_GROUP_LEN))


class Activation:
    """Активация кодов + генерация. Хранение — таблица activation_codes в ControlStore
    (атомарное «проверить и потратить» под локом стора)."""

    def __init__(self, store: Any, *,
                 notify: Callable[..., Awaitable[None]] | None = None,
                 clock: Callable[[], float] = time.time):
        self.store = store
        self.notify = notify          # notify(acc_id, title, subtitle) — как у Billing
        self.clock = clock
        self._attempts: dict[str, list[float]] = {}   # acc_id -> метки попыток ввода
        self._locks: dict[str, asyncio.Lock] = {}     # сериализация активаций аккаунта

    def _lock(self, acc_id: str) -> asyncio.Lock:
        return self._locks.setdefault(acc_id, asyncio.Lock())

    def _register_attempt(self, acc_id: str) -> None:
        """Учесть попытку ввода; сверх лимита — 429 с оценкой ожидания."""
        now = self.clock()
        recent = [t for t in self._attempts.get(acc_id, ()) if now - t < ATTEMPTS_WINDOW]
        if len(recent) >= ATTEMPTS_MAX:
            wait_min = max(1, int((ATTEMPTS_WINDOW - (now - recent[0])) // 60) + 1)
            self._attempts[acc_id] = recent
            raise ActivationError(429, "too_many_attempts",
                                  f"Слишком много попыток. Попробуйте через {wait_min} мин.")
        recent.append(now)
        self._attempts[acc_id] = recent

    async def activate(self, acc_id: str, raw_code: Any) -> dict[str, Any]:
        """Применить код к аккаунту. Успех → {'until': epoch}. Ошибки — ActivationError."""
        async with self._lock(acc_id):
            self._register_attempt(acc_id)
            code = normalize_code(raw_code)
            if code is None:
                raise ActivationError(400, "bad_code_format",
                                      "Неверный формат кода. Ожидается XXXX-XXXX-XXXX.")
            claim = await self.store.claim_activation_code(
                code, acc_id, now=int(self.clock()))
            if claim == "expired":
                raise ActivationError(410, "code_expired",
                                      "Срок действия кода истёк. Используйте новый код.")
            if claim != "used":
                raise ActivationError(404, "code_not_found",
                                      "Код не найден или уже использован.")
            sub = self.store.subscription(acc_id)
            now = self.clock()
            active = sub.get("status") == "active" and float(sub.get("paid_until") or 0) > now
            base = float(sub.get("paid_until")) if active else now
            until = add_month(base)
            await self.store.set_subscription(acc_id, {
                "status": "active", "trial": False,
                "paid_until": until, "renew_at": _date_str(until),
                "last_error": None,
            })
            await self.store.reset_traffic(acc_id)
            log.info("activation: код %s… активирован аккаунтом %s (до %s)",
                     code[:4], acc_id, _date_str(until))
            if self.notify is not None:
                try:
                    await self.notify(acc_id, f"Код активирован — подписка до {_date_ru(until)}",
                                      f"Месяц тарифа {_plan_title(self.store, acc_id)} без привязки способа оплаты.")
                except Exception:  # noqa: BLE001 — уведомление не должно ломать активацию
                    log.warning("activation notify сбой (%s)", acc_id, exc_info=True)
            return {"until": int(until)}

    async def grant_month(self, acc_id: str) -> dict[str, Any]:
        """Прямая выдача месяца текущего тарифа администратором (без кода): активной подписке — месяц К
        дате истечения, неактивной — от «сейчас». Привязку не трогает, трафик обновляет."""
        async with self._lock(acc_id):
            sub = self.store.subscription(acc_id)
            now = self.clock()
            active = sub.get("status") == "active" and float(sub.get("paid_until") or 0) > now
            base = float(sub.get("paid_until")) if active else now
            until = add_month(base)
            await self.store.set_subscription(acc_id, {
                "status": "active", "trial": False,
                "paid_until": until, "renew_at": _date_str(until), "last_error": None,
            })
            await self.store.reset_traffic(acc_id)
            log.info("activation: месяц выдан админом аккаунту %s (до %s)", acc_id, _date_str(until))
            if self.notify is not None:
                try:
                    await self.notify(acc_id, f"Подписка продлена до {_date_ru(until)}",
                                      f"Месяц тарифа {_plan_title(self.store, acc_id)} от администратора.")
                except Exception:  # noqa: BLE001
                    log.warning("grant_month notify сбой (%s)", acc_id, exc_info=True)
            return {"until": int(until)}

    async def generate(self, count: int) -> list[str]:
        """Сгенерировать и сохранить count новых кодов (админ)."""
        count = max(1, min(int(count), GENERATE_MAX))
        existing = self.store.table("activation_codes")
        codes: list[str] = []
        while len(codes) < count:
            code = generate_code()
            if code not in existing and code not in codes:   # коллизия ~невозможна, но дёшево
                codes.append(code)
        await self.store.add_activation_codes(codes, created_at=int(self.clock()))
        log.info("activation: сгенерировано кодов: %d", len(codes))
        return codes
