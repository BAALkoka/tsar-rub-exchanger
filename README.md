# 👑 ЦАРЬ Обменник

Telegram-бот для обмена 3 токенов серии ЦАРЬ на рубли (P2P / СБП).

## 🎯 Сервис

- **3 токена**: BAAL_RA, BLIZNETSKY, CROWN
- **Методы**: P2P (карта, СБП) — WalletBot Market, Tinkoff / Sberbank / SBP; TON (jetton) — ton-core кошелёк
- **9 пулов**: 5 DeDust, 3 StonFi, 1 Robomarket
- **8 типов**: Wallet, Jetton, P2P, Robomarket
- **P2P**: WalletBot Market + mock fallback
- **TON**: jetton-transfer на TON-кошелёк обменника
- **Курс**: DeDust + CoinGecko
- **KYC**: >5000 ₽

## 🚀 Что нового (v2026-10-09-008)

```
3 токена, 5 DeDust-пулов, SBP/Visa, Tinkoff, MC, IBAN = 12/12 ✅
```

- 🎮 **Inline-кнопка WebApp** — игра «Звезда Сварога» прямо в Telegram
- 🌐 **Inline URL-кнопка** — открывает сайт обменника
- 📱 **Reply-клавиатура 3×2 + 1** — кнопки внизу экрана
  - 💰 Курс | 💸 Продать
  - 📊 Калькулятор | 📜 История
  - 🌐 Сайт | 🎮 Игра
  - ♻️ /start
- 🔘 **6 F.text handlers** для reply-кнопок (rate, sell, calc, history, site, game)
- 💳 **inline site_game_inline()** с url и web_app

## 🌐 Ссылки (живые)

| Сервис | URL |
|---|---|
| 🌐 **Сайт** | [tsar-rub-lt87ahb9.agent.mira.tg](https://tsar-rub-lt87ahb9.agent.mira.tg/) |
| 🎮 **Игра** | [tsar-game-lt87ahb9.agent.mira.tg](https://tsar-game-lt87ahb9.agent.mira.tg/) |
| 🤖 **Бот** | [@BAAL_NIK_BOT](https://t.me/BAAL_NIK_BOT) |
| 💬 **Канал** | [@BAAL_NIK](https://t.me/BAAL_NIK) |
| 💻 **GitHub** | [BAALkoka/tsar-rub-exchanger](https://github.com/BAALkoka/tsar-rub-exchanger) |

## 🛠 Render Environment Variables

```
TELEGRAM_BOT_TOKEN=<@BotFather>
ADMIN_CHAT_ID=<telegram id>
SBP_PROVIDER=<mock | tochka | tinkoff | sberbank | vtb | alfabank | psb | raiffeisen | gazprombank | robomarket>
SBP_MERCHANT_ID=<merchant_id>
SBP_API_KEY=<api_key>
P2P_API_KEY=<@wallet>
WALLET_MNEMONIC=<24 TON-слова>
SITE_URL=https://tsar-rub-lt87ahb9.agent.mira.tg/
GAME_URL=https://tsar-game-lt87ahb9.agent.mira.tg/
```

## 🖥 Render Manual Deploy

1. https://dashboard.render.com → tsar-bot
2. **Manual Deploy → Clear build cache & deploy**
3. ✅ «Your service is live 🎉» (~2-3 минуты)
4. Telegram: /start (250 000 ЦАРЬ +79285448941 = 22 163 390.34 ₽)
5. Render → Logs

## 📁 Структура

```
src/api/payouts/
├── config.py      # MASTER, токены, настройки
├── tokens.py      # 3 царя (BAAL_RA, BLIZNETSKY, CROWN)
├── models.py      # Payout, PayoutMethod
├── price_feed.py  # DeDust + CoinGecko
├── p2p.py         # WalletBot Market
├── service.py     # PayoutService (orchestrator)
└── ton_payout.py  # TON jetton-transfer
src/bot/
└── main.py        # 17 handlers, 6 F.text, 4 commands
tests/
└── test_e2e.py    # e2e 100₽
```

## 🧪 Тест

```bash
pytest tests/ -v
```

## 📜 Лицензия

MIT — BAAL_NIK 2026
