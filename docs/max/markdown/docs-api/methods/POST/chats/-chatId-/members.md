<!-- source: https://dev.max.ru/docs-api/methods/POST/chats/-chatId-/members -->
> Источник: https://dev.max.ru/docs-api/methods/POST/chats/-chatId-/members

# Добавление участников в групповой чат или канал

POST`/chats/{chatId}/members`

Добавляет участников в групповой чат или канал

Бот, чей токен `access_token` используется для авторизации, должен быть администратором этого чата или канала с соответствующим правом `add_remove_members`. Чтобы получить информацию о правах бота, используйте [GET /chats/-chatId-/members/admins](../../../GET/chats/-chatId-/members/admins.md). Подробнее о правах — в описании объекта [`Chat`](../../../../objects/Chat.md)

Пример запроса:

BASH

```
curl -X POST "https://platform-api.max.ru/chats/{chatId}/members" \
  -H "Authorization: {access_token}" \
  -H "Content-Type: application/json" \
  -d '{
  "user_ids": ["{user_id_1}", "{user_id_2}"]
}'
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

## Тело запроса

`user_ids`  
 integer[]

Массив ID пользователей, которых вы хотите добавить в групповой чат или канал. В одном запросе можно передать максимум 100 идентификаторов

## Результат

`success`  
boolean

`true`, если запрос был успешным, `false` — в противном случае

`message`  
string  optional

Объяснительное сообщение, если результат не был успешным

`failed_user_ids`  
 integer[] Nullable optional

ID пользователей, которых не удалось добавить

`failed_user_details`  
 FailedUserDetails[] Nullable optional

Подробное описание, почему пользователь не был добавлен в групповой чат или канал
