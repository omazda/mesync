"""Автовыдача цифровых кодов Яндекс Маркета."""
from __future__ import annotations

import asyncio
import json
import sys
import time
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from control import config  # noqa: E402
from control.api import create_app, set_yandex_market  # noqa: E402
from control.store import ACTIVATION_CODE_TTL, ControlStore  # noqa: E402
from control.yandex_market import (  # noqa: E402
    YandexMarketClient,
    YandexMarketDigital,
    YandexMarketError,
)


def run(coro):
    return asyncio.run(coro)


def fresh_store(tmp_path: Path) -> ControlStore:
    return ControlStore(tmp_path / f"market-{time.time_ns()}.json")


class FakeMarketClient:
    def __init__(self, *, fail_first: bool = False):
        self.enabled = True
        self.business_id = 22
        self.campaign_id = 11
        self.fail_first = fail_first
        self.get_calls = 0
        self.deliveries: list[list[dict]] = []

    async def get_order(self, order_id: int) -> dict:
        self.get_calls += 1
        return {
            "orderId": order_id,
            "campaignId": self.campaign_id,
            "status": "PROCESSING",
            "items": [{"id": 101, "offerId": "MESYNC-SMART-1M", "count": 2}],
            "delivery": {
                "type": "DIGITAL",
                "digitalGoods": {"type": "ACTIVATION_CODE"},
            },
        }

    async def deliver_digital_goods(self, order_id: int, items: list[dict]) -> dict:
        self.deliveries.append(json.loads(json.dumps(items)))
        if self.fail_first and len(self.deliveries) == 1:
            raise YandexMarketError(500, "temporary", "try later", transient=True)
        return {"status": "OK"}


def test_digital_worker_retries_same_codes_and_is_idempotent(tmp_path):
    store = fresh_store(tmp_path)
    client = FakeMarketClient(fail_first=True)
    now = {"value": 1_700_000_000}
    worker = YandexMarketDigital(
        store, client, sku="MESYNC-SMART-1M",
        activation_url="https://service.example/activate",
        clock=lambda: now["value"],
        poll_interval=0.01)

    notification = {
        "notificationType": "ORDER_STATUS_UPDATED",
        "campaignId": 11,
        "orderId": 9001,
        "status": "PROCESSING",
        "updatedAt": "2026-07-11T10:00:00Z",
    }
    run(worker.handle_notification(notification))
    assert run(worker.tick()) == 1
    rec = store.market_order("11:9001")
    assert rec["state"] == "retry"
    assert len(rec["items"]) == 1 and len(rec["items"][0]["codes"]) == 2
    first_codes = client.deliveries[0][0]["codes"]
    assert len(set(first_codes)) == 2
    for code in first_codes:
        code_rec = store.table("activation_codes")[code]
        assert code_rec["source"] == "yandex_market"
        assert code_rec["market_order_id"] == "11:9001"
        assert code_rec["expires_at"] == now["value"] + ACTIVATION_CODE_TTL

    now["value"] = rec["next_attempt_at"]
    assert run(worker.tick()) == 1
    assert store.market_order("11:9001")["state"] == "delivery_sent"
    assert client.deliveries[1][0]["codes"] == first_codes
    assert client.deliveries[1][0]["activate_till"] == "2023-12-14"
    assert "https://service.example/activate" in client.deliveries[1][0]["slip"]

    # Дубликат PROCESSING после успешного deliverDigitalGoods не открывает заказ заново.
    run(worker.handle_notification(notification))
    assert run(worker.tick()) == 0
    assert len(client.deliveries) == 2
    run(worker.handle_notification({
        **notification, "status": "DELIVERED", "updatedAt": "2026-07-11T10:00:10Z"}))
    assert store.market_order("11:9001")["state"] == "delivered"


def test_cancel_before_delivery_removes_reserved_codes(tmp_path):
    store = fresh_store(tmp_path)
    rec = run(store.queue_market_order(11, 9002))
    run(store.reserve_market_activation_codes(rec["id"], [{
        "id": 7,
        "offer_id": "MESYNC-SMART-1M",
        "codes": ["AbCd-1234-WxYz"],
        "activate_till": "2030-01-01",
    }], created_at=1_700_000_000))
    assert "AbCd-1234-WxYz" in store.table("activation_codes")
    run(store.set_market_order_status(11, 9002, market_status="CANCELLED"))
    assert store.market_order("11:9002")["state"] == "cancelled"
    assert "AbCd-1234-WxYz" not in store.table("activation_codes")


def test_cancel_racing_delivery_keeps_already_exposed_code(tmp_path):
    class BlockingClient(FakeMarketClient):
        def __init__(self):
            super().__init__()
            self.started = asyncio.Event()
            self.release = asyncio.Event()

        async def deliver_digital_goods(self, order_id: int, items: list[dict]) -> dict:
            self.deliveries.append(json.loads(json.dumps(items)))
            self.started.set()
            await self.release.wait()
            return {"status": "OK"}

    async def scenario():
        store = fresh_store(tmp_path)
        client = BlockingClient()
        worker = YandexMarketDigital(store, client, sku="MESYNC-SMART-1M")
        processing = {
            "notificationType": "ORDER_STATUS_UPDATED",
            "campaignId": 11,
            "orderId": 9010,
            "status": "PROCESSING",
        }
        await worker.handle_notification(processing)
        delivery_task = asyncio.create_task(worker.tick())
        await client.started.wait()
        cancel_task = asyncio.create_task(worker.handle_notification({
            "notificationType": "ORDER_CANCELLED",
            "campaignId": 11,
            "orderId": 9010,
        }))
        await asyncio.sleep(0)
        assert not cancel_task.done()  # отмена сериализована с выдачей одного заказа
        client.release.set()
        await delivery_task
        await cancel_task
        rec = store.market_order("11:9010")
        assert rec["state"] == "cancelled_after_delivery"
        code = client.deliveries[0][0]["codes"][0]
        assert code in store.table("activation_codes")

    run(scenario())


def test_partner_client_uses_api_key_and_official_paths():
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path.endswith("/orders"):
            return httpx.Response(200, json={"orders": [{"orderId": 9}]})
        return httpx.Response(200, json={"status": "OK"})

    async def scenario():
        client = YandexMarketClient("secret-api-key", business_id=22, campaign_id=11)
        client._client = httpx.AsyncClient(
            base_url="https://api.partner.market.yandex.ru",
            transport=httpx.MockTransport(handler))
        try:
            assert (await client.get_order(9))["orderId"] == 9
            await client.deliver_digital_goods(9, [{
                "id": 1, "codes": ["code"], "slip": "instruction",
                "activate_till": "2030-01-01"}])
        finally:
            await client.aclose()

    run(scenario())
    assert requests[0].headers["Api-Key"] == "secret-api-key"
    assert requests[0].url.path == "/v1/businesses/22/orders"
    assert json.loads(requests[0].content) == {"orderIds": [9], "campaignIds": [11]}
    assert requests[1].url.path == "/v2/campaigns/11/orders/9/deliverDigitalGoods"


def test_notification_webhook_secret_ip_ping_and_queue(tmp_path, monkeypatch):
    class Handler:
        def __init__(self):
            self.payloads = []

        async def handle_notification(self, payload):
            self.payloads.append(payload)

    handler = Handler()
    monkeypatch.setattr(config, "YANDEX_MARKET_ENABLED", True)
    monkeypatch.setattr(config, "YANDEX_MARKET_WEBHOOK_SECRET", "webhook-secret")
    monkeypatch.setattr(config, "YANDEX_MARKET_ENFORCE_IP", True)
    set_yandex_market(handler)
    try:
        client = TestClient(create_app(fresh_store(tmp_path)))
        allowed = {"X-Forwarded-For": "203.0.113.8, 5.45.207.42"}
        # Кабинет принимает базовый URL, но фактический POST отправляет на /notification.
        ping = client.post(
            "/api/yandex-market/notifications/webhook-secret/notification",
            headers=allowed,
            json={"notificationType": "PING", "time": "2026-07-11T10:00:00Z"},
        )
        assert ping.status_code == 200
        assert ping.json()["version"] == "1.0.0"
        assert ping.json()["name"].endswith(" Yandex Market digital delivery")
        assert handler.payloads[-1]["notificationType"] == "PING"

        # Старый прямой URL остаётся рабочим для совместимости и ручного smoke.
        direct = client.post(
            "/api/yandex-market/notifications/webhook-secret",
            headers=allowed, json={"notificationType": "PING"})
        assert direct.status_code == 200

        wrong_secret = client.post(
            "/api/yandex-market/notifications/wrong", headers=allowed,
            json={"notificationType": "PING"})
        assert wrong_secret.status_code == 401
        wrong_ip = client.post(
            "/api/yandex-market/notifications/webhook-secret",
            headers={"X-Forwarded-For": "203.0.113.8"},
            json={"notificationType": "PING"})
        assert wrong_ip.status_code == 403

        notification = {
            "notificationType": "ORDER_STATUS_UPDATED",
            "campaignId": 11,
            "orderId": 9003,
            "status": "PROCESSING",
            "updatedAt": "2026-07-11T10:00:00Z",
        }
        queued = client.post(
            "/api/yandex-market/notifications/webhook-secret",
            headers=allowed, json=notification)
        assert queued.status_code == 200
        assert handler.payloads[-1] == notification
    finally:
        set_yandex_market(None)


def test_notification_webhook_is_disabled_by_env_flag(tmp_path, monkeypatch):
    class Handler:
        def __init__(self):
            self.payloads = []

        async def handle_notification(self, payload):
            self.payloads.append(payload)

    handler = Handler()
    monkeypatch.setattr(config, "YANDEX_MARKET_ENABLED", False)
    monkeypatch.setattr(config, "YANDEX_MARKET_WEBHOOK_SECRET", "webhook-secret")
    monkeypatch.setattr(config, "YANDEX_MARKET_ENFORCE_IP", True)
    set_yandex_market(handler)
    try:
        client = TestClient(create_app(fresh_store(tmp_path)))
        response = client.post(
            "/api/yandex-market/notifications/webhook-secret/notification",
            headers={"X-Forwarded-For": "5.45.207.42"},
            json={"notificationType": "PING"},
        )
        assert response.status_code == 503
        assert response.json()["detail"]["code"] == "market_integration_disabled"
        assert handler.payloads == []
    finally:
        set_yandex_market(None)


def test_worker_rejects_mixed_or_unsupported_sku(tmp_path):
    store = fresh_store(tmp_path)
    client = FakeMarketClient()

    async def mixed_order(order_id: int) -> dict:
        order = await FakeMarketClient.get_order(client, order_id)
        order["items"].append({"id": 102, "offerId": "OTHER-SKU", "count": 1})
        return order

    client.get_order = mixed_order
    worker = YandexMarketDigital(store, client, sku="MESYNC-SMART-1M")
    run(worker.handle_notification({
        "notificationType": "ORDER_STATUS_UPDATED",
        "campaignId": 11,
        "orderId": 9004,
        "status": "PROCESSING",
    }))
    assert run(worker.tick()) == 1
    rec = store.market_order("11:9004")
    assert rec["state"] == "failed"
    assert "unsupported_offer" in rec["last_error"]
    assert client.deliveries == []
