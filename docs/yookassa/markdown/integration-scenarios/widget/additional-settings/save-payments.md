<!-- Источник: https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/additional-settings/save-payments -->
<!-- Полная копия статьи официальной документации ЮKassa, сохранено 2026-07-02 -->

# Запоминание банковских карт пользователя

Виджет ЮKassa может запоминать данные банковских карт, которыми пользователь платил в вашем магазине. При повторном платеже пользователю не придется заново вводить данные — он сможет выбрать карту, которой расплачивался ранее. Для оплаты пользователю нужно только подтвердить платеж — пройти аутентификацию по 3-D Secure или ввести код CVV2 (CVC2, CID).

Если вы хотите реализовать собственный экран выбора способа оплаты и сохранять платежные данные для [покупок в один клик](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/scenarios#one-click-payments), используйте [автоплатежи с условным сохранением способа оплаты](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/additional-settings/recurring-payments#recurring-payments-save-guide).

![Выбор запомненной карты при платеже](https://static.yoomoney.ru/docops-static/images/developers-widget-memo-card.image.ru.9f7ee285.gif)

Выбор запомненной карты при платеже

Особенности

Виджет запоминает банковские карты, оплата по которым прошла успешно, и отображает их при повторных платежах. Пользователь может выбрать одну из пяти часто используемых карт или ввести новую. Ненужные карты можно удалить.

Виджет запоминает только произвольные банковские карты, поэтому карты, которые привязаны к кошельку ЮMoney или Mir Pay, запомнить не получится.

В запросе на [создание платежа](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/integration#payment-process-create-payment) нужно передавать `merchant_customer_id` — идентификатор пользователя в вашей системе. Если этого не сделать, запомнить карту не получится.

Убедитесь, что `merchant_customer_id` относится к пользователю, который хочет совершить покупку. Например, используйте двухфакторную аутентификацию. Если в запросе передать неверный идентификатор, пользователь сможет выбрать для оплаты чужие банковские карты.

Если у вас к ЮKassa подключено несколько магазинов, пользователь может использовать запомненную карту в каждом из них. Для этого идентификатор пользователя во всех ваших магазинах должен быть одинаковый.

При платеже виджет может одновременно запомнить карту и сохранить её для автоплатежей. [Подробнее про запоминание банковской карты и ее сохранение для автоплатежей](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/additional-settings/save-payments#memo-saving-for-recurring_payments)

Запоминание карт в виджете не подходит для регулярных безакцептных списаний. Если вы хотите делать автоплатежи, передавайте в запросе параметр `save_payment_method` и при последующих платежах используйте `payment_method_id`. [Подробнее про сохранение способа оплаты для автоплатежей](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/additional-settings/recurring-payments)

Если у вашего магазина отключено [прохождение аутентификации по 3-D Secure](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/bank-card#3ds), вы не сможете сохранить банковскую карту. Напишите менеджеру ЮKassa для подключения возможности запомнить карту.

Сценарий взаимодействия

**Шаг 1**. [Первый платеж в магазин](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/additional-settings/save-payments#first-payment) — пользователь вводит данные банковской карты и разрешает их запомнить. После того как пользователь подтвердит списание денег, виджет ЮKassa запомнит данные банковской карты пользователя.

**Шаг 2**. [Следующие платежи в магазин](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/additional-settings/save-payments#second-payment) — при повторных платежах пользователь выбирает для оплаты сохраненную в виджете карту.

Первый платеж в магазин

1. Пользователь переходит к оплате.
2. Вы отправляете ЮKassa запрос на [создание платежа](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/integration#payment-process-create-payment) и дополнительно передаете в нём идентификатор пользователя в вашей системе.
3. ЮKassa возвращает вам созданный объект платежа с токеном для инициализации виджета.
4. Вы инициализируете виджет и отображаете форму на странице оплаты.
5. Пользователь выбирает оплату банковской картой, вводит данные и разрешает запомнить свои платежные данные.
6. При необходимости виджет отображает всплывающее окно для аутентификации по 3‑D Secure.
7. Пользователь подтверждает платеж.
8. Если платеж прошел, виджет перенаправляет пользователя на страницу завершения оплаты на вашей стороне.
9. Вы отображаете нужную информацию, в зависимости от статуса платежа.

![Запоминание банковской карты в магазине](https://static.yoomoney.ru/docops-static/images/developers-widget-save-bank-card.image.ru.db5def2b.svg)

Запоминание банковской карты в магазине

Следующие платежи в магазин

1. Пользователь переходит к оплате.
2. Вы отправляете ЮKassa запрос на [создание платежа](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/integration#payment-process-create-payment) и дополнительно передаете в нём идентификатор пользователя в вашей системе.
3. ЮKassa возвращает вам созданный объект платежа с токеном для инициализации виджета.
4. Вы инициализируете виджет и отображаете форму на странице оплаты.
5. Виджет отображает привязанные банковские карты пользователя
6. Пользователь выбирает карту, привязанную к вашему магазину.
7. Виджет отображает всплывающее окно для аутентификации по 3‑D Secure или просит ввести код CVV2 (CVC2, CID).
8. Пользователь подтверждает платеж.
9. Если платеж прошел, виджет перенаправляет пользователя на страницу завершения оплаты на вашей стороне.
10. Вы отображаете нужную информацию в зависимости от статуса платежа.

![Выбор запомненной карты при следующем платеже](https://static.yoomoney.ru/docops-static/images/developers-widget-saved-card.image.ru.a814a835.svg)

Выбор запомненной карты при следующем платеже

Платеж с запоминанием банковской карты

[Создайте платеж](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/integration#payment-process-create-payment) и передайте в нём `merchant_customer_id` с идентификатором пользователя в вашей системе, например логин от его учетной записи в вашем магазине.

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
        "description": "Заказ №72",
        "merchant_customer_id": "79999999999"
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
            'confirmation' => array(
                'type' => 'embedded',
            ),
            'capture' => true,
            'description' => 'Заказ №72',
            'merchant_customer_id' => '79999999999',
        ),
        $idempotenceKey
    );
    
    //get confirmation token
    $confirmationToken= $response->getConfirmation()->getConfirmationToken();
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
    "confirmation": {
        "type": "embedded"
    },
    "capture": True,
    "description": "Заказ №72",
    "merchant_customer_id": "79999999999"
}, idempotence_key)

# get confirmation token
confirmation_token= payment.confirmation.confirmation_token
```

В ответ ЮKassa вернет `merchant_customer_id` в неизменном виде и `confirmation_token` — токен для инициализации виджета. Далее проводите платеж как обычно.

Запоминание банковской карты и ее сохранение для автоплатежей

Виджет может одновременно запомнить банковскую карту и начать ее использовать для автоплатежей. Для безусловного сохранения в [запросе на создание платежа](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/integration#payment-process-create-payment) передайте идентификатор пользователя в вашей системе и параметр `save_payment_method` со значением `true`. Для условного сохранения передайте только идентификатор пользователя — передавать `save_payment_method` не нужно. [Подробнее про сохранение способа оплаты для автоплатежей](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/additional-settings/recurring-payments#recurring-payments-save-guide)

![Запоминание банковской карты и ее сохранение для автоплатежей](https://static.yoomoney.ru/docops-static/images/developers-widget-saved-recurrent-card.image.ru.eb7760ff.svg)

Запоминание банковской карты и ее сохранение для автоплатежей

Платеж с запоминанием банковской карты и ее сохранением для автоплатежей

[Создайте платеж](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/integration#payment-process-create-payment) и передайте в нём `save_payment_method` и `merchant_customer_id` с идентификатором пользователя в вашей системе.

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
        "description": "Заказ №72",
        "merchant_customer_id": "79999999999"
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
            'confirmation' => array(
                'type' => 'embedded',
            ),
            'capture' => true,
            'save_payment_method' => true,
            'description' => 'Заказ №72',
            'merchant_customer_id' => '79999999999',
        ),
        $idempotenceKey
    );
    
    //get confirmation token
    $confirmationToken= $response->getConfirmation()->getConfirmationToken();
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
    "confirmation": {
        "type": "embedded"
    },
    "capture": True,
    "save_payment_method": True,
    "description": "Заказ №72",
    "merchant_customer_id": "79999999999"
}, idempotence_key)

# get confirmation token
confirmation_token= payment.confirmation.confirmation_token
```

В ответ ЮKassa вернет `merchant_customer_id` в неизменном виде и `confirmation_token` — токен для инициализации виджета.

Если оплата прошла успешно, сохраните идентификатор способа оплаты `payment_method.id`. Его нужно будет использовать в качестве идентификатора сохраненного способа оплаты при последующих платежах.

Что почитать еще

[Сохранение способа оплаты для автоплатежей](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/additional-settings/recurring-payments)

[Автоплатежи](https://yookassa.ru/developers/payment-acceptance/scenario-extensions/recurring-payments/basics)

[Справочник виджета](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/reference)

[Типовые сценарии интеграции виджета](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/scenarios)
