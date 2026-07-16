<!-- source: https://dev.max.ru/docs-api/methods/POST/messages -->
> Источник: https://dev.max.ru/docs-api/methods/POST/messages

# Отправить сообщение

POST`/messages`

Отправляет сообщение в чат

#### Пример запроса с одной кнопкой-ссылкой

Больше примеров запросов с кнопками — [в разделе «Клавиатура»](../../../docs-api.md#%D0%9A%D0%B0%D0%BA%20%D0%B4%D0%BE%D0%B1%D0%B0%D0%B2%D0%B8%D1%82%D1%8C%20%D0%BA%D0%BD%D0%BE%D0%BF%D0%BA%D0%B8)

BASH

```
curl -X POST "https://platform-api.max.ru/messages?user_id={user_id}" \
  -H "Authorization: {access_token}" \
  -H "Content-Type: application/json" \
  -d '{
  "text": "Это сообщение с кнопкой-ссылкой",
  "attachments": [
    {
      "type": "inline_keyboard",
      "payload": {
        "buttons": [
          [
            {
              "type": "link",
              "text": "Откройте сайт",
              "url": "https://example.com"
            }
          ]
        ]
      }
    }
  ]
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

`user_id`  
integer  <int64> optional

Если вы хотите отправить сообщение пользователю, укажите его ID

`chat_id`  
integer  <int64> optional

Если сообщение отправляется в чат, укажите его ID. Как получить ID — в [разделе «Получение chat\_id»](../../../docs-api.md#%D0%9F%D0%BE%D0%BB%D1%83%D1%87%D0%B5%D0%BD%D0%B8%D0%B5%20chat_id)

`disable_link_preview`  
boolean  optional

Если `false`, сервер не будет генерировать превью для ссылок в тексте сообщения

## Тело запроса

`text`  
string  Nullable

до `4000` символов

Новый текст сообщения

`attachments`  
 AttachmentRequest[] Nullable

Вложения сообщения. Если поле равно `null`, изменений не произойдет. Если пусто, все вложения будут удалены

`link`  
object NewMessageLink Nullable

Ссылка на сообщение

`notify`  
boolean  optional

По умолчанию: `true`

Если false, участники чата не будут уведомлены (по умолчанию `true`)

`format`  
enum TextFormat Nullable optional

Возможные значения в enum: `"markdown"` `"html"`

Если установлен, текст сообщения будет форматирован данным способом. Для подробной информации загляните в раздел [Форматирование](../../../docs-api.md#%D0%A4%D0%BE%D1%80%D0%BC%D0%B0%D1%82%D0%B8%D1%80%D0%BE%D0%B2%D0%B0%D0%BD%D0%B8%D0%B5%20%D1%82%D0%B5%D0%BA%D1%81%D1%82%D0%B0%20%D0%B2%20%D1%81%D0%BE%D0%BE%D0%B1%D1%89%D0%B5%D0%BD%D0%B8%D1%8F%D1%85)

## Результат

`message`  
object Message

Сообщение в чате
