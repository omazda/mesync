<!-- Источник: https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/other/cash -->
<!-- Полная копия статьи официальной документации ЮKassa, сохранено 2026-07-02 -->

# Наличные

Особенности

- Тип способа оплаты в API: `cash`
- [Сценарий подтверждения](https://yookassa.ru/developers/payment-acceptance/getting-started/payment-process#user-confirmation): Redirect
- [Срок оплаты](https://yookassa.ru/developers/payment-acceptance/getting-started/payment-methods#payment-term): Без ограничений
- [Холдирование](https://yookassa.ru/developers/payment-acceptance/getting-started/payment-process#capture-and-cancel): 6 часов, доступно только полное списание оплаты
- [Код в реестре](https://yookassa.ru/developers/payment-acceptance/after-the-payment/reports): GP
- [Возврат](https://yookassa.ru/developers/payment-acceptance/after-the-payment/refunds): нет
- [Автоплатежи](https://yookassa.ru/developers/payment-acceptance/scenario-extensions/recurring-payments/basics): нет
- [Лимиты](https://yookassa.ru/developers/payment-acceptance/getting-started/payment-methods#payment-limit): минимальный размер платежа — 1 рубль, максимальный — 100 000 рублей, но может быть меньше (зависит от терминала оплаты)

Сценарии интеграции

Готовые решения: [Умный платеж](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/smart-payment)

Самостоятельная интеграция: [Оплата по коду подтверждения](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/other/cash#create-payment)

Оплата по коду подтверждения

**Шаг 1**. [Создайте платеж](https://yookassa.ru/developers/api#create_payment), в объекте `payment_method_data` передайте тип `cash` и, если известен, телефон пользователя, на который придет код подтверждения платежа. В объекте `confirmation` передайте тип `redirect` и адрес страницы на вашей стороне, на которую пользователь вернется после оплаты (в параметре `return_url`).

**Пример запроса**

**cURL**

```bash
curl https://api.yookassa.ru/v3/payments \
  -X POST \
  -u <Идентификатор магазина>:<Секретный ключ> \
  -H 'Idempotence-Key: <Ключ идемпотентности>' \
  -H 'Content-Type: application/json' \
  -d '{
        "amount": {
          "value": "2.00",
          "currency": "RUB"
        },
        "payment_method_data": {
          "type": "cash",
          "phone": "79000000000"
        },
        "confirmation": {
          "type": "redirect",
          "return_url": "https://www.example.com/return_url"
        },
        "description": "Заказ №72"
      }'
```

**PHP**

```php
<?php
    $client->createPayment(
        array(
            'amount' => array(
                'value' => 2,
                'currency' => 'RUB',
            ),
            'payment_method_data' => array(
                'type' => 'cash',
                'phone' => '79000000000',
            ),
            'confirmation' => array(
                'type' => 'redirect',
                'return_url' => 'https://www.example.com/return_url',
            ),
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
    "amount": {
        "value": "2.00",
        "currency": "RUB"
    },
    "payment_method_data": {
        "type": "cash",
        "phone": "79000000000"
    },
    "confirmation": {
        "type": "redirect",
        "return_url": "https://www.example.com/return_url"
    },
    "description": "Заказ №72"
})
```

**Шаг 2**. Перенаправьте пользователя на страницу для получения кода платежа (ссылка на страницу придет в параметре `confirmation_url`).

**Пример созданного объекта платежа**

**JSON**

```json
{
  "id": "22c5d3e2-000f-5000-8000-10a783a9392b",
  "status": "pending",
  "paid": false,
  "amount": {
    "value": "2.00",
    "currency": "RUB"
  },
  "confirmation": {
    "type": "redirect",
    "confirmation_url": "https://yoomoney.ru/api-pages/v2/payment-confirm/cash?orderId=22c5d3e2-000f-5000-8000-10a783a9392b"
  },
  "created_at": "2018-06-27T16:49:38.669Z",
  "description": "Заказ №72",
  "metadata": {},
  "payment_method": {
    "type": "cash",
    "id": "22c5d3e2-000f-5000-8000-10a783a9392b",
    "saved": false
  },
  "recipient": {
    "account_id": "100500",
    "gateway_id": "100700"
  },
  "refundable": false,
  "test": false
}
```

**Шаг 3**. Дождитесь успешного завершения платежа: подождите, когда придет [уведомление](https://yookassa.ru/developers/using-api/webhooks) от ЮKassa, или периодически отправляйте запросы, чтобы получить [информацию о платеже](https://yookassa.ru/developers/api#get_payment).

Что почитать еще

[Основы проведения платежей](https://yookassa.ru/developers/payment-acceptance/getting-started/payment-process)

[Неуспешные платежи](https://yookassa.ru/developers/payment-acceptance/after-the-payment/declined-payments)

[Отправка чеков в налоговую](https://yookassa.ru/developers/payment-acceptance/receipts/basics)
