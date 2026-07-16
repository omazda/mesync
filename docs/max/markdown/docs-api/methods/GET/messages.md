<!-- source: https://dev.max.ru/docs-api/methods/GET/messages -->
> Источник: https://dev.max.ru/docs-api/methods/GET/messages

# Получение сообщений

GET`/messages`

Метод возвращает информацию о сообщении или массив сообщений из чата. Для выполнения запроса нужно указать один из параметров — `chat_id` или `message_ids`:

- `chat_id` — метод возвращает массив сообщений из указанного чата. Сообщения возвращаются в обратном порядке: последние сообщения будут первыми в массиве. Как получить ID — в [разделе «Получение chat\_id»](../../../docs-api.md#%D0%9F%D0%BE%D0%BB%D1%83%D1%87%D0%B5%D0%BD%D0%B8%D0%B5%20chat_id)
- `message_ids` — метод возвращает информацию о запрошенных сообщениях. Можно указать один идентификатор или несколько

#### Пример запроса с использованием `chat_id`:

BASH

```
curl -X GET "https://platform-api.max.ru/messages?chat_id={chat_id}" \
  -H "Authorization: {access_token}"
```

#### Пример запроса с использованием `message_ids`:

BASH

```
curl -X GET "https://platform-api.max.ru/messages?message_ids={message_id1},{message_id2}" \
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

`chat_id`  
integer bigint <int64> optional

ID чата, чтобы получить сообщения из определённого чата. Обязательный параметр, если не указан `message_ids`. Как получить ID — в [разделе «Получение chat\_id»](../../../docs-api.md#%D0%9F%D0%BE%D0%BB%D1%83%D1%87%D0%B5%D0%BD%D0%B8%D0%B5%20chat_id)

`message_ids`  
array  <string> optional

Список ID сообщений, которые нужно получить (через запятую). Обязательный параметр, если не указан `chat_id`

`from`  
integer bigint <int64> optional

Время, до которого будут запрошены все сообщения с начала чата (в формате Unix timestamp)

`to`  
integer bigint <int64> optional

Время, начиная с которого будут запрошены все сообщения до конца чата (в формате Unix timestamp)

`count`  
integer  [1-100] optional

По умолчанию: `50`

Максимальное количество сообщений в ответе

## Результат

`messages`  
 Message[]

Массив сообщений
