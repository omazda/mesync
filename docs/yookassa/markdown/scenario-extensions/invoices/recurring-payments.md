<!-- Источник: https://yookassa.ru/developers/payment-acceptance/scenario-extensions/invoices/recurring-payments -->
<!-- Полная копия статьи официальной документации ЮKassa, сохранено 2026-07-02 -->

# Автоплатежи по выставленному счету

Если хотите использовать автоплатежи и выставлять счета с сохранением способа оплаты, напишите вашему менеджеру ЮKassa.

При выставлении счета по API вы можете сохранить платежные данные, которые использовались для оплаты, и проводить с ними автоплатежи. В этом случае пользователю нужно получить только один счет и подтвердить платеж по нему. Вы сохраните платежные данные (способ оплаты) и сможете использовать их при последующих безакцептных списаниях.

Автоплатежи по выставленному счету отличаются от обычных платежей только на этапе сохранения способа оплаты. Особенности, доступные способы оплаты, проведение повторных списаний и остальное работает так же, как для стандартных автоплатежей c привязкой во время платежа. [Подробнее об особенностях и порядке работы автоплатежей](https://yookassa.ru/developers/payment-acceptance/scenario-extensions/recurring-payments/basics)

Если вам разрешено использование автоплатежей, вы можете проводить платежи:

- [с сохранением способа оплаты](https://yookassa.ru/developers/payment-acceptance/scenario-extensions/invoices/recurring-payments#save),
- [без сохранения способа оплаты](https://yookassa.ru/developers/payment-acceptance/scenario-extensions/invoices/recurring-payments#not-save).

Платеж с сохранением способа оплаты

При платеже с сохранением способа оплаты на платежной форме отобразятся только те способы, которые поддерживают эту опцию. [Подробнее о способах оплаты](https://yookassa.ru/developers/payment-acceptance/getting-started/payment-methods)

Если вы используете СБП, ознакомьтесь с [особенностями проведения платежей при оплате через СБП](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/other/sbp#payment-process-recurrent-payments).

Чтобы провести платеж с сохранением способа оплаты, вам нужно выставить счет с соответствующими настройками и после проведения платежа сохранить идентификатор способа оплаты. Он нужен, чтобы в дальнейшем проводить безакцептные списания.

При выставлении счетов вы можете принимать платежи с безусловным или с условным сохранением способа оплаты.

[Безусловное сохранение способа оплаты](https://yookassa.ru/developers/payment-acceptance/scenario-extensions/invoices/recurring-payments#save-invoice-required) — сохранение способа происходит по умолчанию, пользователь не может на это повлиять. Как это выглядит:

- Вы предупреждаете пользователя, что сохраните его платежные данные, и рассказываете, как будете их использовать, например с какой регулярностью вы будете списывать деньги и на какую сумму, как пользователь может отказаться от повторных списаний в вашем магазине.
- Вы на своей стороне получаете от пользователя согласие на проведение автоплатежей.
- Платежная форма отображает пользователю способы оплаты, поддерживающие безусловное сохранение, и предупреждает, что после платежа способ оплаты будет привязан к вашему магазину. При успешной оплате данные способа оплаты автоматически сохранятся в ЮKassa.

[Способы оплаты](https://yookassa.ru/developers/payment-acceptance/getting-started/payment-methods), которые поддерживают безусловное сохранение: кошелек ЮMoney, банковская карта, Mir Pay, SberPay, T-Pay, СБП.

[Условное сохранение способа оплаты](https://yookassa.ru/developers/payment-acceptance/scenario-extensions/invoices/recurring-payments#save-invoice-required) — сохранение способа происходит по желанию пользователя. Как это выглядит:

- Вы рассказываете пользователю о возможности сохранить платежные данные, о том, как вы будете их использовать и как потом от этого отказаться.
- При переходе к оплате платежная форма отображает пользователю все доступные способы оплаты. Если пользователь выберет способ оплаты, поддерживающий условное сохранение, ЮKassa предложит ему сохранить данные для вашего магазина. Если пользователь согласится, при успешной оплате данные способа будут сохранены в ЮKassa, и вы сможете использовать идентификатор сохраненного способа оплаты для последующих платежей. Если не согласится, платеж пройдет без привязки данных к магазину.

[Способы оплаты](https://yookassa.ru/developers/payment-acceptance/getting-started/payment-methods), которые поддерживают условное сохранение: кошелек ЮMoney, банковская карта.

Создание счета с безусловным сохранением способа оплаты

**Шаг 1.** Чтобы сохранить способ оплаты, [создайте счет](https://yookassa.ru/developers/payment-acceptance/scenario-extensions/invoices/payments#payment-acceptance) и добавьте в объект `payment_data` параметр `save_payment_method` со значением `true`.

**Пример запроса на создание счета с безусловным сохранением способа оплаты**

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
            "save_payment_method": true,
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
            'save_payment_method' => true,
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
        "save_payment_method": True,
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

Далее действуйте как обычно: в ответ на запрос получите от ЮKassa [объект счета](https://yookassa.ru/developers/api#invoice_object), отправьте пользователю ссылку из значения параметра `delivery_method.url` и дождитесь, когда он подтвердит оплату.

**Шаг 2.** Если оплата счета прошла успешно, [получите идентификатор сохраненного способа оплаты](https://yookassa.ru/developers/payment-acceptance/scenario-extensions/invoices/recurring-payments#get-saved-payment-method-id).

Создание счета с условным сохранением способа оплаты

**Шаг 1.** [Создайте счет](https://yookassa.ru/developers/payment-acceptance/scenario-extensions/invoices/payments#payment-acceptance), передавать параметр `save_payment_method` не нужно.

**Пример запроса на создание счета с условным сохранением способа оплаты**

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

Далее действуйте как обычно: в ответ на запрос получите от ЮKassa [объект счета](https://yookassa.ru/developers/api#invoice_object), отправьте пользователю ссылку из значения параметра `delivery_method.url` и дождитесь, когда он подтвердит оплату.

**Шаг 2.** Если оплата счета прошла успешно, [получите идентификатор сохраненного способа оплаты](https://yookassa.ru/developers/payment-acceptance/scenario-extensions/invoices/recurring-payments#get-saved-payment-method-id).

Получение идентификатора сохраненного способа оплаты

**Шаг 1.** Дождитесь, когда пользователь подтвердит оплату и платеж перейдет в статус `succeeded` (или `waiting_for_capture`, если это платеж в две стадии). Вы можете узнать о платеже и его статусе двумя способами:

- Подождите, когда придет [уведомление от ЮKassa](https://yookassa.ru/developers/using-api/webhooks) по платежу. Оно будет содержать [объект платежа](https://yookassa.ru/developers/api#payment_object), в котором, помимо прочих данных, будет идентификатор и статус платежа, а также объект `invoice_details` с идентификатором счета. Используйте эти данные, чтобы сопоставить платеж с конкретным счетом.
- Периодически отправляйте GET-запросы для получения [информации о счете](https://yookassa.ru/developers/api#get_invoice)  — в ответ на запрос ЮKassa вернет [объект счета](https://yookassa.ru/developers/api#invoice_object). Если пользователь подтвердил оплату, то в объект счета будет включен объект `payment_details` с идентификатором и статусом платежа. С идентификатором платежа отправьте новый [GET-запрос](https://yookassa.ru/developers/api#get_payment). В ответе ЮKassa вернет [объект платежа](https://yookassa.ru/developers/api#payment_object).

**Шаг 2.** Убедитесь, что способ оплаты сохранен: в [объекте платежа](https://yookassa.ru/developers/api#payment_object) значение `payment_method.saved` изменилось на `true`.

**Пример объекта платежа в статусе succeeded**

**JSON**

```json
{
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
    "saved": true,
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
```

**Шаг 3.** Сохраните идентификатор способа оплаты `payment_method.id`. Его нужно будет использовать в качестве идентификатора сохраненного способа оплаты при последующих платежах.

**Шаг 4.** При необходимости сохраните идентификатор счета в связке со значением параметра `payment_method.id`. Это может быть полезно, потому что идентификатор счета в [объекте платежа](https://yookassa.ru/developers/api#payment_object) возвращается только при сохранении способа оплаты.

Готово!

Теперь вы можете проводить автоплатежи.

Проведение автоплатежа

Проведение платежа сохраненным способом оплаты нужно реализовать самостоятельно. Для этого отправьте запрос на создание автоплатежа и передайте в нём параметр `payment_method_id` с идентификатором сохраненного способа оплаты. [Подробнее о проведении автоплатежа](https://yookassa.ru/developers/payment-acceptance/scenario-extensions/recurring-payments/pay-with-saved)

В [объекте платежа](https://yookassa.ru/developers/api#payment_object) будет отсутствовать идентификатор счета. Сопоставить рекуррентный платеж и счет можно по связке `payment_method.id` c идентификатором счета, если вы сохраняли их ранее.

Платеж без сохранения способа оплаты

Вы можете проводить платежи без сохранения способа оплаты. Пользователь сможет оплатить любым доступным способом. Способ оплаты не сохранится.

Чтобы принять по счету платеж без сохранения способа оплаты, создайте счет и в объекте `payment_data` передайте параметр `save_payment_method` со значением `false`.

**Пример запроса на создание счета без сохранения способа оплаты**

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
            "save_payment_method": false,
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
            'save_payment_method' => false,
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
        "save_payment_method": False,
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

Далее действуйте как обычно: в ответ на запрос получите от ЮKassa [объект счета](https://yookassa.ru/developers/api#invoice_object), отправьте пользователю ссылку из значения параметра `delivery_method.url` и дождитесь, когда он подтвердит оплату.

Что почитать еще

[Автоплатежи](https://yookassa.ru/developers/payment-acceptance/scenario-extensions/recurring-payments/basics)

[Неуспешные платежи](https://yookassa.ru/developers/payment-acceptance/after-the-payment/declined-payments)

[Способы оплаты](https://yookassa.ru/developers/payment-acceptance/getting-started/payment-methods)

[Основы проведения платежей](https://yookassa.ru/developers/payment-acceptance/getting-started/payment-process)
