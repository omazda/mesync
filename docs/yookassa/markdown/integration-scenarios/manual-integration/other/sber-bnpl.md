<!-- Источник: https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/other/sber-bnpl -->
<!-- Полная копия статьи официальной документации ЮKassa, сохранено 2026-07-02 -->

# Плати частями

Этот способ оплаты доступен, только если:

- Вы принимаете платежи на сайте.
- Вы используете [обычные платежи](https://yookassa.ru/developers/payment-acceptance/overview) или [партнерскую программу](https://yookassa.ru/developers/solutions-for-platforms/partners-api/basics).
- Вы компания или ИП.

Особенности

- Тип способа оплаты в API: `sber_bnpl`
- [Сценарий подтверждения](https://yookassa.ru/developers/payment-acceptance/getting-started/payment-process#user-confirmation): Redirect
- [Срок оплаты](https://yookassa.ru/developers/payment-acceptance/getting-started/payment-methods#payment-term): 1 час
- [Холдирование](https://yookassa.ru/developers/payment-acceptance/getting-started/payment-process#capture-and-cancel): 7 дней, доступно полное и частичное списание оплаты
- [Код в реестре](https://yookassa.ru/developers/payment-acceptance/after-the-payment/reports): реестры [отправляет партнер](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/other/sber-bnpl#registry)
- [Возврат](https://yookassa.ru/developers/payment-acceptance/after-the-payment/refunds): да, полный и частичный
- Срок возврата: от 1 до 10 рабочих дней
- [Автоплатежи](https://yookassa.ru/developers/payment-acceptance/scenario-extensions/recurring-payments/basics): нет
- [Лимиты](https://yookassa.ru/developers/payment-acceptance/getting-started/payment-methods#payment-limit): минимальный размер платежа — 1 000 рублей, максимальный — 50 000 рублей

Сценарии интеграции

Готовые решения: [Умный платеж](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/smart-payment)

Самостоятельная интеграция:

- [Оплата на готовой странице ЮKassa](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/other/sber-bnpl#ready-made-form)
- [Оплата с вводом номера на вашей стороне](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/other/sber-bnpl#merchant-form)

О способе оплаты

- [Как это работает](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/other/sber-bnpl#payment-method-overview-how-it-works)
- [Какие сроки оплаты доступны](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/other/sber-bnpl#payment-method-overview-term)
- [Как проходит платеж](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/other/sber-bnpl#payment-method-overview-payment-process)
- [Кто может использовать сервис «Плати частями»](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/other/sber-bnpl#payment-method-overview-requirements)
- [Как выглядит сценарий проведения платежа](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/other/sber-bnpl#payment-method-overview-scenarios)
- [Как подключить способ оплаты](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/other/sber-bnpl#payment-method-overview-activation)

Как это работает

Плати частями — это способ оплаты, который работает по принципу BNPL — Buy Now, Pay Later. С помощью него пользователь может разделить сумму платежа на несколько равных частей и оплачивать их постепенно в течение [определенного срока](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/other/sber-bnpl#payment-method-overview-term).

Операции через сервис «[Плати частями](https://platichastyami.ru/)» проводит партнер — ООО «Центр Новых Финансовых Сервисов» (ЦНФС). ЮKassa выступает в роли посредника: платежи и возвраты оформляются через ЮKassa, но обрабатываются партнером. Все расчеты как с продавцом, так и с покупателем осуществляет партнер, который затем информирует ЮKassa о результатах операций.

Какие сроки оплаты доступны

Доступен только один срок оплаты — 2 месяца. Оплата вносится раз в две недели. График и сумму платежей пользователь увидит при оплате, а затем сможет проверить [на сайте](https://platichastyami.ru/) или в приложении сервиса.

Как проходит платеж

Чтобы начать работать с сервисом «Плати частями», пользователю нужно указать номер телефона для авторизации, ФИО и дату рождения для проверки, а также платежные данные. ФИО и дата рождения нужны, только если пользователь не авторизован через SberID и впервые платит через сервис «Плати частями».

В процессе платежа пользователь указывает необходимые данные, а затем подтверждает платеж кодом из смс. Подтвердить нужно только первый платеж — оплату первой части суммы. Остальные платежи списываются автоматически по установленному графику платежей.

Вы получаете полную сумму платежа за вычетом комиссии на свой расчетный счет. Партнер перечисляет вам деньги на следующий рабочий день после списания первой части суммы.

Кто может использовать сервис «Плати частями»

Оплатить покупку частями могут пользователи с гражданством РФ от 18 до 70 лет. Для оплаты нужна дебетовая или кредитная карта любого российского банка.

Как выглядит сценарий проведения платежа

В этом разделе описан общий порядок проведения платежа для сценария [Умный платеж](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/smart-payment) или [Оплата на готовой странице ЮKassa](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/other/sber-bnpl#ready-made-form). В выбранном вами сценарии интеграции порядок действий может немного меняться.

![Схема проведения платежа](https://static.yoomoney.ru/docops-static/images/developers-payments-schema-sber-bnpl-payment.image.ru.05aebb00.svg)

Схема проведения платежа

Как проходит платеж:

1. Пользователь переходит к оплате (например, для Умного платежа нажимает кнопку **Заплатить**).
2. Вы создаете платеж — отправляете ЮKassa POST-запрос с учетом выбранного вами сценария интеграции.
3. ЮKassa возвращает вам созданный объект платежа в статусе `pending` и со ссылкой на платежную форму (параметр `confirmation_url` в объекте платежа).
4. Вы перенаправляете пользователя на страницу оплаты.
5. Пользователь вводит свой номер телефона на странице оплаты.
6. ЮKassa перенаправляет пользователя на страницу партнера.
7. Пользователь на странице партнера вводит данные, запрашиваемые партнером, указывает данные банковской карты и подтверждает платеж.
8. Партнер списывает первую часть суммы и сохраняет карту для списания остатка суммы.
9. Партнер сообщает ЮKassa о результате платежа.
10. Если у вас настроены уведомления, ЮKassa присылает уведомление о переходе платежа в статус `succeeded` (для платежей в одну стадию) или в статус `waiting_for_capture` (для платежей в две стадии).
11. Вы запрашиваете информацию о платеже — отправляете ЮKassa GET-запрос с идентификатором платежа.
12. ЮKassa возвращает вам созданный объект платежа в актуальном статусе.
13. Вы сообщаете пользователю результат проведения платежа.

Если вы проводите платежи в [две стадии](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/other/sber-bnpl#capture-and-cancel), то после получения оплаты от пользователя вам необходимо списать деньги или отменить платеж.

Как подключить способ оплаты

Проверьте, что вы можете подключить этот способ оплаты:

- Вы принимаете платежи на сайте.
- Вы используете [обычные платежи](https://yookassa.ru/developers/payment-acceptance/overview) или [партнерскую программу](https://yookassa.ru/developers/solutions-for-platforms/partners-api/basics).
- Вы компания или ИП.

Чтобы подключить этот способ оплаты:

1. Сообщите менеджеру ЮKassa, что хотите принимать платежи через сервис «Плати частями».
2. Проинтегрируйтесь с ЮKassa по инструкциям:
   - Проведение платежа: [Умный платеж](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/smart-payment), [Оплата на готовой странице ЮKassa](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/other/sber-bnpl#ready-made-form) или [Оплата с вводом номера на вашей стороне](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/other/sber-bnpl#merchant-form)
   - [Платежи в две стадии](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/other/sber-bnpl#capture-and-cancel) (при необходимости)
   - [Возвраты платежей](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/other/sber-bnpl#refunds)
   - [Отправка чеков в налоговую](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/other/sber-bnpl#receipts)
3. Протестируйте интеграцию — проведите платеж на минимальную сумму, затем сделайте возврат.

Готово! Можно принимать платежи от реальных пользователей.

Оплата на готовой странице ЮKassa

Как это работает

В этом сценарии вы самостоятельно реализуете выбор способа оплаты. После создания платежа вы перенаправляете пользователя на страницу ЮKassa. На этой странице пользователь вводит свой номер телефона. Он нужен для авторизации в сервисе «Плати частями».

![Пример формы для ввода номера телефона](https://static.yoomoney.ru/docops-static/images/developers-payments-sber-bnpl-payment-form-manual.35170b20.svg)

Пример формы для ввода номера телефона

После ввода телефона пользователь переходит на страницу партнера. На этой странице пользователь вводит необходимые данные, которые запрашивает партнер. После этого пользователь вводит платежные данные и подтверждает платеж, а партнер списывает первую часть суммы. Остальные платежи списываются автоматически по установленному графику платежей.

Когда пользователь вернется обратно к вам на сайт, вы запрашиваете у ЮKassa результаты платежа.

Как провести платеж

**Шаг 1.** [Создайте платеж](https://yookassa.ru/developers/api#create_payment): отправьте ЮKassa запрос с данными для [аутентификации запроса](https://yookassa.ru/developers/using-api/interaction-format#auth), [ключом идемпотентности](https://yookassa.ru/developers/using-api/interaction-format#idempotence) и данными для платежа:

- в объекте `amount` передайте сумму платежа;
- в параметре `description` передайте описание платежа, которое пользователь увидит при оплате;
- в объекте `payment_method_data` передайте код способа оплаты `sber_bnpl`;
- в объекте `confirmation` в параметре `type` передайте тип `redirect`, а в параметре `return_url` — ссылку, по которой пользователь вернется к вам в магазин после оплаты.

В запросе можно передать дополнительные параметры, кроме `payment_token`, `payment_method_id`, `airline`, `transfers`, `deal`.

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
          "value": "1000.00",
          "currency": "RUB"
        },
        "payment_method_data": {
          "type": "sber_bnpl"
        },
        "confirmation": {
          "type": "redirect",
          "return_url": "https://www.example.com/return_url"
        },
        "capture": true,
        "description": "Заказ №72"
      }'
```

В ответ на запрос вернется [объект платежа](https://yookassa.ru/developers/api#payment_object) в актуальном статусе.

**Шаг 2.** Перенаправьте пользователя на страницу ЮKassa, адрес которой придет в `confirmation_url`. На этой странице пользователь введет свой номер телефона, а затем перейдет в сервис «Плати частями» для завершения оплаты.

**Пример тела ответа**

**JSON**

```json
{
  "id": "22e12f66-000f-5000-8000-18db351245c7",
  "status": "pending",
  "paid": false,
  "amount": {
    "value": "1000.00",
    "currency": "RUB"
  },
  "confirmation": {
    "type": "redirect",
    "return_url": "https://www.example.com/return_url",
    "confirmation_url": "https://yoomoney.ru/checkout/payments/v2/contract?orderId=22e12f66-000f-5000-8000-18db351245c7"
  },
  "created_at": "2021-04-12T13:59:33.681Z",
  "description": "Заказ №72",
  "metadata": {},
  "payment_method": {
    "type": "sber_bnpl",
    "id": "22e12f66-000f-5000-8000-18db351245c7",
    "saved": false,
    "status": "inactive"
  },
  "recipient": {
    "account_id": "100500",
    "gateway_id": "100700"
  },
  "refundable": false,
  "test": false
}
```

**Шаг 3.** Дождитесь успешного завершения платежа: подождите, когда придет когда придет [уведомление от ЮKassa](https://yookassa.ru/developers/using-api/webhooks), или периодически отправляйте запросы, чтобы получить [информацию о платеже](https://yookassa.ru/developers/api#get_payment).

**Пример платежа в статусе succeeded**

**JSON**

```json
{
  "id": "22e12f66-000f-5000-8000-18db351245c7",
  "status": "succeeded",
  "paid": true,
  "amount": {
    "value": "1000.00",
    "currency": "RUB"
  },
  "captured_at": "2021-04-13T09:27:09.960Z",
  "created_at": "2021-04-13T09:25:13.087Z",
  "description": "Заказ №72",
  "income_amount": {
    "value": "1000.00",
    "currency": "RUB"
  },
  "payment_method": {
    "type": "sber_bnpl",
    "id": "22e12f66-000f-5000-8000-18db351245c7",
    "saved": false,
    "status": "inactive"
  },
  "recipient": {
    "account_id": "100500",
    "gateway_id": "100700"
  },
  "refundable": true,
  "refunded_amount": {
    "value": "0.00",
    "currency": "RUB"
  },
  "test": false
}
```

**Шаг 4.** Сообщите пользователю результат оплаты.

Готово! Если вы проводите платеж в две стадии, [подтвердите](https://yookassa.ru/developers/payment-acceptance/getting-started/payment-process#capture) или [отмените платеж](https://yookassa.ru/developers/payment-acceptance/getting-started/payment-process#cancel). Сообщите пользователю финальный результат платежа.

Оплата с вводом номера на вашей стороне

Как это работает

В этом сценарии вы самостоятельно реализуете выбор способа оплаты. Чтобы создать платеж, вы на своей стороне получаете номер телефона пользователя и передаете его в ЮKassa. Номер нужен для авторизации в сервисе «Плати частями».

После создания платежа вы перенаправляете пользователя в сервис «Плати частями» через промежуточную страницу ЮKassa. На промежуточной странице пользователь не выполняет никаких действий — это техническая страница, на которую пользователь попадает на доли секунды. Затем ЮKassa автоматически перенаправляет его на страницу партнера. На этой странице пользователь вводит необходимые данные, которые запрашивает партнер. После этого пользователь вводит платежные данные и подтверждает платеж, а партнер списывает первую часть суммы. Остальные платежи списываются автоматически по установленному графику платежей.

Когда пользователь вернется обратно к вам на сайт, вы запрашиваете у ЮKassa результаты платежа.

Как провести платеж

**Шаг 1.** Получите номер телефона пользователя на своей стороне.

**Шаг 2.** [Создайте платеж](https://yookassa.ru/developers/api#create_payment): отправьте ЮKassa запрос с данными для [аутентификации запроса](https://yookassa.ru/developers/using-api/interaction-format#auth), [ключом идемпотентности](https://yookassa.ru/developers/using-api/interaction-format#idempotence) и данными для платежа:

- в объекте `amount` передайте сумму платежа;
- в параметре `description` передайте описание платежа, которое пользователь увидит при оплате;
- в объекте `payment_method_data` передайте код способа оплаты `sber_bnpl`;
- в параметре `payment_method_data.phone` передайте номер телефона пользователя;
- в объекте `confirmation` в параметре `type` передайте тип `redirect`, а в параметре `return_url` — ссылку, по которой пользователь вернется к вам в магазин после оплаты.

В запросе можно передать дополнительные параметры, кроме `payment_token`, `payment_method_id`, `airline`, `transfers`, `deal`.

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
          "value": "1000.00",
          "currency": "RUB"
        },
        "payment_method_data": {
          "type": "sber_bnpl",
          "phone": "79000000000"
        },
        "confirmation": {
          "type": "redirect",
          "return_url": "https://www.example.com/return_url"
        },
        "capture": true,
        "description": "Заказ №72"
      }'
```

В ответ на запрос вернется [объект платежа](https://yookassa.ru/developers/api#payment_object) в актуальном статусе.

**Шаг 3.** Перенаправьте пользователя на страницу ЮKassa, адрес которой придет в `confirmation_url`.  С этой страницы ЮKassa самостоятельно перенаправит пользователя в сервис «Плати частями» для завершения оплаты.

**Пример тела ответа**

**JSON**

```json
{
  "id": "22e12f66-000f-5000-8000-18db351245c7",
  "status": "pending",
  "paid": false,
  "amount": {
    "value": "1000.00",
    "currency": "RUB"
  },
  "confirmation": {
    "type": "redirect",
    "return_url": "https://www.example.com/return_url",
    "confirmation_url": "https://yoomoney.ru/checkout/payments/v2/contract?orderId=22e12f66-000f-5000-8000-18db351245c7"
  },
  "created_at": "2021-04-12T13:59:33.681Z",
  "description": "Заказ №72",
  "metadata": {},
  "payment_method": {
    "type": "sber_bnpl",
    "id": "22e12f66-000f-5000-8000-18db351245c7",
    "saved": false,
    "status": "inactive"
  },
  "recipient": {
    "account_id": "100500",
    "gateway_id": "100700"
  },
  "refundable": false,
  "test": false
}
```

**Шаг 4.** Дождитесь успешного завершения платежа: подождите, когда придет когда придет [уведомление от ЮKassa](https://yookassa.ru/developers/using-api/webhooks), или периодически отправляйте запросы, чтобы получить [информацию о платеже](https://yookassa.ru/developers/api#get_payment).

**Пример платежа в статусе succeeded**

**JSON**

```json
{
  "id": "22e12f66-000f-5000-8000-18db351245c7",
  "status": "succeeded",
  "paid": true,
  "amount": {
    "value": "1000.00",
    "currency": "RUB"
  },
  "captured_at": "2021-04-13T09:27:09.960Z",
  "created_at": "2021-04-13T09:25:13.087Z",
  "description": "Заказ №72",
  "income_amount": {
    "value": "1000.00",
    "currency": "RUB"
  },
  "payment_method": {
    "type": "sber_bnpl",
    "id": "22e12f66-000f-5000-8000-18db351245c7",
    "saved": false,
    "status": "inactive"
  },
  "recipient": {
    "account_id": "100500",
    "gateway_id": "100700"
  },
  "refundable": true,
  "refunded_amount": {
    "value": "0.00",
    "currency": "RUB"
  },
  "test": false
}
```

**Шаг 5.** Сообщите пользователю результат оплаты.

Готово! Если вы проводите платеж в две стадии, [подтвердите](https://yookassa.ru/developers/payment-acceptance/getting-started/payment-process#capture) или [отмените платеж](https://yookassa.ru/developers/payment-acceptance/getting-started/payment-process#cancel). Сообщите пользователю финальный результат платежа.

Платежи в две стадии

Платежи через сервис «Плати частями» можно проводить в [одну или две стадии](https://yookassa.ru/developers/payment-acceptance/getting-started/payment-process#capture-and-cancel). Если проводите платежи в две стадии, всё проходит [стандартно](https://yookassa.ru/developers/payment-acceptance/getting-started/payment-process#capture-and-cancel). Оплату по двухстадийному платежу можно списать полностью или частично, а также отменить. Есть нюансы с точки зрения взаимодействия с пользователем:

- Если вы списываете оплату полностью, всё стандартно. Партнер списывает по графику ту сумму, которую пользователь видел при подтверждении платежа.
- Если вы списываете оплату по платежу частично, ЮKassa передает партнеру новую сумму платежа. Партнер на своей стороне уменьшает сумму периодических платежей и информирует пользователя об изменении суммы в своем интерфейсе.
- Если вы отменяете платеж, партнер самостоятельно возвращает пользователю списанную сумму.

[Подробнее о платежах в две стадии](https://yookassa.ru/developers/payment-acceptance/getting-started/payment-process#capture-and-cancel)

Возвраты платежей

Возврат платежа [стандартный](https://yookassa.ru/developers/payment-acceptance/after-the-payment/refunds). Чтобы сделать возврат, вы отправляете запрос по API ЮKassa. Зачислением возврата платежа на карту пользователя занимается партнер без участия ЮKassa.

Вернуть можно только те платежи, с момента создания которых прошло не больше 1 года. Срок возврата — от 1 до 10 рабочих дней.

Комиссия ЮKassa и партнера за проведение платежа не возвращается.

Отправка чеков в налоговую

[Чеки от ЮKassa](https://yookassa.ru/developers/payment-acceptance/receipts/54fz/yoomoney/basics) недоступны для способа оплаты «Плати частями».

Для отправки чеков в налоговую можно использовать решение ЮKassa для отправки чеков [сторонней онлайн-кассе](https://yookassa.ru/developers/payment-acceptance/receipts/54fz/other-services/basics) или пробивать чеки самостоятельно.

По платежам через сервис «Плати частями» пользователь получает два чека:

1. Первый чек на полную сумму покупки — его отправляете вы.
2. Второй чек на сумму комиссии за использование сервиса «Плати частями» — его отправляет партнер.

Если вы вернули, отменили или частично подтвердили платеж, вам нужно стандартно сформировать дополнительные чеки. [Подробнее об отправке чеков](https://yookassa.ru/developers/payment-acceptance/receipts/54fz/other-services/basics#onboarding)

Неуспешные платежи и возвраты

Если в процессе платежа или возврата что-то пошло не так, может потребоваться обращение в техническую поддержку ЮKassa или партнера. Зависит от того, на чьей стороне и в какой момент возникла ошибка:

- если у вас в процессе создания платежа или возврата возникла ошибка, обратитесь в техническую поддержку ЮKassa — напишите на почту `b2b_support@yoomoney.ru` или в [чате](https://yookassa.ru/my/payments?chat=open);
- если у вас есть вопрос по зачислению возврата на карту пользователя, обратитесь в техническую поддержку партнера — напишите на почту `support@cnfs.ru`;
- если у пользователя есть вопросы по платежу или возврату, вы можете рекомендовать ему обратиться в поддержку партнера — +`7``800``10``10``999`.

Реестры платежей и возвратов

Все взаиморасчеты по платежам и возвратам через сервис «Плати частями» вы проводите напрямую с партнером — ООО «ЦНФС» (Центр Новых Финансовых Сервисов).

В [реестрах платежей и возвратов](https://yookassa.ru/developers/payment-acceptance/after-the-payment/reports) от ЮKassa будет отсутствовать информация о платежах через сервис «Плати частями». Это связано с тем, что в реестрах указывается только информация о расчетах с ЮKassa.

Реестры платежей и возвратов по платежам через сервис «Плати частями» вы получаете от партнера. Партнер отправит реестры с почты с доменом `@sber-solution` или `@cnfs.ru`. Формат и содержание реестров определяется на стороне партнера и будет отличаться от реестров ЮKassa.

По вопросам реестров, сверок и взаиморасчетов вы можете написать партнеру напрямую — `finance@cnfs.ru`.

Что почитать еще

[Основы проведения платежей](https://yookassa.ru/developers/payment-acceptance/getting-started/payment-process)

[Неуспешные платежи](https://yookassa.ru/developers/payment-acceptance/after-the-payment/declined-payments)

[Отправка чеков в налоговую](https://yookassa.ru/developers/payment-acceptance/receipts/basics)

[Тестирование платежей](https://yookassa.ru/developers/payment-acceptance/testing-and-going-live/testing)
