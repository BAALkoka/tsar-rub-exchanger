# ЦАРЬ Exchange v20 — Исправлен GeckoTerminal + все кнопки → t.me/RA_BAAL

Live: https://tsar-exchange-lt87ahb9.agent.mira.tg

## Проблема:
Карточки токенов были кликабельные через `onclick`, но этот onclick **конфликтовал** с вложенной ссылкой `STON.fi` (DexScreener) внутри карточки. Клик по карточке срабатывал на DexScreener, а не на GeckoTerminal.

## Решение:
- Вся карточка теперь обёрнута в `<a class="card-gt-link" href="https://www.geckoterminal.com/...">`
- Внутри карточки две кнопки в ряд:
  - 📈 **GeckoTerminal** (главный график)
  - 🔗 **STON.fi / PancakeSwap** (DEX)

## Все GeckoTerminal URLs:
- TON #1: https://www.geckoterminal.com/ton/tokens/EQB2T7svf6RzbvYc99jWBfj6n9P3gUsyR4AiiBLgPYIwqKX2
- TON #2 (Gemini): https://www.geckoterminal.com/ton/tokens/EQBcUttXk7IhCF23ZghXNc7HY9v3_SAuhsWgW_YHntHsUYtM
- TON #3 (BAAL_RA): https://www.geckoterminal.com/ton/tokens/EQC5D3XIrc777bcr8EOQ2_ZBMPuePUqT-zzWTr9-pJEoe7uf
- BSC #1 (КРУБЛИК): https://www.geckoterminal.com/bsc/tokens/0x992560BF75de459d708Fad69a1f6cfd24D6181Cf
- BSC #2: https://www.geckoterminal.com/bsc/tokens/0xFb8a945e263Dcee13D84147305C9bF25543158Eb
- BSC #3: https://www.geckoterminal.com/bsc/tokens/0x8a3eCb08C627a890736De00BE734E2c68c1A220
- BSC #4: https://www.geckoterminal.com/bsc/tokens/0x94640e51d4D6C24d373E0756B5780CB45559E4D7

## По голосовому Шведенко Н.А. 03:11:
- «Кнопка Поддержка вставь вот эту ссылку» — на https://t.me/RA_BAAL

## Заменено:
- Все 3 ссылки `baal.tb.ru/2505lis` → `t.me/RA_BAAL`
  - 📢 Telegram → https://t.me/RA_BAAL
  - 🛟 Поддержка → https://t.me/RA_BAAL
  - 👑 BAAL_NIK → https://t.me/RA_BAAL