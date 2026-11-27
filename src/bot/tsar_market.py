"""Рынок ЦАРЯ: цена, ликвидность, изменение за 24ч и ссылки на покупку.

Источник — DexScreener API (все сети: TON, BSC). Для каждого токена серии
ЦАРЬ ищем реальные DEX-пары, берём самую ликвидную и отдаём:
  - цену в USD,
  - ликвидность пула в USD,
  - изменение цены за 24ч,
  - прямую ссылку на DEX для покупки.

Если пар нет — токен помечается как «рынка нет», без выдуманных цифр.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

log = logging.getLogger(__name__)

DEXSCREENER_TOKENS_URL = "https://api.dexscreener.com/latest/dex/tokens/{address}"
DEXSCREENER_SEARCH_URL = "https://api.dexscreener.com/latest/dex/search"


@dataclass
class MarketPair:
    """Одна реальная DEX-пара по токену ЦАРЯ."""

    dex: str
    chain: str
    pair_address: str
    base_symbol: str
    quote_symbol: str
    price_usd: float
    liquidity_usd: float
    change_24h: float | None
    url: str
    volume_24h: float = 0.0


@dataclass
class TokenMarket:
    """Сводка по одному токену серии ЦАРЬ."""

    slug: str
    symbol: str
    network: str
    best: MarketPair | None = None
    pairs_found: int = 0


def _f(v, default: float = 0.0) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def _pair_from_raw(p: dict) -> MarketPair | None:
    try:
        liq = _f((p.get("liquidity") or {}).get("usd"))
        price = _f(p.get("priceUsd"))
        if liq <= 0 and price <= 0:
            return None
        chg = (p.get("priceChange") or {}).get("h24")
        return MarketPair(
            dex=str(p.get("dexId") or "?"),
            chain=str(p.get("chainId") or "?"),
            pair_address=str(p.get("pairAddress") or ""),
            base_symbol=str((p.get("baseToken") or {}).get("symbol") or "?"),
            quote_symbol=str((p.get("quoteToken") or {}).get("symbol") or "?"),
            price_usd=price,
            liquidity_usd=liq,
            change_24h=_f(chg) if chg is not None else None,
            url=str(p.get("url") or ""),
            volume_24h=_f((p.get("volume") or {}).get("h24")),
        )
    except Exception as e:
        log.debug("pair parse failed: %s", e)
        return None


async def fetch_pairs(address: str) -> list[MarketPair]:
    """Все пары токена по DexScreener, отсортированные по ликвидности."""
    import httpx

    out: list[MarketPair] = []
    try:
        async with httpx.AsyncClient(
            timeout=10.0,
            headers={"User-Agent": "tsar-bot/1.0", "accept": "application/json"},
        ) as c:
            r = await c.get(DEXSCREENER_TOKENS_URL.format(address=address))
            if r.status_code != 200:
                return []
            data = r.json()
    except Exception as e:
        log.debug("dexscreener %s: %s", address, e)
        return []

    for p in data.get("pairs") or []:
        mp = _pair_from_raw(p)
        if mp is not None:
            out.append(mp)
    out.sort(key=lambda x: x.liquidity_usd, reverse=True)
    return out


async def market_for(token) -> TokenMarket:
    """Рынок для одного токена серии ЦАРЬ (TokenMeta)."""
    pairs = await fetch_pairs(token.master)
    return TokenMarket(
        slug=token.slug,
        symbol=token.symbol,
        network=token.network,
        best=pairs[0] if pairs else None,
        pairs_found=len(pairs),
    )


def format_market(m: TokenMarket) -> str:
    """Строка для Telegram: цена, ликвидность, 24ч, ссылка."""
    if m.best is None:
        return (
            f"{m.symbol} ({m.network.upper()}) — \U0001F6AB рынка нет "
            f"(нет DEX-пар с достаточной ликвидностью)"
        )
    b = m.best
    parts = [
        f"{m.symbol} ({m.network.upper()}) — <b>${b.price_usd:.10g}</b>",
        f"ликвидность <b>${b.liquidity_usd:,.0f}</b>",
    ]
    if b.change_24h is not None:
        sign = "+" if b.change_24h >= 0 else ""
        parts.append(f"24ч <b>{sign}{b.change_24h:.2f}%</b>")
    parts.append(f"DEX {b.dex} · пара {b.base_symbol}/{b.quote_symbol}")
    return " · ".join(parts)
