# 👑 ЦАРЬ Обменник

Telegram-бот для обмена 3 токенов серии ЦАРЬ на рубли (P2P / СБП).

## 🎯 Сервис
- **3 токена**: BAAL_RA, BLIZNETSY, CROWN
- **Методы**: P2P (карта) или СБП (по телефону +79285448941)
- **9 пулов**: 5 DeDust, 3 StonFi, 1 Robomarket
- **8 типов**: Wallet, Jetton, P2P, Robomarket
- **KYC**: >5000 ₽

## 🚀 v2026-10-10-014
- ✅ **Кнопка «📜 История»** — реальная логика с MemoryStorage + JSON
- ✅ История последних 10 операций на пользователя
- ✅ Inline-кнопка «📜 Открыть историю» под каждой заявкой
- ✅ Полный файл main.py (12 КБ) с 9 @router.message + 3 callback_query

## 🎮 Кнопки в боте
- 💰 **Курс** — все 3 DeDust-пула
- 💸 **Продать** — выбор серии ЦАРЬ
- 📊 **Калькулятор** — /sell 1000000
- 📜 **История** — последние 10 выводов
- 🌐 **Сайт** — обменник
- 🎮 **Игра** — Звезда Сварога (WebApp)

## 🔗 Ссылки
- 🌐 Сайт: https://tsar-rub-lt87ahb9.agent.mira.tg/
- 🎮 Игра: https://tsar-game-lt87ahb9.agent.mira.tg/
- 🤖 Бот: https://t.me/BAAL_NIK_BOT
- 💬 Чат: https://t.me/BAAL_NIK_chat
- 💻 GitHub: https://github.com/BAALkoka/tsar-rub-exchanger

## 🛠 Render

```
TELEGRAM_BOT_TOKEN=<@BotFather>
ADMIN_CHAT_ID=<telegram id>
P2P_API_KEY=<@wallet>
SITE_URL=https://tsar-rub-lt87ahb9.agent.mira.tg/
GAME_URL=https://tsar-game-lt87ahb9.agent.mira.tg/
```

1. https://dashboard.render.com → tsar-bot
2. **Manual Deploy → Clear build cache & deploy**
3. ✅ "Your service is live" (~2-3 мин)
4. Telegram: /start → жми 📜 История

## 📁 Структура
```
src/api/payouts/
├── config.py      # MASTER, токены
├── tokens.py      # 3 царя
├── models.py      # Payout, PayoutMethod
├── price_feed.py  # DeDust + CoinGecko
├── p2p.py         # WalletBot Market
├── service.py     # PayoutService
└── ton_payout.py  # TON jetton-transfer
src/bot/
└── main.py        # 9 handlers, 7 F.text, 3 callback
tests/
└── test_e2e.py    # e2e 100₽
```

## 🧪 Тест
```bash
pytest tests/ -v
```

## 📜 Лицензия
MIT — BAAL_NIK 2026
