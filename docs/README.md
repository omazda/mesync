# Документация проекта sync-bot

Локальная база официальной технической документации для интеграций **MAX ↔ Telegram**,
приёма платежей и ИИ-модерации.

## Структура

```
docs/
├── README.md                         ← этот индекс
├── yandex-market-digital.md             ← настройка автоматической выдачи цифровых кодов
├── telegram/
│   ├── markdown/                      ← читаемая документация (для сверки при разработке)
│   └── html/                          ← исходный сырой HTML (полная копия страниц)
├── max/
│   ├── README.md                      ← индекс документации MAX (все методы/объекты/гайды)
│   ├── markdown/                      ← читаемая документация MAX (docs-api / docs / ui / help)
│   └── html/                          ← исходный сырой HTML (полная копия страниц)
├── yookassa/
│   ├── README.md                      ← индекс документации ЮKassa (приём платежей)
│   ├── markdown/                      ← читаемая документация (50 страниц, все примеры кода)
│   ├── html/                          ← исходный сырой HTML (полная копия страниц)
│   └── tools/                         ← скрипты скачивания/конвертации
└── minimax/
    ├── README.md                      ← индекс документации MiniMax (ИИ для модерации) + ключевые факты
    └── markdown/                      ← читаемая документация (Anthropic-совместимый API, Token Plan, лимиты, ошибки)
```

## Официальная документация Telegram (`telegram/markdown/`)

| Файл | Что внутри | Источник |
| --- | --- | --- |
| `00-introduction.md` | Введение в ботов | core.telegram.org/bots |
| `01-faq.md` | FAQ: лимиты, медиа, апдейты | /bots/faq |
| `02-features.md` | Возможности: Privacy Mode, Rich Messages, Local API, клавиатуры | /bots/features |
| `03-tutorial.md` | Туториал «от BotFather до Hello World» | /bots/tutorial |
| `04-api-reference.md` | **Главный справочник Bot API** (все методы и объекты) | /bots/api |
| `05-api-changelog.md` | История изменений Bot API | /bots/api-changelog |
| `06-webhooks.md` | Полный гайд по вебхукам | /bots/webhooks |
| `07-inline.md` | Inline-режим | /bots/inline |
| `08-payments.md` | Платежи | /bots/payments |
| `09-payments-stars.md` | Платежи через Telegram Stars | /bots/payments-stars |
| `10-games.md` | Игровая платформа | /bots/games |
| `11-webapps-miniapps.md` | Telegram Mini Apps | /bots/webapps |
| `12-samples.md` | Примеры библиотек | /bots/samples |
| `blog-watch-apps-and-more-ru.md` | Блог-пост 11.06.2026: Rich Messages для ботов, часы и др. | telegram.org/blog/watch-apps-and-more/ru |

## Официальная документация MAX (`max/`)

Полная копия всех четырёх разделов `dev.max.ru` (108 страниц). Подробный индекс со всеми методами и объектами — в **[`max/README.md`](max/README.md)**.

| Раздел | Что внутри | Источник |
| --- | --- | --- |
| `max/markdown/docs-api.md` + `docs-api/` | **Главный справочник Bot API MAX**: обзор (форматирование, клавиатуры, вложения), 30 методов, 8 объектов | dev.max.ru/docs-api |
| `max/markdown/docs.md` + `docs/` | Гайды: создание чат-ботов (JS/Go/примеры), мини-приложения (WebApps, Bridge, валидация), каналы, подключение бизнес-профиля, юридическое | dev.max.ru/docs |
| `max/markdown/ui.md` + `ui/` | UI-кит для мини-приложений (35 компонентов + композиции) | dev.max.ru/ui |
| `max/markdown/help.md` + `help/` | Справка: чат-боты, мини-приложения, каналы, события, диплинки, интеграция | dev.max.ru/help |

Ключевое для интеграции: базовый URL Bot API — `https://platform-api.max.ru`; авторизация — заголовок `Authorization: <access_token>`; события — Webhook (`POST /subscriptions`) для production, Long Polling (`GET /updates`) для разработки.

## Официальная документация ЮKassa — приём платежей (`yookassa/`)

Полная копия 50 страниц раздела «Приём платежей» `yookassa.ru/developers/payment-acceptance` (быстрый старт, процесс платежа, способы оплаты, выбор сценария; Умный платёж; виджет — быстрый старт/сценарии/интеграция/все доп. настройки/справочник; Checkout.js; мобильные SDK iOS/Android; самостоятельная интеграция по способам оплаты: карта, Mir Pay, SberPay, ЮMoney, Alfa Pay, T-Pay, СБП, кредиты/рассрочка Сбера, B2B, электронный сертификат, баланс телефона, наличные; расширения сценариев: автоплатежи — привязка средства во время платежа/на нулевую сумму и списания по `payment_method_id`, выставление счетов — платежи/возвраты/автоплатежи/чеки). Все варианты примеров кода (cURL/PHP/Python/JavaScript/HTML/JSON/XML/Swift/Java, 309 блоков) сохранены. Подробный индекс — в **[`yookassa/README.md`](yookassa/README.md)**.

Ключевое для интеграции: API `https://api.yookassa.ru/v3/…` (Basic auth `shopId:секретный ключ`, обязательный `Idempotence-Key` на POST); сценарии подтверждения `redirect` (готовая форма) и `embedded` (виджет + `confirmation_token`); итог платежа проверять по статусу (`pending → waiting_for_capture → succeeded/canceled`), а не по возврату на `return_url`.

## Официальная документация MiniMax — ИИ для модерации (`minimax/`)

Копия ключевых страниц `platform.minimax.io/docs` для интеграции ИИ-проверки пересылаемых сообщений (модерация по жалобам и стоп-словарю) через **Anthropic-совместимый API** MiniMax. Тариф проекта — **Token Plan** (квота в 5-часовых/недельных окнах, ошибка `2056` при исчерпании). Подробный индекс и ключевые факты (что поддержано, а что нет) — в **[`minimax/README.md`](minimax/README.md)**.

Ключевое для интеграции: base URL `https://api.minimax.io/anthropic` со стандартным SDK `anthropic`; модели `MiniMax-M3` (thinking по умолчанию выключен) и `MiniMax-M2.x` (thinking неотключаем); `tool_choice` только `auto`/`none` (принудительного вызова нет), structured outputs нет → JSON-вердикты через промпт + валидацию.

## С чего начинать чтение

1. `telegram/markdown/04-api-reference.md` — точные сигнатуры методов и поля объектов Telegram.
2. `telegram/markdown/02-features.md` — Privacy Mode и Rich Messages.
3. `max/README.md` → `max/markdown/docs-api.md` — методы и объекты Bot API MAX.
4. `yookassa/README.md` → `yookassa/markdown/getting-started/quick-start.md` — приём платежей.
5. `yandex-market-digital.md` — настройка API-уведомлений и выдачи кодов Маркета.
