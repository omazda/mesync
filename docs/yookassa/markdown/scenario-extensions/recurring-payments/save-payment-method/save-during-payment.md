<!-- Источник: https://yookassa.ru/developers/payment-acceptance/scenario-extensions/recurring-payments/save-payment-method/save-during-payment -->
<!-- Полная копия статьи официальной документации ЮKassa, сохранено 2026-07-02 -->

# Привязка платежного средства во время платежа

Привязка во время платежа — это вид сохранения способа оплаты, при котором вы создаете платеж и привязываете к магазину платежное средство, которое пользователь выбрал для оплаты.

Вы можете проводить платежи с безусловным или условным сохранением способа оплаты:

- [Безусловное сохранение способа оплаты](https://yookassa.ru/developers/payment-acceptance/scenario-extensions/recurring-payments/save-payment-method/save-during-payment#save-mandatory) — сохранение способа оплаты происходит по умолчанию, пользователь не может на это повлиять.
- [Условное сохранение способа оплаты](https://yookassa.ru/developers/payment-acceptance/scenario-extensions/recurring-payments/save-payment-method/save-during-payment#save-optional) — сохранение способа оплаты происходит по желанию пользователя.

При необходимости вы можете создать [привязку во время двухстадийного платежа на минимальную сумму](https://yookassa.ru/developers/payment-acceptance/scenario-extensions/recurring-payments/save-payment-method/save-during-payment#save-and-cancel). Это позволит вам дождаться оплаты от пользователя, сохранить способ оплаты, а затем отменить платеж. Деньги вернутся пользователю.

Если вы принимаете платежи с помощью виджета ЮKassa, для сохранения способа оплаты ознакомьтесь с [инструкцией для виджета](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/additional-settings/recurring-payments).

Особенности

Доступные сценарии интеграции и способы оплаты

Если вы [партнер](https://yookassa.ru/developers/solutions-for-platforms/partners-api/basics) и для аутентификации запросов используете OAuth-токен, особенности будут отличаться от стандартных. Подробнее в разделе [Для партнеров](https://yookassa.ru/developers/payment-acceptance/scenario-extensions/recurring-payments/save-payment-method/save-during-payment#onboarding-platforms)

Привязка во время платежа поддерживается во всех [сценариях интеграции](https://yookassa.ru/developers/payment-acceptance/getting-started/selecting-integration-scenario).

Способы оплаты, которые можно сохранять во время платежа:

- кошелек [ЮMoney](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/yoo-money) (кроме банковских карт, привязанных к кошельку);
- произвольная [банковская карта](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/bank-card);
- [Mir Pay](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/mir-pay);
- [SberPay](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/sberpay);
- [T-Pay](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/other/tinkoff-bank);
- [СБП](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/other/sbp) (есть [особенности](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/other/sbp#payment-process-recurrent-payments)).

Тестирование

Автоплатежи с привязкой во время платежа по умолчанию доступны в [тестовом магазине](https://yookassa.ru/developers/payment-acceptance/testing-and-going-live/testing). Если вы хотите проводить автоплатежи в настоящем магазине — сообщите об этом вашему менеджеру ЮKassa.

Для партнеров

Если вы [партнер](https://yookassa.ru/developers/solutions-for-platforms/partners-api/basics) и для аутентификации запросов используете OAuth-токен, вы можете проводить автоплатежи от имени пользователей ЮKassa. Доступно только для сценариев интеграции [Виджет ЮKassa](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/basics) и [Умный платеж](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/smart-payment). Сохранить для автоплатежей можно только кошелек ЮMoney и произвольную банковскую карту.

Чтобы проводить автоплатежи от лица магазина:

- сообщите магазину, что ему нужно обратиться к менеджеру ЮKassa, чтобы подключить автоплатежи;
- [запросите у магазина право](https://yookassa.ru/developers/solutions-for-platforms/partners-api/oauth/basics) на сохранение и использование способов оплаты для повторных платежей.

Порядок работы

Привязка во время платежа проходит следующим образом:

1. Вы создаете платеж с [условным](https://yookassa.ru/developers/payment-acceptance/scenario-extensions/recurring-payments/save-payment-method/save-during-payment#save-mandatory) или [безусловным](https://yookassa.ru/developers/payment-acceptance/scenario-extensions/recurring-payments/save-payment-method/save-optional) сохранением способа оплаты.
2. Пользователь разрешает вам привязать платежное средство к магазину и подтверждает списание денег.
3. ЮKassa сохраняет у себя данные, которые использовались при оплате.
4. Вы сохраняете идентификатор платежа в качестве идентификатора способа оплаты. Он нужен, чтобы проводить [автоплатежи](https://yookassa.ru/developers/payment-acceptance/scenario-extensions/recurring-payments/pay-with-saved).

Привязка с безусловным сохранением способа оплаты

Если вы создаете привязку с безусловным сохранением способа оплаты, пользователь не может повлиять на привязку платежного средства. На форме оплаты ЮKassa сообщает, что после подтверждения платежа пользователь разрешает автосписания в ваш магазин.

Способы оплаты, которые поддерживают безусловное сохранение: [кошелек ЮMoney](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/yoo-money), [банковская карта](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/bank-card), [Mir Pay](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/mir-pay), [SberPay](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/sberpay), [T-Pay](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/other/tinkoff-bank), [СБП](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/other/sbp).

Безусловное сохранение поддерживают все [сценарии интеграции](https://yookassa.ru/developers/payment-acceptance/getting-started/selecting-integration-scenario).

Пример использования: подписка на регулярные платежи.

Как это работает

1. Вы на своей стороне предупреждаете пользователя, что сохраните его платежные данные, и рассказываете, как будете их использовать. Например, с какой регулярностью вы будете списывать деньги и на какую сумму, как пользователь может отказаться от повторных списаний в вашем магазине. Вы на своей стороне получаете от пользователя согласие на проведение автоплатежей.
2. ЮKassa отображает пользователю способы оплаты, поддерживающие безусловное сохранение, и предупреждает, что платежное средство будет привязано к вашему магазину. При успешной оплате данные способа оплаты автоматически сохранятся в ЮKassa.

Как создать привязку

[Cоздайте платеж](https://yookassa.ru/developers/api#create_payment) в соответствии с выбранным [сценарием интеграции](https://yookassa.ru/developers/payment-acceptance/getting-started/selecting-integration-scenario) и передайте в запросе параметр `save_payment_method` со значением `true`. Далее проводите платеж в соответствии с выбранным сценарием интеграции.

**Пример запроса для сценария интеграции Умный платеж**

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
          "type": "redirect",
          "return_url": "https://www.example.com/return_url"
        },
        "capture": true,
        "description": "Заказ №72",
        "save_payment_method": "true"
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
            'confirmation' => array(
                'type' => 'redirect',
                'return_url' => 'https://www.example.com/return_url',
            ),
            'capture' => true,
            'description' => 'Заказ №72',
            'save_payment_method' => true,
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
    "confirmation": {
        "type": "redirect",
        "return_url": "https://www.example.com/return_url"
    },
    "capture": True,
    "description": "Заказ №72",
    "save_payment_method": True
})
```

Чтобы **получить идентификатор** способа оплаты:

**Шаг 1.** Дождитесь, когда пользователь подтвердит оплату, и платеж перейдет в статус `succeeded` (или `waiting_for_capture`, если это платеж в [две стадии](https://yookassa.ru/developers/payment-acceptance/getting-started/payment-process#capture-and-cancel)). Чтобы узнать статус платежа, подождите, когда придет [уведомление](https://yookassa.ru/developers/using-api/webhooks) от ЮKassa, или периодически отправляйте запросы, чтобы получить [информацию о платеже](https://yookassa.ru/developers/api#get_payment).

**Шаг 2.** Убедитесь, что способ оплаты сохранен: в объекте платежа значение `payment_method.saved` изменилось на `true`.

**Пример успешного платежа**

**JSON**

```json
{
  "id": "22e18a2f-000f-5000-a000-1db6312b7767",
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

**Шаг 3.** Сохраните идентификатор способа оплаты `payment_methods.id`. Рекомендуется сохранять его в связке с идентификатором пользователя в вашей системе. Это нужно, чтобы в дальнейшем вы могли соотнести пользователя и его платежные данные.

**Шаг 4.** Сообщите пользователю результаты сохранения способа оплаты.

Готово!

Вы сохранили способ оплаты и теперь можете проводить [автоплатежи](https://yookassa.ru/developers/payment-acceptance/scenario-extensions/recurring-payments/pay-with-saved). Также идентификатор способа оплаты можно использовать для проведения [выплат](https://yookassa.ru/developers/payouts/scenario-extensions/multipurpose-token) (только для банковских карт).

Привязка с условным сохранением способа оплаты

Если вы создаете привязку с условным сохранением способа оплаты, пользователь на форме оплаты принимает решение о привязке платежного средства к вашему магазину. Во время платежа пользователь может выбрать опцию сохранить способ оплаты и согласиться на последующие автосписания.

Способы оплаты, которые поддерживают условное сохранение: [кошелек ЮMoney](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/yoo-money), [банковская карта](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/bank-card).

Сценарии интеграции, которые поддерживают условное сохранение: [Умный платеж](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/smart-payment), [Виджет ЮKassa](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/basics), [Самостоятельная интеграция](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/basics).

Пример использования: моментальная оплата привязанным платежным средством на вашем экране выбора способа оплаты.

Как это работает

1. Вы на своей стороне рассказываете о возможности сохранить платежные данные, а также о том, как вы будете их использовать и как потом от этого отказаться.
2. ЮKassa отображает пользователю все доступные способы оплаты. Если пользователь выберет способ оплаты, поддерживающий условное сохранение, ЮKassa предложит ему сохранить данные для вашего магазина. Если пользователь согласится, при успешной оплате данные способа будут сохранены в ЮKassa, и вы сможете использовать идентификатор способа оплаты для последующих автоплатежей. Если не согласится, платеж пройдет без сохранения способа оплаты.

Как создать привязку

[Cоздайте платеж](https://yookassa.ru/developers/api#create_payment) в соответствии с выбранным [сценарием интеграции](https://yookassa.ru/developers/payment-acceptance/getting-started/selecting-integration-scenario). Передавать параметр `save_payment_method` не нужно. Далее проводите платеж в соответствии с выбранным сценарием интеграции.

**Пример запроса для сценария интеграции Умный платеж**

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
          "type": "redirect",
          "return_url": "https://www.example.com/return_url"
        },
        "capture": true,
        "description": "Заказ №72"
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
            'confirmation' => array(
                'type' => 'redirect',
                'return_url' => 'https://www.example.com/return_url',
            ),
            'capture' => true,
            'description' => 'Заказ №72'
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
    "confirmation": {
        "type": "redirect",
        "return_url": "https://www.example.com/return_url"
    },
    "capture": True,
    "description": "Заказ №72"
})
```

Чтобы **получить идентификатор** способа оплаты:

**Шаг 1.** Дождитесь, когда пользователь подтвердит оплату, и платеж перейдет в статус `succeeded` (или `waiting_for_capture`, если это платеж в [две стадии](https://yookassa.ru/developers/payment-acceptance/getting-started/payment-process#capture-and-cancel)). Чтобы узнать статус платежа, подождите, когда придет [уведомление](https://yookassa.ru/developers/using-api/webhooks) от ЮKassa, или периодически отправляйте запросы, чтобы получить [информацию о платеже](https://yookassa.ru/developers/api#get_payment).

**Шаг 2.** Убедитесь, что способ оплаты сохранен: в объекте платежа значение `payment_method.saved` изменилось на `true`.

**Пример успешного платежа**

**JSON**

```json
{
  "id": "22e18a2f-000f-5000-a000-1db6312b7767",
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

**Шаг 3.** Сохраните идентификатор способа оплаты `payment_methods.id`. Рекомендуется сохранять его в связке с идентификатором пользователя в вашей системе. Это нужно, чтобы в дальнейшем вы могли соотнести пользователя и его платежные данные.

**Шаг 4.** Сообщите пользователю результаты сохранения способа оплаты.

Готово!

Вы сохранили способ оплаты и теперь можете проводить [автоплатежи](https://yookassa.ru/developers/payment-acceptance/scenario-extensions/recurring-payments/pay-with-saved). Также идентификатор способа оплаты можно использовать для проведения [выплат](https://yookassa.ru/developers/payouts/scenario-extensions/multipurpose-token) (только для банковских карт).

Привязка во время двухстадийного платежа на минимальную сумму

Вы можете сохранить способ оплаты во время платежа, а затем отменить его, чтобы деньги вернулись пользователю. Для этого создайте [двухстадийный платеж](https://yookassa.ru/developers/payment-acceptance/getting-started/payment-process#capture-and-cancel) на минимальную сумму, дождитесь, пока пользователь завершит оплату, и сохраните идентификатор способа оплаты. После этого платеж можно отменить.

Такие платежи рекомендуется проводить с [безусловным сохранением способа оплаты](https://yookassa.ru/developers/payment-acceptance/scenario-extensions/recurring-payments/save-payment-method/save-during-payment#save-mandatory).

Как это работает

1. Вы на своей стороне предупреждаете пользователя, что сохраните его платежные данные, и рассказываете, как будете их использовать. Например, с какой регулярностью вы будете списывать деньги и на какую сумму, как пользователь может отказаться от повторных списаний в вашем магазине. Дополнительно вы рассказываете пользователю, что для привязки нужно провести платеж на минимальную сумму, который вы затем отмените, поэтому деньги вернутся на счет. Вы на своей стороне получаете от пользователя согласие на проведение автоплатежей.
2. ЮKassa отображает пользователю способы оплаты, поддерживающие безусловное сохранение, и предупреждает, что платежное средство будет привязано к вашему магазину. При успешной оплате данные способа оплаты автоматически сохранятся в ЮKassa.
3. После сохранения способа оплаты вы отменяете платеж. Деньги возвращаются на счет пользователя.

Как создать привязку

**Шаг 1.** [Cоздайте платеж](https://yookassa.ru/developers/api#create_payment) в соответствии с выбранным [сценарием интеграции](https://yookassa.ru/developers/payment-acceptance/getting-started/selecting-integration-scenario) и передайте в запросе следующие параметры:

- параметр `save_payment_method` со значением `true`, чтобы сохранить способ оплаты;
- параметр `capture` со значением `false`, чтобы провести платеж в две стадии.

Далее проводите платеж в соответствии с выбранным сценарием интеграции.

**Пример запроса для сценария интеграции Умный платеж**

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
          "type": "redirect",
          "return_url": "https://www.example.com/return_url"
        },
        "capture": true,
        "description": "Заказ №72",
        "save_payment_method": "true"
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
            'confirmation' => array(
                'type' => 'redirect',
                'return_url' => 'https://www.example.com/return_url',
            ),
            'capture' => true,
            'description' => 'Заказ №72',
            'save_payment_method' => true,
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
    "confirmation": {
        "type": "redirect",
        "return_url": "https://www.example.com/return_url"
    },
    "capture": True,
    "description": "Заказ №72",
    "save_payment_method": True
})
```

**Шаг 2.** Получите идентификатор способа оплаты.

1. Дождитесь, когда пользователь подтвердит оплату, и платеж перейдет в статус `waiting_for_capture`. Чтобы узнать статус платежа, подождите, когда придет [уведомление](https://yookassa.ru/developers/using-api/webhooks) от ЮKassa, или периодически отправляйте запросы, чтобы получить [информацию о платеже](https://yookassa.ru/developers/api#get_payment).
2. Убедитесь, что способ оплаты сохранен: в объекте платежа значение `payment_method.saved` изменилось на `true`.
3. Сохраните идентификатор способа оплаты `payment_methods.id`. Рекомендуется сохранять его в связке с идентификатором пользователя в вашей системе. Это нужно, чтобы в дальнейшем вы могли соотнести пользователя и его платежные данные.

**Пример платежа в статусе waiting\_for\_capture**

**JSON**

```json
{
  "id": "2a217a2d-000f-5000-9000-1bd6f124af9c",
  "status": "waiting_for_capture",
  "amount": {
    "value": "1.00",
    "currency": "RUB"
  },
  "description": "Оплата заказа №37",
  "recipient": {
    "account_id": "100500",
    "gateway_id": "100700"
  },
  "payment_method": {
    "type": "bank_card",
    "id": "2a217a2d-000f-5000-9000-1bd6f124af9c",
    "saved": true,
    "title": "Bank card *4444",
    "card": {
      "first6": "555555",
      "last4": "4444",
      "expiry_year": "2030",
      "expiry_month": "12",
      "card_type": "Mir",
      "card_product": {
        "code": "MCP",
        "name": "MIR Privilege"
      },
      "issuer_country": "RU"
    }
  },
  "created_at": "2022-05-26T11:37:17.497Z",
  "expires_at": "2022-06-02T11:37:55.385Z",
  "test": false,
  "paid": true,
  "refundable": false,
  "metadata": {
    "order_id": "37"
  },
  "authorization_details": {
    "rrn": "603668680243",
    "auth_code": "000000",
    "three_d_secure": {
      "applied": true
    }
  }
}
```

**Шаг 3**. [Отмените платеж](https://yookassa.ru/developers/api#cancel_payment).

**Пример запроса на отмену платежа**

**cURL**

```bash
curl https://api.yookassa.ru/v3/payments/{payment_id}/cancel \
  -X POST \
  -u <Идентификатор магазина>:<Секретный ключ> \
  -H 'Idempotence-Key: <Ключ идемпотентности>' \
  -H 'Content-Type: application/json' \
  -d '{

      }'
```

**PHP**

```php
<?php
    $paymentId = '215d8da0-000f-50be-b000-0003308c89be';
    $idempotenceKey = uniqid('', true);
    $response = $client->cancelPayment(
        $paymentId,
        $idempotenceKey
    );
?>
```

**Python**

```python
from yookassa import Payment
import uuid

payment_id = '215d8da0-000f-50be-b000-0003308c89be'
idempotence_key = str(uuid.uuid4())
response = Payment.cancel(
  payment_id,
  idempotence_key
)
```

**Пример платежа в статусе canceled**

**JSON**

```json
{
  "id": "2a217a2d-000f-5000-9000-1bd6f124af9c",
  "status": "canceled",
  "amount": {
    "value": "1.00",
    "currency": "RUB"
  },
  "description": "Оплата заказа №37",
  "recipient": {
    "account_id": "100500",
    "gateway_id": "100700"
  },
  "payment_method": {
    "type": "bank_card",
    "id": "2a217a2d-000f-5000-9000-1bd6f124af9c",
    "saved": true,
    "title": "Bank card *4444",
    "card": {
      "first6": "555555",
      "last4": "4444",
      "expiry_year": "2030",
      "expiry_month": "12",
      "card_type": "Mir",
      "card_product": {
        "code": "MCP",
        "name": "MIR Privilege"
      },
      "issuer_country": "RU"
    }
  },
  "created_at": "2022-05-26T11:37:17.497Z",
  "test": false,
  "paid": false,
  "refundable": false,
  "metadata": {
    "order_id": "37"
  },
  "cancellation_details": {
    "party": "merchant",
    "reason": "canceled_by_merchant"
  },
  "authorization_details": {
    "rrn": "603668680243",
    "auth_code": "000000",
    "three_d_secure": {
      "applied": true
    }
  }
}
```

**Шаг 4.** Сообщите пользователю результаты сохранения способа оплаты.

Готово!

Вы сохранили способ оплаты и теперь можете проводить [автоплатежи](https://yookassa.ru/developers/payment-acceptance/scenario-extensions/recurring-payments/pay-with-saved). Также идентификатор способа оплаты можно использовать для проведения [выплат](https://yookassa.ru/developers/payouts/scenario-extensions/multipurpose-token) (только для банковских карт).

Проведение автоплатежа

Проведение платежа сохраненным способом оплаты нужно реализовать самостоятельно. Для этого отправьте запрос на создание автоплатежа и передайте в нём параметр `payment_method_id` с идентификатором способа оплаты. [Подробнее о проведении автоплатежа](https://yookassa.ru/developers/payment-acceptance/scenario-extensions/recurring-payments/pay-with-saved)

Что почитать еще

[Основы проведения платежей](https://yookassa.ru/developers/payment-acceptance/getting-started/payment-process)

[Тестирование автоплатежей](https://yookassa.ru/developers/payment-acceptance/testing-and-going-live/testing#test-recurrent)

[Неуспешные платежи](https://yookassa.ru/developers/payment-acceptance/after-the-payment/declined-payments)

[Платеж без сохранения способа оплаты](https://yookassa.ru/developers/payment-acceptance/scenario-extensions/recurring-payments/pay-without-saving)
