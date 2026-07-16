<!-- source: https://dev.max.ru/docs-api/methods/DELETE/chats/-chatId-/members -->
> Источник: https://dev.max.ru/docs-api/methods/DELETE/chats/-chatId-/members

# Удаление участника из группового чата или канала

DELETE`/chats/{chatId}/members`

Удаляет участника из группового чата или канала

Бот, чей токен `access_token` используется для авторизации, должен быть администратором этого чата или канала с соответствующим правом `add_remove_members`. Чтобы получить информацию о правах бота, используйте [GET /chats/-chatId-/members/admins](../../../GET/chats/-chatId-/members/admins.md). Подробнее о правах — в описании объекта [`Chat`](../../../../objects/Chat.md)

Пример запроса:

BASH

```
curl -X DELETE "https://platform-api.max.ru/chats/{chatId}/members?user_id={user_id}&block=true" \
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

`user_id`  
integer  <int64>

ID пользователя, которого нужно удалить из группового чата или канала

`block`  
boolean  optional

Если передать `true`, пользователь будет заблокирован в чате. Применяется только для чатов с публичной или приватной ссылкой. Игнорируется в остальных случаях

## Результат

`success`  
boolean

`true`, если запрос был успешным, `false` — в противном случае

`message`  
string  optional

Объяснительное сообщение, если результат не был успешным
