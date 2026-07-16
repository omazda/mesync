<!-- Источник: https://yookassa.ru/developers/payment-acceptance/getting-started/quick-start -->
<!-- Полная копия статьи официальной документации ЮKassa, сохранено 2026-07-02 -->

# Быстрый старт

API ЮKassa позволяет принимать платежи онлайн — в вебе и на мобильных устройствах. Эта статья поможет вам принять первый платеж, при этом вашим покупателям будут доступны все способы оплаты, которые вы подключили.

Подготовка

Чтобы начать работать с ЮKassa, вам нужно [зарегистрироваться](https://yookassa.ru/joinups) и получить доступ к личному кабинету. Для аутентификации запросов в API вам потребуется секретный ключ и идентификатор магазина из личного кабинета. [Подробнее об основах работы с API ЮKassa](https://yookassa.ru/developers/using-api/interaction-format)

Вы можете провести этот платеж в тестовом магазине. При оплате всё проходит, как при настоящих платежах, но деньги никуда не переводятся. Протестировать можно только два способа оплаты: банковские карты и ЮMoney. [Подробнее о тестовом режиме](https://yookassa.ru/developers/payment-acceptance/testing-and-going-live/testing)

Если вы хотите оценить возможности API, но у вас пока нет личного кабинета в ЮKassa, [зарегистрируйтесь по этой ссылке](https://yookassa.ru/joinups?createTestShop=true). Это самый простой способ получить тестовый магазин. Указывать данные компании и подписывать договор не нужно.

Шаг 1. Создайте платеж

Платеж — главная сущность API ЮKassa. Чтобы его создать, вам понадобятся сумма платежа и URL, на который пользователь вернется после оплаты. Также вам нужно передать параметр `capture` со значением `true`. Это значит, что вы получите деньги сразу после оплаты (при значении `false` нужная сумма заблокируется на счете пользователя, и после этого вы можете ее [списать](https://yookassa.ru/developers/payment-acceptance/getting-started/payment-process#capture-and-cancel) в удобное вам время).

Если хотите добавить описание платежа, которое вы увидите в личном кабинете, а пользователь — при оплате, передайте его в параметре `description`. Описание должно быть не более 128 символов.

Отправьте ЮKassa запрос и передайте в нём данные для создания платежа, данные для аутентификации (идентификатор магазина и секретный ключ) и [ключ идемпотентности](https://yookassa.ru/developers/using-api/interaction-format#idempotence) (подойдет любое случайное значение).

Все запросы к API ЮKassa необходимо отправлять с вашего сервера. Для взаимодействия с ЮKassa вы можете использовать готовые серверные [SDK](https://yookassa.ru/developers/using-api/using-sdks).

**Пример запроса на создание платежа**

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

Шаг 2. Отправьте пользователя на страницу оплаты

В теле ответа от ЮKassa вы получите созданный [объект платежа](https://yookassa.ru/developers/api#payment_object) в статусе `pending`. Для оплаты перенаправьте пользователя на `confirmation_url`.

Redirect — это основной [сценарий подтверждения](https://yookassa.ru/developers/payment-acceptance/getting-started/payment-process#user-confirmation) платежа пользователем. В некоторых случаях подтверждение пользователем не требуется или может проходить по другому сценарию.

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

Если вы создаете платеж для тестового магазина, для оплаты используйте одну из [тестовых карт](https://yookassa.ru/developers/payment-acceptance/testing-and-going-live/testing#test-bank-card), например `5555``5555``5555``4444` (подойдет любой код CVC и дата из будущего).

После успешной оплаты (и если что-то пойдет не так) ЮKassa вернет пользователя на `return_url`, который вы передали при создании платежа.

Шаг 3. Дождитесь успешного выполнения платежа

Платеж можно считать успешным, как только он перешел в статус `succeeded`. Если пользователь передумает платить или [что-то пойдет не так](https://yookassa.ru/developers/payment-acceptance/after-the-payment/declined-payments), платеж перейдет в статус `canceled`.

Чтобы узнать статус платежа, подпишитесь на [уведомления](https://yookassa.ru/developers/using-api/webhooks) от ЮKassa.

Также вы можете следить за статусом, запрашивая [информацию о платеже](https://yookassa.ru/developers/api#get_payment) с удобной для вас периодичностью (например, после того, как пользователь вернулся на `return_url`). Для этого вам понадобится идентификатор платежа (значение параметра `id` в созданном объекте платежа).

**Ура, вы приняли первый платеж!**

В этом примере пользователь выбирал способы оплаты и вводил данные на стороне ЮKassa. Этот сценарий называется Умный платеж. Если для ваших задач он не подходит, вы можете выбрать другой [сценарий интеграции](https://yookassa.ru/developers/payment-acceptance/getting-started/selecting-integration-scenario).

Помните, что для приема реальных платежей нужно использовать идентификатор и секретный ключ настоящего магазина.

Что почитать еще

[Сценарии интеграции](https://yookassa.ru/developers/payment-acceptance/getting-started/selecting-integration-scenario)

[Неуспешные платежи](https://yookassa.ru/developers/payment-acceptance/after-the-payment/declined-payments)

[Способы оплаты](https://yookassa.ru/developers/payment-acceptance/getting-started/payment-methods)

[Отправка чеков в налоговую](https://yookassa.ru/developers/payment-acceptance/receipts/basics)
