"""Сервис выплат ЦАРЬ → USDT → P2P → RUB → карта (СБП).

Pipeline:
  1. PriceFeed.quote(tsar_amount) — получить курс через DeDust-пул
  2. P2PClient.best_buy_ad() — найти лучшего покупателя USDT за RUB
  3. SbpClient.payout() — отправить RUB на карту получателя по СБП
  4. ton_payout.send_tsar() — сжечь/отправить ЦАРЬ с кошелька пользователя

Методы:
  - quote() — только расчёт (без побочных эффектов)
  - payout() — расчёт + создание заявки (PENDING)
  - execute() — реальная отправка через P2P + СБП
"""
from __future__ import annotations
import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from typing import Optional

from .config import USD_RUB_FALLBACK, MIN_PAYOUT_TSAR, SBP_FEE_PCT, SERVICE_FEE_PCT
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
    stages: list[str] = field(default_factory=list)


class PayoutService:
    def __init__(
        self,
        *,
        p2p_client: P2PClient,
        price_feed: PriceFeed,
        sbp_client=None,           # опционально (для теста 100₽ можно None)
        ton_payout=None,           # опционально (модуль отправки ЦАРЬ)
        service_fee_pct: float = SERVICE_FEE_PCT,
        sbp_fee_pct: float = SBP_FEE_PCT,
    ):
        self.p2p = p2p_client
        self.feed = price_feed
        self.sbp = sbp_client
        self.ton = ton_payout
        self.fee_pct = service_fee_pct
        self.sbp_fee_pct = sbp_fee_pct

    # ============= РАСЧЁТ (без побочных эффектов) =============

    async def quote(self, tsar_amount: float) -> PayoutResult:
        """Только квота: курс, USD, RUB gross/net."""
        if tsar_amount < MIN_PAYOUT_TSAR:
            return PayoutResult(
                ok=False,
                payout=Payout(
                    id="", user_id=0, amount_rub=0, amount_tzar=tsar_amount,
                    rate=0, method=PayoutMethod.SBP, recipient="",
                    status=PayoutStatus.FAILED,
                ),
                error=f"минимум {MIN_PAYOUT_TSAR:,.0f} ЦАРЬ",
            )

        # 1) Курс
        try:
            price_quote = await self.feed.quote(tsar_amount)
        except Exception as e:
            return self._fail(tsar_amount, 0, 0, f"price feed error: {e}")
        if not price_quote.ok:
            return self._fail(tsar_amount, 0, 0, f"price not available: {price_quote.error}", rate=0)

        # 2) Лучший P2P-покупатель USDT
        best_ad = None
        try:
            best_ad = await self.p2p.best_buy_ad(fiat="RUB")
        except P2PError as e:
            logger.warning("P2P best_buy_ad failed (mock fallback): %s", e)

        # 3) Расчёт суммы
        if best_ad:
            usdt_rub = best_ad.price      # ₽/USDT
            usd_amount = price_quote.usd_amount
            gross_rub = usd_amount * usdt_rub
        else:
            usdt_rub = price_quote.rate_used
            usd_amount = price_quote.usd_amount
            gross_rub = price_quote.rub_amount

        service_fee = gross_rub * self.fee_pct / 100
        sbp_fee = gross_rub * self.sbp_fee_pct / 100
        net_rub = gross_rub - service_fee - sbp_fee

        payout = Payout(
            id=str(uuid.uuid4()),
            user_id=0,
            amount_rub=round(net_rub, 2),
            amount_tzar=tsar_amount,
            rate=price_quote.rate,
            method=PayoutMethod.SBP,
            recipient="",
            status=PayoutStatus.CREATED,
        )
        return PayoutResult(
            ok=True,
            payout=payout,
            p2p_ad=best_ad,
            stages=["quote.ok", f"rate={price_quote.rate:.4f}", f"gross={gross_rub:.2f}", f"net={net_rub:.2f}"],
        )

    # ============= ИСПОЛНЕНИЕ (реальная отправка) =============

    async def execute(
        self,
        *,
        user_id: int,
        tsar_amount: float,
        recipient: str,            # телефон +7... или номер карты
        method: PayoutMethod = PayoutMethod.SBP,
    ) -> PayoutResult:
        """Полный цикл: расчёт → P2P-продажа USDT → СБП-перевод."""
        stages: list[str] = []

        # Stage 1: квота
        q = await self.quote(tsar_amount)
        if not q.ok:
            return PayoutResult(ok=False, payout=q.payout, error=q.error, stages=stages)
        stages.extend(q.stages)
        stages.append("quote.ok")

        # Определяем phone (для СБП) и card (для CARD_RU)
        phone = self._normalize_phone(recipient) if method == PayoutMethod.SBP else None
        if method == PayoutMethod.SBP and not phone:
            return PayoutResult(
                ok=False,
                payout=self._make_payout(user_id, tsar_amount, recipient, method, 0, q.payout.rate, PayoutStatus.FAILED),
                error="нужен номер телефона в формате +7XXXXXXXXXX",
                stages=stages,
            )

        # Stage 2: P2P — найти покупателя USDT
        best_ad = q.p2p_ad
        if not best_ad:
            try:
                best_ad = await self.p2p.best_buy_ad(fiat="RUB")
            except P2PError as e:
                return PayoutResult(
                    ok=False,
                    payout=self._make_payout(user_id, tsar_amount, recipient, method, 0, q.payout.rate, PayoutStatus.FAILED),
                    error=f"P2P недоступен: {e}",
                    stages=stages + ["p2p.error"],
                )
        stages.append(f"p2p.ok:{best_ad.nickname}@{best_ad.price:.2f}")

        # Stage 3: TON-перевод ЦАРЬ → кошелёк обменника
        if self.ton:
            try:
                tx_hash = await self.ton.send_tsar(amount=tsar_amount)
                stages.append(f"ton.ok:{tx_hash[:10]}")
            except Exception as e:
                return PayoutResult(
                    ok=False,
                    payout=self._make_payout(user_id, tsar_amount, recipient, method, 0, q.payout.rate, PayoutStatus.FAILED),
                    error=f"TON-перевод не прошёл: {e}",
                    stages=stages + ["ton.error"],
                )

        # Stage 4: USDT → RUB через P2P (в мок-режиме — фиксация, в реальном — вызов P2P API)
        if self.p2p.is_configured:
            try:
                await self.p2p.create_order(
                    ad_id=best_ad.id,
                    usdt_amount=q.payout.amount_tzar * 1.0,  # 1:1 USDT к ЦАРЬ (для MVP)
                    fiat="RUB",
                )
                stages.append("p2p.order.ok")
            except P2PError as e:
                return PayoutResult(
                    ok=False,
                    payout=self._make_payout(user_id, tsar_amount, recipient, method, 0, q.payout.rate, PayoutStatus.FAILED),
                    error=f"P2P-сделка не прошла: {e}",
                    stages=stages + ["p2p.order.error"],
                )
        else:
            stages.append("p2p.mock")

        # Stage 5: СБП-перевод RUB → карта
        external_id = None
        if self.sbp:
            try:
                external_id = await self.sbp.payout(
                    amount_rub=q.payout.amount_rub,
                    phone=phone or recipient,
                    idempotency_key=str(q.payout.id),
                )
                stages.append(f"sbp.ok:{external_id[:18]}")
            except Exception as e:
                return PayoutResult(
                    ok=False,
                    payout=self._make_payout(user_id, tsar_amount, recipient, method, q.payout.amount_rub, q.payout.rate, PayoutStatus.FAILED),
                    error=f"СБП не прошёл: {e}",
                    stages=stages + ["sbp.error"],
                )
        else:
            stages.append("sbp.mock")
            external_id = f"sbp_mock_{uuid.uuid4().hex[:12]}"

        # ✅ Успех
        payout = self._make_payout(
            user_id, tsar_amount, recipient, method,
            amount_rub=q.payout.amount_rub,
            rate=q.payout.rate,
            status=PayoutStatus.SENT,
        )
        payout.external_id = external_id
        return PayoutResult(ok=True, payout=payout, p2p_ad=best_ad, stages=stages)

    # ============= HELPERS =============

    def _make_payout(
        self, user_id, tsar_amount, recipient, method,
        amount_rub, rate, status,
    ) -> Payout:
        return Payout(
            id=str(uuid.uuid4()),
            user_id=user_id,
            amount_rub=amount_rub,
            amount_tzar=tsar_amount,
            rate=rate,
            method=method,
            recipient=recipient,
            status=status,
        )

    def _fail(self, tsar_amount, rate, amount_rub, error, rate_=0):
        return PayoutResult(
            ok=False,
            payout=self._make_payout(0, tsar_amount, "", PayoutMethod.SBP, amount_rub, rate_, PayoutStatus.FAILED),
            error=error,
        )

    @staticmethod
    def _normalize_phone(raw: str) -> Optional[str]:
        """Приводит телефон к +7XXXXXXXXXX. Возвращает None если не похоже на телефон."""
        digits = "".join(c for c in raw if c.isdigit())
        if len(digits) == 11 and digits.startswith("8"):
            digits = "7" + digits[1:]
        elif len(digits) == 10:
            digits = "7" + digits
        if len(digits) != 11 or not digits.startswith("7"):
            return None
        return "+" + digits
