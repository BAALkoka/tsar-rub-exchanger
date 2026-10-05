# GitHub Secrets — Tsar RUB Exchanger

Секреты, которые нужны для production в `BAALkoka/tsar-rub-exchanger`.

## Уже заданы

| Secret | Что | Когда добавлен |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | Токен @BAAL_NIK_BOT | 2026-10-04 |
| `P2P_API_KEY` | X-API-Key WalletBot P2P Market (зашифрован libsodium) | 2026-10-05 |

## Опциональные

| Secret | Что | Зачем |
|---|---|---|
| `TONAPI_TOKEN` | Bearer-токен [tonapi.io](https://tonapi.io/) | Лимит 1 req/sec, без токена — 0.5 req/sec |
| `ADMIN_CHAT_ID` | Telegram chat_id (число) | Уведомления о входящих IP-переводах |
| `P2P_API_URL` | URL P2P Market | По умолчанию `https://p2p.walletbot.me` |
| `USD_RUB_FALLBACK` | Курс доллара к рублю | По умолчанию 90.0 |

## Как обновить P2P_API_KEY

1. Зайти на [p2p.walletbot.me](https://p2p.walletbot.me) → Integration API
2. Скопировать новый X-API-Key
3. Прислать ключ боту @mira одним сообщением
4. Mira зашифрует libsodium sealed_box и зальёт через `GITHUB_CREATE_OR_UPDATE_A_REPOSITORY_SECRET`

## Использование

В коде секреты доступны через переменные окружения:

```python
import os
P2P_API_KEY = os.getenv("P2P_API_KEY")
TONAPI_TOKEN = os.getenv("TONAPI_TOKEN")
```

В `bot/main.py`, `api/payouts/p2p.py` и `api/payouts/ton_watcher.py` секреты
читаются автоматически при старте.