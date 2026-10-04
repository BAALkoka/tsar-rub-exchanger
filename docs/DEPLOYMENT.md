# 🚀 Деплой

## Render (web API)

1. https://render.com → New + → Blueprint
2. Подключите `BAALkoka/tsar-rub-exchanger`
3. Render увидит `infra/render.yaml`
4. Добавьте env-vars: `TELEGRAM_BOT_TOKEN`, `TINKOFF_TERMINAL_KEY`, `TINKOFF_PASSWORD`

## Background Worker (бот)

На Render — отдельный "Background Worker":
- Build: `pip install -r src/api/payouts/requirements.txt && pip install aiogram==3.13.1`
- Start: `python -m bot.main`

## VPS (дешевле, надёжнее)

```bash
git clone https://github.com/BAALkoka/tsar-rub-exchanger.git
cd tsar-rub-exchanger
docker build -t tsar .
docker run -d --restart=always -p 8080:8080 \
  -e TELEGRAM_BOT_TOKEN=$TOKEN \
  -e TINKOFF_TERMINAL_KEY=$TK \
  -e TINKOFF_PASSWORD=$PW \
  --name tsar tsar

# Бот — отдельный процесс
TELEGRAM_BOT_TOKEN=$TOKEN python -m bot.main
```

## Проверка после деплоя

```bash
curl https://your-app.onrender.com/health
# {"status":"ok","tsar_master":"EQC5D3X...","pool":"EQBfclRZ..."}
```