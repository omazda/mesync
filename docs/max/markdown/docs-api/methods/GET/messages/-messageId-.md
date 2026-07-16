<!-- source: https://dev.max.ru/docs-api/methods/GET/messages/-messageId- -->
> Источник: https://dev.max.ru/docs-api/methods/GET/messages/-messageId-

# Получить сообщение

GET`/messages/{messageId}`

Возвращает сообщение по его ID

#### Пример запроса:

BASH

```
curl -X GET "https://platform-api.max.ru/messages/{messageId}" \
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

`messageId`  
string    
[a-zA-Z0-9\_\-]+

ID сообщения (`mid`), чтобы получить одно сообщение в чате

## Результат

`sender`  
object User optional

Пользователь, отправивший сообщение

`recipient`  
object Recipient

Получатель сообщения. Может быть пользователем или чатом

`timestamp`  
integer  <int64>

Время создания сообщения в формате Unix-time

`link`  
object LinkedMessage Nullable optional

Пересланное или ответное сообщение

`body`  
object MessageBody

Содержимое сообщения. Текст + вложения. Может быть `null`, если сообщение содержит только пересланное сообщение

`stat`  
object MessageStat Nullable optional

Статистика сообщения. Возвращается только для постов в каналах

`url`  
string  Nullable optional

Публичная ссылка на пост в канале. Отсутствует для диалогов и групповых чатов
