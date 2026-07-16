<!-- Источник: https://yookassa.ru/developers/payment-acceptance/integration-scenarios/mobile-sdks/android-sdk -->
<!-- Полная копия статьи официальной документации ЮKassa, сохранено 2026-07-02 -->

# Использование Android SDK

Библиотека позволяет встроить прием платежей в мобильные приложения на Android и работает как дополнение к API ЮKassa.

В мобильный SDK входят готовые платежные интерфейсы (форма оплаты и всё, что с ней связано). С помощью SDK можно получать токены для проведения оплаты с банковской карты, через SberPay, СБП или из кошелька ЮMoney.

Требования: Android 7 или новее

Демо-приложение

Посмотреть, как выглядят платежные интерфейсы и как проходит процесс оплаты, можно в специальном демо-приложении. Установите приложение на ваше устройство и пройдите весь процесс так, как это сделают ваши пользователи: нажмите на кнопку **Купить**, введите данные банковской карты или кошелька ЮMoney. Приложение позволяет воспроизводить разные сценарии оплаты.

[Скачать демо-приложение](https://apps.rustore.ru/app/ru.yoo.sdk.kassa.payments.example.release)

Приложение нужно устанавливать со смартфона

Скачивая демо-приложение, вы принимаете [лицензионное соглашение](https://yoomoney.ru/page?id=530190).

Порядок работы с SDK

Для начала вам нужно реализовать прием платежей по [API ЮKassa](https://yookassa.ru/developers/api). После этого:

1. Сообщите менеджеру, что собираетесь проводить платежи с помощью мобильного SDK.
2. Когда вам подключат мобильный SDK, выпустите для него ключ в личном кабинете, в разделе [Интеграция — Ключи API](https://yookassa.ru/my/merchant/integration/api-keys).
3. [Скачайте SDK](https://git.yoomoney.ru/projects/SDK/repos/yookassa-android-sdk).
4. Добавьте SDK в приложение и настройте выпуск одноразовых платежных токенов по [инструкции в репозитории ЮKassa](https://git.yoomoney.ru/projects/SDK/repos/yookassa-android-sdk).
5. Реализуйте отправку одноразовых токенов из мобильного приложения в вашу систему (например, в бэкенд вашего сайта, который отвечает за работу с ЮKassa).
6. Проводите платежи с использованием [платежных токенов](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/mobile-sdks/payments-with-tokens) через API ЮKassa.

Возможности SDK

С помощью SDK вы можете:

- токенизировать платежные данные пользователя;
- при оплате банковской картой сканировать данные карты и обрабатывать 3-D Secure;
- настраивать интерфейс платежной формы.

Для отладки токенизации вы можете использовать логирование сетевых запросов. Корректность интеграции SDK можно проверить с помощью тестового режима.

Более подробная информация о возможностях Android SDK приведена в документации в [репозитории ЮKassa](https://git.yoomoney.ru/projects/SDK/repos/yookassa-android-sdk).

Что почитать еще

[Проведение платежа с использованием токена](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/mobile-sdks/payments-with-tokens)

[Основы проведения платежей](https://yookassa.ru/developers/payment-acceptance/getting-started/payment-process)

[Способы оплаты](https://yookassa.ru/developers/payment-acceptance/getting-started/payment-methods)

[Входящие уведомления](https://yookassa.ru/developers/using-api/webhooks)
