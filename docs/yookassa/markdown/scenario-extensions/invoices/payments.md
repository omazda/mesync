<!-- Источник: https://yookassa.ru/developers/payment-acceptance/scenario-extensions/invoices/payments -->
<!-- Полная копия статьи официальной документации ЮKassa, сохранено 2026-07-02 -->

# Прием платежа по выставленному счету

Чтобы принять платеж, вам нужно создать счет по API, отправить ссылку на него пользователю (самостоятельно или через ЮKassa) и дождаться оплаты. У платежей, созданных при выставлении счета по API, стандартный [жизненный цикл](https://yookassa.ru/developers/payment-acceptance/getting-started/payment-process#lifecycle) и [причины отмены платежа](https://yookassa.ru/developers/payment-acceptance/after-the-payment/declined-payments).

В этой статье описано, как выставить счет по API и принять платеж.

Общий сценарий выставления счета

В этом разделе описан общий сценарий выставления счета с [самостоятельной доставкой пользователю](https://yookassa.ru/developers/payment-acceptance/scenario-extensions/invoices/payments#payment-acceptance-self). Если вы используете другой [способ доставки счета](https://yookassa.ru/developers/payment-acceptance/scenario-extensions/invoices/basics#send-invoice), порядок действий может немного меняться.

![Сценарий выставления счета](https://static.yoomoney.ru/docops-static/images/developers-payment-acceptance-scenario-extensions-invoices-payments-schema.image.en.5e06c701.svg)

Сценарий выставления счета

1. Пользователь подтверждает детали заказа.
2. Вы создаете счет — отправляете ЮKassa POST-запрос с данными платежа, корзины заказа и сроком действия счета.
3. ЮKassa возвращает вам созданный [объект счета](https://yookassa.ru/developers/api#invoice_object) в статусе `pending` со ссылкой на счет (параметр `url` в объекте счета).
4. Вы самостоятельно отправляете полученную ссылку пользователю любым удобным способом (например, в мессенджере).
5. Пользователь переходит по ссылке на страницу счета. Там он видит корзину заказа, срок действия счета и кнопку **К оплате** с суммой платежа.
6. Пользователь переходит к оплате.
7. ЮKassa создает платеж по выставленному счету.
8. ЮKassa на платежной форме отображает способы оплаты, доступные для этого платежа.
9. Пользователь выбирает способ оплаты, вводит данные и подтверждает платеж.
10. Вы можете получить информацию об оплате выставленного счета двумя способами:
    - Через платеж: если у вас настроены [уведомления](https://yookassa.ru/developers/using-api/webhooks), ЮKassa присылает уведомление о переходе платежа в статус `succeeded` (для платежей в одну стадию) или в статус `waiting_for_capture` (для платежей в две стадии). Так вы получите [объект платежа](https://yookassa.ru/developers/api#payment_object) в актуальном статусе.
    - Через счет: вы отправляете ЮKassa GET-запрос на [получение информации о счете](https://yookassa.ru/developers/api#get_invoice). Так вы получите [объект счета](https://yookassa.ru/developers/api#invoice_object) в актуальном статусе.
11. При необходимости вы сообщаете пользователю результат оплаты счета.

Создание счета и прием платежа

При создании счета вы можете выбрать один из трех [способов доставки](https://yookassa.ru/developers/payment-acceptance/scenario-extensions/invoices/basics#send-invoice):

- [Самостоятельная доставка счета](https://yookassa.ru/developers/payment-acceptance/scenario-extensions/invoices/payments#payment-acceptance-self)
- [Доставка счета по электронной почте](https://yookassa.ru/developers/payment-acceptance/scenario-extensions/invoices/payments#payment-acceptance-email)
- [Доставка счета в смс](https://yookassa.ru/developers/payment-acceptance/scenario-extensions/invoices/payments#payment-acceptance-sms)

От выбранного способа доставки счета зависит состав запроса на [создание счета](https://yookassa.ru/developers/api#create_invoice) и процесс передачи пользователю ссылки на счет.

Создание счета с самостоятельной доставкой

**Шаг 1.** [Создайте счет](https://yookassa.ru/developers/api#create_invoice). Передайте в запросе следующие данные:

- объект `payment_data` с данными платежа и, при необходимости, [данными для чека](https://yookassa.ru/developers/payment-acceptance/scenario-extensions/invoices/receipts);
- в объекте `payment_data` передайте параметр `capture` со значением `true`, если хотите провести платеж в одну стадию, и со значением `false`, если вам нужны платежи в [две стадии](https://yookassa.ru/developers/payment-acceptance/getting-started/payment-process#capture-and-cancel);
- массив `cart` с корзиной заказа, которую пользователь увидит на странице счета;
- в объекте `delivery_method_data` передайте тип `self` — самостоятельная доставка счета;
- параметр `expires_at` с датой и временем, до которого счет может быть оплачен.

**Пример запроса на создание счета**

**cURL**

```bash
  curl https://api.yookassa.ru/v3/invoices \
    -X POST \
    -u <Идентификатор магазина>:<Секретный ключ> \
    -H 'Idempotence-Key: <Ключ идемпотентности>' \
    -H 'Content-Type: application/json' \
    -d '{
          "payment_data": {
            "amount": {
              "value": "10.00",
              "currency": "RUB"
            },
            "capture": true,
            "description": "Заказ №37",
            "metadata": {
              "order_id": "37"
            }
          },
          "cart": [
            {
              "description": "Товар арт. 12345",
              "price": {
                "value": "9.00",
                "currency": "RUB"
              },
              "discount_price": {
                "value": "7.00",
                "currency": "RUB"
              },
              "quantity": 1.000
            },
            {
              "description": "Товар арт. 67890",
              "price": {
                "value": "1.00",
                "currency": "RUB"
              },
              "quantity": 3.000
            }
          ],
          "delivery_method_data": {
            "type": "self"
          },
          "locale": "ru_RU",
          "expires_at": "2024-10-18T10:51:18.139Z",
          "description": "Счет на оплату заказа номер 37",
          "metadata": {
            "order_id": "37"
          }
       }'
```

**PHP**

```php
<?php
    # Доступно в PHP SDK от ЮKassa, начиная с версии 3.7
    $idempotenceKey = uniqid('', true);
    $invoice = $client->createInvoice([
        'payment_data' => [
            'amount' => [
                'value' => '10.00',
                'currency' => 'RUB',
            ],
            'capture' => true,
            'description' => 'Заказ №37',
            'metadata' => [
                'order_id' => '37',
            ],
        ],
        'cart' => [
            [
                'description' => 'Товар арт. 12345',
                'price' => [
                    'value' => '9.00',
                    'currency' => 'RUB',
                ],
                'discount_price' => [
                    'value' => '7.00',
                    'currency' => 'RUB',
                ],
                'quantity' => 1.000,
            ],
            [
                'description' => 'Товар арт. 67890',
                'price' => [
                    'value' => '1.00',
                    'currency' => 'RUB',
                ],
                'quantity' => 3.000,
            ],
        ],
        'delivery_method_data' => [
            'type' => 'self',
        ],
        'locale' => 'ru_RU',
        'expires_at' => '2024-10-18T10:51:18.139Z',
        'description' => 'Счет на оплату заказа номер 37',
        'metadata' => [
            'order_id' => '37',
        ],
    ], $idempotenceKey);

    if ($invoice->getDeliveryMethod()) {
        $linkToInvoice = $invoice->getDeliveryMethod()->getUrl();
    }
    if ($invoiceResponse->getPaymentDetails()) {
        $paymentId = $invoice->getPaymentDetails()->getId();
    }
?>
```

**Python**

```python
from yookassa.invoice import Invoice
import uuid

idempotence_key = str(uuid.uuid4())
invoice = Invoice.create({
    "payment_data": {
        "amount": {
            "value": "10.00",
            "currency": "RUB"
        },
        "capture": True,
        "description": "Заказ №37",
        "metadata": {
            "order_id": "37"
        }
    },
    "cart": [
        {
            "description": "Товар арт. 12345",
            "price": {
                "value": "9.00",
                "currency": "RUB"
            },
            "discount_price": {
                "value": "7.00",
                "currency": "RUB"
            },
            "quantity": 1.000
        },
        {
            "description": "Товар арт. 67890",
            "price": {
                "value": "1.00",
                "currency": "RUB"
            },
            "quantity": 3.000
        }
    ],
    "delivery_method_data": {
        "type": "self"
    },
    "locale": "ru_RU",
    "expires_at": "2024-10-18T10:51:18.139Z",
    "description": "Счет на оплату заказа номер 37",
    "metadata": {
        "order_id": "37"
    }
}, idempotence_key)

if invoice.delivery_method is not None:
    linkToInvoice = invoice.delivery_method.url
if invoice.payment_details is not None:
    paymentId = invoice.payment_details.id
```

В ответ на запрос ЮKassa вернет созданный [объект счета](https://yookassa.ru/developers/api#invoice_object).

**Пример созданного объекта счета**

**JSON**

```json
{
  "id": "in-e44e8088-bd73-43b1-959a-954f3a7d0c54",
  "status": "pending",
  "cart": [
    {
      "description": "Товар арт. 12345",
      "price": {
        "value": "9.00",
        "currency": "RUB"
      },
      "discount_price": {
        "value": "7.00",
        "currency": "RUB"
      },
      "quantity": 1.000
    },
    {
      "description": "Товар арт. 67890",
      "price": {
        "value": "1.00",
        "currency": "RUB"
      },
      "quantity": 3.000
    }
  ],
  "delivery_method": {
    "type": "self",
    "url": "https://yookassa.ru/my/i/Zqncq0lhxSqo/a"
  },
  "created_at": "2024-10-01T11:37:15.137Z",
  "expires_at": "2024-10-18T10:51:18.139Z",
  "description": "Счет на оплату заказа номер 37",
  "metadata": {
    "order_id": "37"
  }
}
```

**Шаг 2.** Отправьте пользователю ссылку на счет любым удобным способом: она вернется в параметре `delivery_method.url` в [объекте счета](https://yookassa.ru/developers/api#invoice_object). При переходе по этой ссылке пользователь попадет на страницу счета.

**Шаг 3.** Дождитесь успешного платежа по счету. Вы можете узнать о платеже и его статусе двумя способами:

- Подождите, когда придет [уведомление от ЮKassa](https://yookassa.ru/developers/using-api/webhooks) по платежу. В [объекте платежа](https://yookassa.ru/developers/api#payment_object), помимо прочих данных, будет объект `invoice_details` с идентификатором счета — так вы сможете сопоставить платеж с конкретным счетом.
- Периодически отправляйте GET-запросы для получения [информации о счете](https://yookassa.ru/developers/api#get_invoice) — в ответ на запрос ЮKassa вернет [объект счета](https://yookassa.ru/developers/api#invoice_object). Если пользователь подтвердил оплату, то в объект счета будет включен объект `payment_details` с идентификатором и статусом платежа. При необходимости отправьте GET-запрос с идентификатором платежа, чтобы получить расширенную [информацию о нём](https://yookassa.ru/developers/api#get_payment).

**Пример объекта счета в статусе succeeded с объектом payment\_details**

**JSON**

```json
{
  "id": "in-e44e8088-bd73-43b1-959a-954f3a7d0c54",
  "status": "succeeded",
  "cart": [
    {
      "description": "Товар арт. 12345",
      "price": {
        "value": "9.00",
        "currency": "RUB"
      },
      "discount_price": {
        "value": "7.00",
        "currency": "RUB"
      },
      "quantity": 1.000
    },
    {
      "description": "Товар арт. 67890",
      "price": {
        "value": "1.00",
        "currency": "RUB"
      },
      "quantity": 3.000
    }
  ],
  "payment_details": {
    "id": "22e18a2f-000f-5000-a000-1db6312b7767",
    "status": "succeeded"
  },
  "created_at": "2024-10-01T11:37:15.137Z",
  "description": "Счет на оплату заказа номер 37",
  "metadata": {
    "order_id": "37"
  }
}
```

Если вы принимаете платежи в одну стадию, то это финальный шаг — платеж и счет в статусе `succeeded`, значит счет оплачен.

Готово! Если вы принимаете платежи в две стадии, [спишите оплату или отмените платеж](https://yookassa.ru/developers/payment-acceptance/scenario-extensions/invoices/payments#two-phase).

Создание счета с доставкой по электронной почте

**Шаг 1.** Получите электронную почту пользователя на своей стороне.

**Шаг 2.** [Создайте счет](https://yookassa.ru/developers/api#create_invoice). Передайте в запросе следующие данные:

- объект `payment_data` с данными платежа и, при необходимости, [данными для чека](https://yookassa.ru/developers/payment-acceptance/scenario-extensions/invoices/receipts);
- в объекте `payment_data` передайте параметр `capture` со значением `true`, если хотите провести платеж в одну стадию, и со значением `false`, если вам нужны платежи в [две стадии](https://yookassa.ru/developers/payment-acceptance/getting-started/payment-process#capture-and-cancel);
- массив `cart` с корзиной заказа, которую пользователь увидит на странице счета;
- в объекте `delivery_method_data` передайте тип `email` и параметр `email` с номером телефона для доставки счета;
- параметр `expires_at` с датой и временем, до которого счет может быть оплачен.

**Пример запроса на создание счета**

**cURL**

```bash
  curl https://api.yookassa.ru/v3/invoices \
    -X POST \
    -u <Идентификатор магазина>:<Секретный ключ> \
    -H 'Idempotence-Key: <Ключ идемпотентности>' \
    -H 'Content-Type: application/json' \
    -d '{
          "payment_data": {
            "amount": {
              "value": "10.00",
              "currency": "RUB"
            },
            "capture": true,
            "description": "Заказ №37",
            "metadata": {
              "order_id": "37"
            }
          },
          "cart": [
            {
              "description": "Товар арт. 12345",
              "price": {
                "value": "9.00",
                "currency": "RUB"
              },
              "discount_price": {
                "value": "7.00",
                "currency": "RUB"
              },
              "quantity": 1.000
            },
            {
              "description": "Товар арт. 67890",
              "price": {
                "value": "1.00",
                "currency": "RUB"
              },
              "quantity": 3.000
            }
          ],
          "delivery_method_data": {
            "type": "email",
            "email": "user@example.com"
          },
          "locale": "ru_RU",
          "expires_at": "2024-10-18T10:51:18.139Z",
          "description": "Счет на оплату заказа номер 37",
          "metadata": {
            "order_id": "37"
          }
       }'
```

**PHP**

```php
<?php
    # Доступно в PHP SDK от ЮKassa, начиная с версии 3.7
    $idempotenceKey = uniqid('', true);
    $invoice = $client->createInvoice([
        'payment_data' => [
            'amount' => [
                'value' => '10.00',
                'currency' => 'RUB',
            ],
            'capture' => true,
            'description' => 'Заказ №37',
            'metadata' => [
                'order_id' => '37',
            ],
        ],
        'cart' => [
            [
                'description' => 'Товар арт. 12345',
                'price' => [
                    'value' => '9.00',
                    'currency' => 'RUB',
                ],
                'discount_price' => [
                    'value' => '7.00',
                    'currency' => 'RUB',
                ],
                'quantity' => 1.000,
            ],
            [
                'description' => 'Товар арт. 67890',
                'price' => [
                    'value' => '1.00',
                    'currency' => 'RUB',
                ],
                'quantity' => 3.000,
            ],
        ],
        'delivery_method_data' => [
            'type' => 'email',
            'email' => 'user@example.com'
        ],
        'locale' => 'ru_RU',
        'expires_at' => '2024-10-18T10:51:18.139Z',
        'description' => 'Счет на оплату заказа номер 37',
        'metadata' => [
            'order_id' => '37',
        ],
    ], $idempotenceKey);

    if ($invoice->getDeliveryMethod()) {
        $linkToInvoice = $invoice->getDeliveryMethod()->getUrl();
    }
    if ($invoiceResponse->getPaymentDetails()) {
        $paymentId = $invoice->getPaymentDetails()->getId();
    }
?>
```

**Python**

```python
from yookassa.invoice import Invoice
import uuid

idempotence_key = str(uuid.uuid4())
invoice = Invoice.create({
    "payment_data": {
        "amount": {
            "value": "10.00",
            "currency": "RUB"
        },
        "capture": True,
        "description": "Заказ №37",
        "metadata": {
            "order_id": "37"
        }
    },
    "cart": [
        {
            "description": "Товар арт. 12345",
            "price": {
                "value": "9.00",
                "currency": "RUB"
            },
            "discount_price": {
                "value": "7.00",
                "currency": "RUB"
            },
            "quantity": 1.000
        },
        {
            "description": "Товар арт. 67890",
            "price": {
                "value": "1.00",
                "currency": "RUB"
            },
            "quantity": 3.000
        }
    ],
    "delivery_method_data": {
      "type": "email",
      "email": "user@example.com"
    },
    "locale": "ru_RU",
    "expires_at": "2024-10-18T10:51:18.139Z",
    "description": "Счет на оплату заказа номер 37",
    "metadata": {
        "order_id": "37"
    }
}, idempotence_key)

if invoice.delivery_method is not None:
    linkToInvoice = invoice.delivery_method.url
if invoice.payment_details is not None:
    paymentId = invoice.payment_details.id
```

В ответ на запрос ЮKassa вернет вам созданный [объект счета](https://yookassa.ru/developers/api#invoice_object) и отправит пользователю письмо со ссылкой на счет.

**Пример созданного объекта счета**

**JSON**

```json
{
  "id": "in-e44e8088-bd73-43b1-959a-954f3a7d0c54",
  "status": "pending",
  "cart": [
    {
      "description": "Товар арт. 12345",
      "price": {
        "value": "9.00",
        "currency": "RUB"
      },
      "discount_price": {
        "value": "7.00",
        "currency": "RUB"
      },
      "quantity": 1.000
    },
    {
      "description": "Товар арт. 67890",
      "price": {
        "value": "1.00",
        "currency": "RUB"
      },
      "quantity": 3.000
    }
  ],
  "delivery_method": {
    "type": "email"
  },
  "created_at": "2024-10-01T11:37:15.137Z",
  "expires_at": "2024-10-18T10:51:18.139Z",
  "description": "Счет на оплату заказа номер 37",
  "metadata": {
    "order_id": "37"
  }
}
```

**Шаг 3.** Дождитесь успешного платежа по счету. Вы можете узнать о платеже и его статусе двумя способами:

- Подождите, когда придет [уведомление от ЮKassa](https://yookassa.ru/developers/using-api/webhooks) по платежу. В [объекте платежа](https://yookassa.ru/developers/api#payment_object), помимо прочих данных, будет объект `invoice_details` с идентификатором счета — так вы сможете сопоставить платеж с конкретным счетом.
- Периодически отправляйте GET-запросы для получения [информации о счете](https://yookassa.ru/developers/api#get_invoice) — в ответ на запрос ЮKassa вернет [объект счета](https://yookassa.ru/developers/api#invoice_object). Если пользователь подтвердил оплату, то в объект счета будет включен объект `payment_details` с идентификатором и статусом платежа. При необходимости отправьте GET-запрос с идентификатором платежа, чтобы получить расширенную [информацию о нём](https://yookassa.ru/developers/api#get_payment).

**Пример объекта счета в статусе succeeded с объектом payment\_details**

**JSON**

```json
{
  "id": "in-e44e8088-bd73-43b1-959a-954f3a7d0c54",
  "status": "succeeded",
  "cart": [
    {
      "description": "Товар арт. 12345",
      "price": {
        "value": "9.00",
        "currency": "RUB"
      },
      "discount_price": {
        "value": "7.00",
        "currency": "RUB"
      },
      "quantity": 1.000
    },
    {
      "description": "Товар арт. 67890",
      "price": {
        "value": "1.00",
        "currency": "RUB"
      },
      "quantity": 3.000
    }
  ],
  "payment_details": {
    "id": "22e18a2f-000f-5000-a000-1db6312b7767",
    "status": "succeeded"
  },
  "created_at": "2024-10-01T11:37:15.137Z",
  "description": "Счет на оплату заказа номер 37",
  "metadata": {
    "order_id": "37"
  }
}
```

Если вы принимаете платежи в одну стадию, то это финальный шаг — платеж и счет в статусе `succeeded`, значит счет оплачен.

Готово! Если вы принимаете платежи в две стадии, [спишите оплату или отмените платеж](https://yookassa.ru/developers/payment-acceptance/scenario-extensions/invoices/payments#two-phase).

Создание счета с доставкой в смс

**Шаг 1.** Получите номер телефона пользователя на своей стороне.

**Шаг 2.** [Создайте счет](https://yookassa.ru/developers/api#create_invoice). Передайте в запросе следующие данные:

- объект `payment_data` с данными платежа и, при необходимости, [данными для чека](https://yookassa.ru/developers/payment-acceptance/scenario-extensions/invoices/receipts);
- в объекте `payment_data` передайте параметр `capture` со значением `true`, если хотите провести платеж в одну стадию, и со значением `false`, если вам нужны платежи в [две стадии](https://yookassa.ru/developers/payment-acceptance/getting-started/payment-process#capture-and-cancel);
- массив `cart` с корзиной заказа, которую пользователь увидит на странице счета;
- в объекте `delivery_method_data` передайте тип `sms` и параметр `phone` с номером телефона для доставки счета;
- параметр `expires_at` с датой и временем, до которого счет может быть оплачен.

**Пример запроса на создание счета**

**cURL**

```bash
  curl https://api.yookassa.ru/v3/invoices \
    -X POST \
    -u <Идентификатор магазина>:<Секретный ключ> \
    -H 'Idempotence-Key: <Ключ идемпотентности>' \
    -H 'Content-Type: application/json' \
    -d '{
          "payment_data": {
            "amount": {
              "value": "10.00",
              "currency": "RUB"
            },
            "capture": true,
            "description": "Заказ №37",
            "metadata": {
              "order_id": "37"
            }
          },
          "cart": [
            {
              "description": "Товар арт. 12345",
              "price": {
                "value": "9.00",
                "currency": "RUB"
              },
              "discount_price": {
                "value": "7.00",
                "currency": "RUB"
              },
              "quantity": 1.000
            },
            {
              "description": "Товар арт. 67890",
              "price": {
                "value": "1.00",
                "currency": "RUB"
              },
              "quantity": 3.000
            }
          ],
          "delivery_method_data": {
            "type": "sms",
            "phone": "79000000000"
          },
          "locale": "ru_RU",
          "expires_at": "2024-10-18T10:51:18.139Z",
          "description": "Счет на оплату заказа номер 37",
          "metadata": {
            "order_id": "37"
          }
       }'
```

**PHP**

```php
<?php
    # Доступно в PHP SDK от ЮKassa, начиная с версии 3.7
    $idempotenceKey = uniqid('', true);
    $invoice = $client->createInvoice([
        'payment_data' => [
            'amount' => [
                'value' => '10.00',
                'currency' => 'RUB',
            ],
            'capture' => true,
            'description' => 'Заказ №37',
            'metadata' => [
                'order_id' => '37',
            ],
        ],
        'cart' => [
            [
                'description' => 'Товар арт. 12345',
                'price' => [
                    'value' => '9.00',
                    'currency' => 'RUB',
                ],
                'discount_price' => [
                    'value' => '7.00',
                    'currency' => 'RUB',
                ],
                'quantity' => 1.000,
            ],
            [
                'description' => 'Товар арт. 67890',
                'price' => [
                    'value' => '1.00',
                    'currency' => 'RUB',
                ],
                'quantity' => 3.000,
            ],
        ],
        'delivery_method_data' => [
            'type' => 'sms',
            'email' => '79000000000'
        ],
        'locale' => 'ru_RU',
        'expires_at' => '2024-10-18T10:51:18.139Z',
        'description' => 'Счет на оплату заказа номер 37',
        'metadata' => [
            'order_id' => '37',
        ],
    ], $idempotenceKey);

    if ($invoice->getDeliveryMethod()) {
        $linkToInvoice = $invoice->getDeliveryMethod()->getUrl();
    }
    if ($invoiceResponse->getPaymentDetails()) {
        $paymentId = $invoice->getPaymentDetails()->getId();
    }
?>
```

**Python**

```python
from yookassa.invoice import Invoice
import uuid

idempotence_key = str(uuid.uuid4())
invoice = Invoice.create({
    "payment_data": {
        "amount": {
            "value": "10.00",
            "currency": "RUB"
        },
        "capture": True,
        "description": "Заказ №37",
        "metadata": {
            "order_id": "37"
        }
    },
    "cart": [
        {
            "description": "Товар арт. 12345",
            "price": {
                "value": "9.00",
                "currency": "RUB"
            },
            "discount_price": {
                "value": "7.00",
                "currency": "RUB"
            },
            "quantity": 1.000
        },
        {
            "description": "Товар арт. 67890",
            "price": {
                "value": "1.00",
                "currency": "RUB"
            },
            "quantity": 3.000
        }
    ],
    "delivery_method_data": {
      "type": "sms",
      "phone": "79000000000"
    },
    "locale": "ru_RU",
    "expires_at": "2024-10-18T10:51:18.139Z",
    "description": "Счет на оплату заказа номер 37",
    "metadata": {
        "order_id": "37"
    }
}, idempotence_key)

if invoice.delivery_method is not None:
    linkToInvoice = invoice.delivery_method.url
if invoice.payment_details is not None:
    paymentId = invoice.payment_details.id
```

В ответ на запрос ЮKassa вернет вам созданный [объект счета](https://yookassa.ru/developers/api#invoice_object) и отправит пользователю смс со ссылкой на счет.

**Пример созданного объекта счета**

**JSON**

```json
{
  "id": "in-e44e8088-bd73-43b1-959a-954f3a7d0c54",
  "status": "pending",
  "cart": [
    {
      "description": "Товар арт. 12345",
      "price": {
        "value": "9.00",
        "currency": "RUB"
      },
      "discount_price": {
        "value": "7.00",
        "currency": "RUB"
      },
      "quantity": 1.000
    },
    {
      "description": "Товар арт. 67890",
      "price": {
        "value": "1.00",
        "currency": "RUB"
      },
      "quantity": 3.000
    }
  ],
  "delivery_method": {
    "type": "sms"
  },
  "created_at": "2024-10-01T11:37:15.137Z",
  "expires_at": "2024-10-18T10:51:18.139Z",
  "description": "Счет на оплату заказа номер 37",
  "metadata": {
    "order_id": "37"
  }
}
```

**Шаг 3.** Дождитесь успешного платежа по счету. Вы можете узнать о платеже и его статусе двумя способами:

- Подождите, когда придет [уведомление от ЮKassa](https://yookassa.ru/developers/using-api/webhooks) по платежу. В [объекте платежа](https://yookassa.ru/developers/api#payment_object), помимо прочих данных, будет объект `invoice_details` с идентификатором счета — так вы сможете сопоставить платеж с конкретным счетом.
- Периодически отправляйте GET-запросы для получения [информации о счете](https://yookassa.ru/developers/api#get_invoice) — в ответ на запрос ЮKassa вернет [объект счета](https://yookassa.ru/developers/api#invoice_object). Если пользователь подтвердил оплату, то в объект счета будет включен объект `payment_details` с идентификатором и статусом платежа. При необходимости отправьте GET-запрос с идентификатором платежа, чтобы получить расширенную [информацию о нём](https://yookassa.ru/developers/api#get_payment).

**Пример объекта счета в статусе succeeded с объектом payment\_details**

**JSON**

```json
{
  "id": "in-e44e8088-bd73-43b1-959a-954f3a7d0c54",
  "status": "succeeded",
  "cart": [
    {
      "description": "Товар арт. 12345",
      "price": {
        "value": "9.00",
        "currency": "RUB"
      },
      "discount_price": {
        "value": "7.00",
        "currency": "RUB"
      },
      "quantity": 1.000
    },
    {
      "description": "Товар арт. 67890",
      "price": {
        "value": "1.00",
        "currency": "RUB"
      },
      "quantity": 3.000
    }
  ],
  "payment_details": {
    "id": "22e18a2f-000f-5000-a000-1db6312b7767",
    "status": "succeeded"
  },
  "created_at": "2024-10-01T11:37:15.137Z",
  "description": "Счет на оплату заказа номер 37",
  "metadata": {
    "order_id": "37"
  }
}
```

Если вы принимаете платежи в одну стадию, то это финальный шаг — платеж и счет в статусе `succeeded`, значит счет оплачен.

Готово! Если вы принимаете платежи в две стадии, [спишите оплату или отмените платеж](https://yookassa.ru/developers/payment-acceptance/scenario-extensions/invoices/payments#two-phase).

Особенности проведения платежей в две стадии

Если вы принимаете платежи в две стадии, то после подтверждения пользователем платеж перейдет в статус `waiting_for_capture`. Этот статус означает, что вам нужно принять решение: [подтвердить платеж](https://yookassa.ru/developers/payment-acceptance/getting-started/payment-process#hold) (списать оплату полностью или частично) или [отменить его](https://yookassa.ru/developers/payment-acceptance/getting-started/payment-process#cancel). Для этого:

**Шаг 1.** Получите идентификатор платежа. [Подробнее о получении идентификатора](https://yookassa.ru/developers/payment-acceptance/scenario-extensions/invoices/payments#how-to-get-payment-id)

**Шаг 2.** Отправьте запрос на [подтверждение](https://yookassa.ru/developers/api#capture_payment) или [отмену платежа](https://yookassa.ru/developers/api#cancel_payment). В запросе передайте полученный идентификатор платежа. Подробнее о подтверждении и отмене платежа:

- [Полное списание оплаты](https://yookassa.ru/developers/payment-acceptance/getting-started/payment-process#capture-full)
- [Частичное списание оплаты](https://yookassa.ru/developers/payment-acceptance/getting-started/payment-process#capture-partly)
- [Отмена платежа](https://yookassa.ru/developers/payment-acceptance/getting-started/payment-process#cancel)

**Пример запроса на частичное списание оплаты**

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

**Шаг 3.** Дождитесь, когда платеж перейдет в нужный статус:

- При успешном подтверждении платеж перейдет в статус `succeeded`. Счет также останется в статусе `succeeded` и будет считаться оплаченным.
- При отмене платеж перейдет в статус `canceled`. Счет также отменится, перейдет в статус `canceled`. Оплатить счет уже не получится, для приема платежа нужно будет создать новый счет.

Чтобы узнать текущий статус платежа или счета, вы можете [настроить уведомления](https://yookassa.ru/developers/using-api/webhooks) от ЮKassa (только для платежей) или запросить информацию по API (для [платежей](https://yookassa.ru/developers/api#get_payment) и [счетов](https://yookassa.ru/developers/api#get_invoice)).

Идентификатор платежа: как получить и зачем он нужен

Когда на странице счета пользователь перейдет к оплате, ЮKassa автоматически создаст [объект платежа](https://yookassa.ru/developers/api#payment_object) и перенаправит пользователя на платежную форму. У каждого объекта платежа есть идентификатор. Например, `22e18a2f-000f-5000-a000-1db6312b7767`.

Он потребуется вам для следующих действий:

- отмена или списание оплаты по платежу в [две стадии](https://yookassa.ru/developers/payment-acceptance/scenario-extensions/invoices/payments#two-phase);
- [возврат платежа](https://yookassa.ru/developers/payment-acceptance/scenario-extensions/invoices/refunds);
- сохранение способа оплаты для [автоплатежей](https://yookassa.ru/developers/payment-acceptance/scenario-extensions/invoices/recurring-payments#get-saved-payment-method-id);
- [отправка чеков](https://yookassa.ru/developers/payment-acceptance/scenario-extensions/invoices/receipts) с использованием решений ЮKassa для работы по 54-ФЗ;
- [получение информации о платеже](https://yookassa.ru/developers/api#get_payment).

Как получить идентификатор платежа

В объекте платежа

Если дожидаетесь [уведомления от ЮKassa](https://yookassa.ru/developers/using-api/webhooks) по платежу, то идентификатор получите в значении параметра `object.id` в [объекте платежа](https://yookassa.ru/developers/api#payment_object). Кроме того, в объекте платежа вернется идентификатор счета в параметре `invoice_details.id` — так вы сможете сопоставить платеж и счет.

**Пример тела уведомления payment.waiting\_for\_capture**

**JSON**

```json
{
  "type": "notification",
  "event": "payment.waiting_for_capture",
  "object": {
    "id": "22e18a2f-000f-5000-a000-1db6312b7767",
    "status": "succeeded",
    "paid": true,
    "amount": {
      "value": "10.00",
      "currency": "RUB"
    },
    "authorization_details": {
      "rrn": "603668680243",
      "auth_code": "000000",
      "three_d_secure": {
        "applied": true
      }
    },
    "captured_at": "2024-10-02T12:46:18.139Z",
    "created_at": "2024-10-02T12:45:15.137Z",
    "description": "Заказ №37",
    "metadata": {},
    "payment_method": {
      "type": "bank_card",
      "id": "22e18a2f-000f-5000-a000-1db6312b7767",
      "saved": false,
      "card": {
        "first6": "555555",
        "last4": "4444",
        "expiry_month": "07",
        "expiry_year": "2022",
        "card_type": "Mir",
        "card_product": {
          "code": "MCP",
          "name": "MIR Privilege"
        },
        "issuer_country": "RU",
        "issuer_name": "Sberbank"
      },
      "title": "Bank card *4444"
    },
    "refundable": true,
    "refunded_amount": {
      "value": "0.00",
      "currency": "RUB"
    },
    "recipient": {
      "account_id": "100500",
      "gateway_id": "100700"
    },
    "test": false,
    "invoice_details": {
      "id": "in-e44e8088-bd73-43b1-959a-954f3a7d0c54"
    }
  }
}
```

В объекте счета

Если отправляете GET-запросы, чтобы получить [информацию о счете](https://yookassa.ru/developers/api#get_invoice), то идентификатор вернется в значении параметра `payment_details.id` в [объекте счета](https://yookassa.ru/developers/api#invoice_object), но только при условии, что пользователь уже подтвердил платеж. С идентификатором платежа вы сможете отправить ещё один GET-запрос, чтобы [получить объект платежа](https://yookassa.ru/developers/api#get_payment) с расширенной информацией о нём (способ оплаты, дата и время оплаты и т.д.).

Если платежа не было или пользователь его еще не подтвердил, то [объект счета](https://yookassa.ru/developers/api#invoice_object) вернется без объекта `payment_details`.

**Пример объекта счета в статусе succeeded**

**JSON**

```json
{
  "id": "in-e44e8088-bd73-43b1-959a-954f3a7d0c54",
  "status": "succeeded",
  "cart": [
    {
      "description": "Товар арт. 12345",
      "price": {
        "value": "9.00",
        "currency": "RUB"
      },
      "discount_price": {
        "value": "7.00",
        "currency": "RUB"
      },
      "quantity": 1.000
    },
    {
      "description": "Товар арт. 67890",
      "price": {
        "value": "1.00",
        "currency": "RUB"
      },
      "quantity": 3.000
    }
  ],
  "payment_details": {
    "id": "22e18a2f-000f-5000-a000-1db6312b7767",
    "status": "waiting_for_capture"
  },
  "created_at": "2024-10-01T11:37:15.137Z",
  "description": "Счет на оплату заказа номер 37",
  "metadata": {
    "order_id": "37"
  }
}
```

Информирование об оплате счета

Вы можете узнавать об оплаченных счетах несколькими способами: в личном кабинете, по электронной почте, по API или с помощью уведомлений по платежу от ЮKassa.

В личном кабинете

В личном кабинете вы можете найти информацию о статусе в разделе [Счета клиентам](https://yookassa.ru/my/invoice).

По электронной почте

По электронной почте вы можете получить письмо об оплате счета. Для этого [включите уведомления о счетах](https://yookassa.ru/docs/support/merchant/payments/settings#settings__account-notifications) в личном кабинете.

По API

По API вы можете периодически отправлять запросы, чтобы [получить объект счета](https://yookassa.ru/developers/api#get_invoice). В нём содержится статус счета, срок действия, корзина заказа и другие данные. Этот способ подойдет только для счетов, выставленных по API. Если вы выставили счет в личном кабинете или через Telegram-бота, то получить информацию о нём по API не получится.

Уведомления по платежу от ЮKassa

Вы можете дожидаться [уведомления по платежу](https://yookassa.ru/developers/using-api/webhooks) от ЮKassa. В теле уведомления вы получите [объект платежа](https://yookassa.ru/developers/api#payment_object), в котором, помимо прочих данных, содержится объект `invoice_details` с идентификатором выставленного счета. С его помощью вы можете сопоставить платеж с конкретным счетом. Если объект платежа в статусе `succeedeed`, то счет оплачен.

Что почитать еще

[Основы проведения платежей](https://yookassa.ru/developers/payment-acceptance/getting-started/payment-process)

[Неуспешные платежи](https://yookassa.ru/developers/payment-acceptance/after-the-payment/declined-payments)

[Возврат платежей по выставленным счетам](https://yookassa.ru/developers/payment-acceptance/scenario-extensions/invoices/refunds)

[Отправка чеков для платежей по выставленным счетам](https://yookassa.ru/developers/payment-acceptance/scenario-extensions/invoices/basics)
