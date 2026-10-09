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
        pool_label: str = "",   # 'USDT' или 'TON'
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

    async def quote(self, tsar_amount: float) -> PriceQuote:
        """Главный метод: возвращает полную квоту для tsar_amount ЦАРЬ."""
        try:
            base = await self.get_rate()
            if not base.ok:
                return PriceQuote(
                    rate=0, source=base.source, token_master=self.token_master,
                    tsar_price_usd=0, usd_amount=0, rub_amount=0, rate_used=0,
                    pool_label=self.pool_label,
                    ok=False, error=base.error,
                )
            usd_amount = tsar_amount * base.tsar_price_usd
            rub_amount = tsar_amount * base.rate
            return PriceQuote(
                rate=base.rate,
                source=base.source,
                token_master=self.token_master,
                tsar_price_usd=base.tsar_price_usd,
                usd_amount=usd_amount,
                rub_amount=rub_amount,
                rate_used=base.rate_used,
                pool_label=base.pool_label,
                ok=True,
                fetched_at=base.fetched_at,
            )
        except Exception as e:
            logger.exception("quote failed")
            return PriceQuote(
                rate=0, source="error", token_master=self.token_master,
                tsar_price_usd=0, usd_amount=0, rub_amount=0, rate_used=0,
                pool_label=self.pool_label,
                ok=False, error=str(e),
            )

    async def get_rate(self) -> PriceQuote:
        if self._cache and self._cache.is_fresh(self.CACHE_TTL) and self._cache.ok:
            return self._cache
        async with self._cache_lock:
            if self._cache and self._cache.is_fresh(self.CACHE_TTL) and self._cache.ok:
                return self._cache
            for source_fn in (
                self._from_coingecko_pro,
                self._from_coingecko_free,
                self._from_geckoterminal,
                self._from_manual,
            ):
                try:
                    quote = await source_fn()
                    if quote and quote.ok and quote.rate > 0:
                        self._cache = quote
                        return quote
                    if quote and not quote.ok:
                        logger.warning("source %s: %s", source_fn.__name__, quote.error)
                except Exception as e:
                    logger.warning("source %s raised: %s", source_fn.__name__, e)
            err = PriceQuote(
                rate=0, source="none", token_master=self.token_master,
                tsar_price_usd=0, usd_amount=0, rub_amount=0, rate_used=0,
                pool_label=self.pool_label,
                ok=False, error="All price sources failed", fetched_at=time.time(),
            )
            self._cache = err
            return err

    # === CoinGecko Pro ===
    async def _from_coingecko_pro(self) -> Optional[PriceQuote]:
        if not (self.coingecko_api_key and self.coingecko_token_id):
            return None
        url = (
            f"{self.COINGECKO_BASE}/simple/price"
            f"?ids={self.coingecko_token_id}&vs_currencies=usd,rub"
        )
        r = await self._client.get(url, headers={"x-cg-pro-api-key": self.coingecko_api_key})
        r.raise_for_status()
        data = r.json().get(self.coingecko_token_id)
        if not data or "rub" not in data:
            return None
        rub = float(data["rub"])
        usd = float(data.get("usd") or 0)
        return self._make_quote(rub, usd, "coingecko-pro")

    # === CoinGecko Free ===
    async def _from_coingecko_free(self) -> Optional[PriceQuote]:
        if not self.coingecko_token_id:
            return None
        url = (
            f"{self.COINGECKO_BASE}/simple/price"
            f"?ids={self.coingecko_token_id}&vs_currencies=usd,rub"
        )
        r = await self._client.get(url)
        r.raise_for_status()
        data = r.json().get(self.coingecko_token_id)
        if not data or "rub" not in data:
            return None
        rub = float(data["rub"])
        usd = float(data.get("usd") or 0)
        return self._make_quote(rub, usd, "coingecko-free")

    # === GeckoTerminal DeDust ===
    async def _from_geckoterminal(self) -> Optional[PriceQuote]:
        if not self.token_pool:
            return PriceQuote(
                rate=0, source="geckoterminal", token_master=self.token_master,
                tsar_price_usd=0, usd_amount=0, rub_amount=0, rate_used=0,
                pool_label=self.pool_label,
                ok=False, error="no token_pool configured",
            )
        url = (
            f"{self.GECKOTERMINAL_BASE}/networks/{GECKOTERMINAL_NETWORK}"
            f"/pools/{self.token_pool}"
        )
        r = await self._client.get(url)
        if r.status_code != 200:
            return PriceQuote(
                rate=0, source="geckoterminal", token_master=self.token_master,
                tsar_price_usd=0, usd_amount=0, rub_amount=0, rate_used=0,
                pool_label=self.pool_label,
                ok=False, error=f"GeckoTerminal HTTP {r.status_code}",
            )
        payload = r.json()
        attrs = (payload.get("data") or {}).get("attributes") or {}
        if not attrs:
            return PriceQuote(
                rate=0, source="geckoterminal", token_master=self.token_master,
                tsar_price_usd=0, usd_amount=0, rub_amount=0, rate_used=0,
                pool_label=self.pool_label,
                ok=False, error="GeckoTerminal: empty data",
            )

        # Цена базового токена (ЦАРЬ)
        price_usd = float(attrs.get("base_token_price_usd") or 0)
        price_native = float(attrs.get("base_token_price_native_currency") or 0)

        # Если USD-цена пустая или подозрительно маленькая — TON-пул с микроценой
        if price_usd <= 0 or price_usd < 1e-12:
            if price_native > 0:
                ton_usd = await self._fetch_ton_usd()
                price_usd = price_native * ton_usd
            else:
                return PriceQuote(
                    rate=0, source="geckoterminal", token_master=self.token_master,
                    tsar_price_usd=0, usd_amount=0, rub_amount=0, rate_used=0,
                    pool_label=self.pool_label,
                    ok=False, error="GeckoTerminal: no price fields",
                )

        usd_rub = await self._fetch_usd_rub()
        rub = price_usd * usd_rub
        return self._make_quote(rub, price_usd, "geckoterminal", usd_rub)

    async def _fetch_ton_usd(self) -> float:
        """TON/USD курс через CoinGecko."""
        try:
            r = await self._client.get(
                f"{self.COINGECKO_BASE}/simple/price?ids=the-open-network&vs_currencies=usd"
            )
            r.raise_for_status()
            return float(r.json().get("the-open-network", {}).get("usd") or 0)
        except Exception:
            return 0.0

    async def _fetch_usd_rub(self) -> float:
        try:
            r = await self._client.get("https://api.exchangerate-api.com/v4/latest/USD")
            r.raise_for_status()
            rate = float((r.json().get("rates") or {}).get("RUB") or 0)
            return rate if rate > 0 else USD_RUB_FALLBACK
        except Exception:
            return USD_RUB_FALLBACK

    # === Manual ===
    async def _from_manual(self) -> Optional[PriceQuote]:
        if self.manual_rate is None or self.manual_rate <= 0:
            return PriceQuote(
                rate=0, source="manual", token_master=self.token_master,
                tsar_price_usd=0, usd_amount=0, rub_amount=0, rate_used=0,
                pool_label=self.pool_label,
                ok=False, error="manual_rate not set",
            )
        usd_rub = await self._fetch_usd_rub()
        return self._make_quote(self.manual_rate, self.manual_rate / usd_rub, "manual", usd_rub)

    def _make_quote(
        self, rate_rub: float, tsar_price_usd: float,
        source: str, usd_rub: Optional[float] = None,
    ) -> PriceQuote:
        return PriceQuote(
            rate=rate_rub,
            source=source,
            token_master=self.token_master,
            tsar_price_usd=tsar_price_usd,
            usd_amount=0,
            rub_amount=0,
            rate_used=usd_rub if usd_rub is not None else USD_RUB_FALLBACK,
            pool_label=self.pool_label,
            ok=True,
            fetched_at=time.time(),
        )
