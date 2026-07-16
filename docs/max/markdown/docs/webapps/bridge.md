<!-- source: https://dev.max.ru/docs/webapps/bridge -->
> Источник: https://dev.max.ru/docs/webapps/bridge

# MAX Bridge

Библиотека MAX Bridge позволяет мини-приложениям корректно взаимодействовать с API MAX и API операционной системы на устройстве пользователя

## Подключение библиотеки

Через CDN добавьте библиотеку max-web-app.js

HTML

```
<script src="https://st.max.ru/js/max-web-app.js"></script>
```

После подключения библиотеки приложение получит доступ к объекту `WebApp` через глобальный объект `window`

JAVASCRIPT

```
window.WebApp
```

`window.WebApp` — это глобальный объект, который связывает мини-приложение с клиентом и позволяет взаимодействовать с MAX, управлять интерфейсом приложения и получать информацию о пользователях. Объект создаётся с каждым запуском сервиса, предзагружает данные и не требует отдельной инициализации: его методы и параметры доступны напрямую

## Функциональность библиотеки

### Работа с данными инициализации

Чтобы получить инициализационные данные, в объекте `WebApp` предусмотрены следующие методы:

- [`initData`](#window.WebApp.initData)
- [`initDataUnsafe`](#window.WebApp.initDataUnsafe)
- [`platform`](#window.WebApp.platform)
- [`version`](#window.WebApp.version)

#### window.WebApp.initData

Строка со стартовыми параметрами в URL-кодировке.
Содержит данные о пользователе и другие инициализационные данные в виде закодированной в UTF-8 строки для [валидации](validation.md) на стороне сервера

**Тип возвращаемых данных**

JAVASCRIPT

```
string
```

#### window.WebApp.initDataUnsafe

Объект, который содержит данные из `initData` в виде JSON-объекта

> Обратите внимание, что объект **нельзя использовать** для [валидации](validation.md) данных

**Пример**

JAVASCRIPT

```
interface InitData {
query_id: string;
    ip?: string;
auth_date: number;
hash: string;
user: {
id: number;
first_name: string;
last_name: string;
username: string;
language_code: string;
photo_url: string;
};
chat: {
id: number;
type: 'DIALOG' | 'CHAT' | 'CHANNEL';
};
start_param: string;
}
```

**Описание свойств объекта**

| Поле | Тип данных | Описание |
| --- | --- | --- |
| `query_id` | `string` | Уникальный идентификатор текущей сессии |
| `ip?` | `string` | IP-адрес пользователя |
| `auth_date` | `number` | Время выдачи данных. Позволяет определить момент инвалидации данных. Рекомендуемый интервал составляет 1 час |
| `hash` | `string` | Хеш переданных параметров, который можно использовать для проверки их достоверности |
| `user` | `object` | Объект содержит данные о пользователе, который открывает мини-приложение |
| `user.id` | `number` | Идентификатор пользователя |
| `user.first_name` | `string` | Имя пользователя |
| `user.last_name` | `string` | Фамилия пользователя |
| `user.username` | `string` | Никнейм пользователя |
| `user.language_code` | `string` | Язык [интерфейса клиента MAX](https://datatracker.ietf.org/doc/html/rfc5646) |
| `user.photo_url` | `string` | Ссылка на фото профиля пользователя |
| `chat` | `object` | Объект содержит данные о чате, в котором открыто мини-приложение |
| `chat.id` | `number` | Идентификатор чата |
| `chat.type` | `string` | Тип чата (`DIALOG` / `CHAT` / `CHANNEL`) |
| `start_param` | `string` | Значение, переданное в мини-приложение через query-параметр    Пример:  `https://max.ru/<your_awesome_bot>?startapp=someData`, где поле `start_param` будет содержать значение `someData` |

#### window.WebApp.platform

Платформа, с которой запущено мини-приложение.
Возможные значения: `ios`, `android`, `desktop`, `web`

**Тип возвращаемых данных**

JAVASCRIPT

```
string
```

**Пример**

JAVASCRIPT

```
type platform = 'ios' | 'android' | 'desktop' | 'web'
```

#### window.WebApp.version

Версия приложения MAX, с которого запущено мини-приложение

Имеет формат `<year>.<build_number — возрастающий счётчик>.<patch_version — для патчей>`, например `25.9.16`

Этот параметр не участвует в формировании хеша для валидации — в хеше учитываются только данные из `WebAppData`

**Тип возвращаемых данных**

JAVASCRIPT

```
string
```

### Работа с экраном

#### window.WebApp.requestScreenMaxBrightness()

Устанавливает яркость экрана пользователя на максимум

Клиент поддержит максимальную яркость 30 секунд, затем восстановит исходное значение

**Тип возвращаемых данных**

JAVASCRIPT

```
Promise<{maxBrightness: boolean}>
```

**Пример**

JAVASCRIPT

```
window.WebApp.requestScreenMaxBrightness().then(({maxBrightness}) => {
console.log('Яркость установлена на максимум')
});
```

#### window.WebApp.restoreScreenBrightness()

Восстанавливает яркость экрана пользователя до исходного значения

**Тип возвращаемых данных**

JAVASCRIPT

```
Promise<{maxBrightness: boolean}>
```

**Пример**

JAVASCRIPT

```
window.WebApp.restoreScreenBrightness().then(({maxBrightness}) => {
console.log('Яркость восстановлена до исходного значения')
});
```

#### window.WebApp.ScreenCapture.enableScreenCapture()

Включает возможность делать скриншоты или записывать экран

**Тип возвращаемых данных**

JAVASCRIPT

```
Promise<{isScreenCaptureEnabled: boolean}>
```

**Пример**

JAVASCRIPT

```
window.WebApp.ScreenCapture.enableScreenCapture().then(({isScreenCaptureEnabled}) => {
console.log('Включена возможность захвата экрана')
});
```

#### window.WebApp.ScreenCapture.disableScreenCapture()

Отключает возможность делать скриншоты или записывать экран

**Тип возвращаемых данных**

JAVASCRIPT

```
Promise<{isScreenCaptureEnabled: boolean}>
```

**Пример**

JAVASCRIPT

```
window.WebApp.ScreenCapture.disableScreenCapture().then(({isScreenCaptureEnabled}) => {
console.log('Отключена возможность захвата экрана')
});
```

### Запрос номера телефона

> Обратите внимание: отправка номера телефона в чат-бот описана на [странице API](../../docs-api.md#%D0%9A%D0%BD%D0%BE%D0%BF%D0%BA%D0%B0%20request_contact)

#### window.WebApp.requestContact()

Запрашивает номер телефона пользователя в модальном окне нативного клиента МАКС

> Данные пользователя (включая номер телефона), полученные с помощью метода `requestContact()`, могут использоваться только для взаимодействия с текущим мини-приложением. Например, их можно применять для регистрации в программе лояльности, проверки статуса заказа, идентификации пользователя

**Тип возвращаемых данных**

JAVASCRIPT

```
Promise<{
phone: string;
authDate: string; // timestamp создания hash
hash: string;
}>
```

**Пример**

JAVASCRIPT

```
window.WebApp.requestContact().then(({phone}) => {
console.log(`Номер телефона пользователя ${phone}`)
});
```

**Проверка номера телефона**

Для проверки, что полученный на запрос номер телефона совпадает с номером, привязанным к аккаунту пользователя в МАКС, сравните:

- Значение поля `hash`, полученное от клиента
- Значение функции `HMAC_SHA256(authDate + phone + userId, botToken)`, где:
  - `HMAC_SHA256` — стандартная для большинства языков программирования криптографическая функция
  - `authDate + phone + userId` — параметры в алфавитном порядке, используемые для вычисления хеша: сформируйте строку, объединив пары `key=value` с разделителем `\n`
  - `botToken` — токен бота, чьё мини-приложение запрашивает номер телефона пользователя

Если значения совпадают, это подтверждает, что пользователь поделился номером телефона, привязанным к его аккаунту в МАКС

> При вычислении хеша значение `phone` не должно содержать `+`: вместо `+7**********` используется `7**********`

**Возможные ошибки**

Если пользователь отказывается поделиться номером телефона или запрос завершился ошибкой, возвращает:

JSON

```
{
"error": {
"code": "client.request_phone.<reason>"
}
}
```

| Номер ошибки | Возможное значение `reason` | Описание ошибки |
| --- | --- | --- |
| 01 | `user_refused_provide_phone_number` | Пользователь отказался предоставить номер телефона |
| 02 | `request_error` | Ошибка при выполнении запроса (нет сети / не ответил backend) |

### Подтверждение закрытия мини-приложения

> Обратите внимание, что возможности из этой категории отправляют запрос клиенту MAX в **одностороннем порядке**

#### window.WebApp.enableClosingConfirmation()

Включает предупреждение о риске потерять заполненные данные, если закрыть мини-приложение

**Пример**

JAVASCRIPT

```
window.WebApp.enableClosingConfirmation()
```

#### window.WebApp.disableClosingConfirmation()

Выключает предупреждение о риске потерять заполненные данные, если закрыть мини-приложение

**Пример**

JAVASCRIPT

```
window.WebApp.disableClosingConfirmation()
```

### Открытие ссылок

Библиотека поддерживает два формата открытия ссылок:

- во внешнем браузере
- в виде диплинка, связанного с max.ru

#### window.WebApp.openLink(url)

Открывает ссылку во внешнем браузере

> Чтобы обезопасить процесс, перед вызовом метода MAX Bridge проверяет клик пользователя в мини-приложении. Если клика не было, перехода по ссылке не будет

**Тип передаваемых данных**

JAVASCRIPT

```
// URL веб-страницы, которую нужно открыть
url: string
```

**Пример**

JAVASCRIPT

```
// После вызова метода откроется ссылка во внешнем браузере
window.WebApp.openLink('https://max.ru/');
```

#### window.WebApp.openMaxLink(url)

Открывает диплинк вида `https://max.ru/<some-url>` из мини-приложения внутри MAX. Если передать ссылку другого вида, метод откроет её во внешнем браузере

**Тип передаваемых данных**

JAVASCRIPT

```
// Диплинк для клиента MAX
url: string
```

**Пример**

JAVASCRIPT

```
// Будет открыт нужный чат, контакт или мини-приложение в клиенте MAX
window.WebApp.openMaxLink('https://max.ru/<your-url>');
```

### Скачивание файла

Условие для скачивания файла — наличие защищённого `https`-соединения

> Чтобы обезопасить процесс, перед вызовом метода MAX Bridge проверяет клик пользователя в мини-приложении. Если клика не было, файл не будет скачан

#### window.WebApp.downloadFile(url, file\_name)

Скачивает файл по переданной `https`-ссылке под нужным названием

**Тип передаваемых данных**

JAVASCRIPT

```
url: string // URL для доступа к нужному ресурсу
file_name: string // Название файла
```

**Тип возвращаемых данных**

JAVASCRIPT

```
Promise<{
status: 'downloading' | 'cancelled';
}>
```

**Пример**

JAVASCRIPT

```
const fileName = 'My file'
const fileUrl = 'https://some-url/file'
window.WebApp.downloadFile(fileUrl, fileName).then(({status}) => {
if(status === 'downloading') {
console.log(`${fileName} загружается`)
}
});
```

### Шеринг контента

В библиотеке есть два способа для шеринга контента:

- во внешние приложения
- внутри MAX

#### window.WebApp.shareContent(params)

Вызывает нативный экран шеринга из мини-приложения на iOS, Android.
Передаются параметры `text` и/или `link`: один из параметров всегда должен быть передан. Разделение является условным и сделано для удобства восприятия: если передать и текст, и ссылку в одном поле `text`, то результат не изменится

> Этот метод **не поддерживается веб-клиентом**

**Тип передаваемых данных**

JAVASCRIPT

```
params: {
    text?: string;
    link?: string
}
```

**Тип возвращаемых данных**

JAVASCRIPT

```
Promise<{
status: 'shared' | 'cancelled';
}>
```

**Пример**

JAVASCRIPT

```
const text = 'Look at this'
const url = 'https://epic-video-url'
// Вызывается нативное окно шеринга во внешние приложения
window.WebApp.shareContent({text, link}).then(({status}) => {
if(status === 'shared') {
console.log('Сообщение было отправлено')
}
});
```

#### window.WebApp.shareMaxContent(params)

Открывает экран шеринга внутри MAX

> Чтобы обезопасить процесс, перед вызовом метода MAX Bridge проверяет клик пользователя в мини-приложении. Если клика не было, экран шеринга не откроется

Метод предоставляет возможность шеринга контента из мини-приложения в диалоги или групповые чаты MAX. Метод работает в двух режимах:

- шеринг текста, который аналогичен `WebApp.shareContent(params)`
- шеринг текста с контентом: файл, медиа

Для шеринга файла или медиа бот, на котором работает мини-приложение, предварительно отправляет контент пользователю через [POST/messages](../../docs-api/methods/POST/messages.md). Шеринг медиа работает как пересылка сообщения, поэтому поддерживается любой тип контента:

1. Бот отправляет контент пользователю, например медиафайл или открытку
2. Мини-приложение получает идентификатор этого сообщения `mid`. Его возвращает MAX Bot API, когда сообщение отправляется пользователю
3. В мини-приложении вызывается `shareMaxContent({ mid, chatType })`, где `mid` — идентификатор сообщения от бота, а `chatType` — тип чата, сообщением из которого нужно поделиться:
   - `DIALOG` — для диалога, личного чата между двумя пользователями
   - `CHAT` — для группового чата. Пользователь должен быть участником чата
4. Пользователь выбирает, куда отправить контент — сообщение пересылается в выбранный чат

В метод передаются либо `text` и/или `link`, либо `mid` и `chatType`. Если при шеринге медиа или файла передать `text` или `link`, они будут проигнорированы

**Тип передаваемых данных**

JAVASCRIPT

```
params: {
    text?: string;
    link?: string
} | {
mid: string;
chatType: 'DIALOG' | 'CHAT'
}
```

**Тип возвращаемых данных**

JAVASCRIPT

```
Promise<{
status: 'shared' | 'cancelled';
}>
```

**Пример**

JAVASCRIPT

```
const text = 'Look at this'
const url = 'https://epic-video-url'
// Отправит текст и ссылку в выбранный пользователем чат
window.WebApp.shareMaxContent({text, link}).then(({status}) => {
if(status === 'shared') {
console.log('Сообщение успешно отправлено')
}
if(status === 'cancelled') {
console.log('Пользователь закрыл шторку без шеринга')
}
})
const mid = `mid.<hash>`
const chatType = 'CHAT'
// Сообщение с файлом будет отправлено в выбранный пользователем чат
window.WebApp.shareMaxContent({mid, chatType}).then(({status}) => {
if(status === 'shared') {
console.log('Сообщение c файлом успешно отправлено')
}
if(status === 'cancelled') {
console.log('Пользователь закрыл шторку без шеринга')
}
})
```

### Сканирование QR-кодов

Библиотекой предусмотрено два режима работы:

- сканирование QR-кода камерой
- выбор файла для сканирования из файловой системы

По умолчанию установлен режим выбора файла из системы

#### window.WebApp.openCodeReader(fileSelect = true)

Открывает камеру для считывания QR-кода

**Тип передаваемых данных**

JAVASCRIPT

```
// Использовать файл из системы или сканировать камерой
fileSelect: boolean
```

**Тип возвращаемых данных**

JAVASCRIPT

```
Promise<{
value: string;
}>
```

**Пример**

JAVASCRIPT

```
window.WebApp.openCodeReader().then(({value}) => {
console.log('Данные с QR-кода', value)
})
```

Клиент вернёт результат в виде строки, если QR-код был найден и распознан

- `fileSelect = true` — доступен также выбор из галереи
- `fileSelect = false` — доступно сканирование только через камеру

Если `fileSelect` не передан, то по умолчанию считается `fileSelect = true`

### Управление кнопкой «Назад» в шапке приложения

Управление кнопкой **Назад** происходит через объект `BackButton`

#### window.WebApp.BackButton.show()

Делает кнопку **Назад** активной и видимой

**Пример**

JAVASCRIPT

```
window.WebApp.BackButton.show()
```

#### window.WebApp.BackButton.hide()

Скрывает кнопку **Назад**

**Пример**

JAVASCRIPT

```
window.WebApp.BackButton.hide()
```

#### window.WebApp.BackButton.isVisible

Управляет отображением кнопки **Назад** в заголовке мини-приложения в интерфейсе MAX

**Тип возвращаемых данных**

JAVASCRIPT

```
boolean
```

**Пример**

JAVASCRIPT

```
window.WebApp.BackButton.isVisible
// isVisible = true — кнопка отображается
// isVisible = false — кнопка не отображается
```

> Значение false задано по умолчанию

#### window.WebApp.BackButton.onClick(callback)

Устанавливает обработчик событий нажатия на кнопку **Назад**

> Чтобы оставить возможность отписки от события нажатия на кнопку, сохраните ссылку на функцию, которая будет передана в качестве callbcak

**Тип передаваемых данных**

JAVASCRIPT

```
callback: () => void
```

**Пример**

JAVASCRIPT

```
const onBackButtonPress = () => {
console.log('Кнопка назад была нажата')
}
window.WebApp.BackButton.onClick(onBackButtonPress)
```

#### window.WebApp.BackButton.offClick(callback)

Отключает обработчик событий нажатия кнопки **Назад**

**Тип передаваемых данных**

JAVASCRIPT

```
callback: () => void
```

**Пример**

JAVASCRIPT

```
const onBackButtonPress = () => {
console.log('Кнопка назад была нажата')
}
// Подписаться на событие нажатия
window.WebApp.BackButton.onClick(onBackButtonPress)
// Отписаться от события нажатия
window.WebApp.BackButton.offClick(onBackButtonPress)
```

### Хранилище устройства

С помощью `DeviceStorage` можно сохранять данные на устройстве пользователя. Объект предоставляет мини-приложению доступ к хранилищу данных, ассоциированному с конкретным пользователем MАХ

> Методы этого объекта **не поддерживаются веб-клиентом**

#### window.WebApp.DeviceStorage.setItem(key, value)

Сохраняет переданную пару «ключ-значение» в локальном хранилище устройства для этого мини-приложения

**Тип передаваемых данных**

JAVASCRIPT

```
key: string
value: string
```

**Тип возвращаемых данных**

JAVASCRIPT

```
Promise<{
status: 'updated' | 'removed'
}>
```

**Пример**

JAVASCRIPT

```
const key = 'key'
const value = 'value'
window.WebApp.DeviceStorage.setItem(key, value).then(({status}) => {
if(status === 'updated') {
console.log(`Данные [${key}]: ${value} успешно сохранены`)
}
});
```

#### window.WebApp.DeviceStorage.getItem(key)

Получает значение из локального хранилища устройства по указанному ключу

**Тип передаваемых данных**

JAVASCRIPT

```
key: string
```

**Тип возвращаемых данных**

JAVASCRIPT

```
Promise<{
key: string;
value: string;
}>
```

**Пример**

JAVASCRIPT

```
const key = 'storageEntryKey'
window.WebApp.DeviceStorage.getItem(getKey).then((result) => {
console.log(result) // {key: 'storageEntryKey', value: 'some value'}
});
```

#### window.WebApp.DeviceStorage.removeItem(key)

Удаляет значение из локального хранилища устройства по указанному ключу

**Тип передаваемых данных**

JAVASCRIPT

```
key: string
```

**Тип возвращаемых данных**

JAVASCRIPT

```
Promise<{
status: 'updated' | 'removed'
}>
```

**Пример**

JAVASCRIPT

```
const key = 'key'
window.WebApp.DeviceStorage.removeItem(key).then(({status}) => {
if(status === 'removed') {
console.log(`Данные по ключу ${key} успешно удалены`)
}
});
```

#### window.WebApp.DeviceStorage.clear()

Очищает все ключи, ранее сохранённые ботом в локальном хранилище устройства

**Пример**

JAVASCRIPT

```
// Хранилище очищено
window.WebApp.DeviceStorage.clear();
```

### Защищённое хранилище устройства

С помощью объекта `SecureStorage` можно получить доступ к безопасному хранилищу конфиденциальных данных на устройстве пользователя.
Это гарантирует, что все сохраненные значения зашифрованы и недоступны для неавторизованных приложений

Защищённое хранилище подходит для хранения токенов, секретов, состояния аутентификации и другой конфиденциальной пользовательской информации.
Каждый бот может хранить до 10 ключей на пользователя

> Методы этого объекта **не поддерживаются веб-клиентом**

#### window.WebApp.SecureStorage.setItem(key, value)

Сохраняет переданную пару «ключ-значение» в защищённом хранилище устройства

**Тип передаваемых данных**

JAVASCRIPT

```
key: string
value: string
```

**Тип возвращаемых данных**

JAVASCRIPT

```
Promise<{
status: 'updated' | 'removed'
}>
```

**Пример**

JAVASCRIPT

```
const key = 'key'
const value = 'value'
window.WebApp.SecureStorage.setItem(key, value).then(({status}) => {
if(status === 'updated') {
console.log(`Данные [${key}]: ${value} успешно сохранены`)
}
});
```

#### window.WebApp.SecureStorage.getItem(key)

Получает значение из защищённого хранилища устройства по указанному ключу

**Тип передаваемых данных**

JAVASCRIPT

```
key: string
```

**Тип возвращаемых данных**

JAVASCRIPT

```
Promise<{
key: string;
value: string;
}>
```

**Пример**

JAVASCRIPT

```
const key = 'secureStorageEntryKey'
window.WebApp.SecureStorage.getItem(getKey).then((result) => {
console.log(result) // {key: 'secureStorageEntryKey', value: 'some value'}
});
```

#### window.WebApp.SecureStorage.removeItem(key)

Удаляет значение из защищённого хранилища устройства по указанному ключу

**Тип передаваемых данных**

JAVASCRIPT

```
key: string
```

**Тип возвращаемых данных**

JAVASCRIPT

```
Promise<{
status: 'updated' | 'removed'
}>
```

**Пример**

JAVASCRIPT

```
const key = 'key'
window.WebApp.SecureStorage.removeItem(key).then(({status}) => {
if(status === 'removed') {
console.log(`Данные по ключу ${key} успешно удалены`)
}
});
```

#### window.WebApp.SecureStorage.clear()

Очищает все ключи, ранее сохранённые в защищённом хранилище устройства

**Пример**

JAVASCRIPT

```
// Хранилище очищено
window.WebApp.SecureStorage.clear();
```

### Использование биометрии

Работа с биометрией доступна через объект `BiometricManager`. Он нужен для аутентификации, когда доступ к данным в `keychain` получается через биометрические идентификаторы

> Методы этого объекта **не поддерживаются десктоп и веб-клиентом**

#### window.WebApp.BiometricManager.init()

Перед использованием методов объекта `BiometricManager` нужно однократно вызвать метод первичной инициализации биометрии — `init`:

- Проверяет наличие функции биометрии на устройстве
- Проверяет, предоставлен ли доступ к биометрии на устройстве

**Тип возвращаемых данных**

JAVASCRIPT

```
type BiometryType = 'finger' | 'face' | 'unknown';
interface BiometryInfo {
available: boolean;
type: BiometryType[];
accessRequested: boolean;
accessGranted: boolean;
tokenSaved: boolean;
deviceId: string | null;
}
Promise<BiometryInfo>
```

| Поле | Тип данных | Описание |
| --- | --- | --- |
| `available` | `boolean` | Проверка доступности биометрии на устройстве пользователя, который запустил мини-приложение |
| `type` | `array` | Типы биометрии: `fingerprint`, `faceid`, `unknown`     Если пользователь отказался предоставить доступ к биометрии, то `biometricType= array<unknown>`. Для Android всегда `unknown` |
| `accessRequested` | `boolean` | Проверка отправки запроса на предоставление доступа к биометрии устройства     Если пользователь отказался предоставить доступ к биометрии, то `accessRequested = false` |
| `accessGranted` | `boolean` | Проверка предоставления доступа к биометрии |
| `tokenSaved` | `boolean` | Проверка наличия токена авторизации через биометрию в безопасном хранилище устройства |
| `deviceId` | `string` | Идентификатор устройства — можно использовать для сопоставления токена с устройством |

**Пример**

JAVASCRIPT

```
window.WebApp.BiometricManager.init().then((biometricManagerData) => {
console.log('Данные менеджера биометрии', biometricManagerData)
});
```

#### window.WebApp.BiometricManager.isInited

Получает состояние инициализации `BiometricManager` — была ли ранее первичная инициализация

**Тип возвращаемых данных**

JAVASCRIPT

```
boolean
```

**Пример**

JAVASCRIPT

```
// true или false
window.WebApp.BiometricManager.isInited
```

#### window.WebApp.BiometricManager.isBiometricAvailable

Проверяет доступность биометрии на устройстве пользователя, который запустил мини-приложение

**Тип возвращаемых данных**

JAVASCRIPT

```
boolean
```

**Пример**

JAVASCRIPT

```
// true или false
window.WebApp.BiometricManager.isBiometricAvailable
```

Если пользователь отказался предоставить доступ к биометрии, значение будет `false`

#### window.WebApp.BiometricManager.isAccessRequested

Проверяет, был ли ранее отправлен запрос на предоставление доступа к биометрии устройства

**Тип возвращаемых данных**

JAVASCRIPT

```
boolean
```

**Пример**

JAVASCRIPT

```
// true или false
window.WebApp.BiometricManager.isAccessRequested
```

Если пользователь отказался предоставить доступ к биометрии, значение будет `false`

#### window.WebApp.BiometricManager.isAccessGranted

Проверяет, предоставлен ли доступ к биометрии

**Тип возвращаемых данных**

JAVASCRIPT

```
boolean
```

**Пример**

JAVASCRIPT

```
// true или false
window.WebApp.BiometricManager.isAccessGranted
```

Если пользователь отказался предоставить доступ к биометрии, значение будет `false`

#### window.WebApp.BiometricManager.isBiometricTokenSaved

Проверяет наличие токена в безопасном хранилище устройства

**Тип возвращаемых данных**

JAVASCRIPT

```
boolean
```

**Пример**

JAVASCRIPT

```
// true или false
window.WebApp.BiometricManager.isBiometricTokenSaved
```

Если пользователь отказался предоставить доступ к биометрии, значение будет `false`

#### window.WebApp.BiometricManager.biometricType

Позволяет посмотреть доступные типы биометрии:

- `fingerprint`
- `faceid`
- `unknown`

**Тип возвращаемых данных**

JAVASCRIPT

```
Array<'finger' | 'face' | 'unknown'>
```

**Пример**

JAVASCRIPT

```
window.WebApp.BiometricManager.biometricType
```

Если пользователь отказался предоставить доступ к биометрии, то `biometricType=["unknown"]`

Для Android всегда `["unknown"]`

#### window.WebApp.BiometricManager.deviceId

Возвращает идентификатор устройства — можно использовать для сопоставления токена с устройством

**Тип возвращаемых данных**

JAVASCRIPT

```
string | null
```

**Пример**

JAVASCRIPT

```
window.WebApp.BiometricManager.deviceId
```

Возвращает `null`, если пользователь отказался предоставить доступ к биометрии

#### window.WebApp.BiometricManager.requestAccess(reason)

Отправляет запрос на доступ к использованию биометрии на устройстве

Возвращает тип данных `BiometryInfo`, подробнее — в подразделе про [использование биометрии](bridge.md#%D0%98%D1%81%D0%BF%D0%BE%D0%BB%D1%8C%D0%B7%D0%BE%D0%B2%D0%B0%D0%BD%D0%B8%D0%B5%20%D0%B1%D0%B8%D0%BE%D0%BC%D0%B5%D1%82%D1%80%D0%B8%D0%B8)

**Тип передаваемых данных**

JAVASCRIPT

```
// Причина запроса мини-приложения на использование доступа
// Размер: 1-128 символов, остальное будет отрезаться
// Необязательное поле
reason?: string
```

**Тип возвращаемых данных**

JAVASCRIPT

```
Promise<BiometryInfo>
```

**Пример**

JAVASCRIPT

```
const reason = 'some reason'
window.WebApp.BiometricManager.requestAccess(reason).then((response) => {
console.log('Данные биометрии', response)
})
```

#### window.WebApp.BiometricManager.authenticate(reason)

Запускает процесс аутентификации при помощи биометрических данных

**Тип передаваемых данных**

JAVASCRIPT

```
// Причина запроса мини-приложения на использование доступа
// Размер: 1-128 символов, остальное будет отрезаться
// Необязательное поле
reason?: string
```

**Тип возвращаемых данных**

JAVASCRIPT

```
Promise<{
status: 'authorized';
token: string;
}>
```

**Пример**

JAVASCRIPT

```
const reason = 'some reason'
window.WebApp.BiometricManager.authenticate(reason).then(({token}) => {
console.log('Авторизационный токен', token)
})
```

#### window.WebApp.BiometricManager.updateBiometricToken(token, reason)

Обновляет биометрический токен в безопасном хранилище устройства

> Для удаления токена вызовите метод без передачи параметра токена

**Тип передаваемых данных**

JAVASCRIPT

```
token?: string
// Причина запроса мини-приложения на использование доступа
// Размер: 1-128 символов, остальное будет отрезаться
// Необязательное поле
reason?: string
```

**Тип возвращаемых данных**

JAVASCRIPT

```
Promise<{
status: 'updated' | 'removed';
}>
```

**Пример**

JAVASCRIPT

```
const reason = 'some reason'
const {token} = await window.WebApp.BiometricManager.authenticate(reason)
// Обновление/сохранение токена
window.WebApp.BiometricManager.updateBiometricToken(token).then((response) => {
console.log('Биометрический токен успешно обновлен')
})
// Удаление токена
window.WebApp.BiometricManager.updateBiometricToken().then(({status}) => {
if(status === 'removed') {
console.log('Биометрический токен успешно удален')
}
})
```

#### window.WebApp.BiometricManager.openSettings()

Отображает нативное диалоговое окно с предложением перейти в настройки MAХ на экран приватности, чтобы дать доступ к биометрии устройства для мини-приложения

Вызывает закрытие мини-приложения

**Тип возвращаемых данных**

JAVASCRIPT

```
Promise<{
status: 'opened'
}>
```

**Пример**

JAVASCRIPT

```
// Откроется диалоговое окно
window.WebApp.BiometricManager.openSettings()
```

### Тактильные отклики

Чтобы активировать и настроить тактильную обратную связь при взаимодействии пользователя с веб-приложением, используйте объект `HapticFeedback`

> Методы этого объекта **не поддерживаются десктоп и веб-клиентом**

#### window.WebApp.HapticFeedback.impactOccurred(impactStyle, disableVibrationFallback)

С помощью этого метода приложение MAX может воспроизвести соответствующие тактильные эффекты на основе переданного значения стиля

Подходит для тактильного отклика на интерактивные элементы, например при нажатии на кнопку

Стиль может иметь одно из следующих значений:

- `soft` — мягкая вибрация
- `light` — лёгкая вибрация
- `medium` — средняя вибрация
- `heavy` — сильная вибрация
- `rigid` — жёсткая вибрация

`disableVibrationFallback` — разрешение использовать вибрацию с постоянной амплитудой на устройствах, которые не поддерживают вибрацию с переменной амплитудой. Значение по умолчанию: `false`

**Тип передаваемых данных**

JAVASCRIPT

```
impactStyle: 'light' | 'medium' | 'heavy' | 'rigid' | 'soft'
disableVibrationFallback?: boolean // По умолчанию false
```

**Тип возвращаемых данных**

JAVASCRIPT

```
Promise<{
status: 'impactOccured'
}>
```

**Пример**

JAVASCRIPT

```
window.WebApp.HapticFeedback.impactOccurred('light').then(() => {
console.log('Произошло тактильное воздействие')
});
```

#### window.WebApp.HapticFeedback.notificationOccurred(notificationType, disableVibrationFallback)

Возвращает статус событий или действий: выполнены успешно, не удалось выполнить или выдано предупреждение

Приложение MAХ может воспроизводить соответствующие тактильные сигналы на основе переданного значения типа. Тип может быть одним из следующих значений:

- `error` — не удалось выполнить
- `success` — выполнены успешно
- `warning` — выдано предупреждение

`disableVibrationFallback` — разрешение использовать вибрацию с постоянной амплитудой на устройствах, которые не поддерживают вибрацию с переменной амплитудой. Значение по умолчанию: `false`

**Тип передаваемых данных**

JAVASCRIPT

```
impactStyle: 'error' | 'success' | 'warning'
disableVibrationFallback?: boolean // По умолчанию false
```

**Тип возвращаемых данных**

JAVASCRIPT

```
Promise<{
status: 'notificationOccured'
}>
```

**Пример**

JAVASCRIPT

```
window.WebApp.HapticFeedback.notificationOccurred('error').then(() => {
console.log('Появилось тактильное уведомление об ошибке')
});
```

#### window.WebApp.HapticFeedback.selectionChanged(disableVibrationFallback)

Сообщает, что пользователь изменил выбор

Приложение MAX может воспроизвести соответствующие тактильные сигналы

> Не используйте эту обратную связь, когда пользователь делает или подтверждает выбор. Используйте её только при изменении выбора

`disableVibrationFallback` — разрешение использовать вибрацию с постоянной амплитудой на устройствах, которые не поддерживают вибрацию с переменной амплитудой. Значение по умолчанию: `false`

**Тип передаваемых данных**

JAVASCRIPT

```
// По умолчанию false
disableVibrationFallback?: boolean
```

**Тип возвращаемых данных**

JAVASCRIPT

```
Promise<{
status: 'selectionChanged'
}>
```

**Пример**

JAVASCRIPT

```
window.WebApp.HapticFeedback.selectionChanged().then(() => {
console.log('Сработал тактильный отклик на действие пользователя')
});
```

### NFC-модуль

Работа с NFC-модулем доступна через объект `NfcManager`

> Методы этого объекта **поддерживаются только для Android**

Чтобы начать использовать методы объекта `NfcManager`, необходимо сначала вызвать его метод инициализации `init`

#### window.WebApp.NfcManager.init()

Инициализирует `NfcManager`

**Тип возвращаемых данных**

JAVASCRIPT

```
interface NfcInfo {
available: boolean;
enabled: boolean;
  accessRevoked?: boolean;
}
```

**Описание свойств объекта**

| Поле | Тип данных | Описание |
| --- | --- | --- |
| `available` | `boolean` | Проверка наличия NFC-модуля на устройстве пользователя |
| `enabled` | `boolean` | Проверка включения NFC-модуля в настройках системы |
| `accessRevoked?` | `boolean` | Отозвал ли пользователь разрешение использовать NFC-модуль для текущего мини-приложения в настройках приватности MAX |

**Пример**

JAVASCRIPT

```
window.WebApp.NfcManager.init().then((nfcManagerData) => {
console.log('Данные менеджера NFC', nfcManagerData)
});
```

#### window.WebApp.NfcManager.isInited

Возвращает состояние инициализации `NfcManager`

**Тип возвращаемых данных**

JAVASCRIPT

```
boolean
```

**Пример**

JAVASCRIPT

```
window.WebApp.NfcManager.isInited // true или false
```

#### window.WebApp.NfcManager.openSystemSettings()

Открывает страницу системных настроек доступа к NFC-модулю и вызывает закрытие мини-приложения

> Если пользователь не отключал NFC-модуль, то переход не будет выполнен

**Тип возвращаемых данных**

JAVASCRIPT

```
Promise<{
status: 'opened'
}>
```

**Пример**

JAVASCRIPT

```
// Откроются системные настройки
window.WebApp.NfcManager.openSystemSettings()
```

#### window.WebApp.NfcManager.emulateNfcTag(nfctag)

Запускает через NFC-модуль передачу данных, полученных из мини-приложения

> Если не передать данные NFC-метки, то вещание будет остановлено

**Тип передаваемых данных**

JAVASCRIPT

```
nfctag?: 'string'
```

**Тип возвращаемых данных**

JAVASCRIPT

```
Promise<{
status: 'scanned' | 'stopped'
}>
```

**Пример**

JAVASCRIPT

```
const nfcTagData = 'Some data'
window.WebApp.NfcManager.emulateNfcTag(nfcTagData).then(({status}) => {
console.log('NFC метка отсканирована')
});
window.WebApp.NfcManager.emulateNfcTag().then(({status}) => {
if(status === 'stopped') {
console.log('Вещание остановлено')
}
});
```

## Ошибки и обработка исключений

Большинство методов возвращают Promise-объекты, и в случае ошибки вызывается `reject`

**Объект ошибки имеет структуру**

JAVASCRIPT

```
{
error: {
code: string
    }
}
```

**Пример**

JAVASCRIPT

```
window.WebApp.SecureStorage.setItem('key', 'value')
.then((result) => {
console.log('Успешно сохранено');
})
.catch(({error}) => {
console.error('Произошла ошибка:', error.code);
});
```
