<!-- source: https://dev.max.ru/docs-api/methods/POST/chats/-chatId-/actions -->
> Источник: https://dev.max.ru/docs-api/methods/POST/chats/-chatId-/actions

# Отправка действия бота в групповой чат

POST`/chats/{chatId}/actions`

Позволяет отправлять в групповой чат такие действия бота, как например: «набор текста» или «отправка фото»

#### Пример запроса:

BASH

```
curl -X POST "https://platform-api.max.ru/chats/{chatId}/actions" \
  -H "Authorization: {access_token}" \
  -H "Content-Type: application/json" \
  -d '{
  "action": "typing_on"
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

ID чата

## Тело запроса

`action`  
enum SenderAction

Возможные значения в enum: `"typing_on"` `"sending_photo"` `"sending_video"` `"sending_audio"` `"sending_file"`

Действие, отправляемое участникам чата. Возможные значения:

- `"typing_on"` — Бот набирает сообщение
- `"sending_photo"` — Бот отправляет фото
- `"sending_video"` — Бот отправляет видео
- `"sending_audio"` — Бот отправляет аудиофайл
- `"sending_file"` — Бот отправляет файл

## Результат

`success`  
boolean

`true`, если запрос был успешным, `false` — в противном случае

`message`  
string  optional

Объяснительное сообщение, если результат не был успешным
