"""P2P Market client (WalletBot) + fallback на публичный список.

Использует:
  1. WalletBot P2P Market (если задан P2P_API_KEY через секрет GitHub Actions)
  2. Если ключа нет — возвращает ok=False с понятной ошибкой,
     и бот показывает заглушечные объявления из конфига.
"""
from __future__ import annotations

import logging
import os
import asyncio
from dataclasses import dataclass, field
from typing import Optional

import httpx

from .config import (
    P2P_API_KEY,
    P2P_API_URL,
    P2P_PATH,
    USD_RUB_FALLBACK,
)

logger = logging.getLogger(__name__)


class P2PError(Exception):
    pass


class P2PNoAds(P2PError):
    """Нет объявлений, удовлетворяющих фильтру."""
    pass


@dataclass
class P2PAd:
    id: str
    nickname: str
    price: float                # ₽/USDT
    available_usdt: float
    min_amount_rub: float
    max_amount_rub: float
    payments: list[str] = field(default_factory=list)
    merchant_level: str = ""
    is_online: bool = True


class P2PClient:
    """Клиент WalletBot P2P Market. Если API_KEY пустой — возвращает []."""

    def __init__(self, *, timeout_sec: float = 10.0, api_key: Optional[str] = None):
        self.base_url = P2P_API_URL.rstrip("/")
        self.path = P2P_PATH
        self.api_key = (api_key if api_key is not None else P2P_API_KEY or "").strip() or None
        self.timeout = timeout_sec
        self._client = httpx.AsyncClient(
            timeout=timeout_sec,
            headers={"accept": "application/json"},
        )

    async def close(self) -> None:
        await self._client.aclose()

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key)

    async def get_buy_ads(
        self,
        *,
        crypto: str = "USDT",
        fiat: str = "RUB",
        side: str = "BUY",
        page_size: int = 10,
    ) -> list[P2PAd]:
        """Получает активные объявления: где трейдеры ПОКУПАЮТ USDT за RUB.

        side=BUY  — значит мы ХОТИМ ПРОДАТЬ USDT (трейдер покупает у нас).
        Для выплаты RUB через P2P нам нужно найти трейдеров, которые
        покупают USDT (side=BUY в их терминах).
        """
        if not self.api_key:
            logger.info("P2P API key not configured; returning mock ads")
            return self._mock_ads()

        url = f"{self.base_url}{self.path}"
        params = {
            "crypto": crypto,
            "fiat": fiat,
            "side": side,
            "pageSize": page_size,
            "lang": "ru",
        }
        headers = {"X-API-Key": self.api_key}
        try:
            r = await self._client.get(url, params=params, headers=headers)
            if r.status_code == 401:
                raise P2PError("P2P API key invalid (401)")
            if r.status_code == 429:
                raise P2PError("P2P rate limit (429)")
            if r.status_code != 200:
                raise P2PError(f"P2P HTTP {r.status_code}: {r.text[:200]}")
            data = r.json()
        except httpx.HTTPError as e:
            raise P2PError(f"P2P network error: {e}") from e

        ads_raw = data.get("items") or data.get("data") or data.get("ads") or []
        ads: list[P2PAd] = []
        for a in ads_raw:
            try:
                ads.append(P2PAd(
                    id=str(a.get("id") or a.get("adId") or ""),
                    nickname=str(a.get("nickname") or a.get("merchantName") or "unknown"),
                    price=float(a.get("price") or a.get("unitPrice") or 0),
                    available_usdt=float(a.get("available") or a.get("availableAmount") or 0),
                    min_amount_rub=float(a.get("minAmount") or a.get("min") or 0),
                    max_amount_rub=float(a.get("maxAmount") or a.get("max") or 0),
                    payments=list(a.get("payments") or a.get("paymentMethods") or []),
                    merchant_level=str(a.get("merchantLevel") or a.get("level") or ""),
                    is_online=bool(a.get("isOnline", True)),
                ))
            except (TypeError, ValueError) as e:
                logger.warning("skip bad P2P ad: %s | %s", a, e)
        return ads

    def _mock_ads(self) -> list[P2PAd]:
        """Заглушки когда P2P_API_KEY не задан."""
        return [
            P2PAd(
                id="mock-1",
                nickname="P2P_Trader_Demo",
                price=USD_RUB_FALLBACK,
                available_usdt=10_000,
                min_amount_rub=2_000,
                max_amount_rub=500_000,
                payments=["Tinkoff", "Sberbank", "СБП"],
                merchant_level="Gold",
                is_online=True,
            ),
            P2PAd(
                id="mock-2",
                nickname="TradeHub_RU",
                price=USD_RUB_FALLBACK + 0.3,
                available_usdt=25_000,
                min_amount_rub=5_000,
                max_amount_rub=1_000_000,
                payments=["СБП", "Альфа", "ВТБ"],
                merchant_level="Diamond",
                is_online=True,
            ),
        ]

    async def best_buy_ad(self, *, fiat: str = "RUB") -> Optional[P2PAd]:
        """Возвращает лучшее объявление (минимальная цена ₽/USDT)."""
        ads = await self.get_buy_ads(fiat=fiat, side="BUY")
        if not ads:
            return None
        return min(ads, key=lambda a: a.price)