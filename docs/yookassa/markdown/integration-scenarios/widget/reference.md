<!-- Источник: https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/reference -->
<!-- Полная копия статьи официальной документации ЮKassa, сохранено 2026-07-02 -->

# Справочник параметров, методов и кодов ошибок

В этом справочнике описаны:

- [Параметры](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/reference#initialization-parameters), которые передаются при инициализации виджета;
- [Ошибки](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/reference#errors), связанные с инициализацией виджета;
- [Методы виджета](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/reference#methods);
- [События виджета](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/reference#widget-events).

Описание параметров для инициализации виджета

Описание параметров, которые необходимо передать в экземпляр класса `YooMoneyCheckoutWidget` на [странице оплаты](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/integration#payment-page-initialize-and-render) для инициализации виджета.

| Параметр | Тип | Обязательность | Описание |
| --- | --- | --- | --- |
| confirmation\_token | string | Обязательный | Токен ЮKassa для инициализации виджета. Чтобы получить токен, нужно [создать платеж](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/integration#payment-process-create-payment) |
| return\_url | string | Необязательный | Адрес страницы, на которую пользователь вернется после завершения оплаты. Адрес должен быть абсолютным (с указанием протокола и домена сайта). Пример: `https://example.com/return_url`.  Если адрес страницы не передан, необходимо [обработать события процесса оплаты](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/additional-settings/behaviour#payment-events) |
| error\_callback | (error) => void | Обязательный | Callback-функция, которая принимает [код ошибки инициализации](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/reference#errors) |
| customization | object | Необязательный | Настройка платежной формы. Сейчас можно настроить [способ отображения платежной формы](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/additional-settings/modal-window), [цветовую схему](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/additional-settings/design#color) и [отображение способов оплаты](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/additional-settings/separate-payment-methods). |
| modal | boolean | Необязательный | Передается в `customization`.  Настройка способа отображения платежной формы. Возможные значения:   - `true` — платежная форма отображается во [всплывающем окне](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/additional-settings/modal-window); - `false` — платежную форму нужно размещать на [странице оплаты](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/integration#payment-page-initialize-and-render). |
| colors | object | Необязательный | Передается в `customization`.  [Настройка цветовой схемы](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/additional-settings/design#color). В объекте передаются [цвета](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/reference#customize-color), которые нужно изменить в интерфейсе платежной формы. |
| payment\_methods | array | Необязательный | Передается в `customization`.  [Настройка отображения способов оплаты](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/additional-settings/separate-payment-methods). Возможные значения:   - `bank_card` — банковская карта; - `yoo_money` — ЮMoney (кошелек, привязанные карты и баллы лояльности); - `mir_pay` — Mir Pay; - `sber_loan` — «Покупки в кредит» от СберБанка; - `sberbank` — SberPay; - `sbp` — СБП (Система быстрых платежей); - `tinkoff_bank` — T-Pay.   Если хотите настраивать отображение способов оплаты, напишите вашему менеджеру ЮKassa. |

Описание параметров для настройки цветовой схемы

Описание всех параметров объекта `colors`, которые можно использовать для [настройки цветовой схемы](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/additional-settings/design#color).

Для тех, кто настраивает [отображение способов оплаты](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/additional-settings/separate-payment-methods): если на платежной форме [виджета ЮKassa](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/basics) вы отображаете только Mir Pay или банковскую карту с Mir Pay, то вместо блока способа оплаты Mir Pay будет отображаться кнопка. Цветовую схему этой кнопки изменить нельзя — ее фон может быть только белым.

| Параметр | Тип | Описание | По умолчанию |
| --- | --- | --- | --- |
| control\_primary | string | Цвет фона акцентных элементов: кнопок **Заплатить**, **Закрыть**, выбранные переключатели, опции, граница выбранного текстового поля. Рекомендуется использовать яркий цвет, привлекающий внимание | `#FFCC00` (желтый) |
| control\_primary\_content | string | Цвет текста в кнопках **Заплатить** и **Закрыть**, содержимого акцентных переключателей и опций (например, выставленный флажок). Рекомендуется использовать цвет, контрастный к `control_primary`.  Если параметр не передан, цвет рассчитывается на основе `control_primary` | `#000000` (черный) или `#FFFFFF` (белый) — выбирается контрастный к `control_primary` |
| background | string | Цвет фона платежной формы, в том числе страницы успеха, цвет сообщений об ошибках и подсказок. Рекомендуется использовать цвет, близкий к цвету фона контейнера, в котором размещен виджет | `#FFFFFF` (белый) |
| text | string | Цвет всех текстов на платежной форме, кроме текстов в кнопках **Заплатить**, **Закрыть** и во всплывающих подсказках.  Если параметр не передан, цвет рассчитывается на основе `background` | Контрастный к `background` |
| border | string | Цвет границ и разделителей.  Если параметр не передан, цвет рассчитывается на основе `background` | Контрастный к `background` |
| control\_secondary | string | Цвет неакцентных элементов интерфейса.  Если параметр не передан, цвет рассчитывается на основе `background` | Контрастный к `background` |

Ошибки инициализации виджета

Если [инициализация виджета](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/integration#payment-process-widget-initialization) закончилась неудачей, ЮKassa передаст в callback-функцию код ошибки.

| Код ошибки | Описание |
| --- | --- |
| customization\_of\_payment\_methods\_not\_allowed | Этот магазин не может использовать параметр `payment_methods`. Если хотите [настраивать отображение способов оплаты](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/additional-settings/separate-payment-methods), напишите вашему менеджеру ЮKassa. |
| internal\_service\_error | При создании платежа возникла ошибка. Повторите [инициализацию виджета](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/integration#payment-process-widget-initialization) |
| invalid\_combination\_of\_payment\_methods | Недопустимое сочетание способов оплаты в `payment_methods` объекта `customization`. Одновременно можно передавать только `bank_card` и `mir_pay`, если вам разрешено [настраивать отображение способов оплаты](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/additional-settings/separate-payment-methods). |
| invalid\_payment\_methods | Некорректное значение `payment_methods` объекта `customization`. В массиве можно передать коды только тех [способов оплаты](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/additional-settings/separate-payment-methods), которые поддерживает виджет. Если отображаете несколько способов, их коды нужно перечислять через запятую. |
| invalid\_return\_url | Некорректный URL возврата. При [инициализации виджета](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/integration#payment-process-widget-initialization) передайте в `return_url` абсолютный URL страницы завершения оплаты, указав в нём протокол и домен вашего сайта |
| invalid\_token | Неверный токен. Для получения токена [создайте платеж](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/integration#payment-process-create-payment) |
| no\_payment\_methods\_to\_display | Отсутствуют способы оплаты для отображения: например, вы не можете принимать платежи выбранным способом или способ оплаты не поддерживает выбранные вами опции проведения платежа (оплату в [две стадии](https://yookassa.ru/developers/payment-acceptance/getting-started/payment-process#capture-and-cancel), [автоплатежи](https://yookassa.ru/developers/payment-acceptance/scenario-extensions/recurring-payments/basics)).  При [инициализации виджета](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/integration#payment-process-widget-initialization) передайте в `payment_methods` другой способ оплаты |
| token\_expired | Истек срок действия токена. Для получения нового токена [создайте платеж](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/integration#payment-process-create-payment) |
| token\_required | Токен не передан. При [инициализации виджета](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/integration#payment-process-widget-initialization) передайте `confirmation_token` |

Описание методов виджета

| Метод | Тип | Описание |
| --- | --- | --- |
| `render` | `(id?: string) => Promise<undefined>` | Отображение платежной формы. Исполнение Promise говорит о полной загрузке платежной формы. Promise можно не использовать.  Если вы [размещаете виджет на странице оплаты](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/integration#payment-page-initialize-and-render), в параметрах метода передайте значение атрибута `id` контейнера, в котором нужно разместить платежную форму. Если хотите [отображать виджет во всплывающем окне](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/additional-settings/modal-window), в параметрах метода ничего передавать не нужно. |
| `destroy` | `() => void` | Удаление инициализированного виджета. |
| `on` | `(event, callback) => void` | Регистрация [события виджета](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/reference#widget-events) и вызов callback-функции. |

Описание событий виджета

Виджет может уведомлять о следующих событиях:

| Событие | Описание |
| --- | --- |
| success | [Пользователь успешно завершил оплату](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/additional-settings/behaviour#payment-events-success-fail). Используется совместно с `fail` |
| fail | [Пользователь неудачно завершил оплату](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/additional-settings/behaviour#payment-events-success-fail). Используется совместно с `success` |
| complete | [Пользователь завершил оплату](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/additional-settings/behaviour#payment-events-complete). Событие наступает после успешной или неудачной оплаты. |
| modal\_close | [Пользователь закрыл всплывающее окно с платежной формой](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/additional-settings/behaviour#payment-modal-events). Для тех, кто [отображает виджет во всплывающем окне](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/additional-settings/modal-window). |

Что почитать еще

[Справочник API](https://yookassa.ru/developers/api)

[Интеграция виджета](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/integration)

[Типовые сценарии интеграции виджета](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/scenarios)
