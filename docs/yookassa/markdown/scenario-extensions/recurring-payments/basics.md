<!-- Источник: https://yookassa.ru/developers/payment-acceptance/scenario-extensions/recurring-payments/basics -->
<!-- Полная копия статьи официальной документации ЮKassa, сохранено 2026-07-02 -->

# Автоплатежи

Автоплатежи — это автоматические списания денег со счета пользователя. Их можно использовать, например, чтобы принимать абонентскую плату за подписку или моментально списывать оплату за покупки в вашем магазине без необходимости вводить платежные данные.

С помощью API ЮKassa вы можете принимать автоплатежи. Для этого пользователю нужно согласиться на привязку платежного средства — ЮKassa сохранит способ оплаты, и вы сможете использовать его, чтобы списывать деньги без дополнительного подтверждения.

По умолчанию автоплатежи работают только в [тестовом магазине](https://yookassa.ru/developers/payment-acceptance/testing-and-going-live/testing). Если хотите использовать их в вашем реальном магазине, напишите менеджеру ЮKassa.

Жизненный цикл автоплатежа

1. Подключение автоплатежа — вы получаете согласие пользователя на проведение автоплатежей. Для этого вы предупреждаете его, что сохраните платежные данные, а также рассказываете, как вы будете их использовать. Например, с какой регулярностью вы будете списывать деньги и как пользователь сможет отказаться от повторных списаний. Если пользователь согласен с условиями и хочет подключить автоплатежи, вы [сохраняете способ оплаты](https://yookassa.ru/developers/payment-acceptance/scenario-extensions/recurring-payments/basics#how-it-works-save-payment-method).
2. Проведение автоплатежа — вы [проводите автоплатежи](https://yookassa.ru/developers/payment-acceptance/scenario-extensions/recurring-payments/basics#how-it-works-use-payment-method), используя сохраненный способ оплаты в соответствии с условиями, на которые согласился пользователь.
3. Отключение автоплатежа — если пользователь решает отказаться от повторных списаний, вы [прекращаете использовать сохраненный способ оплаты](https://yookassa.ru/developers/payment-acceptance/scenario-extensions/recurring-payments/basics#how-it-works-delete-payment-method).

Как это работает

Основная сущность API ЮKassa для приема автоплатежей — способ оплаты. Это конкретное платежное средство, которое можно привязать к вашему магазину в ЮKassa и использовать для автоматических списаний денег со счета пользователя. Например, карта с номером `5555****4444` и карта с номером `4111****1111` — это два разных способа оплаты (в контексте проведения автоплатежей).

Со способом оплаты можно выполнять разные действия:

- [Сохранение способа оплаты](https://yookassa.ru/developers/payment-acceptance/scenario-extensions/recurring-payments/basics#how-it-works-save-payment-method) для привязки платежного средства к вашему магазину.
- [Использование сохраненного способа оплаты](https://yookassa.ru/developers/payment-acceptance/scenario-extensions/recurring-payments/basics#how-it-works-use-payment-method) для проведения автоплатежей и выплат.
- [Удаление сохраненного способа оплаты](https://yookassa.ru/developers/payment-acceptance/scenario-extensions/recurring-payments/basics#how-it-works-delete-payment-method) на вашей стороне для отключения автоплатежей.

Сохранение способа оплаты

Чтобы подключить пользователю автоплатежи, вы сохраняете способ оплаты — привязываете платежное средство к своему магазину. В ЮKassa есть два вида сохранения способа оплаты:

- [Привязка во время платежа](https://yookassa.ru/developers/payment-acceptance/scenario-extensions/recurring-payments/save-payment-method/save-during-payment) — вы проводите платеж и одновременно сохраняете способ оплаты, который выбрал пользователь. Вы можете проводить платеж с безусловным или условным сохранением способа оплаты:
  - [Безусловное сохранение способа оплаты](https://yookassa.ru/developers/payment-acceptance/scenario-extensions/recurring-payments/save-payment-method/save-during-payment#save-mandatory)— сохранение способа оплаты происходит по умолчанию, пользователь не может на это повлиять.
  - [Условное сохранение способа оплаты](https://yookassa.ru/developers/payment-acceptance/scenario-extensions/recurring-payments/save-payment-method/save-during-payment#save-optional)— сохранение способа оплаты происходит по желанию пользователя. Он сможет решить прямо на форме оплаты, хочет ли привязать платежное средство к вашему магазину.
- [Привязка на нулевую сумму](https://yookassa.ru/developers/payment-acceptance/scenario-extensions/recurring-payments/save-payment-method/save-without-payment/basics) — пользователь указывает данные платежного средства, ЮKassa проверяет, что их можно использовать для автоплатежей, и сохраняет этот способ оплаты без списания денег со счета пользователя.

В процессе привязки вы получаете идентификатор способа оплаты и сохраняете его, если привязка прошла успешно. Чтобы вы могли соотнести пользователя и его платежные данные, рекомендуется сохранять идентификатор способа оплаты в связке с идентификатором пользователя из вашей системы.

Если ваш магазин настроен для приема автоплатежей, то пользователю будет предлагаться [условное сохранение способа оплаты](https://yookassa.ru/developers/payment-acceptance/scenario-extensions/recurring-payments/save-payment-method/save-during-payment#save-optional) при каждом платеже из кошелька ЮMoney или с банковской карты. Чтобы провести платеж без сохранения способа оплаты, ознакомьтесь с [особенностями создания платежа](https://yookassa.ru/developers/payment-acceptance/scenario-extensions/recurring-payments/pay-without-saving).

Использование сохраненного способа оплаты

Вы можете использовать сохраненный способ оплаты для проведения [автоплатежей](https://yookassa.ru/developers/payment-acceptance/scenario-extensions/recurring-payments/pay-with-saved). Например, раз в месяц списываете 399 рублей в качестве абонентской платы за подписку на ваш сервис. Для продления подписки вы не просите пользователя ввести платежные данные и подтвердить платеж, а автоматически списываете деньги с его счета, используя идентификатор сохраненного способа оплаты.

Если вы сохраняли данные банковской карты, то такой способ оплаты можно использовать для проведения [выплат](https://yookassa.ru/developers/payouts/scenario-extensions/multipurpose-token).

Удаление сохраненного способа оплаты

Для ЮKassa автоплатеж — это создание платежа с сохраненным способом оплаты. Пока вы создаете такие платежи, ЮKassa будет их проводить.

Удаление идентификатора сохраненного способа оплаты равноценно отключению автоплатежа для пользователя. В ЮKassa нельзя удалить сохраненный способ оплаты или отменить его сохранение, вы можете сделать это только на своей стороне.

Если вы хотите отключить автоплатежи для определенного пользователя, вам нужно на своей стороне прекратить использовать сохраненный способ оплаты для создания платежей. Например, вы можете удалить идентификатор способа оплаты из вашей системы или пометить его как неактивный.

В некоторых случаях пользователь может самостоятельно отозвать свое разрешение на повторы платежей (например, через службу поддержки своего банка). В этих случаях платеж отменится или завершится ошибкой. Вы можете удалить идентификатор способа оплаты на своей стороне, если выяснилось, что пользователь отозвал разрешение на повторы платежей через свой банк.

Порядок интеграции

1. Составьте оферту для пользователей — с условиями настройки и отключения автоплатежей.
2. Сообщите вашему менеджеру ЮKassa, что планируете принимать автоплатежи.
3. Дождитесь, когда ваш магазин настроят для приема автоплатежей.
4. Продумайте и реализуйте на своей стороне следующую функциональность:
   - информирование пользователей об условиях использования автоплатежей;
   - настройка периодичности и суммы списаний;
   - отключение автоплатежей.
5. Реализуйте автоплатежи по инструкциям:
   - Сохранение способа оплаты через привязку [во время платежа](https://yookassa.ru/developers/payment-acceptance/scenario-extensions/recurring-payments/save-payment-method/save-during-payment) или [на нулевую сумму](https://yookassa.ru/developers/payment-acceptance/scenario-extensions/recurring-payments/save-payment-method/save-without-payment/basics). Вы можете использовать как один, так и оба вида сохранения способа оплаты.
   - [Проведение автоплатежа](https://yookassa.ru/developers/payment-acceptance/scenario-extensions/recurring-payments/pay-with-saved)
   - [Платеж без сохранения способа оплаты](https://yookassa.ru/developers/payment-acceptance/scenario-extensions/recurring-payments/pay-without-saving) (при необходимости)

Готово!

Теперь вы можете проводить автоплатежи.

Что почитать еще

[Тестирование автоплатежей](https://yookassa.ru/developers/payment-acceptance/testing-and-going-live/testing#test-recurrent)

[Универсальный токен для платежей и выплат](https://yookassa.ru/developers/payouts/scenario-extensions/multipurpose-token)

[Виджет ЮKassa](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/basics)

[Проведение платежей](https://yookassa.ru/developers/payment-acceptance/getting-started/payment-process)

[Способы оплаты](https://yookassa.ru/developers/payment-acceptance/getting-started/payment-methods)
