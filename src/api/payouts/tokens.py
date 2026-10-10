"""Метаданные токенов серии ЦАРЬ. v3.1 — 3 TON + 4 BSC = 7 токенов."""
from dataclasses import dataclass
from typing import Optional


@dataclass
class TokenMeta:
    slug: str
    name: str
    symbol: str
    network: str
    master: str
    pool: str
    pool_label: str
    decimals: int
    min_tsar: int
    description: str
    emoji: str = "👑"
    gecko_url: str = ""


# === TON ===
TSAR_MASTER_BAAL_RA   = "EQC5D3XIrc777bcr8EOQ2_ZBMPuePUqT-zzWTr9-pJEoe7uf"
TSAR_MASTER_BLIZNETSY = "EQBcUttXk7IhCF23ZghXNc7HY9v3_SAuhsWgW_YHntHsUYtM"
TSAR_MASTER_CROWN     = "EQB2T7svf6RzbvYc99jWBfj6n9P3gUsyR4AiiBLgPYIwqKX2"

POOL_BAAL_RA_USDT   = "EQBfclRZ2puWZvqy85DbMhKnqZh2386mxrOKki8GZo3YDgq4"
POOL_BLIZNETSY_TON  = "EQAQdBFfSkFbXWB_3jYaREV7aqGXj1S09NX3E03sOkZaUaKz"
POOL_CROWN_TON      = "EQDGUZi_NjzljeAtIXzSQ5eku9YeamABuRftyKN7HC-6Rk_K"

# === BSC ===
BSC_TOKEN_1 = "0xfb8a945e263dcee13d84147305c9bf25543158eb"
BSC_TOKEN_2 = "0x992560bf75de459d708fad69a1f6cfd24d6181cf"
BSC_TOKEN_3 = "0x94640e51d4d6c24d373e0756b5780cb45559e4d7"
BSC_TOKEN_4 = "0x8a3ecb08c627a890736dec00be734e2c68c1a220"

POOL_BSC_1_WBNB = "0xf782639538de63c67b759ca3f4be82d96368a2dd"
POOL_BSC_2_ETH  = "0x6f049ab46a4ddf4299eef4dd8808b8ec6b763082"
POOL_BSC_3_CLMM = "0xc8f0bf58c185133fb125962eda12b814cf8935d4f45cbc8d67f4a83ce8825360"
POOL_BSC_4_WBNB = "0x99705be5b0b1d27b6fabfe4a4613cd5b34f3658d"


TOKENS = {
    "BAAL_RA": TokenMeta(
        slug="BAAL_RA", name="Царь BAAL_RA", symbol="ЦАРЬ", network="ton",
        master=TSAR_MASTER_BAAL_RA, pool=POOL_BAAL_RA_USDT, pool_label="USDT",
        decimals=9, min_tsar=250_000, description="Основной ЦАРЬ — DeDust USDT",
        emoji="👑", gecko_url="https://www.geckoterminal.com/ton/pools/" + POOL_BAAL_RA_USDT,
    ),
    "BLIZNETSY": TokenMeta(
        slug="BLIZNETSY", name="Царь Близнецы", symbol="ЦАРЬ♊", network="ton",
        master=TSAR_MASTER_BLIZNETSY, pool=POOL_BLIZNETSY_TON, pool_label="TON",
        decimals=9, min_tsar=250_000, description="Близнецы — DeDust TON",
        emoji="♊", gecko_url="https://www.geckoterminal.com/ton/pools/" + POOL_BLIZNETSY_TON,
    ),
    "CROWN": TokenMeta(
        slug="CROWN", name="Царь с коронкой", symbol="ЦАРЬ👑", network="ton",
        master=TSAR_MASTER_CROWN, pool=POOL_CROWN_TON, pool_label="TON",
        decimals=9, min_tsar=250_000, description="С коронкой — DeDust TON",
        emoji="👑", gecko_url="https://www.geckoterminal.com/ton/pools/" + POOL_CROWN_TON,
    ),
    "BSC_TSAR_1": TokenMeta(
        slug="BSC_TSAR_1", name="ЦАРЬ BSC #1", symbol="ЦАРЬ", network="bsc",
        master=BSC_TOKEN_1, pool=POOL_BSC_1_WBNB, pool_label="WBNB",
        decimals=18, min_tsar=100_000, description="ЦАРЬ/WBNB V2",
        emoji="👑", gecko_url="https://www.geckoterminal.com/bsc/pools/" + POOL_BSC_1_WBNB,
    ),
    "BSC_TSAR_2": TokenMeta(
        slug="BSC_TSAR_2", name="ЦАРЬ BSC #2", symbol="ЦАРЬ", network="bsc",
        master=BSC_TOKEN_2, pool=POOL_BSC_2_ETH, pool_label="ETH",
        decimals=18, min_tsar=100_000, description="ЦАРЬ/ETH V2",
        emoji="👑", gecko_url="https://www.geckoterminal.com/bsc/pools/" + POOL_BSC_2_ETH,
    ),
    "BSC_HTTPS_DR": TokenMeta(
        slug="BSC_HTTPS_DR", name="HTTPS://DR", symbol="DR", network="bsc",
        master=BSC_TOKEN_3, pool=POOL_BSC_3_CLMM, pool_label="BNB",
        decimals=18, min_tsar=100_000, description="DR/BNB CLMM",
        emoji="🔗", gecko_url="https://www.geckoterminal.com/bsc/pools/" + POOL_BSC_3_CLMM,
    ),
    "BSC_TSAR_4": TokenMeta(
        slug="BSC_TSAR_4", name="ЦАРЬ BSC #4", symbol="ЦАРЬ", network="bsc",
        master=BSC_TOKEN_4, pool=POOL_BSC_4_WBNB, pool_label="WBNB",
        decimals=18, min_tsar=100_000, description="ЦАРЬ/WBNB V2",
        emoji="👑", gecko_url="https://www.geckoterminal.com/bsc/pools/" + POOL_BSC_4_WBNB,
    ),
}

DEFAULT_TOKEN = TOKENS["BAAL_RA"]


def get_token(slug: str) -> Optional[TokenMeta]:
    return TOKENS.get(slug)


def list_tokens() -> list[TokenMeta]:
    return list(TOKENS.values())


def list_by_network(network: str) -> list[TokenMeta]:
    return [t for t in TOKENS.values() if t.network == network]


def find_by_master(master: str) -> Optional[TokenMeta]:
    for t in TOKENS.values():
        if t.master == master:
            return t
    return None


def find_by_pool(pool: str) -> Optional[TokenMeta]:
    for t in TOKENS.values():
        if t.pool == pool:
            return t
    return None


def short_address(addr: str) -> str:
    if not addr or len(addr) < 12:
        return addr or "—"
    return f"{addr[:6]}…{addr[-4:]}"


short_master = short_address
