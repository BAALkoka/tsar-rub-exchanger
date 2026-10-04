"""Сервис выплат через P2P Market.

Цепочка:
  1. ЦАРЬ -> USDT (DeDust DEX)
  2. USDT -> RUB через P2P-объявление (трейдер покупает USDT)
  3. Трейдер переводит RUB на карту получателя
"""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from typing import Optional

from .config import TSAR_PRIMARY_POOL, P2P_API_KEY  # noqa: F401
from .models import Payout, PayoutMethod, PayoutStatus
from .price_feed import PriceFeed, PriceQuote
from .p2p import P2PClient, P2PAd, P2PError, P2PNoAds

logger = logging.getLogger(__name__)


@dataclass
class PayoutResult:
    ok: bool
    payout: Payout
    p2p_ad: Optional[P2PAd] = None
    error: Optional[str] = None


class PayoutService:
    LIMIT_SMALL = 5_000
    LIMIT_MIDDLE = 50_000
    MIN_TSAR = 250_000

    def __init__(self, p2p_client: P2PClient, price_feed: PriceFeed):
        self.p2p = p2p_client
        self.prices = price_feed

    async def quote(self, tsar_amount: float) -> PriceQuote:
        return await self.prices.quote(tsar_amount)

    async def find_payout_partner(self, usdt_amount: float) -> P2PAd:
        """Ищет P2P-объявление, готовое выкупить USDT за RUB."""
        return await self.p2p.best_buy_ad(usdt_amount=usdt_amount, fiat="RUB", require_card=True)

    async def payout(
        self,
        user_id: int,
        tsar_amount: float,
        recipient: str,
        method: PayoutMethod = PayoutMethod.CARD_RU,
    ) -> PayoutResult:
        """Создаёт заявку на выплату.

        recipient: номер карты (16 цифр) для CARD_RU, телефон для SBP.
        Пока реализуем оформление заявки + поиск P2P-партнёра.
        Финальная USDT-передача выполняется оператором вручную (или через TON escrow).
        """
        try:
            quote = await self.quote(tsar_amount)
            if not quote.ok:
                payout = Payout(
                    id=str(uuid.uuid4()),
                    user_id=user_id,
                    amount_rub=0,
                    amount_tzar=tsar_amount,
                    rate=0,
                    method=method,
                    recipient=recipient,
                    status=PayoutStatus.FAILED,
                    error=quote.error,
                )
                return PayoutResult(ok=False, payout=payout, error=quote.error)

            rub_amount = quote.rub_amount
            if rub_amount < self.LIMIT_SMALL:
                err = f"Минимальная сумма вывода {self.LIMIT_SMALL} ₽"
                payout = Payout(
                    id=str(uuid.uuid4()),
                    user_id=user_id,
                    amount_rub=rub_amount,
                    amount_tzar=tsar_amount,
                    rate=quote.tsar_price_usd,
                    method=method,
                    recipient=recipient,
                    status=PayoutStatus.FAILED,
                    error=err,
                )
                return PayoutResult(ok=False, payout=payout, error=err)

            # USDT, которые нужно доставить до P2P-партнёра.
            # Курс RUB/USDT берём из P2P (средний), запас 1% на проскальзывание.
            try:
                rub_per_usdt = await self.p2p.quote_rub_per_usdt()
            except P2PError as e:
                logger.warning("P2P quote failed, fallback 100: %s", e)
                rub_per_usdt = 100.0
            usdt_amount = (rub_amount / rub_per_usdt) * 1.01

            # Ищем партнёра
            try:
                ad = await self.p2p.best_buy_ad(usdt_amount=usdt_amount, fiat="RUB", require_card=True)
            except P2PNoAds as e:
                payout = Payout(
                    id=str(uuid.uuid4()),
                    user_id=user_id,
                    amount_rub=rub_amount,
                    amount_tzar=tsar_amount,
                    rate=quote.tsar_price_usd,
                    method=method,
                    recipient=recipient,
                    status=PayoutStatus.FAILED,
                    error=str(e),
                )
                return PayoutResult(ok=False, payout=payout, error=str(e))

            payout = Payout(
                id=f"tsar-{uuid.uuid4().hex[:12]}",
                user_id=user_id,
                amount_rub=rub_amount,
                amount_tzar=tsar_amount,
                rate=quote.tsar_price_usd,
                method=method,
                recipient=recipient,
                status=PayoutStatus.PROCESSING,
            )
            logger.info(
                "payout created: id=%s usdt=%.2f partner=%s price=%.2f",
                payout.id, usdt_amount, ad.nickname, ad.price,
            )
            return PayoutResult(ok=True, payout=payout, p2p_ad=ad)
        except Exception as e:
            logger.exception("payout failed")
            payout = Payout(
                id=str(uuid.uuid4()),
                user_id=user_id,
                amount_rub=0,
                amount_tzar=tsar_amount,
                rate=0,
                method=method,
                recipient=recipient,
                status=PayoutStatus.FAILED,
                error=str(e),
            )
            return PayoutResult(ok=False, payout=payout, error=str(e))