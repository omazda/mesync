<!-- Источник: https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/additional-settings/design -->
<!-- Полная копия статьи официальной документации ЮKassa, сохранено 2026-07-02 -->

# Внешний вид платежной формы

В платежной форме виджета вы можете изменить язык, на котором отображаются тексты, и настроить цвета элементов интерфейса.

Настройка языка

По умолчанию тексты в платежной форме отображаются на русском. Вы можете изменить язык интерфейса на английский: при [создании платежа](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/integration#payment-process-create-payment) передайте в `confirmation` параметр `locale` со значением `en_US`.

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
                'type' => 'embedded',
                'locale' => 'en_US',
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
        "type": "embedded",
        "locale": "en_US"
    },
    "capture": True,
    "description": "Заказ №72"
})
```

Управление цветовой схемой интерфейса

По умолчанию в виджете белая платежная форма, а для важных элементов, например кнопки **Заплатить**, используется акцентный желтый цвет. Такой дизайн помогает пользователю сфокусироваться на главном — какой способ оплаты он выбрал, куда вводит данные и как перейти к оплате.

Виджет можно адаптировать под любой дизайн. Для настройки достаточно задать всего один или два цвета — остальные цвета виджет подберет сам. При необходимости вы можете откорректировать автоматически рассчитанные цвета, передав дополнительные параметры.

![Примеры настройки цветовой схемы](https://static.yoomoney.ru/docops-static/images/developers-widget-customization.image.ru.6c7ec30c.gif)

Примеры настройки цветовой схемы

Настройка цветовой схемы

Цветовая схема задается при [инициализации виджета](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/integration#payment-page-initialize-and-render) с помощью объекта `colors`, переданного в объекте `customization`. В объекте `colors` задаются параметры, влияющие на цвета элементов интерфейса.

Можно задать максимум шесть параметров: два базовых и четыре дополнительных. Каждый из базовых параметров отвечает за определенную группу элементов интерфейса. Если передать такой параметр, виджет на его основе рассчитает все нужные цвета. При необходимости вы можете уточнить автоматически подобранные цвета с помощью дополнительных параметров.

Значения цветов необходимо задавать в шестнадцатеричном представлении (HEX), иначе виджет проигнорирует настройки.

Полезное для настройки цветовой схемы:

- [Быстрый старт](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/additional-settings/design#color-quick-start)
- [Основные варианты настройки](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/additional-settings/design#color-guides)
- [Справочник параметров объекта colors](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/reference#customize-color)

Быстрый старт

Выберите, что вы хотите попробовать изменить: [цвет кнопки Заплатить](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/additional-settings/design#color-quick-start-primary) или [цвет всей формы](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/additional-settings/design#color-quick-start-full).

Быстрый старт: кнопка Заплатить

**Шаг 1**. Добавьте в скрипт для [инициализации виджета](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/integration#payment-page-initialize-and-render) объект `customization` с объектом `colors` и параметром `control_primary`.

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
    return_url: 'https://example.com', //Ссылка на страницу завершения оплаты

    //Настройка виджета
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

**Шаг 2**. [Создайте платеж](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/integration#payment-process-create-payment) для тестового магазина и инициализируйте виджет.

![Пример настроек из Быстрого старта (кнопка Заплатить)](https://static.yoomoney.ru/docops-static/images/developers-widget-customization-color-quick-start-primary.image.ru.1e386bd1.svg)

Пример настроек из Быстрого старта (кнопка Заплатить)

Готово! Кнопка **Заплатить** и другие акцентные элементы изменили свой цвет.

Это самый простой способ изменить цвет акцентных элементов. Вы можете выбрать другой [вариант настройки](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/additional-settings/design#color-guides), если хотите уточнить автоматически рассчитанные цвета или изменить другие элементы интерфейса.

Быстрый старт: вся платежная форма

**Шаг 1**. Добавьте в скрипт для [инициализации виджета](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/integration#payment-page-initialize-and-render) объект `customization` с объектом `colors` и параметрами `control_primary` и `background`.

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
    return_url: 'https://example.com', //Ссылка на страницу завершения оплаты

    //Настройка виджета
    customization: {
        //Настройка цветовой схемы, минимум один параметр, значения цветов в HEX
        colors: {
            //Цвет акцентных элементов: кнопка Заплатить, выбранные переключатели, опции и текстовые поля
            control_primary: '#00BF96', //Значение цвета в HEX

            //Цвет платежной формы и ее элементов
            background: '#F2F3F5' //Значение цвета в HEX
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

**Шаг 2**. [Создайте платеж](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/integration#payment-process-create-payment) для тестового магазина и инициализируйте виджет.

![Пример настроек из Быстрого старта (вся платежная форма)](https://static.yoomoney.ru/docops-static/images/developers-widget-customization-color-quick-start-full.image.ru.4b59ac40.svg)

Пример настроек из Быстрого старта (вся платежная форма)

Готово! Платежная форма, страница успеха и кнопка **Заплатить** изменили свои цвета.

Это самый простой способ изменить цвета всей платежной формы. Вы можете выбрать другой [вариант настройки](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/additional-settings/design#color-guides), если хотите уточнить автоматически рассчитанные цвета или изменить другие элементы интерфейса.

Варианты настройки цветовой схемы

Количество параметров, передаваемых в `colors`, зависит от того, что вы хотите изменить:

- [Только акцентные элементы](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/additional-settings/design#color-guides-primary): белая платежная форма подходит вашему сайту, а желтые акцентные элементы — нет.
- [Только платежная форма](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/additional-settings/design#color-guides-background): желтые акценты устраивают, но белая форма не подходит (например, у вас на сайте есть темная тема).
- [Акцентные элементы и платежная форма](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/additional-settings/design#color-guides-full): цвета по умолчанию не подходят совсем, нужно поменять цвета всех элементов.
- [Только детали](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/additional-settings/design#color-guides-selective): всё в целом устраивает, но нужно изменить какие-то детали, например цвет границ платежной формы.

[Справочник всех параметров объекта colors](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/reference#customize-color)

Варианты настройки: только акцентные элементы

Акцентные элементы в виджете — это то, что помогает сфокусироваться и призывает к действию: кнопка **Заплатить**, кнопка **Закрыть** на странице успеха, выбранные переключатели, опции, граница выбранного текстового поля.

На цвет акцентных элементов влияют два параметра:

- `control_primary` (базовый цвет) — цвет фона кнопки **Заплатить** и других акцентных элементов.
- `control_primary_content` — цвет текста в кнопке и содержимого акцентных переключателей и опций (например, выставленный флажок).

Чтобы изменить цвет акцентных элементов, достаточно передать только `control_primary`. В этом случае виджет автоматически выберет в качестве цвета текста либо черный, либо белый цвет (наиболее контрастный к `control_primary`).

![Параметры, определяющие цвет акцентных элементов — экран выбора способа оплаты](https://static.yoomoney.ru/docops-static/images/developers-widget-customization-primary-color-2.image.ru.889fdf4a.svg)

Параметры, определяющие цвет акцентных элементов — экран выбора способа оплаты

![Параметры, определяющие цвет акцентных элементов — экран ввода данных](https://static.yoomoney.ru/docops-static/images/developers-widget-customization-color-primary.image.ru.227028e7.svg)

Параметры, определяющие цвет акцентных элементов — экран ввода данных

Рекомендуется для `control_primary` выбирать цвет, привлекающий внимание, для `control_primary_content` — контрастный цвет, который будет читаться на фоне базового цвета.

Рекомендуется начать настройку с базового цвета, а дополнительный цвет использовать при необходимости:

**Шаг 1**. Добавьте в скрипт для [инициализации виджета](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/integration#payment-page-initialize-and-render) объект `customization` с объектом `colors` и параметром `control_primary`.

**JavaScript**

```javascript
    customization: {
        //Настройка цветовой схемы, минимум один параметр, значения цветов в HEX
        colors: {
          control_primary: '#00BF96' // Базовый цвет кнопки Заплатить и других акцентных элементов
          // Цвет текста кнопки Заплатить, цвет флажка в переключателе подберется автоматически
        }
    },
```

**Шаг 2**. [Создайте платеж](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/integration#payment-process-create-payment) для тестового магазина, инициализируйте виджет и проверьте, как смотрится платежная форма.

**Шаг 3**. При необходимости уточните автоматически рассчитанный цвет текста в кнопке **Заплатить**. Для этого добавьте в скрипт параметр `control_primary_content` с нужным цветом и инициализируйте виджет заново (или обновите страницу оплаты).

**JavaScript**

```javascript
    customization: {
        //Настройка цветовой схемы, минимум один параметр, значения цветов в HEX
        colors: {
          control_primary: '#00BF96', // Базовый цвет кнопки Заплатить и других акцентных элементов
          control_primary_content: '#FFFFFF' // Цвет текста кнопки Заплатить, цвет флажка в переключателе
        }
    },
```

![Пример настройки цветов акцентных элементов (control_primary и control_primary_content)](https://static.yoomoney.ru/docops-static/images/developers-widget-customization-color-guides-primary.image.ru.6aac9063.svg)

Пример настройки цветов акцентных элементов (control\_primary и control\_primary\_content)

Готово! Виджет можно использовать для приема платежей от ваших пользователей.

[Вернуться к выбору варианта настройки](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/additional-settings/design#color-guides)

Варианты настройки: только платежная форма

Платежная форма состоит из блоков способов оплаты (кошелек ЮMoney, банковская карта, SberPay, Mir Pay и другие), страницы успеха, сообщения о принятии оферты и логотипа ЮKassa.

Цвет фона, на котором располагаются элементы, — это цвет страницы оплаты или фона контейнера, в котором размещен виджет (вы изменяете его самостоятельно на [странице оплаты](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/integration#payment-page)). Кнопка **Заплатить** — акцентный элемент, который [настраивается отдельно](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/additional-settings/design#color-guides-primary). На все остальные элементы влияют четыре параметра:

- `background` (базовый цвет) — цвет фона блоков способов оплаты, цвет сообщений об ошибках и подсказок.
- `text` — цвет текста.
- `border` — цвет границ и разделителей.
- `control_secondary` — цвет неакцентных элементов интерфейса.

Чтобы изменить цвет платежной формы, достаточно передать только `background`. В этом случае цвет границ, текста и неакцентных элементов виджет рассчитает автоматически.

![Параметры, определяющие цвет формы — экран выбора способа оплаты](https://static.yoomoney.ru/docops-static/images/developers-widget-customization-color-background-2.image.ru.f79b9bfa.svg)

Параметры, определяющие цвет формы — экран выбора способа оплаты

![Параметры, определяющие цвет формы — экран ввода данных](https://static.yoomoney.ru/docops-static/images/developers-widget-customization-color-background.image.ru.4eb751e2.svg)

Параметры, определяющие цвет формы — экран ввода данных

Рекомендуется для `background` выбирать цвет, близкий к цвету фона контейнера, в котором размещен виджет, для `text` — контрастный цвет, который будет читаться на фоне платежной формы, на фоне неакцентных элементов и на фоне контейнера. Остальные цвета рекомендуется подбирать так, чтобы они хорошо смотрелись на фоне `background`.

Рекомендуется начать настройку с базового цвета, а дополнительные цвета использовать при необходимости:

**Шаг 1**. Добавьте в скрипт для [инициализации виджета](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/integration#payment-page-initialize-and-render) объект `customization` с объектом `colors` и параметром `background`.

**JavaScript**

```javascript
    customization: {
        //Настройка цветовой схемы, минимум один параметр, значения цветов в HEX
        colors: {
          background: '#F2F3F5' // Цвет фона платежной формы
          //Цвет текста, границ, неакцентных элементов рассчитается автоматически
        }
    },
```

**Шаг 2**. [Создайте платеж](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/integration#payment-process-create-payment) для тестового магазина, инициализируйте виджет и проверьте, как смотрится платежная форма.

**Шаг 3**. При необходимости уточните автоматически рассчитанные цвета текстов, границ или неакцентных элементов. Для этого добавьте в скрипт дополнительные параметры с нужными цветами и инициализируйте виджет заново (или обновите страницу оплаты).

**JavaScript**

```javascript
    customization: {
        //Настройка цветовой схемы, минимум один параметр, значения цветов в HEX
        colors: {
          background: '#F2F3F5', // Цвет фона платежной формы
          text: '#222222', // Цвет текста
          border: '#D4D4D4', // Цвет границ и разделителей
          control_secondary: '#AFBDCA' // Цвет неакцентных элементов интерфейса
        }
    },
```

![Пример настройки цветов платежной формы (background, text, border, control_secondary)](https://static.yoomoney.ru/docops-static/images/developers-widget-customization-color-guides-background.image.ru.f7f6c010.svg)

Пример настройки цветов платежной формы (background, text, border, control\_secondary)

Готово! Виджет можно использовать для приема платежей от ваших пользователей.

[Вернуться к выбору варианта настройки](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/additional-settings/design#color-guides)

Варианты настройки: акцентные элементы и платежная форма

Если вы хотите поменять все цвета виджета, используйте одновременно параметры для изменения [акцентных элементов](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/additional-settings/design#color-guides-primary) и [платежной формы](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/additional-settings/design#color-guides-background).

Рекомендуется начать настройку с базовых цветов, а дополнительные цвета использовать при необходимости:

**Шаг 1**. Добавьте в скрипт для [инициализации виджета](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/integration#payment-page-initialize-and-render) объект `customization` с объектом `colors` и параметрами `control_primary` и `background`.

**JavaScript**

```javascript
    customization: {
        //Настройка цветовой схемы, минимум один параметр, значения цветов в HEX
        colors: {
          background: '#0D182F',  // Цвет фона платежной формы
          control_primary: '#00BF96' // Цвет кнопки Заплатить и других акцентных элементов
        }
    },
```

**Шаг 2**. [Создайте платеж](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/integration#payment-process-create-payment) для тестового магазина, инициализируйте виджет и проверьте, как смотрится платежная форма.

**Шаг 3**. При необходимости уточните автоматически рассчитанные цвета. Для этого добавьте в скрипт дополнительные параметры с нужными цветами и инициализируйте виджет заново (или обновите страницу оплаты).

**JavaScript**

```javascript
    customization: {
        //Настройка цветовой схемы, минимум один параметр, значения цветов в HEX
        colors: {
          background: '#0D182F', // Цвет фона платежной формы
          control_primary: '#00BF96', // Цвет кнопки Заплатить и других акцентных элементов
          control_primary_content: '#FFFFFF', // Цвет текста кнопки Заплатить
          control_secondary: '#366093', // Цвет неакцентных элементов интерфейса
          border: '#244166', // Цвет границ и разделителей
          text: '#DBDCE0' // Цвет текста
        }
    },
```

![Пример настройки всех цветов (все параметры). Фон контейнера задается отдельно](https://static.yoomoney.ru/docops-static/images/developers-widget-customization-color-guides-full.image.ru.87ddda2e.svg)

Пример настройки всех цветов (все параметры). Фон контейнера задается отдельно

Готово! Виджет можно использовать для приема платежей от ваших пользователей.

[Вернуться к выбору варианта настройки](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/additional-settings/design#color-guides)

Варианты настройки: только детали

Вы можете задать только дополнительные цвета, например только цвет границ. Если нужно изменить базовые цвета, используйте инструкции по настройке [акцентных элементов](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/additional-settings/design#color-guides-primary) и [платежной формы](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/additional-settings/design#color-guides-background).

Рекомендуемый порядок настройки:

**Шаг 1**. Добавьте в скрипт для [инициализации виджета](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/integration#payment-page-initialize-and-render) объект `customization` с объектом `colors` и нужными вам [параметрами](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/reference#customize-color).

**Шаг 2**. [Создайте платеж](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/integration#payment-process-create-payment) для тестового магазина, инициализируйте виджет и проверьте, как смотрится платежная форма.

Готово! Виджет можно использовать для приема платежей от ваших пользователей.

**Пример точечной настройки виджета**

**JavaScript**

```javascript
    customization: {
        //Настройка цветовой схемы, минимум один параметр, значения цветов в HEX
        colors: {
          control_primary_content: '#0070F0', // Цвет текста кнопки Заплатить
          border: '#00BF96' // Цвет границ и разделителей
        }
    },
```

![Пример точечной настройки виджета (control_primary_content и border)](https://static.yoomoney.ru/docops-static/images/developers-widget-customization-color-guides-selective.image.ru.90d27328.svg)

Пример точечной настройки виджета (control\_primary\_content и border)

[Вернуться к выбору варианта настройки](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/additional-settings/design#color-guides)

Что почитать еще

[Checkout.js](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/checkout-js/basics)

[Справочник виджета](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/reference)

[Типовые сценарии интеграции виджета](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/scenarios)
