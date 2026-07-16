<!-- Источник: https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/other/sbp -->
<!-- Полная копия статьи официальной документации ЮKassa, сохранено 2026-07-02 -->

# Система быстрых платежей (СБП)

Особенности

- Тип способа оплаты в API: `sbp`
- [Сценарий подтверждения](https://yookassa.ru/developers/payment-acceptance/getting-started/payment-process#user-confirmation): Redirect
- [Срок оплаты](https://yookassa.ru/developers/payment-acceptance/getting-started/payment-methods#payment-term): 1 час
- [Холдирование](https://yookassa.ru/developers/payment-acceptance/getting-started/payment-process#capture-and-cancel): нельзя платить в две стадии
- [Код в реестре](https://yookassa.ru/developers/payment-acceptance/after-the-payment/reports): CP
- [Возврат](https://yookassa.ru/developers/payment-acceptance/after-the-payment/refunds): да, полный и частичный
- Срок возврата: на следующий день
- [Автоплатежи](https://yookassa.ru/developers/payment-acceptance/scenario-extensions/recurring-payments/basics): да, но есть [особенности](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/other/sbp#payment-process-recurrent-payments)
- [Лимиты](https://yookassa.ru/developers/payment-acceptance/getting-started/payment-methods#payment-limit): минимальный размер платежа — 1 рубль, максимальный — 700 000 рублей (можно увеличить через менеджера)

Сценарии интеграции

Готовые решения:

- [Умный платеж](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/smart-payment)
- [Виджет ЮKassa](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/basics)
- [Мобильные SDK](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/mobile-sdks/basics) для iOS и Android

Самостоятельная интеграция: [Оплата через СБП на готовой странице ЮKassa](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/other/sbp#create-payment-redirect)

Процесс платежа

При оплате через СБП пользователю нужно подтвердить платеж в мобильном приложении банка или платежного сервиса, поддерживающем эту функцию. [Список банков и платежных сервисов с оплатой через СБП](https://sbp.nspk.ru/participants/)

Платежи через СБП можно принимать на сайте и в мобильном приложении:

1. Пользователь выбирает СБП в качестве способа оплаты.
2. Пользователь переходит к оплате: в полной версии сайта — сканирует QR-код с помощью своего устройства и переходит по ссылке; в мобильной версии сайта или в мобильном приложении — переходит по кнопке.
3. При необходимости пользователь выбирает из списка нужного ему участника СБП (банк или платежный сервис) и переходит в мобильное приложение выбранного участника СБП.
4. Пользователь в приложении участника СБП подтверждает платеж.
5. Пользователь возвращается к вам на сайт или в приложение и узнает статус платежа.

Особенности проведения платежей с сохранением способа оплаты

Для тех, кто использует [автоплатежи](https://yookassa.ru/developers/payment-acceptance/scenario-extensions/recurring-payments/basics).

Некоторые банки и платежные сервисы, подключенные к СБП, пока не поддерживают проведение автоплатежей.

Если вы проводите платеж через СБП с сохранением способа оплаты (передаете параметр `save_payment_method` со значением `true`), то в процессе платежа в списке участников СБП будут отображаться только те банки и платежные сервисы, которые поддерживают автоплатежи. Если пользователю нужен тот банк или сервис, которого нет в списке, то оплатить не получится.

При платеже предупредите об этом пользователя и при необходимости предложите использовать другой способ для оплаты.

Каждый банк и платежный сервис самостоятельно определяет сроки, когда начнет поддерживать автоплатежи. Это закрытая информация.

Чтобы узнать, какие банки и платежные сервисы уже поддерживают автоплатежи, [перейдите на сайт СБП](https://sbp.nspk.ru/participants/) и выберите фильтр **Привязка счета**.

Оплата через СБП на готовой странице ЮKassa

Как это работает

В этом сценарии после создания платежа вы перенаправляете пользователя на страницу ЮKassa, где он сканирует QR-код или выбирает свой банк или платежный сервис.

![Пример платежной формы](https://static.yoomoney.ru/docops-static/images/developers-payments-sbp-payment-form-redirect-desktop.image.ru.b26aea97.svg)

Пример платежной формы

Для интеграции добавьте на ваш сайт кнопку, по которой можно перейти к оплате. Когда пользователь перейдет по кнопке, получите от ЮKassa ссылку на готовую страницу оплаты и перенаправьте на неё пользователя. Когда пользователь вернется обратно к вам на сайт, запросите у ЮKassa результаты платежа и отобразите их.

Как провести платеж

**Шаг 1**. [Создайте платеж](https://yookassa.ru/developers/api#create_payment):

- в объекте `amount` передайте сумму, которую нужно списать с пользователя; сумма должна укладываться в лимиты;
- в объекте `payment_method_data` передайте тип `sbp`;
- в объекте `confirmation` передайте тип `redirect` и адрес страницы на вашей стороне, на которую пользователь вернется после оплаты (в параметре `return_url`);
- в параметре `capture` передайте значение `true`, чтобы платеж автоматически перешел в статус `succeeded` после оплаты.

В запросе можно передать любые [другие параметры](https://yookassa.ru/developers/api#create_payment), кроме `payment_method_id`, `payment_token`, `airline`.

**Пример запроса**

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
        "payment_method_data": {
          "type": "sbp"
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
    $client->createPayment(
        array(
            'amount' => array(
                'value' => 2,
                'currency' => 'RUB',
            ),
            'payment_method_data' => array(
                'type' => 'sbp',
            ),
            'confirmation' => array(
                'type' => 'redirect',
                'return_url' => 'https://www.example.com/return_url',
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
from yookassa import Payment

payment = Payment.create({
    "amount": {
        "value": "2.00",
        "currency": "RUB"
    },
    "payment_method_data": {
        "type": "sbp"
    },
    "confirmation": {
        "type": "redirect",
        "return_url": "https://www.example.com/return_url"
    },
    "capture": True,
    "description": "Заказ №72"
})
```

**Шаг 2**. Перенаправьте пользователя на страницу ЮKassa, адрес которой придет в `confirmation_url`. Откроется страница ЮKassa, на которой в полной версии сайта отобразится QR-код, а в мобильной — список банков и платежных сервисов.

**Пример тела ответа**

**JSON**

```json
{
  "id": "264e0b53-000f-5000-8000-17409ff6554a",
  "status": "pending",
  "paid": false,
  "amount": {
    "value": "2.00",
    "currency": "RUB"
  },
  "confirmation": {
    "type": "redirect",
    "confirmation_url": "https://yoomoney.ru/checkout/payments/sbp?orderId=272b3eb5-000f-5000-9000-1766dbc50f19"
  },
  "created_at": "2020-05-13T13:35:15.183Z",
  "description": "Заказ №72",
  "metadata": {},
  "payment_method": {
    "type": "sbp",
    "id": "264e0b53-000f-5000-8000-17409ff6554a",
    "saved": false,
    "sbp_operation_id": "1027088AE4CB48CB81287833347A8777"
  },
  "recipient": {
    "account_id": "100500",
    "gateway_id": "100700"
  },
  "refundable": false,
  "test": false
}
```

**Шаг 3**. Дождитесь успешного завершения платежа: подождите, когда придет [уведомление от ЮKassa](https://yookassa.ru/developers/using-api/webhooks), или периодически отправляйте запросы, чтобы [получить информацию о платеже](https://yookassa.ru/developers/api#get_payment).

**Пример тела ответа**

**JSON**

```json
{
  "id": "264e0bc0-000f-5000-a000-109b22344b4c",
  "status": "succeeded",
  "paid": true,
  "amount": {
    "value": "2.00",
    "currency": "RUB"
  },
  "income_amount": {
    "value": "1.97",
    "currency": "RUB"
  },
  "captured_at": "2020-05-13T13:49:16.887Z",
  "created_at": "2020-05-13T13:37:04.389Z",
  "description": "Заказ №72",
  "income_amount": {
    "value": "2.00",
    "currency": "RUB"
  },
  "metadata": {},
  "payment_method": {
    "type": "sbp",
    "id": "264e0bc0-000f-5000-a000-109b22344b4c",
    "saved": false,
    "sbp_operation_id": "1027088AE4CB48CB81287833347A8777",
    "payer_bank_details": {
      "bic": "044525444",
      "bank_id": "100000000022"
    }
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
  "test": false
}
```

**Шаг 4**. Когда пользователь вернется на `return_url`, отобразите результат проведения платежа (успех или неудача) в зависимости от [статуса платежа](https://yookassa.ru/developers/payment-acceptance/getting-started/payment-process#lifecycle).

Готово!

Что почитать еще

[Основы проведения платежей](https://yookassa.ru/developers/payment-acceptance/getting-started/payment-process)

[Неуспешные платежи](https://yookassa.ru/developers/payment-acceptance/after-the-payment/declined-payments)

[Отправка чеков в налоговую](https://yookassa.ru/developers/payment-acceptance/receipts/basics)
