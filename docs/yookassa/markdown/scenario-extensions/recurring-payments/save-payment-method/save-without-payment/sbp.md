<!-- Источник: https://yookassa.ru/developers/payment-acceptance/scenario-extensions/recurring-payments/save-payment-method/save-without-payment/sbp -->
<!-- Полная копия статьи официальной документации ЮKassa, сохранено 2026-07-02 -->

# Привязка счета СБП на нулевую сумму

Вы можете сохранить счет СБП для дальнейших автоплатежей с помощью [привязки на нулевую сумму](https://yookassa.ru/developers/payment-acceptance/scenario-extensions/recurring-payments/save-payment-method/save-without-payment/basics).

Для этого вы создаете привязку и, чтобы подтвердить сохранение способа оплаты, перенаправляете пользователя в приложение участника СБП (банка или платежного сервиса, подключенного к СБП). Это можно сделать двумя способами:

- [На странице ЮKassa](https://yookassa.ru/developers/payment-acceptance/scenario-extensions/recurring-payments/save-payment-method/save-without-payment/sbp#ready-made-payment-form) — вы перенаправляете пользователя на готовую страницу ЮKassa, где он сканирует QR-код или выбирает банк или платежный сервис из списка.
- [На вашей стороне](https://yookassa.ru/developers/payment-acceptance/scenario-extensions/recurring-payments/save-payment-method/save-without-payment/sbp#merchant-side) — вы получаете платежную ссылку СБП, генерируете QR-код (для компьютера) или перенаправляете по ссылке (для мобильного устройства).

Когда пользователь подтвердит привязку, ЮKassa проверит, что этот счет СБП можно использовать для автоплатежей, и привяжет его к вашему магазину.

Порядок работы

Привязка счета СБП на нулевую сумму проходит следующим образом:

1. Вы создаете привязку.
2. ЮKassa возвращает вам идентификатор способа оплаты. Его пока нельзя использовать для автоплатежей, нужно дождаться, когда ЮKassa проверит счет.
3. Пользователь для перехода в приложение участника СБП либо сканирует QR-код, либо выбирает свой банк или платежный сервис [на стороне ЮKassa](https://yookassa.ru/developers/payment-acceptance/scenario-extensions/recurring-payments/save-payment-method/save-without-payment/sbp#ready-made-payment-form) или [на вашей стороне](https://yookassa.ru/developers/payment-acceptance/scenario-extensions/recurring-payments/save-payment-method/save-without-payment/sbp#merchant-side).
4. Пользователь переходит в приложение участника СБП и подтверждает привязку.
5. ЮKassa проверяет, что с счетом всё в порядке, его можно использовать для последующих автоплатежей.
6. ЮKassa привязывает счет СБП к вашему магазину.
7. Вы сохраняете идентификатор способа оплаты. Он нужен, чтобы проводить [автоплатежи](https://yookassa.ru/developers/payment-acceptance/scenario-extensions/recurring-payments/pay-with-saved).

Cценарий привязки на нулевую сумму

В этом разделе описан общий порядок проведения привязки на нулевую сумму [на странице ЮKassa](https://yookassa.ru/developers/payment-acceptance/scenario-extensions/recurring-payments/save-payment-method/save-without-payment/sbp#ready-made-payment-form), где пользователь сканирует QR-код в приложении участника СБП. Если пользователь переходит к привязке [на вашей стороне](https://yookassa.ru/developers/payment-acceptance/scenario-extensions/recurring-payments/save-payment-method/save-without-payment/sbp#merchant-side) или сканирует QR-код через другое приложение, порядок действий может немного отличаться.

![Сценарий привязки с отображением QR-кода СБП на странице ЮKassa](https://static.yoomoney.ru/docops-static/images/developers-payments-schema-reccuring-payments-zero-amount-binding-sbp.image.ru.6b2daf8e.svg)

Сценарий привязки с отображением QR-кода СБП на странице ЮKassa

1. Пользователь переходит к привязке счета СБП.
2. Вы [создаете объект способа оплаты](https://yookassa.ru/developers/api#create_payment_method) — отправляете ЮKassa POST-запрос.
3. ЮKassa возвращает вам созданный [объект способа оплаты](https://yookassa.ru/developers/api#payment_method_object) в статусе `pending` . В объект включен идентификатор способа оплаты и ссылка на готовую страницу привязки (параметр `confirmation_url`).
4. Вы перенаправляете пользователя на готовую страницу привязки.
5. Пользователь сканирует QR-код и переходит в приложение участника СБП.
6. Пользователь подтверждает привязку в приложении участника СБП.
7. НСПК (Национальная система платежных карт — оператор СБП) проверяет ограничения на привязку счета СБП.
8. НСПК возвращает ЮKassa результат проверки.
9. ЮKassa сохраняет способ оплаты — привязывает счет СБП к вашему магазину.
10. ЮKassa перенаправляет пользователя по ссылке, которую вы передали в параметре `return_url` в объекте `confirmation`.
11. Если у вас настроены уведомления, ЮKassa присылает [уведомление о сохранении способа оплаты](https://yookassa.ru/developers/using-api/webhooks) — `payment_method.active`.
12. Вы запрашиваете информацию о способе оплаты — отправляете ЮKassa GET-запрос с идентификатором способа оплаты.
13. Вы сохраняете идентификатор способа оплаты. Этот идентификатор можно использовать для [автоплатежей](https://yookassa.ru/developers/payment-acceptance/scenario-extensions/recurring-payments/pay-with-saved).
14. Вы сообщаете пользователю результат привязки.

Привязка счета СБП на странице ЮKassa

- [Как это работает](https://yookassa.ru/developers/payment-acceptance/scenario-extensions/recurring-payments/save-payment-method/save-without-payment/sbp#ready-made-payment-form-how-it-works)
- [Как создать привязку](https://yookassa.ru/developers/payment-acceptance/scenario-extensions/recurring-payments/save-payment-method/save-without-payment/sbp#ready-made-payment-form-create)

Как это работает

В этом сценарии вы создаете привязку и перенаправляете пользователя на страницу ЮKassa, где он сканирует QR-код или выбирает свой банк или платежный сервис.

![Пример формы привязки счета СБП на компьютере](https://static.yoomoney.ru/docops-static/images/developers-payments-reccuring-payments-zero-amount-binding-form-sbp-desktop.image.ru.af51b62e.svg)

Пример формы привязки счета СБП на компьютере

Если способ оплаты нельзя сохранить (например, счет заблокирован), форма привязки обрабатывает неуспешные попытки: она отображает пользователю сообщение об ошибке и предлагает попробовать привязать счет СБП еще раз. Вы можете отключить эту настройку через менеджера ЮKassa и обрабатывать неуспешные попытки самостоятельно.

Для интеграции добавьте на ваш сайт кнопку, по которой можно перейти к привязке. Когда пользователь перейдет по кнопке, получите от ЮKassa ссылку на готовую страницу привязки и перенаправьте на неё пользователя. Срок жизни этой ссылки — 1 час.

На странице привязки пользователь в зависимости от своего устройства либо отсканирует QR-код, либо выберет свой банк или платежный сервис, а затем перейдет в приложение участника СБП для подтверждения привязки. ЮKassa проверит, что с счетом СБП всё в порядке, привяжет платежное средство к вашему магазину и отобразит результат привязки.

Когда пользователь вернется обратно к вам на сайт, запросите у ЮKassa результаты привязки. При необходимости отобразите их пользователю.

Как создать привязку

**Шаг 1.** Предупредите пользователя, что сохраните его платежные данные, и расскажите, как будете их использовать. Например, с какой регулярностью вы будете списывать деньги и как пользователь сможет отказаться от повторных списаний.

**Шаг 2.** [Создайте объект способа оплаты](https://yookassa.ru/developers/api#create_payment_method). Передайте в запросе следующие данные:

- параметр `type` со значением `sbp`;
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
          "type": "sbp",
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
  "type": "sbp",
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

**Шаг 3.** Перенаправьте пользователя на `confirmation_url`, который придет в [объекте способа оплаты](https://yookassa.ru/developers/api#payment_method_object). Это ссылка на страницу ЮKassa, на которой пользователь отсканирует QR-код или выберет банк или платежный сервис.

Если пользователь сканирует QR-код, он может сделать это двумя способами:

- в приложении банка или платежного сервиса — тогда пользователь сразу перейдет к подтверждению привязки счета СБП;
- в другом приложении для сканирования QR-кодов — тогда пользователь перейдет на страницу НСПК для выбора банка или платежного сервиса, счет в котором он хочет привязать к вашему магазину.

Чтобы сохранить **идентификатор способа оплаты**:

**Шаг 1.** Дождитесь, когда пользователь подтвердит привязку, а ЮKassa проверит счет СБП: подождите, когда придет [уведомление от ЮKassa](https://yookassa.ru/developers/using-api/webhooks), или периодически отправляйте запросы, чтобы получить [информацию о сохраненном способе оплаты](https://yookassa.ru/developers/api#get_payment_method).

**Шаг 2.** Убедитесь, что способ оплаты сохранен: в [объекте способа оплаты](https://yookassa.ru/developers/api#payment_method_object) будут параметры `status=active` и `saved=true` .

Если в процессе привязки возникла ошибка (например, счет заблокирован), то в объекте способа оплаты вернутся параметры `status=inactive` и `saved=false` . Для уточнения причин ошибки обратитесь в техническую поддержку ЮKassa.

**Пример объекта способа оплаты в статусе active**

**JSON**

```json
{
  "type": "sbp",
  "id": "22e12f66-000f-5000-8000-18db351245c7",
  "saved": true,
  "status": "active",
  "holder": {
    "account_id": "100500",
    "gateway_id": "100700"
  },
  "payer_bank_details": {
    "bank_id": " 100000000022"
  },
  "metadata": {
    "order_id": "37"
  }
}
```

**Шаг 3.** Сохраните идентификатор способа оплаты `payment_methods.id`. Рекомендуется сохранять его в связке с идентификатором пользователя в вашей системе. Это нужно, чтобы в дальнейшем вы могли соотнести пользователя и его платежные данные.

**Шаг 4.** Сообщите пользователю результаты сохранения способа оплаты.

Готово!

Вы сохранили способ оплаты и теперь можете проводить [автоплатежи](https://yookassa.ru/developers/payment-acceptance/scenario-extensions/recurring-payments/pay-with-saved).

Привязка счета СБП на вашей стороне

- [Как это работает](https://yookassa.ru/developers/payment-acceptance/scenario-extensions/recurring-payments/save-payment-method/save-without-payment/sbp#merchant-side-how-it-works)
- [Как создать привязку](https://yookassa.ru/developers/payment-acceptance/scenario-extensions/recurring-payments/save-payment-method/save-without-payment/sbp#merchant-side-how-to-create)

Как это работает

В этом сценарии вы создаете привязку и получаете от ЮKassa платежную ссылку СБП. Затем, в зависимости от устройства пользователя, вы либо самостоятельно генерируете и отображаете QR-код, либо перенаправляете пользователя по платежной ссылке СБП для выбора банка или платежного сервиса из списка.

Если способ оплаты нельзя сохранить (например, счет заблокирован), вы самостоятельно обрабатываете неуспешные попытки и сообщаете пользователю результат привязки.

Для интеграции добавьте на ваш сайт кнопку, по которой можно перейти к привязке. Когда пользователь перейдет по кнопке, получите от ЮKassa платежную ссылку СБП:

- В полной версии сайта сгенерируйте QR-код с помощью любого доступного инструмента и отобразите его пользователю.
- В мобильной версии сайта или в мобильном приложении перенаправьте пользователя по этой ссылке.

Срок жизни платежной ссылки СБП — 1 час.

Когда пользователь подтвердит привязку в приложении участника СБП, ЮKassa проверит, что с счетом СБП всё в порядке, и привяжет платежное средство к вашему магазину. После возвращения пользователя обратно к вам на сайт запросите у ЮKassa результаты привязки. При необходимости отобразите их пользователю.

Как создать привязку

**Шаг 1.** Предупредите пользователя, что сохраните его платежные данные, и расскажите, как будете их использовать. Например, с какой регулярностью вы будете списывать деньги и как пользователь сможет отказаться от повторных списаний.

**Шаг 2.** [Создайте объект способа оплаты](https://yookassa.ru/developers/api#create_payment_method). Передайте в запросе следующие данные:

- параметр `type` со значением `sbp`;
- объект `confirmation` с типом `qr` и адресом страницы на вашей стороне, на которую пользователь вернется после подтверждения привязки в приложении участника СБП (в параметре `return_url`);
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
          "type": "qr",
          "return_url": "https://www.example.com/return_url"
        },
        "type": "sbp",
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
  "type": "sbp",
  "id": "22e12f66-000f-5000-8000-18db351245c7",
  "saved": false,
  "status": "pending",
  "holder": {
    "account_id": "100500",
    "gateway_id": "100700"
  },
  "confirmation": {
    "type": "qr",
    "confirmation_data": "https://qr.nspk.ru/QR_ID"
  },
  "metadata": {
    "order_id": "37"
  }
}
```

**Шаг 3.** В параметре `confirmation_data` ЮKassa вернет URL — это платежная ссылка СБП. В полной версии сайта сгенерируйте QR-код с помощью любого доступного инструмента и отобразите его пользователю. В мобильной версии сайта или в мобильном приложении перенаправьте пользователя по этому URL.

Если пользователь сканирует QR-код, он может сделать это двумя способами:

- в приложении банка или платежного сервиса — тогда пользователь сразу перейдет к подтверждению привязки счета СБП;
- в другом приложении для сканирования QR-кодов — тогда пользователь перейдет на страницу НСПК для выбора банка или платежного сервиса, счет в котором он хочет привязать к вашему магазину.

Чтобы сохранить **идентификатор способа оплаты**:

**Шаг 1.** Дождитесь, когда пользователь подтвердит привязку, а ЮKassa проверит счет СБП: подождите, когда придет [уведомление от ЮKassa](https://yookassa.ru/developers/using-api/webhooks), или периодически отправляйте запросы, чтобы получить [информацию о сохраненном способе оплаты](https://yookassa.ru/developers/api#get_payment_method).

**Шаг 2.** Убедитесь, что способ оплаты сохранен: в [объекте способа оплаты](https://yookassa.ru/developers/api#payment_method_object) будут параметры `status=active` и `saved=true`.

Если в процессе привязки возникла ошибка (например, счет заблокирован), то в объекте способа оплаты вернутся параметры `status=inactive` и `saved=false`. Для уточнения причин ошибки обратитесь в техническую поддержку ЮKassa.

**Пример объекта способа оплаты в статусе active**

**JSON**

```json
{
  "type": "sbp",
  "id": "22e12f66-000f-5000-8000-18db351245c7",
  "saved": true,
  "status": "active",
  "holder": {
    "account_id": "100500",
    "gateway_id": "100700"
  },
  "payer_bank_details": {
    "bank_id": " 100000000022"
  },
  "metadata": {
    "order_id": "37"
  }
}
```

**Шаг 3.** Сохраните идентификатор способа оплаты `payment_methods.id`. Рекомендуется сохранять его в связке с идентификатором пользователя в вашей системе. Это нужно, чтобы в дальнейшем вы могли соотнести пользователя и его платежные данные.

**Шаг 4.** Сообщите пользователю результаты сохранения способа оплаты.

Готово!

Вы сохранили способ оплаты и теперь можете проводить [автоплатежи](https://yookassa.ru/developers/payment-acceptance/scenario-extensions/recurring-payments/pay-with-saved).

Проведение автоплатежа

Проведение платежа сохраненным способом оплаты нужно реализовать самостоятельно. Для этого отправьте запрос на создание автоплатежа и передайте в нём параметр `payment_method_id` с идентификатором способа оплаты. [Подробнее о проведении автоплатежа](https://yookassa.ru/developers/payment-acceptance/scenario-extensions/recurring-payments/pay-with-saved)

Что почитать еще

[Привязка банковской карты на нулевую сумму](https://yookassa.ru/developers/payment-acceptance/scenario-extensions/recurring-payments/save-payment-method/save-without-payment/bank-card)

[Привязка на нулевую сумму](https://yookassa.ru/developers/payment-acceptance/scenario-extensions/recurring-payments/save-payment-method/save-without-payment/basics)

[Привязка во время платежа](https://yookassa.ru/developers/payment-acceptance/scenario-extensions/recurring-payments/save-payment-method/save-during-payment)

[Платеж без сохранения способа оплаты](https://yookassa.ru/developers/payment-acceptance/scenario-extensions/recurring-payments/pay-without-saving)
