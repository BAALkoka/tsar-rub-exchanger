"""P2P-выплата через WalletBot P2P Market API.

Цепочка выплат:
    ЦАРЬ -> USDT (DEX/DeDust) -> P2P-объявление (покупатель USDT) -> RUB на карту

API возвращает список объявлений. Для выплаты мы выбираем объявление SIDE=BUY
(трейдер хочет КУПИТЬ USDT за RUB) с лучшим курсом и переводим USDT в
направлении трейдера; трейдер переводит RUB на карту получателя.
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Optional

import httpx

logger = logging.getLogger(__name__)


P2P_API_URL = os.getenv("P2P_API_URL", "https://p2p.walletbot.me")
P2P_API_KEY = os.getenv("P2P_API_KEY", "")
P2P_PATH = "/p2p/integration-api/v1/item/online"


class P2PError(Exception):
    """Базовое исключение P2P."""


class P2PNoAds(P2PError):
    """Нет подходящих объявлений."""


@dataclass
class P2PAd:
    """Объявление P2P-трейдера (он покупает USDT за RUB)."""

    id: str
    number: str
    user_id: int
    nickname: str
    price: float          # RUB за 1 USDT
    available_usdt: float
    min_amount_rub: float
    max_amount_rub: Optional[float]
    payments: list[str]
    execute_rate: float
    is_online: bool
    merchant_level: str
    payment_period_min: int
    is_auto_accept: bool

    def accepts_card(self) -> bool:
        """Проверяет, принимает ли трейдер карты (sber/tinkoff/alfabank/...)."""
        card_codes = {"sberbank", "tinkoff", "alfabank", "raiffeisen", "vtb", "rshb"}
        return any(p.lower() in card_codes for p in self.payments)


class P2PClient:
    """Клиент WalletBot P2P Market API.

    Источник: https://p2p.walletbot.me/p2p/integration-api/v1/item/online
    Авторизация: X-API-Key header.
    """

    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None, timeout_sec: float = 10.0):
        self.api_key = api_key or P2P_API_KEY
        self.base_url = (base_url or P2P_API_URL).rstrip("/")
        self.timeout = timeout_sec
        if not self.api_key:
            logger.warning("P2P_API_KEY не задан; P2P будет недоступен")

    def _headers(self) -> dict:
        return {
            "X-API-Key": self.api_key,
            "Content-Type": "application/json",
            "accept": "application/json",
        }

    async def get_buy_ads(
        self,
        crypto: str = "USDT",
        fiat: str = "RUB",
        side: str = "BUY",           # нам нужны BUY (трейдеры, которые КУПЯТ USDT)
        page: int = 1,
        page_size: int = 20,
    ) -> list[P2PAd]:
        """Получить список активных объявлений.

        side='BUY' -> объявления трейдеров, которые ХОТЯТ КУПИТЬ USDT за RUB
        (т.е. продавцы RUB, покупатели USDT). Идеально для нашей выплаты.
        """
        url = f"{self.base_url}{P2P_PATH}"
        body = {
            "cryptoCurrency": crypto,
            "fiatCurrency": fiat,
            "side": side,
            "page": page,
            "pageSize": page_size,
        }
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                r = await client.post(url, headers=self._headers(), json=body)
        except httpx.HTTPError as e:
            raise P2PError(f"P2P network error: {e}") from e

        if r.status_code == 401:
            raise P2PError("P2P: invalid API key (401)")
        if r.status_code == 403:
            raise P2PError("P2P: access denied (403)")
        if r.status_code == 429:
            raise P2PError("P2P: rate limit reached (429)")
        if r.status_code != 200:
            raise P2PError(f"P2P: HTTP {r.status_code}: {r.text[:200]}")

        try:
            data = r.json()
        except Exception as e:
            raise P2PError(f"P2P: invalid JSON: {e}") from e

        if data.get("status") != "SUCCESS":
            raise P2PError(f"P2P: status={data.get('status')}")

        ads = []
        for item in data.get("data", []):
            try:
                ads.append(P2PAd(
                    id=str(item["id"]),
                    number=str(item["number"]),
                    user_id=int(item["userId"]),
                    nickname=str(item["nickname"]),
                    price=float(item["price"]),
                    available_usdt=float(item["lastQuantity"]),
                    min_amount_rub=float(item["minAmount"]),
                    max_amount_rub=(float(item["maxAmount"]) if item.get("maxAmount") else None),
                    payments=list(item.get("payments", [])),
                    execute_rate=float(item.get("executeRate", "0")),
                    is_online=bool(item.get("isOnline", False)),
                    merchant_level=str(item.get("merchantLevel", "REGULAR_USER")),
                    payment_period_min=int(item.get("paymentPeriod", 15)),
                    is_auto_accept=bool(item.get("isAutoAccept", False)),
                ))
            except (KeyError, ValueError) as e:
                logger.warning("P2P: skip bad ad: %s", e)
        return ads

    async def best_buy_ad(self, usdt_amount: float, fiat: str = "RUB", require_card: bool = True) -> P2PAd:
        """Лучшее объявление для продажи USDT (side=BUY).

        Критерии:
          - доступно USDT >= нам нужно
          - online
          - merchant_level in {MERCHANT, TRUSTED_MERCHANT}
          - (опц.) принимает карты
          - лучший курс (price ниже -> для нас хуже, нам нужно ПРОДАТЬ USDT;
            трейдер покупает по своему price, поэтому для нас выгоден БОЛЕЕ
            ВЫСОКИЙ price).
        """
        ads = await self.get_buy_ads(crypto="USDT", fiat=fiat, side="BUY")
        if not ads:
            raise P2PNoAds("P2P: нет объявлений BUY по USDT/RUB")

        candidates = [a for a in ads if a.is_online and a.available_usdt >= usdt_amount]
        if require_card:
            candidates = [a for a in candidates if a.accepts_card()]
        candidates = [a for a in candidates if a.merchant_level in ("MERCHANT", "TRUSTED_MERCHANT")]

        if not candidates:
            # fallback: разрешаем любые онлайн-объявления
            candidates = [a for a in ads if a.is_online and a.available_usdt >= usdt_amount]

        if not candidates:
            raise P2PNoAds(
                f"P2P: нет подходящих объявлений (нужно {usdt_amount} USDT, "
                f"доступно {sum(a.available_usdt for a in ads):.2f})"
            )

        # Лучший = наивысшая цена RUB/USDT (нам платят больше)
        return max(candidates, key=lambda a: a.price)

    async def quote_rub_per_usdt(self) -> float:
        """Возвращает средний курс RUB/USDT по онлайн-объявлениям BUY."""
        ads = await self.get_buy_ads(crypto="USDT", fiat="RUB", side="BUY", page_size=10)
        if not ads:
            raise P2PNoAds("P2P: нет объявлений")
        online = [a for a in ads if a.is_online]
        sample = online if online else ads
        return sum(a.price for a in sample) / len(sample)