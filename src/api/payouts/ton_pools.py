"""Утилита для поиска DEX-пула ЦАРЬ/ТОН по TON-адресу кошелька.

Использует бесплатные публичные API:
  - TON API (tonapi.io) — для просмотра jetton-транзакций
  - DeDust API — для поиска пулов
"""
from __future__ import annotations

import asyncio
import logging
import os
from typing import Optional

import httpx

logger = logging.getLogger(__name__)


class TonPoolFinder:
    """Поисковик DEX-пула для токенов серии ЦАРЬ."""

    TONAPI = "https://tonapi.io/v2"
    DEDUST = "https://api.dedust.io/v2"

    def __init__(self, wallet_address: str, *, tonapi_token: Optional[str] = None):
        self.wallet = wallet_address
        self.tonapi_token = tonapi_token or os.environ.get("TONAPI_TOKEN")
        self._client = httpx.AsyncClient(timeout=10.0)

    async def close(self) -> None:
        await self._client.aclose()

    async def get_jettons(self) -> list[dict]:
        """Список jetton-контрактов, связанных с кошельком."""
        headers = {"Authorization": f"Bearer {self.tonapi_token}"} if self.tonapi_token else {}
        url = f"{self.TONAPI}/accounts/{self.wallet}/jettons"
        r = await self._client.get(url, headers=headers)
        r.raise_for_status()
        return r.json().get("jettons", [])

    async def find_dedust_pool(self, jetton_address: str) -> Optional[dict]:
        """Ищет пул ЦАРЬ-жетон/TON на DeDust."""
        r = await self._client.get(f"{self.DEDUST}/pools")
        r.raise_for_status()
        for pool in r.json():
            assets = pool.get("assets", [])
            asset_addrs = [a.get("address") for a in assets]
            if jetton_address in asset_addrs:
                symbols = [a.get("symbol", "").upper() for a in assets]
                if "TON" in symbols or "SCALE" in symbols:
                    return pool
        return None

    async def run(self) -> dict:
        """Полный сценарий: жетоны → пулы."""
        jettons = await self.get_jettons()
        tsar_jettons = [
            j for j in jettons
            if "ЦАРЬ" in (j.get("metadata", {}).get("name", "") or "").upper()
            or "TSAR" in (j.get("metadata", {}).get("symbol", "") or "").upper()
        ]

        pools = []
        for j in tsar_jettons:
            pool = await self.find_dedust_pool(j["address"])
            if pool:
                pools.append({
                    "jetton": j.get("metadata", {}).get("name"),
                    "jetton_address": j["address"],
                    "pool_address": pool.get("address"),
                })
        return {
            "wallet": self.wallet,
            "tsar_jettons_count": len(tsar_jettons),
            "pools": pools,
        }


if __name__ == "__main__":
    import json
    import sys

    addr = sys.argv[1] if len(sys.argv) > 1 else "EQAQdBFfSkFbXWB_3jYaREV7aqGXj1S09NX3E03sOkZaUaKz"
    finder = TonPoolFinder(addr)
    try:
        result = asyncio.run(finder.run())
        print(json.dumps(result, indent=2, ensure_ascii=False))
    finally:
        asyncio.run(finder.close())