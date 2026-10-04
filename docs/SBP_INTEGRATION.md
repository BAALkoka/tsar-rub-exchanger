# 💳 Интеграция Тинькофф СБП

## Что нужно

- `TINKOFF_TERMINAL_KEY` — terminal key
- `TINKOFF_PASSWORD` — пароль для подписи
- `TINKOFF_API_URL` — по умолчанию https://api.tinkoff.ru/v1

## Env-vars

```bash
export TINKOFF_TERMINAL_KEY="..."
export TINKOFF_PASSWORD="..."
```

## Поток выплаты

1. `/withdraw` → сумма ЦАРЬ → получатель (телефон/карта)
2. Бот вызывает `SBPBridge.payout_rub()`
3. `TinkoffSBPClient.create_payout()` → Тинькофф СБП
4. Зачисление на карту пользователю

## Без ключей (manual)

Бот работает: заявки принимаются, СБП-вызов не делается. Менеджер обрабатывает вручную. В `/start` бот напишет «⚠️ ручной режим».