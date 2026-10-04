"""Конфигурация обменника: токены, пулы, курсы.

Обнаружено ДВА мастера токена ЦАРЬ от одного эмитента:
  - Старый (основной, ликвидный):
      мастер: EQBcUttXk7IhCF23ZghXNc7HY9v3_SAuhsWgW_YHntHsUYtM
      имя: Gemini, символ: ЦАРЬ
      total supply: 10 000 000 000
      decimals: 9
      сайт: https://sites.google.com/view/ano-center-gemini25
      FDV: $483 005

  - Новый (экспериментальный, нишевая ликвидность):
      мастер: EQB2T7svf6RzbvYc99jWBfj6n9P3gUsyR4AiiBLgPYIwqKX2
      имя: 👑 царь, символ: 👑 ЦАРЬ
      total supply: 1 000 000 000
      decimals: 9
      тот же сайт эмитента
      FDV: $32 180

  - Связующий пул ЦАРЬ ↔ 👑 ЦАРЬ:
      EQByk1LaKJuo5eW1N-PsWjqDeIrPOl5Mv5fLiXgr8EDlxIb1
      (можно использовать для атомарного обмена между токенами)

Основные пулы TON/ЦАРЬ (для офф-рамп):
  - EQAQdBFfSkFbXWB_3jYaREV7aqGXj1S09NX3E03sOkZaUaKz  (основной, Gemini)
  - EQDGUZi_NjzljeAtIXzSQ5eku9YeamABuRftyKN7HC-6Rk_K  (👑 царь)
"""
from __future__ import annotations

# === Основной (Gemini) ===
TSAR_MASTER = "EQBcUttXk7IhCF23ZghXNc7HY9v3_SAuhsWgW_YHntHsUYtM"
TSAR_MASTER_RAW = "0:5c52db5793b221085db766085735cec763dbf7fd202e86c5a05bf6079ed1ec51"
TSAR_NAME = "Gemini"
TSAR_SYMBOL = "ЦАРЬ"
TSAR_DECIMALS = 9
TSAR_TOTAL_SUPPLY = 10_000_000_000_000_000_000_000  # 10 млрд × 10^9
TSAR_FDV_USD = 483_005
TSAR_TON_POOL = "EQAQdBFfSkFbXWB_3jYaREV7aqGXj1S09NX3E03sOkZaUaKz"

# === Новый (👑 царь) ===
TSAR2_MASTER = "EQB2T7svf6RzbvYc99jWBfj6n9P3gUsyR4AiiBLgPYIwqKX2"
TSAR2_MASTER_RAW = "0:764fbb2f7fa4736ef61cf7d8d605f8fa9fd3f7814b324780228812e03d8230a8"
TSAR2_NAME = "👑 царь"
TSAR2_SYMBOL = "👑 ЦАРЬ"
TSAR2_DECIMALS = 9
TSAR2_TOTAL_SUPPLY = 1_000_000_000_000_000_000_000  # 1 млрд × 10^9
TSAR2_FDV_USD = 32_180
TSAR2_TON_POOL = "EQDGUZi_NjzljeAtIXzSQ5eku9YeamABuRftyKN7HC-6Rk_K"

# === Связующий пул ===
TSAR_CROSS_POOL = "EQByk1LaKJuo5eW1N-PsWjqDeIrPOl5Mv5fLiXgr8EDlxIb1"

# === Какие токены принимает обменник ===
ACCEPTED_MASTERS = (TSAR_MASTER, TSAR2_MASTER)
DEFAULT_TSAR_MASTER = TSAR_MASTER  # основной — Gemini

# === Параметры ===
TSAR_POOL_FEE = "0.25"  # %
COINGECKO_TSAR_TOKEN_ID = None  # ещё не зарегистрирован
GECKOTERMINAL_NETWORK = "ton"
USD_RUB_FALLBACK = 90.0
DEFAULT_USER_DAILY_LIMIT_RUB = 100_000