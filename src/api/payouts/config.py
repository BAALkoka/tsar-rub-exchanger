"""Конфигурация обменника: токены, пулы, курсы.

В серии "ЦАРЬ" есть ТРИ jetton-мастера от одного эмитента:

  - Основной (АНО ЦЕНТР БЛИЗНЕЦЫ, BAAL_RA, Николай Александрович Ш.):
      мастер: EQC5D3XIrc777bcr8EOQ2_ZBMPuePUqT-zzWTr9-pJEoe7uf
      имя: BAAL_RA, символ: ЦАРЬ
      total supply: 100 000
      decimals: 9
      сайт: https://sites.google.com/view/2505lis
      описание: АНО ЦЕНТР БЛИЗНЕЦЫ (с 2019), планы на золотые монеты и биржу
      ПУЛ USDT/ЦАРЬ: EQBfclRZ2puWZvqy85DbMhKnqZh2386mxrOKki8GZo3YDgq4
      1 ЦАРЬ ≈ 83 ₽ (FDV $1.4B, ликпул пока тонкий)

  - Тестовые/экспериментальные (для совместимости):
      - EQBcUttXk7IhCF23ZghXNc7HY9v3_SAuhsWgW_YHntHsUYtM (Gemini, supply 10B)
      - EQB2T7svf6RzbvYc99jWBfj6n9P3gUsyR4AiiBLgPYIwqKX2 (👑 царь, supply 1B)

  - Связующие пулы ЦАРЬ ↔ ЦАРЬ (можно использовать для арбитража):
      EQByk1LaKJuo5eW1N-PsWjqDeIrPOl5Mv5fLiXgr8EDlxIb1
"""
from __future__ import annotations

# === ОСНОВНОЙ: BAAL_RA (АНО ЦЕНТР БЛИЗНЕЦЫ) ===
TSAR_MASTER = "EQC5D3XIrc777bcr8EOQ2_ZBMPuePUqT-zzWTr9-pJEoe7uf"
TSAR_MASTER_RAW = "0:b90f75c8adcefbedb72bf04390dbf64130fb9e3d4a93fb3cd64ebf7ea491287b"
TSAR_NAME = "BAAL_RA"
TSAR_SYMBOL = "ЦАРЬ"
TSAR_DECIMALS = 9
TSAR_TOTAL_SUPPLY = 100_000_000_000_000  # 100 тыс × 10^9
TSAR_FDV_USD = 1_423_809_143  # ~$1.4 млрд
TSAR_USDT_POOL = "EQBfclRZ2puWZvqy85DbMhKnqZh2386mxrOKki8GZo3YDgq4"
TSAR_WBTC_POOL = "EQDIcp8Av-6nkhC8NgBF_0posdKbyAcXieNMFQn-Dtzx_Ei7"

# Используется пул USDT/ЦАРЬ как основной источник цены
TSAR_PRIMARY_POOL = TSAR_USDT_POOL

# === Тестовые (принимаем, но с пометкой) ===
TSAR_LEGACY_GEMINI = "EQBcUttXk7IhCF23ZghXNc7HY9v3_SAuhsWgW_YHntHsUYtM"  # Gemini, supply 10B
TSAR_LEGACY_CROWN = "EQB2T7svf6RzbvYc99jWBfj6n9P3gUsyR4AiiBLgPYIwqKX2"  # 👑 царь, supply 1B

# === Все принимаемые мастера ===
ACCEPTED_MASTERS = (TSAR_MASTER, TSAR_LEGACY_GEMINI, TSAR_LEGACY_CROWN)

# === Связующий пул ===
TSAR_CROSS_POOL = "EQByk1LaKJuo5eW1N-PsWjqDeIrPOl5Mv5fLiXgr8EDlxIb1"

# === Параметры ===
TSAR_POOL_FEE = "0.25"  # %
COINGECKO_TSAR_TOKEN_ID = None  # ещё не зарегистрирован
GECKOTERMINAL_NETWORK = "ton"
USD_RUB_FALLBACK = 90.0
DEFAULT_USER_DAILY_LIMIT_RUB = 100_000
EMITTER_SITE = "https://sites.google.com/view/2505lis"
EMITTER_ORG = "АНО ЦЕНТР БЛИЗНЕЦЫ"