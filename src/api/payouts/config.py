"""Конфигурация обменника: токены, пулы, курсы.

Все реальные идентификаты найдены автоматически:
  - jetton-мастер ЦАРЬ: EQBcUttXk7IhCF23ZghXNc7HY9v3_SAuhsWgW_YHntHsUYtM
  - jetton-мастер ЦАРЬ (raw): 0:5c52db5793b221085db766085735cec763dbf7fd202e86c5a05bf6079ed1ec51
  - пул TON/ЦАРЬ (DeDust): EQAQdBFfSkFbXWB_3jYaREV7aqGXj1S09NX3E03sOkZaUaKz
  - decimals: 9
  - total supply: 10_000_000_000 * 10^9
"""
from __future__ import annotations

# Jetton-метаданные
TSAR_MASTER = "EQBcUttXk7IhCF23ZghXNc7HY9v3_SAuhsWgW_YHntHsUYtM"
TSAR_MASTER_RAW = "0:5c52db5793b221085db766085735cec763dbf7fd202e86c5a05bf6079ed1ec51"
TSAR_NAME = "Gemini"
TSAR_SYMBOL = "ЦАРЬ"
TSAR_DECIMALS = 9
TSAR_TOTAL_SUPPLY = 10_000_000_000_000_000_000_000  # 10 млрд

# Основной пул для ликвидности TON ↔ ЦАРЬ
TSAR_TON_POOL = "EQAQdBFfSkFbXWB_3jYaREV7aqGXj1S09NX3E03sOkZaUaKz"
TSAR_POOL_FEE = "0.25"  # %

# Источники цен
COINGECKO_TSAR_TOKEN_ID = None  # не зарегистрирован, ждём
GECKOTERMINAL_NETWORK = "ton"

# Резервный курс USD/RUB на случай ошибки фида (обновляется руками)
USD_RUB_FALLBACK = 90.0

# Дневной лимит на одного пользователя (RUB)
DEFAULT_USER_DAILY_LIMIT_RUB = 100_000