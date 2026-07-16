<!-- Источник: https://yookassa.ru/developers/payment-acceptance/scenario-extensions/recurring-payments/pay-with-saved -->
<!-- Полная копия статьи официальной документации ЮKassa, сохранено 2026-07-02 -->

# Проведение автоплатежа

Автоплатежи — это повторные безакцептные списания. Их можно проводить, когда вы привяжете платежное средство пользователя к своему магазину. Периодичность списаний и процесс отключения автоплатежей настраивается на вашей стороне без участия ЮKassa.

Создание автоплатежа

Чтобы провести автоплатеж, [создайте платеж](https://yookassa.ru/developers/api#create_payment) и передайте в нём сумму, описание транзакции и параметр `payment_method_id` с идентификатором сохраненного способа оплаты. Такой платеж не потребует дополнительного [подтверждения от пользователя](https://yookassa.ru/developers/payment-acceptance/getting-started/payment-process#user-confirmation).

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
        "capture": true,
        "payment_method_id": "<Идентификатор сохраненного способа оплаты>",
        "description": "Заказ №37"
      }'
```

**PHP**

```php
<?php
    $payment = $client->createPayment(
        array(
            'amount' => array(
                'value' => 2.0,
                'currency' => 'RUB',
            ),
            'capture' => true,
            'payment_method_id' => '<Идентификатор сохраненного способа оплаты>',
            'description' => 'Заказ №37',
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
    "capture": True,
    "payment_method_id": "<Идентификатор сохраненного способа оплаты>",
    "description": "Заказ №37"
})
```

При успешной оплате в объекте `payment_method` будет отображаться информация о платежных данных сохраненного способа.

Если вы используете решение ЮKassa для работы по 54-ФЗ и сценарий [Сначала чек, потом платеж](https://yookassa.ru/developers/payment-acceptance/receipts/54fz/other-services/basics#payment-after-receipt), то платеж может вернуться в статусе `pending`. Это значит, что ЮKassa дожидается от онлайн-кассы результатов формирования чека. Чтобы узнать об успешной или неуспешной регистрации чека и статусе платежа, дождитесь [уведомления](https://yookassa.ru/developers/using-api/webhooks) от ЮKassa или периодически отправляйте запросы, чтобы получить [информацию о платеже](https://yookassa.ru/developers/api#get_payment).

**Пример успешного платежа**

**JSON**

```json
{
  "id": "255350c9-000f-5000-a000-1f211b3ea0a7",
  "status": "succeeded",
  "paid": true,
  "amount": {
    "value": "2.00",
    "currency": "RUB"
  },
  "authorization_details": {
    "rrn": "603668680243",
    "auth_code": "000000",
    "three_d_secure": {
      "applied": true
    }
  },
  "captured_at": "2018-07-18T17:20:50.825Z",
  "created_at": "2018-07-18T17:18:39.345Z",
  "description": "Заказ №72",
  "metadata": {},
  "payment_method": {
    "type": "bank_card",
    "id": "22e18a2f-000f-5000-a000-1db6312b7767",
    "saved": true,
    "card": {
      "first6": "555555",
      "last4": "4444",
      "expiry_month": "07",
      "expiry_year": "2022",
      "card_type": "Mir",
      "card_product": {
        "code": "MCP",
        "name": "MIR Privilege"
      },
      "issuer_country": "RU",
      "issuer_name": "Sberbank"
    },
    "title": "Bank card *4444"
  },
  "refundable": true,
  "refunded_amount": {
    "value": "0.00",
    "currency": "RUB"
  },
  "recipient": {
    "account_id": "100500",
    "gateway_id": "100700"
  },
  "test": false
}
```

Неуспешные автоплатежи

В процессе автоплатежа что-то может пойти не так: может не хватать денег для списания, пользователь может запретить автоплатежи для привязанного платежного средства, эмитент может быть недоступен. В этом случае платеж будет [отменен](https://yookassa.ru/developers/payment-acceptance/after-the-payment/declined-payments) и перейдет в статус `canceled`. В [объекте платежа](https://yookassa.ru/developers/api#payment_object) вы получите комментарий к отмене платежа (`cancellation_details`).

Например, если пользователь отозвал свое разрешение на повторные списания из кошелька ЮMoney, в объекте `cancellation_details` будет указана причина отмены — `permission_revoked`.

**Пример неуспешного платежа**

**JSON**

```json
{
    "id": "24a40656-000f-5000-9000-134108dd5325",
    "status": "canceled",
    "paid": false,
    "amount": {
        "value": "10.00",
        "currency": "RUB"
    },
    "created_at": "2019-06-25T10:08:22.531Z",
    "metadata": {},
    "payment_method": {
        "type": "yoo_money",
        "id": "249ea698-000f-5000-9000-1200128b882c",
        "saved": true
    },
    "recipient": {
        "account_id": "100500",
        "gateway_id": "100700"
    },
    "refundable": false,
    "test": false,
    "cancellation_details": {
        "party": "yoo_money",
        "reason": "permission_revoked"
    }
}
```

Что почитать еще

[Основы проведения платежей](https://yookassa.ru/developers/payment-acceptance/getting-started/payment-process)

[Тестирование автоплатежей](https://yookassa.ru/developers/payment-acceptance/testing-and-going-live/testing#test-recurrent)

[Неуспешные платежи](https://yookassa.ru/developers/payment-acceptance/after-the-payment/declined-payments)

[Универсальный токен для платежей и выплат](https://yookassa.ru/developers/payouts/scenario-extensions/multipurpose-token)
