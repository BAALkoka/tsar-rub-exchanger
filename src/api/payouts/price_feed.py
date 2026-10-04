"""Ценовой фид для обоих токенов серии ЦАРЬ.

Источники (по убыванию приоритета):
  1. CoinGecko Pro
  2. CoinGecko Free
  3. GeckoTerminal DEX (по пулу)
  4. Manual override
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
    TSAR_MASTER,
    TSAR_TON_POOL,
    TSAR2_MASTER,
    TSAR2_TON_POOL,
    USD_RUB_FALLBACK,
)

logger = logging.getLogger(__name__)


@dataclass
class PriceQuote:
    rate: float  # RUB за 1 токен
    source: str
    token_master: str
    fetched_at: float

    def is_fresh(self, max_age_sec: float = 60.0) -> bool:
        return time.time() - self.fetched_at < max_age_sec

    @property
    def age_sec(self) -> float:
        return time.time() - self.fetched_at


class PriceFeedError(Exception):
    """Все источники цен упали."""


class PriceFeed:
    CACHE_TTL = 60.0

    def __init__(
        self,
        *,
        coingecko_api_key: Optional[str] = None,
        manual_rate: Optional[float] = None,
        coingecko_token_id: Optional[str] = None,
        token_master: str = TSAR_MASTER,
        token_pool: Optional[str] = None,
        timeout_sec: float = 5.0,
    ):
        self.coingecko_api_key = coingecko_api_key or os.environ.get("COINGECKO_API_KEY")
        self.manual_rate = manual_rate
        self.coingecko_token_id = coingecko_token_id or os.environ.get("COINGECKO_TSAR_TOKEN_ID")
        self.token_master = token_master
        # По умолчанию выбираем пул под конкретный master
        self.token_pool = token_pool or (
            TSAR2_TON_POOL if token_master == TSAR2_MASTER else TSAR_TON_POOL
        )
        self.timeout = timeout_sec
        self._cache: Optional[PriceQuote] = None
        self._client = httpx.AsyncClient(timeout=timeout_sec)

    async def close(self) -> None:
        await self._client.aclose()

    async def get_rate(self) -> PriceQuote:
        if self._cache and self._cache.is_fresh(self.CACHE_TTL):
            return self._cache

        for source_fn in (
            self._from_coingecko_pro,
            self._from_coingecko_free,
            self._from_geckoterminal,
            self._from_manual,
        ):
            try:
                quote = await source_fn()
                if quote and quote.rate > 0:
                    self._cache = quote
                    return quote
            except Exception as e:
                logger.warning("PriceFeed: source %s failed: %s", source_fn.__name__, e)
        raise PriceFeedError("All price sources failed")

    async def _from_coingecko_pro(self) -> Optional[PriceQuote]:
        if not (self.coingecko_api_key and self.coingecko_token_id):
            return None
        url = (
            f"https://pro-api.coingecko.com/api/v3/simple/price"
            f"?ids={self.coingecko_token_id}&vs_currencies=rub"
        )
        r = await self._client.get(url, headers={"x-cg-pro-api-key": self.coingecko_api_key})
        r.raise_for_status()
        rate = float(r.json()[self.coingecko_token_id]["rub"])
        return self._make_quote(rate, "coingecko-pro")

    async def _from_coingecko_free(self) -> Optional[PriceQuote]:
        if not self.coingecko_token_id:
            return None
        url = (
            f"https://api.coingecko.com/api/v3/simple/price"
            f"?ids={self.coingecko_token_id}&vs_currencies=rub"
        )
        r = await self._client.get(url)
        r.raise_for_status()
        data = r.json()
        if self.coingecko_token_id not in data:
            return None
        rate = float(data[self.coingecko_token_id]["rub"])
        return self._make_quote(rate, "coingecko-free")

    async def _from_geckoterminal(self) -> Optional[PriceQuote]:
        if not self.token_pool:
            return None
        url = (
            f"https://api.geckoterminal.com/api/v2/networks/{GECKOTERMINAL_NETWORK}"
            f"/pools/{self.token_pool}"
        )
        r = await self._client.get(url)
        r.raise_for_status()
        data = r.json()
        attrs = data["data"]["attributes"]
        price_usd = float(attrs["base_token_price_usd"])
        usd_rub = await self._fetch_usd_rub()
        return self._make_quote(price_usd * usd_rub, "geckoterminal")

    async def _fetch_usd_rub(self) -> float:
        try:
            r = await self._client.get(
                "https://api.exchangerate-api.com/v4/latest/USD"
            )
            r.raise_for_status()
            return float(r.json()["rates"]["RUB"])
        except Exception:
            return USD_RUB_FALLBACK

    async def _from_manual(self) -> Optional[PriceQuote]:
        if self.manual_rate is None:
            return None
        return self._make_quote(self.manual_rate, "manual")

    def _make_quote(self, rate: float, source: str) -> PriceQuote:
        return PriceQuote(
            rate=rate,
            source=source,
            token_master=self.token_master,
            fetched_at=time.time(),
        )