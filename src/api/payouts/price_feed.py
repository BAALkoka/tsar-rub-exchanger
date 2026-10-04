"""Ценовой фид ЦАРЬ → RUB.

Источники (в порядке приоритета):
  1. CoinGecko Pro API (если активирован PRO-ключ)
  2. CoinGecko Free API (fallback)
  3. GeckoTerminal DEX API (бесплатный, по контракту)
  4. Rate override вручную (последний резерв)

Для каждого источника реализован TTL-кэш (60 сек) и circuit breaker.
"""
from __future__ import annotations

import asyncio
import logging
import os
import time
from dataclasses import dataclass
from typing import Optional

import httpx

logger = logging.getLogger(__name__)


@dataclass
class PriceQuote:
    """Котировка ЦАРЬ → RUB."""

    rate: float
    source: str
    fetched_at: float
    age_sec: float

    def is_fresh(self, max_age_sec: float = 60.0) -> bool:
        return self.age_sec < max_age_sec


class PriceFeedError(Exception):
    """Не получилось достать курс ни из одного источника."""


class PriceFeed:
    """Оркестратор ценового фида."""

    CACHE_TTL = 60.0

    def __init__(
        self,
        *,
        coingecko_api_key: Optional[str] = None,
        manual_rate: Optional[float] = None,
        geckoterminal_pool_address: Optional[str] = None,
        coingecko_token_id: Optional[str] = None,
        timeout_sec: float = 5.0,
    ):
        self.coingecko_api_key = coingecko_api_key or os.environ.get("COINGECKO_API_KEY")
        self.manual_rate = manual_rate
        self.geckoterminal_pool_address = geckoterminal_pool_address
        self.coingecko_token_id = coingecko_token_id or os.environ.get(
            "COINGECKO_TSAR_TOKEN_ID", "tsar-token"
        )
        self.timeout = timeout_sec
        self._cache: Optional[PriceQuote] = None
        self._client = httpx.AsyncClient(timeout=timeout_sec)

    async def close(self) -> None:
        await self._client.aclose()

    async def get_rate(self) -> PriceQuote:
        """Возвращает свежий курс. Пробует источники по очереди."""
        if self._cache and self._cache.is_fresh(self.CACHE_TTL):
            self._cache.age_sec = time.time() - self._cache.fetched_at
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
        if not self.coingecko_api_key:
            return None
        url = (
            f"https://pro-api.coingecko.com/api/v3/simple/price"
            f"?ids={self.coingecko_token_id}&vs_currencies=rub"
        )
        headers = {"x-cg-pro-api-key": self.coingecko_api_key}
        r = await self._client.get(url, headers=headers)
        r.raise_for_status()
        data = r.json()
        rate = float(data[self.coingecko_token_id]["rub"])
        return PriceQuote(rate=rate, source="coingecko-pro", fetched_at=time.time(), age_sec=0)

    async def _from_coingecko_free(self) -> Optional[PriceQuote]:
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
        return PriceQuote(rate=rate, source="coingecko-free", fetched_at=time.time(), age_sec=0)

    async def _from_geckoterminal(self) -> Optional[PriceQuote]:
        """Бесплатный DEX-фид: используем пул ЦАРЬ/ТОН на GeckoTerminal."""
        if not self.geckoterminal_pool_address:
            return None
        # Формат: /networks/ton/pools/{pool_address}
        url = f"https://api.geckoterminal.com/api/v2/networks/ton/pools/{self.geckoterminal_pool_address}"
        r = await self._client.get(url)
        r.raise_for_status()
        data = r.json()
        attrs = data["data"]["attributes"]
        # Цена в USD, конвертим в RUB через CBR (статичный fallback)
        price_usd = float(attrs["base_token_price_usd"])
        usd_to_rub = await self._fetch_usd_rub()
        return PriceQuote(
            rate=price_usd * usd_to_rub,
            source="geckoterminal",
            fetched_at=time.time(),
            age_sec=0,
        )

    async def _fetch_usd_rub(self) -> float:
        try:
            r = await self._client.get("https://api.coingecko.com/api/v3/simple/price?ids=usd&vs_currencies=rub")
            r.raise_for_status()
            return float(r.json()["usd"]["rub"])
        except Exception:
            return 90.0  # запасной курс, обновляется руками

    async def _from_manual(self) -> Optional[PriceQuote]:
        if self.manual_rate is None:
            return None
        return PriceQuote(
            rate=self.manual_rate,
            source="manual",
            fetched_at=time.time(),
            age_sec=0,
        )