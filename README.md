# 👑 Tsar RUB Exchanger

Telegram-бот + FastAPI для off-ramp токенов ЦАРЬ → RUB на карту.

## Возможности

- 3 серии ЦАРЬ с emoji-атрибутом 👑:
  - 👑 **Царь BAAL_RA** — основной
  - ♊ **Царь Гемини** — Gemini-серия
  - 👑 **Царь с коронкой** — коллекционная
- **TON auto-detect** — watcher опрашивает tonapi.io каждые 15с
- **Автоопределение токена** по jetton-master при входящем IP-переводе
- **P2P Market** — через WalletBot API (`X-API-Key`) — находит трейдеров BUY USDT
- **DeDust-пул TSAR/USDT** — реальный курс через GeckoTerminal
- **FastAPI endpoints** — `/v1/quote`, `/v1/payouts`, `/v1/pools`, `/ton/notify`
- **GitHub Actions workflow** — бот живёт 24/7 бесплатно

## Архитектура

```
src/
├── bot/main.py              # Telegram-бот + TonWatcher
└── api/payouts/
    ├── tokens.py            # 3 серии ЦАРЬ + emoji 👑 + find_by_master
    ├── price_feed.py        # GeckoTerminal → DeDust-пул TSAR/USDT
    ├── p2p.py               # WalletBot P2P Market client
    ├── ton_watcher.py       # Polling tonapi.io + detect_token
    ├── service.py           # ЦАРЬ → USDT → P2P → RUB → карта
    ├── api.py               # FastAPI: /v1/quote, /v1/payouts, /ton/notify
    └── config.py            # MASTER-адреса, пулы, treasury
```

## Запуск

```bash
export TELEGRAM_BOT_TOKEN="..."
export P2P_API_KEY="..."          # WalletBot (опц.)
export TONAPI_TOKEN="..."         # tonapi.io (опц.)
export ADMIN_CHAT_ID="..."        # для уведомлений о IP-переводах
export PYTHONPATH=src
python3 -m bot.main
```

## Команды бота

- `/start` — главное меню (3 токена 👑)
- `/rate` — курс ЦАРЬ
- `/pool` — курс DeDust-пула TSAR/USDT
- `/tokens` — все 3 серии
- `/withdraw` — вывод RUB на карту
- `/help` — справка

## Кнопки

```
👑 ЦАРЬ Царь BAAL_RA (EQC5D3…Eoe7uf)
♊ ЦАРЬ♊ Царь Гемини (EQBcUt…HsUYtM)
👑 ЦАРЬ👑 Царь с коронкой (EQB2T7…IwqKX2)
💱 Курс ЦАРЬ
📊 P2P-объявления
🏦 Курс DeDust-пула
🆘 Поддержка
```

## TON-казначейство

USDT приём на кошелёк казначейства: `UQA5gfkm8i4DutEDkMvjmTi3N8VC46yZHKAK_nnpYjawvCet`

Когда приходит jetton — автодетект по master-адресу:
- `EQC5D3XIrc777bcr8EOQ2_ZBMPuePUqT-zzWTr9-pJEoe7uf` → BAAL_RA
- `EQBcUttXk7IhCF23ZghXNc7HY9v3_SAuhsWgW_YHntHsUYtM` → Гемини
- `EQB2T7svf6RzbvYc99jWBfj6n9P3gUsyR4AiiBLgPYIwqKX2` → С коронкой

## Deploy

Render Blueprint: `infra/render.yaml`
GitHub Actions: `.github/workflows/bot-keepalive.yml`