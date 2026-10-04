"""Smoke-тесты для SBP-клиента.

Запуск: pytest src/api/payouts/tests
"""
import pytest

from src.api.payouts.sbp import SbpClient, SbpConfig, SbpError


@pytest.mark.asyncio
async def test_sbp_payout_ok():
    client = SbpClient(SbpConfig(merchant_id="test", api_key="x"))
    ext = await client.payout(amount_rub=1000.0, phone="+79991234567", idempotency_key="k1")
    assert ext.startswith("sbp_mock_")


@pytest.mark.asyncio
async def test_sbp_idempotency():
    client = SbpClient(SbpConfig(merchant_id="test", api_key="x"))
    e1 = await client.payout(amount_rub=1000.0, phone="+79991234567", idempotency_key="k2")
    e2 = await client.payout(amount_rub=1000.0, phone="+79991234567", idempotency_key="k2")
    assert e1 == e2