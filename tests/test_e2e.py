"""End-to-end тест полного цикла ЦАРЬ → RUB через mock-режим.

Запуск: pytest tests/test_e2e.py -v
"""
from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path

# Корень проекта в sys.path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

# Mock-режим: всё фиктивно, без реальных переводов.
os.environ.setdefault("MIN_PAYOUT_TSAR", "1")
os.environ.setdefault("SERVICE_FEE_PCT", "0.25")
os.environ.setdefault("SBP_FEE_PCT", "0.40")
os.environ.setdefault("P2P_FEE_PCT", "0.20")
os.environ.setdefault("P2P_API_KEY", "")
os.environ.setdefault("SBP_PROVIDER", "mock")
os.environ.setdefault("USD_RUB_FALLBACK", "90.0")

import pytest  # noqa: E402

from src.api.payouts.models import PayoutMethod  # noqa: E402
from src.api.payouts.p2p import P2PClient  # noqa: E402
from src.api.payouts.price_feed import PriceFeed  # noqa: E402
from src.api.payouts.sbp import CardTransferClient, SbpClient, SbpConfig  # noqa: E402
from src.api.payouts.service import PayoutService, detect_recipient_kind, normalize_phone  # noqa: E402

# Детерминированный курс: 0.1027881907 USDT за 1 ЦАРЬ × 90 ₽ = 9.2509 ₽/ЦАРЬ
TEST_PRICE_USDT = 0.1027881907
TEST_USD_RUB = 90.0
TSAR_AMOUNT = 12.0  # ~111 ₽ до комиссий


@pytest.fixture
def service():
    feed = PriceFeed(manual_rate=TEST_PRICE_USDT, fallback_price=TEST_PRICE_USDT)

    async def fixed_usd_rub() -> float:
        return TEST_USD_RUB

    feed.get_usd_rub = fixed_usd_rub
    p2p = P2PClient(api_key="")
    sbp = SbpClient(SbpConfig(provider="mock", merchant_id="test", api_key="test"))
    card = CardTransferClient(SbpConfig(provider="mock", merchant_id="test", api_key="test"))
    svc = PayoutService(
        p2p_client=p2p,
        price_feed=feed,
        sbp_client=sbp,
        card_client=card,
        ton_payout=None,
    )
    yield svc


@pytest.mark.asyncio
async def test_quote_100rub(service):
    """Квота на 12 ЦАРЬ должна дать около 100 ₽ нетто."""
    q = await service.quote(TSAR_AMOUNT)
    assert q.ok, f"quote failed: {q.error}"
    assert q.payout.rate > 0
    assert 80 < q.payout.amount_rub < 200
    print(f"\n✅ quote: rate={q.payout.rate:.4f} ₽/ЦАРЬ, net={q.payout.amount_rub:.2f} ₽")


@pytest.mark.asyncio
async def test_execute_100rub_sbp(service):
    """Полный pipeline: ЦАРЬ→USDT→P2P→СБП→+7XXXXXXXXXX."""
    r = await service.execute(
        user_id=123456789,
        tsar_amount=TSAR_AMOUNT,
        recipient="+79001234567",
        method=PayoutMethod.SBP,
    )
    assert r.ok, f"execute failed: {r.error}"
    assert r.payout.status.value == "sent"
    assert r.payout.external_id
    assert r.payout.amount_rub > 80
    stages = " ".join(r.stages)
    assert "p2p" in stages or "p2p.unavailable" in stages
    assert "sbp.mock" in stages or "sbp.ok" in stages
    print(f"\n✅ execute: {r.payout.amount_rub:.2f}₽ → {r.payout.external_id}")
    print(f"   stages: {r.stages}")


def test_phone_normalization():
    """Телефоны 8, +7, 10 цифр нормализуются в +7XXXXXXXXXX."""
    for raw, expected in [
        ("+79001234567", "+79001234567"),
        ("89001234567", "+79001234567"),
        ("9001234567", "+79001234567"),
        ("7 900 123 45 67", "+79001234567"),
    ]:
        n = normalize_phone(raw)
        assert n == expected, f"{raw} → {n} (expected {expected})"
    assert normalize_phone("123") is None
    assert normalize_phone("abc") is None
    print("\n✅ phone normalization works")


def test_detect_recipient_kind():
    """СБП для телефона, карта для 16 цифр, IBAN для зарубежной карты."""
    assert detect_recipient_kind("+79001234567") == PayoutMethod.SBP
    assert detect_recipient_kind("2200123456789012") == PayoutMethod.CARD_RU
    assert detect_recipient_kind("DE89370400440532013000") == PayoutMethod.CARD_FOREIGN
    print("\n✅ recipient kind detection works")


@pytest.mark.asyncio
async def test_min_payout_enforced():
    """MIN_PAYOUT_TSAR проверяется в quote() — на малой сумме должна быть ошибка."""
    import src.api.payouts.config as config
    import src.api.payouts.service as service_mod

    old = os.environ.get("MIN_PAYOUT_TSAR")
    os.environ["MIN_PAYOUT_TSAR"] = "250000"
    try:
        importlib.reload(config)
        importlib.reload(service_mod)
        feed = PriceFeed(manual_rate=TEST_PRICE_USDT, fallback_price=TEST_PRICE_USDT)

        async def fixed_usd_rub() -> float:
            return TEST_USD_RUB

        feed.get_usd_rub = fixed_usd_rub
        p2p = P2PClient(api_key="")
        svc = service_mod.PayoutService(p2p_client=p2p, price_feed=feed)
        q = await svc.quote(1.0)
        assert not q.ok
        assert "мин" in q.error or "250" in q.error
        print(f"\n✅ min_payout enforced: {q.error}")
    finally:
        if old is None:
            os.environ.pop("MIN_PAYOUT_TSAR", None)
        else:
            os.environ["MIN_PAYOUT_TSAR"] = old
        importlib.reload(config)
        importlib.reload(service_mod)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
