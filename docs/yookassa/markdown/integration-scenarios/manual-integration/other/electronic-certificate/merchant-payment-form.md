<!-- Источник: https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/other/electronic-certificate/merchant-payment-form -->
<!-- Полная копия статьи официальной документации ЮKassa, сохранено 2026-07-02 -->

# Электронный сертификат: оплата со сбором данных на вашей стороне

В этой статье описано, как принимать оплату по электронным сертификатам с использованием вашей страницы оплаты.

Чтобы использовать этот вариант интеграции, необходимо подтвердить соответствие определенному уровню PCI DSS (Payment Card Industry Data Security Standard). Для этого заполните лист самооценки SAQ D. [Подробнее о самооценке по PCI DSS](https://www.nspk.ru/cards-mir/security/standart-pcidss/self-assessment/)

Как это работает

В этом сценарии вы самостоятельно реализуете выбор способа оплаты. Вы на своей стороне получаете данные банковской карты пользователя, к которой привязан сертификат. Одобряете в ФЭС НСПК использование сертификата. После этого создаете платеж в ЮKassa и дожидаетесь, когда пользователь подтвердит оплату.

Для интеграции добавьте на ваш сайт кнопку, по которой пользователь перейдет к оплате, а также платежную форму для получения данных банковской карты. Когда пользователь введет данные, одобрите использование сертификата в ФЭС НСПК. После этого получите от ЮKassa ссылку на страницу аутентификации по 3-D Secure и перенаправьте на неё пользователя. Когда пользователь вернется обратно к вам на сайт, запросите у ЮKassa результаты платежа.

Общие сценарии и схемы проведения платежа и возврата

- [Проведение платежа](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/other/electronic-certificate/merchant-payment-form#scenarios-payment)
- [Возврат платежа](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/other/electronic-certificate/merchant-payment-form#scenarios-refund)

Проведение платежа

![Проведение платежа (оплата со сбором данных на вашей стороне)](https://static.yoomoney.ru/docops-static/images/developers-payments-schema-electronic-certificate-payment-merchant-form.image.ru.cd7af932.svg)

Проведение платежа (оплата со сбором данных на вашей стороне)

Как проходит платеж:

1. Пользователь переходит к оплате.
2. Вы запрашиваете у пользователя данные банковской карты «Мир», к которой привязан электронный сертификат.
3. Пользователь вводит данные карты.
4. Вы запрашиваете в ФЭС НСПК предварительное одобрение использования сертификата — отправляете ФЭС НСПК POST-запрос с данными банковской карты и со списком товаров, которые можно оплатить по электронному сертификату.
5. ФЭС НСПК возвращает вам идентификатор корзины покупки, сумму к оплате по сертификату и одобренные товары.
6. Вы создаете платеж — отправляете ЮKassa POST-запрос с данными банковской карты «Мир», идентификатором корзины покупки и суммой к оплате по сертификату.
7. ЮKassa возвращает вам созданный объект платежа в статусе `pending` и со ссылкой на страницу прохождения аутентификации по 3-D Secure.
8. Вы перенаправляете пользователя на эту страницу.
9. Пользователь проходит аутентификацию.
10. ЮKassa запрашивает в НСПК списание необходимой суммы с карты.
11. НСПК возвращает результат списания.
12. ЮKassa запрашивает в НСПК списание необходимой суммы с сертификата.
13. НСПК возвращает результат списания.
14. Если у вас настроены [уведомления](https://yookassa.ru/developers/using-api/webhooks), ЮKassa присылает уведомление о переходе платежа в статус `succeeded`.
15. Вы запрашиваете информацию о платеже — отправляете ЮKassa GET-запрос с идентификатором платежа.
16. ЮKassa возвращает вам созданный объект платежа в актуальном статусе.
17. Вы сообщаете пользователю результат проведения платежа.
18. Если формируете чек самостоятельно (не через ЮKassa), вы регистрируете чек в онлайн-кассе, затем подаете данные о нём в личном кабинете ЮKassa.
19. ЮKassa передает данные чека в НСПК.
20. НСПК сообщает результат.
21. Вы проверяете в личном кабинете ЮKassa, что чек доставлен в НСПК. При необходимости передаете данные повторно.

[Подробнее о том, как провести платеж](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/other/electronic-certificate/merchant-payment-form#payment)

Возврат платежа

Это сценарий для ситуации, когда вы возвращаете товары, для оплаты которых использовался электронный сертификат. В остальных случаях возврат стандартный.

![Возврат платежа (оплата была со сбором данных на вашей стороне)](https://static.yoomoney.ru/docops-static/images/developers-payments-schema-electronic-certificate-refund-merchant-form.image.ru.aed96001.svg)

Возврат платежа (оплата была со сбором данных на вашей стороне)

Как проходит возврат:

1. Вы запрашиваете в ФЭС НСПК предварительное одобрение возврата — отправляете ФЭС НСПК POST-запрос с идентификатором корзины покупки, данными банковской карты и другими данным.
2. ФЭС НСПК возвращает вам идентификатор корзины возврата.
3. Вы создаете возврат — отправляете ЮKassa POST-запрос с идентификатором корзины возврата.
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

[Подробнее о том, как провести возврат](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/other/electronic-certificate/merchant-payment-form#refund)

Проведение платежа

**Шаг 1.** Получите от пользователя данные банковской карты, к которой привязан электронный сертификат.

**Шаг 2.** Отправьте ФЭС НСПК запрос на предварительное одобрение использования сертификата (Pre-Auth). В запросе передайте данные банковской карты «Мир», к которой привязан электронный сертификат, корзину покупки и другие данные. [Подробнее в документации API ФЭС](https://www.nspk.ru/developer/api-fes/#operation/preAuthPurchase)

В ответе вернется идентификатор корзины покупки `purchaseBasketId`, а также сумма к оплате с использованием сертификата `totalCertAmount`. Эти данные нужны для проведения платежа через ЮKassa.

Срок жизни идентификатора корзины (`purchaseBasketId`) — 30 минут.

**Шаг 3**. [Создайте платеж](https://yookassa.ru/developers/api#create_payment): отправьте ЮKassa запрос с данными для аутентификации запроса, ключом идемпотентности и данными для платежа:

- в объекте `amount` передайте общую сумму к оплате;
- в объекте `payment_method_data` передайте:
  - параметр `type` с кодом способа оплаты `electronic_certificate`;
  - объект `card` с данными банковской карты «Мир», к которой привязан электронный сертификат;
  - объект `electronic_certificate` с идентификатором корзины покупки (значение параметра `purchaseBasketId` из предыдущего шага) и суммой сертификата (значение `totalCertAmount` из предыдущего шага);
- в объекте `confirmation` передайте тип `redirect` и параметр `return_url` с адресом страницы на вашей стороне, на которую пользователь вернется после оплаты;
- в параметре `description` передайте описание платежа;
- в параметре `capture` передайте значение `true`, чтобы платеж автоматически перешел в статус `succeeded` после оплаты.

В запросе можно передать любые [другие параметры](https://yookassa.ru/developers/api#create_payment), кроме `save_payment_method`, `payment_method_id`, `payment_token`, `airline`, `transfers`, `deal`.

Создайте платеж в течение 30 минут с того момента, как получите идентификатор корзины покупки. Если передадите идентификатор с истекшим сроком жизни, платеж не пройдет.

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
            "card": {
              "number": "5555555555554477",
              "expiry_year": "2025",
              "expiry_month": "07",
              "csc": "012",
              "cardholder": "Cardholder"
            },
            "electronic_certificate": {
              "basket_id": "445923711677676901483590",
              "amount": {
                "value": "2700.00",
                "currency": "RUB"
              }
            }
        },
        "confirmation": {
            "type": "redirect",
            "return_url": "https://example.com/return_url"
        },
        "capture": true,
        "description": "Оплата заказа №37",
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
    $payment = $client->createPayment(
        [
            'amount' => [
                'value' => '5000.00',
                'currency' => 'RUB',
            ],
            'payment_method_data' => [
                'type' => 'electronic_certificate',
                'card' => [
                    'number' => '5555555555554477',
                    'expiry_year' => '2025',
                    'expiry_month' => '07',
                    'csc' => '012',
                    'cardholder' => 'Cardholder',
                ],
                'electronic_certificate' => [
                    'basket_id' => '445923711677676901483590',
                    'amount' => [
                        'value' => '2700.00',
                        'currency' => 'RUB',
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
        "card": {
            "number": "5555555555554477",
            "expiry_year": "2025",
            "expiry_month": "07",
            "csc": "012",
            "cardholder": "Cardholder"
        },
        "electronic_certificate": {
            "basket_id": "445923711677676901483590",
            "amount": {
                "value": "2700.00",
                "currency": "RUB"
            }
        }
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

**Шаг 4.** Если объект платежа вернется в статусе `pending`, перенаправьте пользователя на страницу ЮKassa, адрес которой придет в `confirmation_url`. Это ссылка для прохождения аутентификации по 3-D Secure. Она действует 1 час. Если пользователь не пройдет аутентификацию за это время, ЮKassa отменит платеж.

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

**Шаг 5.** Дождитесь успешного завершения платежа: подождите, когда придет [уведомление](https://yookassa.ru/developers/using-api/webhooks) от ЮKassa, или периодически отправляйте запросы, чтобы получить [информацию о платеже](https://yookassa.ru/developers/api#get_payment).

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

**Шаг 6.** Когда пользователь вернется на `return_url`, отобразите результат проведения платежа (успех или неудача) в зависимости от [статуса платежа](https://yookassa.ru/developers/payment-acceptance/getting-started/payment-process#lifecycle).

**Шаг 7.** Убедитесь, что сформирован чек прихода:

- Если используете [решения ЮKassa для отправки чеков в налоговую](https://yookassa.ru/developers/payment-acceptance/receipts/basics), убедитесь в [личном кабинете](https://yookassa.ru/my) или по API, что чек успешно зарегистрирован в онлайн-кассе.
- Если отправляете чеки самостоятельно (не через ЮKassa), зарегистрируйте чек в онлайн-кассе.

**Шаг 8.** Убедитесь, что данные о чеках доставлены в НСПК:

- Если отправляете чеки через ЮKassa, убедитесь в [личном кабинете](https://yookassa.ru/my), что данные доставлены в НСПК. Если что-то пошло не так, повторите отправку через личный кабинет и проверьте еще раз статус доставки в НСПК. [Как отправить данные повторно](https://yookassa.ru/docs/support/payments/tax-sync/mir-certificates#change-and-send-again)
- Если отправляете чеки самостоятельно, передайте данные чека через [личный кабинет](https://yookassa.ru/my) и убедитесь, что они доставлены. [Как подать данные в НСПК через личный кабинет ЮKassa](https://yookassa.ru/docs/support/payments/tax-sync/mir-certificates#send-independently)

Готово!

Возврат платежа

Можно делать [полные](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/other/electronic-certificate/merchant-payment-form#refund-full) и [частичные](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/other/electronic-certificate/merchant-payment-form#refund-partial) возвраты.

Если при возврате на сертификат что-то пошло не так, вся операция отменяется, нужно повторять ее заново. [Подробнее о неуспешных возвратах](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/other/electronic-certificate/merchant-payment-form#refund-declined)

Если возврат успешно прошел, деньги на сертификат и карту зачислятся в среднем в течение трех дней. [Подробнее о сроках возврата](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/other/electronic-certificate/basics#how-it-works-refunds-processing-time)

Полный возврат

**Шаг 1.** Отправьте ФЭС НСПК запрос на предварительное одобрение возврата (Refund Pre-Auth). В запросе передайте идентификатор корзины покупки (`purchaseBasketId`), который вы получили при проведении платежа, данные банковской карты «Мир», к которой привязан электронный сертификат, корзину возврата и другие данные. [Подробнее в документации API ФЭС](https://www.nspk.ru/developer/api-fes#operation/preAuthReturn)

В ответ вы получите идентификатор корзины возврата `returnBasketId`, а также сумму, которая вернется на электронный сертификат `totalCertAmount`. Эти данные нужны для проведения возврата через ЮKassa.

Срок жизни идентификатора корзины возврата (`returnBasketId`) — 30 минут.

**Шаг 2.** [Создайте возврат](https://yookassa.ru/developers/api#create_refund): отправьте ЮKassa запрос с данными для аутентификации запроса, ключом идемпотентности и данными для проведения возврата:

- в объекте `amount` передайте общую сумму возврата;
- в параметре `payment_id` передайте идентификатор возвращаемого платежа;
- в объекте `refund_method_data` передайте код способа оплаты `electronic_certificate`, а также объект `electronic_certificate` с идентификатором корзины возврата (значение параметра `returnBasketId` из предыдущего шага) и возвращаемой на сертификат суммой;
- при необходимости в параметре `description` передайте описание возврата.

В запросе можно передать любые [другие параметры](https://yookassa.ru/developers/api#create_refund), кроме `sources`, `deal`.

Создайте возврат в течение 30 минут с того момента, как получите идентификатор корзины возврата. Если передадите идентификатор с истекшим сроком жизни, возврат не пройдет.

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
        "amount": {
            "value": "5000.00",
            "currency": "RUB"
        },
        "refund_method_data": {
            "type": "electronic_certificate",
            "electronic_certificate": {
               "basket_id": "110200010001100000000001",
               "amount": {
                   "value": "2700.00",
                   "currency": "RUB"
                }
            }
        },
        "description": "Возврат заказа №37",
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
    $response = $client->createRefund(
        [
            'payment_id' => '2d78da66-000f-5000-9000-1297ba86ffa5',
            'amount' => [
                'value' => '5000.00',
                'currency' => 'RUB',
            ],
            'refund_method_data'=> [
                'type'=> 'electronic_certificate',
                'electronic_certificate'=> [
                    'basket_id'=> '110200010001100000000001',
                    'amount'=> [
                        'value'=> '2700.00',
                        'currency'=> 'RUB',
                    ],
                ],
            ],
            'description' => 'Возврат заказа №37',
            'metadata' => [
                'order_id' => '37',
            ]
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
    "amount": {
        "value": "5000.00",
        "currency": "RUB"
    },
    "refund_method_data": {
        "type": "electronic_certificate",
        "electronic_certificate": {
           "basket_id": "110200010001100000000001",
           "amount": {
               "value": "2700.00",
               "currency": "RUB"
            }
        }
    },
    "description": "Возврат заказа №37",
    "metadata": {
        "order_id": "37"
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

**Шаг 3.** Убедитесь, что сформирован чек возврата прихода:

- Если используете [решения ЮKassa для отправки чеков в налоговую](https://yookassa.ru/developers/payment-acceptance/receipts/basics), убедитесь в [личном кабинете](https://yookassa.ru/my) или по API, что чек успешно зарегистрирован в онлайн-кассе.
- Если отправляете чеки самостоятельно (не через ЮKassa), зарегистрируйте чек в онлайн-кассе.

**Шаг 4.** Убедитесь, что данные о чеках доставлены в НСПК:

- Если отправляете чеки через ЮKassa, убедитесь в [личном кабинете](https://yookassa.ru/my), что данные доставлены в НСПК. Если что-то пошло не так, повторите отправку через личный кабинет и проверьте еще раз статус доставки в НСПК. [Как отправить данные повторно](https://yookassa.ru/docs/support/payments/tax-sync/mir-certificates#change-and-send-again)
- Если отправляете чеки самостоятельно, передайте данные чека через [личный кабинет](https://yookassa.ru/my) и убедитесь, что они доставлены. [Как подать данные в НСПК через личный кабинет ЮKassa](https://yookassa.ru/docs/support/payments/tax-sync/mir-certificates#send-independently)

Готово!

Частичный возврат

Если вы возвращаете товары, для оплаты которых использовался электронный сертификат (полностью или частично), то такой возврат создается аналогично [полному](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/other/electronic-certificate/merchant-payment-form#refund-full). Единственные отличия: в ФЭС НСПК нужно одобрять только те товары, которые хотите вернуть, а в запросе к ЮKassa в параметре `amount` и в объекте `electronic_certificate` нужно передать только возвращаемую часть суммы.

**Пример запроса к ЮKassa на создание частичного возврата**

**cURL**

```bash
curl https://api.yookassa.ru/v3/refunds \
  -X POST \
  -u <Идентификатор магазина>:<Секретный ключ> \
  -H 'Idempotence-Key: <Ключ идемпотентности>' \
  -H 'Content-Type: application/json' \
  -d '
        "payment_id": "2d78da66-000f-5000-9000-1297ba86ffa5",
        "description": "Возврат заказа №37",
        "amount": {
          "value": "2000.00",
          "currency": "RUB"
        },
        "refund_method_data": {
            "type": "electronic_certificate",
            "electronic_certificate": {
               "basket_id": "110200010001100000000001",
               "amount": {
                   "value": "1200.00",
                   "currency": "RUB"
                }
            }
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
                'electronic_certificate'=> [
                    'basket_id'=> '110200010001100000000001',
                    'amount'=> [
                        'value'=> '1200.00',
                        'currency'=> 'RUB',
                    ],
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
        "electronic_certificate": {
           "basket_id": "110200010001100000000001",
           "amount": {
               "value": "1200.00",
               "currency": "RUB"
            }
        }
    }
})
```

Если возвращаете только те товары из корзины покупки, которые оплачивались банковской картой (доплата), то возврат [стандартный](https://yookassa.ru/developers/payment-acceptance/after-the-payment/refunds), объект `refund_method_data` передавать не нужно. Сумма возврата (`amount`) должна быть не больше суммы доплаты, иначе возврат не пройдет.

**Пример запроса к ЮKassa на создание частичного возврата (только доплата)**

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
