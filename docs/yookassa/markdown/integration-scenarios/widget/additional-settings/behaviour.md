<!-- Источник: https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/additional-settings/behaviour -->
<!-- Полная копия статьи официальной документации ЮKassa, сохранено 2026-07-02 -->

# Обработка событий виджета

Виджет умеет уведомлять о событиях, которые с ним происходят, например о том, что пользователь завершил оплату или закрыл всплывающее окно, в котором отображается платежная форма. Вы можете обрабатывать такие события, чтобы реализовать более гибкую логику взаимодействия с пользователем.

События виджета

У виджета ЮKassa есть две группы событий: события процесса оплаты и события платежной формы.

- [События процесса оплаты](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/additional-settings/behaviour#payment-events) связаны со статусом подтверждения платежа пользователем. Виджет может уведомлять вас просто о факте завершения оплаты или о конкретном статусе (успешно или нет). Обработка этих событий нужна, если вас не устраивает автоматическое перенаправление пользователя на `return_url` и вы хотите реализовать собственную логику завершения платежа.
- [События платежной формы](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/additional-settings/behaviour#payment-modal-events) связаны с действиями пользователя на платежной форме. Сейчас виджет может уведомлять только о закрытии всплывающего окна. Это событие нужно использовать, только если вы [отображаете виджет во всплывающем окне](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/additional-settings/modal-window).

Для обработки события виджета вызовите метод `on`, передайте в него [код события](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/reference#widget-events) и callback-функцию с вашим кодом. При наступлении события виджет вызовет callback-функцию.

Если платеж успешен, виджет обработает событие после закрытия [cтраницы успеха](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/basics#features-payment-form-succeeded). Страница успеха закрывается автоматически через 10 секунд или когда пользователь самостоятельно закрывает ее.

Обработка событий процесса оплаты

По умолчанию после платежа виджет перенаправляет пользователя на страницу завершения оплаты — `return_url` в [скрипте для инициализации виджета](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/integration#payment-page-initialize-and-render). Если такая логика вас не устраивает, вы можете реализовать собственную, обрабатывая события процесса оплаты.

Вы можете выбрать один из двух сценариев:

- [Простое уведомление о завершении оплаты](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/additional-settings/behaviour#payment-events-complete) — виджет уведомляет о завершении оплаты независимо от того, как она прошла (успешно или нет).
- [Уведомление о завершении оплаты с детализацией статуса](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/additional-settings/behaviour#payment-events-success-fail) — виджет уведомляет о том, как именно завершилась оплата — успехом или неудачей.

Если сработало событие процесса оплаты, сначала проверьте статус платежа: подождите, когда придет [уведомление](https://yookassa.ru/developers/using-api/webhooks) от ЮKassa, или периодически отправляйте запросы, чтобы получить [информацию о платеже](https://yookassa.ru/developers/api#get_payment).

Простое уведомление о завершении оплаты

В этом сценарии вам необходимо обработать только одно событие — `complete` (оплата завершена). Событие возникает в следующих случаях:

- пользователь успешно ввел данные и подтвердил платеж (событие обработается после закрытия [страницы успеха](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/basics#features-payment-form-succeeded));
- если вы отключили обработку [неуспешных попыток](https://yookassa.ru/developers/payment-acceptance/after-the-payment/declined-payments) в виджете: пользователь выбрал любой способ оплаты, но платеж не прошел;
- закончился срок действия токена.

Для обработки события:

**Шаг 1**. Проверьте, что в скрипте отсутствует `return_url`. Если оставить `return_url`, события обрабатываться не будут.

**Шаг 2**. Вызовите метод `on`, передайте в него код `complete` и callback-функцию с методом `destroy` и вашим кодом.

Метод `destroy` нужен, чтобы после наступления события вы при необходимости могли заново инициализировать виджет и отобразить пользователю платежную форму.

**HTML**

```html
<!--Подключение библиотеки-->
<script src="https://yookassa.ru/checkout-widget/v1/checkout-widget.js"></script>

<!--HTML-элемент, в котором будет отображаться платежная форма-->
<div id="payment-form"></div>

<script>
  //Инициализация виджета.
  const checkout = new window.YooMoneyCheckoutWidget({
    confirmation_token: 'confirmation-token', //Токен, который перед проведением оплаты нужно получить из API ЮKassa

    error_callback: function(error) {
      //Обработка ошибок инициализации
    }
  });

  checkout.on('complete', () => {
    //Код, который нужно выполнить после оплаты.

    //Удаление инициализированного виджета
    checkout.destroy();
  });

  //Отображение платежной формы в контейнере
  checkout.render('payment-form');
</script>
```

Уведомление о завершении оплаты с детализацией статуса

В этом сценарии вам необходимо обработать два события — `success` (оплата завершена успешно) и `fail` (оплата завершена неудачно). Событие `success` возникает, когда пользователь успешно ввел данные и подтвердил платеж. Это событие обработается после закрытия [страницы успеха](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/basics#features-payment-form-succeeded). Событие `fail` возникает в следующих случаях:

- если вы отключили обработку [неуспешных попыток](https://yookassa.ru/developers/payment-acceptance/after-the-payment/declined-payments) в виджете: пользователь выбрал любой способ оплаты, но платеж не прошел;
- закончился срок действия токена.

Для обработки событий:

**Шаг 1**. Проверьте, что в скрипте отсутствует `return_url`. Если оставить `return_url`, события обрабатываться не будут.

**Шаг 2**. Вызовите метод `on`, передайте в него код `success` и callback-функцию с методом `destroy` и кодом, который необходимо выполнить при успешном завершении оплаты.

**Шаг 3**. Вызовите метод `on`, передайте в него код `fail` и callback-функцию с методом `destroy` и кодом, который необходимо выполнить при неудачном завершении оплаты.

Метод `destroy` нужен, чтобы после наступления события вы при необходимости могли заново инициализировать виджет и отобразить пользователю платежную форму.

**HTML**

```html
<!--Подключение библиотеки-->
<script src="https://yookassa.ru/checkout-widget/v1/checkout-widget.js"></script>

<!--HTML-элемент, в котором будет отображаться платежная форма-->
<div id="payment-form"></div>

<script>
  //Инициализация виджета.
  const checkout = new window.YooMoneyCheckoutWidget({
    confirmation_token: 'confirmation-token', //Токен, который перед проведением оплаты нужно получить из API ЮKassa

    error_callback: function(error) {
      //Обработка ошибок инициализации
    }
  });

  checkout.on('success', () => {
      //Код, который нужно выполнить после успешной оплаты.

      //Удаление инициализированного виджета
      checkout.destroy();
    });

  checkout.on('fail', () => {
      //Код, который нужно выполнить после неудачной оплаты.

      //Удаление инициализированного виджета
      checkout.destroy();
    });

  //Отображение платежной формы в контейнере
  checkout.render('payment-form')
</script>
```

Обработка событий платежной формы

Только для тех, кто [отображает виджет во всплывающем окне](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/additional-settings/modal-window)

Виджет может уведомлять вас о том, что пользователь закрыл всплывающее окно с платежной формой (событие `modal_close`). Вы можете обрабатывать это событие, чтобы реализовать дополнительную логику взаимодействия с пользователем, например при закрытии окна сообщить пользователю, что оплата не завершена.

Для обработки события:

**Шаг 1**. Проверьте, что отображаете виджет во всплывающем окне: при [инициализации виджета](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/integration#payment-page-initialize-and-render) в объекте `customization` передан параметр `modal` со значением `true`. Если виджет размещен на странице оплаты, событие обрабатываться не будет.

**Шаг 2**. Вызовите метод `on`, передайте в него код `modal_close` и callback-функцию с кодом, который необходимо выполнить при закрытии всплывающего окна.

**HTML**

```html
<!--Подключение библиотеки-->
<script src="https://yookassa.ru/checkout-widget/v1/checkout-widget.js"></script>

<script>
  //Инициализация виджета.
  const checkout = new window.YooMoneyCheckoutWidget({
    confirmation_token: 'confirmation-token', //Токен, который перед проведением оплаты нужно получить из API ЮKassa

    error_callback: function(error) {
      //Обработка ошибок инициализации
    }
  });

  checkout.on('modal_close', () => {
    //Код, который нужно выполнить после закрытия всплывающего окна.

  });

  //Отображение платежной формы во всплывающем окне
  checkout.render();
</script>
```

Что почитать еще

[Типовые сценарии интеграции виджета](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/scenarios)

[Проведение платежей](https://yookassa.ru/developers/payment-acceptance/getting-started/payment-process)

[Входящие уведомления](https://yookassa.ru/developers/using-api/webhooks)

[Справочник виджета](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/reference)
