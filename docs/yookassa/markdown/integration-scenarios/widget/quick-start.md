<!-- Источник: https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/quick-start -->
<!-- Полная копия статьи официальной документации ЮKassa, сохранено 2026-07-02 -->

# Быстрый старт для виджета ЮKassa

С помощью этой статьи вы проведете свой первый платеж с использованием виджета ЮKassa.

В статье описан самый простой сценарий интеграции. Подробные инструкции — в разделе [Интеграция](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/integration).

Как проходит платеж

1. Пользователь переходит на страницу оплаты.
2. Вы инициализируете виджет на странице оплаты и отображаете платежную форму.
3. Пользователь выбирает способ оплаты, вводит данные и подтверждает платеж.
4. Если платеж успешен, ЮKassa уведомляет об этом пользователя (виджет отображает [страницу успеха](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/basics#features-payment-form-succeeded)).
5. ЮKassa перенаправляет пользователя на вашу страницу.
6. При необходимости вы отображаете пользователю информацию в зависимости от статуса платежа.

Готово!

Как подготовиться к проведению платежа

Вам понадобятся инструменты для взаимодействия с ЮKassa по API и две страницы для проведения платежа.

Подготовка к взаимодействию по API

При оплате вам нужно взаимодействовать с ЮKassa по API. Подготовьте удобные для вас инструменты тестирования запросов к API.

Для аутентификации запросов понадобятся [идентификатор и секретный ключ](https://yookassa.ru/developers/using-api/interaction-format#auth) вашего магазина в ЮKassa.

Этот платеж рекомендуется проводить в тестовый магазин ЮKassa. При оплате в тестовом магазине всё проходит, как при настоящих платежах, но деньги никуда не переводятся. Если у вас пока нет тестового магазина, создайте и настройте его в личном кабинете и получите его идентификатор и секретный ключ. [Подробнее о тестовом режиме](https://yookassa.ru/developers/payment-acceptance/testing-and-going-live/testing)

Если вы хотите оценить возможности API, но у вас пока нет личного кабинета в ЮKassa, [зарегистрируйтесь по этой ссылке](https://yookassa.ru/joinups?createTestShop=true). Это самый простой способ получить тестовый магазин. Указывать данные компании и подписывать договор не нужно.

Страницы для проведения платежа

Для проведения платежа вам нужно подготовить страницу оплаты и страницу завершения оплаты.

Страница оплаты — страница на вашем сайте, на которой вы отобразите платежную форму, а пользователь введет свои данные для платежа. На эту страницу нужно встроить виджет. Для проведения этого платежа создайте тестовую страницу: скопируйте код ниже и сохраните его в файл формата HTML.

Страница завершения оплаты — страница на вашем сайте, на которую виджет перенаправит пользователя после платежа и в случае успеха, и в случае неудачи. URL этой страницы необходимо указать в скрипте для инициализации виджета на странице оплаты, в параметре `return_url`. Для проведения этого платежа можете использовать любую страницу, например главную вашего сайта.

**Код тестовой страницы оплаты**

**HTML**

```html
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.1//EN" "http://www.w3.org/TR/xhtml11/DTD/xhtml11.dtd">
<html>
 <head>
  <meta http-equiv="Content-Type" content="text/html; charset=utf-8">
  <title>Прием платежа с помощью виджета ЮKassa</title>

  <!--Подключение библиотеки для инициализации виджета ЮKassa-->
  <script src="https://yookassa.ru/checkout-widget/v1/checkout-widget.js"></script>
 </head>
 <body>
  Ниже отобразится платежная форма. Если вы еще не создавали платеж и не передавали токен для инициализации виджета, появится сообщение об ошибке.

  <!--Контейнер, в котором будет отображаться платежная форма-->
  <div id="payment-form"></div>

  Данные банковской карты для оплаты в <b>тестовом магазине</b>:

   - номер — <b>5555 5555 5555 4477</b>
   - срок действия — <b>01/30</b> (или другая дата, больше текущей)
   - CVC — <b>123</b> (или три любые цифры)
   - код для прохождения 3-D Secure — <b>123</b> (или три любые цифры)

  <a href=https://yookassa.ru/developers/payment-acceptance/testing-and-going-live/testing#test-bank-card>Другие тестовые банковские карты</a>

  <script>
  //Инициализация виджета. Все параметры обязательные.
  const checkout = new window.YooMoneyCheckoutWidget({
      confirmation_token: 'ct-287e0c37-000f-5000-8000-16961d35b0fd', //Токен, который перед проведением оплаты нужно получить от ЮKassa
      return_url: 'https://example.com/', //Ссылка на страницу завершения оплаты, это может быть любая ваша страница

      //При необходимости можно изменить цвета виджета, подробные настройки см. в документации
       //customization: {
        //Настройка цветовой схемы, минимум один параметр, значения цветов в HEX
        //colors: {
            //Цвет акцентных элементов: кнопка Заплатить, выбранные переключатели, опции и текстовые поля
            //control_primary: '#00BF96', //Значение цвета в HEX

            //Цвет платежной формы и ее элементов
            //background: '#F2F3F5' //Значение цвета в HEX
        //}
      //},
      error_callback: function(error) {
          console.log(error)
      }
  });

  //Отображение платежной формы в контейнере
  checkout.render('payment-form');
  </script>
 </body>
</html>
```

Как провести тестовый платеж

Шаг 1. Создайте платеж

Для создания платежа отправьте ЮKassa запрос, передайте в нём данные для аутентификации запроса для тестового магазина, [ключ идемпотентности](https://yookassa.ru/developers/using-api/interaction-format#idempotence), сумму и описание платежа, объект `confirmation` с типом `embedded` (это значит, что для приема оплаты вы используете виджет ЮKassa). Также передайте параметр `capture` со значением `true` — так вы получите деньги сразу после оплаты (при значении `false` нужная сумма заблокируется на счете пользователя, и после этого вы можете ее списать в удобное вам время).

Если проводите платеж в тестовый магазин, то в нём списание и начисление денег будет только имитироваться.

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
    "description": "Заказ №72"
}, idempotence_key)

# get confirmation token
confirmation_token= payment.confirmation.confirmation_token
```

В объекте платежа ЮKassa вернет `confirmation_token`. Значение этого параметра понадобится для инициализации виджета.

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
  "test": true
}
```

Шаг 2. Инициализируйте виджет и отобразите платежную форму

Откройте код [страницы оплаты](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/quick-start#preparation-pages), вставьте в скрипт для инициализации виджета значение `confirmation_token`, полученное от ЮKassa на предыдущем шаге. Сохраните изменения и откройте страницу в браузере — отобразится платежная форма виджета.

**HTML**

```html
//Пример скрипта с переданным токеном.
<script>
//Инициализация виджета. Все параметры обязательные.
const checkout = new window.YooMoneyCheckoutWidget({
    confirmation_token: 'ct-24301ae5-000f-5000-9000-13f5f1c2f8e0', //Токен, который вы получили после создания платежа
    return_url: 'https://yookassa.ru/', //Ссылка на страницу завершения оплаты
    error_callback: function(error) {
        console.log(error)
    }
});

//Отображение платежной формы в контейнере
checkout.render('payment-form');
</script>
```

Шаг 3. Введите тестовые данные

Порядок действий зависит от того, в какой магазин вы проводите платеж — в тестовый или в реальный.

Платеж в тестовый магазин

Если вы проводите платеж в тестовый магазин, в виджете отобразятся два способа оплаты — из кошелька ЮMoney и банковской картой. Для оплаты можно использовать только карту.

Для проведения платежа используйте данные специальной [тестовой банковской карты](https://yookassa.ru/developers/payment-acceptance/testing-and-going-live/testing#test-bank-card), например:

- номер — `5555``5555``5555``4477`
- срок действия — `01/30` (или другая дата, больше текущей)
- CVC — `123` (или три любые цифры)
- код для прохождения 3-D Secure — `123` (или три любые цифры)

Платеж в реальный магазин

Если вы проводите платеж в ваш реальный магазин, в виджете отобразятся все способы оплаты, доступные вашему магазину.

Для проведения платежа выберите нужный вам способ оплаты и введите данные реального платежного средства.

Шаг 4. Завершите оплату

После успешного подтверждения платежа виджет на 10 секунд отобразит [страницу успеха](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/basics#features-payment-form-succeeded), а затем перенаправит вас на страницу завершения оплаты — `return_url`, который вы указали в скрипте инициализации виджета. При неуспешном подтверждении платежа виджет отобразит вам сообщение об ошибке и предложит попробовать оплатить еще раз с повторным выбором способа оплаты. При приеме оплаты от реальных пользователей вам нужно самостоятельно узнать [статус платежа](https://yookassa.ru/developers/payment-acceptance/getting-started/payment-process#lifecycle) и отобразить пользователю соответствующую информацию.

Чтобы узнать статус платежа, периодически [отправляйте запросы](https://yookassa.ru/developers/api#get_payment), чтобы получить информацию о платеже. Также вы можете [настроить уведомления](https://yookassa.ru/developers/using-api/webhooks) и дождаться, когда ЮKassa сообщит об изменении статуса.

**Пример успешно завершенного платежа**

**JSON**

```json
{
  "id": "22d6d597-000f-5000-9000-145f6df21d6f",
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
  "captured_at": "2018-07-10T14:32:08.545Z",
  "created_at": "2018-07-10T14:25:27.535Z",
  "description": "Заказ №72",
  "income_amount": {
    "value": "1.92",
    "currency": "RUB"
  },
  "metadata": {},
  "payment_method": {
    "type": "bank_card",
    "id": "22d6d597-000f-5000-9000-145f6df21d6f",
    "saved": false,
    "card": {
      "first6": "555555",
      "last4": "4477",
      "expiry_month": "01",
      "expiry_year": "2030",
      "card_type": "MasterCard",
      "issuer_country": "US"
    },
    "title": "Bank card *4477"
  },
  "recipient": {
    "account_id": "100500",
    "gateway_id": "100700"
  },
  "refundable": true,
  "refunded_amount": {
    "value": "0.00",
    "currency": "RUB"
  },
  "test": true
}
```

Готово! Вы провели свой первый платеж с использованием виджета.

Дальнейшие шаги

- Если вы использовали тестовый магазин, получите [данные для аутентификации запросов](https://yookassa.ru/developers/using-api/interaction-format#auth) для реального магазина.
- Ознакомьтесь с [типовыми сценариями интеграции виджета](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/scenarios) и возможностями ЮKassa, выберите то, что нужно вам.
- [Разместите виджет на собственной странице оплаты](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/integration#payment-page-initialize-and-render) или настройте [отображение виджета во всплывающем окне](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/additional-settings/modal-window).
- Выберите, как будете [взаимодействовать с пользователем после оплаты](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/additional-settings/behaviour#payment-events).
- [Настройте прием платежей](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/integration#payment-process).
- [Настройте внешний вид платежной формы](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/additional-settings/design): выберите язык текстов в интерфейсе и настройте цвета элементов.
- [Настройте обработку ошибок инициализации виджета](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/reference#errors).

Что почитать еще

[Основы работы с API](https://yookassa.ru/developers/using-api/interaction-format)

[Входящие уведомления](https://yookassa.ru/developers/using-api/webhooks)

[Справочник API](https://yookassa.ru/developers/api)

[Справочник виджета](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/reference)
