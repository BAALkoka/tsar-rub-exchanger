"""Метаданные токенов серии ЦАРЬ.

Каждый токен имеет:
  - emoji-атрибут 👑 (визуальный признак царя)
  - jetton-master (адрес контракта в TON)
  - pool (DeDust-пул для расчёта курса)
"""
from dataclasses import dataclass
from typing import Optional


@dataclass
class TokenMeta:
    slug: str
    name: str
    symbol: str
    master: str               # jetton-master (EQ...)
    pool: str                 # DeDust-пул (EQB...)
    pool_label: str           # что в пуле: TON, USDT, jWBTC
    decimals: int
    min_tsar: int
    description: str
    emoji: str = "👑"          # атрибут царь


# === Мастер-адреса ===
TSAR_MASTER_BAAL_RA = "EQC5D3XIrc777bcr8EOQ2_ZBMPuePUqT-zzWTr9-pJEoe7uf"
TSAR_MASTER_BLIZNETSY  = "EQBcUttXk7IhCF23ZghXNc7HY9v3_SAuhsWgW_YHntHsUYtM"
TSAR_MASTER_CROWN   = "EQB2T7svf6RzbvYc99jWBfj6n9P3gUsyR4AiiBLgPYIwqKX2"

# === DeDust-пулы (самые ликвидные по каждому токену) ===
POOL_BAAL_RA_USDT   = "EQBfclRZ2puWZvqy85DbMhKnqZh2386mxrOKki8GZo3YDgq4"  # USD₮/ЦАРЬ
POOL_BLIZNETSY_TON     = "EQAQdBFfSkFbXWB_3jYaREV7aqGXj1S09NX3E03sOkZaUaKz"  # BLIZNETSY/TON
POOL_CROWN_TON      = "EQDGUZi_NjzljeAtIXzSQ5eku9YeamABuRftyKN7HC-6Rk_K"  # CROWN/TON


TOKENS = {
    "BAAL_RA": TokenMeta(
        slug="BAAL_RA",
        name="Царь BAAL_RA",
        symbol="ЦАРЬ",
        master=TSAR_MASTER_BAAL_RA,
        pool=POOL_BAAL_RA_USDT,
        pool_label="USDT",
        decimals=9,
        min_tsar=250_000,
        description="Основной токен ЦАРЬ (BAAL_RA) — DeDust USD₮-пул",
        emoji="👑",
    ),
    "BLIZNETSY": TokenMeta(
        slug="BLIZNETSY",
        name="Царь Близнецы",
        symbol="ЦАРЬ♊",
        master=TSAR_MASTER_BLIZNETSY,
        pool=POOL_BLIZNETSY_TON,
        pool_label="TON",
        decimals=9,
        min_tsar=250_000,
        description="Царь Близнецы — Bliznetsy-серия — DeDust TON-пул",
        emoji="♊",
    ),
    "CROWN": TokenMeta(
        slug="CROWN",
        name="Царь с коронкой",
        symbol="ЦАРЬ👑",
        master=TSAR_MASTER_CROWN,
        pool=POOL_CROWN_TON,
        pool_label="TON",
        decimals=9,
        min_tsar=250_000,
        description="Царь с коронкой — коллекционная серия — DeDust TON-пул",
        emoji="👑",
    ),
}

DEFAULT_TOKEN = TOKENS["BAAL_RA"]


def get_token(slug: str) -> Optional[TokenMeta]:
    return TOKENS.get(slug)


def list_tokens() -> list[TokenMeta]:
    return list(TOKENS.values())


def find_by_master(master: str) -> Optional[TokenMeta]:
    """Найти токен по jetton-master (для автодетекта при IP-переводе)."""
    for t in TOKENS.values():
        if t.master == master:
            return t
    return None


def find_by_pool(pool: str) -> Optional[TokenMeta]:
    """Найти токен по DeDust-пулу."""
    for t in TOKENS.values():
        if t.pool == pool:
            return t
    return None


def short_master(master: str) -> str:
    if not master or len(master) < 10:
        return master
    return f"{master[:6]}…{master[-6:]}"
