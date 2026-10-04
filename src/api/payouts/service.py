"""Сервис выплат: связывает Telegram-бот ↔ backend ↔ СБП/банк."""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from typing import Optional

from .models import Payout, PayoutMethod, PayoutStatus
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

    def __init__(self, sbp_client: SbpClient):
        self.sbp = sbp_client

    def scenario_for(self, amount_rub: float) -> str:
        if amount_rub <= self.LIMIT_SMALL:
            return "small"
        if amount_rub <= self.LIMIT_MIDDLE:
            return "middle"
        return "large"

    async def create(
        self,
        *,
        user_id: int,
        amount_rub: float,
        amount_tzar: float,
        rate: float,
        method: PayoutMethod,
        recipient: str,
    ) -> PayoutResult:
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

        # KYC-gate: для среднего и крупного нужна верификация
        scenario = self.scenario_for(amount_rub)
        if scenario in ("middle", "large") and not await self._has_kyc(user_id):
            payout.status = PayoutStatus.KYC_REQUIRED
            return PayoutResult(ok=False, payout=payout, error="kyc_required")

        # Отправляем через СБП
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
        """Заглушка: проверка, что пользователь прошёл KYC.

        В проде — запрос в KYC-провайдер (SumSub и т.д.).
        """
        return False