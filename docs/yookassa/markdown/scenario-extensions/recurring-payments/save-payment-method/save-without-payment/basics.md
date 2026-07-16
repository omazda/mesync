<!-- Источник: https://yookassa.ru/developers/payment-acceptance/scenario-extensions/recurring-payments/save-payment-method/save-without-payment/basics -->
<!-- Полная копия статьи официальной документации ЮKassa, сохранено 2026-07-02 -->

# Привязка на нулевую сумму

Привязка на нулевую сумму — это вид сохранения способа оплаты, при котором у пользователя не списываются деньги со счета. В процессе привязки ЮKassa сначала проверяет, что платежное средство можно использовать для автоплатежей (например, что нет блокировок или других ограничений), а затем привязывает его к вашему магазину.

Особенности

Доступные способы оплаты

Привязки на нулевую сумму доступны для следующих способов оплаты:

- [Банковские карты](https://yookassa.ru/developers/payment-acceptance/scenario-extensions/recurring-payments/save-payment-method/save-without-payment/bank-card)
- [СБП](https://yookassa.ru/developers/payment-acceptance/scenario-extensions/recurring-payments/save-payment-method/save-without-payment/sbp)

Тестирование

Автоплатежи с привязкой на нулевую сумму по умолчанию доступны в [тестовом магазине](https://yookassa.ru/developers/payment-acceptance/testing-and-going-live/testing). Если вы хотите проводить автоплатежи в настоящем магазине — сообщите об этом вашему менеджеру ЮKassa.

Протестировать можно только привязку банковской карты. Платежи и привязки через СБП в тестовом магазине недоступны.

Для партнеров

Если вы [партнер](https://yookassa.ru/developers/solutions-for-platforms/partners-api/basics) и для аутентификации запросов используете OAuth-токен, вы можете сохранять способ оплаты и проводить автоплатежи от имени пользователей ЮKassa. Для этого:

- сообщите магазину, что ему нужно обратиться к менеджеру ЮKassa, чтобы подключить автоплатежи;
- [запросите у магазина право](https://yookassa.ru/developers/solutions-for-platforms/partners-api/oauth/basics) на сохранение и использование способов оплаты для повторных платежей.

Сценарии привязки способа оплаты

Для привязки на нулевую сумму доступен только один сценарий — привязка конкретного способа оплаты.

В этом сценарии вы максимально контролируете взаимодействие с пользователем: ЮKassa берёт на себя только взаимодействие с платежными системами и сервисами. Вам необходимо самостоятельно реализовать следующие шаги процесса привязки:

- выбор способа оплаты (если у вас несколько способов оплаты для автоплатежей);
- получение от пользователя данных платежного средства (зависит от варианта интеграции);
- сообщение пользователю результатов сохранения способа оплаты.

Сценарии подтверждения привязки аналогичны [сценариям подтверждения платежа](https://yookassa.ru/developers/payment-acceptance/getting-started/payment-process#confirmation-scenarios), только без списания денег.

Есть два варианта интеграции:

- **Привязка на готовой странице ЮKassa**: вы перенаправляете пользователя на готовую страницу ЮKassa, где он сразу вводит данные для привязки конкретного способа оплаты, и подтверждает привязку.
- **Привязка со сбором данных на вашей стороне**: вы самостоятельно запрашиваете у пользователя данные для привязки платежного средства, затем отправляете их ЮKassa и реализуете подтверждение привязки.

| Способ оплаты | Вариант интеграции | Сценарий подтверждения | Сбор платежных данных |
| --- | --- | --- | --- |
| Банковская карта  `bank_card` | [Привязка банковской карты на готовой странице ЮKassa](https://yookassa.ru/developers/payment-acceptance/scenario-extensions/recurring-payments/save-payment-method/save-without-payment/bank-card#ready-made-payment-form) | Redirect | ➖ |
| [Привязка банковской карты с вводом данных на вашей стороне](https://yookassa.ru/developers/payment-acceptance/scenario-extensions/recurring-payments/save-payment-method/save-without-payment/bank-card#merchant-side) (нужен сертификат о соответствии требованиям [PCI DSS](https://ru.wikipedia.org/wiki/PCI_DSS)) | Redirect | ✔️ |
| СБП (Система быстрых платежей)  `sbp` | [Привязка счета СБП на готовой странице ЮKassa](https://yookassa.ru/developers/payment-acceptance/scenario-extensions/recurring-payments/save-payment-method/save-without-payment/sbp#ready-made-payment-form) | Redirect | ➖ |
| [Привязка счета СБП с отображением QR-кода на вашей стороне](https://yookassa.ru/developers/payment-acceptance/scenario-extensions/recurring-payments/save-payment-method/save-without-payment/sbp#merchant-side) | QR-код | ➖ |

Порядок работы

Привязка на нулевую сумму, независимо от выбранного сценария привязки и платежного средства, проходит следующим образом:

1. Вы создаете привязку.
2. ЮKassa возвращает вам идентификатор способа оплаты. Его пока нельзя использовать для автоплатежей, нужно дождаться, когда ЮKassa проверит платежное средство.
3. Пользователь подтверждает привязку.
4. ЮKassa проверяет, что с платежным средством всё в порядке и его можно использовать для последующих автоплатежей.
5. ЮKassa привязывает платежное средство к вашему магазину.
6. Вы сохраняете идентификатор способа оплаты. Он нужен, чтобы проводить [автоплатежи](https://yookassa.ru/developers/payment-acceptance/scenario-extensions/recurring-payments/pay-with-saved).

Что почитать еще

[Привязка счета СБП на нулевую сумму](https://yookassa.ru/developers/payment-acceptance/scenario-extensions/recurring-payments/save-payment-method/save-without-payment/sbp)

[Привязка банковской карты на нулевую сумму](https://yookassa.ru/developers/payment-acceptance/scenario-extensions/recurring-payments/save-payment-method/save-without-payment/bank-card)

[Привязка во время платежа](https://yookassa.ru/developers/payment-acceptance/scenario-extensions/recurring-payments/save-payment-method/save-during-payment)

[Платеж без сохранения способа оплаты](https://yookassa.ru/developers/payment-acceptance/scenario-extensions/recurring-payments/pay-without-saving)
