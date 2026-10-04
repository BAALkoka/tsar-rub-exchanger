from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from typing import Optional

from .config import TSAR_PRIMARY_POOL  # noqa: F401
from .models import Payout, PayoutMethod, PayoutStatus
from .price_feed import PriceFeed, PriceQuote
from .sbp import SbpClient, SbpError

logger = logging.getLogger(__name__)


@dataclass
class PayoutResult:
    ok: bool
    payout: Payout
    error: Optional[str] = None


class PayoutService:
    LIMIT_SMALL = 5_000
    LIMIT_MIDDLE = 50_000
    MIN_TSAR = 250_000

    def __init__(self, sbp_client: SbpClient, price_feed: PriceFeed):
        self.sbp = sbp_client
        self.prices = price_feed

    async def quote(self, tsar_amount: float) -> PriceQuote:
        return await self.prices.quote(tsar_amount)

    async def payout(
        self,
        tsar_amount: float,
        card_number: str,
        method: PayoutMethod = PayoutMethod.SBP,
    ) -> PayoutResult:
        try:
            quote = await self.quote(tsar_amount)
            if not quote.ok:
                return PayoutResult(
                    ok=False,
                    payout=Payout(
                        amount=tsar_amount,
                        card_number=card_number,
                        method=method,
                        status=PayoutStatus.FAILED,
                    ),
                    error=quote.error,
                )
            rub_amount = quote.rub_amount
            if rub_amount < self.LIMIT_SMALL:
                return PayoutResult(
                    ok=False,
                    payout=Payout(
                        amount=tsar_amount,
                        card_number=card_number,
                        method=method,
                        status=PayoutStatus.FAILED,
                    ),
                    error=f"Минимальная сумма вывода {self.LIMIT_SMALL} ₽",
                )
            payout_id = f"tsar-{uuid.uuid4().hex[:12]}"
            payout = Payout(
                id=payout_id,
                amount=tsar_amount,
                rub_amount=rub_amount,
                card_number=card_number,
                method=method,
                status=PayoutStatus.PENDING,
            )
            try:
                sbp_result = await self.sbp.transfer(
                    amount_rub=rub_amount,
                    card_number=card_number,
                    payout_id=payout_id,
                )
                if sbp_result.ok:
                    payout.status = PayoutStatus.SUCCESS
                    return PayoutResult(ok=True, payout=payout)
                else:
                    payout.status = PayoutStatus.FAILED
                    return PayoutResult(ok=False, payout=payout, error=sbp_result.error)
            except SbpError as e:
                payout.status = PayoutStatus.FAILED
                return PayoutResult(ok=False, payout=payout, error=str(e))
        except Exception as e:
            logger.exception("payout failed")
            return PayoutResult(
                ok=False,
                payout=Payout(
                    amount=tsar_amount,
                    card_number=card_number,
                    method=method,
                    status=PayoutStatus.FAILED,
                ),
                error=str(e),
            )