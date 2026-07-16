<!-- Источник: https://yookassa.ru/developers/payment-acceptance/scenario-extensions/invoices/receipts -->
<!-- Полная копия статьи официальной документации ЮKassa, сохранено 2026-07-02 -->

# Отправка чеков по выставленным счетам

Компаниям и ИП при проведении платежей и возвратов необходимо формировать чеки. Выставление счетов — это вспомогательный инструмент для проведения платежей, поэтому здесь также нужно регистрировать чеки в налоговой. Вы можете делать это самостоятельно или использовать [решения ЮKassa для отправки чеков в налоговую](https://yookassa.ru/developers/payment-acceptance/receipts/basics).

Всё работает, как для обычных платежей, особенности есть только при создании счета и проведении платежа.

Особенности отправки чеков при выставлении счетов

При проведении обычных платежей данные для чека передаются двумя способами:

- вместе с данными о платеже или возврате — в запросе на создание платежа, подтверждение платежа или в запросе на создание возврата;
- отдельным запросом на создание чека.

Способ отправки данных зависит от выбранного решения, сценария отправки чеков и от операции, которую вы хотите выполнить.

| Решение и сценарий | Способ отправки данных |
| --- | --- |
| [54-ФЗ: чеки от ЮKassa](https://yookassa.ru/developers/payment-acceptance/receipts/54fz/yoomoney/basics)  [54-ФЗ: сторонняя онлайн-касса](https://yookassa.ru/developers/payment-acceptance/receipts/54fz/other-services/basics), сценарий [Платеж и чек одновременно](https://yookassa.ru/developers/payment-acceptance/receipts/54fz/other-services/basics#payment-and-receipt)  [54-ФЗ: сторонняя онлайн-касса](https://yookassa.ru/developers/payment-acceptance/receipts/54fz/other-services/basics), сценарий [Сначала чек, потом платеж](https://yookassa.ru/developers/payment-acceptance/receipts/54fz/other-services/basics#payment-after-receipt) | - Данные для чека при проведении платежа передаются в запросе на создание платежа и в запросе на подтверждение платежа (при платежах в две стадии) - Для 54-ФЗ: Данные для чека зачета предоплаты передаются в запросе на создание чека - Данные для чека при проведении возврата передаются в запросе на создание возврата |
| [54-ФЗ: сторонняя онлайн-касса](https://yookassa.ru/developers/payment-acceptance/receipts/54fz/other-services/basics), сценарий [Сначала платеж, потом чек](https://yookassa.ru/developers/payment-acceptance/receipts/54fz/other-services/basics#receipt-after-payment) | - Данные для чека при проведении платежа передаются в запросе на создание чека после перехода платежа в определенный статус - Данные для чека зачета предоплаты передаются в запросе на создание чека - Данные для чека при проведении возврата передаются в запросе на создание чека после перехода возврата в определенный статус |

Если вы выставляете счета, отличия незначительные:

- При выставлении счета:
  - Если используете [чеки от ЮKassa](https://yookassa.ru/developers/payment-acceptance/receipts/54fz/yoomoney/basics), [решение для сторонних онлайн-касс](https://yookassa.ru/developers/payment-acceptance/receipts/54fz/other-services/basics) (сценарии [Платеж и чек одновременно](https://yookassa.ru/developers/payment-acceptance/receipts/54fz/other-services/basics#payment-and-receipt) или [Сначала чек, потом платеж](https://yookassa.ru/developers/payment-acceptance/receipts/54fz/other-services/basics#payment-after-receipt)), данные для чеков нужно передавать не в запросе на создание платежа, а в запросе на создание счета. [Подробнее о чеке в запросе на создание счета](https://yookassa.ru/developers/payment-acceptance/scenario-extensions/invoices/receipts#payment-receipt-create-invoice-with-receipt)
  - Если используете [решение для сторонних онлайн-касс](https://yookassa.ru/developers/payment-acceptance/receipts/54fz/other-services/basics) и сценарий [Сначала платеж, потом чек](https://yookassa.ru/developers/payment-acceptance/receipts/54fz/other-services/basics#receipt-after-payment), нужно сначала выставить счет, дождаться оплаты и узнать идентификатор платежа для выставленного счета, после этого создать чек. [Подробнее о создании чека отдельным запросом](https://yookassa.ru/developers/payment-acceptance/scenario-extensions/invoices/receipts#payment-receipt-create-receipt-independently)
- При выполнении других операций (подтверждение и отмена платежа при оплате в две стадии, формирование чека зачета предоплаты, возврат платежа): нужно предварительно узнать идентификатор платежа для выставленного счета, после этого использовать его для выполнения операции и отправки данных для чеков. Подробнее о чеках при [выполнении других операций с платежами](https://yookassa.ru/developers/payment-acceptance/scenario-extensions/invoices/receipts#payment-receipt-other-cases) и при [возвратах платежей](https://yookassa.ru/developers/payment-acceptance/scenario-extensions/invoices/receipts#refund-receipt)

Чеки при выставлении счета

Выберите нужный вам способ отправки данных для чека:

- [Чек прихода в запросе на создание счета](https://yookassa.ru/developers/payment-acceptance/scenario-extensions/invoices/receipts#payment-receipt-create-invoice-with-receipt)
- [Чек прихода отдельным запросом](https://yookassa.ru/developers/payment-acceptance/scenario-extensions/invoices/receipts#payment-receipt-create-receipt-independently)

Чек прихода в запросе на создание счета

Если вы используете эти решения ЮKassa, данные для чека при платеже нужно передавать в запросе на создание счета:

- [54-ФЗ: чеки от ЮKassa](https://yookassa.ru/developers/payment-acceptance/receipts/54fz/yoomoney/basics)
- [54-ФЗ: сторонняя онлайн-касса](https://yookassa.ru/developers/payment-acceptance/receipts/54fz/other-services/basics), сценарий [Платеж и чек одновременно](https://yookassa.ru/developers/payment-acceptance/receipts/54fz/other-services/basics#payment-and-receipt)
- [54-ФЗ: сторонняя онлайн-касса](https://yookassa.ru/developers/payment-acceptance/receipts/54fz/other-services/basics), сценарий [Сначала чек, потом платеж](https://yookassa.ru/developers/payment-acceptance/receipts/54fz/other-services/basics#payment-after-receipt)

В этом разделе описано создание чека прихода на примере компании, которая использует решение ЮKassa для сторонних онлайн-касс и формирует чеки по сценарию [Платеж и чек одновременно](https://yookassa.ru/developers/payment-acceptance/receipts/54fz/other-services/basics#payment-and-receipt). Для других решений и сценариев запрос может отличаться.

Как отправить данные для чека:

**Шаг 1.** Перед выставлением счета получите от пользователя данные для доставки ему чека: адрес электронной почты или номер телефона (доступно для всех решений, кроме чеков от ЮKassa).

**Шаг 2.** [Создайте счет](https://yookassa.ru/developers/payment-acceptance/scenario-extensions/invoices/payments#payment-acceptance) и добавьте в объект `payment_data` объект `receipt` с данными для чека. Требования к данным для чека зависят от решения ЮKassa, которое вы используете для отправки чеков.

**Пример запроса на создание счета с параметрами для чека (54-ФЗ, сторонняя онлайн-касса, сценарий Платеж и чек одновременно)**

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
            "receipt": {
              "customer": {
                "full_name": "Иванов Иван Иванович",
                "email": "user@example.com"
              },
              "items": [
                {
                  "description": "Товар арт. 12345",
                  "quantity": 1.000,
                  "amount": {
                    "value": "7.00",
                    "currency": "RUB"
                  },
                  "vat_code": 2,
                  "payment_mode": "full_prepayment",
                  "payment_subject": "commodity"
                },
                {
                  "description": "Товар арт. 67890",
                  "quantity": 3.000,
                  "amount": {
                    "value": "1.00",
                    "currency": "RUB"
                  },
                  "vat_code": 2,
                  "payment_mode": "full_prepayment",
                  "payment_subject": "commodity"
                }
              ]
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
            'receipt'=> [
                'customer' => [
                    'full_name' => 'Иванов Иван Иванович',
                    'email' => 'user@example.com'
                ],
                'items' => [
                    [
                        'description'=> 'Товар арт. 12345',
                        'amount'=> [
                            'value'=> '7.00',
                            'currency'=> 'RUB',
                        ],
                        'quantity'=> 1.000,
                        'vat_code' => 2,
                        'payment_mode' => 'full_prepayment',
                        'payment_subject' => 'commodity',
                    ],
                    [
                        'description'=> 'Товар арт. 67890',
                        'amount'=> [
                            'value'=> '1.00',
                            'currency'=> 'RUB',
                        ],
                        'quantity'=> 3.000,
                        'vat_code' => 2,
                        'payment_mode' => 'full_prepayment',
                        'payment_subject' => 'commodity',
                    ],
                ]
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
        "receipt": {
            "customer": {
                "full_name": "Иванов Иван Иванович",
                "email": "user@example.com"
            },
            "items": [
                {
                  "description": "Товар арт. 12345",
                  "quantity": 1.000,
                  "amount": {
                    "value": "7.00",
                    "currency": "RUB"
                  },
                  "vat_code": 2,
                  "payment_mode": "full_prepayment",
                  "payment_subject": "commodity"
                },
                {
                  "description": "Товар арт. 67890",
                  "quantity": 3.000,
                  "amount": {
                    "value": "1.00",
                    "currency": "RUB"
                  },
                  "vat_code": 2,
                  "payment_mode": "full_prepayment",
                  "payment_subject": "commodity"
                }
            ]
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

Далее выполняйте действия, как с обычным счетом: получите ссылку на счет, отправьте ее пользователю и дождитесь оплаты.

ЮKassa отправит данные для чека в онлайн-кассу, когда пользователь завершит оплату выставленного счета.

**Шаг 3.** Убедитесь, что чек сформирован. Статус регистрации чека можно проверить в [объекте платежа](https://yookassa.ru/developers/api#payment_object). Порядок действий зависит от того, какое [решение для работы с чеками](https://yookassa.ru/developers/payment-acceptance/receipts/basics) вы используете:

Для компаний и ИП, которые используют чеки от ЮKassa

Для компаний и ИП, которые отправляют чеки сторонней онлайн-кассе по сценарию Платеж и чек одновременно

Для компаний и ИП, которые отправляют чеки сторонней онлайн-кассе по сценарию Сначала чек, потом платеж

Также статус регистрации чека можно проверить в [личном кабинете](https://yookassa.ru/my) ЮKassa в истории платежей.

**Шаг 4.** При необходимости [получите идентификатор платежа](https://yookassa.ru/developers/payment-acceptance/scenario-extensions/invoices/payments#how-to-get-payment-id) для выполнения других операций.

Готово!

Чек прихода отдельным запросом

Если вы используете [решение ЮKassa для сторонних онлайн-касс](https://yookassa.ru/developers/payment-acceptance/receipts/54fz/other-services/basics) и формируете чеки по сценарию [Сначала платеж, потом чек](https://yookassa.ru/developers/payment-acceptance/receipts/54fz/other-services/basics#receipt-after-payment), данные для чека при платеже необходимо передавать после создания счета.

Как отправить данные для чека:

**Шаг 1.** Перед выставлением счета получите от пользователя его данные для доставки ему чека: адрес электронной почты или номер телефона.

**Шаг 2.** [Создайте счет](https://yookassa.ru/developers/payment-acceptance/scenario-extensions/invoices/payments#payment-acceptance) как обычно. Данные для чека передавать не нужно.

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

Далее выполняйте действия, как с обычным счетом: получите ссылку на счет, отправьте ее пользователю и дождитесь оплаты.

**Шаг 3.** Дождитесь, когда платеж перейдет в статус `waiting_for_capture` (для платежей в две стадии) или `succeeded` (для платежей в одну стадию).

**Шаг 4.** [Получите идентификатор платежа](https://yookassa.ru/developers/payment-acceptance/scenario-extensions/invoices/payments#how-to-get-payment-id).

**Шаг 5.** [Создайте чек](https://yookassa.ru/developers/payment-acceptance/receipts/54fz/other-services/payments#create_receipt).

**Шаг 6.** Убедитесь, что чек сформирован. Для этого дождитесь, когда [объект чека](https://yookassa.ru/developers/api#receipt_object) перейдет в статус `succeeded`.

Также статус регистрации чека можно проверить в [личном кабинете](https://yookassa.ru/my) ЮKassa в истории платежей.

ЮKassa ожидает от онлайн-кассы ответа о регистрации чека в течение одного дня. Если что-то пойдет не так, сформируйте чек вручную в своей онлайн-кассе.

Готово!

Чеки при платежах в две стадии и чеки зачета предоплаты

При формировании большинства чеков не имеет значения, как создан платеж: по выставленному счету или стандартно.

Воспользуйтесь инструкциями для обычных платежей, если вы:

- принимаете платежи в [две стадии](https://yookassa.ru/developers/payment-acceptance/getting-started/payment-process#capture-and-cancel) и списываете оплату частично;
- формируете чеки зачета предоплаты;
- для 54 ФЗ: отправляете чеки сторонней онлайн-кассе по сценарию [Сначала платеж, потом чек](https://yookassa.ru/developers/payment-acceptance/receipts/54fz/other-services/basics#receipt-after-payment).

Для формирования таких чеков вам потребуется передать в запросе идентификатор платежа — вы получите его в уведомлении по платежу от ЮKassa или в ответе на запрос информации по счету. [Подробнее о получении идентификатора платежа](https://yookassa.ru/developers/payment-acceptance/scenario-extensions/invoices/payments#how-to-get-payment-id)

Подробнее о чеках при платежах:

- [54-ФЗ: чеки от ЮKassa](https://yookassa.ru/developers/payment-acceptance/receipts/54fz/yoomoney/payments);
- [54-ФЗ: сторонняя онлайн-касса](https://yookassa.ru/developers/payment-acceptance/receipts/54fz/other-services/payments).

Чеки при возвратах

При возврате платежей, созданных при выставлении счетов по API, чеки формируются стандартно. Подробнее о формировании чека возврата прихода:

- [54-ФЗ: чеки от ЮKassa](https://yookassa.ru/developers/payment-acceptance/receipts/54fz/yoomoney/refunds);
- [54-ФЗ: сторонняя онлайн-касса](https://yookassa.ru/developers/payment-acceptance/receipts/54fz/other-services/refunds).

Для чеков при возвратах нужно передавать идентификатор платежа, если вы:

- оформляете частичный возврат;
- используете сценарий отправки чеков [Сначала платеж, потом чек](https://yookassa.ru/developers/payment-acceptance/receipts/54fz/other-services/basics#receipt-after-payment) и принимаете платежи в две стадии, списывая оплату [частично](https://yookassa.ru/developers/payment-acceptance/getting-started/payment-process#capture-partly).

[Подробнее о получении идентификатора платежа](https://yookassa.ru/developers/payment-acceptance/scenario-extensions/invoices/payments#how-to-get-payment-id)

Что почитать еще

[Оплата с соблюдением требований 54-ФЗ](https://yookassa.ru/developers/payment-acceptance/receipts/54fz/basics)

[Прием платежа по выставленному счету](https://yookassa.ru/developers/payment-acceptance/scenario-extensions/invoices/payments)

[Чеки в справочнике API ЮKassa](https://yookassa.ru/developers/api#receipt)
