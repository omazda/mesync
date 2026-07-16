<!-- Источник: https://yookassa.ru/developers/payment-acceptance/integration-scenarios/mobile-sdks/ios-sdk -->
<!-- Полная копия статьи официальной документации ЮKassa, сохранено 2026-07-02 -->

# Использование iOS SDK

Библиотека позволяет встроить прием платежей в мобильные приложения на iOS и работает как дополнение к API ЮKassa.

В мобильный SDK входят готовые платежные интерфейсы (форма оплаты и всё, что с ней связано). С помощью SDK можно получать токены для проведения оплаты с банковской карты, через SberPay, СБП или из кошелька ЮMoney.

Требования: iOS 14 или новее

Порядок работы с SDK

Для начала вам нужно реализовать прием платежей по [API ЮKassa](https://yookassa.ru/developers/api). После этого:

1. Сообщите менеджеру, что собираетесь проводить платежи с помощью мобильного SDK.
2. Когда вам подключат мобильный SDK, выпустите для него ключ в личном кабинете, в разделе [Интеграция — Ключи API](https://yookassa.ru/my/merchant/integration/api-keys).
3. [Скачайте SDK](https://git.yoomoney.ru/projects/SDK/repos/yookassa-payments-swift).
4. Добавьте SDK в приложение и настройте выпуск одноразовых платежных токенов по [инструкции в репозитории ЮKassa](https://git.yoomoney.ru/projects/SDK/repos/yookassa-payments-swift).
5. Реализуйте отправку одноразовых токенов из мобильного приложения в вашу систему (например, в бэкенд вашего сайта, который отвечает за работу с ЮKassa).
6. Проводите платежи с использованием [платежных токенов](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/mobile-sdks/payments-with-tokens) через API ЮKassa.

Возможности SDK

С помощью SDK вы можете:

- токенизировать платежные данные пользователя;
- при оплате банковской картой сканировать данные карты и обрабатывать 3-D Secure;
- настраивать интерфейс платежной формы.

Для отладки токенизации вы можете использовать логирование сетевых запросов. Корректность интеграции SDK можно проверить с помощью тестового режима.

Более подробная информация о возможностях iOS SDK приведена в документации в [репозитории ЮKassa](https://git.yoomoney.ru/projects/SDK/repos/yookassa-payments-swift).

Что почитать еще

[Проведение платежа с использованием токена](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/mobile-sdks/payments-with-tokens)

[Основы проведения платежей](https://yookassa.ru/developers/payment-acceptance/getting-started/payment-process)

[Способы оплаты](https://yookassa.ru/developers/payment-acceptance/getting-started/payment-methods)

[Входящие уведомления](https://yookassa.ru/developers/using-api/webhooks)
