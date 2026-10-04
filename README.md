# 👑 ЦАРЬ → RUB → Карта

**Off-ramp сервис для серии токенов ЦАРЬ: обмен крипты → RUB → банковская карта.**

Держатели токенов серии **ЦАРЬ** могут продавать монеты за фиат (₽) и получать деньги напрямую на карту — без бирж и сложного онбординга.

## 🎯 Цель

Сделать обмен ЦАРЬ → RUB за 3 клика в Telegram, без регистрации на бирже, без KYC до порога.

## ⚙️ Архитектура

- **Frontend**: Telegram-бот (основной UI), web-кабинет для крупных сумм
- **Backend**: Python + FastAPI, REST API + webhooks
- **Blockchain**: TON-контракт escrow для приёма ЦАРЬ
- **Price oracle**: CoinGecko / CMC / DEX-фид
- **AML/KYC**: модуль верификации по порогам суммы
- **Payment rails**: СБП, банковские карты РФ

## 📂 Структура репозитория

```
tsar-rub-exchanger/
├── README.md
├── ROADMAP.md
├── LICENSE
├── docs/
│   └── ARCHITECTURE.md
└── src/
    ├── api/
    │   └── payouts/        # СБП-модуль, выплаты
    │       ├── __init__.py
    │       ├── service.py
    │       ├── sbp.py
    │       ├── models.py
    │       ├── requirements.txt
    │       └── tests/
    ├── bot/                 # Telegram-бот на aiogram v3
    │   ├── main.py
    │   ├── config.py
    │   ├── middlewares.py
    │   ├── requirements.txt
    │   └── handlers/
    │       ├── start.py
    │       ├── balance.py
    │       └── withdraw.py
    └── onchain/
        └── escrow/          # TON-смарт-контракт
            ├── contract.fc
            └── README.md
```

## 🚀 Quickstart

### Backend (выплаты)
```bash
cd src/api/payouts
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pytest tests/
```

### Telegram-бот
```bash
cd src/bot
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export BOT_TOKEN=xxx
python main.py
```

### TON escrow
```bash
# см. src/onchain/escrow/README.md
```

## 📜 Лицензия

MIT — см. [LICENSE](LICENSE).

## 👑 Контакты

- Telegram: [@BAAL_NIK](https://t.me/BAAL_NIK_2505lis)
- Сайт: [ANO Center Gemini](https://sites.google.com/view/ano-center-gemini25)