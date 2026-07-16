<!-- Источник: https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/additional-settings/modal-window -->
<!-- Полная копия статьи официальной документации ЮKassa, сохранено 2026-07-02 -->

# Отображение виджета во всплывающем окне

Вы можете управлять тем, как будет отображаться виджет — на вашей странице оплаты или во всплывающем окне.

**Размещение на странице оплаты** (основной способ) — вы разрабатываете страницу оплаты с контейнером для размещения платежной формы и инициализируете виджет: пользователь переходит на вашу страницу оплаты, выбирает способ оплаты и подтверждает платеж. [Подробнее про размещение на странице оплаты](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/integration#payment-page-initialize-and-render)

**Отображение виджета во всплывающем окне** — вам нужно только инициализировать виджет: когда пользователь переходит к оплате, виджет в вашем интерфейсе отображает всплывающее окно с платежной формой. В этом окне пользователь выбирает способ оплаты и подтверждает платеж.

![Пример виджета во всплывающем окне](https://static.yoomoney.ru/docops-static/images/developers-widget-modal-window-methods.image.ru.5d075d4c.gif)

Пример виджета во всплывающем окне

Сценарий проведения платежа

1. Пользователь переходит к оплате, например нажимает кнопку **Заплатить**.
2. Вы отправляете ЮKassa запрос на создание платежа.
3. ЮKassa возвращает вам созданный объект платежа с токеном для инициализации виджета.
4. Вы инициализируете виджет с помощью токена.
5. Виджет автоматически отображает всплывающее окно с платежной формой.
6. Пользователь выбирает способ оплаты, вводит данные.
7. При необходимости виджет перенаправляет пользователя на страницу подтверждения платежа или отображает еще одно всплывающее окно (например, для аутентификации по 3‑D Secure).
8. Пользователь подтверждает платеж.
9. Если по какой-то причине платеж не прошел (например, не хватило денег) и срок действия токена для инициализации виджета еще не истек, виджет отображает пользователю сообщение об ошибке и предлагает оплатить еще раз с возможностью повторно выбрать способ оплаты.
10. Если пользователь подтвердил платеж или если закончился срок действия токена для инициализации, виджет перенаправляет пользователя на страницу завершения оплаты на вашей стороне.
11. Вы отображаете нужную информацию, в зависимости от статуса платежа.

Инструкция по инициализации платежной формы

Чтобы платежная форма открывалась во всплывающем окне, нужно при [инициализации виджета](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/integration#payment-page-initialize-and-render) в объекте `customization` передать параметр `modal` со значением `true`. Для отображения платежной формы вызовите метод `render`.

Вы можете узнать, когда пользователь закрыл всплывающее окно, и [обработать это событие](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/additional-settings/behaviour#payment-modal-events), например сообщить пользователю, что оплата не завершена.

При необходимости вы можете настроить [цветовую схему платежной формы](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/additional-settings/design#color) и [отображение способов оплаты](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/additional-settings/separate-payment-methods).

**HTML**

```html
<!--Подключение библиотеки-->
<script src="https://yookassa.ru/checkout-widget/v1/checkout-widget.js"></script>

<script>
//Инициализация виджета. Все параметры обязательные, кроме объекта customization.
const checkout = new window.YooMoneyCheckoutWidget({
    confirmation_token: 'confirmation-token', //Токен, который перед проведением оплаты нужно получить от ЮKassa
    return_url: 'https://example.com', //Ссылка на страницу завершения оплаты

    //Настройка виджета
    customization: {
        //Настройка способа отображения
        modal: true
    },
    error_callback: function(error) {
        //Обработка ошибок инициализации
    }
});

//Отображение платежной формы в модальном окне
checkout.render()
//Метод возвращает Promise, исполнение которого говорит о полной загрузке платежной формы (можно не использовать).
  .then(() => {
     //Код, который нужно выполнить после отображения платежной формы.
});
</script>
```

Что почитать еще

[Справочник виджета](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/reference)

[Внешний вид платежной формы](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/additional-settings/design)

[Размещение виджета на собственной странице оплаты](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/integration#payment-page-initialize-and-render)

[Обработка событий виджета](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/additional-settings/behaviour)
