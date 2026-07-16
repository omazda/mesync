<!-- source: https://dev.max.ru/docs/chatbots/bots-coding/go -->
> Источник: https://dev.max.ru/docs/chatbots/bots-coding/go

# Работа с библиотекой Golang

Если вы пишете ботов на GO, рекомендуем использовать нашу официальную библиотеку MAX Bot API. Расширенную версию библиотеки с примерами реализации смотрите [на GitHub](https://github.com/max-messenger/max-bot-api-client-go)

В этом разделе разберём, как подключить библиотеку MAX Bot API и эффективно использовать стандартные методы и утилиты, которыми она располагает

## Установка MAX Bot API

Чтобы установить библиотеку MAX Bot API, зарегистрируйте бота на платформе и подключитесь к API MAX — следуйте подсказкам [в разделе «Подготовка и настройка бота»](prepare.md)

Все примеры в этом разделе написаны на GO с переменными окружения

1. Создайте новый проект `my-first-bot` и установите библиотеку. Для этого откройте терминал и выполните следующие команды:

BASH

```
# Создайте новую папку для исходного кода вашего модуля Go и перейдите в неё
mkdir my-first-bot
cd my-first-bot
# Запустите свой модуль с помощью команды go mod init.
go mod init first-max-bot

# Установите библиотеку для работы с MAX API на golang
go get github.com/max-messenger/max-bot-api-client-go
```

Команда `go mod init` создает файл `go.mod` для отслеживания зависимостей вашего кода. Пока что файл включает только имя вашего модуля и версию Go, которую поддерживает ваш код

2. Теперь создайте файл, например, `bot.go`

Весь код в языке Go организуется в пакеты. Пакеты представляют удобную организацию разделения кода на отдельные части или модули. Модульность позволяет определять один раз пакет с нужной функциональностью и потом использовать его многократно в различных программах. Код пакета располагается в одном или нескольких файлах с расширением `go`. Для определения пакета применяется ключевое слово package. Поэтому наш файл `bot.go` будет иметь следующую структуру

GO

```
package main
import "fmt"
func main() {
    fmt.Println("Hello Max Bot Go")
}
```

bot.go

В данном случае пакет называется `main`. Определение пакета должно идти в начале файла

Есть два типа пакетов: исполняемые (`executable`) и библиотеки (`reusable`). Для создания исполняемых файлов пакет должен иметь имя `main`. Все остальные пакеты не являются исполняемыми. При этом пакет `main` должен содержать функцию `main`, которая является входной точкой в приложение

3. Создайте экземпляр класса Bot и передайте [токен бота](../bots-nocode/manage.md#%D0%93%D0%B4%D0%B5%20%D0%BF%D0%BE%D1%81%D0%BC%D0%BE%D1%82%D1%80%D0%B5%D1%82%D1%8C%20%D1%82%D0%BE%D0%BA%D0%B5%D0%BD%20%D0%B1%D0%BE%D1%82%D0%B0) из его настроек (карточки) в конструктор через переменные окружения. Импортируйте в наш пакет `main` установленный [модуль](https://github.com/max-messenger/max-bot-api-client-go)

GO

```
package main
import (
"fmt"
    maxbot "github.com/max-messenger/max-bot-api-client-go"
)
func main() {
    api := maxbot.New(os.Getenv("TOKEN"))
// Some methods demo:
    info, err := api.Bots.GetBot()
    fmt.Printf("Get me: %#v %#v", info, err)
}
```

bot.go

Код выше создаёт объект `api`, передавая токен в его конструктор `New`. Мы рекомендуем передавать токен через переменные окружения, т. к. использовать токен в коде — плохая практика

4. Запустите бота

BASH

```
# Передайте переменную окружения и запустите бота
TOKEN="<your_token_here>" go run
```

## Работа с обновлениями

Данная программа выведет только информацию о вашем боте и закончит работу. Чтобы бот заработал, необходим обработчик событий из канала с обновлениями

GO

```
package main
import (
"fmt"
    maxbot "github.com/max-messenger/max-bot-api-client-go"
)
func main() {
    api := maxbot.New(os.Getenv("TOKEN"))
// Some methods demo:
    info, err := api.Bots.GetBot()
    fmt.Printf("Get me: %#v %#v", info, err)

    ctx, cancel := context.WithCancel(context.Background()) // создам
go func() {
        exit := make(chan os.Signal)
        signal.Notify(exit, os.Kill, os.Interrupt)
<-exit
        cancel()
}()
for upd := range api.GetUpdates(ctx) { // Чтение из канала с обновлениями
switch upd := upd.(type) { // Определение типа пришедшего обновления
case *schemes.MessageCreatedUpdate:
// Отправка сообщения
_, err := api.Messages.Send(maxbot.NewMessage().SetChat(upd.Message.Recipient.ChatId).SetText("Hello from Bot"))
}
}
}
```

Поздравляем, вы написали первого бота!

  

![ℹ️](https://dev.max.ru/assets/emoji/information_2139-fe0f.png) Если у вас возникли вопросы, [посмотрите раздел с ответами](../../../help.md)
