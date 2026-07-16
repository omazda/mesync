<!-- Источник: https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/other/b2b-sberbank -->
<!-- Полная копия статьи официальной документации ЮKassa, сохранено 2026-07-02 -->

# СберБанк Бизнес Онлайн

Особенности

- Тип способа оплаты в API: `b2b_sberbank`
- [Сценарий подтверждения](https://yookassa.ru/developers/payment-acceptance/getting-started/payment-process#user-confirmation): Redirect
- [Срок оплаты](https://yookassa.ru/developers/payment-acceptance/getting-started/payment-methods#payment-term): 8 часов
- [Холдирование](https://yookassa.ru/developers/payment-acceptance/getting-started/payment-process#capture-and-cancel): нельзя платить в две стадии
- [Код в реестре](https://yookassa.ru/developers/payment-acceptance/after-the-payment/reports): 2S
- [Возврат](https://yookassa.ru/developers/payment-acceptance/after-the-payment/refunds): нет
- [Автоплатежи](https://yookassa.ru/developers/payment-acceptance/scenario-extensions/recurring-payments/basics): нет
- [Лимиты](https://yookassa.ru/developers/payment-acceptance/getting-started/payment-methods#payment-limit): минимальный размер платежа — 1 рубль, максимальный — 700 000 рублей (можно увеличить через менеджера), есть [дополнительные ограничения](https://yookassa.ru/docs/support/payments/limits)

Сценарии интеграции

Доступно только для [самостоятельной интеграции](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/other/b2b-sberbank#create-payment).

Оплата в сервисе СберБанк Бизнес Онлайн

Подключение способа оплаты

1. Сообщите менеджеру ЮKassa о своем желании подключить этот способ оплаты.
2. Пополните обеспечительный счет, с которого ЮKassa будет списывать комиссию за проведение платежей (реквизиты придут вам на электронную почту).

Проведение платежа

**Шаг 1**. [Создайте платеж](https://yookassa.ru/developers/api#create_payment):

- в объекте `payment_method_data` передайте тип `b2b_sberbank`, опишите назначение платежа и укажите информацию об НДС;
- в объекте `confirmation` передайте тип `redirect` и адрес страницы на вашей стороне, на которую пользователь вернется после оплаты (в параметре `return_url`);
- в параметре `capture` передайте значение `true`, чтобы платеж автоматически перешел в статус `succeeded` после оплаты.

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
          "value": "50.00",
          "currency": "RUB"
        },
        "payment_method_data": {
          "type": "b2b_sberbank",
          "payment_purpose": "Оплата заказа №37",
          "vat_data": {
            "type": "calculated",
            "rate": 22,
            "amount": {
              "value": "11.00",
              "currency": "RUB"
            }
          }
        },
        "confirmation": {
          "type": "redirect",
          "return_url": "https://www.example.com/return_url"
        },
        "capture": true,
        "description": "Оплата заказа №37"
      }'
```

**PHP**

```php
<?php
    $client->createPayment(
        array(
            'amount' => array(
                'value' => 50,
                'currency' => 'RUB',
            ),
            'payment_method_data' => array(
                'type' => 'b2b_sberbank',
                'payment_purpose' => 'Оплата заказа №37',
                'vat_data' => array(
                    'type' => 'calculated',
                    'rate' => 22,
                    'amount' => array(
                        'value' => 11,
                        'currency' => 'RUB',
                    ),
                ),
            ),
            'confirmation' => array(
                'type' => 'redirect',
                'return_url' => 'https://www.example.com/return_url',
            ),
            'capture' => true,
            'description' => 'Оплата заказа №37',
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
        "value": "50.00",
        "currency": "RUB"
    },
    "payment_method_data": {
      "type": "b2b_sberbank",
      "payment_purpose": "Оплата заказа №37",
      "vat_data": {
        "type": "calculated",
        "rate": "22",
        "amount": {
          "value": "11.00",
          "currency": "RUB"
        }
      }
    },
    "confirmation": {
        "type": "redirect",
        "return_url": "https://www.example.com/return_url"
    },
    "capture": True,
    "description": "Оплата заказа №37"
})
```

**Шаг 2**. Перенаправьте пользователя на страницу для подтверждения оплаты (ссылка на страницу придет в параметре `confirmation_url`).

**Пример созданного объекта платежа**

**JSON**

```json
{
  "id": "1da5c87d-0984-50e8-a7f3-8de646dd9ec9",
  "status": "pending",
  "paid": false,
  "amount": {
    "value": "50.00",
    "currency": "RUB"
  },
  "confirmation": {
    "type": "redirect",
    "confirmation_url": "http://b2bsberbank.confirmation.url?orderId=1da5c87d-0984-50e8-a7f3-8de646dd9ec9"
  },
  "created_at": "2017-06-29T22:20:00.000Z",
  "description": "Оплата заказа №37",
  "metadata": {},
  "payment_method": {
    "id": "1da5c87d-0984-50e8-a7f3-8de646dd9ec9",
    "type": "b2b_sberbank",
    "saved": false,
    "payment_purpose": "Оплата заказа №37",
    "vat_data": {
      "type": "calculated",
      "amount": {
        "value": "11.00",
        "currency": "RUB"
      },
      "rate": "22"
    }
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

**Пример объекта платежа в статусе succeeded**

**JSON**

```json
{
  "id": "1da5c87d-0984-50e8-a7f3-8de646dd9ec9",
  "status": "succeeded",
  "paid": true,
  "amount": {
    "value": "50.00",
    "currency": "RUB"
  },
  "captured_at": "2017-06-29T22:30:00.000Z",
  "created_at": "2017-06-29T22:20:00.000Z",
  "income_amount": {
    "value": "48.17",
    "currency": "RUB"
  },
  "description": "Оплата заказа №37",
  "metadata": {},
  "payment_method": {
    "id": "1da5c87d-0984-50e8-a7f3-8de646dd9ec9",
    "type": "b2b_sberbank",
    "saved": false,
    "payer_bank_details": {
      "account": "40702810355002135468",
      "address": "197111, Российская Федерация, г.Санкт-Петербург, ул.3-й Северовокзальный, д.17, корп./стр.2, кв.16",
      "bank_bik": "044030653",
      "bank_branch": "СЕВЕРО-ЗАПАДНЫЙ БАНК СБЕРБАНКА РФ",
      "bank_name": "СЕВЕРО-ЗАПАДНЫЙ БАНК ПАО СБЕРБАНК",
      "full_name": "Общество с ограниченной ответственностью 'Организация'",
      "inn": "7728662610",
      "kpp": "783501610",
      "short_name": "ООО 'Организация'"
    },
    "payment_purpose": "Оплата заказа №37",
    "vat_data": {
      "type": "calculated",
      "amount": {
        "value": "11.00",
        "currency": "RUB"
      },
      "rate": "22"
    }
  },
  "refunded_amount": {
    "value": "0.00",
    "currency": "RUB"
  },
  "refundable": false,
  "test": false
}
```

Реестр B2B-Платежей

Платежи через СберБанк Бизнес Онлайн не попадают в реестр платежей. Для этих платежей формируются отдельные реестры. [Подробнее о реестре B2B-Платежей](https://yookassa.ru/docs/support/merchant/payments/reports/reports-new#b2b)

Что почитать еще

[Основы проведения платежей](https://yookassa.ru/developers/payment-acceptance/getting-started/payment-process)

[Неуспешные платежи](https://yookassa.ru/developers/payment-acceptance/after-the-payment/declined-payments)
