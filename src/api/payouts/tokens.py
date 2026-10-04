"""Каталог поддерживаемых ЦАРЬ-токенов.

Эмитент: АНО ЦЕНТР БЛИЗНЕЦЫ (Николай Александрович Ш.)
Сайт: https://baal.tb.ru/2505lis
"""
from __future__ import annotations
from dataclasses import dataclass
from .config import (
    TSAR_MASTER,
    TSAR_LEGACY_GEMINI,
    TSAR_LEGACY_CROWN,
    TSAR_PRIMARY_POOL,
)


@dataclass(frozen=True)
class TokenMeta:
    code: str
    symbol: str
    name: str
    master: str
    pool: str
    decimals: int
    description: str
    emoji: str
    is_primary: bool


TOKENS: dict[str, TokenMeta] = {
    "BAAL_RA": TokenMeta(
        code="BAAL_RA",
        symbol="ЦАРЬ",
        name="BAAL RA (основной)",
        master=TSAR_MASTER,
        pool=TSAR_PRIMARY_POOL,
        decimals=9,
        description="Основной выпуск АНО ЦЕНТР БЛИЗНЕЦЫ. 100 000 supply.",
        emoji="👑",
        is_primary=True,
    ),
    "GEMINI": TokenMeta(
        code="GEMINI",
        symbol="ЦАРЬ-GEMINI",
        name="Царь Гемини",
        master=TSAR_LEGACY_GEMINI,
        pool="EQAQdBFfSkFbXWB_3jYaREV7aqGXj1S09NX3E03sOkZaUaKz",
        decimals=9,
        description="Серия Гемини, 10B supply.",
        emoji="♊️",
        is_primary=False,
    ),
    "CROWN": TokenMeta(
        code="CROWN",
        symbol="ЦАРЬ-👑",
        name="Царь с коронкой",
        master=TSAR_LEGACY_CROWN,
        pool="EQDGUZi_NjzljeAtIXzSQ5eku9YeamABuRftyKN7HC-6Rk_K",
        decimals=9,
        description="Серия Царь с коронкой, 1B supply.",
        emoji="👑",
        is_primary=False,
    ),
}

DEFAULT_TOKEN = "BAAL_RA"


def get_token(code: str | None = None) -> TokenMeta:
    if not code:
        return TOKENS[DEFAULT_TOKEN]
    code = code.upper()
    if code not in TOKENS:
        return TOKENS[DEFAULT_TOKEN]
    return TOKENS[code]


def list_tokens() -> list[TokenMeta]:
    return list(TOKENS.values())