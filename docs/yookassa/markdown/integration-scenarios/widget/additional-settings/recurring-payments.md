<!-- Источник: https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/additional-settings/recurring-payments -->
<!-- Полная копия статьи официальной документации ЮKassa, сохранено 2026-07-02 -->

# Сохранение способа оплаты для автоплатежей

С помощью виджета ЮKassa вы можете сохранять способ оплаты, чтобы использовать его для [автоплатежей](https://yookassa.ru/developers/payment-acceptance/scenario-extensions/recurring-payments/basics). Например, для ежемесячной оплаты подписки.

По умолчанию автоплатежи работают только в [тестовом магазине](https://yookassa.ru/developers/payment-acceptance/testing-and-going-live/testing). Если хотите использовать их в вашем реальном магазине, напишите менеджеру ЮKassa.

Если вам разрешено использование автоплатежей, вы можете проводить платежи:

- [с сохранением способа оплаты](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/additional-settings/recurring-payments#recurring-payments-save-guide),
- [без сохранения способа оплаты](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/additional-settings/recurring-payments#recurring-payments-without-saving).

Платеж с сохранением способа оплаты

Сохранение способа оплаты позволяет привязать карту, кошелек ЮMoney, Mir Pay, SberPay, T-Pay или СБП к вашему магазину.

Если вы используете СБП, ознакомьтесь с [особенностями проведения платежей при оплате через СБП](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/other/sbp#payment-process-recurrent-payments).

С помощью виджета вы можете проводить платежи с безусловным или с условным сохранением способа.

[Безусловное сохранение способа оплаты](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/additional-settings/recurring-payments#recurring-payments-save-mandatory) — сохранение способа происходит по умолчанию, пользователь не может на это повлиять. Как это выглядит:

1. Вы на сайте предупреждаете пользователя, что сохраните его платежные данные, и рассказываете, как будете их использовать, например с какой регулярностью вы будете списывать деньги и на какую сумму, как пользователь может отказаться от повторных списаний в вашем магазине. Вы на своей стороне получаете от пользователя согласие на проведение автоплатежей.
2. Виджет отображает пользователю способы оплаты, поддерживающие безусловное сохранение, и предупреждает, что после платежа способ оплаты будет привязан к вашему магазину. При успешной оплате данные способа оплаты автоматически сохранятся в ЮKassa.

[Способы оплаты](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/integration#configuration-payment-methods), которые поддерживают безусловное сохранение: кошелек ЮMoney, банковская карта, Mir Pay, SberPay, T-Pay, СБП.

Пример использования: подписка на регулярные платежи.

![Платеж с безусловным сохранением способа оплаты](https://static.yoomoney.ru/docops-static/images/developers-widget-save-payment-method-true.image.ru.de42dc2f.svg)

Платеж с безусловным сохранением способа оплаты

[Условное сохранение способа оплаты](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/additional-settings/recurring-payments#recurring-payments-save-optional) — сохранение способа происходит по желанию пользователя. Как это выглядит:

1. Вы на сайте рассказываете о возможности сохранить платежные данные, о том, как вы будете их использовать и как потом от этого отказаться.
2. Виджет отображает пользователю все доступные способы оплаты. Если пользователь выберет способ оплаты, поддерживающий условное сохранение, виджет предложит ему сохранить данные для вашего магазина. Если пользователь согласится, при успешной оплате данные способа будут сохранены в ЮKassa, и вы сможете использовать идентификатор сохраненного способа оплаты для последующих платежей. Если не согласится, платеж пройдет без привязки данных к магазину.

[Способы оплаты](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/integration#configuration-payment-methods), которые поддерживают условное сохранение: кошелек ЮMoney, банковская карта.

Пример использования: привязка платежного средства к магазину для ускорения процесса оплаты при последующих платежах с самостоятельной реализацией экрана выбора способа оплаты.

Если вы хотите пользоваться готовым экраном выбора способа оплаты и сохранять только банковские карты пользователя, используйте [запоминание банковских карт пользователя](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/additional-settings/save-payments).

![Платеж с условным сохранением способа оплаты](https://static.yoomoney.ru/docops-static/images/developers-widget-save-payment-method-undefined.image.ru.25d0807c.svg)

Платеж с условным сохранением способа оплаты

Платеж с безусловным сохранением способа оплаты

**Шаг 1**. [Создайте платеж](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/integration#payment-process-create-payment) и передайте в нём `save_payment_method` со значением `true`.

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
        "confirmation": {
          "type": "embedded"
        },
        "capture": true,
        "save_payment_method": true,
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
            'confirmation' => array(
                'type' => 'embedded'
            ),
            'capture' => true,
            'save_payment_method' => true,
            'description' => 'Заказ №72',
        ),
        uniqid('', true)
    );
?>
```

**Python**

```python
payment = Payment.create({
    "amount": {
        "value": "2.00",
        "currency": "RUB"
    },
    "confirmation": {
        "type": "embedded"
    },
    "capture": True,
    "description": "Заказ №72",
    "save_payment_method": True
})
```

**Шаг 2**. В ответе от ЮKassa получите `confirmation_token` — токен для инициализации виджета.

**JSON**

```json
{
  "id": "25564507-000f-5000-9000-19878c91d156",
  "status": "pending",
  "paid": false,
  "amount": {
    "value": "2.00",
    "currency": "RUB"
  },
  "confirmation": {
    "type": "embedded",
    "confirmation_token": "ct-25564507-000f-5000-9000-19878c91d156"
  },
  "created_at": "2019-11-07T14:59:19.351Z",
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

**Шаг 3**. [Инициализируйте виджет и отобразите платежную форму](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/integration#payment-process-widget-initialization).

**Шаг 4**. Далее проводите платеж как обычно.

Если оплата прошла успешно, [получите идентификатор сохраненного способа оплаты](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/additional-settings/recurring-payments#recurring-payments-get-id).

Платеж с условным сохранением способа оплаты

**Шаг 1**. [Создайте платеж](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/integration#payment-process-create-payment), передавать `save_payment_method` не нужно.

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
        "confirmation": {
          "type": "embedded"
        },
        "capture": true,
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
            'confirmation' => array(
                'type' => 'embedded'
            ),
            'capture' => true,
            'description' => 'Заказ №72',
        ),
        uniqid('', true)
    );
?>
```

**Python**

```python
payment = Payment.create({
    "amount": {
        "value": "2.00",
        "currency": "RUB"
    },
    "confirmation": {
        "type": "embedded"
    },
    "capture": True,
    "description": "Заказ №72"
})
```

**Шаг 2**. В ответе от ЮKassa получите `confirmation_token` — токен для инициализации виджета.

**JSON**

```json
{
  "id": "25564507-000f-5000-9000-19878c91d156",
  "status": "pending",
  "paid": false,
  "amount": {
    "value": "2.00",
    "currency": "RUB"
  },
  "confirmation": {
    "type": "embedded",
    "confirmation_token": "ct-2557c659-000f-5000-9000-12714806d854"
  },
  "created_at": "2019-11-07T14:59:19.351Z",
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

**Шаг 3**. [Инициализируйте виджет и отобразите платежную форму](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/integration#payment-process-widget-initialization).

**Шаг 4**. Далее проводите платеж как обычно.

Если оплата прошла успешно, [получите идентификатор сохраненного способа оплаты](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/additional-settings/recurring-payments#recurring-payments-get-id).

Получение идентификатора сохраненного способа оплаты

**Шаг 1**. Дождитесь, когда пользователь подтвердит оплату, и платеж перейдет в статус `succeeded` (или `waiting_for_capture`, если это платеж в [две стадии](https://yookassa.ru/developers/payment-acceptance/getting-started/payment-process#capture-and-cancel)). Чтобы узнать статус платежа, подождите, когда придет [уведомление](https://yookassa.ru/developers/using-api/webhooks) от ЮKassa, или периодически отправляйте запросы, чтобы получить [информацию о платеже](https://yookassa.ru/developers/api#get_payment).

**Шаг 2**. Убедитесь, что способ оплаты сохранен: в объекте платежа значение `payment_method.saved` изменилось на `true`.

**JSON**

```json
{
  "id": "25564507-000f-5000-9000-19878c91d156",
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
    "id": "25564507-000f-5000-9000-19878c91d156",
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

**Шаг 3**. Сохраните идентификатор способа оплаты `payment_method.id`. Его нужно будет использовать в качестве идентификатора сохраненного способа оплаты при последующих платежах.

Готово!

Теперь вы можете проводить автоплатежи. Проведение платежа сохраненным способом оплаты нужно реализовать [самостоятельно](https://yookassa.ru/developers/payment-acceptance/scenario-extensions/recurring-payments/pay-with-saved).

Платеж без сохранения способа оплаты

Вы можете проводить платежи без сохранения способа оплаты. Пользователь сможет оплатить любым доступным способом. Способ оплаты не сохранится.

Чтобы провести платеж без сохранения способа оплаты:

**Шаг 1**. [Создайте платеж](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/integration#payment-process-create-payment) и передайте в нём `save_payment_method` со значением `false`.

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
        "confirmation": {
          "type": "embedded"
        },
        "capture": true,
        "save_payment_method": false,
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
            'confirmation' => array(
                'type' => 'embedded'
            ),
            'capture' => true,
            'save_payment_method' => false,
            'description' => 'Заказ №72',
        ),
        uniqid('', true)
    );
?>
```

**Python**

```python
payment = Payment.create({
    "amount": {
        "value": "2.00",
        "currency": "RUB"
    },
    "confirmation": {
        "type": "embedded"
    },
    "capture": True,
    "description": "Заказ №72",
    "save_payment_method": False
})
```

**Шаг 2**. В ответе от ЮKassa получите `confirmation_token` — токен для инициализации виджета.

**JSON**

```json
{
  "id": "25564507-000f-5000-9000-19878c91d156",
  "status": "pending",
  "paid": false,
  "amount": {
    "value": "2.00",
    "currency": "RUB"
  },
  "confirmation": {
    "type": "embedded",
    "confirmation_token": "ct-25564507-000f-5000-9000-19878c91d156"
  },
  "created_at": "2019-11-07T14:59:19.351Z",
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

**Шаг 3**. [Инициализируйте виджет и отобразите платежную форму](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/integration#payment-process-widget-initialization).

**Шаг 4**. Далее проводите платеж как обычно.

Что почитать еще

[Запоминание банковских карт пользователя](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/additional-settings/save-payments)

[Автоплатежи](https://yookassa.ru/developers/payment-acceptance/scenario-extensions/recurring-payments/basics)

[Тестирование автоплатежей](https://yookassa.ru/developers/payment-acceptance/testing-and-going-live/testing#test-recurrent)

[Справочник виджета](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/reference)

[Типовые сценарии интеграции виджета](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/scenarios)
