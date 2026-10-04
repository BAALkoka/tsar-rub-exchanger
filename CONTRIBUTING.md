# Contributing

Спасибо, что хочешь контрибьютить в **ЦАРЬ → RUB → Карта** 👑

## Установка

```bash
git clone https://github.com/BAALkoka/tsar-rub-exchanger.git
cd tsar-rub-exchanger
```

## Структура

| Путь | Назначение |
|---|---|
| `src/api/payouts/` | Backend: выплаты через СБП |
| `src/bot/` | Telegram-бот на aiogram v3 |
| `src/onchain/escrow/` | TON-смарт-контракт (FunC) |
| `docs/` | Архитектура и спеки |

## Разработка

### Backend
```bash
cd src/api/payouts
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pytest tests/
```

### Bot
```bash
cd src/bot
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export BOT_TOKEN=...
python main.py
```

### TON escrow
```bash
func -o build/escrow.fif src/onchain/escrow/contract.fc
```

## Code style

- Python: `ruff` + `mypy`
- Docstrings — на русском для продукта, на английском — для generic utils
- Логи — через `logging`, никаких `print`

## Pull request

1. Создай ветку `feat/...`, `fix/...`, `docs/...`
2. Заполни `.github/PULL_REQUEST_TEMPLATE.md`
3. Убедись, что CI зелёный
4. Запроси review у `@BAALkoka`

## Issues

Используй шаблоны:
- 🐛 Bug report
- ✨ Feature request
- 📋 Spec
- ⚖️ Compliance

## Коммуникация

Telegram: [@BAAL_NIK](https://t.me/BAAL_NIK_2505lis)