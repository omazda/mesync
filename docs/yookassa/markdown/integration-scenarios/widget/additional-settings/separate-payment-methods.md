<!-- Источник: https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/additional-settings/separate-payment-methods -->
<!-- Полная копия статьи официальной документации ЮKassa, сохранено 2026-07-02 -->

# Настройка отображения способов оплаты

Доступность этой опции уточняйте у вашего менеджера ЮKassa.

По умолчанию на платежной форме отображаются все способы оплаты, которые доступны магазину и есть в виджете. Дизайн этого экрана и порядок отображения способов оплаты определяет виджет. Когда пользователь переходит к оплате, он выбирает нужный ему способ, вводит данные и подтверждает платеж.

Если готовый экран выбора вам не подходит, вы можете его отключить и указать те способы оплаты, которые хотите отобразить пользователю. Эта опция подойдет тем, кто хочет реализовать собственный экран выбора.

Использование формы для оплаты конкретным способом

Чтобы отобразить форму оплаты конкретным способом, при инициализации виджета передайте объект `customization` с массивом `payment_methods`. Значение, которое нужно передать в массиве `payment_methods`, зависит от способа оплаты, который вы хотите использовать:

- [Банковская карта](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/additional-settings/separate-payment-methods#bank-card)
- [ЮMoney](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/additional-settings/separate-payment-methods#yoo-money)
- [Mir Pay](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/additional-settings/separate-payment-methods#mir-pay)
- [SberPay](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/additional-settings/separate-payment-methods#sberbank)
- [T-Pay](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/additional-settings/separate-payment-methods#tinkoff-bank)
- [СБП (Система быстрых платежей)](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/additional-settings/separate-payment-methods#sbp)
- [«Покупки в кредит» от СберБанка](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/additional-settings/separate-payment-methods#sber-loan)
- [Комбинации способов оплаты](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/additional-settings/separate-payment-methods#combinations)

Вы можете разместить на странице оплаты несколько экземпляров виджета. В этом случае создать платеж нужно только один раз и инициализировать все экземпляры одним и тем же токеном. Токен будет работать, пока не закончится срок его действия или пока пользователь не подтвердит платеж.

Банковская карта

Чтобы отобразить форму для оплаты банковской картой, передайте в `payment_methods` значение `bank_card`. Минимальная ширина контейнера для отображения платежной формы — 288 пикселей.

![Пример платежной формы: банковская карта](https://static.yoomoney.ru/docops-static/images/developers-payments-widget-bank-card.image.ru.5bd2170d.svg)

Пример платежной формы: банковская карта

При неуспешном платеже банковской картой виджет отображает пользователю сообщение об ошибке и предлагает попробовать оплатить еще раз. Если хотите самостоятельно взаимодействовать с пользователем при каждой неуспешной попытке оплаты, напишите вашему менеджеру ЮKassa.

**JavaScript**

```javascript
<script>
//Инициализация виджета. Все параметры обязательные, кроме объекта customization.
const checkout = new window.YooMoneyCheckoutWidget({
    confirmation_token: 'confirmation-token', //Токен, который перед проведением оплаты нужно получить от ЮKassa
    return_url: 'https://example.com', //Ссылка на страницу завершения оплаты

    //Настройка виджета
    customization: {
        //Код, который нужно выполнить после отображения платежной формы.
        payment_methods: ['bank_card']
    },
    error_callback: function(error) {
        //Обработка ошибок инициализации
    }
});

//Отображение платежной формы в контейнере
checkout.render('payment-form');
</script>
```

ЮMoney

Чтобы отобразить форму для оплаты из кошелька ЮMoney, с привязанных карт и баллами лояльности, передайте в `payment_methods` значение `yoo_money`. Минимальная ширина контейнера для отображения платежной формы — 288 пикселей.

![Пример платежной формы: ЮMoney](https://static.yoomoney.ru/docops-static/images/developers-payments-widget-yoomoney.image.ru.c1e66995.svg)

Пример платежной формы: ЮMoney

При неуспешном платеже из кошелька ЮMoney или с привязанной к кошельку карты виджет отображает пользователю сообщение об ошибке и предлагает попробовать оплатить еще раз. Если хотите самостоятельно взаимодействовать с пользователем при каждой неуспешной попытке оплаты, напишите вашему менеджеру ЮKassa.

**JavaScript**

```javascript
<script>
//Инициализация виджета. Все параметры обязательные, кроме объекта customization.
const checkout = new window.YooMoneyCheckoutWidget({
    confirmation_token: 'confirmation-token', //Токен, который перед проведением оплаты нужно получить от ЮKassa
    return_url: 'https://example.com', //Ссылка на страницу завершения оплаты

    //Настройка виджета
    customization: {
        //Выбор способа оплаты для отображения
        payment_methods: ['yoo_money']
    },
    error_callback: function(error) {
        //Обработка ошибок инициализации
    }
});

//Отображение платежной формы в контейнере
checkout.render('payment-form');
</script>
```

Mir Pay

Чтобы отобразить кнопку для оплаты через Mir Pay, передайте в `payment_methods` значение `mir_pay`. Минимальная ширина контейнера для отображения кнопки — 288 пикселей. [Цветовую схему](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/additional-settings/design#color-how-to) кнопки изменить нельзя — ее фон может быть только белым.

![Пример платежной формы на мобильном устройстве: Mir Pay](https://static.yoomoney.ru/docops-static/images/developers-payments-widget-mir-pay.266ef3c0.svg)

Пример платежной формы на мобильном устройстве: Mir Pay

Кнопка отображается при оплате с мобильных устройств на Android. Если кнопку отобразить нельзя, вы получите ошибку `no_payment_methods_to_display`.

Если вы отображаете кнопку для оплаты через Mir Pay, вам нужно самостоятельно взаимодействовать с пользователем при каждой попытке оплаты. Если платеж закончился неудачей, выясните причину отмены платежа и сообщите ее пользователю. Чтобы виджет обрабатывал неуспешные попытки самостоятельно, отображайте все способы оплаты или [комбинацию способов оплаты](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/additional-settings/separate-payment-methods#combinations) Mir Pay и банковская карта.

**JavaScript**

```javascript
<script>
//Инициализация виджета. Все параметры обязательные, кроме объекта customization.
const checkout = new window.YooMoneyCheckoutWidget({
    confirmation_token: 'confirmation-token', //Токен, который перед проведением оплаты нужно получить от ЮKassa
    return_url: 'https://example.com', //Ссылка на страницу завершения оплаты

    //Настройка виджета
    customization: {
        //Выбор способа оплаты для отображения
        payment_methods: ['mir_pay']
    },
    error_callback: function(error) {
        //Обработка ошибок инициализации
    }
});

//Отображение платежной формы в контейнере
checkout.render('payment-form');
</script>
```

SberPay

Чтобы отобразить форму для оплаты через SberPay, передайте в `payment_methods` значение `sberbank`. Минимальная ширина контейнера для отображения платежной формы — 288 пикселей.

Оплата через SberPay для компьютера и мобильного устройства отличается. При оплате с компьютера формируется QR-код, который нужно отсканировать телефоном в приложении СберБанка:

![Пример платежной формы (с компьютера): SberPay](https://static.yoomoney.ru/docops-static/images/developers-payments-widget-sberpay-desktop.image.ru.76b76b54.svg)

Пример платежной формы (с компьютера): SberPay

При оплате с мобильного устройства виджет открывает приложение СберБанка. Если открыть приложение не удалось, отображается кнопка **Перейти в приложение**:

![Пример платежной формы (с мобильного устройства): SberPay](https://static.yoomoney.ru/docops-static/images/developers-payments-widget-sberpay-mobile.image.ru.8224ddba.svg)

Пример платежной формы (с мобильного устройства): SberPay

При неуспешном платеже через SberPay виджет отображает пользователю сообщение об ошибке и предлагает попробовать оплатить еще раз. Если хотите самостоятельно взаимодействовать с пользователем при каждой неуспешной попытке оплаты, напишите вашему менеджеру ЮKassa.

**JavaScript**

```javascript
<script>
//Инициализация виджета. Все параметры обязательные, кроме объекта customization.
const checkout = new window.YooMoneyCheckoutWidget({
    confirmation_token: 'confirmation-token', //Токен, который перед проведением оплаты нужно получить от ЮKassa
    return_url: 'https://example.com', //Ссылка на страницу завершения оплаты

    //Настройка виджета
    customization: {
        //Выбор способа оплаты для отображения
        payment_methods: ['sberbank']
    },
    error_callback: function(error) {
        //Обработка ошибок инициализации
    }
});

//Отображение платежной формы в контейнере
checkout.render('payment-form');
</script>
```

T-Pay

Чтобы отобразить форму для оплаты через T-Pay, передайте в `payment_methods` значение `tinkoff_bank`. Минимальная ширина контейнера для отображения платежной формы — 288 пикселей.

Оплата через T-Pay для компьютера и мобильного устройства отличается. При оплате с компьютера формируется QR-код, который нужно отсканировать телефоном:

![Пример платежной формы (с компьютера): T-Pay](https://static.yoomoney.ru/docops-static/images/developers-payments-widget-tinkoff-bank-desktop.image.ru.20815025.svg)

Пример платежной формы (с компьютера): T-Pay

При оплате с мобильного устройства отображается кнопка **Перейти в приложение**.

![Пример платежной формы (с мобильного устройства): T-Pay](https://static.yoomoney.ru/docops-static/images/developers-payments-widget-tinkoff-bank-mobile.image.ru.7d3f5816.svg)

Пример платежной формы (с мобильного устройства): T-Pay

При неуспешном платеже через T-Pay виджет отображает пользователю сообщение об ошибке и предлагает попробовать оплатить еще раз. Если хотите самостоятельно взаимодействовать с пользователем при каждой неуспешной попытке оплаты, напишите вашему менеджеру ЮKassa.

**JavaScript**

```javascript
<script>
//Инициализация виджета. Все параметры обязательные, кроме объекта customization.
const checkout = new window.YooMoneyCheckoutWidget({
    confirmation_token: 'confirmation-token', //Токен, который перед проведением оплаты нужно получить от ЮKassa
    return_url: 'https://example.com', //Ссылка на страницу завершения оплаты

    //Настройка виджета
    customization: {
        //Выбор способа оплаты для отображения
        payment_methods: ['tinkoff_bank']
    },
    error_callback: function(error) {
        //Обработка ошибок инициализации
    }
});

//Отображение платежной формы в контейнере
checkout.render('payment-form');
</script>
```

СБП (Система быстрых платежей)

Доступно только при платежах в одну стадию (если в запросе на создание платежа вы передаете параметр `capture` со значением `true`). При платеже в [две стадии](https://yookassa.ru/developers/payment-acceptance/getting-started/payment-process#capture-and-cancel) при инициализации виджета вернется ошибка `no_payment_methods_to_display`.

Чтобы отобразить форму для оплаты через СБП, передайте в `payment_methods` значение `sbp`. Минимальная ширина контейнера для отображения платежной формы — 288 пикселей.

Оплата через СБП для компьютера и мобильного устройства отличается. При оплате с компьютера формируется QR-код, который нужно отсканировать телефоном:

![Пример платежной формы (с компьютера): СБП](https://static.yoomoney.ru/docops-static/images/developers-payments-widget-sbp-desktop.image.ru.07dc8108.svg)

Пример платежной формы (с компьютера): СБП

При оплате с мобильного устройства отображается список банков и платежных сервисов:

![Пример платежной формы (с мобильного устройства): СБП](https://static.yoomoney.ru/docops-static/images/developers-payments-widget-sbp-mobile.image.ru.cc76abc2.svg)

Пример платежной формы (с мобильного устройства): СБП

При неуспешном платеже через СБП виджет отображает пользователю сообщение об ошибке и предлагает попробовать оплатить еще раз. Если хотите самостоятельно взаимодействовать с пользователем при каждой неуспешной попытке оплаты, напишите вашему менеджеру ЮKassa.

**JavaScript**

```javascript
<script>
//Инициализация виджета. Все параметры обязательные, кроме объекта customization.
const checkout = new window.YooMoneyCheckoutWidget({
    confirmation_token: 'confirmation-token', //Токен, который перед проведением оплаты нужно получить от ЮKassa
    return_url: 'https://example.com', //Ссылка на страницу завершения оплаты

    //Настройка виджета
    customization: {
        //Выбор способа оплаты для отображения
        payment_methods: ['sbp']
    },
    error_callback: function(error) {
        //Обработка ошибок инициализации
    }
});

//Отображение платежной формы в контейнере
checkout.render('payment-form');
</script>
```

«Покупки в кредит» от СберБанка

Чтобы отобразить форму для оплаты через «Покупки в кредит» от СберБанка, передайте в `payment_methods` значение `sber_loan`. Минимальная ширина контейнера для отображения платежной формы — 288 пикселей.

На платежной форме отображаются тарифы, которые вы выбрали при подключении. По кнопке **Кредит от СберБанка** пользователь сможет перейти к оформлению потребительского кредита, а в блоке про **Рассрочка от СберБанка** сможет выбрать нужную ему рассрочку и перейти к ее оформлению.

![Пример платежной формы: «Покупки в кредит» от СберБанка (рассрочка и кредит)](https://static.yoomoney.ru/docops-static/images/developers-payments-widget-sber-loan-credit-and-installments-desktop.image.ru.d68e72ab.svg)

Пример платежной формы: «Покупки в кредит» от СберБанка (рассрочка и кредит)

Если вы подключили только кредит или только рассрочку, отобразится только одна кнопка с соответствующим названием.

После выбора тарифа виджет перенаправит пользователя в СберБанк Онлайн для заполнения заявки. Действия пользователя отличаются для компьютера и мобильного устройства.

При оплате с компьютера виджет формирует QR-код, который нужно отсканировать камерой мобильного устройства или в приложении СберБанка. Также можно перейти на сайт СберБанк Онлайн по ссылке под QR-кодом.

![Пример формы при выборе кредита (при оплате с компьютера)](https://static.yoomoney.ru/docops-static/images/developers-payments-widget-sber-loan-credit-desktop.image.ru.f74e4552.svg)

Пример формы при выборе кредита (при оплате с компьютера)

При оплате с мобильного устройства виджет открывает приложение СберБанка. Если открыть приложение не удалось, виджет отображает кнопку **Перейти в приложение**.

![Пример формы при выборе кредита (при оплате с мобильного устройства)](https://static.yoomoney.ru/docops-static/images/developers-payments-widget-sber-loan-credit-mobile.image.ru.4182053a.svg)

Пример формы при выборе кредита (при оплате с мобильного устройства)

При неуспешном платеже через «Покупки в кредит» от СберБанка виджет отображает пользователю сообщение об ошибке и предлагает оплатить еще раз. Если хотите самостоятельно взаимодействовать с пользователем при каждой неуспешной попытке оплаты, напишите вашему менеджеру ЮKassa.

**JavaScript**

```javascript
<script>
//Инициализация виджета. Все параметры обязательные, кроме объекта customization.
const checkout = new window.YooMoneyCheckoutWidget({
    confirmation_token: 'confirmation-token', //Токен, который перед проведением оплаты нужно получить от ЮKassa
    return_url: 'https://example.com', //Ссылка на страницу завершения оплаты

    //Настройка виджета
    customization: {
        //Выбор способа оплаты для отображения
        payment_methods: ['sber_loan']
    },
    error_callback: function(error) {
        //Обработка ошибок инициализации
    }
});

//Отображение платежной формы в контейнере
checkout.render('payment-form');
</script>
```

Комбинации способов оплаты

Вы можете передать только одну комбинацию способов оплаты: Mir Pay и банковская карта. Если оплата проходит с мобильного устройства на Android, кнопка Mir Pay отобразится над банковской картой.

Чтобы использовать комбинацию способов оплаты, перечислите их коды через запятую. Минимальная ширина контейнера для отображения платежной формы — 288 пикселей. [Цветовую схему](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/additional-settings/design#color-how-to) кнопки Mir Pay изменить нельзя — ее фон может быть только белым.

Одновременно можно передавать только коды `bank_card` и `mir_pay`. Если передать комбинацию из других способов оплаты, виджет вернет ошибку `invalid_combination_of_payment_methods`.

![Комбинация способов оплаты на компьютере: отображается только банковская карта](https://static.yoomoney.ru/docops-static/images/developers-payments-widget-combination-bank-card-mir-pay-desktop.image.ru.987043d6.svg)

Комбинация способов оплаты на компьютере: отображается только банковская карта

![Комбинация способов оплаты на мобильном устройстве: Mir Pay и банковская карта (на Android)](https://static.yoomoney.ru/docops-static/images/developers-payments-widget-combination-bank-card-mir-pay-mobile.image.ru.f62680aa.svg)

Комбинация способов оплаты на мобильном устройстве: Mir Pay и банковская карта (на Android)

**JavaScript**

```javascript
<script>
//Инициализация виджета. Все параметры обязательные, кроме объекта customization.
const checkout = new window.YooMoneyCheckoutWidget({
    confirmation_token: 'confirmation-token', //Токен, который перед проведением оплаты нужно получить от ЮKassa
    return_url: 'https://example.com', //Ссылка на страницу завершения оплаты

    //Настройка виджета
    customization: {
        //Выбор способа оплаты для отображения
        payment_methods: ['bank_card', 'mir_pay']
    },
    error_callback: function(error) {
        //Обработка ошибок инициализации
    }
});

//Отображение платежной формы в контейнере
checkout.render('payment-form');
</script>
```

Что почитать еще

[Checkout.js](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/checkout-js/basics)

[Справочник виджета](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/reference)

[Подключение способов оплаты в виджете](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/integration#configuration-payment-methods)
