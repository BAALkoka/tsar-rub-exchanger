# 🚀 Деплой на Render.com (Blueprint)

## Шаг 1 — Подключить репо к Render
1. Открой https://dashboard.render.com/blueprints
2. Нажми **"New Blueprint Instance"**
3. Подключи свой GitHub-аккаунт (если не подключён)
4. Выбери репозиторий `BAALkoka/tsar-rub-exchanger`
5. Render найдёт `infra/render.yaml` и предложит план
6. Нажми **"Apply"**

## Шаг 2 — Добавить секреты
Render покажет форму с переменными `sync: false`:
- `TELEGRAM_BOT_TOKEN` → `6637597430:AAHTkc2hJH6PUzAAkBoBeKVduHEg2rKNHrc`
- `BOT_WEBHOOK_URL` → оставь пустым (мы используем polling)

Или добавь через dashboard → Environment → Add Secret.

## Шаг 3 — Дождаться билда (~5 минут)
Render покажет логи. После успеха:
- API: `https://tsar-exchanger-api.onrender.com/health`
- Бот: в Telegram @BAAL_NIK_BOT — нажми /start

## Что внутри
| Сервис | Тип | Что делает |
|---|---|---|
| `tsar-exchanger-api` | web | FastAPI + healthcheck, не даёт Render заснуть |
| `tsar-exchanger-bot` | worker | Telegram-бот в polling-режиме |

## Бесплатные ограничения Render
- 750 часов/мес (worker + web = 2 машины, ≈700 часов)
- Спит после 15 минут idle → бот worker не спит, api держит веб
- Для прод-нагрузок → перейти на Starter ($7/мес за каждый)