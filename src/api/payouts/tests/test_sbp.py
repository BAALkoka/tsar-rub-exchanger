"""Тесты СБП-клиента и перевода на карту.

Реальный API: SbpClient.payout(...) -> SbpResult (external_id, status, ...),
идемпотентность через idempotency_key.
"""
from __future__ import annotations

import pytest

from src.api.payouts.sbp import CardTransferClient, SbpClient, SbpConfig


@pytest.fixture
def sbp_client():
    return SbpClient(SbpConfig(provider="mock", merchant_id="test", api_key="test"))


@pytest.fixture
def card_client():
    return CardTransferClient(SbpConfig(provider="mock", merchant_id="test", api_key="test"))


@pytest.mark.asyncio
async def test_sbp_payout_ok(sbp_client):
    """Mock-провайдер отдаёт external_id и статус sent."""
    res = await sbp_client.payout(
        amount_rub=1000.0, phone="+79991234567", idempotency_key="k1"
    )
    assert res.external_id
    assert res.external_id.startswith("sbp_mock_")
    assert res.status == "sent"
    assert res.amount_rub == 1000.0
    assert res.phone == "+79991234567"


@pytest.mark.asyncio
async def test_sbp_idempotency(sbp_client):
    """Повтор с тем же idempotency_key не создаёт вторую выплату."""
    e1 = await sbp_client.payout(
        amount_rub=1000.0, phone="+79991234567", idempotency_key="k2"
    )
    e2 = await sbp_client.payout(
        amount_rub=1000.0, phone="+79991234567", idempotency_key="k2"
    )
    # Дубль возвращает ИСХОДНЫЙ external_id первой выплаты
    assert e1.external_id == e2.external_id
    assert e1.external_id.startswith("sbp_mock_")
    assert e2.status == "duplicate"


@pytest.mark.asyncio
async def test_sbp_not_live_in_mock_mode(sbp_client):
    """В mock-режиме клиент не считается боевым."""
    assert sbp_client.is_live() is False


@pytest.mark.asyncio
async def test_card_transfer_ok(card_client):
    """Перевод на карту в mock-режиме возвращает идентификатор."""
    res = await card_client.transfer(
        amount_rub=5000.0, card="4276380000000000", idempotency_key="c1"
    )
    assert res.external_id
    assert res.status == "sent"
    assert res.amount_rub == 5000.0
