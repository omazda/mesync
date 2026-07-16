<!-- source: https://dev.max.ru/docs-api/methods/PUT/chats/-chatId-/pin -->
> Источник: https://dev.max.ru/docs-api/methods/PUT/chats/-chatId-/pin

# Закрепление сообщения в групповом чате или канале

PUT`/chats/{chatId}/pin`

Закрепляет сообщение в групповом чате или канале

Бот, чей токен `access_token` используется для авторизации, должен быть администратором этого чата или канала

Пример запроса:

BASH

```
curl -X PUT "https://platform-api.max.ru/chats/{chatId}/pin" \
  -H "Authorization: {access_token}" \
  -H "Content-Type: application/json" \
  -d '{
  "message_id": "{message_id}",
  "notify": true
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

ID группового чата или канала, где нужно закрепить сообщение

## Тело запроса

`message_id`  
string

ID сообщения, которое нужно закрепить. Соответствует полю `Message.body.mid`

`notify`  
boolean  Nullable optional

По умолчанию: `true`

Если `true`, участники получат уведомление с системным сообщением о закреплении

## Результат

`success`  
boolean

`true`, если запрос был успешным, `false` — в противном случае

`message`  
string  optional

Объяснительное сообщение, если результат не был успешным
