"""Биллинг подписки Smart (299 ₽/мес) через ЮKassa.

Модель (сверено с `docs/yookassa/`):
  - Пробный период: НОВЫЙ пользователь получает TRIAL_DAYS дней бесплатно за
    привязку автоплатежа. Привязка — «на нулевую сумму» (POST /v3/payment_methods,
    редирект на готовую страницу ЮKassa); ЮKassa поддерживает её только для
    банковской карты и СБП (save-without-payment/basics.md).
  - Оплата: платёж 299 ₽ через виджет ЮKassa (confirmation.type=embedded →
    confirmation_token). С автоплатежом — save_payment_method=true (безусловное
    сохранение; виджет сам покажет только способы с поддержкой привязки: карта,
    ЮMoney, Mir Pay, SberPay, T-Pay, СБП — widget/additional-settings/
    recurring-payments.md). Без автоплатежа — save_payment_method=false, триал
    при этом не положен (отключение автоплатежа = полная стоимость без привязки).
  - Продление: ровно на 1 месяц, В МОМЕНТ истечения — фоновый tick() создаёт
    автоплатёж по payment_method_id (pay-with-saved.md). Неудача → подписка сразу
    неактивна, ретраи каждые RENEW_RETRY_SECONDS до RENEW_MAX_ATTEMPTS.
  - Отключение автоплатежа = удаление payment_method_id на нашей стороне
    (recurring-payments/basics.md: в ЮKassa привязку удалить нельзя, достаточно
    перестать использовать идентификатор). У пользователя в ПРОБНОМ периоде
    отключение немедленно аннулирует триал: подписка гаснет, дальше — оплата
    полной стоимости без привязки.

Запись подписки в store (см. store._default_subscription):
  status ('active'|'inactive'), plan, renew_at (ISO-дата для UI), created_at,
  paid_until (epoch, точный момент истечения), trial, trial_used, autopay,
  payment_method_id, payment_method_title,
  pending ({kind: 'bind_trial'|'bind'|'purchase'|'renewal'|'traffic_topup',
            id, autopay, created_at, expires_at, confirmation_token|confirmation_url,
            topup_bytes?, price_rub?}),
  renew_attempts, renew_retry_at, last_error.

Все проверки/применения статусов сериализуются per-account локом — параллельные
опрос фронта, вебхук и фоновый tick не применят один платёж дважды.
"""
from __future__ import annotations

import asyncio
import calendar
import datetime as dt
import logging
import time
from typing import Any, Awaitable, Callable

from . import config, tariffs
from .yookassa import YooKassaClient, YooKassaError

log = logging.getLogger("control.billing")

BIND_METHODS = ("bank_card", "sbp")  # нулевая привязка — только карта и СБП (docs)
PENDING_DEFAULT_TTL = 3600           # страница подтверждения/привязки живёт около часа
PENDING_REISSUE_WINDOW = 3 * 60      # новую платёжку выпускаем только в последние 3 минуты
SUBSCRIPTION_PENDING_KINDS = {"bind_trial", "bind", "purchase"}
PAYMENT_PENDING_KINDS = {"purchase", "traffic_topup"}


class BillingError(Exception):
    def __init__(self, status: int, code: str, message: str):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message


def add_month(ts: float) -> int:
    """+1 календарный месяц (31 янв → 28/29 фев). Продление всегда ровно на месяц."""
    d = dt.datetime.fromtimestamp(ts, dt.timezone.utc)
    year, month = (d.year + 1, 1) if d.month == 12 else (d.year, d.month + 1)
    day = min(d.day, calendar.monthrange(year, month)[1])
    return int(d.replace(year=year, month=month, day=day).timestamp())


def _date_str(ts: float) -> str:
    return dt.datetime.fromtimestamp(ts, dt.timezone.utc).date().isoformat()


def _date_ru(ts: float) -> str:
    months = ("января", "февраля", "марта", "апреля", "мая", "июня", "июля",
              "августа", "сентября", "октября", "ноября", "декабря")
    d = dt.datetime.fromtimestamp(ts, dt.timezone.utc)
    return f"{d.day} {months[d.month - 1]}"


def _parse_yk_ts(value: Any) -> int | None:
    """ISO timestamp ЮKassa (`...Z`) → epoch seconds."""
    if not value:
        return None
    try:
        return int(dt.datetime.fromisoformat(str(value).replace("Z", "+00:00")).timestamp())
    except Exception:  # noqa: BLE001
        return None


def _pending_expires_at(obj: dict[str, Any], now: float) -> int:
    return _parse_yk_ts(obj.get("expires_at")) or int(now + PENDING_DEFAULT_TTL)


def _pm_title(pm: dict[str, Any]) -> str:
    """Человеческое имя способа оплаты из объекта payment_method ЮKassa."""
    title = pm.get("title")
    if title:
        return str(title)
    t = pm.get("type")
    card = pm.get("card") or {}
    if t == "bank_card" and card.get("last4"):
        return f"Карта •{card['last4']}"
    names = {"bank_card": "Банковская карта", "sbp": "СБП", "yoo_money": "ЮMoney",
             "sberbank": "SberPay", "tinkoff_bank": "T-Pay", "mir_pay": "Mir Pay"}
    return names.get(str(t), str(t or "способ оплаты"))


class Billing:
    def __init__(self, store: Any, yk: YooKassaClient, *, price_rub: int, trial_days: int,
                 return_url: str, renew_retry_seconds: int = 4 * 3600,
                 renew_max_attempts: int = 6, renew_window_days: int = 5,
                 notify: Callable[..., Awaitable[None]] | None = None,
                 paused_provider: Callable[[], bool] | None = None,
                 clock: Callable[[], float] = time.time):
        self.store = store
        self.yk = yk
        self.price = price_rub
        self.trial_days = trial_days
        self.return_url = return_url
        self.renew_retry_seconds = renew_retry_seconds
        self.renew_max_attempts = renew_max_attempts
        # Окно ранней ручной оплаты: без автопродления «Продлить» доступно за
        # renew_window_days дней до истечения (месяц добавится к дате истечения).
        self.renew_window_days = renew_window_days
        # notify(acc_id, title, subtitle) — уведомление в mini-app и мессенджеры.
        self.notify = notify
        # paused_provider() -> bool — глобальная приостановка приёма платежей из админ-панели
        # (settings.payments_paused). None → никогда не на паузе.
        self._paused_provider = paused_provider
        self.clock = clock
        self._locks: dict[str, asyncio.Lock] = {}

    @property
    def enabled(self) -> bool:
        return self.yk.enabled

    @property
    def accepting_payments(self) -> bool:
        return self.enabled and not self._paused()

    def _paused(self) -> bool:
        if self._paused_provider is None:
            return False
        try:
            return bool(self._paused_provider())
        except Exception:  # noqa: BLE001 — сбой провайдера не должен ронять биллинг
            return False

    def _acc_price(self, acc_id: str) -> int:
        """Цена для аккаунта: персональный оверрайд из стора или глобальный дефолт (этап 4.3)."""
        try:
            return int(self.store.price_for(acc_id))
        except Exception:  # noqa: BLE001
            return int(self.price)

    def _plan_title(self, acc_id: str) -> str:
        try:
            return tariffs.payment_title(self.store.has_individual_tariff(acc_id))
        except Exception:  # noqa: BLE001
            return tariffs.payment_title(False)

    def _lock(self, acc_id: str) -> asyncio.Lock:
        return self._locks.setdefault(acc_id, asyncio.Lock())

    async def _notify(self, acc_id: str, title: str, subtitle: str | None = None) -> None:
        if self.notify is None:
            return
        try:
            await self.notify(acc_id, title, subtitle)
        except Exception:  # noqa: BLE001 — уведомление не должно ломать биллинг
            log.warning("billing notify сбой (%s)", acc_id, exc_info=True)

    def _require_enabled(self) -> None:
        if not self.enabled:
            raise BillingError(503, "pay_unavailable",
                               "Оплата временно недоступна. Попробуйте позже.")

    @staticmethod
    def _pending_ttl(p: dict[str, Any], now: float) -> float:
        expires_at = float(p.get("expires_at") or 0)
        if expires_at <= 0:
            expires_at = float(p.get("created_at") or now) + PENDING_DEFAULT_TTL
        return expires_at - now

    @staticmethod
    def _pending_response(p: dict[str, Any]) -> dict[str, Any] | None:
        expires_at = int(p.get("expires_at") or 0) or None
        if p.get("kind") in ("bind_trial", "bind"):
            url = p.get("confirmation_url")
            if not url:
                return None
            return {"kind": "binding", "paymentMethodId": p.get("id"),
                    "confirmationUrl": url, "expiresAt": expires_at, "reused": True}
        if p.get("kind") == "purchase":
            token = p.get("confirmation_token")
            if not token:
                return None
            return {"kind": "payment", "paymentId": p.get("id"),
                    "confirmationToken": token, "expiresAt": expires_at, "reused": True}
        if p.get("kind") == "traffic_topup":
            token = p.get("confirmation_token")
            if not token:
                return None
            return {"kind": "payment", "paymentId": p.get("id"),
                    "confirmationToken": token, "expiresAt": expires_at, "reused": True,
                    "purpose": "traffic_topup",
                    "topupBytes": int(p.get("topup_bytes") or config.TOPUP_BYTES),
                    "price": int(p.get("price_rub") or config.TOPUP_PRICE_RUB)}
        return None

    @staticmethod
    def _pending_matches_checkout(p: dict[str, Any], mode: str, *,
                                  method: str, autopay: bool) -> bool:
        kind = p.get("kind")
        if mode == "trial":
            return kind == "bind_trial" and str(p.get("method") or method) == method
        if mode == "bind":
            return kind == "bind" and str(p.get("method") or method) == method
        if mode == "pay":
            return kind == "purchase" and bool(p.get("autopay")) == bool(autopay)
        return False

    async def _refresh_pending_confirmation(self, p: dict[str, Any]) -> dict[str, Any]:
        """Для legacy pending без сохранённого token/url пробуем перечитать объект ЮKassa."""
        if p.get("confirmation_token") or p.get("confirmation_url"):
            return p
        try:
            if p.get("kind") in ("bind_trial", "bind"):
                fresh = await self.yk.get_payment_method(str(p.get("id")))
                confirmation = fresh.get("confirmation") or {}
                p = {**p, "confirmation_url": confirmation.get("confirmation_url"),
                     "expires_at": p.get("expires_at") or _pending_expires_at(fresh, self.clock())}
            elif p.get("kind") in PAYMENT_PENDING_KINDS:
                fresh = await self.yk.get_payment(str(p.get("id")))
                confirmation = fresh.get("confirmation") or {}
                p = {**p, "confirmation_token": confirmation.get("confirmation_token"),
                     "expires_at": p.get("expires_at") or _pending_expires_at(fresh, self.clock())}
        except Exception:  # noqa: BLE001 — основной check_pending отдельно обработает ошибки
            return p
        return p

    async def _reuse_or_replace_pending(self, acc_id: str, mode: str, *, method: str,
                                        autopay: bool, now: float) -> dict[str, Any] | None:
        """Живой pending того же сценария переиспользуем (не плодим объекты в ЮKassa);
        pending ДРУГОГО сценария бросаем и разрешаем выпустить новую платёжку —
        пользователь передумал (например, снял галочку автопродления), блокировать
        его сообщением «подождите» нельзя."""
        sub = self.store.subscription(acc_id)
        p = sub.get("pending")
        if not p or p.get("kind") == "renewal":
            return None
        state = await self._check_pending_locked(acc_id)
        if state != "pending":
            return None
        p = dict(self.store.subscription(acc_id).get("pending") or {})
        if not p or p.get("kind") == "renewal":
            return None
        if p.get("kind") not in SUBSCRIPTION_PENDING_KINDS:
            raise BillingError(409, "payment_pending",
                               "У вас уже есть незавершённая оплата. Завершите её или попробуйте позже.")
        ttl = self._pending_ttl(p, now)
        if ttl <= PENDING_REISSUE_WINDOW:
            await self.store.set_subscription(acc_id, {"pending": None})
            return None
        p = await self._refresh_pending_confirmation(p)
        response = self._pending_response(p) if self._pending_matches_checkout(
            p, mode, method=method, autopay=autopay) else None
        if response:
            await self.store.set_subscription(acc_id, {"pending": p, "last_error": None})
            return response
        # Сценарий сменился (сняли/включили автопродление, оплата вместо привязки,
        # другой способ привязки) либо у совпавшего pending потерян token/url.
        # Отменить pending-объект в ЮKassa нельзя (API отменяет только
        # waiting_for_capture — docs/yookassa payment-process «Отмена платежа»),
        # поэтому просто перестаём его отслеживать: неоплаченный объект ЮKassa
        # погасит сама (expired_on_confirmation), а поздний успех брошенного
        # объекта вебхук игнорирует (его id не совпадёт с текущим pending).
        log.info("checkout %s: сценарий сменился (%s/autopay=%s → %s/autopay=%s) — "
                 "старая платёжка %s брошена", acc_id, p.get("kind"), p.get("autopay"),
                 mode, autopay, p.get("id"))
        await self.store.set_subscription(acc_id, {"pending": None})
        return None

    @staticmethod
    def _user_error(e: YooKassaError, *, mode: str) -> BillingError:
        """Ошибка API ЮKassa → человеческое сообщение пользователю (не сырой 500)."""
        desc = (e.description or "").lower()
        if e.status == 403 and "recurring" in desc:
            # Автоплатежи для магазина ещё не включены менеджером ЮKassa.
            if mode in ("trial", "bind"):
                msg = ("Пробный период временно недоступен: автоплатежи ещё подключаются. "
                       "Пока можно оплатить подписку без автоплатежа.")
            else:
                msg = ("Автоплатежи ещё подключаются. Отключите автоплатёж — "
                       "и оплатите подписку без привязки.")
            return BillingError(409, "recurring_unavailable", msg)
        log.warning("ЮKassa отклонила запрос: %s", e)
        return BillingError(502, "yk_error",
                            "Платёжный сервис сейчас недоступен. Попробуйте ещё раз чуть позже.")

    # ---------------- checkout ----------------
    async def start_checkout(self, acc_id: str, mode: str, *, method: str = "bank_card",
                             autopay: bool = True) -> dict[str, Any]:
        """Начать оформление.

        mode='trial' — 7 дней бесплатно за привязку автоплатежа (нулевая привязка,
          только новый пользователь; method: bank_card|sbp) → confirmationUrl.
        mode='pay'   — платёж 299 ₽ виджетом; autopay=True → с привязкой (безусловное
          сохранение), autopay=False → без привязки → confirmationToken.
        mode='bind'  — привязка способа оплаты для УЖЕ активной подписки (включение
          автопродления без нового списания) → confirmationUrl.
        """
        self._require_enabled()
        if self._paused():
            raise BillingError(503, "payments_paused",
                               "Приём платежей приостановлен. Попробуйте немного позже.")
        async with self._lock(acc_id):
            sub = self.store.subscription(acc_id)
            now = self.clock()
            active = sub.get("status") == "active" and float(sub.get("paid_until") or 0) > now
            reused = await self._reuse_or_replace_pending(
                acc_id, mode, method=method, autopay=autopay, now=now)
            if reused:
                return reused
            sub = self.store.subscription(acc_id)
            active = sub.get("status") == "active" and float(sub.get("paid_until") or 0) > now
            if mode == "trial":
                if sub.get("trial_used"):
                    raise BillingError(409, "trial_used",
                                       "Пробный период уже был использован.")
                if active:
                    raise BillingError(409, "already_active", "Подписка уже активна.")
                if method not in BIND_METHODS:
                    raise BillingError(400, "bad_method",
                                       "Для привязки доступны банковская карта и СБП.")
                try:
                    pm = await self.yk.create_payment_method(
                        type_=method, return_url=self.return_url,
                        metadata={"account_id": acc_id, "kind": "bind_trial"})
                except YooKassaError as e:
                    raise self._user_error(e, mode=mode)
                await self.store.set_subscription(acc_id, {
                    "pending": {"kind": "bind_trial", "id": pm["id"], "autopay": True,
                                "method": method, "created_at": int(now),
                                "expires_at": _pending_expires_at(pm, now),
                                "confirmation_url": (pm.get("confirmation") or {}).get("confirmation_url")},
                    "last_error": None})
                return {"kind": "binding", "paymentMethodId": pm["id"],
                        "confirmationUrl": (pm.get("confirmation") or {}).get("confirmation_url"),
                        "expiresAt": _pending_expires_at(pm, now), "reused": False}
            if mode == "bind":
                if not active:
                    raise BillingError(409, "not_active",
                                       "Привязка доступна при активной подписке.")
                if method not in BIND_METHODS:
                    raise BillingError(400, "bad_method",
                                       "Для привязки доступны банковская карта и СБП.")
                try:
                    pm = await self.yk.create_payment_method(
                        type_=method, return_url=self.return_url,
                        metadata={"account_id": acc_id, "kind": "bind"})
                except YooKassaError as e:
                    raise self._user_error(e, mode=mode)
                await self.store.set_subscription(acc_id, {
                    "pending": {"kind": "bind", "id": pm["id"], "autopay": True,
                                "method": method, "created_at": int(now),
                                "expires_at": _pending_expires_at(pm, now),
                                "confirmation_url": (pm.get("confirmation") or {}).get("confirmation_url")},
                    "last_error": None})
                return {"kind": "binding", "paymentMethodId": pm["id"],
                        "confirmationUrl": (pm.get("confirmation") or {}).get("confirmation_url"),
                        "expiresAt": _pending_expires_at(pm, now), "reused": False}
            if mode == "pay":
                if active:
                    # Ранняя РУЧНАЯ оплата: доступна без автопродления в последние
                    # renew_window_days дней — месяц добавится к дате истечения
                    # (см. _apply_paid), оплаченные дни не сгорают.
                    if sub.get("autopay") and sub.get("payment_method_id"):
                        raise BillingError(409, "already_active",
                                           "Автопродление включено — списание произойдёт "
                                           "в момент истечения подписки.")
                    if float(sub.get("paid_until") or 0) - now > self.renew_window_days * 86400:
                        raise BillingError(409, "already_active",
                                           "Подписка уже активна. Продлить вручную можно "
                                           f"за {self.renew_window_days} дней до истечения.")
                try:
                    pay = await self.yk.create_payment(
                        amount_rub=self._acc_price(acc_id), embedded=True,
                        description=f"Подписка {config.BOT_NAME}: {self._plan_title(acc_id)} — 1 месяц",
                        save_payment_method=bool(autopay),
                        metadata={"account_id": acc_id, "kind": "purchase"})
                except YooKassaError as e:
                    raise self._user_error(e, mode=mode)
                await self.store.set_subscription(acc_id, {
                    "pending": {"kind": "purchase", "id": pay["id"], "autopay": bool(autopay),
                                "created_at": int(now),
                                "expires_at": _pending_expires_at(pay, now),
                                "confirmation_token": (pay.get("confirmation") or {}).get("confirmation_token")},
                    "last_error": None})
                return {"kind": "payment", "paymentId": pay["id"],
                        "confirmationToken": (pay.get("confirmation") or {}).get("confirmation_token"),
                        "expiresAt": _pending_expires_at(pay, now), "reused": False}
            raise BillingError(400, "bad_mode", "Неизвестный режим оформления.")

    async def start_traffic_topup(self, acc_id: str, *,
                                  n_bytes: int | None = None,
                                  price_rub: int | None = None) -> dict[str, Any]:
        """Начать оплату бессрочного пакета добавочного трафика через виджет ЮKassa."""
        self._require_enabled()
        if self._paused():
            raise BillingError(503, "payments_paused",
                               "Приём платежей приостановлен. Попробуйте немного позже.")
        topup_bytes = max(1, int(n_bytes if n_bytes is not None else config.TOPUP_BYTES))
        price = max(1, int(price_rub if price_rub is not None else config.TOPUP_PRICE_RUB))
        async with self._lock(acc_id):
            sub = self.store.subscription(acc_id)
            now = self.clock()
            active = sub.get("status") == "active" and float(sub.get("paid_until") or 0) > now
            if not active:
                raise BillingError(409, "subscription_required",
                                   "Пакет трафика можно купить при активной подписке.")
            reused = await self._reuse_or_replace_topup_pending(
                acc_id, topup_bytes=topup_bytes, price=price, now=now)
            if reused:
                return reused
            try:
                pay = await self.yk.create_payment(
                    amount_rub=price, embedded=True,
                    description=f"Пакет трафика {config.BOT_NAME}: {tariffs.fmt_bytes_ru(topup_bytes)}",
                    save_payment_method=False,
                    metadata={"account_id": acc_id, "kind": "traffic_topup",
                              "topup_bytes": str(topup_bytes), "price_rub": str(price)})
            except YooKassaError as e:
                raise self._user_error(e, mode="pay")
            pending = {
                "kind": "traffic_topup",
                "id": pay["id"],
                "autopay": False,
                "topup_bytes": topup_bytes,
                "price_rub": price,
                "created_at": int(now),
                "expires_at": _pending_expires_at(pay, now),
                "confirmation_token": (pay.get("confirmation") or {}).get("confirmation_token"),
            }
            await self.store.set_subscription(acc_id, {"pending": pending, "last_error": None})
            return {"kind": "payment", "paymentId": pay["id"],
                    "confirmationToken": pending.get("confirmation_token"),
                    "expiresAt": pending["expires_at"], "reused": False,
                    "purpose": "traffic_topup", "topupBytes": topup_bytes, "price": price}

    async def _reuse_or_replace_topup_pending(self, acc_id: str, *, topup_bytes: int,
                                              price: int, now: float) -> dict[str, Any] | None:
        p = self.store.subscription(acc_id).get("pending")
        if not p or p.get("kind") == "renewal":
            return None
        state = await self._check_pending_locked(acc_id)
        if state != "pending":
            return None
        p = dict(self.store.subscription(acc_id).get("pending") or {})
        if not p or p.get("kind") == "renewal":
            return None
        ttl = self._pending_ttl(p, now)
        if ttl <= PENDING_REISSUE_WINDOW:
            await self.store.set_subscription(acc_id, {"pending": None})
            return None
        if p.get("kind") != "traffic_topup":
            raise BillingError(409, "payment_pending",
                               "У вас уже есть незавершённая оплата. Завершите её или попробуйте позже.")
        if int(p.get("topup_bytes") or 0) != topup_bytes or int(p.get("price_rub") or 0) != price:
            raise BillingError(409, "payment_pending",
                               "Завершите текущую оплату пакета или попробуйте позже.")
        p = await self._refresh_pending_confirmation(p)
        response = self._pending_response(p)
        if response:
            await self.store.set_subscription(acc_id, {"pending": p, "last_error": None})
            return response
        await self.store.set_subscription(acc_id, {"pending": None})
        return None

    async def cancel_pending(self, acc_id: str) -> None:
        async with self._lock(acc_id):
            sub = self.store.subscription(acc_id)
            p = sub.get("pending")
            if not p:
                return
            state = await self._check_pending_locked(acc_id)
            p = self.store.subscription(acc_id).get("pending")
            if state != "pending" or not p:
                return
            # Закрытие окна на фронте не отменяет объект в ЮKassa. Если стереть local
            # pending сразу, следующий тап выпишет новую платёжку. Держим старую до
            # последних 3 минут жизни, а потом разрешаем выпуск новой.
            if self._pending_ttl(p, self.clock()) <= PENDING_REISSUE_WINDOW:
                await self.store.set_subscription(acc_id, {"pending": None})

    # ---------------- применение результатов ----------------
    async def check_pending(self, acc_id: str) -> str:
        """Проверить незавершённую оплату/привязку. → 'none'|'pending'|'succeeded'|'failed'."""
        self._require_enabled()
        async with self._lock(acc_id):
            return await self._check_pending_locked(acc_id)

    async def _check_pending_locked(self, acc_id: str) -> str:
        sub = self.store.subscription(acc_id)
        p = sub.get("pending")
        if not p:
            return "none"
        kind, obj_id = p.get("kind"), p.get("id")
        if kind in ("bind_trial", "bind"):
            try:
                pm = await self.yk.get_payment_method(obj_id)
            except YooKassaError as e:
                return await self._pending_fetch_failed(acc_id, e)
            if pm.get("status") == "active" and pm.get("saved"):
                await self._apply_binding(acc_id, pm, trial=(kind == "bind_trial"))
                return "succeeded"
            if pm.get("status") == "inactive":
                await self.store.set_subscription(acc_id, {
                    "pending": None,
                    "last_error": "Не удалось привязать способ оплаты. Попробуйте другой."})
                return "failed"
            return "pending"
        try:
            pay = await self.yk.get_payment(obj_id)
        except YooKassaError as e:
            return await self._pending_fetch_failed(acc_id, e)
        status = pay.get("status")
        if status == "succeeded":
            if kind == "traffic_topup":
                await self._apply_traffic_topup(acc_id, pay, p)
            else:
                await self._apply_paid(acc_id, pay, autopay=bool(p.get("autopay")),
                                       renewal=(kind == "renewal"))
            return "succeeded"
        if status == "canceled":
            if kind == "renewal":
                await self._on_renewal_failed(acc_id, pay)
            elif kind == "traffic_topup":
                await self.store.set_subscription(acc_id, {
                    "pending": None,
                    "last_error": "Оплата пакета трафика не прошла. Попробуйте ещё раз."})
            else:
                await self.store.set_subscription(acc_id, {
                    "pending": None,
                    "last_error": "Оплата не прошла. Попробуйте ещё раз."})
            return "failed"
        return "pending"

    async def _pending_fetch_failed(self, acc_id: str, e: YooKassaError) -> str:
        """Ошибка чтения незавершённого объекта: 404 — объект пропал (сбрасываем
        оформление), остальное считаем транзиентным и продолжаем ждать."""
        if e.status == 404:
            await self.store.set_subscription(acc_id, {
                "pending": None,
                "last_error": "Оплата не была завершена. Попробуйте ещё раз."})
            return "failed"
        log.warning("check_pending (%s): временная ошибка ЮKassa: %s", acc_id, e)
        return "pending"

    async def _apply_binding(self, acc_id: str, pm: dict[str, Any], *, trial: bool) -> None:
        now = self.clock()
        patch: dict[str, Any] = {
            "pending": None, "last_error": None,
            "payment_method_id": pm["id"], "payment_method_title": _pm_title(pm),
            "autopay": True, "renew_attempts": 0, "renew_retry_at": 0,
        }
        if trial:
            until = int(now + self.trial_days * 86400)
            patch.update({"status": "active", "trial": True, "trial_used": True,
                          "paid_until": until, "renew_at": _date_str(until)})
        await self.store.set_subscription(acc_id, patch)
        if trial:
            await self.store.reset_traffic(acc_id)
            await self._notify(
                acc_id, f"Пробный период до {_date_ru(now + self.trial_days * 86400)}",
                f"Способ оплаты привязан. Далее {self._acc_price(acc_id)} ₽/мес спишется автоматически; "
                "отключить автоплатёж можно в настройках подписки.")
        else:
            # Привязка при активной подписке: кнопка ранней оплаты на фронте скрывается
            # (canRenewEarly гаснет), а пользователю явно сообщаем момент списания.
            until = float(self.store.subscription(acc_id).get("paid_until") or 0)
            when = (f"{_date_ru(until)} — в момент истечения подписки"
                    if until > now else "в момент истечения подписки")
            await self._notify(acc_id, "Автопродление включено",
                               f"{_pm_title(pm)} · списание {self._acc_price(acc_id)} ₽ произойдёт {when}.")

    async def _apply_paid(self, acc_id: str, pay: dict[str, Any], *,
                          autopay: bool, renewal: bool) -> None:
        sub = self.store.subscription(acc_id)
        now = self.clock()
        # Сумма в чеке — ФАКТИЧЕСКИ списанная (зафиксирована в объекте платежа при его
        # создании), а не текущая цена аккаунта: между созданием и подтверждением админ мог
        # поменять персональную цену, и `_acc_price` вернул бы уже другое число.
        try:
            charged = int(round(float((pay.get("amount") or {}).get("value"))))
        except (TypeError, ValueError):
            charged = self._acc_price(acc_id)
        old_until = float(sub.get("paid_until") or 0)
        # Продление в момент истечения (автоплатёж) — бесшовно от старой даты; ранняя
        # РУЧНАЯ оплата при ещё активной подписке — тоже от даты истечения (оплаченные
        # дни не сгорают). Просроченные ретраи и первая покупка — месяц от «сейчас».
        extend = bool(old_until) and (old_until > now or (renewal and now - old_until < 3600))
        base = old_until if extend else now
        until = add_month(base)
        pm = pay.get("payment_method") or {}
        saved = bool(pm.get("saved"))
        patch: dict[str, Any] = {
            "pending": None, "last_error": None,
            "status": "active", "trial": False, "trial_used": True,
            "paid_until": until, "renew_at": _date_str(until),
            "renew_attempts": 0, "renew_retry_at": 0,
        }
        if saved:
            patch.update({"payment_method_id": pm.get("id"),
                          "payment_method_title": _pm_title(pm), "autopay": True})
        elif not renewal:
            # Покупка без привязки: автопродления не будет.
            patch.update({"autopay": False, "payment_method_id": None,
                          "payment_method_title": None})
        await self.store.set_subscription(acc_id, patch)
        await self.store.reset_traffic(acc_id)
        if renewal:
            await self._notify(acc_id, f"Подписка продлена до {_date_ru(until)}",
                               f"Списано {charged} ₽.")
        else:
            tail = ("Автопродление включено." if (saved or autopay and saved)
                    else "Автопродление отключено — в дату истечения подписку нужно оплатить вручную.")
            title = (f"Подписка продлена до {_date_ru(until)}" if old_until > now  # ранняя оплата
                     else f"Тариф {self._plan_title(acc_id)} активен до {_date_ru(until)}")
            await self._notify(acc_id, title, f"Оплачено {charged} ₽. {tail}")

    async def _apply_traffic_topup(self, acc_id: str, pay: dict[str, Any],
                                   pending: dict[str, Any]) -> None:
        topup_bytes = max(1, int(pending.get("topup_bytes") or config.TOPUP_BYTES))
        expected_price = max(1, int(pending.get("price_rub") or config.TOPUP_PRICE_RUB))
        try:
            charged = int(round(float((pay.get("amount") or {}).get("value"))))
        except (TypeError, ValueError):
            charged = expected_price
        if charged < expected_price:
            await self.store.set_subscription(acc_id, {
                "pending": None,
                "last_error": "Сумма платежа за пакет трафика не совпала. Обратитесь в поддержку."})
            log.error("traffic topup %s: сумма платежа %s меньше ожидаемой %s",
                      acc_id, charged, expected_price)
            return
        await self.store.add_topup(acc_id, topup_bytes)
        await self.store.set_subscription(acc_id, {"pending": None, "last_error": None})
        await self._notify(
            acc_id,
            "Добавочный трафик начислен",
            f"{tariffs.fmt_bytes_ru(topup_bytes)} без срока действия. Списано {charged} ₽.")

    # ---------------- автоплатёж вкл/выкл ----------------
    async def set_autopay(self, acc_id: str, enabled: bool) -> dict[str, Any]:
        async with self._lock(acc_id):
            sub = self.store.subscription(acc_id)
            now = self.clock()
            if enabled:
                if not sub.get("payment_method_id"):
                    raise BillingError(409, "need_bind",
                                       "Сначала привяжите способ оплаты.")
                await self.store.set_subscription(acc_id, {"autopay": True,
                                                           "renew_attempts": 0,
                                                           "renew_retry_at": 0})
                return {"annulled": False}
            # Отключение: перестаём использовать сохранённый способ оплаты
            # (равноценно отключению автоплатежа — docs/yookassa recurring basics).
            patch: dict[str, Any] = {"autopay": False, "payment_method_id": None,
                                     "payment_method_title": None}
            annulled = bool(sub.get("trial")) and sub.get("status") == "active"
            if annulled:
                # Пробный период держится на привязке: без неё он аннулируется сразу.
                patch.update({"status": "inactive", "trial": False,
                              "paid_until": int(now), "renew_at": _date_str(now)})
            await self.store.set_subscription(acc_id, patch)
            if annulled:
                await self._notify(acc_id, "Пробный период завершён",
                                   "Автоплатёж отключён — пробный период аннулирован. "
                                   f"Подписка — {self._acc_price(acc_id)} ₽/мес без привязки.")
            elif sub.get("status") == "active":
                until = float(sub.get("paid_until") or now)
                await self._notify(acc_id, "Автопродление отключено",
                                   f"Подписка активна до {_date_ru(until)}, продления не будет.")
            return {"annulled": annulled}

    # ---------------- вебхук ----------------
    async def webhook(self, event: str, obj: dict[str, Any]) -> None:
        """Уведомление ЮKassa. Телу не доверяем: перечитываем объект из API по id
        и применяем через общий путь check_pending (идемпотентно)."""
        if not self.enabled:
            return
        obj_id = str(obj.get("id") or "")
        if not obj_id:
            return
        try:
            if event.startswith("payment_method."):
                fresh = await self.yk.get_payment_method(obj_id)
            elif event.startswith("payment."):
                fresh = await self.yk.get_payment(obj_id)
            else:
                return
        except YooKassaError:
            log.warning("webhook: объект %s не найден в API", obj_id)
            return
        acc_id = str((fresh.get("metadata") or {}).get("account_id") or "")
        if not acc_id or self.store.account(acc_id) is None:
            return
        async with self._lock(acc_id):
            sub = self.store.subscription(acc_id)
            p = sub.get("pending")
            if p and p.get("id") == obj_id:
                await self._check_pending_locked(acc_id)

    # ---------------- фоновый цикл ----------------
    async def tick(self) -> None:
        """Один проход: дожать незавершённые оплаты (fallback вебхука) и продлить/
        погасить истёкшие подписки. Зовётся из run_app каждые ~30 секунд."""
        if not self.enabled:
            return
        if self._paused():
            return  # приём платежей приостановлен: не списываем и не гасим (grace до снятия паузы)
        now = self.clock()
        subs = self.store.table("subscriptions")
        for acc_id in list(subs.keys()):
            sub = self.store.subscription(acc_id)
            try:
                # Миграция записей до-биллинговой эпохи (демо-оплата): активная подписка
                # с renew_at, но без paid_until — иначе первый же tick счёл бы её истёкшей.
                if sub.get("status") == "active" and not sub.get("paid_until"):
                    ra = str(sub.get("renew_at") or "")
                    try:
                        y, m, d = (int(x) for x in ra.split("-"))
                        ts = int(dt.datetime(y, m, d, tzinfo=dt.timezone.utc).timestamp())
                    except Exception:  # noqa: BLE001 — нет/битая дата → месяц от сейчас
                        ts = add_month(now)
                    await self.store.set_subscription(acc_id, {"paid_until": ts})
                    continue
                p = sub.get("pending")
                if p and now - float(p.get("created_at") or 0) > 10:
                    async with self._lock(acc_id):
                        await self._check_pending_locked(acc_id)
                    sub = self.store.subscription(acc_id)
                if sub.get("status") == "active" and float(sub.get("paid_until") or 0) <= now \
                        and not sub.get("pending"):
                    async with self._lock(acc_id):
                        await self._renew_or_expire(acc_id)
                elif sub.get("status") == "inactive" and sub.get("autopay") \
                        and sub.get("payment_method_id") and not sub.get("pending") \
                        and 0 < float(sub.get("renew_retry_at") or 0) <= now \
                        and int(sub.get("renew_attempts") or 0) < self.renew_max_attempts:
                    async with self._lock(acc_id):
                        await self._try_renew(acc_id)
            except Exception:  # noqa: BLE001 — один аккаунт не должен ломать обход
                log.warning("billing tick: сбой для %s", acc_id, exc_info=True)

    async def _renew_or_expire(self, acc_id: str) -> None:
        sub = self.store.subscription(acc_id)
        if sub.get("status") != "active" or float(sub.get("paid_until") or 0) > self.clock():
            return
        if sub.get("autopay") and sub.get("payment_method_id"):
            await self._try_renew(acc_id)
            return
        await self.store.set_subscription(acc_id, {"status": "inactive", "trial": False})
        await self._notify(acc_id, "Подписка истекла",
                           f"Правила на паузе. Продлите за {self._acc_price(acc_id)} ₽ — всё продолжит работать.")

    async def _try_renew(self, acc_id: str) -> None:
        sub = self.store.subscription(acc_id)
        attempts = int(sub.get("renew_attempts") or 0)
        until = float(sub.get("paid_until") or 0)
        was_trial = bool(sub.get("trial"))
        # Идемпотентность: ключ фиксирован на (аккаунт, период, попытка) — рестарт
        # между тиками не создаст второй платёж за ту же попытку.
        idem = f"renew:{acc_id}:{int(until)}:{attempts}"
        try:
            pay = await self.yk.create_payment(
                amount_rub=self._acc_price(acc_id),
                description=(f"Подписка {config.BOT_NAME}: {self._plan_title(acc_id)} — 1 месяц (первый платёж после пробного периода)"
                             if was_trial else f"Продление подписки {config.BOT_NAME}: {self._plan_title(acc_id)} — 1 месяц"),
                payment_method_id=str(sub["payment_method_id"]),
                metadata={"account_id": acc_id, "kind": "renewal"},
                idempotence_key=idem)
        except YooKassaError as e:
            log.warning("автопродление %s: ошибка API %s", acc_id, e)
            await self._schedule_retry(acc_id, reason=e.code)
            return
        status = pay.get("status")
        if status == "succeeded":
            await self._apply_paid(acc_id, pay, autopay=True, renewal=True)
        elif status == "canceled":
            await self._on_renewal_failed(acc_id, pay)
        else:  # pending (например, «сначала чек, потом платёж») — дожмёт следующий tick
            await self.store.set_subscription(acc_id, {
                "pending": {"kind": "renewal", "id": pay["id"], "autopay": True,
                            "created_at": int(self.clock())}})

    async def _on_renewal_failed(self, acc_id: str, pay: dict[str, Any]) -> None:
        reason = str(((pay.get("cancellation_details") or {}).get("reason")) or "")
        if reason == "permission_revoked":
            # Пользователь отозвал разрешение на списания через банк — привязку
            # удаляем на своей стороне (рекомендация docs/yookassa pay-with-saved).
            await self.store.set_subscription(acc_id, {
                "pending": None, "status": "inactive", "trial": False,
                "autopay": False, "payment_method_id": None, "payment_method_title": None,
                "last_error": "Автосписания отозваны через банк."})
            await self._notify(acc_id, "Автоплатёж отключён банком",
                               "Разрешение на списания отозвано. Оплатите подписку вручную.")
            return
        await self._schedule_retry(acc_id, reason=reason or "canceled")

    async def _schedule_retry(self, acc_id: str, *, reason: str) -> None:
        sub = self.store.subscription(acc_id)
        attempts = int(sub.get("renew_attempts") or 0) + 1
        exhausted = attempts >= self.renew_max_attempts
        await self.store.set_subscription(acc_id, {
            "pending": None, "status": "inactive", "trial": False,
            "renew_attempts": attempts,
            "renew_retry_at": 0 if exhausted else int(self.clock() + self.renew_retry_seconds),
            "last_error": f"Автопродление не прошло ({reason}).",
        })
        if attempts == 1:
            await self._notify(acc_id, "Не удалось продлить подписку",
                               "Списание не прошло — попробуем ещё раз автоматически. "
                               "Правила пока на паузе; можно оплатить вручную.")
        elif exhausted:
            await self._notify(acc_id, "Автопродление остановлено",
                               f"Списание не прошло {attempts} раз. Оплатите подписку вручную.")
