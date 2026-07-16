<!-- source: https://dev.max.ru/docs-api/methods/POST/answers -->
> Источник: https://dev.max.ru/docs-api/methods/POST/answers

# Ответ на callback

POST`/answers`

Этот метод используется для отправки ответа после того, как пользователь нажал на кнопку. Ответом может быть обновленное сообщение и/или одноразовое уведомление для пользователя

#### Пример запроса:

BASH

```
curl -X POST "https://platform-api.max.ru/answers?callback_id=callback_id" \
  -H "Authorization: {access_token}" \
  -H "Content-Type: application/json" \
  -d '{
    "message": {
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
    }
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

`callback_id`  
string    
^(?!\s\*$).+

от `1` символа

Идентификатор кнопки, на которую нажал пользователь

Идентификатор можно получить в обновлениях о событиях через [Webhook](subscriptions.md) или [Long Polling](../GET/updates.md)

Получение обновлений с помощью [Long Polling](../GET/updates.md) ограничено по скорости и сроку хранения событий — этот способ не подходит для production-окружения. Рекомендуем на всех этапах работы использовать [Webhook](subscriptions.md)

Когда пользователь нажмёт на кнопку, МАКС отправит событие, содержащее объект [Update](../../objects/Update.md) с типом `message_callback` и идентификатором кнопки в поле `updates[i].callback.callback_id`

## Тело запроса

`message`  
object NewMessageBody Nullable optional

Заполните это, если хотите изменить текущее сообщение

`notification`  
string  Nullable optional

Заполните это, если хотите просто отправить одноразовое уведомление пользователю

## Результат

`success`  
boolean

`true`, если запрос был успешным, `false` — в противном случае

`message`  
string  optional

Объяснительное сообщение, если результат не был успешным
