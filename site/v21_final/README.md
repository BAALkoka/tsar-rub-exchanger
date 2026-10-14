# ЦАРЬ Exchange v21 — CACHE-BUSTING + все 7 GeckoTerminal кликабельны

Live: https://tsar-exchange-lt87ahb9.agent.mira.tg

## По голосовому Шведенко Н.А. 03:21:
> «Нажимаю на первую кнопку. Первый пул. Кнопка проваливает на GeckoTerminal. Всё работает. Остальные кнопки не работают. Именно на те пулы, которые я должен видеть. Исправляй. Всё должно быть кликабельно.»

## Причина:
Edge кэш у CDN отдавал старую версию (32349 → 33749 байт), где только 1-я карточка была правильно обёрнута в `<a>`, а у остальных был только `onclick` (который не работал на мобильных).

## Решение v21:
- ✅ `<meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate">` — браузер не кэширует
- ✅ `<meta http-equiv="Pragma" content="no-cache">`
- ✅ `<meta http-equiv="Expires" content="0">`
- ✅ Версионная метка `v21-final • 2026-10-14 03:23` в футере
- ✅ JS-fallback: console.log показывает количество загруженных карточек

## Проверка (35427 байт):
- ✅ 7 карточек с `<a class="card-gt-link" href="https://www.geckoterminal.com/...">`
- ✅ 7 внутренних кнопок `<a class="token-link gt-link">📈 GeckoTerminal`
- ✅ 10 ссылок на geckoterminal.com
- ✅ 14 ссылок на dexscreener.com (STON.fi / PancakeSwap)

## Прямые URL'ы для проверки (все 7):
- TON #1: https://www.geckoterminal.com/ton/tokens/EQB2T7svf6RzbvYc99jWBfj6n9P3gUsyR4AiiBLgPYIwqKX2
- TON #2: https://www.geckoterminal.com/ton/tokens/EQBcUttXk7IhCF23ZghXNc7HY9v3_SAuhsWgW_YHntHsUYtM
- TON #3: https://www.geckoterminal.com/ton/tokens/EQC5D3XIrc777bcr8EOQ2_ZBMPuePUqT-zzWTr9-pJEoe7uf
- BSC #1: https://www.geckoterminal.com/bsc/tokens/0x992560BF75de459d708Fad69a1f6cfd24D6181Cf
- BSC #2: https://www.geckoterminal.com/bsc/tokens/0xFb8a945e263Dcee13D84147305C9bF25543158Eb
- BSC #3: https://www.geckoterminal.com/bsc/tokens/0x8a3eCb08C627a890736De00BE734E2c68c1A220
- BSC #4: https://www.geckoterminal.com/bsc/tokens/0x94640e51d4D6C24d373E0756B5780CB45559E4D7
