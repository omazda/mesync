<!-- Источник: https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/basics -->
<!-- Полная копия статьи официальной документации ЮKassa, сохранено 2026-07-02 -->

# Самостоятельная интеграция

Самый гибкий способ интеграции с ЮKassa: вы самостоятельно выбираете, какие способы оплаты отобразить пользователю, как их отсортировать, как пользователю подтвердить платеж.

Подготовка

При самостоятельной интеграции вы максимально контролируете взаимодействие с пользователем: ЮKassa берёт на себя только взаимодействие с платежными системами и сервисами. Вам необходимо самостоятельно реализовать следующие шаги процесса оплаты:

- выбор способа оплаты (если у вас несколько способов оплаты);
- получение от пользователя данных для оплаты выбранным способом ([для некоторых способов оплаты](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/basics#integration-options));
- объяснение пользователю, как подтвердить платеж ([для некоторых способов оплаты](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/basics#integration-options));
- сообщение пользователю результатов проведения платежа.

Проведение платежа

В этом разделе описана общая инструкция проведения платежа при самостоятельной интеграции. Ссылки на подробные инструкции по интеграции каждого способа оплаты приведены в разделе [Способы оплаты и варианты интеграции](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/basics#integration-options).

**Шаг 1**. Когда пользователь перейдет к оплате, отобразите ему вашу платежную форму. Дождитесь, когда пользователь выберет в вашем интерфейсе способ оплаты, при необходимости введет свои платежные данные (например, логин в интернет-банке) и подтвердит готовность продолжить оплатить (например, нажмет кнопку **Заплатить**).

**Шаг 2**. [Создайте платеж](https://yookassa.ru/developers/api#create_payment), передайте в запросе объект `payment_method_data` с выбранным способом оплаты и платежными данными и при необходимости объект `confirmation` с информацией о сценарии подтверждения. В запросе можно передать [дополнительные параметры](https://yookassa.ru/developers/api#create_payment), кроме `payment_token`, `payment_method_id`.

**Пример запроса при оплате банковской картой**

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
          "type": "bank_card"
        },
        "confirmation": {
          "type": "redirect",
          "return_url": "https://www.example.com/return_url"
        },
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
                'type' => 'bank_card',
            ),
            'confirmation' => array(
                'type' => 'redirect',
                'return_url' => 'https://www.example.com/return_url',
            ),
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
        "type": "bank_card"
    },
    "confirmation": {
        "type": "redirect",
        "return_url": "https://www.example.com/return_url"
    },
    "description": "Заказ №72"
})
```

**Шаг 3**. Реализуйте нужный сценарий подтверждения, например перенаправьте пользователя на `confirmation_url`, который придет в объекте [платежа](https://yookassa.ru/developers/api#payment_object).

**Пример созданного объекта платежа**

**JSON**

```json
{
  "id": "22c5d173-000f-5000-9000-1bdf241d4651",
  "status": "pending",
  "paid": false,
  "amount": {
    "value": "2.00",
    "currency": "RUB"
  },
  "confirmation": {
    "type": "redirect",
    "return_url": "https://www.example.com/return_url",
    "confirmation_url": "https://yoomoney.ru/payments/external/confirmation?orderId=22c5d173-000f-5000-9000-1bdf241d4651"
  },
  "created_at": "2021-04-12T13:59:33.681Z",
  "description": "Заказ №72",
  "metadata": {},
  "payment_method": {
    "type": "bank_card",
    "id": "22c5d173-000f-5000-9000-1bdf241d4651",
    "saved": false
  },
  "recipient": {
    "account_id": "100500",
    "gateway_id": "100700"
  },
  "refundable": false,
  "test": false
}
```

**Шаг 4**. Дождитесь успешного завершения платежа: подождите, когда придет [уведомление](https://yookassa.ru/developers/using-api/webhooks) от ЮKassa, или периодически отправляйте запросы, чтобы получить [информацию о платеже](https://yookassa.ru/developers/api#get_payment).

**Шаг 5**. Сообщите пользователю результат оплаты.

**Шаг 6**. Если вы проводите платеж в [две стадии](https://yookassa.ru/developers/payment-acceptance/getting-started/payment-process#capture-and-cancel), подтвердите списание оплаты или отмените платеж. И сообщите пользователю финальный результат платежа.

Готово!

Способы оплаты и варианты интеграции

Выберите подходящие вам варианты интеграции способа оплаты в зависимости от [сценария подтверждения платежа пользователем](https://yookassa.ru/developers/payment-acceptance/getting-started/payment-process#user-confirmation) и необходимости собирать платежные данные на вашей стороне. Если указано, что сбор платежных данных не нужен, то в `payment_method_data` необходимо передать только код способа оплаты.

| Способ оплаты | Вариант интеграции | Сценарий подтверждения | Сбор платежных данных |
| --- | --- | --- | --- |
| **Произвольные банковские карты** | | | |
| Банковская карта  `bank_card` | [Оплата банковской картой на готовой странице ЮKassa](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/bank-card#create-payment-redirect) | Redirect | ➖ |
| [Оплата с вводом данных на вашей стороне](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/bank-card#create-payment-with-card-data) (PCI DSS) | Redirect | ✔️ |
| **Платежи через приложения бесконтактной оплаты** | | | |
| Mir Pay  `bank_card` | Самостоятельной интеграции нет. Mir Pay будет доступен при оплате [банковской картой на готовой странице ЮKassa](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/bank-card#create-payment-redirect) совместно с другими способами оплаты. Отображать Mir Pay в виде отдельной кнопки можно только в виджете ЮKassa при определенных настройках. [Подробнее про Mir Pay](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/mir-pay) | | |
| **Электронные кошельки** | | | |
| ЮMoney  `yoo_money` | [Оплата с подтверждением на сайте ЮMoney](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/yoo-money#create-payment) | Redirect | ➖ |
| **Оплата через приложения банков** | | | |
| SberPay  `sberbank` | [Оплата с перенаправлением на страницу ЮKassa](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/sberpay#create-payment-redirect) | Redirect | ➖ |
| [Оплата с подтверждением через пуш‑уведомление или смс](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/sberpay#create-payment-external) | External | ✔️ |
| [Оплата с перенаправлением в приложение банка (для мобильных устройств)](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/sberpay#create-payment-mobile-application) | Mobile application | ➖ |
| [Оплата с перенаправлением в приложение банка (для десктопа)](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/sberpay#create-payment-qr) | QR-код | ➖ |
| Alfa Pay  `alfa_pay` | [Оплата в приложении Альфа Банка](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/other/alfa-pay) | Redirect | ➖ |
| T-Pay  `tinkoff_bank` | [Оплата в приложении Т-Банка](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/other/tinkoff-bank#create-payment) | Redirect | ➖ |
| СБП (Система быстрых платежей)  `sbp` | [Оплата через СБП на готовой странице ЮKassa](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/other/sbp#create-payment-redirect) | Redirect | ➖ |
| **Кредитование** | | | |
| «Покупки в кредит» от СберБанка  `sber_loan` | [Оплата в кредит или рассрочку от СберБанка на готовой странице ЮKassa](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/other/sber-loan#create-payment-redirect) | Redirect | ➖ |
| **BNPL-сервисы** | | | |
| Плати частями  `sber_bnpl` | [Оплата на готовой странице ЮKassa](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/other/sber-bnpl#ready-made-form) | Redirect | ➖ |
| [Оплата с вводом номера на вашей стороне](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/developers/payment-acceptance/integration-scenarios/manual-integration/other/sber-bnpl#merchant-form) | Redirect | ✔️ |
| **B2B-платежи** | | | |
| СберБанк Бизнес Онлайн  `b2b_sberbank` | [Оплата в сервисе СберБанк Бизнес Онлайн](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/other/b2b-sberbank#create-payment) | Redirect | ➖ |
| **Другие способы** | | | |
| Баланс телефона  `mobile_balance` | [Оплата с баланса мобильного телефона](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/other/mobile-balance#create-payment) | External | ✔️ |
| Наличные  `cash` | [Оплата по коду подтверждения](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/other/cash#create-payment) | Redirect | ✔️ (опционально) |
| Электронный сертификат  `electronic_certificate` | [Оплата по сертификату на готовой странице ЮKassa](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/other/electronic-certificate/ready-made-payment-form) | Redirect | ➖ |
| [Оплата по сертификату со сбором данных на вашей стороне](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/other/electronic-certificate/merchant-payment-form) (PCI DSS) | Redirect | ✔️ |

Что почитать еще

[Сценарии интеграции](https://yookassa.ru/developers/payment-acceptance/getting-started/selecting-integration-scenario)

[Отправка чеков в налоговую](https://yookassa.ru/developers/payment-acceptance/receipts/basics)

[Неуспешные платежи](https://yookassa.ru/developers/payment-acceptance/after-the-payment/declined-payments)

[Входящие уведомления](https://yookassa.ru/developers/using-api/webhooks)
