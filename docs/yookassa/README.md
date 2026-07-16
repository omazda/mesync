# Документация ЮKassa — приём платежей (локальная копия)

Полная копия 50 страниц раздела «Приём платежей» официальной документации
**ЮKassa** (`yookassa.ru/developers/payment-acceptance/…`), сохранена **2026-07-02**;
плюс страница «Входящие уведомления» раздела «Работа с API»
(`using-api/webhooks`, добавлена **2026-07-04**).
Копия без потери смысла и кода: текст, таблицы и ВСЕ варианты примеров
(cURL / PHP / Python / JavaScript / HTML / JSON / XML / Swift / Java — включая
табы, которые сайт рендерит только на клиенте; они восстановлены из Markdoc-AST
страниц, см. `tools/`). Всего 309 типизированных блоков кода.

При изменении платёжной интеграции сверяйтесь с точными endpoint, параметрами и ограничениями в этих файлах.

## Структура

```
docs/yookassa/
├── README.md        ← этот индекс
├── markdown/        ← читаемая документация (для сверки при разработке)
├── html/            ← исходный сырой HTML (полная копия страниц, Accept-Language: ru)
└── tools/           ← скрипты скачивания/конвертации (yk-urls.txt, yk_convert.py, yk_tabs.py)
```

## Содержание (`markdown/`)

### Начало работы (`getting-started/`)

| Файл | Что внутри |
| --- | --- |
| `quick-start.md` | **Быстрый старт**: аутентификация (shopId + секретный ключ), создание платежа, редирект на confirmation_url, проверка статуса |
| `payment-process.md` | **Процесс платежа**: жизненный цикл и статусы (`pending → waiting_for_capture → succeeded / canceled`), подтверждение (redirect/embedded/qr/external), capture/cancel, уведомления (webhooks) |
| `payment-methods.md` | Способы оплаты (карты, СБП, ЮMoney, SberPay, T-Pay и др.) и их особенности |
| `selecting-integration-scenario.md` | Выбор сценария интеграции: платёжная форма ЮKassa / виджет / своя форма (Checkout.js) / готовые модули |

### Сценарии интеграции (`integration-scenarios/`)

| Файл | Что внутри |
| --- | --- |
| `smart-payment.md` | **Умный платёж**: создание платежа с `confirmation.type=redirect`, готовая платёжная форма ЮKassa |
| `widget/basics.md` | **Виджет ЮKassa** — обзор: что умеет, как выглядит, требования |
| `widget/quick-start.md` | Быстрый старт виджета: платёж с `confirmation.type=embedded` → `confirmation_token` → `YooMoneyCheckoutWidget` |
| `widget/scenarios.md` | Типовые сценарии: оплата на странице / во всплывающем окне, обработка успеха и ошибок |
| `widget/integration.md` | Интеграция виджета по шагам: подключение скрипта, инициализация, render, события, обработка ошибок |
| `widget/additional-settings/behaviour.md` | Обработка событий виджета (`on('success'/'fail'/'complete'/'modal_close')`) |
| `widget/additional-settings/design.md` | Внешний вид платёжной формы: `customization.colors`, тёмная тема, язык интерфейса |
| `widget/additional-settings/modal-window.md` | Виджет во всплывающем окне (`customization.modal`) |
| `widget/additional-settings/separate-payment-methods.md` | Отображение отдельных способов оплаты (`payment_methods`, кнопки способов) |
| `widget/additional-settings/save-payments.md` | Запоминание банковских карт пользователя (`save_payment_method`, привязки) |
| `widget/additional-settings/recurring-payments.md` | **Автоплатежи**: сохранение способа оплаты, `payment_method_id`, повторные списания без пользователя |
| `widget/reference.md` | **Справочник виджета**: все параметры инициализации, методы (`render`, `on`, `off`, `destroy`), коды ошибок |
| `checkout-js/basics.md` | **Checkout.js** — обзор: своя форма + токенизация карточных данных |
| `checkout-js/library-implementation.md` | Использование Checkout.js: подключение, `YooMoneyCheckout(shopId)`, `tokenize()`, обработка ошибок валидации |
| `checkout-js/payments-with-tokens.md` | Проведение платежа с `payment_token`, 3-D Secure (`confirmation.type=redirect`) |

### Мобильные SDK (`integration-scenarios/mobile-sdks/`)

| Файл | Что внутри |
| --- | --- |
| `basics.md` | **Мобильные SDK** — обзор: токенизация в приложении, секции iOS SDK / Android SDK, поддерживаемые способы оплаты, требования к версиям ОС |
| `ios-sdk.md` | Использование iOS SDK: порядок подключения, ключ API, возможности (кода на странице нет — SDK и инструкции в репозитории `yookassa-payments-swift`) |
| `android-sdk.md` | Использование Android SDK: порядок подключения, возможности (SDK и инструкции — в репозитории `yookassa-android-sdk`) |
| `payments-with-tokens.md` | Проведение платежа с `payment_token`, полученным из мобильного SDK (+ 3-D Secure) |

### Самостоятельная интеграция по способам оплаты (`integration-scenarios/manual-integration/`)

| Файл | Что внутри |
| --- | --- |
| `basics.md` | **Самостоятельная интеграция** — обзор: свой UI выбора способа оплаты, `payment_method_data`, сценарии подтверждения по способам |
| `bank-card.md` | Банковская карта: платёж со своей формой, 3-D Secure, оплата в один клик (сохранённая карта) |
| `mir-pay.md` | Mir Pay |
| `sberpay.md` | SberPay: web/mobile сценарии, диплинки в приложения СберБанка (примеры Swift/XML/Java для обработки редиректов) |
| `yoo-money.md` | ЮMoney (кошелёк) |
| `other/alfa-pay.md` | Alfa Pay |
| `other/tinkoff-bank.md` | T-Pay |
| `other/sbp.md` | Система быстрых платежей (СБП) |
| `other/sber-loan.md` | «Покупки в кредит» от СберБанка |
| `other/sber-bnpl.md` | «Плати частями» |
| `other/b2b-sberbank.md` | СберБанк Бизнес Онлайн (B2B-платежи) |
| `other/electronic-certificate/basics.md` | Электронный сертификат — основы (НСПК, корзина `articles`) |
| `other/electronic-certificate/ready-made-payment-form.md` | Электронный сертификат: оплата на готовой странице ЮKassa |
| `other/electronic-certificate/merchant-payment-form.md` | Электронный сертификат: оплата со сбором данных на стороне магазина |
| `other/mobile-balance.md` | Баланс мобильного телефона |
| `other/cash.md` | Наличные (терминалы) |

### Работа с API (`using-api/`)

| Файл | Что внутри |
| --- | --- |
| `webhooks.md` | **Входящие уведомления (webhooks)**: доступные события по платёжным решениям (`payment.*`, `refund.succeeded`, `payout.*`, `deal.closed`, `payment_method.active`), настройка (Basic Auth → личный кабинет, OAuth → API), формат тела `{type, event, object}`, требования к URL (HTTPS, порт 443/8443, TLS ≥ 1.2, сертификат любой), подтверждение ответом HTTP 200 (иначе повторы доставки 24 часа), проверка подлинности (по статусу объекта из API или по IP: 185.71.76.0/27, 185.71.77.0/27, 77.75.153.0/25, 77.75.156.11, 77.75.156.35, 77.75.154.128/25, 2a02:5180::/32) |

### Расширения сценариев (`scenario-extensions/`)

**Автоплатежи (`recurring-payments/`)** — рекуррентные списания без участия пользователя:

| Файл | Что внутри |
| --- | --- |
| `basics.md` | **Автоплатежи** — обзор: привязка платёжного средства, `payment_method_id`, требования и ограничения по способам оплаты |
| `save-payment-method/save-during-payment.md` | Привязка во время платежа: `save_payment_method=true`, сохранённое `payment_method`, статусы привязки |
| `save-payment-method/save-without-payment/basics.md` | Привязка на нулевую сумму — обзор (без списания денег) |
| `save-payment-method/save-without-payment/bank-card.md` | Привязка банковской карты на нулевую сумму |
| `save-payment-method/save-without-payment/sbp.md` | Привязка счёта СБП на нулевую сумму |
| `pay-with-saved.md` | **Проведение автоплатежа**: платёж с `payment_method_id` сохранённого средства |

**Выставление счетов (`invoices/`)** — счета на оплату (объект `invoice`, `POST /v3/invoices`):

| Файл | Что внутри |
| --- | --- |
| `basics.md` | **Выставление счетов** — обзор: что такое счёт (страница оплаты со сроком до 30 дней), как работает, способы оплаты |
| `payments.md` | Приём платежа по выставленному счету: создание счёта (`POST /v3/invoices`, `delivery_method`, корзина `cart`), оплата, статусы, уведомления |
| `refunds.md` | Возврат платежа по выставленному счету |
| `recurring-payments.md` | Автоплатежи по выставленному счету (счёт + сохранение способа оплаты) |
| `receipts.md` | Отправка чеков по выставленным счетам (54-ФЗ) |

## Ключевое для интеграции

- **API**: `https://api.yookassa.ru/v3/…` (главная сущность — платёж: `POST /v3/payments`).
- **Аутентификация**: HTTP Basic — `<Идентификатор магазина>:<Секретный ключ>` из личного кабинета.
- **Идемпотентность**: заголовок `Idempotence-Key` обязателен для POST-запросов.
- **Сценарии подтверждения**: `redirect` (готовая форма/Умный платёж) и `embedded` (виджет, нужен `confirmation_token`).
- **Виджет**: скрипт `https://yookassa.ru/checkout-widget/v1/checkout-widget.js`, класс `YooMoneyCheckoutWidget`.
- **Checkout.js**: скрипт `https://static.yoomoney.ru/checkout-js/v1/checkout.js`, `YooMoneyCheckout(shopId).tokenize(...)` → `payment_token`.
- **Итог платежа** проверять по статусу платежа (уведомления/запрос статуса), а не по возврату пользователя на `return_url`.

## Как обновлять

1. `tools/yk-urls.txt` — список страниц. Скачивание: `curl -sL -H "Accept-Language: ru-RU,ru;q=0.9" -A "Mozilla/5.0 …" <url>` → `html/`.
2. `tools/yk_convert.py` — HTML→Markdown (`beautifulsoup4` + `markdownify`, контент из `<article>`, крупные SVG → `assets/`).
3. `tools/yk_tabs.py` — восстановление всех табов примеров кода (PHP/Python/…) из Markdoc-AST в `window.__data__` и проставление языков fence-блокам.

Скрипты рассчитаны на venv с `beautifulsoup4` и `markdownify` (проектный `.venv` не трогать).
