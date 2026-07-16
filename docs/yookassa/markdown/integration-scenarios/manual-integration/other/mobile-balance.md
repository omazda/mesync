<!-- Источник: https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/other/mobile-balance -->
<!-- Полная копия статьи официальной документации ЮKassa, сохранено 2026-07-02 -->

# Баланс мобильного телефона

Особенности

- Тип способа оплаты в API: `mobile_balance`
- [Сценарий подтверждения](https://yookassa.ru/developers/payment-acceptance/getting-started/payment-process#user-confirmation): External
- [Срок оплаты](https://yookassa.ru/developers/payment-acceptance/getting-started/payment-methods#payment-term): 1 час
- [Холдирование](https://yookassa.ru/developers/payment-acceptance/getting-started/payment-process#capture-and-cancel): 6 часов, доступно только полное списание оплаты
- [Код в реестре](https://yookassa.ru/developers/payment-acceptance/after-the-payment/reports): MC
- [Возврат](https://yookassa.ru/developers/payment-acceptance/after-the-payment/refunds): да, полный и частичный
- Срок возврата: моментально
- [Автоплатежи](https://yookassa.ru/developers/payment-acceptance/scenario-extensions/recurring-payments/basics): нет
- [Лимиты](https://yookassa.ru/developers/payment-acceptance/getting-started/payment-methods#payment-limit): минимальный размер платежа 10 рублей, максимальный — от 5 000 до 15 000 рублей (зависит от оператора), есть [дополнительные ограничения](https://yookassa.ru/docs/support/payments/limits)
- Поддерживаемые операторы мобильной связи: Мегафон, Билайн, МТС, t2

Сценарии интеграции

Готовые решения: [Умный платеж](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/smart-payment)

Самостоятельная интеграция: [Оплата с баланса мобильного телефона](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/other/mobile-balance#create-payment)

Оплата с баланса мобильного телефона

**Шаг 1**. [Создайте платеж](https://yookassa.ru/developers/api#create_payment), в объекте `payment_method_data` передайте тип `mobile_balance` и телефон пользователя, с баланса которого планируется принять оплату, а в объекте `confirmation` передайте тип `external`.

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
          "type": "mobile_balance",
          "phone": "79000000000"
        },
        "confirmation": {
          "type": "external"
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
                'type' => 'mobile_balance',
                'phone' => '79000000000',
            ),
            'confirmation' => array(
                'type' => 'external',
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
        "type": "mobile_balance",
        "phone": "79000000000"
    },
    "confirmation": {
        "type": "external"
    },
    "description": "Заказ №72"
})
```

**Пример созданного объекта платежа**

**JSON**

```json
{
  "id": "22c80e01-000f-5000-a000-14ce15eb7b74",
  "status": "pending",
  "paid": false,
  "amount": {
    "value": "2.00",
    "currency": "RUB"
  },
  "confirmation": {
    "type": "external"
  },
  "created_at": "2018-06-29T09:22:09.367Z",
  "description": "Заказ №72",
  "metadata": {},
  "payment_method": {
    "type": "mobile_balance",
    "id": "22c80e01-000f-5000-a000-14ce15eb7b74",
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

**Шаг 2**. Сообщите пользователю, что ему необходимо подтвердить оплату.

**Шаг 3**. Дождитесь успешного завершения платежа: подождите, когда придет [уведомление](https://yookassa.ru/developers/using-api/webhooks) от ЮKassa, или периодически отправляйте запросы, чтобы получить [информацию о платеже](https://yookassa.ru/developers/api#get_payment).

Готово!

Что почитать еще

[Основы проведения платежей](https://yookassa.ru/developers/payment-acceptance/getting-started/payment-process)

[Неуспешные платежи](https://yookassa.ru/developers/payment-acceptance/after-the-payment/declined-payments)

[Отправка чеков в налоговую](https://yookassa.ru/developers/payment-acceptance/receipts/basics)
