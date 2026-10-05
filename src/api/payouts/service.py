"""Сервис выплат ЦАРЬ → USDT → P2P → RUB на карту.

Использует PriceFeed (уже сконфигурированный под конкретный DeDust-пул)
и P2PClient (mock или реальный WalletBot).
"""
from __future__ import annotations
import asyncio
import logging
import uuid
from dataclasses import dataclass
from typing import Optional

from .config import USD_RUB_FALLBACK
from .models import Payout, PayoutMethod, PayoutStatus
from .p2p import P2PClient, P2PAd, P2PError
from .price_feed import PriceFeed, PriceQuote

logger = logging.getLogger(__name__)


@dataclass
class PayoutResult:
    ok: bool
    payout: Payout
    p2p_ad: Optional[P2PAd] = None
    error: Optional[str] = None


class PayoutService:
    def __init__(self, *, p2p_client: P2PClient, price_feed: PriceFeed,
                 service_fee_pct: float = 0.25):
        self.p2p = p2p_client
        self.feed = price_feed
        self.fee_pct = service_fee_pct

    async def payout(
        self,
        *,
        user_id: int,
        tsar_amount: float,
        recipient: str,
        method: PayoutMethod,
    ) -> PayoutResult:
        try:
            quote = await self.feed.quote(tsar_amount)
        except Exception as e:
            return PayoutResult(
                ok=False,
                payout=Payout(
                    id=str(uuid.uuid4()),
                    user_id=user_id,
                    amount_rub=0,
                    amount_tzar=tsar_amount,
                    rate=0,
                    method=method,
                    recipient=recipient,
                    status=PayoutStatus.FAILED,
                ),
                error=f"price feed error: {e}",
            )
        if not quote.ok:
            return PayoutResult(
                ok=False,
                payout=Payout(
                    id=str(uuid.uuid4()),
                    user_id=user_id,
                    amount_rub=0,
                    amount_tzar=tsar_amount,
                    rate=0,
                    method=method,
                    recipient=recipient,
                    status=PayoutStatus.FAILED,
                ),
                error=f"price not available: {quote.error}",
            )

        try:
            best_ad = await self.p2p.best_buy_ad(fiat="RUB")
        except P2PError as e:
            return PayoutResult(
                ok=False,
                payout=Payout(
                    id=str(uuid.uuid4()),
                    user_id=user_id,
                    amount_rub=0,
                    amount_tzar=tsar_amount,
                    rate=quote.rate,
                    method=method,
                    recipient=recipient,
                    status=PayoutStatus.FAILED,
                ),
                error=f"p2p error: {e}",
            )

        # расчёт суммы RUB
        if best_ad:
            price = best_ad.price          # ₽/USDT
            usd_amount = quote.usd_amount  # USD за N ЦАРЬ
            gross_rub = usd_amount * price
            fee_rub = gross_rub * self.fee_pct / 100
            net_rub = gross_rub - fee_rub
        else:
            price = quote.rate_used
            usd_amount = quote.usd_amount
            gross_rub = quote.rub_amount
            fee_rub = gross_rub * self.fee_pct / 100
            net_rub = gross_rub - fee_rub

        payout = Payout(
            id=str(uuid.uuid4()),
            user_id=user_id,
            amount_rub=net_rub,
            amount_tzar=tsar_amount,
            rate=quote.rate,
            p2p_price=price,
            method=method,
            recipient=recipient,
            status=PayoutStatus.PENDING,
        )

        return PayoutResult(ok=True, payout=payout, p2p_ad=best_ad)