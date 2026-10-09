# 👑 ЦАРЬ бот обменник (tsar-rub-exchanger)

Telegram-бот для обмена **ЦАРЬ** (BAAL_RA, BLIZNETSY, CROWN) на рубли с выводом через СБП по номеру телефона.

## 🚀 Запуск за 2 минуты

```bash
# 1. Склонировать
git clone https://github.com/BAALkoka/tsar-rub-exchanger.git
cd tsar-rub-exchanger

# 2. Установить
pip install -r requirements.txt

# 3. Секреты (минимум — TELEGRAM_BOT_TOKEN)
export TELEGRAM_BOT_TOKEN="..."          # от @BotFather
export ADMIN_CHAT_ID="..."                # твой Telegram id (опц.)
export P2P_API_KEY=""                     # от @wallet (опц., mock без него)
export WALLET_MNEMONIC=""                 # 24 слова (опц., mock без него)
export SBP_PROVIDER=mock                  # mock | tochka | tinkoff | alfa

# 4. Запустить
python bot.py
```

Открой бота в Telegram → `/start` → 💸 Продать → 250000 → +79285448941.

## 📊 Pipeline (5 стадий)

```
1.2 ЦАРЬ → PriceFeed (DeDust) → P2P best_buy → SBP payout → 105.80₽
            ↓                       ↓                  ↓
         rate=85.06₽            GarantTrade@89.62    sbp_mock_xxx
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

bot.py               # Telegram-бот (aiogram 3.13, FSM)
tests/test_e2e.py    # e2e тесты (pytest)
```

## 🧪 Тесты

```bash
MIN_PAYOUT_TSAR=1 SERVICE_FEE_PCT=0.25 SBP_FEE_PCT=0.40 \
  python -m pytest tests/ -v
```

## 💸 Комиссии

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

- `/start` — приветствие + меню
- `/quote` — курс (inline-выбор токена)
- `/sell N` — расчёт для N ЦАРЬ
- `/withdraw` — пошаговый вывод (FSM)
- `/withdraw N +7...` — быстрый вывод
- `/history` — история
- `/help` — справка

## 🔄 Render деплой

1. Подключить репо в [Render Dashboard](https://dashboard.render.com)
2. **New → Web Service → Build Command**: `pip install -r requirements.txt`
3. **Start Command**: `python bot.py`
4. **Environment Variables**:
   ```
   TELEGRAM_BOT_TOKEN=...
   ADMIN_CHAT_ID=...
   MIN_PAYOUT_TSAR=250000
   SERVICE_FEE_PCT=0.25
   SBP_FEE_PCT=0.40
   ```
5. **Manual Deploy → Clear build cache & deploy**

## 🔗 Контакты

- GitHub: [BAALkoka/tsar-rub-exchanger](https://github.com/BAALkoka/tsar-rub-exchanger)
- Telegram: [@BAAL_NIK](https://t.me/BAAL_NIK)

---

## 🛠 История изменений

### v2026-10-09-006 (финальная)
- ✅ FSM /withdraw в стиле "ЦАРЬ бот обменник" (waiting_amount → waiting_phone)
- ✅ Кнопка ⏪ Назад в каждом FSM-сообщении
- ✅ Inline-выбор 3 царей в /quote
- ✅ Валидация: 250к ≤ N ≤ 1 млрд, только +7XXXXXXXXXX
- ✅ Быстрый путь /withdraw N +7...
- ✅ Фикс `PayoutStatus.PENDING` AttributeError

### v2026-10-09-003
- P2P-сначала pipeline (service.py: quote + execute, 5 stages)
- config.py: MIN_PAYOUT_TSAR, SBP_FEE_PCT
- p2p.py: create_order + P2POrder
