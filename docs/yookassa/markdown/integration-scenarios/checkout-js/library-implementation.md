<!-- Источник: https://yookassa.ru/developers/payment-acceptance/integration-scenarios/checkout-js/library-implementation -->
<!-- Полная копия статьи официальной документации ЮKassa, сохранено 2026-07-02 -->

# Использование Checkout.js

Инициализация

Checkout.js подключается только с серверов `https://static.yoomoney.ru`. Так чувствительные данные ваших пользователей всегда будут в безопасности.

Чтобы начать работу с API, загрузите основную библиотеку.

**HTML**

```html
<script src="https://static.yoomoney.ru/checkout-js/v1/checkout.js"></script>
```

Аутентификация

Создайте экземпляр объекта YooMoneyCheckout.

Используйте конструкцию `YooMoneyCheckout (<Идентификатор магазина>)`

`<Идентификатор магазина>` — shopId вашего магазина в ЮKassa (выдается при подключении, его можно посмотреть в личном кабинете ЮKassa).

**JavaScript**

```javascript
const checkout = YooMoneyCheckout(<Идентификатор магазина>);
```

После этого можно будет создать инстанс от YooMoneyCheckout и использовать его для генерации токена с данными банковской карты.

Чтобы вы могли создавать платежи с использованием токена, запросите разрешение у вашего менеджера ЮKassa.

Конфигурация

Вы можете показывать пользователям сообщения и ошибки по-русски или по-английски. По умолчанию ЮKassa отображает ошибки на русском языке.

| Параметр | Описание | Тип | Валидация |
| --- | --- | --- | --- |
| language | Язык пользовательских ошибок.  Возможные значения: `en` и `ru` | string | 2 символа |

**JavaScript**

```javascript
const checkout = YooMoneyCheckout(<Идентификатор магазина>, {
    language: 'en'
});
```

Токенизация

Сгенерируйте платежный токен с данными банковской карты. Токен можно использовать для проведения оплаты по API ЮKassa.

**JavaScript**

```javascript
checkout.tokenize({
    number: document.querySelector('.number').value,
    cvc: document.querySelector('.cvc').value,
    month: document.querySelector('.expiry_month').value,
    year: document.querySelector('.expiry_year').value
}).then(res => {
    if (res.status === 'success') {
        const { paymentToken } = res.data.response;

        return paymentToken;
    }
});
```

Параметры метода

| Параметр | Описание | Тип | Валидация |
| --- | --- | --- | --- |
| number | Номер банковской карты | string | 16 символов, только числа |
| cvc | Код CVC2 или CVV2, 3 или 4 символа, печатается на обратной стороне карты | string | 3, 4 символа, только числа |
| month | Месяц истечения срока действия карты | string | 2 символа, только числа |
| year | Год истечения срока действия карты | string | 2 символа, только числа |

**Пример валидных данных**

**JavaScript**

```javascript
checkout.tokenize({
    number: document.querySelector('.number').value,
    cvc: document.querySelector('.cvc').value,
    month: document.querySelector('.expiry_month').value,
    year: document.querySelector('.expiry_year').value
}).then(response => {
    if (response.status === 'success') {
        const { paymentToken } = response.data.response;

        // eyJlbmNyeXB0ZWRNZXNzYWdlIjoiWlc...
        return paymentToken;
    }
});
```

**Пример невалидных данных**

**JavaScript**

```javascript
checkout.tokenize({
    number: document.querySelector('.number').value,
    cvc: document.querySelector('.cvc').value,
    month: document.querySelector('.expiry_month').value,
    year: document.querySelector('.expiry_year').value
}).then(response => {
    if (response.status === 'error') {
        // validation_error
        const { type } = response.error;

        /*
            [
                {
                    code: 'invalid_expiry_month',
                    message: 'Невалидное значение месяца'
                },
                {
                    code: 'invalid_cvc',
                    message: 'Невалидное значение CVC'
                }
            ]
        */
        const { params } = response.error;

        return response;
    }
});
```

Ошибки

Библиотека возвращает два типа ошибок: ошибки валидации данных на форме и ошибки, связанные с работой Checkout.js.

**JavaScript**

```javascript
try {
    const checkout = YooMoneyCheckout(); // Не передан shopId
} catch(error) {
    // Формат ответа см. в разделе «Ошибки»
}
```

**Формат выдачи ошибок**

**JavaScript**

```javascript
{
    status: 'error',
    error: {
        type: string,
        message: ?string,
        status_code: number,
        code: ?string,
        params: Array<{
            code: string,
            message: string
        }>
    }
}
```

Ошибки валидации возникают, когда пользователь неправильно вводит данные банковской карты: эти ошибки необходимо показывать пользователю.

**JavaScript**

```javascript
{
    status: 'error',
    error: {
        type: 'validation_error',
        message: undefined,
        status_code: 400,
        code: undefined,
        params: [
            {
                code: 'invalid_number',
                message: 'Неверный номер карты'
            },
            {
                code: 'invalid_expiry_month',
                message: 'Невалидное значение месяца'
            }
        ]
    }
}
```

Остальные ошибки возвращаются при проблемах с инициализацией библиотеки или взаимодействием библиотеки с сервером ЮKassa. Такие ошибки показывать пользователю не нужно.

**JavaScript**

```javascript
{
    status: 'error',
    error: {
        type: 'api_connection_error',
        message: 'Ошибка в подключении сервера',
        status_code: 402,
        code: 'processing_error',
        params: []
    }
}
```

Коды ответа

| Код ответа | Значение |
| --- | --- |
| 400 | Ошибка валидации |
| 401 | Ошибка аутентификации |
| 402 | Ошибка подключения к API ЮKassa |
| 404 | Запрашиваемый ресурс не найден |
| 500 | Непредвиденная ошибка |

Checkout.js поддерживает стандартные коды ответа:

- все коды, которые начинаются с `20*`, сигнализируют об успешном выполнении запроса;
- `40*` — о том, что что-то пошло не так;
- `50*` — о том, что произошла какая-то непредвиденная ошибка на стороне ЮKassa.

Типы ошибок

| Тип ошибки | Значение |
| --- | --- |
| authentication\_error | Проблема с аутентификацией |
| api\_connection\_error | Не получилось установить соединение с ЮKassa |
| api\_error | Произошла ошибка на стороне ЮKassa |
| card\_error | Что-то не так с банковской картой |
| invalid\_request\_error | Неверные данные запроса |
| validation\_error | Ошибка валидации, какое-то из полей на форме ввода банковской карты введено неверно |

Коды ошибок

| Код ошибки | Значение |
| --- | --- |
| invalid\_number | Невалидный номер карты |
| invalid\_expiry\_month | Неверный месяц истечения срока действия карты |
| invalid\_expiry\_year | Неверный год истечения срока действия карты |
| invalid\_cvc | Неверный CVC-код |
| processing\_error | Ошибка при проверке карты |
| missing | Непредвиденная ошибка |

Что почитать еще

[Виджет ЮKassa](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/basics)

[Проведение платежа с использованием токена](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/checkout-js/payments-with-tokens)

[Основы проведения платежей](https://yookassa.ru/developers/payment-acceptance/getting-started/payment-process)

[Входящие уведомления](https://yookassa.ru/developers/using-api/webhooks)
