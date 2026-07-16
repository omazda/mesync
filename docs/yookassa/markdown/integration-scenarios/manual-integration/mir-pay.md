<!-- Источник: https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/mir-pay -->
<!-- Полная копия статьи официальной документации ЮKassa, сохранено 2026-07-02 -->

# Mir Pay

Оплата через Mir Pay доступна только для мобильных устройств на Android при оплате картами Мир.

Особенности

- Тип способа оплаты в API: `bank_card`
- [Сценарий подтверждения](https://yookassa.ru/developers/payment-acceptance/getting-started/payment-process#user-confirmation): Redirect
- [Срок оплаты](https://yookassa.ru/developers/payment-acceptance/getting-started/payment-methods#payment-term): 1 час
- [Холдирование](https://yookassa.ru/developers/payment-acceptance/getting-started/payment-process#capture-and-cancel): 7 дней, доступно полное и частичное списание оплаты
- [Код в реестре](https://yookassa.ru/developers/payment-acceptance/after-the-payment/reports): AC
- [Возврат](https://yookassa.ru/developers/payment-acceptance/after-the-payment/refunds): да, полный и частичный
- Срок возврата: от 0 до 3 дней (зависит от эмитента)
- [Автоплатежи](https://yookassa.ru/developers/payment-acceptance/scenario-extensions/recurring-payments/basics): да
- [Лимиты](https://yookassa.ru/developers/payment-acceptance/getting-started/payment-methods#payment-limit): минимальный размер платежа — 1 рубль, максимальный — 350 000 рублей, есть [дополнительные ограничения](https://yookassa.ru/docs/support/payments/limits)
- Поддерживаемая версия приложения Mir Pay: 1.16.2.341 и новее

Сценарии интеграции

Готовые решения:

- [Умный платеж](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/smart-payment)
- [Виджет ЮKassa](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/basics)

Самостоятельная интеграция: кнопка Mir Pay отображается при оплате [банковской картой на готовой странице ЮKassa](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/bank-card#create-payment-redirect). Отображать Mir Pay в виде отдельной кнопки можно только в виджете ЮKassa при [определенных настройках](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/additional-settings/separate-payment-methods).

Подключение

Mir Pay доступен по умолчанию, если вы принимаете платежи с помощью банковских карт.

Оплата через Mir Pay доступна на платежной форме в [виджете ЮKassa](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/basics), [Умном платеже](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/smart-payment) и при [оплате банковской картой на готовой странице ЮKassa](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/manual-integration/bank-card#create-payment-redirect). Дополнительно настраивать ничего не нужно.

Отключить Mir Pay можно через менеджера ЮKassa сразу для всех [сценариев проведения оплаты](https://yookassa.ru/developers/payment-acceptance/getting-started/selecting-integration-scenario).

Процесс платежа

Как проходит платеж для пользователя

1. Пользователь при оплате с мобильного устройства выбирает Mir Pay в качестве способа оплаты.
2. Платежная форма перенаправляет пользователя в мобильное приложение Mir Pay.
3. Пользователь в приложении Mir Pay подтверждает платеж.
4. Пользователь возвращается на мобильную версию вашего сайта или в мобильное приложение и узнает статус платежа.

Пользователь сможет провести платеж, если на устройстве, с которого он платит, установлено приложение Mir Pay версии 1.16.2.341 и новее. Если на устройстве пользователя установлена старая версия приложения Mir Pay, оплата не пройдет, пользователь сможет выбрать другой способ оплаты. Рекомендуется сообщать пользователю, что приложение Mir Pay нужно обновить до последней версии.

Если на устройстве пользователя нет приложения Mir Pay, он сможет установить его из магазина приложений или выбрать другой способ оплаты.

Как выглядит платеж через Mir Pay в API

Если пользователь для оплаты использовал Mir Pay, информация об этом отобразится в [объекте платежа](https://yookassa.ru/developers/api#payment_object) со статусом `succeeded`: в объекте `payment_method` параметр `type` вернется со значением `bank_card`, а параметр `card.source` — со значением `mir_pay`.

**Пример успешного платежа**

**JSON**

```json
{
  "id": "22e12f66-000f-5000-8000-18db351245c7",
  "status": "succeeded",
  "paid": true,
  "amount": {
    "value": "2.00",
    "currency": "RUB"
  },
  "captured_at": "2021-04-12T13:59:33.681Z",
  "created_at": "2021-04-12T13:49:33.026Z",
  "income_amount": {
    "value": "2.00",
    "currency": "RUB"
  },
  "payment_method": {
    "type": "bank_card",
    "id": "22e12f66-000f-5000-8000-18db351245c7",
    "saved": false,
    "card": {
      "first6": "555555",
      "last4": "4444",
      "expiry_month": "01",
      "expiry_year": "2030",
      "card_type": "Mir",
      "card_product": {
        "code": "MCP",
        "name": "MIR Privilege"
      },
      "issuer_country": "RU",
      "issuer_name": "Sberbank",
      "source": "mir_pay"
    }
  },
  "recipient": {
    "account_id": "100500",
    "gateway_id": "100700"
  },
  "refundable": true,
  "refunded_amount": {
    "value": "0.00",
    "currency": "RUB"
  },
  "test": false,
  "authorization_details": {
    "rrn": "603668680243",
    "auth_code": "000000",
    "three_d_secure": {
      "applied": false
    }
  }
}
```

Что почитать еще

[Основы проведения платежей](https://yookassa.ru/developers/payment-acceptance/getting-started/payment-process)

[Неуспешные платежи](https://yookassa.ru/developers/payment-acceptance/after-the-payment/declined-payments)

[Отправка чеков в налоговую](https://yookassa.ru/developers/payment-acceptance/receipts/basics)
