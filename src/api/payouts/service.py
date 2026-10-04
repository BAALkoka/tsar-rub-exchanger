"""Сервис выплат: связывает Telegram-бот ↔ backend ↔ СБП/банк."""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from typing import Optional

from .config import TSAR_TON_POOL
from .models import Payout, PayoutMethod, PayoutStatus
from .price_feed import PriceFeed, PriceQuote
from .sbp import SbpClient, SbpConfig, SbpError

logger = logging.getLogger(__name__)


@dataclass
class PayoutResult:
    ok: bool
    payout: Payout
    error: Optional[str] = None


class PayoutService:
    """Оркестратор выплат."""

    # Пороги (₽) — синхронизированы с README/ROADMAP
    LIMIT_SMALL = 5_000
    LIMIT_MIDDLE = 50_000

    # Минимальная сумма ЦАРЬ для обмена (рынок тонкий)
    MIN_TSAR = 250_000

    def __init__(
        self,
        sbp_client: SbpClient,
        price_feed: PriceFeed,
    ):
        self.sbp = sbp_client
        self.prices = price_feed

    def scenario_for(self, amount_rub: float) -> str:
        if amount_rub <= self.LIMIT_SMALL:
            return "small"
        if amount_rub <= self.LIMIT_MIDDLE:
            return "middle"
        return "large"

    def is_amount_allowed(self, amount_tzar: float, rate: float) -> bool:
        """Гейт по минимальной сумме."""
        return amount_tzar >= self.MIN_TSAR

    async def quote(self, amount_tzar: float) -> PriceQuote:
        """Возвращает котировку перед созданием выплаты."""
        return await self.prices.get_rate()

    async def create(
        self,
        *,
        user_id: int,
        amount_tzar: float,
        method: PayoutMethod,
        recipient: str,
    ) -> PayoutResult:
        quote = await self.prices.get_rate()
        rate = quote.rate

        if not self.is_amount_allowed(amount_tzar, rate):
            return PayoutResult(
                ok=False,
                payout=Payout(
                    id=str(uuid.uuid4()),
                    user_id=user_id,
                    amount_rub=amount_tzar * rate,
                    amount_tzar=amount_tzar,
                    rate=rate,
                    method=method,
                    recipient=recipient,
                    status=PayoutStatus.FAILED,
                    error=f"Минимум {self.MIN_TSAR:,} ЦАРЬ (≈{self.MIN_TSAR * rate:.2f} ₽)".replace(",", " "),
                ),
            )

        amount_rub = amount_tzar * rate

        payout = Payout(
            id=str(uuid.uuid4()),
            user_id=user_id,
            amount_rub=amount_rub,
            amount_tzar=amount_tzar,
            rate=rate,
            method=method,
            recipient=recipient,
            status=PayoutStatus.CREATED,
        )

        scenario = self.scenario_for(amount_rub)
        if scenario in ("middle", "large") and not await self._has_kyc(user_id):
            payout.status = PayoutStatus.KYC_REQUIRED
            return PayoutResult(ok=False, payout=payout, error="kyc_required")

        try:
            external_id = await self.sbp.payout(
                amount_rub=amount_rub,
                phone=recipient,
                idempotency_key=payout.id,
            )
            payout.external_id = external_id
            payout.status = PayoutStatus.SENT
            return PayoutResult(ok=True, payout=payout)
        except SbpError as e:
            payout.status = PayoutStatus.FAILED
            payout.error = str(e)
            logger.exception("Payout failed id=%s", payout.id)
            return PayoutResult(ok=False, payout=payout, error=str(e))

    async def _has_kyc(self, user_id: int) -> bool:
        return False