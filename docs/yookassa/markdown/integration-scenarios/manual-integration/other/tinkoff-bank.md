<!-- Источник: https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/other/tinkoff-bank -->
<!-- Полная копия статьи официальной документации ЮKassa, сохранено 2026-07-02 -->

# T-Pay

Особенности

- Тип способа оплаты в API: `tinkoff_bank`
- [Сценарий подтверждения](https://yookassa.ru/developers/payment-acceptance/getting-started/payment-process#user-confirmation): Redirect
- [Срок оплаты](https://yookassa.ru/developers/payment-acceptance/getting-started/payment-methods#payment-term): 1 час
- [Холдирование](https://yookassa.ru/developers/payment-acceptance/getting-started/payment-process#capture-and-cancel): 7 дней, доступно полное и частичное списание оплаты
- [Код в реестре](https://yookassa.ru/developers/payment-acceptance/after-the-payment/reports): TB
- [Возврат](https://yookassa.ru/developers/payment-acceptance/after-the-payment/refunds): да, полный и частичный
- Срок возврата: моментально
- [Автоплатежи](https://yookassa.ru/developers/payment-acceptance/scenario-extensions/recurring-payments/basics): да
- [Лимиты](https://yookassa.ru/developers/payment-acceptance/getting-started/payment-methods#payment-limit): минимальный размер платежа — 1 рубль, максимальный — 700 000 рублей (можно увеличить через менеджера)

Сценарии интеграции

Готовые решения:

- [Умный платеж](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/smart-payment)
- [Виджет ЮKassa](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/basics)

Самостоятельная интеграция: [Оплата в приложении Т-Банка](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/other/tinkoff-bank#create-payment)

Оплата в приложении Т-Банка

Как это работает

В этом сценарии вы самостоятельно реализуете выбор способа оплаты. После создания платежа вы перенаправляете пользователя на страницу ЮKassa. На этой странице отобразится QR-код или кнопка для перехода в приложение Т-Банка.

![Пример платежной формы](https://static.yoomoney.ru/docops-static/images/developers-payments-tinkoff-bank-payment-form-redirect-desktop.image.ru.0a9ea0b2.svg)

Пример платежной формы

Для интеграции добавьте на ваш сайт кнопку, по которой пользователь перейдет к оплате. Когда пользователь перейдет по кнопке, получите от ЮKassa ссылку на готовую страницу оплаты и перенаправьте на неё пользователя. Когда пользователь вернется обратно к вам на сайт, запросите у ЮKassa результаты платежа.

Как провести платеж

**Шаг 1**. Когда пользователь выберет T-Pay, [создайте платеж](https://yookassa.ru/developers/api#create_payment): отправьте ЮKassa запрос с данными для аутентификации запроса, ключом идемпотентности и данными для платежа:

- в объекте `amount` передайте сумму, которую нужно списать с пользователя; сумма должна укладываться в [лимиты](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/other/tinkoff-bank#specifics);
- в объекте `payment_method_data` передайте код способа оплаты `tinkoff_bank`;
- в объекте `confirmation` передайте тип `redirect` и адрес страницы на вашей стороне, на которую пользователь вернется после оплаты (в параметре `return_url`);
- в параметре `description` передайте описание платежа, которое пользователь увидит при оплате.

В запросе можно передать любые [другие параметры](https://yookassa.ru/developers/api#create_payment), кроме `payment_method_id`, `payment_token`, `airline`.

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
            "type": "tinkoff_bank"
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
                'type' => 'tinkoff_bank',
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
        "type": "tinkoff_bank"
    },
    "confirmation": {
        "type": "redirect",
        "return_url": "https://www.example.com/return_url"
    },
    "description": "Заказ №72"
})
```

В ответ на запрос вернется [объект платежа](https://yookassa.ru/developers/api#payment_object) в актуальном статусе.

**Шаг 2**. Перенаправьте пользователя на страницу ЮKassa, адрес которой придет в `confirmation_url`. Это ссылка на готовую страницу ЮKassa.

**Пример созданного объекта платежа**

**JSON**

```json
{
  "id": "23ce833e-000f-5000-8000-172b6722debf",
  "status": "pending",
  "paid": false,
  "amount": {
    "value": "2.00",
    "currency": "RUB"
  },
  "confirmation": {
    "type": "redirect",
    "confirmation_url": "https://yoomoney.ru/checkout/payments/v2/contract/tinkoff-pay?orderId=23ce833e-000f-5000-8000-172b6722debf"
  },
  "created_at": "2019-01-14T11:16:14.441Z",
  "description": "Заказ №72",
  "metadata": {},
  "payment_method": {
    "type": "tinkoff_bank",
    "id": "23ce833e-000f-5000-8000-172b6722debf",
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

**Пример платежа в статусе succeeded**

**JSON**

```json
{
  "id": "23ce833e-000f-5000-8000-172b6722debf",
  "status": "succeeded",
  "amount": {
    "value": "2.00",
    "currency": "RUB"
  },
  "income_amount": {
    "value": "1.93",
    "currency": "RUB"
  },
  "description": "Заказ №72",
  "recipient": {
    "account_id": "100500",
    "gateway_id": "100700"
  },
  "payment_method": {
    "type": "tinkoff_bank",
    "id": "23ce833e-000f-5000-8000-172b6722debf",
    "saved": false,
    "card": {
         "first6": "555555",
         "last4": "4444",
         "expiry_year": "2022",
         "expiry_month": "07",
         "card_type": "MasterCard"
     }
  },
  "captured_at": "2023-09-08T09:30:11.721Z",
  "created_at": "2023-09-08T09:29:48.933Z",
  "test": false,
  "refunded_amount": {
    "value": "0.00",
    "currency": "RUB"
  },
  "paid": true,
  "refundable": true,
  "metadata": {},
  "authorization_details": {
     "rrn": "603668680243",
     "auth_code": "000000",
     "three_d_secure": {
       "applied": false
     }
  }
}
```

**Шаг 4.** Когда пользователь вернется на `return_url`, отобразите результат проведения платежа (успех или неудача) в зависимости от [статуса платежа](https://yookassa.ru/developers/payment-acceptance/getting-started/payment-process#lifecycle).

Готово! Если вы проводите [платеж в две стадии](https://yookassa.ru/developers/payment-acceptance/getting-started/payment-process#capture-and-cancel), подтвердите списание оплаты или отмените платеж. Сообщите пользователю финальный результат платежа.

Что почитать еще

[Основы проведения платежей](https://yookassa.ru/developers/payment-acceptance/getting-started/payment-process)

[Неуспешные платежи](https://yookassa.ru/developers/payment-acceptance/after-the-payment/declined-payments)

[Отправка чеков в налоговую](https://yookassa.ru/developers/payment-acceptance/receipts/basics)
