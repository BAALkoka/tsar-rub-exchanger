"""Метаданные токенов ЦАРЬ."""
from dataclasses import dataclass
from typing import Optional


@dataclass
class TokenMeta:
    slug: str
    name: str
    symbol: str
    master: str
    pool: str
    decimals: int
    min_tsar: int
    description: str


TOKENS = {
    "BAAL_RA": TokenMeta(
        slug="BAAL_RA",
        name="Царь",
        symbol="ЦАРЬ",
        master="EQC5D3XIrc777bcr8EOQ2_ZBMPuePUqT-zzWTr9-pJEoe7uf",
        pool="EQBfclRZ2puWZvqy85DbMhKnqZh2386mxrOKki8GZo3YDgq4",
        decimals=9,
        min_tsar=250_000,
        description="Основной токен ЦАРЬ (BAAL_RA)",
    ),
    "GEMINI": TokenMeta(
        slug="GEMINI",
        name="Царь Гемини",
        symbol="ЦАРЬ♊",
        master="EQBcUttXk7IhCF23ZghXNc7HY9v3_SAuhsWgW_YHntHsUYtM",
        pool="EQBfclRZ2puWZvqy85DbMhKnqZh2386mxrOKki8GZo3YDgq4",
        decimals=9,
        min_tsar=250_000,
        description="Царь Гемини — Gemini-серия",
    ),
    "CROWN": TokenMeta(
        slug="CROWN",
        name="Царь с коронкой",
        symbol="ЦАРЬ👑",
        master="EQB2T7svf6RzbvYc99jWBfj6n9P3gUsyR4AiiBLgPYIwqKX2",
        pool="EQBfclRZ2puWZvqy85DbMhKnqZh2386mxrOKki8GZo3YDgq4",
        decimals=9,
        min_tsar=250_000,
        description="Царь с коронкой — коллекционная серия",
    ),
}

DEFAULT_TOKEN = TOKENS["BAAL_RA"]


def get_token(slug: str) -> Optional[TokenMeta]:
    return TOKENS.get(slug)


def list_tokens() -> list[TokenMeta]:
    return list(TOKENS.values())
