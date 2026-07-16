<!-- Источник: https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/other/electronic-certificate/basics -->
<!-- Полная копия статьи официальной документации ЮKassa, сохранено 2026-07-02 -->

# Электронный сертификат

Прием платежей по электронному сертификату, привязанному к карте «Мир».

Особенности

- Тип способа оплаты в API: `electronic_certificate`
- [Сценарий подтверждения](https://yookassa.ru/developers/payment-acceptance/getting-started/payment-process#user-confirmation): Redirect
- [Срок оплаты](https://yookassa.ru/developers/payment-acceptance/getting-started/payment-methods#payment-term): 1 час
- [Холдирование](https://yookassa.ru/developers/payment-acceptance/getting-started/payment-process#capture-and-cancel): нельзя платить в две стадии
- [Код в реестре](https://yookassa.ru/developers/payment-acceptance/after-the-payment/reports): EC
- [Возврат](https://yookassa.ru/developers/payment-acceptance/after-the-payment/refunds): да, полный и частичный, есть [особенности](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/other/electronic-certificate/basics#how-it-works-refunds)
- Срок возврата: на электронный сертификат — от 1 до 3 дней, есть [особенности](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/other/electronic-certificate/basics#how-it-works-refunds-processing-time); при доплате с банковской карты — от 0 до 3 дней (зависит от эмитента)
- [Автоплатежи](https://yookassa.ru/developers/payment-acceptance/scenario-extensions/recurring-payments/basics): нет
- [Лимиты](https://yookassa.ru/developers/payment-acceptance/getting-started/payment-methods#payment-limit): минимальный размер платежа — 1 рубль, максимальный — 350 000 рублей, максимальная сумма платежей в месяц — 700 000 рублей; лимиты можно увеличить через менеджера

Сценарии интеграции

Самостоятельная интеграция:

- [Оплата на готовой странице ЮKassa](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/other/electronic-certificate/ready-made-payment-form)
- [Оплата со сбором данных на вашей стороне](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/other/electronic-certificate/merchant-payment-form)

О способе оплаты

[Электронный сертификат](https://www.nspk.ru/ecert) — один из способов получения отдельных видов товаров, работ и услуг (ТРУ) для людей, которые получают социальную поддержку от государства. Например, по электронному сертификату можно приобрести технические средства реабилитации (ТСР).

Электронный сертификат — это запись в электронном реестре Государственной информационной системы электронных сертификатов (ГИС ЭС). Она содержит сведения о товарах, работах и услугах, которые можно приобрести по этому сертификату, предельную сумму и сроки действия сертификата и другие данные. Эта запись привязывается к карте «Мир» любого российского банка.

По электронному сертификату можно самостоятельно приобрести товары или оплатить часть их стоимости в магазинах. Потратить деньги можно только на то, что указано в сертификате.

При проведении платежей и возвратов использование сертификата предварительно одобряется во Фронт-офисе Электронных Сертификатов Национальной системы платежных карт (ФЭС НСПК).

Как это работает

- [Подготовка](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/other/electronic-certificate/basics#how-it-works-preparations)
- [Проведение платежа](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/other/electronic-certificate/basics#how-it-works-payments)
- [Проведение возврата](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/other/electronic-certificate/basics#how-it-works-refunds)
- [Отправка чеков в налоговую](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/other/electronic-certificate/basics#how-it-works-receipts)

Подготовка

Вы в своей системе определяете перечень товаров (ТРУ), которые можно оплатить по электронному сертификату. Каждому товару нужно [присвоить специальный код](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/other/electronic-certificate/basics#payments-preparations-tru-code) (полный код товара, согласованный с [перечнем ТРУ](https://esnsi.gosuslugi.ru/classifiers/10616/data?pg=1&p=1)).

Проведение платежа

Пользователь при покупке формирует корзину заказа. В ней могут быть товары, которые можно оплатить по сертификату, и другие товары, которые нужно оплатить картой. Вы формируете корзину покупки (в терминах ФЭС НСПК) — выбираете из заказа только те товары, которые можно оплатить по сертификату.

![Формирование корзины покупки](https://static.yoomoney.ru/docops-static/images/developers-payments-concept-schema-electronic-certificate-payment-basket-preparation.image.ru.f5cd631b.svg)

Формирование корзины покупки

При оплате пользователь указывает банковскую карту «Мир», к которой привязан сертификат. Карту и состав корзины покупки нужно передать в ФЭС НСПК. Кто это делает — ЮKassa или вы — зависит от вашего [варианта интеграции](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/other/electronic-certificate/basics#payment-method-overview-activation-choose-integration-option) с ЮKassa.

ФЭС НСПК одобряет корзину — отмечает, какие товары и на какую сумму можно компенсировать по сертификату.

![Одобрение корзины в ФЭС НСПК](https://static.yoomoney.ru/docops-static/images/developers-payments-concept-schema-electronic-certificate-payment-basket-approval.image.ru.6d255474.svg)

Одобрение корзины в ФЭС НСПК

После этого ЮKassa проводит платеж: одобренную сумму списывает с сертификата, а оставшуюся — с банковской карты.

![Оплата покупки](https://static.yoomoney.ru/docops-static/images/developers-payments-concept-schema-electronic-certificate-payment-basket-process-payment.image.ru.6ba05d77.svg)

Оплата покупки

Проведение возврата

Доступны полные и частичные возвраты. Вернуть можно как товары, оплата которых была по электронному сертификату, так и товары с оплатой по карте.

Особенности возвратов

- Если оплата товаров была по сертификату, вернуть деньги можно только на него.
- Если оплата товаров была частично по сертификату, частично по банковской карте, то сначала деньги возвращаются на сертификат, и если всё прошло успешно, то оставшаяся часть суммы возвращается на карту. Если при возврате на сертификат что-то пошло не так, вся операция отменяется, нужно повторять заново.
- Если возвращаются те товары из корзины, которые оплачивались банковской картой, то допускается сделать возврат на ту же карту, но на сумму не больше суммы доплаты. Иначе возврат не пройдет.

То, что списали с электронного сертификата, можно вернуть только на сертификат. Любые другие способы нарушают законодательство РФ.

![Особенности возвратов](https://static.yoomoney.ru/docops-static/images/developers-payments-concept-schema-electronic-certificate-refund.image.ru.7b89f14a.svg)

Особенности возвратов

Срок возврата

Срок возврата денег на электронный сертификат зависит от ГИС ЭС: сертификат снова станет активным после обработки операции в системе. В среднем эта процедура занимает от одного до трех дней. Если деньги не вернулись за это время, пользователю нужно обратиться в тот орган, который выдал электронный сертификат.

Если была оплата с банковской карты, то сроки фактического зачисления денег зависят от эмитента. Обычно деньги возвращаются в течение трех дней.

Отправка чеков в налоговую

При оплате по электронным сертификатам данные сформированных чеков нужно передавать не только в налоговую, но и в НСПК. Это касается всех чеков: чеков прихода, чеков возврата прихода, чеков коррекции и т.д.

Как передать чек в НСПК

Ваши действия зависят от того, как вы формируете чеки — [через ЮKassa](https://yookassa.ru/developers/payment-acceptance/receipts/basics) или самостоятельно:

- Если вы передаете данные для чеков через ЮKassa, они отправятся в НСПК автоматически. Убедитесь в [личном кабинете ЮKassa](https://yookassa.ru/my), что чек доставлен в НСПК. Если что-то пошло не так, передайте данные повторно в личном кабинете.
- Если вы отправляете данные для чеков самостоятельно (не через ЮKassa), подайте данные о сформированных чеках в [личном кабинете ЮKassa](https://yookassa.ru/my). Убедитесь, что чек доставлен в НСПК. Если что-то пошло не так, передайте данные повторно.

[Подробнее об отправке чеков в НСПК](https://yookassa.ru/docs/support/payments/tax-sync/mir-certificates)

Подать данные о чеке и узнать статус доставки чека в НСПК можно только в [личном кабинете ЮKassa](https://yookassa.ru/my) в истории платежей.

![Отправка чеков в НСПК](https://static.yoomoney.ru/docops-static/images/developers-payments-concept-schema-electronic-certificate-receipts.image.ru.8301172d.svg)

Отправка чеков в НСПК

Подключение способа оплаты

Чтобы принимать оплату по электронным сертификатам, вам нужно зарегистрироваться в ГИС ЭС и личном кабинете (ЛК) ФЭС НСПК. Подробные актуальные инструкции — на [сайте НСПК](https://www.nspk.ru/cards-mir/certificates).

Шаг 1. Проверьте, что вы можете подключить этот способ оплаты

- Вы резидент РФ — российская компания, ИП.
- Вы используете [обычные платежи](https://yookassa.ru/developers/payment-acceptance/overview) или [партнерскую программу](https://yookassa.ru/developers/solutions-for-platforms/partners-api/basics).
- Вы продаете то, что можно оплатить по электронному сертификату (это есть в [Перечне отдельных видов товаров, работ, услуг, приобретаемых с использованием электронного сертификата](https://esnsi.gosuslugi.ru/classifiers/10616/data?pg=1&p=1)).

Шаг 2. Выберите вариант интеграции с ЮKassa

Выберите подходящий вам вариант интеграции:

- [Оплата на готовой странице ЮKassa](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/other/electronic-certificate/ready-made-payment-form)
- [Оплата со сбором данных на вашей стороне](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/other/electronic-certificate/merchant-payment-form) (на странице вашего сайта)

Шаг 3. Подготовьтесь к интеграции

1. [Подготовьте данные о товарах](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/other/electronic-certificate/basics#payments-preparations), которые можно оплачивать по электронному сертификату (название, код в вашей системе, полный код по Перечню ТРУ).
2. Если выбрали [оплату со сбором данных на вашей стороне](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/other/electronic-certificate/merchant-payment-form), заполните [Лист самооценки SAQ D](https://docs-prv.pcisecuritystandards.org/SAQ%20(Assessment)/SAQ/PCI-DSS-v4-0-SAQ-D-Merchant-r1.pdf) (PCI DSS).

Шаг 4. Зарегистрируйтесь в ГИС ЭС

Зарегистрируйтесь в [Подсистеме обеспечения информационной безопасности Казначейства России](https://ecert.login.roskazna.ru/). Добавьте сотрудников, наделите их необходимыми ролями и полномочиями. Добавьте ваше предприятие и список товаров для оплаты по сертификату. Отправьте на активацию в ЛК ФЭС НСПК.

[Подробнее в инструкциях на сайте НСПК](https://www.nspk.ru/cards-mir/certificates)

Шаг 5. Зарегистрируйтесь в ЛК ФЭС НСПК

Ссылка для регистрации в ЛК ФЭС НСПК придет на почту после регистрации в ГИС ЭС.

[Подробнее в инструкциях на сайте НСПК](https://www.nspk.ru/cards-mir/certificates)

Шаг 6. Выберите вендора и получите данные для интеграции

В ЛК ФЭС НСПК добавьте кассу для вашего предприятия. [Подробнее в инструкциях на сайте НСПК](https://www.nspk.ru/cards-mir/certificates)

При добавлении кассы выберите вендора:

- Для [оплаты на готовой странице ЮKassa](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/other/electronic-certificate/ready-made-payment-form) выберите ЮMoney (ООО НКО «ЮМани»).
- Для [оплаты со сбором данных на вашей стороне](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/other/electronic-certificate/merchant-payment-form) вендор может быть любым.

Получите ID кассы, MAC KEY и API KEY.

Шаг 7. Проинтегрируйтесь с ЮKassa

1. [Зарегистрируйтесь в ЮKassa](https://yookassa.ru/my) (при необходимости).
2. Сообщите менеджеру ЮKassa, что хотите принимать оплату по электронным сертификатам.
3. Если выбрали [оплату на готовой странице ЮKassa](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/other/electronic-certificate/ready-made-payment-form), передайте менеджеру ID кассы, MAC KEY и API KEY, которые вы получили в ЛК ФЭС НСПК.
4. Проинтегрируйтесь по инструкциям в зависимости от вашего вариант интеграции с ЮKassa:
   - [Оплата на готовой странице ЮKassa](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/other/electronic-certificate/ready-made-payment-form)
   - [Оплата со сбором данных на вашей стороне](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/other/electronic-certificate/merchant-payment-form)

Шаг 8. Активируйте ваше предприятие в ГИС ЭС

В ГИС ЭС активируйте ваше предприятие. [Подробнее в инструкциях на сайте НСПК](https://www.nspk.ru/cards-mir/certificates)

Готово! Можно принимать платежи от реальных пользователей.

Подготовка данных о товарах

При проведении платежей и возвратов необходимо одобрять в ФЭС НСПК использование электронного сертификата и возврат на него. Для этого нужны определенные сведения о товаре: полный код товара по Перечню ТРУ (код ТРУ), название и код товара в вашей системе.

Когда и как нужно передавать эти данные:

- Для [оплаты на готовой странице ЮKassa](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/other/electronic-certificate/ready-made-payment-form) — в объекте `articles` в запросах к ЮKassa на создание платежа и на создание возврата.
- Для [оплаты со сбором данных на вашей стороне](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/other/electronic-certificate/merchant-payment-form) — в запросах к ФЭС НСПК на предварительное одобрение использование сертификата и на предварительное одобрение возврата.

Полный код товара по Перечню ТРУ (код ТРУ)

Полный код товара нужен для одобрения платежа или возврата в ФЭС НСПК. Код товара состоит из кода вида ТРУ, кода производителя, кода модели и кода страны производителя.

![Полный код товара по Перечню ТРУ](https://static.yoomoney.ru/docops-static/images/developers-payments-concept-schema-electronic-certificates-tru-code.image.ru.f4afc9bb.svg)

Полный код товара по Перечню ТРУ

Чтобы сформировать код для ТРУ, изучите [Каталог технических средств реабилитации](https://ktsr.sfr.gov.ru/ru-RU). Дальнейшие действия зависят от того, есть в каталоге нужный товар или его нет.

В каталоге есть нужный товар

Скопируйте код ТРУ и приведите его к формату: `NNNNNNNNN.NNNNNNNNNYYYYMMMMZZZ`.

Пример:

- код из каталога: `329921120.060010102.0008.0001.643`
- код для проведения платежа (остается только первая точка): `329921120.06001010200080001643`

Готово! Используйте этот код при проведении платежей и возвратов.

В каталоге нет нужного товара

Сформируйте код самостоятельно. Для этого:

**Шаг 1.** Найдите товар в [Перечне отдельных видов товаров, работ, услуг, приобретаемых с использованием электронного сертификата](https://esnsi.gosuslugi.ru/classifiers/10616/data?pg=1&p=1)

**Шаг 2.** Скопируйте код вида ТРУ из Перечня.

Пример: `329921120.060010102`

**Шаг 3.** Добавьте код производителя в формате `YYYY`. Если неизвестен, добавьте ноли: `0000`.

Примеры:

- Код известен: `329921120.0600101020008`
- Неизвестен: `329921120.0600101020000`

**Шаг 4.** Добавьте код модели в формате `MMMM`. Если неизвестен, добавьте ноли: `0000`.

Примеры:

- Код известен: `329921120.06001010200080001`
- Неизвестен: `329921120.06001010200000000`

**Шаг 5.** Добавьте цифровой код страны производителя по Общероссийскому классификатор стран мира (ОКСМ, [OK (MK (ИСО 3166) 004-97) 025—2001](http://docs.cntd.ru/document/842501280)) в формате `ZZZ`. Если неизвестен, добавьте ноли: `000`.

Примеры:

- Код известен: `329921120.06001010200080001643`
- Неизвестен: `329921120.06001010200000000000`

Готово! Используйте этот код при проведении платежей и возвратов.

Код товара в вашей системе

Этот код товара нужен, чтобы одобрить платеж или возврат в ФЭС НСПК. Требования к формату приведены в [Справочнике API](https://yookassa.ru/developers/api#create_payment_payment_method_data_electronic_certificate_articles_article_code).

Название товара в вашей системе

Если для оплаты используете [готовую страницу ЮKassa](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/other/electronic-certificate/ready-made-payment-form), это название отобразится на платежной форме при проведении платежа. Требования к формату приведены в [Справочнике API](https://yookassa.ru/developers/api#create_payment_payment_method_data_electronic_certificate_articles_article_name).

Что почитать еще

[Информация о проекте на сайте НСПК](https://www.nspk.ru/ecert)

[Оплата на готовой странице ЮKassa](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/other/electronic-certificate/ready-made-payment-form)

[Оплата со сбором данных на вашей стороне](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/other/electronic-certificate/merchant-payment-form)

[Как отправить в НСПК данные чека](https://yookassa.ru/docs/support/payments/tax-sync/mir-certificates)

[Перечень товаров с оплатой по электронному сертификату](https://esnsi.gosuslugi.ru/classifiers/10616/data?pg=1&p=1)
