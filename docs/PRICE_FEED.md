# 💰 Price Feed — CoinGecko + GeckoTerminal

Модуль `src/api/payouts/price_feed.py` подтягивает курс ЦАРЬ → RUB с резервными источниками.

## Источники (по приоритету)

| # | Источник | Стоимость | Когда использовать |
|---|---|---|---|
| 1 | CoinGecko Pro | платно (от $39/мес) | прод, стабильность |
| 2 | CoinGecko Free | бесплатно | MVP, 10–30 req/min |
| 3 | GeckoTerminal DEX | бесплатно | fallback на DEX-пулы |
| 4 | Manual override | — | аварийный режим |

## Конфигурация

```bash
# CoinGecko Pro
export COINGECKO_API_KEY=CG-xxx
export COINGECKO_TSAR_TOKEN_ID=tsar-token

# Ручной override (fallback)
export MANUAL_TSAR_RATE=1.0
```

## Как зарегистрировать ЦАРЬ в CoinGecko

1. Подать заявку на https://www.coingecko.com/en/coins/request
2. Указать: тикер, имя, контракт, официальный сайт, логотип
3. Получить `coin_id` (например `tsar-token`) — использовать как `COINGECKO_TSAR_TOKEN_ID`
4. До одобрения работаем через Free API и GeckoTerminal

## DEX-пул (бесплатный fallback)

Если есть пул ЦАРЬ/ТОН на DeDust или другой DEX:

```python
feed = PriceFeed(geckoterminal_pool_address="EQ...")
await feed.get_rate()  # → котировка с GeckoTerminal
```

## Тестирование

```bash
pytest src/api/payouts/tests/test_price_feed.py -v
```