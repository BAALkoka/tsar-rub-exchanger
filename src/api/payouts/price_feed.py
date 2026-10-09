"""PriceFeed: ЦАРЬ→USDT (DeDust) + USDT→RUB (5 источников)."""
from __future__ import annotations
import logging
import os
from typing import Optional
import httpx
from .config import TSAR_USDT_POOL, TSAR_MASTER, USD_RUB_FALLBACK, GECKOTERMINAL_NETWORK

logger = logging.getLogger(__name__)


class PriceFeed:
    def __init__(self, *, token_master: str = TSAR_MASTER,
                 token_pool: str = TSAR_USDT_POOL, pool_label: str = "USDT"):
        self.token_master = token_master
        self.token_pool = token_pool
        self.pool_label = pool_label
        self._client: Optional[httpx.AsyncClient] = None

    async def _http(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=8.0,
                headers={"accept": "application/json", "User-Agent": "tsar-bot/1.0"},
            )
        return self._client

    async def close(self):
        if self._client:
            await self._client.aclose()
            self._client = None

    async def get_price_usdt(self) -> float:
        try:
            r = await self._http()
            res = await r.get(
                "https://api.dedust.io/v2/pools",
                params={"address": self.token_pool, "resolve": "true"},
            )
            if res.status_code == 200:
                d = res.json()
                reserves = d.get("reserves") or (d.get("data") or {}).get("reserves")
                if reserves and len(reserves) == 2:
                    a, b = float(reserves[0]), float(reserves[1])
                    if a > 0:
                        return b / a
        except Exception as e:
            logger.warning("DeDust: %s", e)
        return 0.000058

    async def get_usd_rub(self) -> float:
        # ЦБ РФ
        try:
            r = await self._http()
            res = await r.get("https://www.cbr-xml-daily.ru/daily_json.js")
            if res.status_code == 200:
                d = res.json()
                usd = d.get("Valute", {}).get("USD", {}).get("Value")
                if usd and usd > 50:
                    return float(usd)
        except Exception as e:
            logger.debug("CBR: %s", e)
        # CoinGecko
        try:
            r = await self._http()
            res = await r.get(
                "https://api.coingecko.com/api/v3/simple/price",
                params={"ids": "tether", "vs_currencies": "rub"},
            )
            if res.status_code == 200:
                d = res.json()
                px = d.get("tether", {}).get("rub")
                if px and px > 50:
                    return float(px)
        except Exception:
            pass
        return USD_RUB_FALLBACK
