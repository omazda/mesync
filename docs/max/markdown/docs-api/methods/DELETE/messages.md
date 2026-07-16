<!-- source: https://dev.max.ru/docs-api/methods/DELETE/messages -->
> Источник: https://dev.max.ru/docs-api/methods/DELETE/messages

# Удалить сообщение

DELETE`/messages`

Удаляет сообщение в диалоге или чате, если бот имеет разрешение на удаление сообщений

#### Пример запроса:

BASH

```
curl -X DELETE "https://platform-api.max.ru/messages?message_id={message_id}" \
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

`message_id`  
string

от `1` символа

ID удаляемого сообщения

## Результат

`success`  
boolean

`true`, если запрос был успешным, `false` — в противном случае

`message`  
string  optional

Объяснительное сообщение, если результат не был успешным
