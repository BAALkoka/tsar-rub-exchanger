# 👑 Tsar-RUB Exchanger

Off-ramp сервис для обмена **ЦАРЬ (BAAL_RA)** на рубли с выводом на карту через СБП.

## 🚀 Что делает

1. **Цена ЦАРЬ** берётся из DeDust-пула (USDT/ЦАРЬ) в реальном времени
2. **P2P Market** (WalletBot) — лучший покупатель USDT за RUB
3. **СБП** — перевод RUB на карту по номеру телефона
4. **TON** — jetton-перевод ЦАРЬ с кошелька пользователя на кошелёк обменника

## 📊 Pipeline

```
1.2 ЦАРЬ → PriceFeed (DeDust) → P2P best_buy → SBP payout → 100₽ на карту
            ↓                       ↓                  ↓
         rate=85₽              ExpressP2P@89.45    sbp_mock_xxx
```

## 🏗 Архитектура

```
src/api/payouts/
├── config.py        # MASTER, пулы, комиссии, лимиты
├── tokens.py        # 3 царя (BAAL_RA, BLIZNETSY, CROWN)
├── models.py        # Payout, PayoutMethod, PayoutStatus
├── price_feed.py    # DeDust + CoinGecko + GeckoTerminal
├── p2p.py           # P2PClient (WalletBot + mock)
├── sbp.py           # SbpClient (mock + Tochka/Tinkoff/Alfa)
├── ton_payout.py    # TonPayout (jetton-transfer)
└── service.py       # PayoutService (5-stage pipeline)

bot.py               # Telegram-бот (aiogram 3.13)
tests/test_e2e.py    # 4 e2e теста (pytest)
```

## ⚙️ Запуск

```bash
# 1. Установить
pip install -r requirements.txt

# 2. Задать секреты
export TELEGRAM_BOT_TOKEN=...      # от @BotFather
export P2P_API_KEY=...             # от @wallet (опц.)
export WALLET_MNEMONIC="..."       # 24 слова (опц.)
export SBP_PROVIDER=tochka         # mock | tochka | tinkoff | alfa
export SBP_MERCHANT_ID=...
export SBP_API_KEY=...

# 3. Запустить
python bot.py
```

## 🧪 Тесты

```bash
MIN_PAYOUT_TSAR=1 SERVICE_FEE_PCT=0.25 SBP_FEE_PCT=0.40 \
  python -m pytest tests/test_e2e.py -v -s
```

## 📊 Комиссии

| Тип | % | Константа |
|---|---|---|
| Сервис | 0.25% | `SERVICE_FEE_PCT` |
| СБП/банк | 0.40% | `SBP_FEE_PCT` |
| P2P-спред | 0.20% | `P2P_FEE_PCT` |
| **Итого** | **~0.85%** | — |

## 🪙 Поддерживаемые токены

- 👑 **BAAL_RA** — Царь (основной)
- 👑👑 **BLIZNETSY** — Близнецы
- 👑💎 **CROWN** — С коронкой

## 📜 Команды бота

- `/start` — приветствие
- `/quote` — курс (с inline-выбором токена)
- `/sell 1.2` — расчёт для 1.2 ЦАРЬ
- `/withdraw 250000 +79001234567` — вывод на СБП
- `/history` — история обменов
- `/help` — справка

## 🔗 Контакты

- GitHub: [BAALkoka/tsar-rub-exchanger](https://github.com/BAALkoka/tsar-rub-exchanger)
- Telegram: [@BAAL_NIK](https://t.me/BAAL_NIK)
