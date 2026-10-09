"""End-to-end тест 100₽ через mock-режим.

Запуск: pytest tests/test_e2e.py -v
или:   python tests/test_e2e.py
"""
import asyncio
import os
import sys
from pathlib import Path

# Корень проекта в sys.path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

# Mock-режим: всё фиктивно, без реальных переводов
os.environ.setdefault("MIN_PAYOUT_TSAR", "1")     # обходим лимит для теста
os.environ.setdefault("SERVICE_FEE_PCT", "0.25")
os.environ.setdefault("SBP_FEE_PCT", "0.40")
os.environ.setdefault("P2P_API_KEY", "")
os.environ.setdefault("SBP_PROVIDER", "mock")

import pytest
from api.payouts.price_feed import PriceFeed
from api.payouts.p2p import P2PClient
from api.payouts.service import PayoutService
from api.payouts.models import PayoutMethod


@pytest.fixture
def service():
    feed = PriceFeed(token_pool=None, pool_label="USDT")
    p2p = P2PClient()
    svc = PayoutService(p2p_client=p2p, price_feed=feed, sbp_client=None, ton_payout=None)
    yield svc
    asyncio.run(p2p.close())
    asyncio.run(feed.close())


@pytest.mark.asyncio
async def test_quote_100rub(service):
    """Квота на 1.2 ЦАРЬ должна дать ~100₽ нетто."""
    q = await service.quote(1.2)
    assert q.ok, f"quote failed: {q.error}"
    assert q.payout.rate > 0
    assert q.payout.amount_rub > 80
    assert q.payout.amount_rub < 200
    print(f"\n✅ quote: rate={q.payout.rate:.4f} ₽/ЦАРЬ, net={q.payout.amount_rub:.2f} ₽")


@pytest.mark.asyncio
async def test_execute_100rub_sbp(service):
    """Полный pipeline: ЦАРЬ→USDT→P2P→СБП→+7XXXXXXXXXX."""
    r = await service.execute(
        user_id=123456789,
        tsar_amount=1.2,
        recipient="+79001234567",
        method=PayoutMethod.SBP,
    )
    assert r.ok, f"execute failed: {r.error}"
    assert r.payout.status.value == "sent"
    assert r.payout.external_id
    assert r.payout.amount_rub > 80
    assert "p2p.ok" in " ".join(r.stages)
    assert "sbp.mock" in " ".join(r.stages) or "sbp.ok" in " ".join(r.stages)
    print(f"\n✅ execute: {r.payout.amount_rub:.2f}₽ → {r.payout.external_id}")
    print(f"   stages: {r.stages}")


@pytest.mark.asyncio
async def test_phone_normalization(service):
    """Телефоны 8, +7, 10 цифр должны нормализоваться в +7XXXXXXXXXX."""
    for raw, expected in [
        ("+79001234567", "+79001234567"),
        ("89001234567",  "+79001234567"),
        ("9001234567",   "+79001234567"),
    ]:
        n = service._normalize_phone(raw)
        assert n == expected, f"{raw} → {n} (expected {expected})"
    assert service._normalize_phone("123") is None
    assert service._normalize_phone("abc") is None
    print("\n✅ phone normalization works")


@pytest.mark.asyncio
async def test_min_payout_enforced():
    """MIN_PAYOUT_TSAR проверяется в quote() — должно падать на малой сумме."""
    import importlib
    from api.payouts import config, service
    importlib.reload(config)
    importlib.reload(service)
    feed = PriceFeed(token_pool=None, pool_label="USDT")
    p2p = P2PClient()
    svc = service.PayoutService(p2p_client=p2p, price_feed=feed)
    q = await svc.quote(1.0)
    assert not q.ok
    assert "минимум" in q.error or "250" in q.error
    print(f"\n✅ min_payout enforced: {q.error}")
    await p2p.close()
    await feed.close()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
