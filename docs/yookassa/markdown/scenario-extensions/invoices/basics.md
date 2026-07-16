<!-- Источник: https://yookassa.ru/developers/payment-acceptance/scenario-extensions/invoices/basics -->
<!-- Полная копия статьи официальной документации ЮKassa, сохранено 2026-07-02 -->

# Выставление счетов

В ЮKassa можно выставлять счета на оплату. Счет — это страница ЮKassa, на которой пользователь увидит описание заказа и сможет заплатить в любой удобный момент в течение заданного вами срока.

С помощью выставления счетов от ЮKassa вы можете автоматизировать прием платежей даже без сайта, увеличить срок оплаты для пользователя до 30 дней (вместо 1 часа) и принимать платежи популярными способами оплаты: кошельком ЮMoney, банковской картой, SberPay, СБП и другими.

В этой статье описано выставление счетов по API.

[Подробнее о других способах выставления счетов](https://yookassa.ru/docs/support/payments/extra/invoicing)

Как это работает

Счет — это готовая страница с описанием заказа, который сделал пользователь. Для приема оплаты ЮKassa использует [Умный платеж](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/smart-payment): когда пользователь перейдет к оплате, ЮKassa автоматически создаст платеж и перенаправит пользователя на страницу оплаты. На платежной форме будут отображаться все способы оплаты, доступные вашему магазину.

Для приема платежа вам нужно только создать счет и передать пользователю ссылку: самостоятельно (любым удобным способом) или через ЮKassa (в смс или по электронной почте). Всё остальное сделает ЮKassa.

При оплате ЮKassa создаст [объект платежа](https://yookassa.ru/developers/api#payment_object). С ним можно выполнять все действия, которые можно делать с платежами: получать уведомления об изменении статуса платежа, запрашивать информацию о платеже, подтверждать платеж, делать возвраты и т.д.

Подробнее о выставлении счетов:

- [Процесс оплаты по выставленному счету](https://yookassa.ru/developers/payment-acceptance/scenario-extensions/invoices/basics#payment-process)
- [Доступные возможности](https://yookassa.ru/developers/payment-acceptance/scenario-extensions/invoices/basics#features)
- [Преимущества выставления счетов по API](https://yookassa.ru/developers/payment-acceptance/scenario-extensions/invoices/basics#advantages)
- [Использование счета](https://yookassa.ru/developers/payment-acceptance/scenario-extensions/invoices/basics#using-invoice)
  - [Прием платежа по счету](https://yookassa.ru/developers/payment-acceptance/scenario-extensions/invoices/basics#invoice-payment-acceptance)
  - [Срок действия счета](https://yookassa.ru/developers/payment-acceptance/scenario-extensions/invoices/basics#invoice-lifetime)
  - [Способы доставки счета пользователю](https://yookassa.ru/developers/payment-acceptance/scenario-extensions/invoices/basics#send-invoice)
  - [Работа в личном кабинете](https://yookassa.ru/developers/payment-acceptance/scenario-extensions/invoices/basics#merchant-profile)
- [Порядок интеграции](https://yookassa.ru/developers/payment-acceptance/scenario-extensions/invoices/basics#integration)
- [Жизненный цикл счета](https://yookassa.ru/developers/payment-acceptance/scenario-extensions/invoices/basics#invoice-status)

Процесс оплаты по выставленному счету

Когда обсудите с пользователем детали заказа, создайте счет и передайте ссылку на него самостоятельно или через ЮKassa. Например, отправьте по электронной почте.

При переходе по ссылке пользователь попадет на страницу счета, где увидит его срок действия, а также корзину заказа и сумму к оплате.

![Пример страницы счета](https://static.yoomoney.ru/docops-static/images/developers_payments_scenario_extensions_invoices_basics_invoice.f9a2ba96.png)

Пример страницы счета

Когда пользователь перейдет к оплате, ЮKassa создаст платеж и перенаправит пользователя на платежную форму, где он выберет подходящий способ оплаты, введет данные и подтвердит платеж. [Подробнее о доступных способах оплаты](https://yookassa.ru/developers/payment-acceptance/getting-started/payment-methods)

![Пример платежной формы](https://static.yoomoney.ru/docops-static/images/developers-payments-smart-payment-desktop.image.ru.3f59938a.svg)

Пример платежной формы

Если по каким-то причинам платеж не пройдет и перейдет в статус `canceled`, пользователь сможет повторять попытку оплаты, пока срок действия счета не истечет. Для этого пользователю нужно вернуться на страницу счета и заново перейти к оплате — каждый раз ЮKassa будет создавать новый платеж.

Счет считается оплаченным, когда по нему есть успешный платеж (в статусе `succeeded`). Вы можете в любой момент проверить статус счета, отправляя запросы на [получение информации о счете](https://yookassa.ru/developers/api#get_invoice).

Возможности

Выставляя счета по API, вы можете:

- автоматизировать оплату по счетам;
- создавать счета со сроком оплаты до 30 дней;
- показывать пользователю корзину заказа прямо на странице ЮKassa;
- отправлять счета самостоятельно (любым удобным для вас способом) или через ЮKassa (в смс или по электронной почте);
- принимать платежи всеми [способами](https://yookassa.ru/developers/payment-acceptance/getting-started/payment-methods), кроме оплаты Электронным сертификатом и через СберБанк Бизнес Онлайн;
- принимать платежи в [две стадии](https://yookassa.ru/developers/payment-acceptance/getting-started/payment-process#capture-and-cancel) и списывать оплату полностью или частично;
- делать возвраты по [API](https://yookassa.ru/developers/payment-acceptance/scenario-extensions/invoices/refunds) или из [личного кабинета](https://yookassa.ru/docs/support/merchant/payments/refunds#from-lk);
- сохранять способы оплаты для проведения [автоплатежей](https://yookassa.ru/developers/payment-acceptance/scenario-extensions/invoices/recurring-payments);
- передавать данные для чека в [онлайн-кассу](https://yookassa.ru/developers/payment-acceptance/receipts/54fz/basics) (для компаний и ИП);
- получать информацию о [счете](https://yookassa.ru/developers/api#get_invoice) и [платеже](https://yookassa.ru/developers/api#get_payment) по API.

Преимущества выставления счетов по API

Выставить счет можно не только по API, но и в [личном кабинете ЮKassa](https://yookassa.ru/docs/support/merchant/invoices-to-clients/invoicing) или [Telegram-боте](https://yookassa.ru/docs/support/payments/onboarding/integration/cms-module/telegram-bot). Тогда вам не потребуется писать код: вы укажете необходимые настройки, получите ссылку на страницу счета и сможете отправить ее пользователю — самостоятельно или через ЮKassa.

Тем не менее, у выставления счетов по API есть ряд преимуществ:

- Выставляя счета по API, вы можете автоматизировать обработку информации о статусе счета. Это недоступно для счетов, выставленных из личного кабинета или через Telegram-бота.
- У всех платежных решений API ЮKassa один и тот же [формат взаимодействия](https://yookassa.ru/developers/using-api/interaction-format). Если вы захотите принимать [платежи на сайте](https://yookassa.ru/developers/payment-acceptance/getting-started/selecting-integration-scenario), [делать выплаты](https://yookassa.ru/developers/payouts/overview) по API ЮKassa или использовать другие платежные решения, вам нужно будет только подписать договор и подключить новые возможности по соответствующим инструкциям.
- API поддерживает те возможности, которых нет в личном кабинете. Например, автоплатежи.
- Если вы используете [решения ЮKassa для работы по 54-ФЗ](https://yookassa.ru/developers/payment-acceptance/receipts/54fz/basics), то выставляя счета по API сможете передавать больше данных для чека, чем в личном кабинете. Например, код маркировки или меру количества предмета расчета.

Использование счета

Прием платежа по счету

Чтобы принять платеж, вам нужно создать счет и отправить пользователю ссылку на него. Когда на странице счета пользователь перейдет к оплате — ЮKassa автоматически создаст платеж и отобразит платежную форму. На ней пользователь увидит все способы оплаты, подключенные в вашем магазине и доступные для этого платежа. [Подробнее об отображении способов оплаты](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/smart-payment#specifics)

Счет одноразовый — с ним может быть связан только один успешный платеж. В контексте выставления счетов это значит, что платеж по счету перешел в статус `succeeded` (при оплате в одну стадию) или в статус `waiting_for_capture` (при оплате в две стадии). Если такой платеж уже есть, в объекте счета появится объект `payment_details` с идентификатором платежа. После этого оплатить счет еще раз не получится — нужно создавать новый счет.

Счет считается оплаченным, когда платеж по нему переходит в статус `succeeded`, т.к. для платежа это финальный статус. Если платеж находится в статусе `wating_for_capture`, то он может перейти как в статус `succeeded`, так и в статус `canceled`. При отмене платежа на этой стадии счет тоже отменится. [Подробнее о статусах счета](https://yookassa.ru/developers/payment-acceptance/scenario-extensions/invoices/basics#invoice-status)

Срок действия счета

Срок действия счета вы можете регулировать самостоятельно при создании счета. Счет может действовать максимум 30 дней.

Когда указанный срок пройдет, счет перейдет в статус `canceled` и его оплатить не получится.

Способы доставки счета пользователю

Вы можете доставить пользователю счет автоматически через ЮKassa (в смс или по электронной почте) или самостоятельно — для этого скопируйте и отправьте ссылку любым удобным способом.

| Способ доставки счета и код способа | Ответственный за доставку счета | Процесс доставки счета | Ограничения |
| --- | --- | --- | --- |
| **Самостоятельная доставка**  `self` | Вы | [При создании счета](https://yookassa.ru/developers/payment-acceptance/scenario-extensions/invoices/payments#payment-acceptance-self) вы не передаете контакты пользователя. ЮKassa формирует ссылку на счет, но не отправляет её пользователю.  Способ отправки ссылки вы выбираете самостоятельно. Например, вы можете отправить её в мессенджере, по электронной почте, с помощью сервисов для автоматических рассылок или показать на странице своего сайта, если он у вас есть. | Минимальная сумма платежа по счету — 1 рубль.  Максимум 100 счетов в минуту для одного магазина (`shopId`). |
| **Электронная почта**  `email` | ЮKassa | [При создании счета](https://yookassa.ru/developers/payment-acceptance/scenario-extensions/invoices/payments#payment-acceptance-email) вы передаете электронную почту пользователя. ЮKassa формирует ссылку на счет и отправляет её пользователю в письме. | Минимальная сумма платежа по счету — 1 рубль.  Максимум 100 счетов в минуту для одного магазина (`shopId`). |
| **Смс**  `sms` | ЮKassa | [При создании счета](https://yookassa.ru/developers/payment-acceptance/scenario-extensions/invoices/payments#payment-acceptance-sms) вы передаете номер телефона пользователя. ЮKassa формирует ссылку на счет и отправляет её пользователю в смс. | Минимальная сумма платежа по счету — 100 рублей.  Максимум 10 счетов в минуту для одного магазина (`shopId`). |

Работа в личном кабинете

Со счетами, выставленными по API, можно работать в личном кабинете. Вы найдете их в разделе [Счета клиентам](https://yookassa.ru/my/invoice).

Так можно посмотреть статус счета и детали: корзину заказа, идентификатор счета и другие данные. Если пользователь уже подтвердил платеж по выставленному счету, то платеж вы тоже увидите в деталях, а также сможете перейти в раздел **Платежи** за более подробной информацией о нём.

При необходимости в личном кабинете вы можете привязывать счета к [гибкому QR](https://yookassa.ru/docs/support/merchant/invoices-to-clients/configurable-qr) и использовать их, например, для приема платежей в офлайне.

Кроме того, если пользователь пока не подтвердил платеж, то в личном кабинете можно [отменить счет](https://yookassa.ru/docs/support/merchant/invoices-to-clients/invoicing#invoicing__cancel) — тогда оплатить его не получится.

Порядок интеграции

Чтобы начать выставлять счета:

1. Изучите [формат взаимодействия](https://yookassa.ru/developers/using-api/interaction-format) по API.
2. Если планируете использовать [автоплатежи](https://yookassa.ru/developers/payment-acceptance/scenario-extensions/invoices/recurring-payments), сообщите об этом вашему менеджеру ЮKassa.
3. Если планируете принимать платежи в [две стадии](https://yookassa.ru/developers/payment-acceptance/getting-started/payment-process#capture-and-cancel) или [автоплатежи](https://yookassa.ru/developers/payment-acceptance/scenario-extensions/invoices/recurring-payments), то проверьте, что в вашем магазине подключен как минимум один способ оплаты, который поддерживает нужную опцию. [Подробнее о способах оплаты](https://yookassa.ru/developers/payment-acceptance/getting-started/payment-methods)
4. При необходимости подпишитесь на [уведомления о платежах](https://yookassa.ru/developers/using-api/webhooks) от ЮKassa в личном кабинете
5. Реализуйте выставление счетов по инструкциям:
   - [Прием платежей](https://yookassa.ru/developers/payment-acceptance/scenario-extensions/invoices/payments)
   - [Проведение возвратов](https://yookassa.ru/developers/payment-acceptance/scenario-extensions/invoices/refunds)
   - [Автоплатежи](https://yookassa.ru/developers/payment-acceptance/scenario-extensions/invoices/recurring-payments)
   - [Отправка чеков](https://yookassa.ru/developers/payment-acceptance/scenario-extensions/invoices/receipts)
6. Протестируйте интеграцию: выставьте счет на небольшую сумму и проверьте все необходимые вам сценарии.

Готово! Можно выставлять счета реальным пользователям.

Жизненный цикл счета

Счет может находиться в статусе `pending`, `canceled` или `succeeded`. Статус счета зависит от того, что происходит с платежом.

**Как связаны статус счета и статус платежа**

| Статус счета | Пояснение к статусу счета | Действия пользователя и статус платежа |
| --- | --- | --- |
| pending | Статус `pending` означает, что счет создан и ожидает оплаты от пользователя или списания оплаты от вас (при проведении платежей в две стадии).  Из статуса pending счет может перейти в `succeeded`, или `canceled` (если что-то пошло не так). | - Пользователь еще не перешел к оплате, платеж не создан. - Пользователь перешел к оплате, но еще не подтвердил платеж. Платеж в статусе `pending`. - Пользователь подтвердил платеж, но что-то пошло не так (например, недостаточно средств на балансе). Платеж в статусе `canceled`, можно повторить попытку оплаты. |
| succeeded | Счет в статусе `succeeded` означает, что пользователь подтвердил платеж по счету и оплата прошла успешно.  Это финальный и неизменяемый статус для платежей в одну стадию. При проведении платежей в две стадии счет может перейти из статуса `succeeded` в статус `canceled`. | - Пользователь подтвердил платеж, и деньги списаны. Платеж в статусе `succeeded`. - Для платежей в [две стадии](https://yookassa.ru/developers/payment-acceptance/getting-started/payment-process#capture-and-cancel): пользователь подтвердил платеж, но вы еще не списали оплату. Платеж в статусе `waiting_for_capture`. - Для платежей в [две стадии](https://yookassa.ru/developers/payment-acceptance/getting-started/payment-process#capture-and-cancel): пользователь подтвердил платеж, и вы списали по нему оплату. Платеж был в статусе `waiting_for_capture` и перешел в статус `succeeded`. |
| canceled | Статус `canceled` означает, что счет отменен. Вы увидите этот статус, если:   - срок действия счета истек, а успешного платежа по счету не было; - вы отменили платеж в две стадии; - вы отменили счет в личном кабинете.   Это финальный и неизменяемый статус. | - Пользователь не переходил к оплате, а срок действия счета истек. Платеж не был создан. - Пользователь не успел перейти к оплате, вы отменили счет в личном кабинете. Платеж не был создан. - Для платежей в [две стадии](https://yookassa.ru/developers/payment-acceptance/getting-started/payment-process#capture-and-cancel): пользователь подтвердил платеж, но вы отменили его. Платеж был в статусе `waiting_for_capture`, но перешел в статус `canceled`. - Пользователь подтвердил платеж, но оплата прошла неуспешно. Платеж в статусе `canceled`, новой попытки оплаты не было. |

Чтобы узнать статус счета, периодически отправляйте запросы на [получение информации о счете](https://yookassa.ru/developers/api#get_invoice) или дождитесь [уведомления по платежу](https://yookassa.ru/developers/using-api/webhooks) от ЮKassa.

[Подробнее об отслеживании статуса счета](https://yookassa.ru/developers/payment-acceptance/scenario-extensions/invoices/payments#inform)

Что почитать еще

[Выставление счетов в личном кабинете и через Telegram](https://yookassa.ru/docs/support/payments/extra/invoicing)

[Основы работы с API](https://yookassa.ru/developers/using-api/interaction-format)

[Умный платеж](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/smart-payment)

[Основы проведения платежей](https://yookassa.ru/developers/payment-acceptance/getting-started/payment-process)
