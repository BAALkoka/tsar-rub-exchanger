# 👑 ЦАРЬ_₽А — Landing Page

**Live**: https://tsar-rub-lt87ahb9.agent.mira.tg

## Стек
- Single-file `index.html` (15 913 байт)
- Inline CSS (Cinzel + Inter Google Fonts)
- Vanilla JS (live rate refresh каждые 30 сек)
- Без бэкенда, без сторонних API

## Фичи
- 👑 Hero с **анимированным царём на коне** (CSS-анимация: float, head-nod, gallop, flicker)
- 💰 **3 курса** в реальном времени (BAAL_RA, BLIZNETSY, CROWN) — fallback 83.42 ₽
- 📝 **Форма заявки**: токен + сумма → кнопка открывает Telegram-бота с deep-link
- ⚡ 4 преимущества (мгновенно / безопасно / 3 царя / в Telegram)
- 🏦 9 банков СБП + 8 CARD
- 📱 **Фикс-панель внизу**: 💸 Продать / 💬 Чат / 📢 Канал

## Цветовая палитра
- Gold: #ffd700
- Crimson: #ff8c00
- Dark: #0a0a0a / #1a0f0a
- Highlight: #00d97e (live tag)

## Деплой
```bash
python3 -c "import zipfile; z=zipfile.ZipFile('site.zip','w'); z.write('index.html')"
# загрузить site.zip → S3 → managePages deploy --slug tsar-rub
```

## Репозиторий
GitHub: https://github.com/BAALkoka/tsar-rub-exchanger
