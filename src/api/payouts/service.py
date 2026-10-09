"""PayoutService — 3 царя × {СБП, карта МИР/Visa/MC, зарубежная карта}.

Банки СБП: Tochka, Tinkoff, Sberbank, VTB, Alfa, PSB, Raiffeisen, Gazprombank, Robomarket.
Банки CARD: Tochka, Tinkoff, Sberbank, VTB, Alfa, PSB, Raiffeisen, Gazprombank.
"""
from __future__ import annotations
import logging
import re
import uuid
from typing import Optional

from .config import (
    MIN_PAYOUT_TSAR, SERVICE_FEE_PCT, SBP_FEE_PCT,
    KYC_THRESHOLD_RUB, USD_RUB_FALLBACK,
)
from .models import Payout, PayoutMethod, PayoutStatus, PayoutResult
from .price_feed import PriceFeed
from .p2p import P2PClient, P2PError
from .sbp import SbpClient, SbpConfig, CardTransferClient
from .ton_payout import TonPayout

logger = logging.getLogger(__name__)

PHONE_RE = re.compile(r"^\+7\d{10}$")
CARD_RU_RE = re.compile(r"^\d{16}$")
CARD_FOREIGN_RE = re.compile(r"^\d{13,19}$")
IBAN_RE = re.compile(r"^[A-Z]{2}\d{2}[A-Z0-9]{1,30}$")


def detect_recipient_kind(recipient: str) -> PayoutMethod:
    r = recipient.strip().replace(" ", "").replace("-", "")
    if PHONE_RE.match(r):
        return PayoutMethod.SBP
    if CARD_RU_RE.match(r):
        return PayoutMethod.CARD_RU
    if IBAN_RE.match(r):
        return PayoutMethod.CARD_FOREIGN
    if CARD_FOREIGN_RE.match(r):
        return PayoutMethod.CARD_FOREIGN
    raise ValueError(
        f"Неверный формат получателя: {recipient[:6]}... "
        f"(ожидается +7XXXXXXXXXX, 16 цифр карты или IBAN)"
    )


class PayoutService:
    def __init__(
        self, *, p2p_client: P2PClient, price_feed: PriceFeed,
        sbp_client: Optional[SbpClient] = None,
        card_client: Optional[CardTransferClient] = None,
        ton_payout: Optional[TonPayout] = None,
    ):
        self.p2p = p2p_client
        self.price = price_feed
        self.sbp = sbp_client
        self.card = card_client
        self.ton = ton_payout

    async def quote(self, tsar_amount: float) -> PayoutResult:
        if tsar_amount < MIN_PAYOUT_TSAR:
            return self._err(tsar_amount, "", 0, f"мин. {MIN_PAYOUT_TSAR:,.0f} ЦАРЬ")
        stages: list[str] = []
        try:
            price_usdt = await self.price.get_price_usdt()
            stages.append(f"price.usdt={price_usdt:.8f}")
        except Exception as e:
            return self._err(tsar_amount, "", 0, f"Курс недоступен: {e}", stages=stages)
        try:
            usd_rub = await self.price.get_usd_rub()
            stages.append(f"usd.rub={usd_rub:.2f}")
        except Exception:
            usd_rub = USD_RUB_FALLBACK
            stages.append(f"usd.rub.fallback={usd_rub:.2f}")

        rate = price_usdt * usd_rub
        best_ad = None
        try:
            best_ad = await self.p2p.best_buy_ad(fiat="RUB")
            if best_ad:
                if price_usdt > 0:
                    p2p_rate = best_ad.price / price_usdt
                    if p2p_rate < rate:
                        rate = p2p_rate
                stages.append(f"p2p.best:{best_ad.nickname}@{best_ad.price:.2f}")
        except P2PError as e:
            stages.append(f"p2p.unavailable:{e}")

        gross = tsar_amount * rate
        service_fee = gross * SERVICE_FEE_PCT / 100
        sbp_fee = gross * SBP_FEE_PCT / 100
        net = gross - service_fee - sbp_fee
        stages += [f"rate={rate:.4f}", f"gross={gross:.2f}", f"net={net:.2f}"]

        status = PayoutStatus.KYC_REQUIRED if net > KYC_THRESHOLD_RUB else PayoutStatus.CREATED
        payout = self._mk(0, tsar_amount, "", PayoutMethod.SBP, net, rate, status)
        ad_d = best_ad.__dict__ if best_ad else None
        return PayoutResult(ok=True, payout=payout, stages=stages, p2p_ad=ad_d)

    async def execute(
        self, *, user_id: int, tsar_amount: float, recipient: str,
        method: Optional[PayoutMethod] = None,
    ) -> PayoutResult:
        if method is None:
            try:
                method = detect_recipient_kind(recipient)
            except ValueError as e:
                return self._err(tsar_amount, recipient, 0, str(e))

        stages: list[str] = []
        q = await self.quote(tsar_amount)
        if not q.ok:
            return PayoutResult(ok=False, payout=q.payout, error=q.error, stages=stages)
        stages.extend(q.stages)
        stages.append("quote.ok")

        try:
            self._validate(recipient, method)
        except ValueError as e:
            return PayoutResult(
                ok=False,
                payout=self._mk(user_id, tsar_amount, recipient, method, 0, q.payout.rate, PayoutStatus.FAILED),
                error=str(e), stages=stages,
            )

        best_ad = q.p2p_ad
        if not best_ad:
            try:
                best_ad_raw = await self.p2p.best_buy_ad(fiat="RUB")
                best_ad = best_ad_raw.__dict__ if best_ad_raw else None
            except P2PError as e:
                return PayoutResult(
                    ok=False,
                    payout=self._mk(user_id, tsar_amount, recipient, method, 0, q.payout.rate, PayoutStatus.FAILED),
                    error=f"P2P недоступен: {e}", stages=stages + ["p2p.error"],
                )
        stages.append(f"p2p.ok:{best_ad.get('nickname','?')}@{best_ad.get('price',0):.2f}")

        if self.ton:
            try:
                tx = await self.ton.send_tsar(amount=tsar_amount)
                stages.append(f"ton.ok:{tx[:10]}")
            except Exception as e:
                return PayoutResult(
                    ok=False,
                    payout=self._mk(user_id, tsar_amount, recipient, method, 0, q.payout.rate, PayoutStatus.FAILED),
                    error=f"TON: {e}", stages=stages + ["ton.error"],
                )

        if self.p2p.is_configured:
            try:
                await self.p2p.create_order(
                    ad_id=best_ad.get("id", ""),
                    usdt_amount=q.payout.amount_tzar, fiat="RUB",
                )
                stages.append("p2p.order.ok")
            except P2PError as e:
                stages.append(f"p2p.order.warn:{e}")
        else:
            stages.append("p2p.mock")

        external_id = None
        final_status = PayoutStatus.PROCESSING

        if method == PayoutMethod.SBP and self.sbp:
            try:
                res = await self.sbp.payout(
                    amount_rub=q.payout.amount_rub, phone=recipient,
                    idempotency_key=str(q.payout.id),
                )
                external_id = res.external_id
                final_status = PayoutStatus.SENT if res.status == "sent" else PayoutStatus.PROCESSING
                stages.append(f"sbp.ok:{res.provider}:{external_id[:18]}")
            except Exception as e:
                return PayoutResult(
                    ok=False,
                    payout=self._mk(user_id, tsar_amount, recipient, method, q.payout.amount_rub, q.payout.rate, PayoutStatus.FAILED),
                    error=f"СБП: {e}", stages=stages + ["sbp.error"],
                )
        elif method in (PayoutMethod.CARD_RU, PayoutMethod.CARD_FOREIGN) and self.card:
            try:
                res = await self.card.transfer(
                    amount_rub=q.payout.amount_rub, card=recipient,
                    idempotency_key=str(q.payout.id),
                )
                external_id = res.external_id
                final_status = PayoutStatus.SENT if res.status == "sent" else PayoutStatus.PROCESSING
                stages.append(f"card.ok:{res.provider}:{external_id[:18]}")
            except Exception as e:
                return PayoutResult(
                    ok=False,
                    payout=self._mk(user_id, tsar_amount, recipient, method, q.payout.amount_rub, q.payout.rate, PayoutStatus.FAILED),
                    error=f"Карта: {e}", stages=stages + ["card.error"],
                )
        else:
            if method == PayoutMethod.SBP:
                external_id = f"sbp_mock_{recipient[-4:]}_{int(q.payout.amount_rub*100)}"
                stages.append(f"sbp.mock:{external_id[:18]}")
            else:
                external_id = f"card_mock_{recipient[-4:]}_{int(q.payout.amount_rub*100)}"
                stages.append(f"card.mock:{external_id[:18]}")
            final_status = PayoutStatus.SENT

        payout = self._mk(
            user_id, tsar_amount, recipient, method,
            q.payout.amount_rub, q.payout.rate, final_status, external_id,
        )
        ad_d = best_ad if isinstance(best_ad, dict) else (best_ad.__dict__ if best_ad else None)
        return PayoutResult(ok=True, payout=payout, stages=stages, p2p_ad=ad_d)

    @staticmethod
    def _validate(recipient: str, method: PayoutMethod):
        if method == PayoutMethod.SBP:
            if not PayoutService._norm_phone(recipient):
                raise ValueError("Нужен телефон +7XXXXXXXXXX")
        elif method == PayoutMethod.CARD_RU:
            d = recipient.strip().replace(" ", "")
            if not (d.isdigit() and len(d) == 16):
                raise ValueError("Нужна карта: 16 цифр (МИР/Visa/MC)")
        elif method == PayoutMethod.CARD_FOREIGN:
            d = recipient.strip().replace(" ", "")
            if d.isdigit() and 13 <= len(d) <= 19:
                pass
            elif re.match(r"^[A-Z]{2}\d{2}[A-Z0-9]{1,30}$", d):
                pass
            else:
                raise ValueError("Нужна карта: 13-19 цифр или IBAN")

    @staticmethod
    def _norm_phone(phone: str) -> Optional[str]:
        p = phone.strip().replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
        if p.startswith("+7") and len(p) == 12 and p[2:].isdigit():
            return p
        if p.startswith("8") and len(p) == 11 and p[1:].isdigit():
            return "+7" + p[1:]
        if p.startswith("7") and len(p) == 11 and p[1:].isdigit():
            return "+" + p
        return None

    def _err(self, tsar_amount, recipient, amount_rub, error, stages=None):
        return PayoutResult(
            ok=False,
            payout=self._mk(0, tsar_amount, recipient, PayoutMethod.SBP, amount_rub, 0, PayoutStatus.FAILED),
            error=error, stages=stages or [],
        )

    def _mk(self, user_id, tsar_amount, recipient, method, amount_rub, rate, status, external_id=None):
        return Payout(
            id=str(uuid.uuid4()), user_id=user_id,
            amount_rub=amount_rub, amount_tzar=tsar_amount, rate=rate,
            method=method, recipient=recipient, status=status, external_id=external_id,
        )
