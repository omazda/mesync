<!-- Источник: https://yookassa.ru/developers/using-api/webhooks -->
<!-- Полная копия статьи официальной документации ЮKassa, сохранено 2026-07-04 -->

# Входящие уведомления

Если вы хотите отслеживать состояние объектов, например платежей или возвратов, вы можете подписаться на уведомления (webhook, callback) о таких событиях.

Уведомления пригодятся в тех случаях, когда объект API изменяется без вашего участия. Например, если пользователю нужно [подтвердить платеж](https://yookassa.ru/developers/payment-acceptance/getting-started/payment-process#user-confirmation), процесс оплаты может занять от нескольких минут до нескольких часов. Вместо того, чтобы всё это время периодически отправлять [GET-запросы](https://yookassa.ru/developers/api#get_payment), чтобы узнать статус платежа, вы можете просто дожидаться уведомления от ЮKassa.

[События](https://yookassa.ru/developers/using-api/webhooks#events), которые вы можете отслеживать, зависят от используемого платежного решения. Способ [настройки](https://yookassa.ru/developers/using-api/webhooks#configuration) уведомлений зависит от метода [аутентификации](https://yookassa.ru/developers/using-api/interaction-format#auth) запросов.

О событиях в ЮKassa

Событие в ЮKassa — изменение статуса объекта. Вы можете отслеживать события платежей, способов оплаты, возвратов, выплат и сделок.

События, на которые можно подписаться, зависят от [платежного решения](https://yookassa.ru/developers/using-api/webhooks#available-events), которое вы используете (например, платежи в интернете или в офлайне, Безопасная сделка, Партнерская программа). Чтобы следить за событиями, [подпишитесь](https://yookassa.ru/developers/using-api/webhooks#configuration) на них.

Как только произойдет событие, на которое вы подписались, вам придет [уведомление](https://yookassa.ru/developers/using-api/webhooks#using). Вам нужно подтвердить его получение. В уведомлении будут все данные об объекте на момент, когда его статус изменился. [Подробнее об использовании уведомлений](https://yookassa.ru/developers/using-api/webhooks#using)

Название события формируется по шаблону `<объект>.<статус>` и состоит из двух частей:

- объект, с которым произошло событие, например: `payment` — платеж, `refund` — возврат, `payout` — выплата, `deal` — сделка, `payment_method` — способ оплаты;
- статус, в который перешел объект, например: `succeeded`, `wayting_for_capture`, `canceled`, `closed`, `active`. Подробнее о статусах для разных объектов смотрите в [Справочнике API](https://yookassa.ru/developers/api).

Пример: `payment.succeeded` — платеж перешел в статус `succeeded`.

Доступные события

| Событие | [Платежи](https://yookassa.ru/developers/payment-acceptance/overview) | [Выплаты](https://yookassa.ru/developers/payouts/overview) | [Сплитование платежей](https://yookassa.ru/developers/solutions-for-platforms/split-payments/basics) | [Партнерская программа](https://yookassa.ru/developers/solutions-for-platforms/partners-api/basics) | [Безопасная сделка](https://yookassa.ru/developers/solutions-for-platforms/safe-deal/basics) |
| --- | --- | --- | --- | --- | --- |
| **Платежи** | | | | |
| payment.waiting\_for\_capture | ✅ | ❌ | ✅ | ✅ | ✅ |
| payment.succeeded | ✅ | ❌ | ✅ | ✅ | ✅ |
| payment.canceled | ✅ | ❌ | ✅ | ✅ | ✅ |
| **Возвраты** | | | | |
| refund.succeeded | ✅ | ❌ | ✅ | ✅ | ✅ |
| **Выплаты** | | | | |
| payout.succeeded | ❌ | ✅ | ❌ | ❌ | ✅ |
| payout.canceled | ❌ | ✅ | ❌ | ❌ | ✅ |
| **Сделки** | | | | |
| deal.closed | ❌ | ❌ | ❌ | ❌ | ✅ |
| **Способы оплаты** — используются для [привязки на нулевую сумму](https://yookassa.ru/developers/payment-acceptance/scenario-extensions/recurring-payments/save-payment-method/save-without-payment/basics). В решениях, которые отмечены в таблице, после успешной привязки вы сохраняете идентификатор способа оплаты и используете его для проведения платежей или выплат. | | | | | |
| payment\_method.active | ✅ | ✅ | ✅ | ✅ | ✅ |

Настройка

В ЮKassa есть два способа настройки уведомлений в зависимости от метода [аутентификации](https://yookassa.ru/developers/using-api/interaction-format#auth) запросов:

- Если вы используете [HTTP Basic Auth](https://yookassa.ru/developers/using-api/webhooks#configuration-Basic-Auth-payment-solutions), настраивать уведомления нужно в личном кабинете.
- Если вы используете [OAuth](https://yookassa.ru/developers/using-api/webhooks#configuration-OAuth-partners), настроить уведомления можно только по API.

Для платежных решений с HTTP Basic Auth

Если вы используете платежное решение с HTTP Basic Auth ([платежи в интернете](https://yookassa.ru/developers/payment-acceptance/overview), [платежи в офлайне](https://yookassa.ru/developers/offline-payments/basics), [выплаты](https://yookassa.ru/developers/payouts/overview), [Сплитование платежей](https://yookassa.ru/developers/solutions-for-platforms/split-payments/basics), [Безопасная сделка](https://yookassa.ru/developers/solutions-for-platforms/safe-deal/basics)), вы можете подписаться на уведомления от ЮKassa в личном кабинете.

Для этого в разделе [Интеграция — HTTP-уведомления](https://yookassa.ru/my/http-notifications-settings) укажите URL для уведомлений и события, которые хотите отслеживать.

Требования к URL для уведомлений — протокол [HTTPS](https://yookassa.ru/docs/support/security) и TCP-порт 443 или 8443. TLS/SSL-сертификат подойдет любой: самоподписанный или выданный центром сертификации. Версия TLS/SSL — 1.2 или выше.

Чтобы отписаться от уведомлений, в разделе [Интеграция — HTTP-уведомления](https://yookassa.ru/my/http-notifications-settings) отключите ненужные события.

Для партнерской программы (OAuth)

Если вы участвуете в [партнерской программе](https://yookassa.ru/developers/solutions-for-platforms/partners-api/basics), вы можете подписаться на уведомления только по API.

Вы можете отслеживать только события платежей и возвратов. Для каждого [события](https://yookassa.ru/developers/using-api/webhooks#available-events), которое вы хотите отслеживать, необходимо создать [объект webhook](https://yookassa.ru/developers/api#webhook_object). Для этого передайте в [запросе](https://yookassa.ru/developers/api#create_webhook) событие, на которое вы хотите подписаться, и URL для уведомлений.

Уведомления будут приходить только для тех объектов, которые созданы вашим приложением.

Для каждого OAuth-токена нужно создавать свой набор webhook.

**Пример запроса на создание объекта webhook**

**cURL**

```bash
curl https://api.yookassa.ru/v3/webhooks \
  -X POST \
  -H 'Authorization: Bearer <oauth_token>' \
  -H 'Idempotence-Key: <Ключ идемпотентности>' \
  -H 'Content-Type: application/json' \
  -d '{
        "event": "payment.succeeded",
        "url": "https://www.example.com/notification_url"
      }'
```

**PHP**

```php
<?php
    use YooKassa\Client;
    use YooKassa\Model\NotificationEventType;

    $client = new Client();
    $client->setAuthToken('<Bearer Token>');

    $response = $client->addWebhook([
        "event" => NotificationEventType::PAYMENT_SUCCEEDED,
        "url"   => "https://www.example.com/notification_url",
    ]);
?>
```

**Python**

```python
from yookassa import Configuration, Webhook

Configuration.configure_auth_token('<Bearer Token>')

response = Webhook.add({
    "event": "payment.succeeded",
    "url": "https://www.example.com/notification_url",
})
```

**Пример тела ответа**

**JSON**

```json
{
  "id": "wh-e44e8088-bd73-43b1-959a-954f3a7d0c54",
  "event": "payment.succeeded",
  "url": "https://www.example.com/notification_url"
}
```

С помощью API вы также можете [просмотреть список](https://yookassa.ru/developers/api#get_webhook_list) отслеживаемых событий и [отписаться](https://yookassa.ru/developers/api#delete_webhook) от тех, которые не нужны.

Чтобы отписаться от уведомлений о событии для переданного OAuth-токена, удалите соответствующий [объект webhook](https://yookassa.ru/developers/api#webhook_object). Для этого передайте в [запросе](https://yookassa.ru/developers/api#delete_webhook) его идентификатор.

Использование

Как только произойдет событие, на которое вы подписались, на URL, который вы указали при настройке, придет уведомление.

**Параметры тела уведомления**

| Параметр | Тип | Описание |
| --- | --- | --- |
| type | string | Тип объекта. Фиксированное значение — `notification` (уведомление).  Обязательный параметр |
| event | string | [Событие](https://yookassa.ru/developers/using-api/webhooks#events), о котором уведомляет ЮKassa. Пример: `payment.waiting_for_capture`.  Обязательный параметр |
| object | object | Объект, с которым произошло указанное событие. Например, если в параметре `event` указано событие `payment.waiting_for_capture`, то в `object` вернется [объект платежа](https://yookassa.ru/developers/api#payment_object), статус которого изменился на `waiting_for_capture`.  Объект содержит данные, актуальные на тот момент, когда произошло событие. Параметры объектов описаны в [Справочнике API](https://yookassa.ru/developers/api).  Обязательный параметр |

**Пример тела уведомления payment.waiting\_for\_capture**

**JSON**

```json
{
  "type": "notification",
  "event": "payment.waiting_for_capture",
  "object": {
    "id": "22d6d597-000f-5000-9000-145f6df21d6f",
    "status": "waiting_for_capture",
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
    "created_at": "2018-07-10T14:27:54.691Z",
    "description": "Заказ №72",
    "expires_at": "2018-07-17T14:28:32.484Z",
    "metadata": {},
    "payment_method": {
      "type": "bank_card",
      "id": "22d6d597-000f-5000-9000-145f6df21d6f",
      "saved": false,
      "card": {
        "first6": "555555",
        "last4": "4444",
        "expiry_month": "07",
        "expiry_year": "2021",
        "card_type": "MasterCard",
      "issuer_country": "RU",
      "issuer_name": "Sberbank"
      },
      "title": "Bank card *4444"
    },
    "refundable": false,
    "test": false
  }
}
```

Вам нужно подтвердить, что вы получили уведомление. Для этого ответьте кодом состояния HTTP 200. ЮKassa проигнорирует всё, что будет находиться в теле или заголовках ответа. Ответы с любыми другими кодами состояний HTTP будут считаться невалидными, и ЮKassa продолжит доставлять уведомление в течение 24 часов, начиная с момента, когда событие произошло.

Проверка подлинности уведомлений

Когда получите уведомление, проверьте его подлинность, например по статусу объекта или по IP-адресу. Это поможет защититься от атак, основанных на поддельных уведомлениях.

Проверка статуса объекта

Проверьте текущий статус объекта, чтобы убедиться, что статус из уведомления актуален.

Проверка IP-адреса

Проверьте IP-адрес, с которого пришло уведомление. ЮKassa может присылать уведомления с любого IP-адреса из списка:

- 185.71.76.0/27
- 185.71.77.0/27
- 77.75.153.0/25
- 77.75.156.11
- 77.75.156.35
- 77.75.154.128/25
- 2a02:5180::/32

Обработка с помощью SDK

Вы можете обрабатывать уведомления с помощью наших [серверных SDK](https://yookassa.ru/developers/using-api/using-sdks):

1. Получите данные из POST-запроса от ЮKassa.
2. Создайте объект класса уведомлений в зависимости от события.
3. Получите объект платежа.

**Пример обработки уведомления с помощью SDK**

**PHP**

```php
// Получите данные из POST-запроса от ЮKassa

<?php
    $source = file_get_contents('php://input');
    $requestBody = json_decode($source, true);
?>

// Создайте объект класса уведомлений в зависимости от события
// NotificationSucceeded, NotificationWaitingForCapture,
// NotificationCanceled,  NotificationRefundSucceeded

<?php
    use YooKassa\Model\Notification\NotificationSucceeded;
    use YooKassa\Model\Notification\NotificationWaitingForCapture;
    use YooKassa\Model\NotificationEventType;

    try {
      $notification = ($requestBody['event'] === NotificationEventType::PAYMENT_SUCCEEDED)
        ? new NotificationSucceeded($requestBody)
        : new NotificationWaitingForCapture($requestBody);
    } catch (Exception $e) {
        // Обработка ошибок при неверных данных
    }
?>

// Получите объект платежа

<?php
    $payment = $notification->getObject();
?>
```

**Python**

```python
# Получите данные из POST-запроса от ЮKassa.
import json
from django.http import HttpResponse
from yookassa.domain.notification import WebhookNotification

def my_webhook_handler(request):
    event_json = json.loads(request.body)
    return HttpResponse(status=200)

# Cоздайте объект класса уведомлений в зависимости от события
try:
    notification_object = WebhookNotification(event_json)
except Exception:
    # обработка ошибок
# Получите объекта платежа
payment = notification_object.object
```

Обработка событий виджета ЮKassa

У виджета ЮKassa есть собственные события, о которых он может информировать. Вы можете [обрабатывать эти события](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/additional-settings/behaviour) для взаимодействия с пользователем после оплаты и во всплывающем окне с платежной формой.

Что почитать еще

[Получение информации о платеже](https://yookassa.ru/developers/api#get_payment)

[Использование SDK](https://yookassa.ru/developers/using-api/using-sdks)

[Жизненный цикл платежа](https://yookassa.ru/developers/payment-acceptance/getting-started/payment-process#lifecycle)
