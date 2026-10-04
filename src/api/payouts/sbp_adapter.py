"""Адаптер: бизнес-логика payouts → реальная выплата через Тинькофф."""
from __future__ import annotations
import logging
import os
import sys
from typing import Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from integrations.sbp.tinkoff import TinkoffSBPClient, PayoutResult

logger = logging.getLogger(__name__)


class SBPBridge:
    def __init__(self, tinkoff: Optional[TinkoffSBPClient] = None):
        self.tinkoff = tinkoff

    async def payout_rub(self, *, amount_rub, recipient, order_id, description="ЦАРЬ → RUB") -> PayoutResult:
        if self.tinkoff is None:
            return PayoutResult(success=False, status="queued_manual", error="sbp_not_configured")

        amount_kop = int(round(amount_rub * 100))
        cleaned = recipient.replace(" ", "").replace("-", "")
        if cleaned.startswith("+"):
            payment_type = "SBP"
        elif cleaned.startswith(("4", "5", "6")) and len(cleaned) == 16:
            payment_type = "Card"
        else:
            payment_type = "SBP"

        return await self.tinkoff.create_payout(
            amount_kopecks=amount_kop,
            recipient=cleaned,
            description=description,
            order_id=order_id,
            payment_type=payment_type,
        )