<!-- Источник: https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/integration -->
<!-- Полная копия статьи официальной документации ЮKassa, сохранено 2026-07-02 -->

# Интеграция виджета

Подробная инструкция по использованию виджета ЮKassa для приема платежей. Если уже проинтегрировались с помощью [Быстрого старта для виджета](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/quick-start) и вас всё устраивает, можете пропустить эту статью.

Предварительная настройка

Подключите нужные вам способы оплаты, настройте свой сайт и подготовьте страницу оплаты.

Подключение способов оплаты

Виджет поддерживает несколько способов оплаты. На платежной форме будут отображаться те способы, которые подключены в вашем магазине. Способы оплаты можно проверить и подключить в личном кабинете, в разделе [Организация — Реквизиты и договор](https://yookassa.ru/my/agreement), или через вашего менеджера ЮKassa.

Некоторые способы оплаты отображаются на платежной форме виджета только при определенных условиях.

| Способ оплаты | Подключение |
| --- | --- |
| [ЮMoney](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/yoo-money) | Доступно по умолчанию |
| [Банковская карта](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/bank-card) | Доступно, если магазину разрешено принимать платежи этим способом. |
| [Mir Pay](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/mir-pay) | Доступно, если магазину разрешено принимать платежи этим способом. Кнопка отображается при оплате с мобильных устройств на Android. |
| [T-Pay](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/other/tinkoff-bank) | Доступно, если магазину разрешено принимать платежи этим способом. |
| [SberPay](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/sberpay) | Доступно, если магазину разрешено принимать платежи этим способом. |
| [СБП (Система быстрых платежей)](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/other/sbp) | Доступно, если магазину разрешено принимать платежи этим способом. |
| [«Покупки в кредит» от СберБанка](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/other/sber-loan) | Доступно, если магазину разрешено принимать платежи этим способом. Есть [два типа тарифов](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/other/sber-loan#payment-method-overview-loan-options): кредит и рассрочка. На платежной форме отображаются только те тарифы, которые вы подключили. |

Требования к сайту

В процессе оплаты виджет может отображать пользователю различные сообщения. Чтобы пользователь мог их прочитать, сайт должен работать в кодировке UTF-8.

Чтобы проверить соответствие вашего сайта этим требованиям, обратитесь к вашему хостинг-провайдеру или протестируйте сайт самостоятельно с помощью сервисов для проверки TLS, SSL и уязвимостей.

Подготовка страницы оплаты

Страница оплаты — это та страница, на которой пользователь увидит платежную форму, введет данные и подтвердит платеж. На этой странице нужно разместить виджет и отобразить платежную форму.

Вы можете настроить [отображение виджета во всплывающем окне](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/additional-settings/modal-window). При таком способе отображения вам не нужно реализовывать страницу оплаты и встраивать в нее виджет.

Размещение виджета и отображение платежной формы

**Шаг 1**. Подключите скрипт. Библиотека будет доступна в глобальной области видимости под именем `YooMoneyCheckoutWidget`.

**Шаг 2**. На страницу оплаты добавьте HTML-элемент, в котором хотите разместить форму. Задайте для данного элемента атрибут `id`. Минимальная ширина контейнера для отображения платежной формы — 288 пикселей.

**Шаг 3**. Для инициализации виджета создайте новый экземпляр класса `YooMoneyCheckoutWidget` и передайте в него следующие параметры:

- `confirmation_token`, который нужно получить в ЮKassa перед проведением платежа.
- callback-функцию, которая будет принимать [код ошибки](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/reference#errors).

Передайте `return_url`, если вы хотите, чтобы пользователь после платежа перешел на страницу завершения оплаты. Если вы хотите по-своему взаимодействовать с пользователем, [настройте обработку событий процесса оплаты](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/additional-settings/behaviour#payment-events).

При необходимости вы можете настроить [цветовую схему платежной формы](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/additional-settings/design#color) и [отображение способов оплаты](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/additional-settings/separate-payment-methods).

`confirmation_token` нужно получать в ЮKassa для [каждого платежа](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/integration#payment-process).

**Шаг 4**. Чтобы отобразить платежную форму, вызовите метод `render`. Передайте в него значение атрибута `id`, в котором нужно разместить форму, и при необходимости код, который нужно выполнить после отображения платежной формы.

**HTML**

```html
<!--Подключение библиотеки-->
<script src="https://yookassa.ru/checkout-widget/v1/checkout-widget.js"></script>

<!--HTML-элемент, в котором будет отображаться платежная форма-->
<div id="payment-form"></div>

<script>
//Инициализация виджета. Все параметры обязательные.
const checkout = new window.YooMoneyCheckoutWidget({
    confirmation_token: 'confirmation-token', //Токен, который перед проведением оплаты нужно получить от ЮKassa
    return_url: 'https://example.com', //Ссылка на страницу завершения оплаты
    error_callback: function(error) {
        //Обработка ошибок инициализации
    }
});

//Отображение платежной формы в контейнере
checkout.render('payment-form')
//Метод возвращает Promise, исполнение которого говорит о полной загрузке платежной формы (можно не использовать).
  .then(() => {
     //Код, который нужно выполнить после отображения платежной формы.
  });
</script>
```

Перезагрузка виджета

Если на вашей странице оплаты пользователь может изменить заказ, вы можете перезагрузить инициализированный виджет без обновления всей страницы.

Как это выглядит:

1. Пользователь переходит к оплате.
2. Вы отправляете ЮKassa запрос на создание платежа, получаете токен, инициализируете виджет и отображаете форму на странице оплаты.
3. Пользователь что-то меняет в заказе.
4. Вы удаляете инициализированный виджет, вызвав метод `destroy`.
5. Вы отправляете ЮKassa запрос на создание платежа, получаете новый токен.
6. Вы инициализируете виджет с новым токеном и отображаете форму на странице оплаты.
7. Пользователь выбирает способ оплаты, вводит данные, подтверждает платеж.
8. Виджет перенаправляет пользователя на вашу страницу завершения оплаты.
9. Вы отображаете нужную информацию, в зависимости от статуса платежа.

**Пример использования метода destroy**

**HTML**

```html
<!--Подключение библиотеки-->
<script src="https://yookassa.ru/checkout-widget/v1/checkout-widget.js"></script>

<!--HTML-элемент, в котором будет отображаться платежная форма-->
<div id="payment-form"></div>

<script>
//Инициализация виджета. Все параметры обязательные.
const checkout = new window.YooMoneyCheckoutWidget({
    confirmation_token: 'confirmation-token', //Токен, который перед проведением оплаты нужно получить от ЮKassa
    return_url: 'https://example.com', //Ссылка на страницу завершения оплаты
    error_callback: function(error) {
        //Обработка ошибок инициализации
    }
});

//Отображение платежной формы в контейнере
checkout.render('payment-form')
//Метод возвращает Promise, исполнение которого говорит о полной загрузке платежной формы (можно не использовать).
  .then(() => {
     //Код, который нужно выполнить после отображения платежной формы.
  });

//Удаление платежной формы из контейнера
checkout.destroy();

//Инициализация нового виджета. Все параметры обязательные.
const checkoutNew = new window.YooMoneyCheckoutWidget({
    confirmation_token: 'confirmation-token', //Токен, который перед проведением оплаты нужно получить от Яндекс.Кассы
    return_url: 'https://example.com', //Ссылка на страницу завершения оплаты
    error_callback: function(error) {
        //Обработка ошибок инициализации
    }
});

//Отображение платежной формы в контейнере
checkoutNew.render('payment-form')
//Метод возвращает Promise, исполнение которого говорит о полной загрузке платежной формы (можно не использовать).
    .then(() => {
       //Код, который нужно выполнить после отображения платежной формы.
  });
</script>
```

Проведение платежа

Чтобы провести платеж:

1. [Создайте платеж в ЮKassa](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/integration#payment-process-create-payment)
2. [Инициализируйте виджет и отобразите форму](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/integration#payment-process-widget-initialization)
3. [Завершите оплату](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/integration#payment-process-end-payment)

Шаг 1. Создайте платеж

Для создания платежа отправьте ЮKassa запрос, передайте в нём данные для [аутентификации запроса](https://yookassa.ru/developers/using-api/interaction-format#auth), [ключ идемпотентности](https://yookassa.ru/developers/using-api/interaction-format#idempotence), объект `amount` с суммой платежа, объект `confirmation` с типом `embedded` и, при необходимости, параметр `description` с описанием транзакции, которое вы увидите в [личном кабинете](https://yookassa.ru/my) и при запросе [информации о платеже](https://yookassa.ru/developers/api#get_payment).

В запросе можно передать любые [другие параметры](https://yookassa.ru/developers/api#create_payment), кроме `payment_method_data`, `payment_method_id`, `payment_token`, `airline`. Например, вы можете передать параметры для [настройки языка текстов в интерфейсе](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/additional-settings/design#locale) или для [сохранения способа оплаты для автоплатежей](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/additional-settings/recurring-payments).

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

Шаг 2. Инициализируйте виджет и отобразите платежную форму

В [объекте платежа](https://yookassa.ru/developers/api#payment_object) ЮKassa вернет `confirmation_token`.

**JSON**

```json
{
  "id": "22d6d597-000f-5000-9000-145f6df21d6f",
  "status": "pending",
  "paid": false,
  "amount": {
    "value": "2.00",
    "currency": "RUB"
  },
  "confirmation": {
    "type": "embedded",
    "confirmation_token": "ct-24301ae5-000f-5000-9000-13f5f1c2f8e0"
  },
  "created_at": "2018-07-10T14:25:27.535Z",
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

Используйте этот токен для создания экземпляра класса `YooMoneyCheckoutWidget` и [инициализации виджета](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/integration#payment-page-initialize-and-render).

Токен одноразовый, срок действия — 1 час. Если использовать токен с истекшим сроком действия, вернется ошибка `token_expired`, виджет не инициализируется. Если пользователь оплатит и вернется к той же форме, она отобразится с ошибкой. Если пользователь не успеет подтвердить оплату в течение срока действия токена, ЮKassa отменит платеж, вам нужно будет завершить оплату (см. шаг 3).

Чтобы заново запросить токен, [создайте платеж](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/integration#payment-process-create-payment) еще раз и инициализируйте виджет с новым токеном.

Шаг 3. Завершите оплату

Когда пользователь введет данные и подтвердит платеж или когда закончится срок действия токена, ЮKassa перенаправит пользователя на `return_url`, который вы передадите при инициализации виджета или выполнит действия, настроенные вами для события завершения оплаты. Вам нужно самостоятельно узнать, как завершился платеж — успехом или неудачей — и отобразить пользователю нужную информацию.

Чтобы узнать статус платежа, подождите, когда придет [уведомление](https://yookassa.ru/developers/using-api/webhooks) от ЮKassa, или периодически отправляйте запросы, чтобы получить [информацию о платеже](https://yookassa.ru/developers/api#get_payment).

Готово!

Что почитать еще

[Типовые сценарии интеграции виджета](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/scenarios)

[Проведение платежей](https://yookassa.ru/developers/payment-acceptance/getting-started/payment-process)

[Входящие уведомления](https://yookassa.ru/developers/using-api/webhooks)

[Справочник виджета](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/reference)
