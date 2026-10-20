# 👑 ЦАРЬ Exchange MVP

Это каркас работоспособного MVP обменника с ручной админ‑выплатой. Проект состоит из:

- backend API (Express + Postgres or in-memory fallback)
- admin UI для просмотра ордеров и manual payouts
- BSC watcher placeholder with webhook to backend
- TON placeholder
- Docker Compose для локального запуска

## Быстрый запуск

1. Скопируйте env:
   ```bash
   cp exchange/.env.example exchange/.env
   ```
2. Отредактируйте `exchange/.env` под вашу среду.
3. Запустите:
   ```bash
   docker compose -f exchange/docker-compose.yml up --build
   ```
4. Откройте:
   - API: http://localhost:3000/health
   - Admin UI: http://localhost:8080/

## API

- `GET /health`
- `POST /api/orders`
- `GET /api/admin/orders`
- `POST /api/webhook/deposit`
- `POST /api/admin/payouts/:id`

## Безопасность

- Никогда не храните секретные ключи в git.
- Используйте GitHub Secrets, Render Secrets, Vault or .env on local only.
- Для production обязательно подключить KYC/AML и подготовить договоры с эквайером / банком.

## Важное

Этот код — рабочий MVP‑каркас, не финальная регулируемая платёжная система. Для реальных выплат на карту/СБП/P2P потребуется договор, KYC и реальные провайдерские API.

## Game

Игровой мини‑проект уже опубликован отдельно:
- https://BAALkoka.github.io/tsar-rub-exchanger/game/

## TODO

- заменить TON placeholder на tonweb/ton-client-js
- подключить реальный RPC и контракт токена
- подключить эквайер/SBP на уровне payouts
- добавить протокол KYC/AML
- перенести production deployment на VPS / Render / Fly

