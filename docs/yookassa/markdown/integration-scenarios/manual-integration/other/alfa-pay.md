<!-- Источник: https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/other/alfa-pay -->
<!-- Полная копия статьи официальной документации ЮKassa, сохранено 2026-07-02 -->

# Alfa Pay

Этот способ оплаты доступен, только если:

- Вы используете [обычные платежи](https://yookassa.ru/developers/payment-acceptance/overview) или [партнерскую программу](https://yookassa.ru/developers/solutions-for-platforms/partners-api/basics).
- Вы компания или ИП.

Особенности

- Тип способа оплаты в API: `alfa_pay`
- [Сценарий подтверждения](https://yookassa.ru/developers/payment-acceptance/getting-started/payment-process#user-confirmation): Redirect
- [Срок оплаты](https://yookassa.ru/developers/payment-acceptance/getting-started/payment-methods#payment-term): 1 час
- [Холдирование](https://yookassa.ru/developers/payment-acceptance/getting-started/payment-process#capture-and-cancel): нельзя платить в две стадии
- [Код в реестре](https://yookassa.ru/developers/payment-acceptance/after-the-payment/reports): AP
- [Возврат](https://yookassa.ru/developers/payment-acceptance/after-the-payment/refunds): да, полный и частичный, есть [особенности](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/other/alfa-pay#refunds)
- Срок возврата: моментально
- [Автоплатежи](https://yookassa.ru/developers/payment-acceptance/scenario-extensions/recurring-payments/basics): нет
- [Лимиты](https://yookassa.ru/developers/payment-acceptance/getting-started/payment-methods#payment-limit): минимальный размер платежа — 1 рубль, максимальный — 700 000 рублей (можно увеличить через менеджера)

Сценарии интеграции

Готовые решения: [Умный платеж](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/smart-payment)

Самостоятельная интеграция: [Оплата в приложении Альфа Банка](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/other/alfa-pay#create-payment)

Оплата в приложении Альфа Банка

Как это работает

В этом сценарии вы самостоятельно реализуете выбор способа оплаты. После создания платежа вы перенаправляете пользователя в Альфа Банк через промежуточную страницу ЮKassa. На промежуточной странице пользователь не выполняет никаких действий — это техническая страница, на которую пользователь попадает на доли секунды.

![Пример промежуточной страницы](https://static.yoomoney.ru/docops-static/images/yookassa/developers/payments/forms/payment-form-manual-integration-alfa-pay-redirect.image.4b80ac48.png)

Пример промежуточной страницы

Затем ЮKassa автоматически перенаправляет пользователя в приложение Альфа Банка, где он выбирает карту и подтверждает платеж. Если пользователь оплачивает покупку с десктопа, ЮKassa перенаправляет его на сайт Альфа Банка, где пользователь может отсканировать QR-код и перейти в приложение Альфа Банка для подтверждения платежа.

Если оплата не прошла, например, не хватило денег, пользователь вернется на страницу ЮKassa. На этой странице ЮKassa отобразит пользователю сообщение об ошибке и предложит попробовать оплатить еще раз.

Для интеграции добавьте на ваш сайт кнопку, по которой можно перейти к оплате. Когда пользователь перейдет по кнопке, получите от ЮKassa ссылку на готовую страницу оплаты и перенаправьте на неё пользователя. Когда пользователь вернется обратно к вам на сайт, запросите у ЮKassa результаты платежа и отобразите их.

Как провести платеж

**Шаг 1**. Когда пользователь выберет Alfa Pay, [создайте платеж](https://yookassa.ru/developers/api#create_payment): отправьте ЮKassa запрос с данными для аутентификации запроса, ключом идемпотентности и данными для платежа:

- в объекте `amount` передайте сумму, которую нужно списать с пользователя; сумма должна укладываться в [лимиты](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/other/alfa-pay#specifics);
- в объекте `payment_method_data` передайте код способа оплаты `alfa_pay`;
- в объекте `confirmation` передайте тип `redirect` и адрес страницы на вашей стороне, на которую пользователь вернется после оплаты (в параметре `return_url`);
- в параметре `description` передайте описание платежа, которое пользователь увидит при оплате.

В запросе можно передать любые [другие параметры](https://yookassa.ru/developers/api#create_payment), кроме `save_payment_method`, `payment_method_id`, `payment_token`, `airline`, `transfers`, `deal`.

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
            "type": "alfa_pay"
          },
          "confirmation": {
            "type": "redirect",
            "return_url": "https://www.example.com/return_url"
          },
          "description": "Заказ №37"
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
                'type' => 'alfa_pay',
            ),
            'confirmation' => array(
                'type' => 'redirect',
                'return_url' => 'https://www.example.com/return_url',
            ),
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
    "payment_method_data": {
        "type": "alfa_pay"
    },
    "confirmation": {
        "type": "redirect",
        "return_url": "https://www.example.com/return_url"
    },
    "description": "Заказ №37"
})
```

В ответ на запрос вернется [объект платежа](https://yookassa.ru/developers/api#payment_object) в актуальном статусе.

**Шаг 2**. Перенаправьте пользователя на страницу ЮKassa, адрес которой придет в `confirmation_url`. С этой страницы ЮKassa самостоятельно перенаправит пользователя в Альфа Банк для завершения оплаты.

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
    "confirmation_url": "https://yoomoney.ru/checkout/payments/v2/contract??orderId=22e12f66-000f-5000-8000-18db351245c7"
  },
  "created_at": "2026-01-14T11:16:14.441Z",
  "description": "Заказ №37",
  "metadata": {},
  "payment_method": {
    "type": "alfa_pay",
    "id": "23ce833e-000f-5000-8000-172b6722debf",
    "saved": false,
    "status": "inactive"
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
  "description": "Заказ №37",
  "recipient": {
    "account_id": "100500",
    "gateway_id": "100700"
  },
  "payment_method": {
    "type": "alfa_pay",
    "id": "23ce833e-000f-5000-8000-172b6722debf",
    "saved": false,
    "status": "inactive",
    "card": {
         "first6": "555555",
         "last4": "4444",
         "expiry_year": "2030",
         "expiry_month": "07",
         "card_type": "MasterCard"
     }
  },
  "captured_at": "2026-01-14T11:18:10.365Z",
  "created_at": "2026-01-14T11:16:14.441Z",
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

Готово!

Особенности возвратов платежей

Возврат платежа [стандартный](https://yookassa.ru/developers/payment-acceptance/after-the-payment/refunds). Срок возврата — от 0 до 3 рабочих дней.

Вернуть можно только те платежи, которые перешли в статус `succeeded`. С момента создания платежа должно пройти не больше 500 дней.

Что почитать еще

[Основы проведения платежей](https://yookassa.ru/developers/payment-acceptance/getting-started/payment-process)

[Неуспешные платежи](https://yookassa.ru/developers/payment-acceptance/after-the-payment/declined-payments)

[Отправка чеков в налоговую](https://yookassa.ru/developers/payment-acceptance/receipts/basics)
