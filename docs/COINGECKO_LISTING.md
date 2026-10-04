# 🦎 CoinGecko Listing Kit

Полный пакет документов для подачи заявки на листинг серии ЦАРЬ.

## Заявка

Подаётся через https://www.coingecko.com/en/coins/request

## Готовые ответы

### Coin name (имя)
```
Gemini
```

### Coin symbol (тикер)
```
ЦАРЬ
```

### Token type
```
TON (Jetton)
```

### Contract address (blockchain explorer)
```
EQBcUttXk7IhCF23ZghXNc7HY9v3_SAuhsWgW_YHntHsUYtM
```
Метаданные: https://tonviewer.com/EQBcUttXk7IhCF23ZghXNc7HY9v3_SAuhsWgW_YHntHsUYtM

### Website / homepage
```
https://sites.google.com/view/ano-center-gemini25
```

### Whitepaper / docs
```
https://github.com/BAALkoka/tsar-rub-exchanger/blob/main/ROADMAP.md
```

### Description (до 500 знаков)
```
Gemini (ЦАРЬ) — серия токенов на TON с off-ramp обменником в RUB. 
Ликвидность на DeDust, прямой вывод на карты и СБП. 
Миссия — связать крипто-экономику ЦАРЬ с реальными рублёвыми платежами.
```

### Logo (уже есть)
```
https://storage.dyor.io/jettons/images/1714335822/14924886.webp
```

### Social links
```
Telegram: https://t.me/BAAL_NIK_2505lis
GitHub: https://github.com/BAALkoka/tsar-rub-exchanger
```

### Decimals
```
9
```

### Total supply
```
10,000,000,000 ЦАРЬ
```

### Circulating supply (на сейчас)
```
TBD (зависит от баланса на кошельке CoinGecko Keeper)
```

## Что добавит листинг

- Публичная страница https://www.coingecko.com/en/coins/...
- Глобальный тикер
- Возможность добавить в портфели на CMC/CoinGecko
- Включение в ценовые агрегаторы (Coinpaprika, LiveCoinWatch)
- Канонический `coin_id` для нашего PriceFeed

## После одобрения

```bash
export COINGECKO_TSAR_TOKEN_ID=gemini-  # какой ID присвоят
# → price_feed.py начнёт тянуть реальные котировки автоматически
```