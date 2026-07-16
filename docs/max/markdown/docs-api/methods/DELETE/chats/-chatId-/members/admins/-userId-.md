<!-- source: https://dev.max.ru/docs-api/methods/DELETE/chats/-chatId-/members/admins/-userId- -->
> Источник: https://dev.max.ru/docs-api/methods/DELETE/chats/-chatId-/members/admins/-userId-

# Отменить права администратора в групповом чате или канале

DELETE`/chats/{chatId}/members/admins/{userId}`

Лишает пользователя или бота прав администратора в групповом чате или канале. При этом из чата и канала они не исключаются

Бот, чей токен `access_token` используется для авторизации, должен быть администратором этого чата или канала с соответствующим правом `add_admins`. Чтобы получить информацию о правах бота, используйте [GET /chats/-chatId-/members/admins](../../../../../GET/chats/-chatId-/members/admins.md). Подробнее о правах — в описании объекта [`Chat`](../../../../../../objects/Chat.md)

Пример запроса:

BASH

```
curl -X DELETE "https://platform-api.max.ru/chats/{chatId}/members/admins/{userId}" \
  -H "Authorization: {access_token}"
```

## Авторизация

`access_token`  
apiKey

> Передача токена через query-параметры больше не поддерживается — используйте заголовок `Authorization: <token>`

Токен для вызова HTTP-запросов присваивается при создании бота — его можно найти на [платформе](https://business.max.ru/self) в разделе **Чат-боты** → **Перейти** → **Расширенные настройки** → **Настроить**

Рекомендуем не разглашать токен посторонним, чтобы они не получили доступ к управлению ботом.
Токен может быть отозван за нарушение Правил платформы

## Параметры

`chatId`  
integer  <int64>   
\-?\d+

ID группового чата или канала

`userId`  
integer  <int64>

Идентификатор пользователя или бота, которого надо лишить прав администратора

## Результат

`success`  
boolean

`true`, если запрос был успешным, `false` — в противном случае

`message`  
string  optional

Объяснительное сообщение, если результат не был успешным
