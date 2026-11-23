# Deploy to Fly.io

```bash
curl -L https://fly.io/install.sh | sh
fly auth signup
fly launch --no-deploy
fly secrets set TELEGRAM_BOT_TOKEN="<TELEGRAM_BOT_TOKEN>"
fly deploy
fly status
```

## Tunnel command
If Fly requires credit card even for free tier:
```bash
fly launch --no-deploy --copy-config
fly secrets set TELEGRAM_BOT_TOKEN="..."
fly deploy
```