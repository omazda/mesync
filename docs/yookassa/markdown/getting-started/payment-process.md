<!-- Источник: https://yookassa.ru/developers/payment-acceptance/getting-started/payment-process -->
<!-- Полная копия статьи официальной документации ЮKassa, сохранено 2026-07-02 -->

# Процесс платежа

В процессе платежа пользователь совершает следующие действия:

1. выбирает способ оплаты;
2. вводит данные для оплаты выбранным способом;
3. при необходимости подтверждает платеж (например, проходит аутентификацию по 3-D Secure или отвечает на смс).

В ЮKassa есть несколько [сценариев проведения оплаты](https://yookassa.ru/developers/payment-acceptance/getting-started/selecting-integration-scenario). Сценарии различаются в зависимости от того, где пользователь выбирает способ оплаты и вводит платежные данные. В некоторых случаях пользователю нужно дополнительно подтвердить, что он согласен на оплату выбранным способом. Для этого вам будет необходимо реализовать определенный [сценарий подтверждения](https://yookassa.ru/developers/payment-acceptance/getting-started/payment-process#user-confirmation).

Каждый платеж можно проводить в [две стадии](https://yookassa.ru/developers/payment-acceptance/getting-started/payment-process#capture-and-cancel). Обычно, если пользователь внес оплату, ЮKassa сразу списывает деньги и перечисляет их на ваш расчетный счет. В двухстадийных платежах вы можете регулировать, в какой момент списать деньги и завершить платеж.

Создание платежа

[Платеж](https://yookassa.ru/developers/api#payment_object) — основная сущность API ЮKassa для приема платежей.

Чтобы создать платеж, вам нужно передать в [запросе](https://yookassa.ru/developers/api#create_payment):

- данные для [аутентификации](https://yookassa.ru/developers/using-api/interaction-format#auth);
- [ключ идемпотентности](https://yookassa.ru/developers/using-api/interaction-format#idempotence) (подойдет любое случайное значение);
- сумму платежа;
- данные для оплаты (зависят от выбранного [сценария проведения платежа](https://yookassa.ru/developers/payment-acceptance/getting-started/selecting-integration-scenario)).

ЮKassa умеет принимать платежи в [две стадии](https://yookassa.ru/developers/payment-acceptance/getting-started/payment-process#capture-and-cancel), но для простоты вы можете провести обычный платеж (параметр `capture` со значением `true`). Это значит, что сразу после оплаты платеж успешно завершится и перейдет в статус `succeeded`.

Также вы можете передать дополнительные данные, например номер заказа в вашей системе. ЮKassa вернет их без изменений. Данные необходимо передавать в объекте `metadata` в виде набора пар «ключ-значение».

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
        "description": "Заказ №37",
        "metadata": {
          "order_id": "37"
        }
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
            'description' => 'Заказ №37',
            'metadata' => array(
                'order_id' => '37',
            )
        ),
        uniqid('', true)
    );
?>
```

**Python**

```python
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
    "description": "Заказ №37",
    "metadata": {
      "order_id": "37"
    }
})
```

В ответ на запрос придет созданный объект [платежа](https://yookassa.ru/developers/api#payment_object).

**Пример созданного объекта платежа**

**JSON**

```json
{
  "id": "2419a771-000f-5000-9000-1edaf29243f2",
  "status": "pending",
  "paid": false,
  "amount": {
    "value": "100.00",
    "currency": "RUB"
  },
  "confirmation": {
    "type": "redirect",
    "confirmation_url": "https://yoomoney.ru/api-pages/v2/payment-confirm/epl?orderId=2419a771-000f-5000-9000-1edaf29243f2"
  },
  "created_at": "2019-03-12T11:10:41.802Z",
  "description": "Заказ №37",
  "metadata": {
    "order_id": "37"
  },
  "recipient": {
    "account_id": "100500",
    "gateway_id": "100700"
  },
  "refundable": false,
  "test": false
}
```

Подтверждение платежа пользователем

Для большинства [способов оплаты](https://yookassa.ru/developers/payment-acceptance/getting-started/payment-methods) после создания платежа вам нужно получить согласие от пользователя, что он готов заплатить. Для этого пользователю нужно дополнительно что-то сделать, например пройти 3-D Secure при оплате банковской картой, подтвердить оплату в платежном сервисе партнера или оплатить счет в интернет-банке.

Если от пользователя нужно получить подтверждение, созданный [платеж](https://yookassa.ru/developers/api#payment_object) сначала перейдет в статус `pending`. В следующие статусы (`succeeded` или `waiting_for_capture`) платеж перейдет, только если пользователь согласится внести оплату.

Если подтверждение не требуется, платеж сразу перейдет в статус `succeeded` или `waiting_for_capture` (если вы проводите платеж в [две стадии](https://yookassa.ru/developers/payment-acceptance/getting-started/payment-process#capture-and-cancel)).

Если пользователь передумает платить или что-то пойдет не так (например, на счете не окажется нужной суммы), платеж [отменится](https://yookassa.ru/developers/payment-acceptance/after-the-payment/declined-payments) и перейдет в статус `canceled`.

Пользователь может подтвердить платеж только за [определенный срок](https://yookassa.ru/developers/payment-acceptance/getting-started/payment-methods#payment-term). Если он не сделает этого, ЮKassa отменит платеж, указав причину `expired_on_confirmation`. [Подробнее о причинах отмены платежа](https://yookassa.ru/developers/payment-acceptance/after-the-payment/declined-payments#cancellation-details-reason)

Сценарии подтверждения

ЮKassa поддерживает несколько сценариев подтверждения: Redirect, External, QR-код, Embedded и Mobile application.

**Сценарий подтверждения Redirect**: пользователю необходимо что-то сделать на странице ЮKassa или ее партнера (например, ввести данные банковской карты или пройти аутентификацию по 3-D Secure). Вам нужно перенаправить пользователя на `confirmation_url`, полученный в [платеже](https://yookassa.ru/developers/api#payment_object). При успешной оплате (и если что-то пойдет не так) ЮKassa вернет пользователя на `return_url`, который вы отправите в запросе на [создание платежа](https://yookassa.ru/developers/api#create_payment).

**Сценарий подтверждения External**: для подтверждения платежа пользователю необходимо совершить действия во внешней системе (например, ответить на смс). От вас требуется только сообщить пользователю о дальнейших шагах.

**Сценарий подтверждения QR-код**: для подтверждения платежа пользователю необходимо просканировать QR-код. От вас требуется сгенерировать QR-код, используя любой доступный инструмент, и отобразить его на странице оплаты.

**Сценарий подтверждения Embedded**: действия, необходимые для подтверждения платежа, будут зависеть от способа оплаты, который пользователь выберет в [виджете ЮKassa](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/basics). Подтверждение от пользователя получит ЮKassa — вам необходимо только встроить виджет к себе на страницу.

**Сценарий подтверждения Mobile application**: для подтверждения платежа пользователю необходимо совершить действия в мобильном приложении (например, в приложении интернет-банка). Вам нужно перенаправить пользователя на `confirmation_url`, полученный в [платеже](https://yookassa.ru/developers/api#payment_object). При успешной оплате (и если что-то пойдет не так) ЮKassa вернет пользователя на `return_url`, который вы отправите в запросе на [создание платежа](https://yookassa.ru/developers/api#create_payment). Подтвердить платеж по этому сценарию можно только на мобильном устройстве (из мобильного приложения или с мобильной версии сайта).

Один способ оплаты может поддерживать несколько сценариев подтверждения. Особенности подтверждения платежа при оплате разными способами описаны в разделе [Способы оплаты](https://yookassa.ru/developers/payment-acceptance/getting-started/payment-methods).

Двухстадийные платежи

Если хотите использовать эту опцию, проверьте, что нужные вам способы оплаты поддерживают холдирование. [Подробнее о способах оплаты и их возможностях](https://yookassa.ru/developers/payment-acceptance/getting-started/payment-methods#all)

Вы можете проводить платежи в две стадии:

1. **Холдирование** (предавторизация): пользователь вносит оплату, и деньги замораживаются — например, на его банковской карте или в электронном кошельке (зависит от способа, которым он платит).
2. **Списание**: замороженные деньги списываются по вашему запросу.

Чтобы создать двухстадийный платеж, передайте в запросе на [создание платежа](https://yookassa.ru/developers/api#create_payment) параметр `capture` со значением `false`.

**Пример запроса на создание двухстадийного платежа**

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
        "capture": false,
        "confirmation": {
          "type": "redirect",
          "return_url": "https://www.example.com/return_url"
        },
        "description": "Заказ №37",
        "metadata": {
          "order_id": "37"
        }
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
            'capture' => false,
            'description' => 'Заказ №37',
            'metadata' => array(
                'order_id' => '37',
            )
        ),
        uniqid('', true)
    );
?>
```

**Python**

```python
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
    "capture": False,
    "description": "Заказ №37",
    "metadata": {
      "order_id": "37"
    }
})
```

Холдирование

Как только деньги будут авторизованы, платеж перейдет в статус `waiting_for_capture`. Этот статус означает, что вам нужно принять решение: списать оплату или отменить платеж. Если вы не сделали это за определенное время, платеж перейдет в статус `canceled`, а деньги автоматически вернутся пользователю.

В зависимости от [способа оплаты](https://yookassa.ru/developers/payment-acceptance/getting-started/payment-methods) у вас есть от 2 часов до 7 дней, чтобы списать деньги. Точное время передается в параметре `expires_at`. Если вы ничего не сделаете с платежом за этот срок, ЮKassa отменит платеж, указав причину `expired_on_capture`. [Подробнее о причинах отмены платежа](https://yookassa.ru/developers/payment-acceptance/after-the-payment/declined-payments#cancellation-details-reason)

Списание оплаты

Когда платеж перешел в статус `waiting_for_capture`, вы можете подтвердить платеж — списать оплату [полностью](https://yookassa.ru/developers/payment-acceptance/getting-started/payment-process#capture-full) или [частично](https://yookassa.ru/developers/payment-acceptance/getting-started/payment-process#capture-partly).

Полное списание

Доступно для всех способов оплаты, которые поддерживают холдирование. [Подробнее о способах оплаты и их возможностях](https://yookassa.ru/developers/payment-acceptance/getting-started/payment-methods#all)

Чтобы списать всю сумму, отправьте ЮKassa запрос на [подтверждение платежа](https://yookassa.ru/developers/api#capture_payment) с пустым телом запроса.

**Пример запроса на списание всей суммы платежа**

**cURL**

```bash
curl https://api.yookassa.ru/v3/payments/{payment_id}/capture \
  -X POST \
  -u <Идентификатор магазина>:<Секретный ключ> \
  -H 'Idempotence-Key: <Ключ идемпотентности>' \
  -H 'Content-Type: application/json'
```

**PHP**

```php
<?php
    $payment = $notification->getObject();
    $client->capturePayment(
        array(
            'amount' => $payment->amount,
        ),
        $payment->id,
        uniqid('', true)
    );
?>
```

**Python**

```python
from yookassa import Payment

Payment.capture(payment_id)
```

Частичное списание

Доступно для этих способов оплаты: банковская карта, кошелек ЮMoney, SberPay, Mir Pay, T‑Pay, «Покупки в кредит» от СберБанка, платежи через сервис «Плати частями».

Если вы проводите [автоплатежи](https://yookassa.ru/developers/payment-acceptance/scenario-extensions/recurring-payments/basics), при сохранении способа оплаты [во время платежа](https://yookassa.ru/developers/payment-acceptance/scenario-extensions/recurring-payments/save-payment-method/save-during-payment) можно списать часть суммы для всех способов оплаты, при повторном платеже (рекурренте) — для всех, кроме кошелька ЮMoney.

Чтобы списать только часть суммы, отправьте ЮKassa запрос на [подтверждение платежа](https://yookassa.ru/developers/api#capture_payment) и передайте в нём в объект `amount` с нужной суммой. Если сумма списания меньше суммы платежа, остаток автоматически вернется пользователю.

**Пример запроса на частичное списание**

**cURL**

```bash
curl https://api.yookassa.ru/v3/payments/{payment_id}/capture \
    -X POST \
    -u <Идентификатор магазина>:<Секретный ключ> \
    -H 'Idempotence-Key: <Ключ идемпотентности>' \
    -H 'Content-Type: application/json' \
    -d '{
          "amount": {
            "value": "2.00",
            "currency": "RUB"
          }
        }'
```

**PHP**

```php
<?php
    $paymentId = '215d8da0-000f-50be-b000-0003308c89be';
    $idempotenceKey = uniqid('', true);
    $response = $client->capturePayment(
        array(
            'amount' => array(
                'value' => '2.00',
                'currency' => 'RUB',
            ),
        ),
        $paymentId,
        $idempotenceKey
    );
?>
```

**Python**

```python
from yookassa import Payment
import uuid

payment_id = '215d8da0-000f-50be-b000-0003308c89be'
idempotence_key = str(uuid.uuid4())
response = Payment.capture(
  payment_id,
  {
    "amount": {
      "value": "2.00",
      "currency": "RUB"
    }
  },
  idempotence_key
)
```

Отмена платежа

Если вы хотите отказаться от оплаты, отправьте ЮKassa запрос на [отмену платежа](https://yookassa.ru/developers/api#cancel_payment). Платеж перейдет в статус `canceled`, и деньги вернутся пользователю В этом случае ЮKassa не будет удерживать комиссию за проведение платежа.

Вы можете отменить только платежи в статусе `waiting_for_capture`. Если платеж перешел в статус `succeeded`, вы можете создать [возврат](https://yookassa.ru/developers/payment-acceptance/after-the-payment/refunds).

**Пример запроса на отмену платежа**

**cURL**

```bash
curl https://api.yookassa.ru/v3/payments/{payment_id}/cancel \
  -X POST \
  -u <Идентификатор магазина>:<Секретный ключ> \
  -H 'Idempotence-Key: <Ключ идемпотентности>' \
  -H 'Content-Type: application/json' \
  -d '{

      }'
```

**PHP**

```php
<?php
    $paymentId = '215d8da0-000f-50be-b000-0003308c89be';
    $idempotenceKey = uniqid('', true);
    $response = $client->cancelPayment(
        $paymentId,
        $idempotenceKey
    );
?>
```

**Python**

```python
from yookassa import Payment
import uuid

payment_id = '215d8da0-000f-50be-b000-0003308c89be'
idempotence_key = str(uuid.uuid4())
response = Payment.cancel(
  payment_id,
  idempotence_key
)
```

Жизненный цикл платежа

Жизненный цикл платежа зависит от настроек вашего магазина и параметров, которые вы передадите в запросе на [создание платежа](https://yookassa.ru/developers/api#create_payment). Каждому этапу жизненного цикла соответствует статус [платежа](https://yookassa.ru/developers/api#payment_object).

Статусы платежа

`pending` — платеж создан и ожидает [действий от пользователя](https://yookassa.ru/developers/payment-acceptance/getting-started/payment-process#user-confirmation). В некоторых случаях платеж может оставаться в этом статусе даже после подтверждения платежа пользователем:

- Если вы используете [стороннюю онлайн-кассу для работы по 54-ФЗ](https://yookassa.ru/developers/payment-acceptance/receipts/54fz/other-services/basics) и сценарий [Сначала чек, потом платеж](https://yookassa.ru/developers/payment-acceptance/receipts/54fz/other-services/basics#payment-after-receipt), то платеж может находиться в статусе `pending` до тех пор, пока онлайн-касса не сообщит об успешной или неуспешной регистрации чека.
- Если вы проводите платеж способом [«Покупки в кредит» от СберБанка](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/other/sber-loan) и применяется [охлаждение кредита или рассрочки](https://yookassa.ru/docs/support/payments/credit-purchases-by-sberbank-with-cooling-off), то платеж будет находиться в статусе `pending`, пока не закончится период охлаждения (срок указывается в параметре `suspended_until`) или пока пользователь не откажется от кредита или рассрочки в приложении СберБанка.

Из статуса `pending` платеж может перейти в `succeeded`, `waiting_for_capture` (при двухстадийной оплате) или `canceled` (если что-то пошло не так).

`waiting_for_capture` — платеж оплачен, деньги авторизованы и ожидают [списания](https://yookassa.ru/developers/payment-acceptance/getting-started/payment-process#capture-and-cancel). Из этого статуса платеж может перейти в `succeeded` (если вы списали оплату) или `canceled` (если вы отменили платеж или что-то пошло не так).

`succeeded` — платеж успешно завершен, деньги будут перечислены на ваш расчетный счет в соответствии с вашим договором с ЮKassa. Это финальный и неизменяемый статус.

`canceled` — платеж отменен. Вы увидите этот статус, если вы отменили платеж самостоятельно, истекло время на принятие платежа или платеж был отклонен ЮKassa или платежным провайдером. Это финальный и неизменяемый статус.

В зависимости от вашего процесса часть статусов может быть пропущена, но их последовательность не меняется.

Чтобы узнать статус платежа, периодически отправляйте запросы, чтобы получить [информацию о платеже](https://yookassa.ru/developers/api#get_payment), или подождите, когда придет [уведомление](https://yookassa.ru/developers/using-api/webhooks) от ЮKassa.

Что почитать еще

[Отправка чеков в налоговую](https://yookassa.ru/developers/payment-acceptance/receipts/basics)

[Неуспешные платежи](https://yookassa.ru/developers/payment-acceptance/after-the-payment/declined-payments)

[Входящие уведомления](https://yookassa.ru/developers/using-api/webhooks)

[Тестирование платежей](https://yookassa.ru/developers/payment-acceptance/testing-and-going-live/testing)
