# ЦАРЬ Exchange v18 — Карточки токенов = `<a>` (а не div+onclick)

## Проблема (по голосовому 03:11):
> «Почему не открывается гекса-терминал графики на каждый токен?»

**Причина:** Использовал `<div onclick="window.open(...)">` — это НЕ работает надёжно на мобильных (iOS Safari блокирует programmatic window.open вне обработчика жеста пользователя).

## Решение:
- Заменил все 7 `<div class="token-card" onclick="...">` на `<a class="token-card" href="..." target="_blank">`
- `<a href target="_blank">` — это **нативный браузерный способ** открыть ссылку в новой вкладке
- Работает **на всех устройствах**: десктоп, Android, iOS
- Поддерживает **middle-click** на десктопе
- Показывает правильный URL при наведении

## URL'ы (все 7):
- **TON #1**: `https://www.geckoterminal.com/ton/tokens/EQB2T7svf6RzbvYc99jWBfj6n9P3gUsyR4AiiBLgPYIwqKX2`
- **TON #2 (Gemini)**: `https://www.geckoterminal.com/ton/tokens/EQBcUttXk7IhCF23ZghXNc7HY9v3_SAuhsWgW_YHntHsUYtM`
- **TON #3 (BAAL_RA)**: `https://www.geckoterminal.com/ton/tokens/EQC5D3XIrc777bcr8EOQ2_ZBMPuePUqT-zzWTr9-pJEoe7uf`
- **BSC #1 (КРУБЛИК)**: `https://www.geckoterminal.com/bsc/tokens/0x992560BF75de459d708Fad69a1f6cfd24D6181Cf`
- **BSC #2**: `https://www.geckoterminal.com/bsc/tokens/0xFb8a945e263Dcee13D84147305C9bF25543158Eb`
- **BSC #3**: `https://www.geckoterminal.com/bsc/tokens/0x8a3eCb08C627a890736De00BE734E2c68c1A220`
- **BSC #4**: `https://www.geckoterminal.com/bsc/tokens/0x94640e51d4D6C24d373E0756B5780CB45559E4D7`

## Бонус:
- При наведении карточка **приподнимается + золотое свечение**
- Появляется плашка `📈 GeckoTerminal` в углу
- text-decoration:none на <a> — карточка выглядит как обычный div
