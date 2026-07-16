<!-- Источник: https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/other/sber-loan -->
<!-- Полная копия статьи официальной документации ЮKassa, сохранено 2026-07-02 -->

# «Покупки в кредит» от СберБанка

Этот способ оплаты доступен, только если:

- Вы принимаете платежи на сайте.
- Вы используете [обычные платежи](https://yookassa.ru/developers/payment-acceptance/overview) или [партнерскую программу](https://yookassa.ru/developers/solutions-for-platforms/partners-api/basics).

Особенности

- Тип способа оплаты в API: `sber_loan`
- [Сценарий подтверждения](https://yookassa.ru/developers/payment-acceptance/getting-started/payment-process#user-confirmation): Redirect
- [Срок оплаты](https://yookassa.ru/developers/payment-acceptance/getting-started/payment-methods#payment-term): 8 часов, если сумма платежа до 50 000 руб., 28 часов, если сумма платежа от 50 000 до 200 000 руб., 72 часа, если сумма больше 200 000 руб.
- [Холдирование](https://yookassa.ru/developers/payment-acceptance/getting-started/payment-process#capture-and-cancel): 2 часа, доступно полное и частичное списание оплаты, есть [особенности](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/other/sber-loan#two-stage-payments)
- [Код в реестре](https://yookassa.ru/developers/payment-acceptance/after-the-payment/reports): SL, есть [особенности](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/other/sber-loan#reports)
- [Возврат](https://yookassa.ru/developers/payment-acceptance/after-the-payment/refunds): да, полный и частичный, есть [особенности](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/other/sber-loan#refunds)
- Срок возврата: от 1 до 3 рабочих дней
- [Автоплатежи](https://yookassa.ru/developers/payment-acceptance/scenario-extensions/recurring-payments/basics): нет
- [Лимиты](https://yookassa.ru/developers/payment-acceptance/getting-started/payment-methods#payment-limit): минимальный размер платежа — 3 000 рублей, максимальный — 1,5 млн рублей, есть [особенности](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/other/sber-loan#payment-method-overview-limits)

Сценарии интеграции

Готовые решения:

- [Умный платеж](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/smart-payment)
- [Виджет ЮKassa](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/basics)

Самостоятельная интеграция: [Оплата на готовой странице ЮKassa](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/other/sber-loan#create-payment-redirect)

О способе оплаты

- [Кто может оформить кредит](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/other/sber-loan#payment-method-overview-requirements)
- [Какие есть тарифы](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/other/sber-loan#payment-method-overview-loan-options)
- [Какие есть особенности кредитов и рассрочек](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/other/sber-loan#payment-method-overview-loan-options-specifics)
- [Какие есть лимиты платежей](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/other/sber-loan#payment-method-overview-limits)
- [Как проходит платеж](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/other/sber-loan#payment-method-process)
- [Как выглядят сценарии проведения платежа и возврата](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/other/sber-loan#payment-method-scenarios)
- [Как подключить способ оплаты](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/other/sber-loan#payment-method-overview-activation)

Кто может оформить кредит

Оформить кредит от СберБанка при оплате покупки могут пользователи с гражданством РФ, у которых есть действующая дебетовая карта СберБанка и доступ к СберБанку Онлайн. [Полные и актуальные требования к покупателям](https://www.sberbank.com/ru/person/credits/money/pos)

Какие есть тарифы

С 1 января 2026 года комиссия за платежи в ЮKassa [увеличится на сумму НДС](https://yookassa.ru/developers/using-api/changelog#2025-12-25): вместе с комиссией за платежи будет списываться НДС — 22% от суммы комиссии. Все примеры расчетов обновлены в соответствии с этими изменениями. До 1 января 2026 года сумму НДС не нужно учитывать при расчетах.

Есть два типа тарифов — кредит и рассрочка:

- Кредит (потребительский кредит) — пользователю нужно вернуть СберБанку стоимость покупки с процентами. Вы получите всю стоимость покупки за вычетом комиссии ЮKassa и суммы НДС с этой комиссии.
- Рассрочка (кредит без переплат) — проценты уже входят в стоимость покупки, поэтому формально пользователь не платит проценты за использование денег СберБанка. Фактически при оформлении рассрочки вы сделаете скидку с суммы покупки (скидка равна процентам за использование заемных денег). Вы получите стоимость покупки, уменьшенную на сумму скидки, за вычетом комиссии ЮKassa и суммы НДС с этой комиссии.

Пример: стоимость покупки (сумма платежа) 5 000 рублей, комиссия ЮKassa — 3,5%, НДС с комиссии — 22%.

| Тариф | Сколько пользователь заплатит банку | Сколько получите вы |
| --- | --- | --- |
| Кредит | Стоимость покупки + проценты банку за использование заемных денег:  `5 000 рублей + проценты` | Стоимость покупки за вычетом комиссии ЮKassa:  `5 000 * (1 − (0.035 + (0.035 * 0.22)))= 5 000 * 0,9573 = 4 786,5 рублей` |
| Рассрочка | Стоимость покупки:  `5 000 рублей` | Стоимость покупки, уменьшенная на сумму скидки СберБанка (например, 10 % от стоимости покупки), за вычетом комиссии ЮKassa:  `(5 000 - 500) * (1 − (0.035 + (0.035 * 0.22))) = 4 500 * 0,9573 = 4 307,85 рублей` |

Конкретные тарифы и их условия можно узнать у менеджера ЮKassa.

Тарифы вы выбираете при подключении способа оплаты и согласовываете с менеджером. При оплате на платежной форме отображаются все выбранные тарифы, пользователь может выбирать между ними. [Подробнее о том, как проходит платеж](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/other/sber-loan#payment-method-process)

Какие есть особенности кредитов и рассрочек

Особенности кредита

- Сумма платежа не меняется. Вы получите всю стоимость покупки за вычетом комиссии ЮKassa.
- При частичном подтверждении платежа сумма должна укладываться в [лимиты](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/other/sber-loan#payment-method-overview-limits-payment-capture).
- При частичном подтверждении, отмене и возврате платежа ЮKassa вернет деньги на карту пользователя. Пользователю нужно самостоятельно погасить задолженность в приложении или на сайте СберБанка Онлайн.

Особенности рассрочек

- Сумма платежа **меняется**: после успешной оплаты ЮKassa пересчитает сумму, которую вы передали в запросе, с учетом скидки по рассрочке. Вы получите стоимость покупки, уменьшенную на сумму скидки, за вычетом комиссии ЮKassa.
- При подтверждении, отмене и возврате платежа вам нужно указывать сумму с учетом скидки.
- При частичном подтверждении платежа сумма должна укладываться в [лимиты](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/other/sber-loan#payment-method-overview-limits-payment-capture).
- При частичном подтверждении, отмене и возврате платежа ЮKassa вернет деньги на карту пользователя. Пользователю нужно самостоятельно погасить задолженность в приложении или на сайте СберБанка Онлайн.
- Если используете решения ЮKassa для [отправки чеков в налоговую](https://yookassa.ru/developers/payment-acceptance/receipts/54fz/basics), при проведении платежа ЮKassa автоматически пересчитает стоимость товаров в чеке (учтет скидку). При частичном подтверждении или частичном возврате платежа вам нужно самостоятельно пересчитать стоимость товаров и передать данные для чека с учетом скидки.

Подробнее об особенностях рассрочек:

- [Особенности проведения платежей в две стадии](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/other/sber-loan#two-stage-payments)
- [Возвраты платежей](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/other/sber-loan#refunds)
- [Отправка чеков в налоговую](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/other/sber-loan#receipts)

Какие есть лимиты платежей

Лимиты платежей зависят от ограничений СберБанка на сумму выдаваемого кредита. Есть лимиты при создании и при подтверждении платежа.

Лимиты при создании платежа

Минимальная сумма платежа:

- Для кредита — 3 000 рублей.
- Для рассрочки — 3 000 рублей плюс сумма максимальной скидки по рассрочке среди выбранных вами тарифов. Пример: если у вас самая большая скидка для рассрочки 10 %, то минимальная сумма платежа — 3 300 рублей (3 000 рублей + скидка 300 рублей).

Максимальная сумма платежа — 1,5 млн рублей.

Лимиты при подтверждении платежа

Минимальная сумма для частичного подтверждения платежа — 3 000 рублей.

Как проходит платеж

Информация актуальна для платежей до 50 000 рублей.  Платежи на большую сумму могут проходить с [охлаждением](https://yookassa.ru/docs/support/payments/credit-purchases-by-sberbank-with-cooling-off).  Особенности проведения таких платежей будут добавлены позже.

При оплате товара пользователь выбирает «Покупки в кредит» от СберБанка и при необходимости тариф — кредит или рассрочку на определенное количество месяцев.

Как это выглядит в разных сценариях интеграции:

![Пример платежной формы при использовании Умного платежа](https://static.yoomoney.ru/docops-static/images/developers-payments-sber-loan-payment-form-smart-payment.image.ru.bbd783ea.svg)

Пример платежной формы при использовании Умного платежа

После этого пользователь переходит в СберБанк Онлайн, где заполняет заявку. Когда СберБанк рассмотрит заявку, он через ЮKassa перечислит вам деньги и перенаправит пользователя обратно к вам на сайт. [Подробные схемы, как проходят платежи и возвраты](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/other/sber-loan#payment-method-scenarios)

Тариф, который выбрал пользователь при платеже, и сумму скидки для рассрочек вы узнаете после успешной оплаты. Если оплата прошла успешно (статус платежа `waiting_for_capture` или `succeeded`), в объекте платежа в объекте `payment_method` вернется информация о выбранном тарифе (параметр `loan_option`) и скидке для рассрочек (объект `discount_amount`). Для рассрочек сумма платежа в объекте `amount` изменится на сумму платежа с учетом скидки.

**Пример платежа в статусе succeeded (кредит)**

**JSON**

```json
{
  "id": "22c5d0f0-000f-5000-8000-13ece77bc6c1",
  "status": "succeeded",
  "paid": true,
  "amount": {
    "value": "5000.00",
    "currency": "RUB"
  },
  "income_amount": {
    "value": "4825.00",
    "currency": "RUB"
  },
  "captured_at": "2021-06-22T21:44:55.506Z",
  "created_at": "2021-06-22T21:43:44.794Z",
  "description": "Заказ №37",
  "metadata": {
    "order_id": "37"
  },
  "payment_method": {
    "type": "sber_loan",
    "id": "22c5d0f0-000f-5000-8000-13ece77bc6c1",
    "saved": false,
    "loan_option": "loan"
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
  "test": true
}
```

**Пример платежа в статусе succeeded (рассрочка)**

**JSON**

```json
{
  "id": "22c5d0f0-000f-5000-8000-13ece77bc6c1",
  "status": "succeeded",
  "paid": true,
  "amount": {
    "value": "4500.00",
    "currency": "RUB"
  },
  "income_amount": {
    "value": "4342.50",
    "currency": "RUB"
  },
  "captured_at": "2021-06-22T21:44:55.506Z",
  "created_at": "2021-06-22T21:43:44.794Z",
  "description": "Заказ №37",
  "metadata": {
    "order_id": "37"
  },
  "payment_method": {
    "type": "sber_loan",
    "id": "22c5d0f0-000f-5000-8000-13ece77bc6c1",
    "saved": false,
    "loan_option": "installments_12",
    "discount_amount": {
      "value": "500.00",
      "currency": "RUB"
    }
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
  "test": true
}
```

Как выглядят сценарии проведения платежа и возврата

- [Сценарий проведения платежа](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/other/sber-loan#payment-method-scenarios-payment)
- [Сценарий проведения возврата](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/other/sber-loan#payment-method-scenarios-refund)

Проведение платежа

Информация актуальна для платежей до 50 000 рублей.  Платежи на большую сумму могут проходить с [охлаждением](https://yookassa.ru/docs/support/payments/credit-purchases-by-sberbank-with-cooling-off).  Особенности проведения таких платежей будут добавлены позже.

В этом разделе описан общий порядок проведения платежа и возврата для сценариев [Умный платеж](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/smart-payment) и [самостоятельная интеграция с оплатой на готовой странице ЮKassa](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/other/sber-loan#create-payment-redirect). В выбранном вами [сценарии интеграции](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/other/sber-loan#integration-scenarios) порядок действий может немного меняться.

![Проведение платежа](https://static.yoomoney.ru/docops-static/images/developers-payments-schema-sber-loan-payment.image.ru.d24ccf2c.svg)

Проведение платежа

Как проходит платеж:

1. Пользователь переходит к оплате (например, для Умного платежа нажимает кнопку **Заплатить**).
2. Вы создаете платеж — отправляете ЮKassa POST-запрос с учетом выбранного вами сценария интеграции.
3. ЮKassa возвращает вам созданный объект платежа в статусе `pending` и со ссылкой на платежную форму (параметр `confirmation_url` в объекте платежа).
4. Вы перенаправляете пользователя на страницу оплаты.
5. Пользователь выбирает нужный ему тариф.
6. ЮKassa перенаправляет пользователя в СберБанк Онлайн.
7. Пользователь в СберБанке Онлайн заполняет заявку на кредит в соответствии с выбранным тарифом.
8. СберБанк рассматривает заявку.
9. СберБанк сообщает результат ЮKassa и пользователю и перенаправляет пользователя к вам на сайт.
10. Если пользователь выбрал рассрочку, ЮKassa рассчитает сумму скидки с учетом того тарифа, который выбрал пользователь, и изменит сумму платежа в объекте платежа и в чеках (если вы отправляете чеки в налоговую через ЮKassa).
11. Если у вас настроены [уведомления](https://yookassa.ru/developers/using-api/webhooks), ЮKassa присылает уведомление о переходе платежа в статус `succeeded` (для платежей в одну стадию) или в статус `waiting_for_capture` (для платежей в [две стадии](https://yookassa.ru/developers/payment-acceptance/getting-started/payment-process#capture-and-cancel)).
12. Вы запрашиваете информацию о платеже — отправляете ЮKassa GET-запрос с идентификатором платежа.
13. ЮKassa возвращает вам созданный объект платежа в актуальном статусе.
14. Вы сообщаете пользователю результат проведения платежа.

Если вы проводите платежи в две стадии, то после получения оплаты от пользователя вам необходимо списать деньги или отменить платеж.

Как подтвердить или отменить платеж в две стадии

Возврат платежа

![Проведение возврата](https://static.yoomoney.ru/docops-static/images/developers-payments-schema-sber-loan-refund.image.ru.016e6dfe.svg)

Проведение возврата

Как проходит возврат платежа:

1. Вы создаете возврат — отправляете ЮKassa POST-запрос с идентификатором платежа и данными о том, какую часть платежа нужно вернуть.
2. ЮKassa возвращает пользователю указанную сумму.
3. ЮKassa возвращает вам объект возврата в статусе `succeeded`.
4. Вы сообщаете пользователю, что вернули деньги, и предупреждаете, что пользователю необходимо самостоятельно погасить задолженность в СберБанке Онлайн.
5. Пользователь погашает задолженность.

Как подключить способ оплаты

Проверьте, что вы можете подключить этот способ оплаты:

- Вы резидент РФ (российская компания или ИП).
- Вы принимаете платежи на сайте.
- Вы используете [обычные платежи](https://yookassa.ru/developers/payment-acceptance/overview) или [партнерскую программу](https://yookassa.ru/developers/solutions-for-platforms/partners-api/basics).

Чтобы подключить этот способ оплаты:

1. Сообщите менеджеру ЮKassa, что хотите использовать «Покупки в кредит» от СберБанка.
2. Выберите нужные вам тарифы из списка, который вам предложит менеджер.
3. Проинтегрируйтесь с ЮKassa по инструкциям:
   - Проведение платежа: [Умный платеж](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/smart-payment), [Виджет ЮKassa](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/basics) или самостоятельная интеграция с [оплатой на готовой странице ЮKassa](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/other/sber-loan#create-payment-redirect).
   - Платежи в две стадии (при необходимости): [общая инструкция](https://yookassa.ru/developers/payment-acceptance/getting-started/payment-process#capture-and-cancel) и [особенности, которые есть при частичном подтверждении и отмене платежей](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/other/sber-loan#two-stage-payments).
   - Возвраты платежей: [общая инструкция](https://yookassa.ru/developers/payment-acceptance/after-the-payment/refunds) и [особенности проведения возвратов](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/other/sber-loan#refunds).
   - Отправка чеков в налоговую: [общая инструкция](https://yookassa.ru/developers/payment-acceptance/receipts/54fz/basics) и [особенности для рассрочек](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/other/sber-loan#receipts).
4. При необходимости [добавьте дополнительные поля в реестры](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/other/sber-loan#reports) платежей и возвратов.
5. Протестируйте интеграцию — проведите платеж на минимальную сумму, затем сделайте возврат.

Готово! Можно принимать платежи от реальных пользователей.

Оплата на готовой странице ЮKassa

Как это работает

В этом сценарии вы самостоятельно реализуете выбор способа оплаты. После создания платежа вы перенаправляете пользователя на страницу ЮKassa. На этой странице отобразится платежная форма с тарифами, которые вы выбрали. По кнопке **Кредит от СберБанка** пользователь сможет перейти к оформлению потребительского кредита, а в блоке про **Рассрочки от СберБанка** сможет выбрать нужную ему рассрочку и перейти к ее оформлению.

![Пример платежной формы при самостоятельной интеграции](https://static.yoomoney.ru/docops-static/images/developers-payments-sber-loan-payment-form-redirect.image.ru.6072628e.svg)

Пример платежной формы при самостоятельной интеграции

Если вы подключили только кредит или только рассрочку, отобразится только одна кнопка с соответствующим названием.

Для интеграции добавьте на ваш сайт кнопку, по которой пользователь перейдет к оплате.

Кнопку и другие элементы управления для выбора этого способа оплаты необходимо сделать в соответствии со [стандартами оформления сайта](https://www.sberbank.com/common/img/uploaded/files/pokupay/website_design_standards.pdf).

Когда пользователь перейдет по кнопке, получите от ЮKassa ссылку на готовую страницу оплаты и перенаправьте на неё пользователя. Когда пользователь вернется обратно к вам на сайт, запросите у ЮKassa результаты платежа.

Как провести платеж

Информация актуальна для платежей до 50 000 рублей.  Платежи на большую сумму могут проходить с [охлаждением](https://yookassa.ru/docs/support/payments/credit-purchases-by-sberbank-with-cooling-off).  Особенности проведения таких платежей будут добавлены позже.

**Шаг 1**. Когда пользователь выберет «Покупки в кредит» от СберБанка, [создайте платеж](https://yookassa.ru/developers/api#create_payment): отправьте ЮKassa запрос с данными для аутентификации запроса, ключом идемпотентности и данными для платежа:

- в объекте `amount` передайте сумму, которую нужно списать с пользователя; сумма должна укладываться в [лимиты](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/other/sber-loan#payment-method-overview-limits-payment-create);
- в объекте `payment_method_data` передайте код способа оплаты `sber_loan`;
- в объекте `confirmation` передайте тип `redirect` и адрес страницы на вашей стороне, на которую пользователь вернется после оплаты (в параметре `return_url`);
- в параметре `description` передайте описание платежа, которое пользователь увидит при оплате.

В запросе можно передать любые [другие параметры](https://yookassa.ru/developers/api#create_payment), кроме `save_payment_method`, `payment_method_id`, `payment_token`, `airline`, `transfers`, `deal`.

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
          "type": "sber_loan"
        },
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
    $idempotenceKey = uniqid('', true);
    $response = $client->createPayment(
        array(
            'amount' => array(
                'value' => '5000.00',
                'currency' => 'RUB',
            ),
            'payment_method_data' => array(
                'type' => 'sber_loan',
            ),
            'confirmation' => array(
                'type' => 'redirect',
               'return_url' => 'https://www.example.com/return_url',
            ),
            'description' => 'Заказ №37',
            'metadata' => array(
                'order_id' => '37'
            ),
        ),
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
        "type": "sber_loan"
    },
    "confirmation": {
        "type": "redirect",
        "return_url": "https://www.example.com/return_url"
    },
    "description": "Заказ №37",
    "metadata": {
        "order_id": "37"
    }
}, idempotence_key)

# get confirmation url
confirmation_url = payment.confirmation.confirmation_url
```

В ответ на запрос вернется объект платежа в актуальном статусе.

**Шаг 2.** Перенаправьте пользователя на страницу ЮKassa, адрес которой придет в `confirmation_url`. Это ссылка на страницу ЮKassa, на которой пользователь выберет тариф и перейдет к подтверждению платежа.

**Пример тела ответа**

**JSON**

```json
{
  "id": "22c5d0f0-000f-5000-8000-13ece77bc6c1",
  "status": "pending",
  "paid": false,
  "amount": {
    "value": "5000.00",
    "currency": "RUB"
  },
  "confirmation": {
    "type": "redirect",
    "confirmation_url": "https://yoomoney.ru/payments/internal/confirmation?orderId=22c5d0f0-000f-5000-8000-13ece77bc6c1"
  },
  "created_at": "2021-06-22T21:44:55.506Z",
  "description": "Заказ №37",
  "payment_method": {
    "type": "sber_loan",
    "id": "22c5d0f0-000f-5000-8000-13ece77bc6c1",
    "saved": false
  },
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

**Шаг 3.** Дождитесь успешного завершения платежа: подождите, когда придет [уведомление от ЮKassa](https://yookassa.ru/developers/using-api/webhooks), или периодически отправляйте запросы, чтобы [получить информацию о платеже](https://yookassa.ru/developers/api#get_payment).

Если оплата прошла успешно (статус платежа `waiting_for_capture` или `succeeded`), в объекте платежа в объекте `payment_method` вернется информация о выбранном тарифе (параметр `loan_option`) и скидке для рассрочек (объект `discount_amount`). Для рассрочек сумма платежа в объекте `amount` изменится на сумму платежа с учетом скидки.

**Пример платежа в статусе succeeded (кредит)**

**JSON**

```json
{
  "id": "22c5d0f0-000f-5000-8000-13ece77bc6c1",
  "status": "succeeded",
  "paid": true,
  "amount": {
    "value": "5000.00",
    "currency": "RUB"
  },
  "income_amount": {
    "value": "4825.00",
    "currency": "RUB"
  },
  "captured_at": "2021-06-22T21:44:55.506Z",
  "created_at": "2021-06-22T21:43:44.794Z",
  "description": "Заказ №37",
  "metadata": {
    "order_id": "37"
  },
  "payment_method": {
    "type": "sber_loan",
    "id": "22c5d0f0-000f-5000-8000-13ece77bc6c1",
    "saved": false,
    "loan_option": "loan"
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
  "test": true
}
```

**Пример платежа в статусе succeeded (рассрочка)**

**JSON**

```json
{
  "id": "22c5d0f0-000f-5000-8000-13ece77bc6c1",
  "status": "succeeded",
  "paid": true,
  "amount": {
    "value": "4500.00",
    "currency": "RUB"
  },
  "income_amount": {
    "value": "4342.50",
    "currency": "RUB"
  },
  "captured_at": "2021-06-22T21:44:55.506Z",
  "created_at": "2021-06-22T21:43:44.794Z",
  "description": "Заказ №37",
  "metadata": {
    "order_id": "37"
  },
  "payment_method": {
    "type": "sber_loan",
    "id": "22c5d0f0-000f-5000-8000-13ece77bc6c1",
    "saved": false,
    "loan_option": "installments_12",
    "discount_amount": {
      "value": "500.00",
      "currency": "RUB"
    }
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
  "test": true
}
```

**Шаг 4.** Когда пользователь вернется на `return_url`, отобразите результат проведения платежа (успех или неудача) в зависимости от [статуса платежа](https://yookassa.ru/developers/payment-acceptance/getting-started/payment-process#lifecycle).

Готово! Если вы проводите [платеж в две стадии](https://yookassa.ru/developers/payment-acceptance/getting-started/payment-process#capture-and-cancel), подтвердите списание оплаты или отмените платеж. Сообщите пользователю финальный результат платежа.

Особенности проведения платежей в две стадии

Если проводите [платежи в две стадии](https://yookassa.ru/developers/payment-acceptance/getting-started/payment-process#capture-and-cancel), есть особенности при частичном подтверждении платежа и при отмене платежа:

- При частичном подтверждении сумма должна укладываться в [лимиты](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/other/sber-loan#payment-method-overview-limits-payment-capture).
- При частичном подтверждении и при отмене платежа ЮKassa вернет деньги на карту пользователя. Предупредите пользователя, что ему необходимо самостоятельно погасить задолженность в приложении или на сайте СберБанка Онлайн. Рекомендуется погасить задолженность как можно скорее, чтобы переплата была как можно меньше или отсутствовала (актуально для всех тарифов, включая рассрочки).

Дополнительно для рассрочек

В запросе на частичное подтверждение платежа указывайте сумму с учетом скидки.

Например, вы создали платеж на сумму 5 000 рублей. Пользователь выбрал рассрочку, скидка составила 10 % (500 рублей). В итоге вы получили 4 500 рублей. Если вы хотите списать, например, только три четверти платежа, подтвердите платеж на 3 375 рублей.

Возвраты платежей

Возврат платежа [стандартный](https://yookassa.ru/developers/payment-acceptance/after-the-payment/refunds).

Вернуть можно только те платежи, с момента создания которых прошло не больше 180 дней. Срок возврата — от 1 до 3 рабочих дней.

При возврате ЮKassa вернет деньги на карту пользователя. Предупредите пользователя, что ему необходимо самостоятельно погасить задолженность в приложении или на сайте СберБанка Онлайн. Рекомендуется погасить задолженность как можно скорее, чтобы переплата была как можно меньше или отсутствовала (актуально для всех тарифов, включая рассрочки).

Дополнительно для рассрочек

В запросе на возврат платежа указывайте сумму с учетом скидки.

Например, вы создали платеж на сумму 5 000 рублей. Пользователь выбрал рассрочку, скидка составила 10 % (500 рублей). В итоге вы получили 4 500 рублей. Если вы хотите вернуть платеж целиком, сделайте возврат на 4 500 рублей. Если хотите вернуть, например, половину платежа, сделайте возврат на 2 250 рублей.

Отправка чеков в налоговую

Для отправки чеков в налоговую можно использовать [решения ЮKassa](https://yookassa.ru/developers/payment-acceptance/receipts/54fz/basics). Если выбрали кредит, всё проходит стандартно, если выбрали рассрочку, то есть нюансы по поводу стоимости, которую нужно указывать в чеках.

Дополнительно для рассрочек

Чек при оплате

Если при оплате пользователь выбрал рассрочку, то при проведении платежа ЮKassa автоматически пересчитает стоимость товаров в чеке (учтет скидку).

Пример: при создании платежа вы указали такие данные для чека.

| Товар | Стоимость | Количество |
| --- | --- | --- |
| Товар 1 | 3 000.00 | 1 |
| Товар 2 | 1 000.00 | 2 |

Общая сумма заказа — 5 000 рублей.

Пользователь выбрал рассрочку, для которой скидка составила 10 % (500 рублей).

ЮKassa пересчитает суммы товаров в чеке.

| Товар | Стоимость | Количество |
| --- | --- | --- |
| Товар 1 | 2 700.00 | 1 |
| Товар 2 | 900.00 | 2 |

Общая сумма заказа — 4 500 рублей.

Чек при частичном подтверждении платежа или при частичном возврате

Если вы делаете частичное подтверждение платежа (при [оплате в две стадии](https://yookassa.ru/developers/payment-acceptance/getting-started/payment-process#capture-and-cancel)) или частичный возврат, вам нужно самостоятельно пересчитать стоимость товаров и передать данные для чека с учетом скидки.

Чтобы это сделать, до проведения платежа сохраните в своей системе перечень выбранных вами тарифов, соответствующие им значения в API и процент скидки.

При проведении частичного подтверждения платежа или частичного возврата:

**Шаг 1.** Узнайте, какой тариф выбрал пользователь при оплате. Эта информация есть в объекте платежа в параметре `payment_method.loan_option`.

**Шаг 2.** Определите процент скидки для этого тарифа.

**Шаг 3.** Откорректируйте стоимость товаров с учетом скидки. Если нужно округлить значение, используйте математическое округление. Пример:

- Исходная стоимость товара в чеке: 999,90 руб.
- Процент скидки: 5 %
- Сумма скидки: 49,995 руб.
- Стоимость товара с учетом скидки: 949,905 руб.
- Стоимость товара с учетом скидки, которую нужно передать в запросе: 949,91 руб.

**Шаг 4.** Отправьте ЮKassa запрос на частичный возврат или частичное подтверждение, в объекте `receipt` передайте стоимость товаров с учетом скидки.

Дополнительные поля в реестрах

Вы можете добавить в реестры успешных платежей и возвратов дополнительные поля про тариф кредита и сумму скидки. Как это сделать:

- Если у вас [стандартные реестры](https://yookassa.ru/docs/support/merchant/payments/reports/reports-old), напишите вашему менеджеру.
- Если у вас [расширенные реестры](https://yookassa.ru/docs/support/merchant/payments/reports/reports-new), добавьте нужные поля в личном кабинете. [Как добавить дополнительные поля для реестров](https://yookassa.ru/docs/support/merchant/payments/reports/reports-new#extra)

Что почитать еще

[Основы проведения платежей](https://yookassa.ru/developers/payment-acceptance/getting-started/payment-process)

[Неуспешные платежи](https://yookassa.ru/developers/payment-acceptance/after-the-payment/declined-payments)

[Отправка чеков в налоговую](https://yookassa.ru/developers/payment-acceptance/receipts/basics)
