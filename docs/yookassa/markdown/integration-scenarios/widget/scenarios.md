<!-- Источник: https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/scenarios -->
<!-- Полная копия статьи официальной документации ЮKassa, сохранено 2026-07-02 -->

# Типовые сценарии использования виджета ЮKassa

В этой статье приведено несколько типовых сценариев интеграции с использованием виджета ЮKassa.

Основные сценарии:

- [Товары с доставкой](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/scenarios#two-stage-payments) — товары и услуги, поставляемые после вашего подтверждения
- [Цифровые товары](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/scenarios#one-stage-payments) — товары и услуги, поставляемые сразу после оплаты

Расширения основных сценариев:

- [Подписка на автоплатежи](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/scenarios#recurring-payments)
- [Покупка в один клик](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/scenarios#one-click-payments)
- [Покупка с выбором запомненной карты](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/scenarios#show-memo-card-payments)

Товары с доставкой

Кому подойдет этот сценарий:

- вы продаете физические товары с доставкой и хотите списывать оплату с пользователя только после проверки, что нужные товары есть на складе;
- вы оказываете услуги и хотите списывать оплату с пользователя только после предварительного обсуждения или проверки заказа.

Полезные материалы

| Главное | Может пригодиться |
| --- | --- |
| [Основы работы с API](https://yookassa.ru/developers/using-api/interaction-format)  [Платежи в две стадии](https://yookassa.ru/developers/payment-acceptance/getting-started/payment-process#capture-and-cancel)  [Интеграция виджета](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/integration)  [Ошибки при инициализации виджета](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/reference#errors) | [Отображение виджета во всплывающем окне](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/additional-settings/modal-window)  [Настройка цветовой схемы виджета](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/additional-settings/design#color)  [Настройка языка текстов](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/additional-settings/design#locale)  [Входящие уведомления](https://yookassa.ru/developers/using-api/webhooks)  [Возвраты платежей](https://yookassa.ru/developers/payment-acceptance/after-the-payment/refunds)  [Покупка в один клик](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/scenarios#one-click-payments)  [Запоминание банковских карт пользователя](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/scenarios#show-memo-card-payments) |

Краткая памятка

Подготовка

**Шаг 1**. Подготовьтесь к интеграции: получите данные для аутентификации запросов, подключите нужные способы оплаты и подготовьте свой сайт.

**Шаг 2**. Подготовьте страницу оплаты: разместите виджет, настройте отображение платежной формы и при необходимости настройте цветовую схему виджета.

**HTML**

```html
<!--Подключение библиотеки-->
<script src="https://yookassa.ru/checkout-widget/v1/checkout-widget.js"></script>

<!--HTML-элемент, в котором будет отображаться платежная форма-->
<div id="payment-form"></div>

<script>
//Инициализация виджета. Все параметры обязательные, кроме объекта customization.
const checkout = new window.YooMoneyCheckoutWidget({
    confirmation_token: 'confirmation-token', //Токен, который перед проведением оплаты нужно получить от ЮKassa
    return_url: 'https://merchant.site', //Ссылка на страницу завершения оплаты

    //Настройка виджета (при необходимости)
    customization: {
        //Настройка цветовой схемы, минимум один параметр, значения цветов в HEX
        colors: {
            //Цвет акцентных элементов: кнопка Заплатить, выбранные переключатели, опции и текстовые поля
            control_primary: '#00BF96' //Значение цвета в HEX
        }
    },
    error_callback: function(error) {
        //Обработка ошибок инициализации
    }
});

//Отображение платежной формы в контейнере
checkout.render('payment-form');
</script>
```

Прием платежа

**Шаг 1**. Настройте создание платежа и получение токена для инициализации виджета, в запросе на создание платежа передайте дополнительно:

- параметр `capture` со значением `false`, чтобы провести платеж в две стадии;
- параметр `confirmation.locale`, если хотите настроить язык текста интерфейса платежной формы.

**Пример запроса на создание платежа**

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
          "type": "embedded",
          "locale": "en_US"
        },
        "capture": false,
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
            'confirmation' => array(
                'type' => 'embedded',
                'locale' => 'en_US',
            ),
            'capture' => false,
            'description' => 'Заказ №72',
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
        "type": "embedded",
        "locale": "en_US"
    },
    "capture": False,
    "description": "Заказ №72"
}, idempotence_key)

# get confirmation token
confirmation_token= payment.confirmation.confirmation_token
```

**Шаг 2**. Настройте инициализацию виджета и обработку ошибок.

**Шаг 3**. Настройте завершение оплаты и отображение пользователю информации в зависимости от статуса платежа.

**Шаг 4**. Настройте списание оплаты и отмену платежа после успешного подтверждения платежа пользователем.

После платежа

При необходимости настройте возврат платежа.

Цифровые товары

Кому подойдет этот сценарий: вы продаете цифровые товары или услуги и предоставляете их пользователю сразу после оплаты.

Полезные материалы

| Главное | Может пригодиться |
| --- | --- |
| [Основы работы с API](https://yookassa.ru/developers/using-api/interaction-format)  [Интеграция виджета](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/integration)  [Ошибки при инициализации виджета](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/reference#errors) | [Отображение виджета во всплывающем окне](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/additional-settings/modal-window)  [Настройка цветовой схемы виджета](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/additional-settings/design#color)  [Настройка языка текстов](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/additional-settings/design#locale)  [Входящие уведомления](https://yookassa.ru/developers/using-api/webhooks)  [Возвраты платежей](https://yookassa.ru/developers/payment-acceptance/after-the-payment/refunds)  [Подписка на автоплатежи](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/scenarios#recurring-payments)  [Запоминание банковских карт пользователя](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/scenarios#show-memo-card-payments) |

Краткая памятка

Подготовка

**Шаг 1**. Подготовьтесь к интеграции: получите данные для аутентификации запросов, подключите нужные способы оплаты и подготовьте свой сайт.

**Шаг 2**. Подготовьте страницу оплаты: разместите виджет, настройте отображение платежной формы и при необходимости настройте цветовую схему виджета.

**HTML**

```html
<!--Подключение библиотеки-->
<script src="https://yookassa.ru/checkout-widget/v1/checkout-widget.js"></script>

<!--HTML-элемент, в котором будет отображаться платежная форма-->
<div id="payment-form"></div>

<script>
//Инициализация виджета. Все параметры обязательные, кроме объекта customization.
const checkout = new window.YooMoneyCheckoutWidget({
    confirmation_token: 'confirmation-token', //Токен, который перед проведением оплаты нужно получить от ЮKassa
    return_url: 'https://merchant.site', //Ссылка на страницу завершения оплаты

    //Настройка виджета (при необходимости)
    customization: {
        //Настройка цветовой схемы, минимум один параметр, значения цветов в HEX
        colors: {
            //Цвет акцентных элементов: кнопка Заплатить, выбранные переключатели, опции и текстовые поля
            control_primary: '#00BF96' //Значение цвета в HEX
        }
    },
    error_callback: function(error) {
        //Обработка ошибок инициализации
    }
});

//Отображение платежной формы в контейнере
checkout.render('payment-form');
</script>
```

Прием платежа

**Шаг 1**. Настройте создание платежа и получение токена для инициализации виджета, в запросе на создание платежа передайте дополнительно:

- параметр `capture` со значением `true`, чтобы списать деньги сразу после подтверждения платежа пользователем;
- параметр `confirmation.locale`, если хотите настроить язык текста интерфейса платежной формы.

**Пример запроса на создание платежа**

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
          "type": "embedded",
          "locale": "en_US"
        },
        "capture": false,
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
            'confirmation' => array(
                'type' => 'embedded',
                'locale' => 'en_US',
            ),
            'capture' => false,
            'description' => 'Заказ №72',
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
        "type": "embedded",
        "locale": "en_US"
    },
    "capture": False,
    "description": "Заказ №72"
}, idempotence_key)

# get confirmation token
confirmation_token= payment.confirmation.confirmation_token
```

**Шаг 2**. Настройте инициализацию виджета и обработку ошибок.

**Шаг 3**. Настройте завершение оплаты и отображение пользователю информации в зависимости от статуса платежа.

После платежа

При необходимости настройте возврат платежа.

Подписка на автоплатежи

Расширение сценариев [Товары с доставкой](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/scenarios#two-stage-payments) и [Цифровые товары](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/scenarios#one-stage-payments). Для тех, кто хочет регулярно списывать абонентскую плату за подписку или реализовать другие повторные платежи.

Полезные материалы

| Главное | Может пригодиться |
| --- | --- |
| Сценарий [Цифровые товары](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/scenarios#one-stage-payments)  Сохранение способа оплаты для автоплатежей:   - [Общая информация](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/additional-settings/recurring-payments) - [Безусловное сохранение способа оплаты](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/additional-settings/recurring-payments#recurring-payments-save-mandatory) - [Получение идентификатора сохраненного способа оплаты](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/additional-settings/recurring-payments#recurring-payments-get-id)   [Проведение автоплатежа](https://yookassa.ru/developers/payment-acceptance/scenario-extensions/recurring-payments/pay-with-saved) | Сценарий [Товары с доставкой](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/scenarios#two-stage-payments)  [Платеж без сохранения способа оплаты](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/additional-settings/recurring-payments#recurring-payments-without-saving) |

Краткая памятка

Подготовка

Дополнительно для автоплатежей:

- Сообщите менеджеру ЮKassa, что собираетесь проводить автоплатежи.
- Реализуйте получение согласия пользователя на проведение автоплатежей.

Прием первого платежа

При создании платежа передайте в запросе параметр `save_payment_method` со значением `true`, чтобы провести платеж с сохранением способа оплаты. Остальные параметры передайте в зависимости от вашего сценария..

**Пример запроса на создание платежа**

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
          "type": "embedded",
          "locale": "ru_RU"
        },
        "capture": true,
        "save_payment_method": true,
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
            'confirmation' => array(
                'type' => 'embedded',
                'locale' => 'ru_RU',
            ),
            'capture' => true,
            'save_payment_method' => true,
            'description' => 'Заказ №72',
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
        "type": "embedded",
        "locale": "ru_RU"
    },
    "capture": True,
    "save_payment_method": True,
    "description": "Заказ №72",
}, idempotence_key)

# get confirmation token
confirmation_token= payment.confirmation.confirmation_token
```

После первого платежа

Получите идентификатор сохраненного способа оплаты.

Прием последующих платежей

Настройте проведение регулярных автоплатежей с использованием сохраненного способа оплаты.

Покупка в один клик

Расширение сценариев [Товары с доставкой](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/scenarios#two-stage-payments) и [Цифровые товары](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/scenarios#one-stage-payments).

Кому подойдет этот сценарий:

- вы хотите дать возможность пользователю оплачивать покупки моментально, в один клик;
- вы собираетесь самостоятельно реализовать форму выбора способа оплаты.

Если вы хотите использовать готовую форму выбора способа оплаты и сохранять только банковскую карту, используйте [покупку с выбором запомненной карты](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/scenarios#show-memo-card-payments).

Полезные материалы

| Главное | Может пригодиться |
| --- | --- |
| Сценарий [Товары с доставкой](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/scenarios#two-stage-payments)  Сохранение способа оплаты для автоплатежей:   - [Общая информация](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/additional-settings/recurring-payments) - [Условное сохранение способа оплаты](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/additional-settings/recurring-payments#recurring-payments-save-optional) - [Получение идентификатора сохраненного способа оплаты](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/additional-settings/recurring-payments#recurring-payments-get-id)   [Проведение автоплатежа](https://yookassa.ru/developers/payment-acceptance/scenario-extensions/recurring-payments/pay-with-saved) | Сценарий [Цифровые товары](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/scenarios#one-stage-payments)  [Платеж без сохранения способа оплаты](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/additional-settings/recurring-payments#recurring-payments-without-saving)  [Покупка с выбором запомненной карты](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/scenarios#show-memo-card-payments) |

Краткая памятка

Подготовка

Дополнительно для автоплатежей:

- Сообщите менеджеру ЮKassa, что собираетесь проводить автоплатежи.
- Реализуйте получение согласия пользователя на проведение автоплатежей.

Прием первого платежа

При создании платежа не передавайте в запросе параметр `save_payment_method`. Остальные параметры передайте в зависимости от вашего сценария.

**Пример запроса на создание платежа**

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
          "type": "embedded",
          "locale": "ru_RU"
        },
        "capture": true,
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
            'confirmation' => array(
                'type' => 'embedded',
                'locale' => 'ru_RU',
            ),
            'capture' => true,
            'description' => 'Заказ №72',
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
        "type": "embedded",
        "locale": "ru_RU"
    },
    "capture": True,
    "description": "Заказ №72",
}, idempotence_key)

# get confirmation token
confirmation_token= payment.confirmation.confirmation_token
```

После первого платежа

Получите идентификатор сохраненного способа оплаты.

Прием последующих платежей

Настройте проведение автоплатежа, когда пользователь выбирает заплатить в один клик.

Покупка с выбором запомненной карты

Расширение сценариев [Товары с доставкой](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/scenarios#two-stage-payments) и [Цифровые товары](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/scenarios#one-stage-payments).

Кому подойдет этот сценарий:

- вы хотите запомнить банковскую карту пользователя и отображать ее при повторной оплате;
- вы собираетесь использовать готовую форму выбора способа оплаты.

Если вы хотите самостоятельно реализовать форму выбора способа оплаты и сохранить кошелек ЮMoney или банковскую карту, используйте [покупку в один клик](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/scenarios#one-click-payments).

Полезные материалы

| Главное | Может пригодиться |
| --- | --- |
| Сценарий [Товары с доставкой](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/scenarios#two-stage-payments)  [Запоминание банковских карт пользователя](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/additional-settings/save-payments) | Сценарий [Цифровые товары](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/scenarios#one-stage-payments)  [Подписка на автоплатежи](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/scenarios#recurring-payments)  [Покупка в один клик](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/scenarios#one-click-payments) |

Краткая памятка

Подготовка

- Если у вашего магазина отключено [прохождение аутентификации по 3D-Secure](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/bank-card#3ds), напишите менеджеру ЮKassa.
- У каждого пользователя в вашей системе должен быть уникальный идентификатор.

Прием первого платежа

При создании платежа передайте `merchant_customer_id` с идентификатором пользователя в вашей системе. Остальные параметры передайте в зависимости от вашего сценария.

**Пример запроса на создание платежа**

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

Прием последующих платежей

В запросе на создание платежа передавайте идентификатор пользователя в вашей системе

Что почитать еще

[Сценарии интеграции](https://yookassa.ru/developers/payment-acceptance/getting-started/selecting-integration-scenario)

[Checkout.js](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/checkout-js/basics)
