# Документация MiniMax (platform.minimax.io)

Локальная копия официальной документации MiniMax по интеграции через **Anthropic-совместимый API**.
Проект использует MiniMax как ИИ-провайдера для модерации пересылаемых сообщений (проверка по жалобам
и по срабатыванию стоп-словаря). Тариф — **Token Plan** (подписка с квотой).

Источник — официальные markdown-страницы Mintlify (`<URL>.md`), полный индекс: <https://platform.minimax.io/docs/llms.txt>.
Сохранено: 2026-07-05.

## Ключевые факты (сверено с документацией)

- **Base URL:** `https://api.minimax.io/anthropic` — работает со стандартным SDK `anthropic`
  (`ANTHROPIC_BASE_URL` + `ANTHROPIC_API_KEY` = ключ MiniMax; для Token Plan — Subscription Key).
- **Модели:** `MiniMax-M3` (контекст 1M; **thinking по умолчанию ВЫКЛЮЧЕН**, включается `{"type": "adaptive"}`),
  `MiniMax-M2.7|M2.5|M2.1|M2` (+`-highspeed`; контекст 204,8K; **thinking неотключаем** — блоки thinking будут всегда).
- **Чего НЕТ (важно для кода):**
  - `tool_choice` — **только `auto` и `none`**; принудительный вызов (`{"type": "tool", ...}`, `any`) не поддержан;
  - structured outputs (`output_config.format`) — отсутствует → гарантированный JSON получаем промптом + строгой валидацией + ретраем;
  - `top_k`, `stop_sequences`, `mcp_servers`, `context_management`, `container` — **игнорируются молча**.
- **Есть:** `system`, `stream`, `temperature` [0..2], `tools`, `top_p`, `metadata.user_id`,
  `service_tier` (`standard`/`priority`, priority = ×1,5 цены), кэширование `cache_control` (см. отдельную страницу),
  `POST /anthropic/v1/messages/count_tokens` (для M3).
- **Rate limits:** M3 — 200 RPM / 10M TPM; M2.x — 500 RPM / 20M TPM.
- **Token Plan:** Plus $20 / Max $50 / Ultra $120 в месяц; квота в **5-часовых скользящих и недельных окнах**;
  покрывает все модели платформы; Credits-пакеты (1000 кредитов = $1, срок 365 дней) покрывают перелив.
- **Коды ошибок, которые обязана обрабатывать наша интеграция:**
  - `1002` rate limit, `1039` token limit → ретрай позже;
  - `2056` **usage limit exceeded** → квота окна Token Plan исчерпана, ждать следующего 5-часового окна;
  - `1008` insufficient balance; `2045` rate growth limit (не наращивать запросы скачком).
- В multi-turn диалогах с tool use возвращать в историю **полный** `response.content` (включая thinking-блоки, не изменяя их).

## Файлы

| Файл | Что внутри |
| --- | --- |
| `markdown/text-anthropic-api.md` | **Главная**: подключение через Anthropic SDK, модели, таблица совместимости параметров, thinking, примеры |
| `markdown/text-chat-anthropic.md` | Справочник Messages API (`POST /anthropic/v1/messages`): полные схемы запроса/ответа (OpenAPI), `ToolChoice` (только auto/none), блоки контента |
| `markdown/pricing-token-plan.md` | Тарифы Token Plan (Plus/Max/Ultra), квотные окна, Credits-пакеты |
| `markdown/rate-limits.md` | Лимиты RPM/TPM по моделям |
| `markdown/errorcode.md` | Коды ошибок API и что с ними делать |
| `markdown/anthropic-api-compatible-cache.md` | Явное кэширование промпта (`cache_control`) в Anthropic-совместимом API |
| `markdown/faq-about-apis.md` | FAQ по API (расчёт tps и пр.) |

## Правило проекта

Перед реализацией **любого** обращения к MiniMax (параметры запроса, выбор модели, обработка ошибок,
кэширование, подсчёт токенов) — сначала сверяться с этими файлами, а не полагаться на память
и не переносить сюда возможности первопартийного API Anthropic (structured outputs, forced tool_choice,
`budget_tokens` и т.п. здесь НЕ работают).
