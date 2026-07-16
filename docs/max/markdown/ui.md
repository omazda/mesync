<!-- source: https://dev.max.ru/ui -->
> Источник: https://dev.max.ru/ui

# Обзор

[MAX UI](https://github.com/max-messenger/max-ui) — библиотека React-компонентов для создания мини-приложений в MAX, сторонних суперприложений, а также standalone-приложений. Готовые компоненты библиотеки умеют подстраиваться под разные платформы и устройства

## Особенности MAX UI

- Дизайн-система MAX
    
  Библиотека компонентов разработана на основе дизайн-системы MAX, что позволяет мини-приложениям выглядеть гармонично в интерфейсе цифровой платформы
- Единообразие на разных платформах
    
  Компоненты библиотеки органично встраиваются в мобильные платформы iOS и Android, а также в экраны устройств разного размера
- Современный UI Kit
    
  Typescript, React 18+, полиморфные компоненты и подробная документация с примерами

> Знаете, как улучшить MAX UI? Мы открыты к предложениям:  
> • Чтобы сообщить об ошибках в библиотеке, [создайте issue](https://github.com/max-messenger/max-ui/issues) в [репозитории MAX UI](https://github.com/max-messenger/max-ui)  
> • Чтобы предложить идею, создайте форк библиотеки и откройте pull request

## Подключаем библиотеку MAX UI

Установите библиотеку одной из команд

SHELL

```
npm i @maxhub/max-ui
yarn add @maxhub/max-ui
pnpm add @maxhub/max-ui
```

Оберните код вашего приложения в провайдер MAX UI и подключите стили

JSX

```
import { createRoot } from 'react-dom/client';
import { MaxUI } from '@maxhub/max-ui';
import '@maxhub/max-ui/dist/styles.css';
import App from './App.jsx';
const Root = () => (
<MaxUI>
<App />
</MaxUI>
)
createRoot(document.getElementById('root')).render(<Root />);
```

index.jsx

Используйте компоненты библиотеки

JSX

```
import { Panel, Grid, Container, Flex, Avatar, Typography } from '@maxhub/max-ui';
const App = () => (
<Panel mode="secondary" className="panel">
<Grid gap={12} cols={1}>
<Container className="me">
<Flex direction="column" align="center">
<Avatar.Container size={72} form="squircle" className="me__avatar">
<Avatar.Image src="https://sun9-21.userapi.com/1N-rJz6-7hoTDW7MhpWe19e_R_TdGV6Wu5ZC0A/67o6-apnAks.jpg" />
</Avatar.Container>
<Typography.Title>Иван Иванов</Typography.Title>
</Flex>
</Container>
</Grid>
</Panel>
)
export default App;
```

App.jsx

## Компоненты

Компоненты библиотеки MAX UI мимикрируют под нативные компоненты iOS и Android и умеют поддерживать светлую и тёмную темы оформления. Тема и платформа определяются автоматически в провайдере MaxUI, но могут быть переопределены через свойства `platform` (`'ios'` | `'android'`) и `colorScheme` (`'light'` | `'dark'`)

JSX

```
import { createRoot } from 'react-dom/client';
import { MaxUI } from '@maxhub/max-ui';
import '@maxhub/max-ui/dist/styles.css';
import App from './App.jsx';
const Root = () => (
    <MaxUI platform="android" colorScheme="dark">
        <App />
    </MaxUI>
)
createRoot(document.getElementById('root')).render(<Root />);
```

### Полиморфные компоненты

Полиморфность компонентов реализована через паттерн asChild prop: это позволяет предотвратить ошибки типизации и не увеличивать время typescript-процессинга

В DOM полиморфные компоненты могут быть представлены в виде тегов. Например, компонент Button — как button, a, span и так далее

| React-компонент | DOM\* |
| --- | --- |
| <Button> Я — кнопка </Button> | <button class="btn-classes"> Я — кнопка </button> |
| <Button asChild> <a href="#">Я — ссылка!</a> </Button> | <a class="btn-classes" href="#"> Я — ссылка! </a> |
| import { Link } from "react-router-dom";  <Button asChild> <Link to="/home">Я — ссылка RRD!</a> </Button> | <a class="btn-classes" href="/home"> Я — ссылка RRD! </a> |
|  | \*упрощённое представление компонента |

### Корнер-кейс с asChild

Паттерн `asChild` prop может привести к конфликту свойств, если у одинаковых свойств родительского и дочернего компонентов разные значения. В этом случае свойства `className`, `style` и обработчики событий on\* (`onClick`, `onChange` и другие) объединяются. В остальных случаях приоритет остаётся у свойств родительского компонента

| React-компонент | DOM\* |
| --- | --- |
| <Button disabled={true} asChild> <button disabled={false}> Кнопка </button> | </Button> <button class="btn-classes" disabled> Я — кнопка </button> |
| <Button style={{ color: 'red' }} asChild> <button style={{ background: 'green' }}> Кнопка </button> | </Button> <button class="btn-classes" style={{ color: 'red', background: 'green' }}> Я — кнопка </button> |
|  | \*упрощённое представление компонента |

### Кастомизация компонентов

![ℹ️](https://dev.max.ru/assets/emoji/information_2139-fe0f.png) Библиотека предоставляет API для кастомизации, но не гарантирует отсутствие изменений в следующих мажорных версиях. Любая кастомизация компонентов — ответственность разработчика мини-приложения

В MAX UI есть два способа кастомизации компонентов — переопределение CSS-переменных и свойство `innerClassNames`

- Переопределение CSS-переменных
    
  Все токены дизайн-системы MAX заданы в CSS-переменных. Вы можете переопределить переменные как для конкретного компонента, так и для всей темы в целом
- Свойство `innerClassNames`
    
  Многосоставные компоненты, например `Button`, имеют свойство `innerClassNames`. Он позволяет указать `className` для внутренних элементов

| React-компонент | DOM\* |
| --- | --- |
| <Button     disabled={true}    iconBefore={<svg />} >    Кнопка с иконкой </Button> | <button class="btn-classes">    <span class="icon-before-classes">       <svg />    </span>    <span>Я — кнопка</span> </button> |
| <Button     disabled={true}    iconBefore={<svg />}    innerClassNames={{       iconBefore: 'my-custom-icon-class'    }} >    Кнопка с иконкой </Button> | <button class="btn-classes">    <span class="icon-before-classes my-custom-icon-class">       <svg />    </span>    <span>Я — кнопка</span> </button> |
|  | \*упрощённое представление компонента |

  

![ℹ️](https://dev.max.ru/assets/emoji/information_2139-fe0f.png) Если у вас возникли вопросы, [посмотрите раздел с ответами](help.md)
