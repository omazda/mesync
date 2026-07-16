<!-- Источник: https://yookassa.ru/developers/payment-acceptance/integration-scenarios/smart-payment -->
<!-- Полная копия статьи официальной документации ЮKassa, сохранено 2026-07-02 -->

# Умный платеж

Самый простой способ интеграции с ЮKassa. Вам нужно только перенаправить пользователя на страницу ЮKassa, где он выберет подходящий способ, введет данные для оплаты и ее подтвердит. Чтобы принять оплату по этому сценарию, необходимо создать платеж и реализовать сценарий подтверждения [Redirect](https://yookassa.ru/developers/payment-acceptance/getting-started/payment-process#redirect).

![Пример платежной формы](https://static.yoomoney.ru/docops-static/images/developers-payments-smart-payment-desktop.image.ru.3f59938a.svg)

Пример платежной формы

Особенности

Умный платеж поддерживает все способы оплаты, кроме оплаты через [СберБанк Бизнес Онлайн](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/other/b2b-sberbank) и по [электронному сертификату](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/other/electronic-certificate/basics). На платежной форме будут отображаться те способы, которые подключены в вашем магазине.

Если проводите платежи в [две стадии](https://yookassa.ru/developers/payment-acceptance/getting-started/payment-process#capture-and-cancel) или сохраняете способ оплаты для [автоплатежей](https://yookassa.ru/developers/payment-acceptance/scenario-extensions/recurring-payments/basics), на платежной форме отображаются только те способы, которые поддерживают используемую вами опцию. [Подробнее о способах оплаты и их возможностях](https://yookassa.ru/developers/payment-acceptance/getting-started/payment-methods#all)

Пример: если вы подключили СБП и проводите платеж в [две стадии](https://yookassa.ru/developers/payment-acceptance/getting-started/payment-process#capture-and-cancel), то этот способ не отобразится на платежной форме, потому что не поддерживает эту опцию. Если это единственный способ оплаты, который есть в вашем магазине, то вы получите ошибку.

Оплата через [Mir Pay](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/mir-pay) будет доступна только для мобильных устройств на Android.

Если оплата не проходит, платежная форма обрабатывает неуспешные попытки: она отображает пользователю сообщение об ошибке и предлагает попробовать оплатить еще раз с повторным выбором способа оплаты. Доступно при оплате произвольной банковской картой, через Alfa Pay, Mir Pay, SberPay, T-Pay, СБП, сервис «Плати частями» и из кошелька ЮMoney. Вы можете отключить эту настройку через менеджера ЮKassa и обрабатывать [неуспешные попытки](https://yookassa.ru/developers/payment-acceptance/after-the-payment/declined-payments) самостоятельно.

Проведение платежа

**Шаг 1**. [Создайте платеж](https://yookassa.ru/developers/api#create_payment). Передайте в запросе объект `confirmation` с типом `redirect` и адресом страницы, на которую вернется пользователь после оплаты. Этот адрес должен быть абсолютным — с указанием протокола и домена сайта. Пример: `https://example.com/return_url`.

Данные о способе оплаты (`payment_method_data`, `payment_token`, `payment_method_id`) в запросе передавать не нужно.

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
          "value": "100.00",
          "currency": "RUB"
        },
        "capture": true,
        "confirmation": {
          "type": "redirect",
          "return_url": "https://www.example.com/return_url"
        },
        "description": "Заказ №1"
      }'
```

**PHP**

```php
<?php
    use YooKassa\Client;

    $client = new Client();
    $client->setAuth('<Идентификатор магазина>', '<Секретный ключ>');
    $payment = $client->createPayment(
        array(
            'amount' => array(
                'value' => 100.0,
                'currency' => 'RUB',
            ),
            'confirmation' => array(
                'type' => 'redirect',
                'return_url' => 'https://www.example.com/return_url',
            ),
            'capture' => true,
            'description' => 'Заказ №1',
        ),
        uniqid('', true)
    );
?>
```

**Python**

```python
import uuid

from yookassa import Configuration, Payment

Configuration.account_id = <Идентификатор магазина>
Configuration.secret_key = <Секретный ключ>

payment = Payment.create({
    "amount": {
        "value": "100.00",
        "currency": "RUB"
    },
    "confirmation": {
        "type": "redirect",
        "return_url": "https://www.example.com/return_url"
    },
    "capture": True,
    "description": "Заказ №1"
}, uuid.uuid4())
```

**Шаг 2**. Перенаправьте пользователя на `confirmation_url`, который придет в объекте [платежа](https://yookassa.ru/developers/api#payment_object). Это ссылка на страницу ЮKassa, на которой пользователь выберет нужный способ и введет данные для оплаты.

**Пример созданного объекта платежа**

**JSON**

```json
{
  "id": "23d93cac-000f-5000-8000-126628f15141",
  "status": "pending",
  "paid": false,
  "amount": {
    "value": "100.00",
    "currency": "RUB"
  },
  "confirmation": {
    "type": "redirect",
    "confirmation_url": "https://yoomoney.ru/api-pages/v2/payment-confirm/epl?orderId=23d93cac-000f-5000-8000-126628f15141"
  },
  "created_at": "2019-01-22T14:30:45.129Z",
  "description": "Заказ №1",
  "metadata": {},
  "recipient": {
    "account_id": "100500",
    "gateway_id": "100700"
  },
  "refundable": false,
  "test": false
}
```

**Шаг 3**. Дождитесь успешного завершения платежа: подождите, когда придет [уведомление](https://yookassa.ru/developers/using-api/webhooks) от ЮKassa, или периодически отправляйте запросы, чтобы получить [информацию о платеже](https://yookassa.ru/developers/api#get_payment).

Что почитать еще

[Выставление счетов по API](https://yookassa.ru/developers/payment-acceptance/scenario-extensions/invoices/basics)

[Отправка чеков в налоговую](https://yookassa.ru/developers/payment-acceptance/receipts/basics)

[Неуспешные платежи](https://yookassa.ru/developers/payment-acceptance/after-the-payment/declined-payments)

[Входящие уведомления](https://yookassa.ru/developers/using-api/webhooks)
