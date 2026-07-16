# Документация для разработчиков MAX (`dev.max.ru`)

Полная локальная копия документации платформы **MAX** для разработчиков.
Скачано 2026-06-14 со всех четырёх разделов `dev.max.ru`: **API**, **Документация**, **UI**, **Помощь**.
При изменении интеграции MAX сверяйтесь с точными сигнатурами и ограничениями в этих файлах.

- `markdown/` — читаемая документация (для сверки при разработке);
- `html/` — исходный сырой HTML (полная копия страниц, со всеми ссылками на ассеты).

## Ключевое для интеграции (бот MAX)

- **Базовый URL Bot API:** `https://platform-api.max.ru`
- **Авторизация:** заголовок `Authorization: <access_token>` (передача токена через query-параметр больше не поддерживается). Токен выдаётся при создании бота на платформе (раздел **Чат-боты**).
- **Получение событий:** **Webhook** (`POST /subscriptions`) — рекомендуется для production; **Long Polling** (`GET /updates`) — только для разработки/тестов.
- **Форматирование текста:** `markdown` или `html` (поле `format` в теле сообщения, объект `NewMessageBody`).
- **Лимит длины текста сообщения:** до `4000` символов.

## API (`docs-api/`)

- **Обзор и общие правила (форматирование, клавиатуры, вложения, рекомендации):** [`markdown/docs-api.md`](markdown/docs-api.md) — *Обзор*

### Объекты

| Объект | Файл |
| --- | --- |
| `BotInfo` | [markdown/docs-api/objects/BotInfo.md](markdown/docs-api/objects/BotInfo.md) |
| `Chat` | [markdown/docs-api/objects/Chat.md](markdown/docs-api/objects/Chat.md) |
| `ChatMember` | [markdown/docs-api/objects/ChatMember.md](markdown/docs-api/objects/ChatMember.md) |
| `Message` | [markdown/docs-api/objects/Message.md](markdown/docs-api/objects/Message.md) |
| `NewMessageBody` | [markdown/docs-api/objects/NewMessageBody.md](markdown/docs-api/objects/NewMessageBody.md) |
| `Update` | [markdown/docs-api/objects/Update.md](markdown/docs-api/objects/Update.md) |
| `User` | [markdown/docs-api/objects/User.md](markdown/docs-api/objects/User.md) |
| `UserWithPhoto` | [markdown/docs-api/objects/UserWithPhoto.md](markdown/docs-api/objects/UserWithPhoto.md) |

### Методы

| Метод | Описание | Файл |
| --- | --- | --- |
| `POST /answers` | Ответ на callback | [markdown/docs-api/methods/POST/answers.md](markdown/docs-api/methods/POST/answers.md) |
| `GET /chats` | Получение списка всех групповых чатов и каналов для бота | [markdown/docs-api/methods/GET/chats.md](markdown/docs-api/methods/GET/chats.md) |
| `DELETE /chats/{chatId}` | Удаление группового чата | [markdown/docs-api/methods/DELETE/chats/-chatId-.md](markdown/docs-api/methods/DELETE/chats/-chatId-.md) |
| `GET /chats/{chatId}` | Получение информации о групповом чате или канале | [markdown/docs-api/methods/GET/chats/-chatId-.md](markdown/docs-api/methods/GET/chats/-chatId-.md) |
| `PATCH /chats/{chatId}` | Изменение информации о групповом чате или канале | [markdown/docs-api/methods/PATCH/chats/-chatId-.md](markdown/docs-api/methods/PATCH/chats/-chatId-.md) |
| `POST /chats/{chatId}/actions` | Отправка действия бота в групповой чат | [markdown/docs-api/methods/POST/chats/-chatId-/actions.md](markdown/docs-api/methods/POST/chats/-chatId-/actions.md) |
| `DELETE /chats/{chatId}/members` | Удаление участника из группового чата или канала | [markdown/docs-api/methods/DELETE/chats/-chatId-/members.md](markdown/docs-api/methods/DELETE/chats/-chatId-/members.md) |
| `GET /chats/{chatId}/members` | Получение участников группового чата или канала | [markdown/docs-api/methods/GET/chats/-chatId-/members.md](markdown/docs-api/methods/GET/chats/-chatId-/members.md) |
| `POST /chats/{chatId}/members` | Добавление участников в групповой чат или канал | [markdown/docs-api/methods/POST/chats/-chatId-/members.md](markdown/docs-api/methods/POST/chats/-chatId-/members.md) |
| `GET /chats/{chatId}/members/admins` | Получение списка администраторов группового чата или канала | [markdown/docs-api/methods/GET/chats/-chatId-/members/admins.md](markdown/docs-api/methods/GET/chats/-chatId-/members/admins.md) |
| `POST /chats/{chatId}/members/admins` | Назначить администратора группового чата или канала | [markdown/docs-api/methods/POST/chats/-chatId-/members/admins.md](markdown/docs-api/methods/POST/chats/-chatId-/members/admins.md) |
| `DELETE /chats/{chatId}/members/admins/{userId}` | Отменить права администратора в групповом чате или канале | [markdown/docs-api/methods/DELETE/chats/-chatId-/members/admins/-userId-.md](markdown/docs-api/methods/DELETE/chats/-chatId-/members/admins/-userId-.md) |
| `DELETE /chats/{chatId}/members/me` | Удаление бота из группового чата или канала | [markdown/docs-api/methods/DELETE/chats/-chatId-/members/me.md](markdown/docs-api/methods/DELETE/chats/-chatId-/members/me.md) |
| `GET /chats/{chatId}/members/me` | Получение информации о членстве бота в групповом чате или канале | [markdown/docs-api/methods/GET/chats/-chatId-/members/me.md](markdown/docs-api/methods/GET/chats/-chatId-/members/me.md) |
| `DELETE /chats/{chatId}/pin` | Открепление сообщения в групповом чате или канале | [markdown/docs-api/methods/DELETE/chats/-chatId-/pin.md](markdown/docs-api/methods/DELETE/chats/-chatId-/pin.md) |
| `GET /chats/{chatId}/pin` | Получение закреплённого сообщения в групповом чате или канале | [markdown/docs-api/methods/GET/chats/-chatId-/pin.md](markdown/docs-api/methods/GET/chats/-chatId-/pin.md) |
| `PUT /chats/{chatId}/pin` | Закрепление сообщения в групповом чате или канале | [markdown/docs-api/methods/PUT/chats/-chatId-/pin.md](markdown/docs-api/methods/PUT/chats/-chatId-/pin.md) |
| `GET /chats/{chatLink}` | Получение информации о канале по его ссылке | [markdown/docs-api/methods/GET/chats/-chatLink-.md](markdown/docs-api/methods/GET/chats/-chatLink-.md) |
| `GET /me` | Получение информации о боте | [markdown/docs-api/methods/GET/me.md](markdown/docs-api/methods/GET/me.md) |
| `DELETE /messages` | Удалить сообщение | [markdown/docs-api/methods/DELETE/messages.md](markdown/docs-api/methods/DELETE/messages.md) |
| `GET /messages` | Получение сообщений | [markdown/docs-api/methods/GET/messages.md](markdown/docs-api/methods/GET/messages.md) |
| `POST /messages` | Отправить сообщение | [markdown/docs-api/methods/POST/messages.md](markdown/docs-api/methods/POST/messages.md) |
| `PUT /messages` | Редактировать сообщение | [markdown/docs-api/methods/PUT/messages.md](markdown/docs-api/methods/PUT/messages.md) |
| `GET /messages/{messageId}` | Получить сообщение | [markdown/docs-api/methods/GET/messages/-messageId-.md](markdown/docs-api/methods/GET/messages/-messageId-.md) |
| `DELETE /subscriptions` | Отписка от обновлений о новых событиях через Webhook | [markdown/docs-api/methods/DELETE/subscriptions.md](markdown/docs-api/methods/DELETE/subscriptions.md) |
| `GET /subscriptions` | Получение всех подписок через Webhook | [markdown/docs-api/methods/GET/subscriptions.md](markdown/docs-api/methods/GET/subscriptions.md) |
| `POST /subscriptions` | Подписка на обновления о новых событиях через Webhook | [markdown/docs-api/methods/POST/subscriptions.md](markdown/docs-api/methods/POST/subscriptions.md) |
| `GET /updates` | Получение обновлений о событиях через Long Polling | [markdown/docs-api/methods/GET/updates.md](markdown/docs-api/methods/GET/updates.md) |
| `POST /uploads` | Загрузка файлов | [markdown/docs-api/methods/POST/uploads.md](markdown/docs-api/methods/POST/uploads.md) |
| `GET /videos/{videoToken}` | Получить информацию о видео | [markdown/docs-api/methods/GET/videos/-videoToken-.md](markdown/docs-api/methods/GET/videos/-videoToken-.md) |

## Документация / гайды (`docs/`)

- **О платформе (старт):** [`markdown/docs.md`](markdown/docs.md) — *О платформе*

| Раздел | Файл |
| --- | --- |
| Создание каналов | [markdown/docs/channels/create.md](markdown/docs/channels/create.md) |
| Как управлять каналами в MAX | [markdown/docs/channels/manage.md](markdown/docs/channels/manage.md) |
| Примеры создания ботов | [markdown/docs/chatbots/bots-coding/examples.md](markdown/docs/chatbots/bots-coding/examples.md) |
| Работа с библиотекой Golang | [markdown/docs/chatbots/bots-coding/go.md](markdown/docs/chatbots/bots-coding/go.md) |
| Работа с библиотекой JavaScript | [markdown/docs/chatbots/bots-coding/js.md](markdown/docs/chatbots/bots-coding/js.md) |
| Подготовка и настройка бота | [markdown/docs/chatbots/bots-coding/prepare.md](markdown/docs/chatbots/bots-coding/prepare.md) |
| Cоздание чат-бота | [markdown/docs/chatbots/bots-create.md](markdown/docs/chatbots/bots-create.md) |
| Подготовка и настройка бота | [markdown/docs/chatbots/bots-nocode/create.md](markdown/docs/chatbots/bots-nocode/create.md) |
| Управление ботом | [markdown/docs/chatbots/bots-nocode/manage.md](markdown/docs/chatbots/bots-nocode/manage.md) |
| Подключение к Цифровому ID | [markdown/docs/digital-id.md](markdown/docs/digital-id.md) |
| Типовое пользовательское соглашение | [markdown/docs/legal/agreement.md](markdown/docs/legal/agreement.md) |
| Типовая политика конфиденциальности | [markdown/docs/legal/privacy.md](markdown/docs/legal/privacy.md) |
| Требования к содержанию и функциональности Приложений Разработчиков | [markdown/docs/legal/requirements.md](markdown/docs/legal/requirements.md) |
| Правила размещения чат-ботов и мини-приложений на платформе «MAX» | [markdown/docs/legal/rules.md](markdown/docs/legal/rules.md) |
| Подключение к платформе и создание профиля организации или ИП | [markdown/docs/maxbusiness/connection.md](markdown/docs/maxbusiness/connection.md) |
| Выбор сервисов для интеграции | [markdown/docs/maxbusiness/selectionservices.md](markdown/docs/maxbusiness/selectionservices.md) |
| Об интеграции с сервисами партнёров | [markdown/docs/partners-integration.md](markdown/docs/partners-integration.md) |
| MAX Bridge | [markdown/docs/webapps/bridge.md](markdown/docs/webapps/bridge.md) |
| Подключение мини-приложения | [markdown/docs/webapps/introduction.md](markdown/docs/webapps/introduction.md) |
| Валидация данных | [markdown/docs/webapps/validation.md](markdown/docs/webapps/validation.md) |

## UI-компоненты (`ui/`)

- **Обзор UI-кита:** [`markdown/ui.md`](markdown/ui.md) — *Обзор*

**Компоненты:** [Avatar.CloseButton](markdown/ui/components/Avatar.CloseButton.md), [Avatar.Container](markdown/ui/components/Avatar.Container.md), [Avatar.Icon](markdown/ui/components/Avatar.Icon.md), [Avatar.Image](markdown/ui/components/Avatar.Image.md), [Avatar.OnlineDot](markdown/ui/components/Avatar.OnlineDot.md), [Avatar.Overlay](markdown/ui/components/Avatar.Overlay.md), [Avatar.Text](markdown/ui/components/Avatar.Text.md), [Button](markdown/ui/components/Button.md), [CellAction](markdown/ui/components/CellAction.md), [CellHeader](markdown/ui/components/CellHeader.md), [CellInput](markdown/ui/components/CellInput.md), [CellList](markdown/ui/components/CellList.md), [CellSimple](markdown/ui/components/CellSimple.md), [Container](markdown/ui/components/Container.md), [Counter](markdown/ui/components/Counter.md), [Dot](markdown/ui/components/Dot.md), [EllipsisText](markdown/ui/components/EllipsisText.md), [Flex](markdown/ui/components/Flex.md), [Grid](markdown/ui/components/Grid.md), [IconButton](markdown/ui/components/IconButton.md), [Input](markdown/ui/components/Input.md), [Panel](markdown/ui/components/Panel.md), [Ripple](markdown/ui/components/Ripple.md), [SearchInput](markdown/ui/components/SearchInput.md), [Spinner](markdown/ui/components/Spinner.md), [Switch](markdown/ui/components/Switch.md), [Textarea](markdown/ui/components/Textarea.md), [ToolButton](markdown/ui/components/ToolButton.md), [Typography.Action](markdown/ui/components/Typography.Action.md), [Typography.Body](markdown/ui/components/Typography.Body.md), [Typography.Display](markdown/ui/components/Typography.Display.md), [Typography.Headline](markdown/ui/components/Typography.Headline.md), [Typography.Label](markdown/ui/components/Typography.Label.md), [Typography.Title](markdown/ui/components/Typography.Title.md)

**Композиции:** [Profile](markdown/ui/compositions/Profile.md)

## Помощь (`help/`)

- **FAQ (старт):** [`markdown/help.md`](markdown/help.md) — *FAQ*

| Тема | Файл |
| --- | --- |
| Каналы | [markdown/help/channels.md](markdown/help/channels.md) |
| Чат-боты | [markdown/help/chatbots.md](markdown/help/chatbots.md) |
| Диплинки | [markdown/help/deeplinks.md](markdown/help/deeplinks.md) |
| Цифровой ID | [markdown/help/digital-id.md](markdown/help/digital-id.md) |
| События | [markdown/help/events.md](markdown/help/events.md) |
| Интеграция с партнёрами | [markdown/help/integration.md](markdown/help/integration.md) |
| Мини-приложения | [markdown/help/miniapps.md](markdown/help/miniapps.md) |
| Создание профиля и верификация организации | [markdown/help/organization.md](markdown/help/organization.md) |
| Регистрация на платформе | [markdown/help/platform_connection.md](markdown/help/platform_connection.md) |
| Служба поддержки | [markdown/help/support.md](markdown/help/support.md) |

## Как обновлять

Страницы качались рекурсивным обходом `dev.max.ru` (Next.js SSR), HTML→Markdown — через `python3` + `beautifulsoup4`/`markdownify` (парсер `lxml`). Скрипт: `/tmp/max_scrape.py`.
