<!-- Источник: https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/other/electronic-certificate/ready-made-payment-form -->
<!-- Полная копия статьи официальной документации ЮKassa, сохранено 2026-07-02 -->

# Электронный сертификат: оплата на готовой странице ЮKassa

В этой статье описано, как принимать оплату по электронным сертификатам с использованием готовой страницы ЮKassa.

Как это работает

В этом сценарии вы самостоятельно реализуете выбор способа оплаты. После создания платежа вы перенаправляете пользователя на страницу ЮKassa. На этой странице пользователь введет данные банковской карты «Мир», к которой привязан электронный сертификат.

![Ввод данных банковской карты](https://static.yoomoney.ru/docops-static/images/developers-payments-electronic-certificate-payment-form-redirect-bank-card-data.f3965cae.svg)

Ввод данных банковской карты

После этого пользователь увидит, какие товары будут оплачены по сертификату, а какие по карте, и сможет оплатить покупку.

![Список товаров с оплатой по электронному сертификату и по карте](https://static.yoomoney.ru/docops-static/images/developers-payments-electronic-certificate-payment-form-redirect-articles.e2932719.svg)

Список товаров с оплатой по электронному сертификату и по карте

Если сертификат, привязанный к карте, не подходит для оплаты выбранных товаров, провести платеж не получится. Пользователю нужно вернуться к вам на сайт и выбрать другой способ оплаты.

Для интеграции добавьте на ваш сайт кнопку, по которой можно перейти к оплате. Когда пользователь перейдет по кнопке, получите от ЮKassa ссылку на готовую страницу оплаты и перенаправьте на неё пользователя. Когда пользователь вернется обратно к вам на сайт, запросите у ЮKassa результаты платежа и отобразите их.

Общие сценарии и схемы проведения платежа и возврата

- [Проведение платежа](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/other/electronic-certificate/ready-made-payment-form#scenarios-payment)
- [Возврат платежа](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/other/electronic-certificate/ready-made-payment-form#scenarios-refund)

Проведение платежа

![Проведение платежа (оплата на готовой странице ЮKassa)](https://static.yoomoney.ru/docops-static/images/developers-payments-schema-electronic-certificate-payment-ready-made-form.image.ru.4237000e.svg)

Проведение платежа (оплата на готовой странице ЮKassa)

Как проходит платеж:

1. Пользователь переходит к оплате.
2. Вы создаете платеж — отправляете ЮKassa POST-запрос со списком товаров, которые нужно оплатить по электронному сертификату.
3. ЮKassa возвращает вам созданный объект платежа в статусе `pending` и со ссылкой на платежную форму (параметр `confirmation_url` в объекте платежа).
4. Вы перенаправляете пользователя на страницу оплаты.
5. Пользователь вводит данные карты «Мир», к которой привязан электронный сертификат.
6. ЮKassa отправляет запрос в ФЭС НСПК для одобрения корзины и использования сертификата.
7. ФЭС НСПК возвращает одобренную корзину.
8. ЮKassa отображает пользователю, какие товары будут оплачены по сертификату, какие — банковской картой, а также отображает сумму доплаты.
9. Пользователь подтверждает оплату.
10. ЮKassa запрашивает в НСПК данные для прохождения аутентификации по 3-D Secure.
11. НПСК возвращает необходимые данные.
12. ЮKassa перенаправляет пользователя на страницу прохождения аутентификации.
13. Пользователь проходит аутентификацию.
14. ЮKassa запрашивает в НСПК списание необходимой суммы с карты.
15. НСПК возвращает результат списания.
16. ЮKassa запрашивает в НСПК списание необходимой суммы с сертификата.
17. НСПК возвращает результат списания.
18. Если у вас настроены [уведомления](https://yookassa.ru/developers/using-api/webhooks), ЮKassa присылает уведомление о переходе платежа в статус `succeeded`.
19. Вы запрашиваете информацию о платеже — отправляете ЮKassa GET-запрос с идентификатором платежа.
20. ЮKassa возвращает вам созданный объект платежа в актуальном статусе.
21. Вы сообщаете пользователю результат проведения платежа.
22. Если формируете чек самостоятельно (не через ЮKassa), вы регистрируете чек в онлайн-кассе, затем подаете данные о нём в личном кабинете ЮKassa.
23. ЮKassa передает данные чека в НСПК.
24. НСПК сообщает результат.
25. Вы проверяете в личном кабинете ЮKassa, что чек доставлен в НСПК. При необходимости передаете данные повторно.

[Подробнее о том, как провести платеж](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/other/electronic-certificate/ready-made-payment-form#payment)

Возврат платежа

Это сценарий для ситуации, когда вы возвращаете товары, для оплаты которых использовался электронный сертификат. В остальных случаях возврат стандартный.

![Возврат платежа (оплата была на готовой странице ЮKassa)](https://static.yoomoney.ru/docops-static/images/developers-payments-schema-electronic-certificate-refund-ready-made-form.image.ru.f6da2278.svg)

Возврат платежа (оплата была на готовой странице ЮKassa)

Как проходит возврат:

1. Вы создаете возврат — отправляете ЮKassa POST-запрос со списком товаров, для оплаты которых использовался электронный сертификат и которые нужно вернуть.
2. ЮKassa отправляет запрос в ФЭС НСПК для одобрения возврата.
3. ФЭС НСПК возвращает идентификатор корзины возврата.
4. ЮKassa запрашивает в НСПК возврат необходимой суммы на сертификат.
5. НСПК возвращает результат возврата.
6. При необходимости ЮKassa запрашивает в НСПК возврат необходимой суммы на карту.
7. НСПК возвращает результат возврата.
8. ЮKassa возвращает вам созданный объект возврата в актуальном статусе.
9. Вы сообщаете пользователю результат проведения возврата.
10. Если формируете чек самостоятельно (не через ЮKassa), вы регистрируете чек в онлайн-кассе, затем подаете данные о нём в личном кабинете ЮKassa.
11. ЮKassa передает данные чека в НСПК.
12. НСПК сообщает результат.
13. Вы проверяете в личном кабинете ЮKassa, что чек доставлен в НСПК. При необходимости передаете данные повторно.

[Подробнее о том, как провести возврат](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/other/electronic-certificate/ready-made-payment-form#refund)

Проведение платежа

**Шаг 1**. Когда пользователь перейдет к оплате, [создайте платеж](https://yookassa.ru/developers/api#create_payment): отправьте ЮKassa запрос с данными для аутентификации запроса, ключом идемпотентности и данными для платежа:

- в объекте `amount` передайте общую сумму к оплате;
- в объекте `payment_method_data` передайте код способа оплаты `electronic_certificate` и массив `articles` со списком товаров, для оплаты которых можно использовать электронный сертификат;
- в объекте `confirmation` передайте тип `redirect` и параметр `return_url` с адресом страницы на вашей стороне, на которую пользователь вернется после оплаты;
- в параметре `description` передайте описание платежа, которое пользователь увидит при оплате;
- в параметре `capture` передайте значение `true`, чтобы платеж автоматически перешел в статус `succeeded` после оплаты.

В запросе можно передать любые [другие параметры](https://yookassa.ru/developers/api#create_payment), кроме `save_payment_method`, `payment_method_id`, `payment_token`, `airline`, `transfers`, `deal`.

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
          "value": "5000.00",
          "currency": "RUB"
        },
        "payment_method_data": {
          "type": "electronic_certificate",
          "articles": [
            {
              "article_number": 1,
              "tru_code": "325022153.09000220200000000000",
              "article_code": "NXXXL",
              "article_name": "Трость опорная не регулируемая по высоте, с устройством противоскольжения универсальная NXXXL",
              "quantity": 2,
              "price": {
                "value": "1500.00",
                "currency": "RUB"
              }
            },
            {
              "article_number": 2,
              "tru_code": "325022153.09000220300000000000",
              "article_code": "HQ819",
              "article_name": "Трость опорная регулируемая по высоте, с устройством противоскольжения неуниверсальная HQ819",
              "quantity": 1,
              "price": {
                "value": "1200.00",
                "currency": "RUB"
              }
            }
          ]
        },
        "confirmation": {
          "type": "redirect",
          "return_url": "https://www.example.com/return_url"
        },
        "capture": true,
        "metadata": {
          "order_id": "37"
        },
        "description": "Заказ №37"
      }'
```

**PHP**

```php
<?php
    # Доступно в PHP SDK от ЮKassa, начиная с версии 3.7
    $idempotenceKey = uniqid('', true);
    $payment = $client->createPayment(
        [
            'amount' => [
                'value' => '5000.00',
                'currency' => 'RUB',
            ],
            'payment_method_data' => [
                'type' => 'electronic_certificate',
                'articles' => [
                    [
                        'article_number' => 1,
                        'tru_code' => '325022153.09000220200000000000',
                        'article_code' => 'NXXXL',
                        'article_name' => 'Трость опорная не регулируемая по высоте, с устройством противоскольжения универсальная NXXXL',
                        'quantity' => 2,
                        'price' => [
                            'value' => '1500.00',
                            'currency' => 'RUB',
                        ],
                    ],
                    [
                        'article_number' => 2,
                        'tru_code' => '325022153.09000220300000000000',
                        'article_code' => 'HQ819',
                        'article_name' => 'Трость опорная регулируемая по высоте, с устройством противоскольжения неуниверсальная HQ819',
                        'quantity' => 1,
                        'price' => [
                            'value' => '1200.00',
                            'currency' => 'RUB',
                        ],
                    ],
                ],
            ],
            'confirmation' => [
                'type' => 'redirect',
                'return_url' => 'https://example.com/return_url',
            ],
            'capture' => true,
            'description' => 'Оплата заказа №37',
            'metadata' => [
                'order_id' => '37',
            ],
        ],
        $idempotenceKey
    );
    
    //get confirmation url
    $confirmationUrl = $response->getConfirmation()->getConfirmationUrl();
?>
```

**Python**

```python
from yookassa import Payment
import uuid

idempotence_key = str(uuid.uuid4())
payment = Payment.create({
    "amount": {
        "value": "5000.00",
        "currency": "RUB"
    },
    "payment_method_data": {
        "type": "electronic_certificate",
        "articles": [
            {
                "article_number": 1,
                "tru_code": "325022153.09000220200000000000",
                "article_code": "NXXXL",
                "article_name": "Трость опорная не регулируемая по высоте, с устройством противоскольжения универсальная NXXXL",
                "quantity": 2,
                "price": {
                    "value": "1500.00",
                    "currency": "RUB"
                }
            },
            {
                "article_number": 2,
                "tru_code": "325022153.09000220300000000000",
                "article_code": "HQ819",
                "article_name": "Трость опорная регулируемая по высоте, с устройством противоскольжения неуниверсальная HQ819",
                "quantity": 1,
                "price": {
                    "value": "1200.00",
                    "currency": "RUB"
                }
            }
        ]
    },
    "confirmation": {
        "type": "redirect",
        "return_url": "https://example.com/return_url"
    },
    "capture": True,
    "description": "Оплата заказа №37",
    "metadata": {
        "order_id": "37"
    }
}, idempotence_key)

# get confirmation url
confirmation_url = payment.confirmation.confirmation_url
```

В ответ на запрос вернется [объект платежа](https://yookassa.ru/developers/api#payment_object) в актуальном статусе.

**Шаг 2.** Перенаправьте пользователя на страницу ЮKassa, адрес которой придет в `confirmation_url`. Это ссылка на готовую страницу ЮKassa.

**Пример созданного объекта платежа**

**JSON**

```json
{
  "id": "2d78da66-000f-5000-9000-1297ba86ffa5",
  "status": "pending",
  "amount": {
    "value": "5000.00",
    "currency": "RUB"
  },
  "description": "Заказ №37",
  "recipient": {
    "account_id": "100500",
    "gateway_id": "100700"
  },
  "payment_method": {
    "type": "electronic_certificate",
    "id": "2d78da66-000f-5000-9000-1297ba86ffa5",
    "saved": false
  },
  "created_at": "2024-01-28T15:21:05.441Z",
  "confirmation": {
    "type": "redirect",
    "enforce": true,
    "return_url": "http://return.url",
    "confirmation_url": "https:// yoomoney.ru/checkout/payments/v2/contract/electronic-certificate?orderId=2d78da66-000f-5000-9000-1297ba86ffa5"
  },
  "test": false,
  "paid": false,
  "refundable": false,
  "metadata": {
    "order_id": "37"
  }
}
```

**Шаг 3.** Дождитесь успешного завершения платежа: подождите, когда придет [уведомление](https://yookassa.ru/developers/using-api/webhooks) от ЮKassa, или периодически отправляйте запросы, чтобы получить [информацию о платеже](https://yookassa.ru/developers/api#get_payment).

**Пример платежа в статусе succeeded**

**JSON**

```json
{
  "id": "2d78da66-000f-5000-9000-1297ba86ffa5",
  "status": "succeeded",
  "amount": {
    "value": "5000.00",
    "currency": "RUB"
  },
  "income_amount": {
    "value": "4825.00",
    "currency": "RUB"
  },
  "recipient": {
    "account_id": "100500",
    "gateway_id": "100700"
  },
  "payment_method": {
    "type": "electronic_certificate",
    "id": "2d78da66-000f-5000-9000-1297ba86ffa5",
    "saved": false,
    "card": {
      "first6": "555555",
      "last4": "4444",
      "expiry_year": "2030",
      "expiry_month": "01",
      "card_type": "Mir"
    },
    "electronic_certificate": {
      "amount": {
        "value": "2700.00",
        "currency": "RUB"
      },
      "basket_id": "445923711677676901483590"
    },
    "articles": [
      {
        "article_number": 1,
        "tru_code": "325022153.09000220200000000000",
        "article_code": "NXXXL",
        "certificates": [
          {
            "certificate_id": "907581400329309796796024853331",
            "tru_amount": 1,
            "max_compensation": {
              "value": "1500.00",
              "currency": "RUB"
            },
            "compensation": {
              "value": "1500.00",
              "currency": "RUB"
            }
          }
        ]
      },
      {
        "article_number": 2,
        "tru_code": "325022153.09000220300000000000",
        "article_code": "HQ819",
        "certificates": [
          {
            "certificate_id": "277321977384515300457417391374",
            "tru_amount": 1,
            "max_compensation": {
              "value": "1200.00",
              "currency": "RUB"
            },
            "compensation": {
              "value": "1200.00",
              "currency": "RUB"
            }
          }
        ]
      }
    ]
  },
  "captured_at": "2024-01-28T15:21:38.320Z",
  "created_at": "2024-01-28T15:21:05.441Z",
  "test": false,
  "refunded_amount": {
    "value": "0.00",
    "currency": "RUB"
  },
  "paid": true,
  "refundable": true,
  "metadata": {
    "order_id": "37"
  },
  "description": "Заказ №37"
}
```

**Шаг 4.** Когда пользователь вернется на `return_url`, отобразите результат проведения платежа (успех или неудача) в зависимости от [статуса платежа](https://yookassa.ru/developers/payment-acceptance/getting-started/payment-process#lifecycle).

**Шаг 5.** Убедитесь, что сформирован чек прихода:

- Если используете [решения ЮKassa для отправки чеков в налоговую](https://yookassa.ru/developers/payment-acceptance/receipts/basics), убедитесь в [личном кабинете](https://yookassa.ru/my) или по API, что чек успешно зарегистрирован в онлайн-кассе.
- Если отправляете чеки самостоятельно (не через ЮKassa), зарегистрируйте чек в онлайн-кассе.

**Шаг 6.** Убедитесь, что данные о чеках доставлены в НСПК:

- Если отправляете чеки через ЮKassa, убедитесь в [личном кабинете](https://yookassa.ru/my), что данные доставлены в НСПК. Если что-то пошло не так, повторите отправку через личный кабинет и проверьте еще раз статус доставки в НСПК. [Как отправить данные повторно](https://yookassa.ru/docs/support/payments/tax-sync/mir-certificates#change-and-send-again)
- Если отправляете чеки самостоятельно, передайте данные чека через [личный кабинет](https://yookassa.ru/my) и убедитесь, что они доставлены. [Как подать данные в НСПК через личный кабинет ЮKassa](https://yookassa.ru/docs/support/payments/tax-sync/mir-certificates#send-independently)

Готово!

Возврат платежа

Можно делать [полные](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/other/electronic-certificate/ready-made-payment-form#refund-full) и [частичные](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/other/electronic-certificate/ready-made-payment-form#refund-partial) возвраты.

Если при возврате на сертификат что-то пошло не так, вся операция отменяется, нужно повторять ее заново. [Подробнее о неуспешных возвратах](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/other/electronic-certificate/ready-made-payment-form#refund-declined)

Если возврат успешно прошел, деньги на сертификат и карту зачислятся в среднем в течение трех дней. [Подробнее о сроках возврата](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/other/electronic-certificate/basics#how-it-works-refunds-processing-time)

Полный возврат

**Шаг 1.** [Создайте возврат](https://yookassa.ru/developers/api#create_refund): отправьте ЮKassa запрос с данными для аутентификации запроса, ключом идемпотентности и данными для проведения возврата:

- в объекте `amount` передайте общую сумму возврата;
- в параметре `payment_id` передайте идентификатор возвращаемого платежа;
- в объекте `refund_method_data` передайте код способа оплаты `electronic_certificate` и массив `articles` со списком товаров, для оплаты которых использовался сертификат (соответствуют списку товаров в объекте платежа);
- при необходимости в параметре `description` передайте описание возврата.

В запросе можно передать любые [другие параметры](https://yookassa.ru/developers/api#create_refund), кроме `sources`, `deal`.

**Пример запроса на создание полного возврата**

**cURL**

```bash
curl https://api.yookassa.ru/v3/refunds \
  -X POST \
  -u <Идентификатор магазина>:<Секретный ключ> \
  -H 'Idempotence-Key: <Ключ идемпотентности>' \
  -H 'Content-Type: application/json' \
  -d '{
        "payment_id": "2d78da66-000f-5000-9000-1297ba86ffa5",
        "description": "Возврат заказа №37",
        "amount": {
          "value": "5000.00",
          "currency": "RUB"
        },
        "refund_method_data": {
          "type": "electronic_certificate",
          "articles": [
            {
              "article_number": 1,
              "payment_article_number": 1,
              "tru_code": "325022153.09000220200000000000",
              "quantity": 1
            },
            {
              "article_number": 2,
              "payment_article_number": 2,
              "tru_code": "325022153.09000220300000000000",
              "quantity": 1
            }
          ]
        }
      }'
```

**PHP**

```php
<?php
    # Доступно в PHP SDK от ЮKassa, начиная с версии 3.7
    $idempotenceKey = uniqid('', true);
    $response = $client->createRefund(
        [
            'payment_id' => '2d78da66-000f-5000-9000-1297ba86ffa5',
            'description' => 'Возврат заказа №37',
            'amount' => [
                'value' => '5000.00',
                'currency' => 'RUB',
            ],
            'refund_method_data'=> [
                'type'=> 'electronic_certificate',
                'articles' => [
                    [
                        'article_number' => 1,
                        'payment_article_number' => 1,
                        'tru_code' => '325022153.09000220200000000000',
                        'quantity' => 1
                    ],
                    [
                        'article_number' => 2,
                        'payment_article_number' => 2,
                        'tru_code' => '325022153.09000220300000000000',
                        'quantity' => 1
                    ]
                ],
            ],
        ],
        $idempotenceKey
    );
?>
```

**Python**

```python
from yookassa import Refund

payment = Refund.create({
    "payment_id": "2d78da66-000f-5000-9000-1297ba86ffa5",
    "description": "Возврат заказа №37",
    "amount": {
        "value": "5000.00",
        "currency": "RUB"
    },
    "refund_method_data": {
        "type": "electronic_certificate",
        "articles": [
            {
                "article_number": 1,
                "payment_article_number": 1,
                "tru_code": "325022153.09000220200000000000",
                "quantity": 1
            },
            {
                "article_number": 2,
                "payment_article_number": 2,
                "tru_code": "325022153.09000220300000000000",
                "quantity": 1
            }
        ]
    }
})
```

В ответ на запрос вернется [объект возврата](https://yookassa.ru/developers/api#refund_object) в актуальном статусе.

**Пример объекта возврата в статусе succeeded**

**JSON**

```json
{
  "id": "216749f7-0016-50be-b000-078d43a63ae4",
  "status": "succeeded",
  "amount": {
    "value": "5000.00",
    "currency": "RUB"
  },
  "description": "Возврат заказа №37",
  "created_at": "2024-01-29T15:21:38.320Z",
  "payment_id": "2d78da66-000f-5000-9000-1297ba86ffa5",
  "refund_method": {
    "type": "electronic_certificate",
    "electronic_certificate": {
      "basket_id": "110200010001100000000001",
      "amount": {
        "value": "2700.00",
        "currency": "RUB"
      }
    },
    "articles": [
      {
        "article_number": 1,
        "payment_article_number": 1,
        "tru_code": "325022153.09000220200000000000",
        "quantity": 1
      },
      {
        "article_number": 2,
        "payment_article_number": 2,
        "tru_code": "325022153.09000220300000000000",
        "quantity": 1
      }
    ]
  },
  "metadata": {}
}
```

**Шаг 2.** Убедитесь, что сформирован чек возврата прихода:

- Если используете [решения ЮKassa для отправки чеков в налоговую](https://yookassa.ru/developers/payment-acceptance/receipts/basics), убедитесь в [личном кабинете](https://yookassa.ru/my) или по API, что чек успешно зарегистрирован в онлайн-кассе.
- Если отправляете чеки самостоятельно (не через ЮKassa), зарегистрируйте чек в онлайн-кассе.

**Шаг 3.** Убедитесь, что данные о чеках доставлены в НСПК:

- Если отправляете чеки через ЮKassa, убедитесь в [личном кабинете](https://yookassa.ru/my), что данные доставлены в НСПК. Если что-то пошло не так, повторите отправку через личный кабинет и проверьте еще раз статус доставки в НСПК. [Как отправить данные повторно](https://yookassa.ru/docs/support/payments/tax-sync/mir-certificates#change-and-send-again)
- Если отправляете чеки самостоятельно, передайте данные чека через [личный кабинет](https://yookassa.ru/my) и убедитесь, что они доставлены. [Как подать данные в НСПК через личный кабинет ЮKassa](https://yookassa.ru/docs/support/payments/tax-sync/mir-certificates#send-independently)

Готово!

Частичный возврат

Если вы возвращаете товары, для оплаты которых использовался электронный сертификат (полностью или частично), то такой возврат создается аналогично [полному](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/other/electronic-certificate/ready-made-payment-form#refund-full). Единственное отличие: в параметре `amount` нужно передать ту часть от суммы принятого платежа, которую вы хотите вернуть, а в массиве `articles` указать только те товары, которые возвращаете.

**Пример запроса на создание частичного возврата**

**cURL**

```bash
curl https://api.yookassa.ru/v3/refunds \
  -X POST \
  -u <Идентификатор магазина>:<Секретный ключ> \
  -H 'Idempotence-Key: <Ключ идемпотентности>' \
  -H 'Content-Type: application/json' \
  -d '{
        "payment_id": "2d78da66-000f-5000-9000-1297ba86ffa5",
        "description": "Возврат заказа №37",
        "amount": {
          "value": "2000.00",
          "currency": "RUB"
        },
        "refund_method_data": {
          "type": "electronic_certificate",
          "articles": [
            {
              "article_number": 1,
              "payment_article_number": 2,
              "tru_code": "325022153.09000220300000000000",
              "quantity": 1
            }
          ]
        }
      }'
```

**PHP**

```php
<?php
    # Доступно в PHP SDK от ЮKassa, начиная с версии 3.7
    $idempotenceKey = uniqid('', true);
    $response = $client->createRefund(
        [
            'payment_id' => '2d78da66-000f-5000-9000-1297ba86ffa5',
            'description' => 'Возврат заказа №37',
            'amount' => [
                'value' => '2000.00',
                'currency' => 'RUB',
            ],
            'refund_method_data'=> [
                'type'=> 'electronic_certificate',
                'articles' => [
                    [
                        'article_number' => 1,
                        'payment_article_number' => 2,
                        'tru_code' => '325022153.09000220300000000000',
                        'quantity' => 1
                    ]
                ],
            ],
        ],
        $idempotenceKey
    );
?>
```

**Python**

```python
from yookassa import Refund

payment = Refund.create({
    "payment_id": "2d78da66-000f-5000-9000-1297ba86ffa5",
    "description": "Возврат заказа №37",
    "amount": {
        "value": "2000.00",
        "currency": "RUB"
    },
    "refund_method_data": {
        "type": "electronic_certificate",
        "articles": [
            {
                "article_number": 1,
                "payment_article_number": 2,
                "tru_code": "325022153.09000220300000000000",
                "quantity": 1
            }
        ]
    }
})
```

Если возвращаете только те товары из корзины, которые оплачивались банковской картой (доплата), то возврат [стандартный](https://yookassa.ru/developers/payment-acceptance/after-the-payment/refunds), объект `refund_method_data` передавать не нужно. Сумма возврата (`amount`) должна быть не больше суммы доплаты, иначе возврат не пройдет.

**Пример запроса на создание частичного возврата (только доплата)**

**cURL**

```bash
curl https://api.yookassa.ru/v3/refunds \
  -X POST \
  -u <Идентификатор магазина>:<Секретный ключ> \
  -H 'Idempotence-Key: <Ключ идемпотентности>' \
  -H 'Content-Type: application/json' \
  -d '{
        "payment_id": "2d78da66-000f-5000-9000-1297ba86ffa5",
        "description": "Возврат заказа №37",
        "amount": {
          "value": "2300.00",
          "currency": "RUB"
        }
      }'
```

**PHP**

```php
<?php
    $idempotenceKey = uniqid('', true);
    $response = $client->createRefund(
        array(
            'payment_id' => '2d78da66-000f-5000-9000-1297ba86ffa5',
            'description' => 'Возврат заказа №37',
            'amount' => array(
                'value' => '2300.00',
                'currency' => 'RUB',
            ),
        ),
        $idempotenceKey
    );
?>
```

**Python**

```python
from yookassa import Refund

payment = Refund.create({
    "payment_id": "2d78da66-000f-5000-9000-1297ba86ffa5",
    "description": "Возврат заказа №37",
    "amount": {
        "value": "2300.00",
        "currency": "RUB"
    }
})
```

Неуспешные возвраты

Если оплата товара была частично по сертификату, частично по банковской карте, то сначала деньги возвращаются на сертификат, и если всё прошло успешно, то оставшаяся часть суммы возвращается на карту. Если при возврате на сертификат что-то пошло не так, вся операция отменяется, нужно повторять ее заново.

Причина отмены будет указана в объекте `cancellation_details`. [Подробнее о причинах отмены возврата](https://yookassa.ru/developers/payment-acceptance/after-the-payment/refunds#declined-refunds-cancellation-details-reason)

**Пример объекта возврата в статусе canceled**

**JSON**

```json
{
  "id": "216749f7-0016-50be-b000-078d43a63ae4",
  "payment_id": "2d78da66-000f-5000-9000-1297ba86ffa5",
  "status": "canceled",
  "cancellation_details": {
    "party": "refund_network",
    "reason": "payment_tru_code_not_found"
  },
  "created_at": "2024-01-29T15:21:38.320Z",
  "amount": {
    "value": "1200.00",
    "currency": "RUB"
  },
  "description": "Возврат заказа №37",
  "metadata": {}
}
```

Что почитать еще

[Основы проведения платежей](https://yookassa.ru/developers/payment-acceptance/getting-started/payment-process)

[Неуспешные платежи](https://yookassa.ru/developers/payment-acceptance/after-the-payment/declined-payments)

[Отправка чеков в налоговую](https://yookassa.ru/developers/payment-acceptance/receipts/basics)

[Как отправить в НСПК данные чека](https://yookassa.ru/docs/support/payments/tax-sync/mir-certificates)
