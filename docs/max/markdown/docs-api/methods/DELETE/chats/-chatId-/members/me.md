<!-- source: https://dev.max.ru/docs-api/methods/DELETE/chats/-chatId-/members/me -->
> Источник: https://dev.max.ru/docs-api/methods/DELETE/chats/-chatId-/members/me

# Удаление бота из группового чата или канала

DELETE`/chats/{chatId}/members/me`

Удаляет бота из участников группового чата или канала

Пример запроса:

BASH

```
curl -X DELETE "https://platform-api.max.ru/chats/{chatId}/members/me" \
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

## Результат

`success`  
boolean

`true`, если запрос был успешным, `false` — в противном случае

`message`  
string  optional

Объяснительное сообщение, если результат не был успешным
