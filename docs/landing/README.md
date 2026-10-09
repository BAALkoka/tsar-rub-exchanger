# 👑 ЦАРЬ_₽А — Landing Page

**Live**: https://tsar-rub-lt87ahb9.agent.mira.tg

## Стек
- Single-file `index.html` (14 421 байт, v3)
- Inline CSS (Cinzel + Inter Google Fonts)
- Vanilla JS (live rate + order form)
- Без бэкенда, без сторонних API

## Фичи (v3)
- 👑 Hero с **анимированным царём на коне** (CSS-анимация: float, head-nod, gallop, flicker)
- 💰 **3 курса** в реальном времени (BAAL_RA, BLIZNETSY, CROWN) — fallback 83.42 ₽
- 📝 **Форма заявки**: токен + сумма → deep-link в Telegram-бота
- ⚡ 4 преимущества
- 🏦 9 банков СБП + 8 CARD
- 📱 **Фикс-панель внизу**: 💸 Продать / 💬 Чат / 📢 Канал
- 🧹 **v3**: убраны все личные данные (2505lis)

## Деплой
```bash
python3 -c "import zipfile; z=zipfile.ZipFile('site.zip','w'); z.write('index.html')"
# загрузить site.zip → S3 → managePages deploy --slug tsar-rub
```

## Репозиторий
GitHub: https://github.com/BAALkoka/tsar-rub-exchanger
