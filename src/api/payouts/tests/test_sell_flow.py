"""Тесты сценария продажи ЦАРЬ → RUB: расчёт → TON-перевод → выплата."""
from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from src.api.payouts.models import Payout, PayoutMethod, PayoutResult, PayoutStatus
from src.api.payouts.ton_payout import TonPayoutError
from src.bot.sell_flow import (
    SellFlow,
    SellInputError,
    SellRequest,
)


@dataclass
class FakeService:
    """Подмена PayoutService: без сети, детерминированные ответы."""

    quote_ok: bool = True
    execute_ok: bool = True
    quote_error: str = ""
    execute_error: str = ""
    quote_calls: list[float] = field(default_factory=list)
    execute_calls: list[dict] = field(default_factory=list)

    async def quote(self, tsar_amount: float) -> PayoutResult:
        self.quote_calls.append(tsar_amount)
        payout = Payout(
            id="q1",
            user_id=0,
            amount_rub=900.0,
            amount_tzar=tsar_amount,
            rate=90.0,
            recipient="",
        )
        if not self.quote_ok:
            return PayoutResult(ok=False, payout=payout, error=self.quote_error)
        return PayoutResult(ok=True, payout=payout)

    async def execute(self, *, user_id: int, tsar_amount: float, recipient: str,
                      method: PayoutMethod | None = None) -> PayoutResult:
        self.execute_calls.append({
            "user_id": user_id,
            "tsar_amount": tsar_amount,
            "recipient": recipient,
            "method": method,
        })
        payout = Payout(
            id="p1",
            user_id=user_id,
            amount_rub=900.0,
            amount_tzar=tsar_amount,
            rate=90.0,
            method=method or PayoutMethod.SBP,
            recipient=recipient,
            status=PayoutStatus.COMPLETED if self.execute_ok else PayoutStatus.FAILED,
        )
        if not self.execute_ok:
            return PayoutResult(ok=False, payout=payout, error=self.execute_error)
        return PayoutResult(ok=True, payout=payout)


class FakeTon:
    """Подмена TonPayout: mock-перевод или заранее заданная ошибка."""

    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.calls: list[dict] = []

    async def send_tsar(self, *, amount: float, slug: str = "BAAL_RA"):
        self.calls.append({"amount": amount, "slug": slug})
        if self.error:
            raise self.error
        from src.api.payouts.ton_payout import TonTx
        return TonTx(
            tx_hash="mock_abc123",
            src="EQsrc",
            dst="EQdst",
            jetton="EQjetton",
            amount=amount,
            amount_raw=int(amount * 10**9),
            source="mock",
            slug=slug,
            jetton_wallet="EQjw",
        )


# --- успешный сценарий ---------------------------------------

async def test_run_success_full_stages():
    svc, ton = FakeService(), FakeTon()
    flow = SellFlow(svc, ton)
    res = await flow.run(SellRequest(
        user_id=42, tsar_amount=1000.0, recipient="+79001234567", slug="BAAL_RA",
    ))
    assert res.ok is True
    assert res.error is None
    assert res.tx_hash == "mock_abc123"
    assert res.method == PayoutMethod.SBP
    assert res.recipient == "+79001234567"
    assert res.rate == 90.0
    assert res.amount_rub == 900.0
    for stage in ("input.ok", "recipient.ok", "quote.ok", "transfer.ok", "payout.ok"):
        assert stage in res.stages


async def test_run_normalizes_phone():
    svc, ton = FakeService(), FakeTon()
    flow = SellFlow(svc, ton)
    res = await flow.run(SellRequest(
        user_id=1, tsar_amount=10.0, recipient="8 900 123-45-67",
    ))
    assert res.ok is True
    assert res.recipient == "+79001234567"
    assert svc.execute_calls[0]["recipient"] == "+79001234567"


async def test_run_passes_slug_to_transfer():
    svc, ton = FakeService(), FakeTon()
    flow = SellFlow(svc, ton)
    res = await flow.run(SellRequest(
        user_id=1, tsar_amount=10.0, recipient="+79001234567", slug="CROWN",
    ))
    assert res.ok is True
    assert ton.calls[0]["slug"] == "CROWN"
    assert res.slug == "CROWN"


# --- ошибки ввода --------------------------------------------

async def test_run_rejects_zero_amount():
    flow = SellFlow(FakeService(), FakeTon())
    res = await flow.run(SellRequest(
        user_id=1, tsar_amount=0, recipient="+79001234567",
    ))
    assert res.ok is False
    assert "больше нуля" in (res.error or "")


async def test_run_rejects_bad_phone():
    flow = SellFlow(FakeService(), FakeTon())
    res = await flow.run(SellRequest(
        user_id=1, tsar_amount=10.0, recipient="нетелефон",
    ))
    assert res.ok is False
    assert res.error


async def test_run_rejects_unknown_slug():
    flow = SellFlow(FakeService(), FakeTon())
    res = await flow.run(SellRequest(
        user_id=1, tsar_amount=10.0, recipient="+79001234567", slug="НЕТ",
    ))
    assert res.ok is False
    assert "slug" in (res.error or "").lower() or res.error


# --- ошибки этапов --------------------------------------------

async def test_run_fails_when_quote_fails():
    svc = FakeService(quote_ok=False, quote_error="нет курса")
    flow = SellFlow(svc, FakeTon())
    res = await flow.run(SellRequest(
        user_id=1, tsar_amount=10.0, recipient="+79001234567",
    ))
    assert res.ok is False
    assert res.error == "нет курса"
    assert "quote.failed" in res.stages
    assert "transfer.ok" not in res.stages


async def test_run_fails_when_transfer_fails():
    ton = FakeTon(error=TonPayoutError("TON transfer failed"))
    flow = SellFlow(FakeService(), ton)
    res = await flow.run(SellRequest(
        user_id=1, tsar_amount=10.0, recipient="+79001234567",
    ))
    assert res.ok is False
    assert "TON transfer failed" in (res.error or "")
    assert "transfer.failed" in res.stages
    assert "payout.ok" not in res.stages


async def test_run_fails_when_payout_fails():
    svc = FakeService(execute_ok=False, execute_error="СБП недоступен")
    flow = SellFlow(svc, FakeTon())
    res = await flow.run(SellRequest(
        user_id=1, tsar_amount=10.0, recipient="+79001234567",
    ))
    assert res.ok is False
    assert res.error == "СБП недоступен"
    assert "payout.failed" in res.stages


# --- вспомогательное -----------------------------------------

def test_status_text_success():
    from src.bot.sell_flow import SellResult
    res = SellResult(ok=True, amount_rub=900.0, rate=90.0, tx_hash="mock_abc123")
    text = SellFlow.status_text(res)
    assert "Готово" in text
    assert "900.00" in text


def test_status_text_failure():
    from src.bot.sell_flow import SellResult
    res = SellResult(ok=False, error="бум")
    assert "бум" in SellFlow.status_text(res)


def test_clean_recipient_rejects_bad_phone():
    with pytest.raises(SellInputError):
        SellFlow._clean_recipient("нетелефон", PayoutMethod.SBP)
