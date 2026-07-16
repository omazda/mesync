"""Автоматическая выдача кодов цифровых DBS-заказов Яндекс Маркета.

Официальный сценарий:
1. API-уведомление сообщает, что заказ перешёл в PROCESSING.
2. POST v1/businesses/{businessId}/orders возвращает актуальный заказ, позиции и
   delivery.digitalGoods.type.
3. Для ACTIVATION_CODE/EMAIL все ключи заказа одним запросом передаются в
   POST v2/campaigns/{campaignId}/orders/{orderId}/deliverDigitalGoods.

Webhook только персистит событие. Отдельный воркер выполняет сетевые запросы, поэтому
PING укладывается в лимит 1 с, обычное уведомление — в 10 с, а очередь переживает рестарт.
Повторная доставка использует уже закреплённые за заказом коды.
"""
from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Any, Callable

import httpx

from . import config
from .activation import generate_code
from .store import ACTIVATION_CODE_TTL

log = logging.getLogger("control.yandex_market")

_DELIVERY_TYPES = {"ACTIVATION_CODE", "EMAIL"}
_FINAL_MARKET_STATUSES = {"CANCELLED", "DELIVERED"}


class YandexMarketError(Exception):
    """Ошибка Partner API или валидации заказа."""

    def __init__(self, status: int, code: str, message: str, *, transient: bool = False):
        super().__init__(f"{status} {code}: {message}")
        self.status = int(status)
        self.code = str(code)
        self.message = str(message)
        self.transient = bool(transient)


class YandexMarketClient:
    """Асинхронный клиент только для двух методов цифровой доставки."""

    def __init__(self, api_key: str, *, business_id: int, campaign_id: int,
                 base_url: str = "https://api.partner.market.yandex.ru",
                 timeout: float = 15.0):
        self.api_key = str(api_key or "").strip()
        self.business_id = int(business_id or 0)
        self.campaign_id = int(campaign_id or 0)
        self.enabled = bool(self.api_key and self.business_id > 0 and self.campaign_id > 0)
        self._base = base_url.rstrip("/")
        self._timeout = float(timeout)
        self._client: httpx.AsyncClient | None = None

    def _http(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self._base,
                headers={"Api-Key": self.api_key, "Accept": "application/json"},
                timeout=self._timeout,
            )
        return self._client

    async def aclose(self) -> None:
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()

    async def _post(self, path: str, body: dict[str, Any]) -> dict[str, Any]:
        try:
            # Передаём Api-Key и на уровне запроса: это сохраняет авторизацию даже при
            # подменённом/тестовом AsyncClient и явно фиксирует обязательный контракт метода.
            response = await self._http().post(path, json=body, headers={"Api-Key": self.api_key})
        except (httpx.TimeoutException, httpx.NetworkError) as exc:
            raise YandexMarketError(0, "network", str(exc), transient=True) from exc
        try:
            data = response.json()
        except Exception:  # noqa: BLE001 — прокси/5xx может вернуть HTML
            data = {}
        if response.status_code >= 400:
            errors = data.get("errors") if isinstance(data, dict) else None
            first = errors[0] if isinstance(errors, list) and errors else {}
            code = str((first or {}).get("code") or "http_error")
            message = str((first or {}).get("message") or response.text[:300])
            # 401/403 могут исчезнуть после исправления прав токена, а 404 иногда
            # возникает на коротком лаге между уведомлением и консистентностью списка.
            transient = response.status_code in {401, 403, 404, 408, 409, 420, 429} \
                or response.status_code >= 500
            raise YandexMarketError(response.status_code, code, message, transient=transient)
        if isinstance(data, dict) and data.get("status") == "ERROR":
            raise YandexMarketError(200, "api_error", repr(data.get("errors") or data),
                                    transient=True)
        return data if isinstance(data, dict) else {}

    async def get_order(self, order_id: int) -> dict[str, Any]:
        data = await self._post(
            f"/v1/businesses/{self.business_id}/orders",
            {"orderIds": [int(order_id)], "campaignIds": [self.campaign_id]},
        )
        # Partner API обычно возвращает orders на верхнем уровне; result поддержан для
        # совместимости с обёртками стандартного ApiResponse.
        result = data.get("result") if isinstance(data.get("result"), dict) else data
        orders = result.get("orders") if isinstance(result, dict) else None
        if not isinstance(orders, list) or not orders:
            raise YandexMarketError(404, "order_not_found", "Заказ не найден")
        return dict(orders[0])

    async def deliver_digital_goods(self, order_id: int,
                                    items: list[dict[str, Any]]) -> dict[str, Any]:
        return await self._post(
            f"/v2/campaigns/{self.campaign_id}/orders/{int(order_id)}/deliverDigitalGoods",
            {"items": items},
        )


class YandexMarketDigital:
    """Персистентный идемпотентный обработчик цифровых заказов."""

    def __init__(self, store: Any, client: YandexMarketClient, *, sku: str,
                 activation_url: str = "http://localhost:8090/ya_market",
                 clock: Callable[[], float] = time.time, poll_interval: float = 2.0):
        self.store = store
        self.client = client
        self.sku = str(sku or "").strip()
        self.activation_url = activation_url.rstrip("/")
        self.clock = clock
        self.poll_interval = max(0.1, float(poll_interval))
        self.enabled = bool(client.enabled and self.sku)
        self._locks: dict[str, asyncio.Lock] = {}

    def _lock(self, key: str) -> asyncio.Lock:
        return self._locks.setdefault(key, asyncio.Lock())

    async def handle_notification(self, payload: dict[str, Any]) -> None:
        notification_type = str(payload.get("notificationType") or "").upper()
        if notification_type == "PING":
            return
        if notification_type not in {"ORDER_STATUS_UPDATED", "ORDER_CANCELLED"}:
            return
        try:
            campaign_id = int(payload["campaignId"])
            order_id = int(payload["orderId"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("campaignId и orderId обязательны") from exc
        if campaign_id != self.client.campaign_id:
            log.info("market: игнорируется уведомление другой кампании %s", campaign_id)
            return
        status = "CANCELLED" if notification_type == "ORDER_CANCELLED" else str(
            payload.get("status") or "").upper()
        updated_at = str(payload.get("updatedAt") or payload.get("cancelledAt") or "") or None
        key = self.store.market_order_key(campaign_id, order_id)
        # Один lock на заказ закрывает гонку «CANCELLED пришёл во время выдачи»:
        # либо отмена удалит ещё не раскрытые коды, либо увидит уже delivery_sent и
        # сохранит их для ручной проверки возврата.
        async with self._lock(key):
            if status == "PROCESSING":
                if not self.enabled:
                    raise RuntimeError("Интеграция Яндекс Маркета не настроена")
                await self.store.queue_market_order(
                    campaign_id, order_id, updated_at=updated_at)
            elif status in _FINAL_MARKET_STATUSES:
                await self.store.set_market_order_status(
                    campaign_id, order_id, market_status=status, updated_at=updated_at)

    async def run(self) -> None:
        log.info("Яндекс Маркет: воркер цифровых заказов запущен (SKU=%s)", self.sku)
        while True:
            try:
                await self.tick()
            except asyncio.CancelledError:
                raise
            except Exception:  # noqa: BLE001 — единичный заказ не должен ронять процесс
                log.warning("market: сбой прохода воркера", exc_info=True)
            await asyncio.sleep(self.poll_interval)

    async def tick(self) -> int:
        processed = 0
        now = int(self.clock())
        for key in self.store.due_market_order_ids(now=now):
            await self._process(key)
            processed += 1
        return processed

    async def _process(self, key: str) -> None:
        async with self._lock(key):
            await self._process_locked(key)

    async def _process_locked(self, key: str) -> None:
        rec = self.store.market_order(key)
        if rec is None or rec.get("state") not in {"queued", "processing", "retry"}:
            return
        attempt = int(rec.get("attempt_count") or 0) + 1
        await self.store.update_market_order(key, {
            "state": "processing",
            "attempt_count": attempt,
            "last_attempt_at": int(self.clock()),
            "last_error": None,
        })
        try:
            order = await self.client.get_order(int(rec["order_id"]))
            await self._deliver_order(key, rec, order)
        except asyncio.CancelledError:
            raise
        except YandexMarketError as exc:
            await self._handle_error(key, rec, attempt, exc)
        except Exception as exc:  # noqa: BLE001 — неизвестный локальный сбой ретраим
            wrapped = YandexMarketError(0, "internal", repr(exc)[:300], transient=True)
            await self._handle_error(key, rec, attempt, wrapped)

    async def _deliver_order(self, key: str, rec: dict[str, Any],
                             order: dict[str, Any]) -> None:
        campaign_id = int(order.get("campaignId") or 0)
        order_id = int(order.get("orderId") or 0)
        if campaign_id != self.client.campaign_id or order_id != int(rec["order_id"]):
            raise YandexMarketError(400, "order_mismatch", "API вернул другой заказ")
        status = str(order.get("status") or "").upper()
        if status in _FINAL_MARKET_STATUSES:
            await self.store.set_market_order_status(
                campaign_id, order_id, market_status=status,
                updated_at=str(order.get("updateDate") or "") or None)
            return
        if status != "PROCESSING":
            raise YandexMarketError(409, "order_not_processing",
                                    f"Актуальный статус заказа: {status or 'UNKNOWN'}",
                                    transient=True)
        delivery = order.get("delivery") if isinstance(order.get("delivery"), dict) else {}
        digital = delivery.get("digitalGoods") if isinstance(delivery.get("digitalGoods"), dict) else {}
        if str(delivery.get("type") or "").upper() != "DIGITAL":
            raise YandexMarketError(400, "not_digital", "Заказ не является цифровым")
        delivery_type = str(digital.get("type") or "").upper()
        if delivery_type not in _DELIVERY_TYPES:
            raise YandexMarketError(
                400, "unsupported_delivery_type", f"Тип доставки {delivery_type or 'UNKNOWN'} не поддержан")

        raw_items = order.get("items") if isinstance(order.get("items"), list) else []
        items: list[dict[str, Any]] = []
        for item in raw_items:
            if not isinstance(item, dict) or str(item.get("offerId") or "") != self.sku:
                raise YandexMarketError(
                    400, "unsupported_offer", "Заказ содержит товар с неподдерживаемым SKU")
            try:
                item_id = int(item["id"])
                count = int(item["count"])
            except (KeyError, TypeError, ValueError) as exc:
                raise YandexMarketError(400, "bad_item", "Некорректная позиция заказа") from exc
            if item_id < 0 or count < 1:
                raise YandexMarketError(400, "bad_item", "Некорректный id или count позиции")
            items.append({"id": item_id, "offer_id": self.sku, "count": count})
        if not items:
            raise YandexMarketError(400, "empty_order", "В заказе нет поддерживаемых позиций")

        reserved = self.store.market_order(key)
        if reserved is None:
            return
        if not reserved.get("items"):
            created_at = int(self.clock())
            activate_till = datetime.fromtimestamp(
                created_at + ACTIVATION_CODE_TTL, tz=timezone.utc).date().isoformat()
            for _ in range(10):
                prepared = [{
                    **item,
                    "codes": [generate_code() for _ in range(item["count"])],
                    "activate_till": activate_till,
                } for item in items]
                try:
                    reserved = await self.store.reserve_market_activation_codes(
                        key, prepared, created_at=created_at)
                    break
                except KeyError:  # практически невозможная коллизия; генерируем заново
                    continue
            else:
                raise YandexMarketError(500, "code_collision", "Не удалось создать уникальные коды",
                                        transient=True)
        if reserved is None:
            return
        slip = (
            f"<h2>Активация {config.BOT_NAME} Smart</h2>"
            "<ol>"
            f"<li>Откройте {self.activation_url}</li>"
            f"<li>Введите номер телефона вашего аккаунта {config.BOT_NAME}.</li>"
            "<li>Введите код из заказа и примите условия.</li>"
            "</ol>"
            "<p>Подписка на один месяц активируется сразу. "
            "Код одноразовый и действует 30 дней.</p>"
        )
        payload_items = [{
            "id": int(item["id"]),
            "codes": list(item.get("codes") or []),
            "slip": slip,
            "activate_till": str(item.get("activate_till") or ""),
        } for item in reserved.get("items") or []]
        await self.client.deliver_digital_goods(order_id, payload_items)
        await self.store.update_market_order(key, {
            "state": "delivery_sent",
            "delivery_sent_at": int(self.clock()),
            "next_attempt_at": 0,
            "last_error": None,
        })
        try:
            await self.store.add_event(
                kind="yandex_market",
                title=f"Коды переданы в заказ Яндекс Маркета №{order_id}",
                detail={"order_id": order_id, "items": len(payload_items),
                        "codes": sum(len(item["codes"]) for item in payload_items)},
            )
        except Exception:  # noqa: BLE001 — журнал не должен повторно раскрывать коды
            log.warning("market: событие успешной доставки не записано", exc_info=True)
        log.info("market: заказ %s — передано кодов: %d", order_id,
                 sum(len(item["codes"]) for item in payload_items))

    async def _handle_error(self, key: str, rec: dict[str, Any], attempt: int,
                            exc: YandexMarketError) -> None:
        now = int(self.clock())
        error = f"{exc.status}:{exc.code}:{exc.message}"[:500]
        if exc.transient:
            delay = min(60, max(2, 2 ** min(attempt, 6)))
            await self.store.update_market_order(key, {
                "state": "retry",
                "next_attempt_at": now + delay,
                "last_error": error,
            })
            log.warning("market: заказ %s — временный сбой, повтор через %s с: %s",
                        rec.get("order_id"), delay, error)
            return
        await self.store.update_market_order(key, {
            "state": "failed",
            "failed_at": now,
            "next_attempt_at": 0,
            "last_error": error,
        })
        await self.store.add_event(
            kind="yandex_market_error",
            title=f"Не выданы коды заказа Яндекс Маркета №{rec.get('order_id')}",
            detail={"order_id": rec.get("order_id"), "error": error},
        )
        log.error("market: заказ %s — окончательный сбой: %s", rec.get("order_id"), error)
