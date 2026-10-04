# TON Escrow — ЦАРЬ

Смарт-контракт для приёма токенов ЦАРЬ и условного депонирования до подтверждения выплаты в RUB.

## Жизненный цикл

```
[Юзер]                [Escrow]            [Backend]            [СБП]
   | --deposit ЦАРЬ--> |                    |                       |
   |                    | --on deposit------>                       |
   |                    |                    | ---выплата ₽------->  |
   |                    |                    | <--статус-------------|
   | <--error-----------|                    |                       |
   | --refund (24h)---->|                     |
```

## Команды

### Сборка
```bash
func -o build/escrow.fif src/onchain/escrow/contract.fc
```

### Тесты
```bash
# TODO: ton-contract-executor tests
```

## Безопасность

Перед продом **обязателен** аудит:
- Reentrancy
- Атомарность (deposit + confirm + refund)
- Multisig для крупных сумм

## TODO

- [ ] Jetton-wallet интеграция (вместо нативного TON)
- [ ] Multisig-адрес для подтверждений
- [ ] Тесты на testnet
- [ ] Аудит безопасности