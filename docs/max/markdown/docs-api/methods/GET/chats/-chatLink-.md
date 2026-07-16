<!-- source: https://dev.max.ru/docs-api/methods/GET/chats/-chatLink- -->
> Источник: https://dev.max.ru/docs-api/methods/GET/chats/-chatLink-

# Получение информации о канале по его ссылке

GET`/chats/{chatLink}`

Возвращает информацию о канале по его публичной ссылке. Метод доступен только для каналов — получить информацию о чате по публичной ссылке не получится

## Авторизация

`access_token`  
apiKey

> Передача токена через query-параметры больше не поддерживается — используйте заголовок `Authorization: <token>`

Токен для вызова HTTP-запросов присваивается при создании бота — его можно найти на [платформе](https://business.max.ru/self) в разделе **Чат-боты** → **Перейти** → **Расширенные настройки** → **Настроить**

Рекомендуем не разглашать токен посторонним, чтобы они не получили доступ к управлению ботом.
Токен может быть отозван за нарушение Правил платформы

## Параметры

`chatLink`  
string    
@?[a-zA-Z]+[\\w-]\*

Публичная ссылка на канал

## Результат

`chat_id`  
integer  <int64>

ID чата или канала — в зависимости от ограничений метода и от того, с чем вы работаете. Как получить ID — в [разделе «Получение chat\_id»](../../../../docs-api.md#%D0%9F%D0%BE%D0%BB%D1%83%D1%87%D0%B5%D0%BD%D0%B8%D0%B5%20chat_id)

`type`  
enum ChatType

Возможные значения в enum: `"chat"`

Тип чата:

- `"chat"` — Групповой чат
- `"channel"` — Канал
- `"dialog"` — Диалог

`status`  
enum ChatStatus

Возможные значения в enum: `"active"` `"removed"` `"left"` `"closed"`

Статус чата:

- `"active"` — Бот является активным участником чата
- `"removed"` — Бот был удалён из чата
- `"left"` — Бот покинул чат
- `"closed"` — Чат был закрыт

`title`  
string  Nullable

Отображаемое название чата или канала. Может быть `null` для диалогов

`icon`  
object Image Nullable

Иконка чата или канала

`last_event_time`  
integer  <int64>

Время последнего события в чате или канале

`participants_count`  
integer  <int32>

Количество участников чата или канала. Для диалогов всегда `2`

`owner_id`  
integer  <int64> Nullable optional

ID владельца чата или канала

`participants`  
object  Nullable optional

Участники чата или канала с временем последней активности. Может быть `null`, если запрашивается список чатов

`is_public`  
boolean

Доступен ли чат публично (для диалогов всегда `false`)

`link`  
string  Nullable optional

Ссылка на чат

`description`  
string  Nullable

Описание чата или канала

`dialog_with_user`  
object UserWithPhoto Nullable optional

Данные о пользователе в диалоге (только для чатов типа `"dialog"`)

`messages_count`  
integer  Nullable optional

Количество сообщений в групповых чатах и каналах

`pinned_message`  
object Message Nullable optional

Закреплённое сообщение в чате (возвращается только при запросе конкретного чата или канала)
