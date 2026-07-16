"""Асинхронный клиент API ЮKassa (минимум, нужный биллингу подписки).

Сверено с локальной документацией `docs/yookassa/`:
  - создание платежа: POST /v3/payments — getting-started/quick-start.md,
    widget/additional-settings/recurring-payments.md (confirmation.type=embedded,
    save_payment_method) и scenario-extensions/recurring-payments/pay-with-saved.md
    (автоплатёж: payment_method_id, без confirmation);
  - информация о платеже: GET /v3/payments/{id} — getting-started/payment-process.md;
  - привязка на нулевую сумму: POST /v3/payment_methods + GET /v3/payment_methods/{id} —
    scenario-extensions/recurring-payments/save-payment-method/save-without-payment/*.md;
  - аутентификация: HTTP Basic `shopId:секретный ключ`; каждый POST обязан нести
    заголовок Idempotence-Key (повтор с тем же ключом безопасен).

Суммы ЮKassa принимает строками с двумя знаками ("299.00", currency "RUB").
"""
from __future__ import annotations

import logging
import uuid
from typing import Any

import httpx

log = logging.getLogger("control.yookassa")


class YooKassaError(Exception):
    """Ошибка API ЮKassa (HTTP-статус + code/description из тела ответа)."""

    def __init__(self, status: int, code: str, description: str):
        super().__init__(f"{status} {code}: {description}")
        self.status = status
        self.code = code
        self.description = description


class YooKassaClient:
    """Тонкая обёртка над HTTP API. Все методы асинхронные (httpx.AsyncClient)."""

    def __init__(self, shop_id: str, secret_key: str,
                 base_url: str = "https://api.yookassa.ru", timeout: float = 20.0):
        self.enabled = bool(shop_id and secret_key)
        self._base = base_url.rstrip("/")
        self._timeout = timeout
        self._client: httpx.AsyncClient | None = None
        self._auth = (shop_id, secret_key)

    def _http(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self._base, auth=self._auth, timeout=self._timeout)
        return self._client

    async def aclose(self) -> None:
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()

    async def _call(self, method: str, path: str, *, body: dict[str, Any] | None = None,
                    idempotence_key: str | None = None) -> dict[str, Any]:
        headers = {}
        if method == "POST":
            # Idempotence-Key обязателен для POST (docs/yookassa: основы работы с API).
            headers["Idempotence-Key"] = idempotence_key or str(uuid.uuid4())
        resp = await self._http().request(method, path, json=body, headers=headers)
        try:
            data = resp.json()
        except Exception:  # noqa: BLE001 — не-JSON ответ (5xx от прокси и т.п.)
            data = {}
        if resp.status_code >= 400:
            raise YooKassaError(resp.status_code, str(data.get("code") or "unknown"),
                                str(data.get("description") or resp.text[:200]))
        return data

    # ---------------- платежи ----------------
    async def create_payment(self, *, amount_rub: int, description: str,
                             metadata: dict[str, Any] | None = None,
                             save_payment_method: bool | None = None,
                             payment_method_id: str | None = None,
                             embedded: bool = False,
                             idempotence_key: str | None = None) -> dict[str, Any]:
        """POST /v3/payments.

        Два режима (оба capture=true — одностадийный платёж):
          - обычный платёж под виджет: embedded=True → confirmation.type=embedded,
            в ответе будет confirmation.confirmation_token;
          - автоплатёж: payment_method_id → без confirmation, подтверждение
            пользователя не требуется (pay-with-saved.md).
        """
        body: dict[str, Any] = {
            "amount": {"value": f"{amount_rub}.00", "currency": "RUB"},
            "capture": True,
            "description": description,
        }
        if metadata:
            body["metadata"] = metadata
        if payment_method_id:
            body["payment_method_id"] = payment_method_id
        elif embedded:
            body["confirmation"] = {"type": "embedded"}
        if save_payment_method is not None:
            body["save_payment_method"] = save_payment_method
        return await self._call("POST", "/v3/payments", body=body,
                                idempotence_key=idempotence_key)

    async def get_payment(self, payment_id: str) -> dict[str, Any]:
        return await self._call("GET", f"/v3/payments/{payment_id}")

    # ---------------- привязка на нулевую сумму ----------------
    async def create_payment_method(self, *, type_: str, return_url: str,
                                    metadata: dict[str, Any] | None = None,
                                    idempotence_key: str | None = None) -> dict[str, Any]:
        """POST /v3/payment_methods (нулевая привязка: bank_card или sbp).

        Ответ содержит confirmation.confirmation_url — готовая страница привязки
        ЮKassa (живёт 1 час); после подтверждения объект переходит в status=active.
        """
        body: dict[str, Any] = {
            "type": type_,
            "confirmation": {"type": "redirect", "return_url": return_url},
        }
        if metadata:
            body["metadata"] = metadata
        return await self._call("POST", "/v3/payment_methods", body=body,
                                idempotence_key=idempotence_key)

    async def get_payment_method(self, payment_method_id: str) -> dict[str, Any]:
        return await self._call("GET", f"/v3/payment_methods/{payment_method_id}")
