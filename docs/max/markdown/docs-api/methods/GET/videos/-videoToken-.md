<!-- source: https://dev.max.ru/docs-api/methods/GET/videos/-videoToken- -->
> Источник: https://dev.max.ru/docs-api/methods/GET/videos/-videoToken-

# Получить информацию о видео

GET`/videos/{videoToken}`

Возвращает подробную информацию о прикреплённом видео. URL-адреса воспроизведения и дополнительные метаданные

#### Пример запроса:

BASH

```
curl -X GET "https://platform-api.max.ru/videos/{video_token}" \
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

`videoToken`  
string    
[a-zA-Z0-9\_\-]+

Токен видео-вложения

## Результат

`token`  
string

Токен видео-вложения

`urls`  
object VideoUrls Nullable optional

URL-ы для скачивания или воспроизведения видео. Может быть null, если видео недоступно

`thumbnail`  
object PhotoAttachmentPayload Nullable optional

Миниатюра видео

`width`  
integer

Ширина видео

`height`  
integer

Высота видео

`duration`  
integer

Длина видео в секундах
