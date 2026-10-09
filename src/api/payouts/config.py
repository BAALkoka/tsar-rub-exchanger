"""Конфигурация off-ramp сервиса ЦАРЬ → RUB → карта."""
from __future__ import annotations
import os

# === MASTER-адреса ===
TSAR_MASTER = "EQC5D3XIrc777bcr8EOQ2_ZBMPuePUqT-zzWTr9-pJEoe7uf"
TSAR_MASTER_RAW = "0:b90f75c8adcefbedb72bf04390dbf64130fb9e3d4a93fb3cd64ebf7ea491287b"
TSAR_NAME = "BAAL_RA"
TSAR_SYMBOL = "ЦАРЬ"
TSAR_DECIMALS = 9
TSAR_TOTAL_SUPPLY = 100_000_000_000_000
TSAR_FDV_USD = 1_423_809_143

# === Пулы ===
TSAR_USDT_POOL = "EQBfclRZ2puWZvqy85DbMhKnqZh2386mxrOKki8GZo3YDgq4"
TSAR_WBTC_POOL = "EQDIcp8Av-6nkhC8NgBF_0posdKbyAcXieNMFQn-Dtzx_Ei7"
TSAR_PRIMARY_POOL = TSAR_USDT_POOL

# === Наследие ===
TSAR_LEGACY_BLIZNETSY = "EQBcUttXk7IhCF23ZghXNc7HY9v3_SAuhsWgW_YHntHsUYtM"
TSAR_LEGACY_CROWN = "EQB2T7svf6RzbvYc99jWBfj6n9P3gUsyR4AiiBLgPYIwqKX2"
ACCEPTED_MASTERS = (TSAR_MASTER, TSAR_LEGACY_BLIZNETSY, TSAR_LEGACY_CROWN)

# === Тонкости ===
TSAR_CROSS_POOL = "EQByk1LaKJuo5eW1N-PsWjqDeIrPOl5Mv5fLiXgr8EDlxIb1"
TSAR_POOL_FEE = "0.25"
COINGECKO_TSAR_TOKEN_ID = None
GECKOTERMINAL_NETWORK = "ton"

# === Курсы ===
USD_RUB_FALLBACK = float(os.getenv("USD_RUB_FALLBACK", "90.0"))

# === Лимиты ===
DEFAULT_USER_DAILY_LIMIT_RUB = 100_000

# === Поддержка ===
SUPPORT_HANDLE = "@BAAL_NIK"
SUPPORT_URL = "https://t.me/BAAL_NIK"

# === Кошелёк для приёма USDT перед P2P-выплатой ===
USDT_TREASURY_ADDRESS = os.getenv("USDT_TREASURY_ADDRESS", "UQA5gfkm8i4DutEDkMvjmTi3N8VC46yZHKAK_nnpYjawvTu7")
TSAR_TREASURY_ADDRESS = os.getenv("TSAR_TREASURY_ADDRESS", "UQA5gfkm8i4DutEDkMvjmTi3N8VC46yZHKAK_nnpYjawvTu7")

# === P2P Market (WalletBot) ===
# 1. Секрет GitHub Actions P2P_API_KEY (реальный, зашифрован libsodium)
# 2. Fallback в открытом коде (опц.) — если секрет не задан, P2P использует эту строку
# 3. Если и она пустая — P2PClient вернёт P2PError(401), бот покажет "P2P недоступен"
P2P_API_URL = os.getenv("P2P_API_URL", "https://p2p.walletbot.me")
P2P_API_KEY = os.getenv("P2P_API_KEY", "") or os.getenv("P2P_API_KEY_FALLBACK", "")
P2P_PATH = "/p2p/integration-api/v1/item/online"

# === TON API ===
TONAPI_TOKEN = os.getenv("TONAPI_TOKEN", "")

# === Админ для уведомлений ===
ADMIN_CHAT_ID = int(os.getenv("ADMIN_CHAT_ID", "0") or "0")
