# 👑 ЦАРЬ → РУБЛЬ Обменник

Telegram-бот для обмена токенов серии ЦАРЬ (TON) на рубли с выводом через СБП или на карту.

## 🎯 Что умеет

- **3 царя**: BAAL_RA, BLIZNETSY, CROWN
- **Любой получатель**: СБП-телефон, карта МИР/Visa/MC, зарубежная карта (IBAN)
- **9 банков СБП**: Точка, Тинькофф, Сбербанк, ВТБ, Альфа, ПСБ, Райффайзен, Газпромбанк, Robomarket
- **8 банков для перевода на карту**: Точка, Тинькофф, Сбербанк, ВТБ, Альфа, ПСБ, Райффайзен, Газпромбанк
- **P2P**: WalletBot Market + mock fallback
- **TON**: jetton-transfer ЦАРЬ → кошелёк обменника
- **Курс**: DeDust + ЦБ РФ + CoinGecko
- **KYC**: авто-флаг при >5000 ₽

## 🧪 E2E-тест (12/12)

```
3 царя × {СБП, МИР, Visa, IBAN} = 12/12 ✅
```

## 🚀 Деплой (Render)

### Render Environment Variables

```
TELEGRAM_BOT_TOKEN=<от @BotFather>
ADMIN_CHAT_ID=<ваш telegram id>
SBP_PROVIDER=<mock | tochka | tinkoff | sberbank | vtb | alfa | psb | raiffeisen | gazprombank | robomarket>
SBP_MERCHANT_ID=<merchant_id>
SBP_API_KEY=<api_key>
P2P_API_KEY=<опц., от @wallet>
WALLET_MNEMONIC=<опц., 24 слова от TON-кошелька>
```

### Render Manual Deploy

1. https://dashboard.render.com → сервис tsar-bot
2. **Manual Deploy → Clear build cache & deploy**
3. Ждём "Your service is live 🎉" (~2-3 мин)
4. Telegram: /start → 💸 Продать → 250000 → +79285448941 → ✅
5. Проверяем: Render → Logs

## 🏗 Архитектура

```
src/api/payouts/
├── config.py         # MASTER, пулы, комиссии, лимиты
├── tokens.py         # 3 царя (BAAL_RA, BLIZNETSY, CROWN)
├── models.py         # Payout, PayoutMethod, PayoutStatus, PayoutResult
├── price_feed.py     # DeDust + CBR + CoinGecko
├── p2p.py            # WalletBot + mock
├── sbp.py            # 9 банков СБП + 8 банков CARD
├── ton_payout.py     # jetton-transfer
└── service.py        # 5-stage pipeline + detect_recipient_kind
```

## 💬 Telegram: @BAAL_NIK (АНО ЦЕНТР «БЛИЗНЕЦЫ», ИНН 0517005693)
