<!-- Источник: https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/bank-card -->
<!-- Полная копия статьи официальной документации ЮKassa, сохранено 2026-07-02 -->

# Банковская карта

Особенности

- Тип способа оплаты в API: `bank_card`
- [Сценарий подтверждения](https://yookassa.ru/developers/payment-acceptance/getting-started/payment-process#user-confirmation): Redirect
- [Срок оплаты](https://yookassa.ru/developers/payment-acceptance/getting-started/payment-methods#payment-term): 1 час
- [Холдирование](https://yookassa.ru/developers/payment-acceptance/getting-started/payment-process#capture-and-cancel): 7 дней, доступно полное и частичное списание оплаты
- [Код в реестре](https://yookassa.ru/developers/payment-acceptance/after-the-payment/reports): AC
- [Возврат](https://yookassa.ru/developers/payment-acceptance/after-the-payment/refunds): да, полный и частичный
- Срок возврата: от 0 до 3 дней (зависит от эмитента)
- [Автоплатежи](https://yookassa.ru/developers/payment-acceptance/scenario-extensions/recurring-payments/basics): да
- [Лимиты](https://yookassa.ru/developers/payment-acceptance/getting-started/payment-methods#payment-limit): минимальный размер платежа — 1 рубль, максимальный — 350 000 рублей, есть [дополнительные ограничения](https://yookassa.ru/docs/support/payments/limits)

Сценарии интеграции

Готовые решения:

- [Умный платеж](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/smart-payment)
- [Виджет ЮKassa](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/basics)
- [Мобильные SDK](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/mobile-sdks/basics) для iOS и Android
- Платежная форма для веба в вашем дизайне — [Checkout.js](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/checkout-js/basics)

Самостоятельная интеграция:

- [Оплата на странице ЮKassa](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/bank-card#create-payment-redirect)
- [Оплата с вводом данных на вашей стороне](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/bank-card#create-payment-with-card-data) (PCI-DSS)
- [Управление 3-D Secure](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/bank-card#3ds)

Оплата на странице ЮKassa

Как это работает

В этом сценарии после создания платежа вы перенаправляете пользователя на страницу ЮKassa, где он выбирает способ оплаты и подтверждает платеж.

Какие способы оплаты доступны:

- По умолчанию отображается только форма для ввода данных банковской карты.
- При платеже с мобильного устройства на Android на платежной форме дополнительно отображается кнопка для оплаты через [Mir Pay](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/mir-pay).
- Если в вашем магазине доступна оплата через [SberPay](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/sberpay), на платежной форме может отображаться кнопка для оплаты этим способом.

Отключить отображение Mir Pay или SberPay можно через менеджера ЮKassa.

![Пример платежной формы](https://static.yoomoney.ru/docops-static/images/developers-payments-bank-card-redirect-desktop.image.ru.c2c61b22.svg)

Пример платежной формы

Для интеграции добавьте на ваш сайт кнопку, по которой можно перейти к оплате. Когда пользователь перейдет по кнопке, получите от ЮKassa ссылку на готовую страницу оплаты и перенаправьте на неё пользователя. Когда пользователь вернется обратно к вам на сайт, запросите у ЮKassa результаты платежа и отобразите их.

Как провести платеж

**Шаг 1**. [Создайте платеж](https://yookassa.ru/developers/api#create_payment), в объекте `payment_method_data` передайте тип `bank_card`, в объекте `confirmation` передайте тип `redirect` и адрес страницы на вашей стороне, на которую вернется пользователь (в параметре `return_url`).

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
          "type": "bank_card"
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
                'type' => 'bank_card',
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
        "type": "bank_card"
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
  "id": "22c5d173-000f-5000-9000-1bdf241d4651",
  "status": "pending",
  "paid": false,
  "amount": {
    "value": "2.00",
    "currency": "RUB"
  },
  "confirmation": {
    "type": "redirect",
    "return_url": "https://www.example.com/return_url",
    "confirmation_url": "https://yoomoney.ru/payments/external/confirmation?orderId=22c5d173-000f-5000-9000-1bdf241d4651"
  },
  "created_at": "2021-04-12T13:59:33.681Z",
  "description": "Заказ №72",
  "metadata": {},
  "payment_method": {
    "type": "bank_card",
    "id": "22c5d173-000f-5000-9000-1bdf241d4651",
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

Если оплата не прошла (например, не хватило денег), ЮKassa отобразит пользователю сообщение об ошибке и предложит попробовать оплатить еще раз.

**Шаг 3**. Дождитесь успешного завершения платежа: подождите, когда придет [уведомление](https://yookassa.ru/developers/using-api/webhooks) от ЮKassa, или периодически отправляйте запросы, чтобы получить [информацию о платеже](https://yookassa.ru/developers/api#get_payment).

Если пользователь ввел данные банковской карты, в объекте `payment_method` вернется код способа оплаты `bank_card`.

**Пример успешного платежа при оплате банковской картой**

**JSON**

```json
{
  "id": "22c5d173-000f-5000-9000-1bdf241d4651",
  "status": "succeeded",
  "paid": true,
  "amount": {
    "value": "2.00",
    "currency": "RUB"
  },
  "description": "Заказ №72",
  "captured_at": "2021-04-12T13:59:33.681Z",
  "created_at": "2021-04-12T13:49:33.026Z",
  "income_amount": {
    "value": "2.00",
    "currency": "RUB"
  },
  "payment_method": {
    "type": "bank_card",
    "id": "22e12f66-000f-5000-8000-18db351245c7",
    "saved": false,
    "card": {
      "first6": "555555",
      "last4": "4444",
      "expiry_month": "01",
      "expiry_year": "2030",
      "card_type": "Mir",
      "card_product": {
          "code": "MCP",
          "name": "MIR Privilege"
      },
      "issuer_country": "RU",
      "issuer_name": "Sberbank"
    }
  },
  "recipient": {
    "account_id": "100500",
    "gateway_id": "100700"
  },
  "refundable": true,
  "refunded_amount": {
    "value": "0.00",
    "currency": "RUB"
  },
  "test": false,
  "authorization_details": {
    "rrn": "603668680243",
    "auth_code": "000000",
    "three_d_secure": {
      "applied": false
    }
  },
  "metadata": {}
}
```

Если пользователь провел оплату через Mir Pay, в объекте `payment_method` вернется код способа оплаты `bank_card`, в параметре `card.source` вернется значение `mir_pay`.

**Пример успешного платежа через Mir Pay**

**JSON**

```json
{
  "id": "22e12f66-000f-5000-8000-18db351245c7",
  "status": "succeeded",
  "paid": true,
  "amount": {
    "value": "2.00",
    "currency": "RUB"
  },
  "captured_at": "2021-04-12T13:59:33.681Z",
  "created_at": "2021-04-12T13:49:33.026Z",
  "income_amount": {
    "value": "2.00",
    "currency": "RUB"
  },
  "payment_method": {
    "type": "bank_card",
    "id": "22e12f66-000f-5000-8000-18db351245c7",
    "saved": false,
    "card": {
      "first6": "555555",
      "last4": "4444",
      "expiry_month": "01",
      "expiry_year": "2030",
      "card_type": "Mir",
      "card_product": {
        "code": "MCP",
        "name": "MIR Privilege"
      },
      "issuer_country": "RU",
      "issuer_name": "Sberbank",
      "source": "mir_pay"
    }
  },
  "recipient": {
    "account_id": "100500",
    "gateway_id": "100700"
  },
  "refundable": true,
  "refunded_amount": {
    "value": "0.00",
    "currency": "RUB"
  },
  "test": false,
  "authorization_details": {
    "rrn": "603668680243",
    "auth_code": "000000",
    "three_d_secure": {
      "applied": false
    }
  }
}
```

Если при оплате пользователь выбрал SberPay, в объекте `payment_method` вернется код способа оплаты `sberbank`.

**Пример успешного платежа через SberPay**

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

Готово!

Оплата с вводом данных на вашей стороне

Чтобы использовать эту возможность, вам нужно получить сертификат на соответствие требованиям [PCI DSS](https://ru.wikipedia.org/wiki/PCI_DSS).

Как это работает

В этом сценарии вы самостоятельно реализуете выбор способа оплаты. Вы на своей стороне получаете данные банковской карты пользователя. После этого создаете платеж в ЮKassa и дожидаетесь, когда пользователь подтвердит оплату.

Для интеграции добавьте на ваш сайт кнопку, по которой пользователь перейдет к оплате, а также платежную форму для получения данных банковской карты. Когда пользователь введет данные, получите от ЮKassa ссылку на страницу аутентификации по 3-D Secure и перенаправьте на неё пользователя. Когда пользователь вернется обратно к вам на сайт, запросите у ЮKassa результаты платежа.

Как провести платеж

**Шаг 1**. [Создайте платеж](https://yookassa.ru/developers/api#create_payment), в объекте `payment_method_data` передайте тип `bank_card` и объект `card` с данными банковской карты, в объекте `confirmation` передайте тип `redirect` и адрес страницы на вашей стороне, на которую пользователь вернется после оплаты (в параметре `return_url`).

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
          "type": "bank_card",
          "card": {
            "cardholder": "MR CARDHOLDER",
            "csc": "213",
            "expiry_month": "01",
            "expiry_year": "2030",
            "number": "5555555555554477"
          }
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
                'type' => 'bank_card',
                'card' => array(
                    'cardholder' => 'MR CARDHOLDER',
                    'csc' => '213',
                    'expiry_month' => '01',
                    'expiry_year' => '2030',
                    'number' => '5555555555554477',
                ),
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
        "type": "bank_card",
        "card": {
          "cardholder": "MR CARDHOLDER",
          "csc": "213",
          "expiry_month": "01",
          "expiry_year": "2030",
          "number": "5555555555554477"
        }
    },
    "confirmation": {
        "type": "redirect",
        "return_url": "https://www.example.com/return_url"
    },
    "description": "Заказ №72"
})
```

**Шаг 2**. Перенаправьте пользователя на страницу аутентификации по 3-D Secure (ссылка на нее придет в параметре `confirmation_url`).

**Пример созданного объекта платежа**

**JSON**

```json
{
    "id": "22c5d173-000f-5000-9000-1bdf241d4651",
    "status": "pending",
    "amount": {
        "value": "2.00",
        "currency": "RUB"
    },
    "description": "Заказ №72",
    "payment_method": {
        "type": "bank_card",
        "id": "22c5d173-000f-5000-9000-1bdf241d4651",
        "saved": false,
        "title": "Bank card *4477",
        "card": {
            "first6": "555555",
            "last4": "4477",
            "expiry_month": "01",
            "expiry_year": "2030",
            "card_type": "Mir",
            "card_product": {
              "code": "MCP",
              "name": "MIR Privilege"
            },
            "issuer_country": "RU",
            "issuer_name": "Sberbank"
    },
    "created_at": "2021-04-12T13:49:33.026Z",
    "confirmation": {
        "type": "redirect",
        "confirmation_url": "<URL для аутентификации по 3-D Secure>"
    },
    "test": true,
    "paid": false,
    "refundable": false,
    "metadata": {}
}
```

**Шаг 3**. Дождитесь успешного завершения платежа: подождите, когда придет [уведомление](https://yookassa.ru/developers/using-api/webhooks) от ЮKassa, или периодически отправляйте запросы, чтобы получить [информацию о платеже](https://yookassa.ru/developers/api#get_payment).

**Пример успешного платежа**

**JSON**

```json
{
  "id": "22c5d173-000f-5000-9000-1bdf241d4651",
  "status": "succeeded",
  "paid": true,
  "amount": {
    "value": "2.00",
    "currency": "RUB"
  },
  "description": "Заказ №72",
  "captured_at": "2021-04-12T13:59:33.681Z",
  "created_at": "2021-04-12T13:49:33.026Z",
  "income_amount": {
    "value": "2.00",
    "currency": "RUB"
  },
  "payment_method": {
    "type": "bank_card",
    "id": "22e12f66-000f-5000-8000-18db351245c7",
    "saved": false,
    "card": {
      "first6": "555555",
      "last4": "4444",
      "expiry_month": "01",
      "expiry_year": "2030",
      "card_type": "Mir",
      "card_product": {
          "code": "MCP",
          "name": "MIR Privilege"
      },
      "issuer_country": "RU",
      "issuer_name": "Sberbank"
    }
  },
  "recipient": {
    "account_id": "100500",
    "gateway_id": "100700"
  },
  "refundable": true,
  "refunded_amount": {
    "value": "0.00",
    "currency": "RUB"
  },
  "test": false,
  "authorization_details": {
    "rrn": "603668680243",
    "auth_code": "000000",
    "three_d_secure": {
      "applied": false
    }
  },
  "metadata": {}
}
```

Готово!

Управление 3-D Secure

Нужно согласовать с менеджером ЮKassa.

Вы можете отключить 3-D Secure, тогда передавать объект `confirmation` не нужно. Если вы хотите запросить прохождение 3-D Secure пользователем, в объекте `confirmation` передайте тип `redirect`, адрес страницы на вашей стороне, на которую пользователь вернется после оплаты (в параметре `return_url`) и параметр `enforce` со значением `true`.

Особые требования

Для некоторых типов платежей нужно передавать дополнительные данные:

- при [пополнении электронных кошельков, банковских счетов и баланса телефонов](https://yookassa.ru/developers/payment-acceptance/scenario-extensions/top-up-phones-balance) — реквизиты получателя оплаты;
- при [продаже авиабилетов](https://yookassa.ru/developers/payment-acceptance/scenario-extensions/airline-tickets) — информацию о билетах, перелетах и пассажирах.

Что почитать еще

[Основы проведения платежей](https://yookassa.ru/developers/payment-acceptance/getting-started/payment-process)

[Неуспешные платежи](https://yookassa.ru/developers/payment-acceptance/after-the-payment/declined-payments)

[Отправка чеков в налоговую](https://yookassa.ru/developers/payment-acceptance/receipts/basics)

[Тестирование платежей](https://yookassa.ru/developers/payment-acceptance/testing-and-going-live/testing)
