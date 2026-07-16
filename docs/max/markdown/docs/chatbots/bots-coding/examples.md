<!-- source: https://dev.max.ru/docs/chatbots/bots-coding/examples -->
> Источник: https://dev.max.ru/docs/chatbots/bots-coding/examples

# Примеры создания ботов

Пример создания демонстрационного **To-do list-бота** вы можете посмотреть в нашем [репозитории](https://github.com/max-messenger/max-bot-example-todolist)

## Примеры создания Hello-бота с помощью библиотек JavaScript и Golang

В этом разделе разберём пример реализации простого бота с использованием библиотеки MAX Bot API — напишем код для Hello Bot, чтобы научить его здороваться с пользователями

Больше примеров смотрите в наших репозиториях на GitHub:

- [JavaScript](https://github.com/max-messenger/max-bot-api-client-ts)
- [Golang](https://github.com/max-messenger/max-bot-api-client-go)

1. Создайте новый проект в терминале и установите библиотеку:

JavaScript

Golang

BASH

```
# Создайте папку и перейдите в неё
mkdir my-first-bot
cd my-first-bot

# Установите MAX Bot API
# Для npm
npm install --save @maxhub/max-bot-api
# Для yarn
yarn add @maxhub/max-bot-api
# Для pnpm
pnpm add @maxhub/max-bot-api
# Для deno
deno add npm:@maxhub/max-bot-api

# Установите и настройте TypeScript (опционально)
yarn add -D typescript
npx tsc --init
```

2. Создайте файл:

- для JavaScript — `bot.js`, TypeScript — `bot.ts`
- для Golang — `bot.go`

3. Обеспечьте доступ к методам и утилитам

JavaScript

Golang

JAVASCRIPT

```
# Создайте объект класса класса Bot — он обеспечит доступ к методам и утилитам

filename="bot.js"
import { Bot } from '@maxhub/max-bot-api';
const bot = new Bot(process.env.BOT_TOKEN); // Токен, полученный при регистрации бота в MAX
bot.start(); // Запускает получение обновлений
```

4. Определите функциональность приветствия — бот будет отвечать на команду `/hello`

JavaScript

Golang

JAVASCRIPT

```
filename="bot.js"
import { Bot } from '@maxhub/max-bot-api';
const bot = new Bot(process.env.BOT_TOKEN);
// Устанавливает список команд, который пользователь будет видеть в чате с ботом
bot.api.setMyCommands([
{
name: 'hello',
description: 'Поприветствовать бота',
},
]);
// Обработчик команды '/hello'
bot.command('hello', (ctx) => {
return ctx.reply('Привет! ✨');
});
bot.start();
```

5. Протестируйте бота — отправьте команду `/hello`

![](https://dev.max.ru/assets/hello_light.png)
*Чат с Hello Bot*

  

![ℹ️](https://dev.max.ru/assets/emoji/information_2139-fe0f.png) Если у вас возникли вопросы, [посмотрите раздел с ответами](../../../help.md)

Готово! Вы написали простого и дружелюбного Hello Bot. Воспользуйтесь возможностями и инструментами платформы MAX, чтобы запустить на платформе собственные проекты
