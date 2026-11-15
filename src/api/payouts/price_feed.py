"""PriceFeed: ЦАРЬ→USDT (GeckoTerminal + DeDust) + USDT→RUB (ЦБ РФ / CoinGecko)."""

from __future__ import annotations

import logging

import httpx

from .config import TSAR_MASTER, TSAR_USDT_POOL, USD_RUB_FALLBACK

logger = logging.getLogger(__name__)


class PriceFeed:
    """Курс ЦАРЬ→USDT и USDT→RUB.

    Источник цены токена — GeckoTerminal: пул DeDust ЦАРЬ/USDT почти пуст
    (reserve ~$0.02), поэтому отношение reserves там даёт неверную цену.
    DeDust остаётся резервным источником и используется только для пулов
    с реальной ликвидностью.
    """

    def __init__(
        self,
        *,
        token_master: str = TSAR_MASTER,
        token_pool: str = TSAR_USDT_POOL,
        pool_label: str = "USDT",
        manual_rate: float = 0.0,
        fallback_price: float = 0.000058,
        network: str = "ton",
        min_liquidity_usd: float = 50.0,
    ):
        self.token_master = token_master
        self.token_pool = token_pool
        self.pool_label = pool_label
        self.manual_rate = float(manual_rate) if manual_rate else 0.0
        self.fallback_price = float(fallback_price) if fallback_price else 0.000058
        self.network = network
        self.min_liquidity_usd = float(min_liquidity_usd)
        self._client: httpx.AsyncClient | None = None

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

    @staticmethod
    def _find_pool(payload: object, pool_address: str) -> dict | None:
        """Найти пул по адресу в ответе DeDust.

        ВАЖНО: /v2/pools?address=... игнорирует фильтр address и отдаёт
        все пулы сети (десятки тысяч). Поэтому ищем вручную.
        """
        pools: list = []
        if isinstance(payload, list):
            pools = payload
        elif isinstance(payload, dict):
            data = payload.get("data")
            if isinstance(data, list):
                pools = data
            elif isinstance(data, dict):
                pools = [data]
            else:
                pools = [payload]
        for pool in pools:
            if isinstance(pool, dict) and pool.get("address") == pool_address:
                return pool
        return None

    @staticmethod
    def _pool_decimals(pool: dict) -> tuple[float, float]:
        """Резервы пула в человеческих единицах (с учётом decimals)."""
        assets = pool.get("assets") or []
        reserves = pool.get("reserves") or []
        a_dec = int((assets[0].get("metadata") or {}).get("decimals", 9))
        b_dec = int((assets[1].get("metadata") or {}).get("decimals", 9))
        a = float(reserves[0]) / (10 ** a_dec)
        b = float(reserves[1]) / (10 ** b_dec)
        return a, b

    def _pool_is_liquid(self, pool: dict) -> bool:
        """Пул считается ликвидным, если в нём достаточно обеих сторон.

        У пула ЦАРЬ/USDT на DeDust всего ~$0.02 в резерве — такое отношение
        reserves нельзя использовать как цену.
        """
        try:
            quote, base = self._pool_decimals(pool)
        except (TypeError, ValueError, IndexError):
            return False
        return quote >= self.min_liquidity_usd and base >= 1000

    @staticmethod
    def _pool_price_usdt(pool: dict) -> float | None:
        """Цена 1 токена в quote-валюте по резервам пула.

        assets[0] — quote (USDT), assets[1] — base (токен).
        """
        try:
            quote, base = PriceFeed._pool_decimals(pool)
        except (TypeError, ValueError, IndexError):
            return None
        if quote <= 0 or base <= 0:
            return None
        return quote / base

    async def _price_from_geckoterminal(self) -> float | None:
        """Цена токена в USDT по GeckoTerminal (основной источник)."""
        r = await self._http()
        res = await r.get(
            f"https://api.geckoterminal.com/api/v2/networks/{self.network}"
            f"/pools/{self.token_pool}",
        )
        if res.status_code != 200:
            return None
        attrs = (res.json().get("data") or {}).get("attributes") or {}
        # В пуле USDT/ЦАРЬ base=USDT, quote=ЦАРЬ, поэтому цена нашего токена —
        # quote_token_price_usd.
        for key in ("quote_token_price_usd", "base_token_price_usd"):
            raw = attrs.get(key)
            if raw is None:
                continue
            try:
                px = float(raw)
            except (TypeError, ValueError):
                continue
            if px > 0:
                return px
        return None

    async def get_price_usdt(self) -> float:
        """Цена 1 ЦАРЬ в USDT.

        Порядок источников: manual_rate → GeckoTerminal → DeDust (ликвидный).
        """
        if self.manual_rate > 0:
            return self.manual_rate

        try:
            px = await self._price_from_geckoterminal()
            if px and px > 0:
                return px
        except Exception as e:
            logger.warning("GeckoTerminal: %s", e)

        try:
            r = await self._http()
            res = await r.get(
                "https://api.dedust.io/v2/pools",
                params={"address": self.token_pool, "resolve": "true"},
            )
            if res.status_code == 200:
                pool = self._find_pool(res.json(), self.token_pool)
                if pool:
                    if self._pool_is_liquid(pool):
                        price = self._pool_price_usdt(pool)
                        if price and price > 0:
                            return price
                    else:
                        logger.info(
                            "DeDust: pool %s has too low liquidity, skipped",
                            self.token_pool,
                        )
                else:
                    logger.warning("DeDust: pool %s not found", self.token_pool)
        except Exception as e:
            logger.warning("DeDust: %s", e)

        return self.fallback_price

    async def get_usd_rub(self) -> float:
        """Курс USDT→RUB: ЦБ РФ, затем CoinGecko, затем fallback."""
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
