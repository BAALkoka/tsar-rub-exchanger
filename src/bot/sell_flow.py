"""Сценарий продажи ЦАРЬ → RUB: расчёт → TON-перевод → выплата на СБП/карту.

Модуль намеренно не зависит от aiogram: чистый async-код, который
легко тестировать и вызывать из хендлера.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from ..api.payouts.models import PayoutMethod, PayoutResult
from ..api.payouts.p2p import P2PError
from ..api.payouts.service import detect_recipient_kind, normalize_phone
from ..api.payouts.ton_payout import (
    TonPayout,
    TonPayoutError,
    normalize_slug,
    supported_slugs,
)

logger = logging.getLogger(__name__)


class SellFlowError(Exception):
    """Базовая ошибка сценария продажи."""


class SellInputError(SellFlowError):
    """Некорректный ввод от пользователя."""


class SellQuoteError(SellFlowError):
    """Не удалось получить котировку."""


class SellTransferError(SellFlowError):
    """TON-перевод ЦАРЬ не прошёл."""


@dataclass
class SellRequest:
    """Входные данные продажи."""

    user_id: int
    tsar_amount: float
    recipient: str
    slug: str = "BAAL_RA"
    method: PayoutMethod | None = None


@dataclass
class SellResult:
    """Итог сценария продажи."""

    ok: bool
    stages: list[str] = field(default_factory=list)
    quote: PayoutResult | None = None
    tx_hash: str = ""
    amount_rub: float = 0.0
    rate: float = 0.0
    recipient: str = ""
    method: PayoutMethod | None = None
    slug: str = "BAAL_RA"
    error: str | None = None

    def stage(self, name: str) -> None:
        self.stages.append(name)


class SellFlow:
    """Оркестратор продажи: расчёт → перевод → выплата."""

    def __init__(self, service: Any, ton: TonPayout) -> None:
        self.service = service
        self.ton = ton

    # --- helpers -------------------------------------------------

    @staticmethod
    def _detect_method(recipient: str) -> PayoutMethod:
        try:
            return detect_recipient_kind(recipient)
        except ValueError as e:
            raise SellInputError(str(e)) from e

    @staticmethod
    def _clean_recipient(recipient: str, method: PayoutMethod) -> str:
        """Нормализует получателя под выбранный метод."""
        r = (recipient or "").strip()
        if method == PayoutMethod.SBP:
            phone = normalize_phone(r)
            if not phone:
                raise SellInputError(
                    f"Неверный формат номера: {r[:6]}... (ожидается +7XXXXXXXXXX)"
                )
            return phone
        return r.replace(" ", "").replace("-", "")

    async def _transfer(self, *, amount: float, slug: str) -> str:
        """Делает TON-перевод ЦАРЬ, возвращает tx_hash."""
        try:
            tx = await self.ton.send_tsar(amount=amount, slug=slug)
        except TonPayoutError as e:
            raise SellTransferError(str(e)) from e
        except ValueError as e:
            raise SellInputError(str(e)) from e
        return tx.tx_hash

    # --- main ----------------------------------------------------

    async def run(self, req: SellRequest) -> SellResult:
        """Прогоняет сценарий продажи."""
        res = SellResult(ok=False, slug=req.slug)
        res.stage("start")

        if req.tsar_amount <= 0:
            res.error = "Сумма должна быть больше нуля"
            res.stage("input.invalid")
            return res

        try:
            slug = normalize_slug(req.slug)
        except TonPayoutError as e:
            res.error = str(e)
            res.stage("input.invalid")
            return res
        res.slug = slug
        res.stage("input.ok")

        try:
            method = req.method or self._detect_method(req.recipient)
            recipient = self._clean_recipient(req.recipient, method)
        except SellInputError as e:
            res.error = str(e)
            res.stage("recipient.invalid")
            return res
        res.method = method
        res.recipient = recipient
        res.stage("recipient.ok")

        # 1. Расчёт
        try:
            quote = await self.service.quote(req.tsar_amount)
        except (P2PError, ValueError, RuntimeError) as e:
            res.error = f"Не удалось рассчитать курс: {e}"
            res.stage("quote.failed")
            return res
        res.quote = quote
        if not quote.ok:
            res.error = quote.error or "Не удалось рассчитать курс"
            res.stage("quote.failed")
            return res
        res.rate = quote.payout.rate
        res.amount_rub = quote.payout.amount_rub
        res.stage("quote.ok")

        # 2. TON-перевод ЦАРЬ на кошелёк обменника
        try:
            tx_hash = await self._transfer(amount=req.tsar_amount, slug=slug)
        except SellFlowError as e:
            res.error = str(e)
            res.stage("transfer.failed")
            return res
        res.tx_hash = tx_hash
        res.stage("transfer.ok")

        # 3. Выплата на СБП/карту
        try:
            payout = await self.service.execute(
                user_id=req.user_id,
                tsar_amount=req.tsar_amount,
                recipient=recipient,
                method=method,
            )
        except (P2PError, ValueError, RuntimeError) as e:
            res.error = f"Ошибка выплаты: {e}"
            res.stage("payout.failed")
            return res
        res.quote = payout
        res.amount_rub = payout.payout.amount_rub
        res.rate = payout.payout.rate
        if not payout.ok:
            res.error = payout.error or "Выплата не прошла"
            res.stage("payout.failed")
            return res
        res.ok = True
        res.stage("payout.ok")
        return res

    # --- справочное ----------------------------------------------

    @staticmethod
    def supported_slugs() -> list[str]:
        return supported_slugs()

    @staticmethod
    def status_text(result: SellResult) -> str:
        """Короткий текст статуса для хендлера."""
        if result.ok:
            return (
                f"✅ Готово: {result.amount_rub:.2f} ₽ по курсу {result.rate:.4f}\n"
                f"tx: {result.tx_hash[:16]}…"
            )
        return f"❌ {result.error or 'не удалось'}"
