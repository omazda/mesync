<!-- source: https://dev.max.ru/docs-api/objects/Message -->
> Источник: https://dev.max.ru/docs-api/objects/Message

# Message

Сообщение в чате

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

## Пример объекта

JSON

```
{
  "sender": { ... },
  "recipient": { ... },
 "timestamp": 0,
  "link": { ... },
  "body": { ... },
  "stat": { ... },
 "url": "string"
}
```
