<!-- Источник: https://yookassa.ru/developers/payment-acceptance/integration-scenarios/checkout-js/basics -->
<!-- Полная копия статьи официальной документации ЮKassa, сохранено 2026-07-02 -->

# Checkout.js

Checkout.js — это JavaScript-библиотека, дополнение к API ЮKassa.

Библиотека позволяет собирать данные банковских карт пользователей на вашей стороне, без необходимости обрабатывать их на ваших серверах. Это значит, что пользователи смогут вводить все данные банковской карты прямо в вашей системе.

С помощью этой библиотеки вы сможете:

- создавать формы в любом дизайне (например, в вашем стиле и с вашим логотипом);
- встраивать их в вашу систему так, как вам удобно;
- проводить тестирование на своей стороне и оптимизировать процесс оплаты.

Чтобы вам не пришлось обрабатывать платежные данные в своей системе, Checkout.js обменивает данные, которые ввел пользователь, на одноразовый платежный токен. Вам нужно отправить этот токен в запросе на [создание платежа](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/checkout-js/payments-with-tokens).

Если вам нужна форма с готовым дизайном, используйте [виджет ЮKassa](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/basics).

Что почитать еще

[Виджет ЮKassa](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/basics)

[Проведение платежа с использованием токена](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/checkout-js/payments-with-tokens)

[Проведение платежей](https://yookassa.ru/developers/payment-acceptance/getting-started/payment-process)

[Входящие уведомления](https://yookassa.ru/developers/using-api/webhooks)
