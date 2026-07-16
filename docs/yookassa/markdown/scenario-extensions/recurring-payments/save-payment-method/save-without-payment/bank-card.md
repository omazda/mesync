<!-- Источник: https://yookassa.ru/developers/payment-acceptance/scenario-extensions/recurring-payments/save-payment-method/save-without-payment/bank-card -->
<!-- Полная копия статьи официальной документации ЮKassa, сохранено 2026-07-02 -->

# Привязка банковской карты на нулевую сумму

Вы можете сохранить банковскую карту для дальнейших автоплатежей с помощью [привязки на нулевую сумму](https://yookassa.ru/developers/payment-acceptance/scenario-extensions/recurring-payments/save-payment-method/save-without-payment/basics).

Для создания привязки нужны данные карты: номер, срок действия и CVC-код. Вы можете получать их двумя способами: [на стороне ЮKassa](https://yookassa.ru/developers/payment-acceptance/scenario-extensions/recurring-payments/save-payment-method/save-without-payment/bank-card#ready-made-payment-form) или [на вашей стороне](https://yookassa.ru/developers/payment-acceptance/scenario-extensions/recurring-payments/save-payment-method/save-without-payment/bank-card#merchant-side) (для этого у вас должен быть сертификат на соответствие требованиям PCI DSS).

Когда пользователь подтвердит привязку, ЮKassa проверит, что эту карту можно использовать для автоплатежей, и привяжет ее к вашему магазину.

Порядок работы

Привязка банковской карты на нулевую сумму проходит следующим образом:

1. Вы создаете привязку c данными банковской карты или без них — зависит от того, как вы их получаете ([самостоятельно](https://yookassa.ru/developers/payment-acceptance/scenario-extensions/recurring-payments/save-payment-method/save-without-payment/bank-card#merchant-side) или [на стороне ЮKassa](https://yookassa.ru/developers/payment-acceptance/scenario-extensions/recurring-payments/save-payment-method/save-without-payment/bank-card#ready-made-payment-form)).
2. ЮKassa возвращает вам идентификатор способа оплаты. Его пока нельзя использовать для автоплатежей, нужно дождаться, когда ЮKassa проверит карту.
3. ЮKassa проводит аутентификацию пользователя по 3-D Secure и проверяет, что с картой всё в порядке, ее можно использовать для последующих автоплатежей.
4. ЮKassa привязывает банковскую карту к вашему магазину.
5. Вы сохраняете идентификатор способа оплаты. Он нужен, чтобы проводить [автоплатежи](https://yookassa.ru/developers/payment-acceptance/scenario-extensions/recurring-payments/pay-with-saved).

Сценарий привязки карты на нулевую сумму

В этом разделе описан общий порядок проведения привязки банковской карты на нулевую сумму с [вводом платежных данных на стороне ЮKassa](https://yookassa.ru/developers/payment-acceptance/scenario-extensions/recurring-payments/save-payment-method/save-without-payment/bank-card#ready-made-payment-form). Если пользователь [вводит платежные данные на вашей стороне](https://yookassa.ru/developers/payment-acceptance/scenario-extensions/recurring-payments/save-payment-method/save-without-payment/bank-card#merchant-side), порядок действий может немного отличаться.

![Сценарий привязки с вводом платежных данных на стороне ЮKassa](https://static.yoomoney.ru/docops-static/images/developers-payments-schema-reccuring-payments-zero-amount-binding.image.ru.18e1ae29.svg)

Сценарий привязки с вводом платежных данных на стороне ЮKassa

1. Пользователь переходит к привязке банковской карты.
2. Вы [создаете объект способа оплаты](https://yookassa.ru/developers/api#create_payment_method) — отправляете ЮKassa POST-запрос.
3. ЮKassa возвращает вам созданный [объект способа оплаты](https://yookassa.ru/developers/api#payment_method_object) в статусе `pending` . В объект включен идентификатор способа оплаты и ссылка на готовую страницу привязки (параметр `confirmation_url`).
4. Вы перенаправляете пользователя на готовую страницу привязки.
5. Пользователь вводит данные банковской карты.
6. ЮKassa запрашивает в платежной системе ссылку для прохождения аутентификации по 3-D Secure.
7. Платежная система возвращает необходимые данные.
8. Пользователь проходит аутентификацию.
9. ЮKassa отправляет карту на проверку в платежную систему.
10. Платежная система возвращает результат проверки.
11. ЮKassa сохраняет способ оплаты — привязывает карту к вашему магазину.
12. ЮKassa перенаправляет пользователя по ссылке, которую вы передали в параметре `return_url` в объекте `confirmation`.
13. Если у вас настроены уведомления, ЮKassa присылает [уведомление о сохранении способа оплаты](https://yookassa.ru/developers/using-api/webhooks) — `payment_method.active`.
14. Вы запрашиваете информацию о способе оплаты — отправляете ЮKassa GET-запрос с идентификатором способа оплаты.
15. Вы сохраняете идентификатор способа оплаты. Этот идентификатор можно использовать для [автоплатежей](https://yookassa.ru/developers/payment-acceptance/scenario-extensions/recurring-payments/pay-with-saved) или [выплат](https://yookassa.ru/developers/payouts/scenario-extensions/multipurpose-token).
16. Вы сообщаете пользователю результат привязки.

Если аутентификация пользователя по 3-D Secure не требуется, то пункты 6-8 пропускаются. Когда пользователь введет данные карты, ЮKassa сразу отправит ее на проверку в платежную систему.

Привязка с вводом платежных данных на стороне ЮKassa

- [Как это работает](https://yookassa.ru/developers/payment-acceptance/scenario-extensions/recurring-payments/save-payment-method/save-without-payment/bank-card#ready-made-payment-form-how-it-works)
- [Как создать привязку](https://yookassa.ru/developers/payment-acceptance/scenario-extensions/recurring-payments/save-payment-method/save-without-payment/bank-card#ready-made-payment-form-create)

Как это работает

В этом сценарии вы создаете привязку и перенаправляете пользователя на страницу привязки ЮKassa, где он вводит платежные данные, а затем подтверждает сохранение способа оплаты.

![Страница привязки карты ЮKassa](https://static.yoomoney.ru/docops-static/images/developers-payments-reccuring-payments-zero-amount-binding-form.image.ru.6f61a641.svg)

Страница привязки карты ЮKassa

Если способ оплаты нельзя сохранить (например, карта заблокирована), форма привязки обрабатывает неуспешные попытки: она отображает пользователю сообщение об ошибке и предлагает попробовать привязать эту или другую карту еще раз. Вы можете отключить эту настройку через менеджера ЮKassa и обрабатывать неуспешные попытки самостоятельно.

Для интеграции добавьте на ваш сайт кнопку, по которой можно перейти к привязке. Когда пользователь перейдет по кнопке, получите от ЮKassa ссылку на готовую страницу привязки, и перенаправьте на неё пользователя. Срок жизни этой ссылки — 1 час. На странице привязки пользователь введет данные карты, а ЮKassa проверит, что с картой все в порядке, и отобразит результат привязки.

Когда пользователь вернется обратно к вам на сайт, запросите у ЮKassa результаты привязки. При необходимости отобразите их пользователю.

Как создать привязку

**Шаг 1.** Предупредите пользователя, что сохраните его платежные данные, и расскажите, как будете их использовать. Например, с какой регулярностью вы будете списывать деньги и как пользователь сможет отказаться от повторных списаний.

**Шаг 2.** [Создайте объект способа оплаты](https://yookassa.ru/developers/api#create_payment_method). Передайте в запросе следующие данные:

- параметр `type` со значением `bank_card`;
- объект `confirmation` с типом `redirect` и адресом страницы на вашей стороне, на которую пользователь вернется после привязки (в параметре `return_url`);
- при необходимости передайте объект `metadata` с любыми дополнительными данными, которые нужны вам для работы (например, ваш внутренний идентификатор заказа).

**Пример запроса**

**cURL**

```bash
curl https://api.yookassa.ru/v3/payment_methods \
    -X POST \
    -u <Идентификатор магазина>:<Секретный ключ> \
    -H 'Idempotence-Key: <Ключ идемпотентности>' \
    -H 'Content-Type: application/json' \
    -d '{
          "confirmation": {
            "type": "redirect",
            "return_url": "https://www.example.com/return_url"
          },
          "type": "bank_card",
          "metadata": {
            "order_id": "37"
          }
        }'
```

В ответ на запрос ЮKassa вернет созданный [объект способа оплаты](https://yookassa.ru/developers/api#payment_method_object).

**Пример созданного объекта способа оплаты**

**JSON**

```json
{
  "type": "bank_card",
  "id": "22e12f66-000f-5000-8000-18db351245c7",
  "saved": false,
  "status": "pending",
  "holder": {
    "account_id": "100500",
    "gateway_id": "100700"
  },
  "confirmation": {
    "type": "redirect",
    "confirmation_url": "https://yoomoney.ru/checkout/payment-methods/v1/contract?paymentMethodId=22e12f66-000f-5000-8000-18db351245c7"
  },
  "metadata": {
    "order_id": "37"
  }
}
```

**Шаг 3.** Перенаправьте пользователя на `confirmation_url`, который придет в [объект способа оплаты](https://yookassa.ru/developers/api#payment_method_object). Это ссылка на страницу ЮKassa, на которой пользователь введет данные карты.

Чтобы сохранить **идентификатор способа оплаты**:

**Шаг 1.** Дождитесь, когда пользователь пройдет аутентификацию, а ЮKassa проверит карту: подождите, когда придет [уведомление от ЮKassa](https://yookassa.ru/developers/using-api/webhooks), или периодически отправляйте запросы, чтобы получить информацию о [информацию о сохраненном способе оплаты](https://yookassa.ru/developers/api#get_payment_method).

**Шаг 2.** Убедитесь, что способ оплаты сохранен: в [объекте способа оплаты](https://yookassa.ru/developers/api#payment_method_object) будут параметры `status=active` и `saved=true` .

Если в процессе привязки возникла ошибка (например, карта заблокирована), то в объекте способа оплаты вернутся параметры `status=inactive` и `saved=false` . Для уточнения причин ошибки обратитесь в техническую поддержку ЮKassa.

**Пример объекта способа оплаты в статусе active**

**JSON**

```json
{
  "type": "bank_card",
  "id": "22e12f66-000f-5000-8000-18db351245c7",
  "saved": true,
  "status": "active",
  "title": "Bank card *4477",
  "holder": {
    "account_id": "100500",
    "gateway_id": "100700"
  },
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
  "metadata": {
    "order_id": "37"
  }
}
```

**Шаг 3.** Сохраните идентификатор способа оплаты `payment_methods.id`. Рекомендуется сохранять его в связке с идентификатором пользователя в вашей системе. Это нужно, чтобы в дальнейшем вы могли соотнести пользователя и его платежные данные.

**Шаг 4.** Сообщите пользователю результаты сохранения способа оплаты.

Готово!

Вы сохранили способ оплаты и теперь можете проводить [автоплатежи](https://yookassa.ru/developers/payment-acceptance/scenario-extensions/recurring-payments/pay-with-saved). Также идентификатор способа оплаты можно использовать для проведения [выплат](https://yookassa.ru/developers/payouts/scenario-extensions/multipurpose-token) (только для банковских карт).

Привязка с вводом платежных данных на вашей стороне

Чтобы использовать эту возможность, вам нужно получить сертификат на соответствие требованиям [PCI DSS](https://ru.wikipedia.org/wiki/PCI_DSS).

- [Как это работает](https://yookassa.ru/developers/payment-acceptance/scenario-extensions/recurring-payments/save-payment-method/save-without-payment/bank-card#merchant-side-how-it-works)
- [Как создать привязку](https://yookassa.ru/developers/payment-acceptance/scenario-extensions/recurring-payments/save-payment-method/save-without-payment/bank-card#merchant-side-how-to-create)

Как это работает

В этом сценарии вы проводите весь процесс на своей стороне: самостоятельно получаете данные банковской карты пользователя, передаете их в ЮKassa, дожидаетесь создания привязки, обрабатываете неуспешные попытки и сообщаете пользователю результат привязки.

Для интеграции добавьте на свою страницу возможность перейти к привязке карты, а также форму для получения данных банковской карты. Далее всё зависит от того, используете ли вы аутентификацию по 3-D Secure:

- Если используете 3-D Secure, то получите от ЮKassa ссылку на страницу аутентификации и перенаправьте по ней пользователя, а затем запросите у ЮKassa результаты привязки и сообщите их пользователю.
- Если не используете 3-D Secure, то запросите результаты привязки и сообщите их пользователю.

Как создать привязку

**Шаг 1.** Предупредите пользователя, что сохраните его платежные данные, и расскажите, как будете их использовать. Например, с какой регулярностью вы будете списывать деньги и как пользователь сможет отказаться от повторных списаний.

**Шаг 2.** Получите данные банковской карты пользователя на своей стороне.

**Шаг 3.** [Создайте объект способа оплаты](https://yookassa.ru/developers/api#create_payment_method). Передайте в запросе следующие данные:

- параметр `type` со значением `bank_card`;
- объект `confirmation` с типом `redirect` и адресом страницы на вашей стороне, на которую пользователь вернется после аутентификации по 3-D Secure (в параметре `return_url`);
- объект `card` с данными банковской карты;
- при необходимости передайте объект `metadata` с любыми дополнительными данными, которые нужны вам для работы (например, ваш внутренний идентификатор заказа).

**Пример запроса**

**cURL**

```bash
curl https://api.yookassa.ru/v3/payment_methods \
  -X POST \
  -u <Идентификатор магазина>:<Секретный ключ> \
  -H 'Idempotence-Key: <Ключ идемпотентности>' \
  -H 'Content-Type: application/json' \
  -d '{
        "confirmation": {
          "type": "redirect",
          "return_url": "https://www.example.com/return_url"
        },
        "type": "bank_card",
        "card": {
          "cardholder": "MR CARDHOLDER",
          "csc": "213",
          "expiry_year": "2030",
          "expiry_month": "01",
          "number": "5555555555554477"
        },
        "metadata": {
          "order_id": "37"
        }
      }'
```

В ответ на запрос ЮKassa вернет созданный [объект способа оплаты](https://yookassa.ru/developers/api#payment_method_object).

**Пример созданного объекта способа оплаты**

**JSON**

```json
{
  "type": "bank_card",
  "id": "22e12f66-000f-5000-8000-18db351245c7",
  "saved": false,
  "status": "pending",
  "title": "Bank card *4477",
  "holder": {
    "account_id": "100500",
    "gateway_id": "100700"
  },
  "confirmation": {
    "type": "redirect",
    "confirmation_url": "<URL для аутентификации по 3-D Secure>"
  },
  "metadata": {
    "order_id": "37"
  }
}
```

**Шаг 4.** Перенаправьте пользователя на страницу аутентификации по 3-D Secure (ссылка на нее придет в параметре `confirmation_url`). Если вы отключили аутентификацию по 3-D Secure через менеджера ЮKassa, пропустите этот шаг.

Чтобы сохранить **идентификатор способа оплаты**:

**Шаг 1.** Дождитесь, когда пользователь пройдет аутентификацию (при необходимости), а ЮKassa проверит карту: подождите, когда придет [уведомление от ЮKassa](https://yookassa.ru/developers/using-api/webhooks), или периодически отправляйте запросы, чтобы получить информацию о [информацию о сохраненном способе оплаты](https://yookassa.ru/developers/api#get_payment_method).

**Шаг 2.** Убедитесь, что способ оплаты сохранен: в [объекте способа оплаты](https://yookassa.ru/developers/api#payment_method_object) будут параметры `status=active` и `saved=true`.

Если в процессе привязки возникла ошибка (например, карта заблокирована), то в объекте способа оплаты вернутся параметры `status=inactive` и `saved=false`. Для уточнения причин ошибки обратитесь в техническую поддержку ЮKassa.

**Пример объекта способа оплаты в статусе active**

**JSON**

```json
{
  "type": "bank_card",
  "id": "22e12f66-000f-5000-8000-18db351245c7",
  "saved": true,
  "status": "active",
  "title": "Bank card *4477",
  "holder": {
    "account_id": "100500",
    "gateway_id": "100700"
  },
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
  "metadata": {
    "order_id": "37"
  }
}
```

**Шаг 3.** Сохраните идентификатор способа оплаты `payment_methods.id`. Рекомендуется сохранять его в связке с идентификатором пользователя в вашей системе. Это нужно, чтобы в дальнейшем вы могли соотнести пользователя и его платежные данные.

**Шаг 4.** Сообщите пользователю результаты сохранения способа оплаты.

Готово!

Вы сохранили способ оплаты и теперь можете проводить [автоплатежи](https://yookassa.ru/developers/payment-acceptance/scenario-extensions/recurring-payments/pay-with-saved). Также идентификатор способа оплаты можно использовать для проведения выплат (только для банковских карт).

Проведение автоплатежа

Проведение платежа сохраненным способом оплаты нужно реализовать самостоятельно. Для этого отправьте запрос на создание автоплатежа и передайте в нём параметр `payment_method_id` с идентификатором способа оплаты. [Подробнее о проведении автоплатежа](https://yookassa.ru/developers/payment-acceptance/scenario-extensions/recurring-payments/pay-with-saved)

Что почитать еще

[Привязка счета СБП на нулевую сумму](https://yookassa.ru/developers/payment-acceptance/scenario-extensions/recurring-payments/save-payment-method/save-without-payment/sbp)

[Привязка на нулевую сумму](https://yookassa.ru/developers/payment-acceptance/scenario-extensions/recurring-payments/save-payment-method/save-without-payment/basics)

[Привязка во время платежа](https://yookassa.ru/developers/payment-acceptance/scenario-extensions/recurring-payments/save-payment-method/save-during-payment)

[Платеж без сохранения способа оплаты](https://yookassa.ru/developers/payment-acceptance/scenario-extensions/recurring-payments/pay-without-saving)
