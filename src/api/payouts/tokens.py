"""Метаданные токенов ЦАРЬ."""
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class TokenMeta:
    slug: str
    name: str
    symbol: str
    master: str              # jetton-master адрес (EQ...)
    pool: str                # пул ликвидности на DeDust
    decimals: int
    min_tsar: int
    description: str
    emoji: str = "👑"        # атрибут царь (по умолчанию — корона)


TOKENS = {
    "BAAL_RA": TokenMeta(
        slug="BAAL_RA",
        name="Царь BAAL_RA",
        symbol="ЦАРЬ",
        master="EQC5D3XIrc777bcr8EOQ2_ZBMPuePUqT-zzWTr9-pJEoe7uf",
        pool="EQBfclRZ2puWZvqy85DbMhKnqZh2386mxrOKki8GZo3YDgq4",
        decimals=9,
        min_tsar=250_000,
        description="Основной токен ЦАРЬ (BAAL_RA)",
        emoji="👑",
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
        emoji="♊",
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
        emoji="👑",
    ),
}

DEFAULT_TOKEN = TOKENS["BAAL_RA"]


def get_token(slug: str) -> Optional[TokenMeta]:
    return TOKENS.get(slug)


def list_tokens() -> list[TokenMeta]:
    return list(TOKENS.values())


def find_by_master(master: str) -> Optional[TokenMeta]:
    """Найти токен по jetton-master-адресу (для автоопределения при переводе)."""
    for t in TOKENS.values():
        if t.master == master:
            return t
    return None


def short_master(master: str) -> str:
    """Короткая запись адреса: EQC5D3...oe7uf"""
    if not master or len(master) < 10:
        return master
    return f"{master[:6]}…{master[-6:]}"