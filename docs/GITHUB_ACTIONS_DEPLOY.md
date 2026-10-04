# GitHub Actions — бесплатный 24/7 хостинг

## Что внутри
Workflow `.github/workflows/bot-keepalive.yml` запускает бота на GitHub-машинах и держит его живым.

## Стоимость
**$0** — GitHub даёт бесплатно 2000 минут/месяц на публичных репо.

## Ограничения
- Job длится до 6 часов (мы ставим `timeout-minutes: 350`)
- Schedule каждые 30 минут запускает свежий job
- Бот живёт ~350 мин × 30 = ~175 часов в месяц бесплатно

## Секрет
В Settings → Secrets and variables → Actions → New repository secret:
- TELEGRAM_BOT_TOKEN = 6637597430:AAHTkc2hJH6PUzAAkBoBeKVduHEg2rKNHrc

## Как запустить
Автоматически по расписанию (каждые 30 мин) ИЛИ вручную:
1. Открой https://github.com/BAALkoka/tsar-rub-exchanger/actions/workflows/bot-keepalive.yml
2. Нажми Run workflow
3. Подожди 30 секунд — бот стартует