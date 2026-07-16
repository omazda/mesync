<!-- Источник: https://yookassa.ru/developers/payment-acceptance/getting-started/payment-methods -->
<!-- Полная копия статьи официальной документации ЮKassa, сохранено 2026-07-02 -->

# Способы оплаты

О способах оплаты

ЮKassa умеет принимать платежи разными способами: с банковских карт, из электронных кошельков, с баланса мобильного телефона, в кредит или рассрочку, наличными, выставлять счета в интернет-банке.

Произвольные банковские карты

Вы можете принимать оплату [банковскими картами](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/bank-card) Visa, Mastercard, Maestro, Мир, JCB и другими. К оплате принимаются карты, выпущенные в России, и некоторые зарубежные карты. [Подробнее о картах, которые можно использовать для оплаты через ЮKassa](https://yookassa.ru/docs/support/payments/accept-methods#cards)

По умолчанию пользователь будет вводить данные карты на странице ЮKassa, но можно [встроить форму](https://yookassa.ru/developers/payment-acceptance/getting-started/selecting-integration-scenario) себе на сайт или в мобильное приложение.

Платежи через приложения бесконтактной оплаты

Вы можете принимать оплату картами Мир через [Mir Pay](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/mir-pay). Доступно только для мобильных устройств на Android.

Оплата из электронных кошельков

Вы можете принимать оплату из кошелька [ЮMoney](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/yoo-money) или с привязанной к нему банковской карты.

Оплата через приложения банков

Вы можете принимать оплату через [SberPay](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/sberpay) с подтверждением в приложении СберБанк Онлайн, [Alfa Pay](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/other/alfa-pay) с подтверждением в приложении Альфа Банка, [T-Pay](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/other/tinkoff-bank) с подтверждением в приложении T-Банка, а также принимать платежи через [СБП](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/other/sbp) (Система быстрых платежей ЦБ РФ).

Кредитование

Вы можете продавать товары в кредит и рассрочку с помощью сервиса «[Покупки в кредит](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/other/sber-loan)» от СберБанка.

BNPL-сервисы

Вы можете дать пользователю возможность оплатить покупку частями без оформления кредитного договора с помощью BNPL-сервиса «[Плати частями](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/other/sber-bnpl)».

B2B-платежи

Вы можете принимать платежи от юридических лиц и ИП через [СберБанк Бизнес Онлайн](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/other/b2b-sberbank).

[Подробнее о B2B-платежах](https://yookassa.ru/b2b/)

Другие способы оплаты

Вы можете принимать платежи с [баланса мобильного телефона](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/other/mobile-balance), [наличными](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/other/cash) через терминал или офис партнера, а также принимать оплату по [электронным сертификатам](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/other/electronic-certificate/basics).

Все способы оплаты

| Название и код способа оплаты | Срок оплаты | Холдиро- вание | Код в реестре | Возврат | Автоплатежи |
| --- | --- | --- | --- | --- | --- |
| **Произвольные банковские карты** | | | | | |
| [Банковская карта](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/bank-card)  `bank_card` | 1 час | 7 дней | AC | ✅ | ✅ |
| **Платежи через приложения бесконтактной оплаты** | | | | | |
| [Mir Pay](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/mir-pay)  `bank_card` | 1 час | 7 дней | AC | ✅ | ✅ |
| **Электронные кошельки** | | | | | |
| [ЮMoney](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/yoo-money)  `yoo_money` | 1 час | 7 дней | PC | ✅ | ✅ |
| **Оплата через приложения банков** | | | | | |
| [SberPay](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/sberpay)  `sberbank` | 1 час | 7 дней | SB | ✅ | ✅ |
| [Alfa Pay](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/other/alfa-pay)  `alfa_pay` | 1 час | — | AP | ✅ | ❌ |
| [T-Pay](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/other/tinkoff-bank)  `tinkoff_bank` | 1 час | 7 дней | TB | ✅ | ✅ |
| [СБП (Система быстрых платежей)](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/other/sbp)  `sbp` | 1 час | — | CP | ✅ | ✅ |
| **Кредитование** | | | | | |
| [«Покупки в кредит» от СберБанка](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/other/sber-loan)  `sber_loan` | от 8 до 72 часов, [подробнее об условиях](https://yookassa.ru/docs/support/payments/credit-purchases-by-sberbank-with-cooling-off) | 2 часа | SL | ✅ | ❌ |
| **BNPL-сервисы** | | | | | |
| [Плати частями](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/other/sber-bnpl)  `sber_bnpl` | 1 час | 7 дней | [Не указывается в реестрах от ЮKassa](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/other/sber-bnpl#registry) | ✅ | ❌ |
| **B2B-платежи** | | | | | |
| [СберБанк Бизнес Онлайн](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/other/b2b-sberbank)  `b2b_sberbank` | 8 часов | — | 2S | ❌ | ❌ |
| **Другие способы** | | | | | |
| [Баланс телефона](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/other/mobile-balance)  `mobile_balance` | 1 час | 6 часов | MC | ✅ | ❌ |
| [Наличные](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/other/cash)  `cash` | Без ограничений | 6 часов | GP | ❌ | ❌ |
| [Электронный сертификат](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/other/electronic-certificate/basics)  `electronic_certificate` | 1 час | — | EC | ✅ | ❌ |

Информация по платежам будет приходить в [реестре платежей](https://yookassa.ru/developers/payment-acceptance/after-the-payment/reports).

Ограничения

Лимиты

Для всех способов оплаты есть лимиты на минимальный и максимальный размер платежа. Для некоторых способов оплаты существуют дополнительные лимиты, например на общую сумму платежей за сутки или месяц. Если лимиты превышены, платежи не пройдут.

[Подробнее о лимитах](https://yookassa.ru/docs/support/payments/limits)

Срок оплаты

В ЮKassa у платежа ограничено время на оплату. Если пользователь не подтвердит оплату до окончания этого срока, ЮKassa отменит платеж, в [причинах отмены](https://yookassa.ru/developers/payment-acceptance/after-the-payment/declined-payments#cancellation-details-reason) будет указано `expired_on_confirmation`. Чтобы пользователь смог оплатить, вам нужно [создать новый платеж](https://yookassa.ru/developers/api#create_payment).

При оплате в приложении банка или другой внешней платежной системе пользователю выставляется счет от ЮKassa. Если в этой системе время на оплату еще есть, а в ЮKassa оно уже истекло, деньги спишутся, но платеж не пройдет. Деньги моментально вернутся пользователю.

Что почитать еще

[Сценарии интеграции](https://yookassa.ru/developers/payment-acceptance/getting-started/selecting-integration-scenario)

[Основы проведения платежей](https://yookassa.ru/developers/payment-acceptance/getting-started/payment-process)

[Неуспешные платежи](https://yookassa.ru/developers/payment-acceptance/after-the-payment/declined-payments)

[Возвраты платежей](https://yookassa.ru/developers/payment-acceptance/after-the-payment/refunds)

[Реестры операций](https://yookassa.ru/docs/support/merchant/payments/reports/overview)
