# 👑 ЦАРЬ Rub Exchanger

Telegram-бот для продажи 3 серий токенов ЦАРЬ (BAAL_RA, Гемини, С-коронкой) за RUB через **P2P** или **СБП**.

## 🌟 Возможности

- **3 серии ЦАРЬ**, каждая со своим DeDust-пулом
- **P2P** — продажа USDT с выводом на карту RUB
- **СБП** — продажа USDT с выводом по номеру телефона
- **Курс DeDust-пула** в реальном времени (GeckoTerminal)
- **P2P-объявления** с кэшем 30 сек (10 mock-продавцов)
- **TonWatcher** для авто-определения токена по входящему jetton
- **FastAPI** для HTTP-endpoints (quote, payout)

## 🤖 Бот в Telegram

[@BAAL_NIK_BOT](https://t.me/BAAL_NIK_BOT)

Команды:
- `/start` — главное меню
- `/rate` — общий курс ЦАРЬ
- `/pool <slug>` — курс конкретного DeDust-пула (BAAL_RA / GEMINI / CROWN)
- `/tokens` — все 3 серии + адреса
- `/p2p` — P2P-объявления RUB/USDT
- `/p2p_refresh` — сбросить кэш P2P
- `/version` — версия бота

## 🪙 3 серии ЦАРЬ

| Серия | Slug | DeDust-пул | Master |
|---|---|---|---|
| 👑 BAAL_RA | `BAAL_RA` | USD₮-пул | `EQC5D3XIrc777bcr8EOQ2_ZBMPuePUqT-zzWTr9-pJEoe7uf` |
| ♊ Гемини | `GEMINI` | TON-пул | `EQBcUttXk7IhCF23ZghXNc7HY9v3_SAuhsWgW_YHntHsUYtM` |
| 👑 С коронкой | `CROWN` | TON-пул | `EQB2T7svf6RzbvYc99jWBfj6n9P3gUsyR4AiiBLgPYIwqKX2` |

🔗 Все адреса доступны в боте через кнопку `📋 Адреса`.

## 🏗 Архитектура

```
src/
├── bot/
│   └── main.py              # Telegram-бот (aiogram)
├── api/payouts/
│   ├── tokens.py            # Реестр 3 серий ЦАРЬ
│   ├── price_feed.py        # Курс DeDust-пулов (GeckoTerminal)
│   ├── p2p.py               # P2P-клиент (10 mock + 3-tier fallback)
│   ├── service.py           # PayoutService
│   ├── ton_watcher.py       # TonWatcher для входящих переводов
│   └── config.py            # USDT_TREASURY_ADDRESS, USD_RUB_FALLBACK
└── tests/
    ├── test_price_feed.py
    ├── test_p2p.py
    └── test_tokens.py
```

## 💱 Курс

1. Получаем курс USDT→RUB (exchangerate-api.com, fallback = 89.40 ₽)
2. Получаем цену ЦАРЬ в USDT (GeckoTerminal, DeDust-пул)
3. Перемножаем: `1 ЦАРЬ = price_usdt × rate_usd_rub`
4. Для 3 серий — 3 разных DeDust-пула → 3 разных цены

## 🤝 P2P

- **Tier 1:** WalletBot P2P Market (если задан `P2P_API_KEY`)
- **Tier 2:** Public API (если доступно)
- **Tier 3:** Mock — 10 продавцов (Diamond/Platinum/Gold) с реалистичной вариативностью ±1%

## 🔐 Безопасность

- **Никогда не храним приватные ключи** от P2P в коде
- P2P API ключи добавляются через GitHub Secrets (вручную)
- Mock-режим работает без ключей

## 📜 История

- **v2026-10-05-003** — 3 царя × (P2P + СБП + Адреса + Курс), упрощённое меню
- **v2026-10-05-002** — P2P refresh + 10 mock sellers + 3 DeDust-пула
- **v2026-10-05-001** — первый рабочий бот с моно-ЦАРЬ

## 📜 Лицензия

MIT

## 📞 Контакты

Telegram: [@BAAL_NIK](https://t.me/BAAL_NIK) · [@BAAL_NIK_2505lis](https://t.me/BAAL_NIK_2505lis) · [https://baal.tb.ru/2505lis](https://baal.tb.ru/2505lis)
