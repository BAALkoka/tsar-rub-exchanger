# Production Deployment Checklist

This repository is prepared for a production deployment, but live deployment itself requires the account credentials and secret values that are stored outside this environment.

Important:
- I cannot access your GitHub account, Telegram account, Render/VPS account, or DNS registrar from this environment.
- I cannot add secrets, DNS records, or webhook configuration on your behalf without your real credentials and access.
- The code and deployment files are ready on the `prod-ready` branch; the remaining steps must be completed from your own account.

## Required secrets and environment values

Set these in your GitHub repository secrets, Render environment variables, or VPS `.env` file:

- TELEGRAM_BOT_TOKEN
- ADMIN_CHAT_ID
- SITE_URL
- DATABASE_URL
- DODO_API_KEY
- DODO_SECRET
- DODO_BASE_URL
- DODO_ENVIRONMENT
- BSC_RPC
- BSC_PRIVATE_KEY or BSC_MNEMONIC
- ADMIN_API_KEY
- PORT
- REDIS_DSN (optional)
- USD_RUB
- SERVICE_FEE_PCT
- SBP_FEE_PCT
- P2P_FEE_PCT
- MIN_PAYOUT_TSAR

## Telegram token

1. Open @BotFather in Telegram.
2. Select your bot.
3. Revoke or regenerate the API token if you previously exposed it.
4. Put the new token only in a secure secret store.
5. Do not paste the token into GitHub issues, public chat, or repository files.

## GitHub / Render / VPS deployment

### GitHub

1. Add repository secrets.
2. Ensure the branch `prod-ready` is used for deployment.
3. Confirm the repository has the correct environment variables configured.

### Render

Use the repository's `render.yaml` and Dockerfiles.

1. Import the repo in Render.
2. Add environment variables above.
3. Set branch to `prod-ready`.
4. Deploy.
5. Verify `/health` returns `200 OK`.

### VPS / Docker

Use Dockerfile.bot and Dockerfile.api.

1. Copy `.env.example` to `.env`.
2. Replace placeholders with real values.
3. Run:

   docker compose up -d --build

4. Verify bot health and startup logs.

## DNS

Configure DNS for your domain and set `SITE_URL` to the HTTPS URL of your deployed app.

Examples:
- `https://api.example.com`
- `https://bot.example.com`

## Final validation

After deployment:

1. Bot responds to `/start` in Telegram.
2. `/health` returns `200` for the API service.
3. Logs show successful bot startup.
4. Dodo API connection works with real credentials.
5. Wallet balance reading works.
6. Order flow can be simulated without failures.

## Status

This repository is prepared for production deployment. The only remaining steps are account-side actions outside this environment:

- Add secrets to GitHub/Render/VPS
- Configure DNS
- Start deployment
- Validate the live app

No further code changes are required on the repo side for the production deployment package itself.
