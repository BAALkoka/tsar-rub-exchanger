"""Одноразовый снимок текущего курса ЦАРЬ.

Запуск: python -m src.api.payouts.tests.snapshot_price

Сохраняет в /tmp/tsar_price.json + печатает в stdout.
"""
import asyncio
import json
import time
from pathlib import Path

import httpx

from src.api.payouts.config import TSAR_TON_POOL, USD_RUB_FALLBACK


async def snapshot():
    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.get(f"https://api.geckoterminal.com/api/v2/networks/ton/pools/{TSAR_TON_POOL}")
        gt = r.json()
        attrs = gt["data"]["attributes"]

        # USD/RUB из бесплатного API
        r2 = await c.get("https://api.exchangerate-api.com/v4/latest/USD")
        rates = r2.json().get("rates", {})
        usd_rub = float(rates.get("RUB", USD_RUB_FALLBACK))

        # Цена ЦАРЬ в TON (base = ЦАРЬ, quote = TON по нашему пулу)
        # base_token_price_native_currency = price of base in native (TON)
        tsar_in_ton = float(attrs["base_token_price_native_currency"])
        tsar_in_usd = float(attrs["base_token_price_usd"])
        tsar_in_rub = tsar_in_usd * usd_rub

        result = {
            "fetched_at": time.time(),
            "pool": TSAR_TON_POOL,
            "tsar_in_ton": tsar_in_ton,
            "tsar_in_usd": tsar_in_usd,
            "tsar_in_rub": tsar_in_rub,
            "usd_rub": usd_rub,
            "fdv_usd": float(attrs.get("fdv_usd", 0)),
            "reserve_in_usd": float(attrs.get("reserve_in_usd", 0)),
            "volume_24h_usd": float((attrs.get("volume_usd") or {}).get("h24", 0)),
            "pool_created_at": attrs.get("pool_created_at"),
        }

        Path("/tmp").mkdir(exist_ok=True)
        Path("/tmp/tsar_price.json").write_text(json.dumps(result, indent=2))
        return result


if __name__ == "__main__":
    out = asyncio.run(snapshot())
    print(json.dumps(out, indent=2, ensure_ascii=False))