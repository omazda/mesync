<!-- Источник: https://yookassa.ru/developers/payment-acceptance/integration-scenarios/mobile-sdks/payments-with-tokens -->
<!-- Полная копия статьи официальной документации ЮKassa, сохранено 2026-07-02 -->

# Проведение платежа с использованием мобильных SDK

Если используете мобильные SDK, для проведения платежа вам нужно обменять в SDK платежные данные на токен и передать его в запросе к API при создании платежа.

Необходимо получить у менеджера ЮKassa разрешение на проведение платежей с использованием токена.

Платеж токеном

**Шаг 1**. Получите платежный токен в [iOS](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/mobile-sdks/ios-sdk) или [Android](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/mobile-sdks/android-sdk) SDK. Токен будет содержать выбранный способ оплаты, платежные данные и данные о [сценарии подтверждения](https://yookassa.ru/developers/payment-acceptance/getting-started/payment-process#user-confirmation) платежа.

**Шаг 2**. Передайте токен на ваш сервер.

**Шаг 3**. [Создайте платеж](https://yookassa.ru/developers/api#create_payment), в параметре `payment_token` передайте платежный токен.

Токен одноразовый, срок действия — 1 час. Если не создать платеж в течение часа, токен нужно будет запрашивать заново.

**Пример запроса**

**cURL**

```bash
curl https://api.yookassa.ru/v3/payments \
  -X POST \
  -u <Идентификатор магазина>:<Секретный ключ> \
  -H 'Idempotence-Key: <Ключ идемпотентности>' \
  -H 'Content-Type: application/json' \
  -d '{
        "payment_token": "pt-28cd3959-0000-500c-a000-03b4de9b24a7",
        "amount": {
          "value": "2.00",
          "currency": "RUB"
        },
        "capture": false,
        "description": "Заказ №72"
      }'
```

**PHP**

```php
<?php
    $client->createPayment(
        array(
            ‘payment_token’ => ‘pt-28cd3959-0000-500c-a000-03b4de9b24a7’,
            'amount' => array(
                'value' => 2,
                'currency' => 'RUB',
            ),
            'capture' => false,
            'description' => 'Заказ №72',
        ),
        uniqid('', true)
    );
?>
```

**Python**

```python
from yookassa import Payment

payment = Payment.create({
    "payment_token": "pt-28cd3959-0000-500c-a000-03b4de9b24a7",
    "amount": {
        "value": "2.00",
        "currency": "RUB"
    },
    "capture": False,
    "description": "Заказ №72"
})
```

**Шаг 4**. Если платеж вернулся в статусе `pending`, передайте `confirmation_url` в мобильный SDK.

**Пример созданного объекта платежа**

**JSON**

```json
{
  "id": "23d93cac-000f-5000-8000-126628f15141",
  "status": "pending",
  "paid": false,
  "amount": {
    "value": "2.00",
    "currency": "RUB"
  },
  "confirmation": {
    "type": "redirect",
    "confirmation_url": "<Ссылка для прохождения 3-D Secure>"
  },
  "created_at": "2019-01-22T14:30:45.129Z",
  "description": "Заказ №72",
  "metadata": {},
  "recipient": {
    "account_id": "100500",
    "gateway_id": "100700"
  },
  "refundable": false,
  "test": false
}
```

**Шаг 5**. Дождитесь успешного завершения платежа: подождите, когда придет [уведомление](https://yookassa.ru/developers/using-api/webhooks) от ЮKassa, или периодически отправляйте запросы, чтобы получить [информацию о платеже](https://yookassa.ru/developers/api#get_payment).

Что почитать еще

[iOS SDK](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/mobile-sdks/ios-sdk)

[Android SDK](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/mobile-sdks/android-sdk)

[Неуспешные платежи](https://yookassa.ru/developers/payment-acceptance/after-the-payment/declined-payments)

[Основы работы с API](https://yookassa.ru/developers/using-api/interaction-format)
