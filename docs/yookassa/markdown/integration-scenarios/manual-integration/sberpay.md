<!-- Источник: https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/sberpay -->
<!-- Полная копия статьи официальной документации ЮKassa, сохранено 2026-07-02 -->

# SberPay

Особенности

- Тип способа оплаты в API: `sberbank`
- [Сценарий подтверждения](https://yookassa.ru/developers/payment-acceptance/getting-started/payment-process#user-confirmation): Redirect, External, Mobile application и QR-код
- [Срок оплаты](https://yookassa.ru/developers/payment-acceptance/getting-started/payment-methods#payment-term): 1 час
- [Холдирование](https://yookassa.ru/developers/payment-acceptance/getting-started/payment-process#capture-and-cancel): 7 дней, доступно полное и частичное списание оплаты
- [Код в реестре](https://yookassa.ru/developers/payment-acceptance/after-the-payment/reports): SB
- [Возврат](https://yookassa.ru/developers/payment-acceptance/after-the-payment/refunds): да, частичный и полный
- Срок возврата: моментально
- [Автоплатежи](https://yookassa.ru/developers/payment-acceptance/scenario-extensions/recurring-payments/basics): да
- [Лимиты](https://yookassa.ru/developers/payment-acceptance/getting-started/payment-methods#payment-limit): минимальный размер платежа — 1 рубль, максимальный — 700 000 рублей (можно увеличить через менеджера), есть [дополнительные ограничения](https://yookassa.ru/docs/support/payments/limits)

Сценарии интеграции

Готовые решения:

- [Умный платеж](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/smart-payment)
- [Виджет ЮKassa](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/basics)
- [Мобильные SDK](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/mobile-sdks/basics) для iOS и Android

Самостоятельная интеграция:

- [Оплата с перенаправлением на страницу ЮKassa](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/sberpay#create-payment-redirect)
- [Оплата с подтверждением через пуш-уведомление или смс](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/sberpay#create-payment-external)
- [Оплата с перенаправлением в приложение банка (для мобильных устройств)](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/sberpay#create-payment-mobile-application)
- [Оплата с перенаправлением в приложение банка (для десктопа)](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/sberpay#create-payment-qr)

Оплата с перенаправлением на страницу ЮKassa

В этом сценарии после создания платежа вы перенаправляете пользователя на страницу ЮKassa. На этой странице пользователь сканирует QR-код для перехода в мобильное приложение банка или вводит номер телефона, привязанный к СберБанку Онлайн, для получения пуша или смс.

**Шаг 1**. [Создайте платеж](https://yookassa.ru/developers/api#create_payment), в объекте `payment_method_data` передайте тип `sberbank`, а в объекте `confirmation` передайте тип `redirect` и адрес страницы на вашей стороне, на которую пользователь вернется после оплаты (в параметре `return_url`).

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
          "type": "sberbank"
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
                'type' => 'sberbank',
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
        "type": "sberbank"
    },
    "confirmation": {
        "type": "redirect",
        "return_url": "https://www.example.com/return_url"
    },
    "description": "Заказ №72"
})
```

**Шаг 2**. Перенаправьте пользователя на страницу ЮKassa (ссылка на нее придет в параметре `confirmation_url`). На этой странице пользователь введет данные карты и подтвердит платеж.

**Пример созданного объекта платежа**

**JSON**

```json
{
   "id":"22e12f66-000f-5000-8000-18db351245c7",
   "status":"pending",
   "paid":false,
   "amount":{
      "value":"2.00",
      "currency":"RUB"
   },
   "confirmation":{
      "type":"redirect",
      "confirmation_url":"https://yoomoney.ru/api-pages/v2/payment-confirm/epl?orderId=23d93cac-000f-5000-8000-126628f15141"
   },
   "created_at":"2018-07-18T10:51:18.139Z",
   "description":"Заказ №72",
   "metadata":{
      "order_id":"72"
   },
   "recipient":{
      "account_id":"100500",
      "gateway_id":"100700"
   },
   "refundable":false,
   "test":false
}
```

Если оплата через SberPay не прошла (например, не хватило денег), ЮKassa отобразит пользователю сообщение об ошибке и предложит попробовать оплатить еще раз.

**Шаг 3**. Дождитесь успешного завершения платежа: подождите, когда придет [уведомление](https://yookassa.ru/developers/using-api/webhooks) от ЮKassa, или периодически отправляйте запросы, чтобы получить [информацию о платеже](https://yookassa.ru/developers/api#get_payment).

**Пример успешного платежа**

**JSON**

```json
{
   "id":"22e12f66-000f-5000-8000-18db351245c7",
   "status":"succeeded",
   "paid":true,
   "amount":{
      "value":"2.00",
      "currency":"RUB"
   },
   "captured_at":"2021-04-13T09:27:09.960Z",
   "created_at":"2021-04-13T09:25:13.087Z",
   "description":"Заказ №72",
   "income_amount":{
      "value":"2.00",
      "currency":"RUB"
   },
   "payment_method":{
      "type":"sberbank",
      "id":"22e12f66-000f-5000-8000-18db351245c7",
      "saved":false,
      "card":{
         "first6":"555555",
         "last4":"4444",
         "expiry_year":"2022",
         "expiry_month":"07",
         "card_type":"MasterCard"
         }
   },
   "recipient":{
      "account_id":"100500",
      "gateway_id":"100700"
   },
   "refundable":true,
   "refunded_amount":{
      "value":"0.00",
      "currency":"RUB"
   },
   "test":false,
   "authorization_details":{
     "rrn":"10000000000",
     "auth_code":"000000",
     "three_d_secure":{
       "applied":false
     }
   }
}
```

**Шаг 4**. Когда пользователь вернется на `return_url`, отобразите результат проведения платежа (успех или неудача) в зависимости от [статуса платежа](https://yookassa.ru/developers/payment-acceptance/getting-started/payment-process#lifecycle).

Оплата с подтверждением через пуш-уведомление или смс

В этом сценарии вы запрашиваете у пользователя номер телефона, который привязан к СберБанку Онлайн, и сообщаете пользователю, что на этот номер поступит пуш-уведомление или смс. Пользователь переходит по пуш-уведомлению или отвечает на смс для подтверждения платежа.

**Шаг 1**. [Создайте платеж](https://yookassa.ru/developers/api#create_payment), в объекте `payment_method_data` передайте тип `sberbank` и телефон пользователя, привязанный к СберБанку Онлайн, а в объекте `confirmation` передайте тип `external`.

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
          "type": "sberbank",
          "phone": "79000000000"
        },
        "confirmation": {
          "type": "external",
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
                'type' => 'sberbank',
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
        "type": "sberbank",
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
   "id":"22e12f66-000f-5000-8000-18db351245c7",
   "status":"pending",
   "paid":false,
   "amount":{
      "value":"2.00",
      "currency":"RUB"
   },
      "confirmation":{
      "type":"external"
   },
   "created_at":"2018-07-18T10:51:18.139Z",
   "description":"Заказ №72",
   "metadata":{
      "order_id":"72"
   },
   "payment_method":{
      "type":"sberbank",
      "phone":"79000000000"
   },
   "recipient":{
      "account_id":"100500",
      "gateway_id":"100700"
   },
   "refundable":false,
   "test":false
}
```

**Шаг 2**. Сообщите пользователю, что ему необходимо подтвердить оплату.

**Шаг 3**. Дождитесь успешного завершения платежа: подождите, когда придет [уведомление](https://yookassa.ru/developers/using-api/webhooks) от ЮKassa, или периодически отправляйте запросы, чтобы получить [информацию о платеже](https://yookassa.ru/developers/api#get_payment).

**Пример успешного платежа**

**JSON**

```json
{
   "id":"22e12f66-000f-5000-8000-18db351245c7",
   "status":"succeeded",
   "paid":true,
   "amount":{
      "value":"2.00",
      "currency":"RUB"
   },
   "captured_at":"2021-04-13T09:27:09.960Z",
   "created_at":"2021-04-13T09:25:13.087Z",
   "description":"Заказ №72",
   "income_amount":{
      "value":"2.00",
      "currency":"RUB"
   },
   "payment_method":{
      "type":"sberbank",
      "id":"22e12f66-000f-5000-8000-18db351245c7",
      "saved":false,
      "card":{
         "first6":"555555",
         "last4":"4444",
         "expiry_year":"2022",
         "expiry_month":"07",
         "card_type":"MasterCard"
         }
   },
   "recipient":{
      "account_id":"100500",
      "gateway_id":"100700"
   },
   "refundable":true,
   "refunded_amount":{
      "value":"0.00",
      "currency":"RUB"
   },
   "test":false,
   "authorization_details":{
     "rrn":"10000000000",
     "auth_code":"000000",
     "three_d_secure":{
       "applied":false
     }
   }
}
```

**Шаг 4**. Отобразите пользователю результат проведения платежа (успех или неудача) в зависимости от [статуса платежа](https://yookassa.ru/developers/payment-acceptance/getting-started/payment-process#lifecycle).

Оплата с перенаправлением в приложение банка (для мобильных устройств)

Только для приема платежей на мобильных устройствах (из мобильного приложения или с мобильной версии сайта).

По этому сценарию после создания платежа вы перенаправляете пользователя по диплинку в мобильное приложение СберБанка. В этом приложении пользователь подтверждает платеж.

**Шаг 1**. [Создайте платеж](https://yookassa.ru/developers/api#create_payment), в объекте `payment_method_data` передайте тип `sberbank`, в объекте `confirmation` передайте тип `mobile_application`, а в параметре `return_url` — диплинк в ваше приложение (при платеже из мобильного приложения) или ссылку на страницу вашего магазина (при платеже из мобильной версии сайта). Максимальная длина для `return_url` — 255 символов.

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
          "type": "sberbank"
        },
        "confirmation": {
          "type": "mobile_application",
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
                'type' => 'sberbank',
            ),
            'confirmation' => array(
                'type' => 'mobile_application',
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
        "type": "sberbank"
    },
    "confirmation": {
        "type": "mobile_application",
        "return_url": "https://www.example.com/return_url"
    },
    "description": "Заказ №72"
})
```

**Пример созданного объекта платежа**

**JSON**

```json
{
   "id":"22e12f66-000f-5000-8000-18db351245c7",
   "status":"pending",
   "paid":false,
   "amount":{
      "value":"2.00",
      "currency":"RUB"
   },
   "payment_method":{
      "type":"sberbank"
   },
   "confirmation":{
      "type":"mobile_application",
      "confirmation_url":"sberpay://invoicing/v2?bankInvoiceId=5eae1999faf15d5e49ee5bd7333ac5a5&operationType=App2App&payment_id=22e12f66-000f-5000-8000-18db351245c7"
   },
   "created_at":"2018-07-18T10:51:18.139Z",
   "description":"Заказ №72",
   "metadata":{
      "order_id":"72"
   },
   "recipient":{
      "account_id":"100500",
      "gateway_id":"100700"
   },
   "refundable":false,
   "test":false
}
```

**Шаг 2**. Перенаправьте пользователя в мобильное приложение СберБанк Онлайн, используя диплинк, который вернется в параметре `confirmation_url`. Пользователь авторизуется в приложении и сразу перейдет к оплате.

[Подробнее о перенаправлении в приложение банка при оплате с мобильного устройства](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/sberpay#deeplink-bankapp)

**Шаг 3**. Дождитесь успешного завершения платежа: подождите, когда придет [уведомление](https://yookassa.ru/developers/using-api/webhooks) от ЮKassa, или периодически отправляйте запросы, чтобы получить [информацию о платеже](https://yookassa.ru/developers/api#get_payment).

**Пример успешного платежа**

**JSON**

```json
{
   "id":"22e12f66-000f-5000-8000-18db351245c7",
   "status":"succeeded",
   "paid":true,
   "amount":{
      "value":"2.00",
      "currency":"RUB"
   },
   "captured_at":"2021-04-13T09:27:09.960Z",
   "created_at":"2021-04-13T09:25:13.087Z",
   "description":"Заказ №72",
   "income_amount":{
      "value":"2.00",
      "currency":"RUB"
   },
   "payment_method":{
      "type":"sberbank",
      "id":"22e12f66-000f-5000-8000-18db351245c7",
      "saved":false,
      "card":{
         "first6":"555555",
         "last4":"4444",
         "expiry_year":"2022",
         "expiry_month":"07",
         "card_type":"MasterCard"
         }
   },
   "recipient":{
      "account_id":"100500",
      "gateway_id":"100700"
   },
   "refundable":true,
   "refunded_amount":{
      "value":"0.00",
      "currency":"RUB"
   },
   "test":false,
   "authorization_details":{
     "rrn":"10000000000",
     "auth_code":"000000",
     "three_d_secure":{
       "applied":false
     }
   }
}
```

**Шаг 4**. Когда пользователь вернется на `return_url`, отобразите результат проведения платежа (успех или неудача) в зависимости от [статуса платежа](https://yookassa.ru/developers/payment-acceptance/getting-started/payment-process#lifecycle).

Оплата с перенаправлением в приложение банка (для десктопа)

Рекомендуется использовать только для полной версии сайта, а для мобильной использовать [сценарий Mobile application](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/sberpay#create-payment-mobile-application).

В этом сценарии ваши действия различаются в зависимости от того, из какой версии вашего сайта пользователь проводит платеж:

- При оплате из полной версии сайта вы генерируете QR-код, который сканирует пользователь в приложении СберБанка.
- При оплате из мобильной версии вы перенаправляете пользователя по диплинку в мобильное приложение СберБанка.

В приложении СберБанка пользователь подтверждает платеж и видит, как прошла оплата (успех или неудача).

**Шаг 1**. [Создайте платеж](https://yookassa.ru/developers/api#create_payment), в объекте `payment_method_data` передайте тип `sberbank`, в объекте `confirmation` — тип `qr`.

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
          "type": "sberbank"
        },
        "confirmation": {
          "type": "qr"
        },
        "description": "Заказ №72"
      }'
```

**PHP**

```php
<?php
    $idempotenceKey = uniqid('', true);
    $response = $client->createPayment(
        array(
            'amount' => array(
                'value' => '2.00',
                'currency' => 'RUB',
            ),
            'payment_method_data' => array(
                'type' => 'sberbank',
            ),
            'confirmation' => array(
                'type' => 'qr',
            ),
            'description' => 'Заказ №72',
        ),
        $idempotenceKey
    );
    
    //get confirmation url
    $confirmationUrl = $response->getConfirmation()->getConfirmationUrl();
?>
```

**Python**

```python
from yookassa import Payment
import uuid

idempotence_key = str(uuid.uuid4())
payment = Payment.create({
    "amount": {
        "value": "2.00",
        "currency": "RUB"
    },
    "payment_method_data": {
        "type": "sberbank"
    },
    "confirmation": {
        "type": "qr"
    },
    "description": "Заказ №72",
}, idempotence_key)

# get confirmation url
confirmation_url = payment.confirmation.confirmation_url
```

**Шаг 2**. В параметре `confirmation_data` ЮKassa передаст URL. Сгенерируйте QR-код с помощью любого доступного инструмента и отобразите его пользователю. В мобильной версии сайта перенаправьте пользователя по этому URL (например, при нажатии на кнопку **Оплатить**) и сообщите, что после оплаты ему необходимо вернуться на страницу вашего магазина.

[Подробнее о перенаправлении в приложение банка при оплате с мобильного устройства](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/sberpay#deeplink-bankapp)

**Пример созданного объекта платежа**

**JSON**

```json
{
   "id":"22e12f66-000f-5000-8000-18db351245c7",
   "status":"pending",
   "paid":false,
   "amount":{
      "value":"2.00",
      "currency":"RUB"
   },
      "confirmation":{
      "type":"qr",
      "confirmation_data": "sberpay://invoicing/v2?bankInvoiceId=successPaymentInApp2433394341762973&operationType=Web2App"
   },
   "created_at":"2021-04-12T13:03:20.155Z",
   "description":"Заказ №72",
   "metadata":{
      "order_id":"72"
   },
   "payment_method":{
      "type":"sberbank",
      "id": "22e12f66-000f-5000-8000-18db351245c7",
      "saved": false
   },
   "recipient":{
      "account_id":"100500",
      "gateway_id":"100700"
   },
   "refundable":false,
   "test":false
}
```

**Шаг 3**. Дождитесь успешного завершения платежа: подождите, когда придет [уведомление от ЮKassa](https://yookassa.ru/developers/using-api/webhooks), или периодически отправляйте запросы, чтобы [получить информацию о платеже](https://yookassa.ru/developers/api#get_payment).

**Пример успешного платежа**

**JSON**

```json
{
   "id":"22e12f66-000f-5000-8000-18db351245c7",
   "status":"succeeded",
   "paid":true,
   "amount":{
      "value":"2.00",
      "currency":"RUB"
   },
   "captured_at":"2021-04-13T09:27:09.960Z",
   "created_at":"2021-04-13T09:25:13.087Z",
   "description":"Заказ №72",
   "income_amount":{
      "value":"2.00",
      "currency":"RUB"
   },
   "payment_method":{
      "type":"sberbank",
      "id":"22e12f66-000f-5000-8000-18db351245c7",
      "saved":false,
      "card":{
         "first6":"555555",
         "last4":"4444",
         "expiry_year":"2022",
         "expiry_month":"07",
         "card_type":"MasterCard"
         }
   },
   "recipient":{
      "account_id":"100500",
      "gateway_id":"100700"
   },
   "refundable":true,
   "refunded_amount":{
      "value":"0.00",
      "currency":"RUB"
   },
   "test":false,
   "authorization_details":{
     "rrn":"10000000000",
     "auth_code":"000000",
     "three_d_secure":{
       "applied":false
     }
   }
}
```

**Шаг 4**. Отобразите пользователю результат проведения платежа (успех или неудача) в зависимости от [статуса платежа](https://yookassa.ru/developers/payment-acceptance/getting-started/payment-process#lifecycle).

Особенности перенаправления пользователя в приложение банка

Для тех, кто принимает платежи в своем мобильном приложении на iOS и Android и использует сценарии с перенаправлением в приложение банка.

ЮKassa в сценариях с перенаправлением в приложение банка возвращает в объекте платежа диплинк. По этому диплинку вам нужно перенаправить пользователя в приложение банка для подтверждения оплаты.

У СберБанка есть несколько приложений:

| Приложение | Схема | Операционная система |
| --- | --- | --- |
| Финансы Онлайн | `onlineios-app://sbolpay` | iOS |
| Семейный Онлайн | `startonline://sbolpay` | iOS |
| Активы Онлайн | `onlineappmobile://sbolpay` | iOS |
| Бюджет Онлайн | `budgetonline-ios://sbolpay` | iOS |
| Учет Онлайн | `btripsexpenses://sbolpay` | iOS |
| Умный Онлайн | `ios-app-smartonline://sbolpay` | iOS |
| СберБанк Онлайн | `sberpay` | Android, iOS |

Для Android приложение одно, подтверждение платежа проходит в нём.

Для iOS приложений несколько. Для подтверждения платежа подойдет любое, но в какое из них нужно перенаправить пользователя, заранее неизвестно.

Чтобы пользователь точно смог попасть в приложение банка и подтвердить оплату, вам нужно доработать ваше приложение. Для этого воспользуйтесь инструкциями:

- [Доработка приложения на iOS](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/sberpay#deeplink-app-ios)
- [Доработка приложения на Android](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/sberpay#deeplink-app-android)

Доработка приложения на iOS

Вам нужно подключить [возможность запуска приложений банка](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/sberpay#deeplink-redirects) из вашего приложения и настроить [перенаправление пользователя сразу в несколько банковских приложений](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/sberpay#deeplink-sbol-sberpay) для подтверждения платежа.

Настройка запуска банковских приложений

**Шаг 1**. Настройте обработку всех редиректов в приложения СберБанка:

| Приложение | Схема |
| --- | --- |
| Финансы Онлайн | `onlineios-app://sbolpay` |
| Семейный Онлайн | `startonline://sbolpay` |
| Активы Онлайн | `onlineappmobile://sbolpay` |
| Бюджет Онлайн | `budgetonline-ios://sbolpay` |
| Учет Онлайн | `btripsexpenses://sbolpay` |
| Умный Онлайн | `ios-app-smartonline://sbolpay` |
| СберБанк Онлайн | `sberpay` |

Редиректы по этим схемам нужно обрабатывать через системный API.

**Пример обработки редиректов**

**Swift**

```swift
func webView(
            _ webView: WKWebView,
            decidePolicyFor navigationAction: WKNavigationAction,
            preferences: WKWebpagePreferences,
            decisionHandler: @escaping (WKNavigationActionPolicy, WKWebpagePreferences) -> Void
        ) {
            if let url = navigationAction.request.url,
               let host = url.scheme,
               host.hasPrefix("onlineios-app://sbolpay") || host.hasPrefix("startonline://sbolpay") || host.hasPrefix("onlineappmobile://sbolpay") || host.hasPrefix("budgetonline-ios://sbolpay") || host.hasPrefix("btripsexpenses://sbolpay") || host.hasPrefix("ios-app-smartonline://sbolpay") || host.hasPrefix("sberpay") {
                if UIApplication.shared.canOpenURL(url) {
                    UIApplication.shared.open(url)
                }
                decisionHandler(.cancel, preferences)
            } else {
                decisionHandler(.allow, preferences)
            }
        }
```

**Шаг 2**. Добавьте в конфигурационный файл `Info.plist` схемы из [таблицы](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/sberpay#deeplink-redirects), чтобы ваше приложение могло запускать приложения СберБанка:

**Пример файла Info.plist**

**XML**

```xml
<key>LSApplicationQueriesSchemes</key>
<array>
  <string>onlineios-app://sbolpay</string>
  <string>startonline://sbolpay</string>
  <string>onlineappmobile://sbolpay</string>
  <string>budgetonline-ios://sbolpay</string>
  <string>btripsexpenses://sbolpay</string>
  <string>ios-app-smartonline://sbolpay</string>
  <string>sberpay</string>
</array>
```

Перенаправление пользователя в несколько банковских приложений

В приложении на iOS перенаправляйте пользователя во все приложения по очереди. Это можно сделать следующим образом:

**Шаг 1**. Из [объекта платежа](https://yookassa.ru/developers/api#payment_object), который вернет ЮKassa, получите диплинк в приложение СберБанк Онлайн. Схема этого диплинка — `sberpay`.

**Пример диплинка в приложение СберБанк Онлайн**

```none
sberpay://invoicing/v2?bankInvoiceId=5eae1999faf15d5e49ee5bd7333ac5a5&operationType=App2App&payment_id=22e12f66-000f-5000-8000-18db351245c7
```

**Шаг 2**. Сформируйте новый диплинк в приложение Финансы Онлайн: измените схему на `onlineios-app://sbolpay`.

**Пример диплинка в приложение Финансы Онлайн**

```none
onlineios-app://sbolpay//invoicing/v2?bankInvoiceId=5eae1999faf15d5e49ee5bd7333ac5a5&operationType=App2App&payment_id=22e12f66-000f-5000-8000-18db351245c7
```

**Шаг 3.** Сформируйте новый диплинк в приложение Семейный Онлайн: измените схему на `startonline://sbolpay`.

**Пример диплинка в приложение Семейный Онлайн**

```none
startonline://sbolpay//invoicing/v2?bankInvoiceId=5eae1999faf15d5e49ee5bd7333ac5a5&operationType=App2App&payment_id=22e12f66-000f-5000-8000-18db351245c7
```

**Шаг 4**. Сформируйте новый диплинк в приложение Активы Онлайн: измените схему на `onlineappmobile://sbolpay`.

**Пример диплинка в приложение Активы Онлайн**

```none
onlineappmobile://sbolpay//invoicing/v2?bankInvoiceId=5eae1999faf15d5e49ee5bd7333ac5a5&operationType=App2App&payment_id=22e12f66-000f-5000-8000-18db351245c7
```

**Шаг 5**. Сформируйте новый диплинк в приложение Бюджет Онлайн: измените схему на `budgetonline-ios://sbolpay`.

**Пример диплинка в приложение Бюджет Онлайн**

```none
budgetonline-ios://sbolpay//invoicing/v2?bankInvoiceId=5eae1999faf15d5e49ee5bd7333ac5a5&operationType=App2App&payment_id=22e12f66-000f-5000-8000-18db351245c7
```

**Шаг 6**. Сформируйте новый диплинк в приложение Учет Онлайн: измените схему на `btripsexpenses://sbolpay`.

**Пример диплинка в приложение Учет Онлайн**

```none
btripsexpenses://sbolpay//invoicing/v2?bankInvoiceId=5eae1999faf15d5e49ee5bd7333ac5a5&operationType=App2App&payment_id=22e12f66-000f-5000-8000-18db351245c7
```

**Шаг 7**. Сформируйте новый диплинк для приложения Умный Онлайн: измените схему на `ios-app-smartonline://sbolpay`.

**Пример диплинка в приложение Умный Онлайн**

```none
ios-app-smartonline://sbolpay//invoicing/v2?bankInvoiceId=5eae1999faf15d5e49ee5bd7333ac5a5&operationType=App2App&payment_id=22e12f66-000f-5000-8000-18db351245c7
```

**Шаг 8**. Последовательно перенаправьте пользователя по сформированным диплинкам. Очередность следующая:

1. Финансы Онлайн (схема `onlineios-app://sbolpay`)
2. Семейный Онлайн (схема `startonline://sbolpay`)
3. Активы Онлайн (схема `onlineappmobile://sbolpay`)
4. Бюджет Онлайн (схема `budgetonline-ios://sbolpay`)
5. Учет Онлайн (схема `btripsexpenses://sbolpay`)
6. Умный Онлайн (схема `ios-app-smartonline://sbolpay`)
7. СберБанк Онлайн (схема `sberpay`)

Если на устройстве пользователя установлено несколько приложений для доступа к мобильному банку, то откроется одно из них.

Доработка приложения на Android

Вам нужно настроить обработку редиректов для подтверждения платежа в приложения СберБанк Онлайн. Для этого переопределите метод `shouldOverrideUrlLoading` следующим образом:

- При проведении платежа проверяйте `url` на наличие схемы для редиректа в приложение СберБанк Онлайн (схема `sberpay`).
- Если `url` содержит нужную схему, проверьте, что на устройстве можно запустить такой диплинк.
- Если можно, то вызовите метод `startActivity` для запуска приложения СберБанка.

**Пример переопределения метода shouldOverrideUrlLoading**

**Java**

```java
override fun shouldOverrideUrlLoading(view: WebView, url: String): Boolean {
    if (url.contains("sberpay")) {
        val intent = Intent(Intent.ACTION_VIEW).setData(Uri.parse(url))
        if (intent.resolveActivity(requireActivity().packageManager) != null) {
            startActivity(intent)
        } else {
            view.loadUrl(url)
        }
    } else {
        view.loadUrl(url)
    }
    return true
}
```

Что почитать еще

[Основы проведения платежей](https://yookassa.ru/developers/payment-acceptance/getting-started/payment-process)

[Неуспешные платежи](https://yookassa.ru/developers/payment-acceptance/after-the-payment/declined-payments)

[Отправка чеков в налоговую](https://yookassa.ru/developers/payment-acceptance/receipts/basics)
