"""Ценовой фид для токенов серии ЦАРЬ.

Источники (по убыванию приоритета):
  1. CoinGecko Pro  (требует COINGECKO_API_KEY)
  2. CoinGecko Free
  3. GeckoTerminal DeDust-пул (РЕАЛЬНЫЙ КУРС)
  4. Manual override

Поддержка двух типов пулов:
  - USDT-пул (BAAL_RA): base_token_price_usd есть сразу
  - TON-пул (BLIZNETSY/CROWN): нужно умножить base_token_price_native_currency на TON/USD

Все цены возвращаются в RUB за 1 ЦАРЬ.
"""
from __future__ import annotations

import asyncio
import logging
import os
import time
from dataclasses import dataclass
from typing import Optional

import httpx

from .config import (
    GECKOTERMINAL_NETWORK,
    TSAR_LEGACY_CROWN,
    TSAR_LEGACY_BLIZNETSY,
    TSAR_MASTER,
    TSAR_PRIMARY_POOL,
    USD_RUB_FALLBACK,
)

logger = logging.getLogger(__name__)


# Запасные пулы (наследие) — все три серии ликвидны в основных DeDust-пулах
_LEGACY_POOLS = {
    TSAR_LEGACY_BLIZNETSY: TSAR_PRIMARY_POOL,
    TSAR_LEGACY_CROWN: TSAR_PRIMARY_POOL,
}


@dataclass
class PriceQuote:
    rate: float            # RUB за 1 ЦАРЬ
    source: str
    token_master: str
    tsar_price_usd: float  # USD за 1 ЦАРЬ
    usd_amount: float
    rub_amount: float
    rate_used: float       # USD/RUB
    pool_label: str = ""
    ok: bool = True
    error: Optional[str] = None
    fetched_at: float = 0.0

    def is_fresh(self, max_age_sec: float = 60.0) -> bool:
        return time.time() - self.fetched_at < max_age_sec

    @property
    def age_sec(self) -> float:
        return time.time() - self.fetched_at


class PriceFeedError(Exception):
    pass


class PriceFeed:
    CACHE_TTL = 60.0
    GECKOTERMINAL_BASE = "https://api.geckoterminal.com/api/v2"
    COINGECKO_BASE = "https://api.coingecko.com/api/v3"

    def __init__(
        self,
        *,
        coingecko_api_key: Optional[str] = None,
        manual_rate: Optional[float] = None,
        coingecko_token_id: Optional[str] = None,
        token_master: str = TSAR_MASTER,
        token_pool: Optional[str] = None,
        pool_label: str = "",
        timeout_sec: float = 8.0,
    ):
        self.coingecko_api_key = (
            coingecko_api_key or os.environ.get("COINGECKO_API_KEY") or ""
        ).strip() or None
        self.manual_rate = manual_rate
        self.coingecko_token_id = (
            coingecko_token_id or os.environ.get("COINGECKO_TSAR_TOKEN_ID") or ""
        ).strip() or None
        self.token_master = token_master
        self.token_pool = token_pool or _LEGACY_POOLS.get(token_master, TSAR_PRIMARY_POOL)
        self.pool_label = pool_label
        self.timeout = timeout_sec
        self._cache: Optional[PriceQuote] = None
        self._cache_lock = asyncio.Lock()
        self._client = httpx.AsyncClient(
            timeout=timeout_sec,
            headers={"accept": "application/json", "User-Agent": "tsar-bot/1.0"},
        )

    async def close(self) -> None:
        await self._client.aclose()
