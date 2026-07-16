<!-- Источник: https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/yoo-money -->
<!-- Полная копия статьи официальной документации ЮKassa, сохранено 2026-07-02 -->

# ЮMoney

Особенности

- Тип способа оплаты в API: `yoo_money`
- [Сценарий подтверждения](https://yookassa.ru/developers/payment-acceptance/getting-started/payment-process#user-confirmation): Redirect
- [Срок оплаты](https://yookassa.ru/developers/payment-acceptance/getting-started/payment-methods#payment-term): 1 час
- [Холдирование](https://yookassa.ru/developers/payment-acceptance/getting-started/payment-process#capture-and-cancel): 7 дней, доступно полное и частичное списание оплаты, есть [особенности](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/yoo-money#two-stage-payments)
- [Код в реестре](https://yookassa.ru/developers/payment-acceptance/after-the-payment/reports): PC
- [Возврат](https://yookassa.ru/developers/payment-acceptance/after-the-payment/refunds): да, полный и частичный
- Срок возврата: моментально
- [Автоплатежи](https://yookassa.ru/developers/payment-acceptance/scenario-extensions/recurring-payments/basics): да
- [Лимиты](https://yookassa.ru/developers/payment-acceptance/getting-started/payment-methods#payment-limit): минимальный размер платежа — 1 рубль, максимальный — от 15 000 до 250 000 рублей (зависит от статуса кошелька), есть [дополнительные ограничения](https://yookassa.ru/docs/support/payments/limits)

Сценарии интеграции

Готовые решения:

- [Умный платеж](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/smart-payment)
- [Виджет ЮKassa](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/basics)
- [Мобильные SDK](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/mobile-sdks/basics) для iOS и Android

Самостоятельная интеграция: [Оплата на странице ЮMoney](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/yoo-money#create-payment)

Оплата с подтверждением на странице ЮMoney

**Шаг 1**. [Создайте платеж](https://yookassa.ru/developers/api#create_payment), в объекте `payment_method_data` передайте тип `yoo_money`, а в объекте `confirmation` передайте тип `redirect` и адрес страницы на вашей стороне, на которую пользователь вернется после оплаты (в параметре `return_url`).

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
          "type": "yoo_money"
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
                'type' => 'yoo_money',
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
        "type": "yoo_money"
    },
    "confirmation": {
        "type": "redirect",
        "return_url": "https://www.example.com/return_url"
    },
    "description": "Заказ №72"
})
```

**Шаг 2**. Перенаправьте пользователя на страницу ЮKassa (ссылка на нее придет в параметре `confirmation_url`). На этой странице пользователь введет данные кошелька и подтвердит платеж.

**Пример созданного объекта платежа**

**JSON**

```json
{
  "id": "22c5d0f0-000f-5000-8000-13ece77bc6c1",
  "status": "pending",
  "paid": false,
  "amount": {
    "value": "2.00",
    "currency": "RUB"
  },
  "confirmation": {
    "type": "redirect",
    "confirmation_url": "https://yoomoney.ru/payments/internal/confirmation?orderId=22c5d0f0-000f-5000-8000-13ece77bc6c1"
  },
  "created_at": "2018-06-27T16:37:04.513Z",
  "description": "Заказ №72",
  "metadata": {},
  "payment_method": {
    "type": "yoo_money",
    "id": "22c5d0f0-000f-5000-8000-13ece77bc6c1",
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

Если оплата из кошелька или привязанной к кошельку картой не прошла (например, не хватило денег), ЮKassa отобразит пользователю сообщение об ошибке и предложит попробовать оплатить еще раз.

**Шаг 3**. Дождитесь успешного завершения платежа: подождите, когда придет [уведомление](https://yookassa.ru/developers/using-api/webhooks) от ЮKassa, или периодически отправляйте запросы, чтобы получить [информацию о платеже](https://yookassa.ru/developers/api#get_payment).

Особенности проведения платежей в две стадии

Для [двухстадийных](https://yookassa.ru/developers/payment-acceptance/getting-started/payment-process#capture-and-cancel) платежей из кошелька ЮMoney доступно полное и частичное списание оплаты. Есть исключение: при [повторном платеже (рекурренте)](https://yookassa.ru/developers/payment-acceptance/scenario-extensions/recurring-payments/pay-with-saved) вы можете списать оплату только полностью.

Особые требования

При [пополнении электронных кошельков, банковских счетов и баланса телефонов](https://yookassa.ru/developers/payment-acceptance/scenario-extensions/top-up-phones-balance) нужно добавить к запросу реквизиты получателя оплаты.

Что почитать еще

[Основы проведения платежей](https://yookassa.ru/developers/payment-acceptance/getting-started/payment-process)

[Неуспешные платежи](https://yookassa.ru/developers/payment-acceptance/after-the-payment/declined-payments)

[Отправка чеков в налоговую](https://yookassa.ru/developers/payment-acceptance/receipts/basics)

[Тестирование платежей](https://yookassa.ru/developers/payment-acceptance/testing-and-going-live/testing)
