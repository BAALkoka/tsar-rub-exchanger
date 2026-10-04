# ⛓ TON Pool Finder

Утилита для автоматического обнаружения DEX-пула ЦАРЬ/ТОН по адресу кошелька.

## Использование

```bash
python -m src.api.payouts.ton_pools EQAQdBFfSkFbXWB_3jYaREV7aqGXj1S09NX3E03sOkZaUaKz

# С TON API токеном (для повышенных лимитов)
export TONAPI_TOKEN=xxx
python -m src.api.payouts.ton_pools EQAQdBFfSkFbXWB_3jYaREV7aqGXj1S09NX3E03sOkZaUaKz
```

## Что делает

1. Берёт кошелёк
2. Через tonapi.io тянет список jetton-контрактов
3. Фильтрует жетоны со словом ЦАРЬ/TSAR
4. Ищет для каждого пул на DeDust
5. Возвращает адрес пула — его вписываем в GeckoTerminal

## Ручной способ найти пул

Если автопоиск не сработал:

1. Открыть DeDust https://app.dedust.io/pools
2. Найти пул TON-ЦАРЬ
3. Скопировать адрес пула
4. Передать в `PriceFeed(geckoterminal_pool_address=...)`