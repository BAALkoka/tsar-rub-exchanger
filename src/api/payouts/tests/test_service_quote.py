"""Тесты расчёта котировки и выплаты (quote / execute) под реальную логику.

Курс фиксирован: 1 ЦАРЬ = 0.1027881907 USDT, USD/RUB = 90.
Минимальная выплата — 1 ЦАРЬ (в окружении тестов MIN_PAYOUT_TSAR=1).
"""
from __future__ import annotations

import pytest

from src.api.payouts.config import SBP_FEE_PCT, SERVICE_FEE_PCT
from src.api.payouts.models import PayoutMethod, PayoutStatus

TEST_PRICE_USDT = 0.1027881907
TEST_USD_RUB = 90.0


@pytest.mark.asyncio
async def test_quote_calculates_net_after_fees(service):
    """quote(): rate = цена × USD/RUB, net = gross − комиссии.

    P2P-объявление отключаем, чтобы курс считался от базовой цены
    (mock-объявления P2P генерируются со случайной ценой).
    """

    async def no_ads(*, fiat="RUB"):
        return None

    service.p2p.best_buy_ad = no_ads

    q = await service.quote(1000.0)
    assert q.ok, f"quote failed: {q.error}"

    gross = 1000.0 * TEST_PRICE_USDT * TEST_USD_RUB
    # Комиссии считаются от gross суммарно: net = gross − 0.25% − 0.40%
    expected_net = gross * (1 - (SERVICE_FEE_PCT + SBP_FEE_PCT) / 100)

    assert q.payout.rate > 0
    assert q.payout.amount_rub == pytest.approx(expected_net, rel=1e-6)
    assert q.payout.amount_tzar == 1000.0
    assert q.payout.status in (PayoutStatus.CREATED, PayoutStatus.KYC_REQUIRED)


@pytest.mark.asyncio
async def test_quote_includes_stage_trace(service):
    """В stages видно цену, курс и итог — по ним бот показывает расчёт."""
    q = await service.quote(1000.0)
    assert q.ok
    stages = " ".join(q.stages)
    assert "price.usdt=" in stages
    assert "usd.rub=" in stages
    assert "rate=" in stages
    assert "net=" in stages


@pytest.mark.asyncio
async def test_quote_kyc_threshold(service):
    """Сумма выше KYC_THRESHOLD_RUB получает статус kyc_required."""
    from src.api.payouts.config import KYC_THRESHOLD_RUB

    # Подбираем сумму так, чтобы net заведомо была выше порога KYC
    big = (KYC_THRESHOLD_RUB / (TEST_PRICE_USDT * TEST_USD_RUB)) * 2
    q = await service.quote(big)
    assert q.ok
    assert q.payout.status == PayoutStatus.KYC_REQUIRED


@pytest.mark.asyncio
async def test_min_payout_enforced(service):
    """Сумма ниже MIN_PAYOUT_TSAR отклоняется с понятной ошибкой."""
    from src.api.payouts.config import MIN_PAYOUT_TSAR

    q = await service.quote(MIN_PAYOUT_TSAR * 0.5)
    assert not q.ok
    assert "мин." in q.error
    assert f"{MIN_PAYOUT_TSAR:,.0f}" in q.error


@pytest.mark.asyncio
async def test_execute_sbp_full_pipeline(service):
    """Полный pipeline: ЦАРЬ→USDT→P2P→СБП→телефон."""
    r = await service.execute(
        user_id=123456789,
        tsar_amount=1000.0,
        recipient="+79001234567",
        method=PayoutMethod.SBP,
    )
    assert r.ok, f"execute failed: {r.error}"
    assert r.payout.status == PayoutStatus.SENT
    assert r.payout.external_id
    assert r.payout.amount_rub > 0
    assert r.payout.recipient == "+79001234567"

    stages = " ".join(r.stages)
    assert "quote.ok" in stages
    assert "p2p.ok" in stages
    assert "sbp.mock" in stages or "sbp.ok" in stages


@pytest.mark.asyncio
async def test_execute_rejects_bad_phone(service):
    """Некорректный телефон для СБП отклоняется, выплата не создаётся."""
    r = await service.execute(
        user_id=1,
        tsar_amount=1000.0,
        recipient="123",
        method=PayoutMethod.SBP,
    )
    assert not r.ok
    assert r.payout.status == PayoutStatus.FAILED


@pytest.mark.asyncio
async def test_execute_rejects_bad_card(service):
    """Карта должна быть ровно из 16 цифр."""
    r = await service.execute(
        user_id=1,
        tsar_amount=1000.0,
        recipient="4111111111111",
        method=PayoutMethod.CARD_RU,
    )
    assert not r.ok
    assert "16 цифр" in r.error


@pytest.mark.asyncio
async def test_p2p_rate_not_divided_by_price(service):
    """Курс P2P = ₽/USDT × USDT-на-ЦАРЬ (умножение, не деление).

    best_ad.price — это ₽ за 1 USDT. Деление на price_usdt дало бы
    курс в тысячи раз меньше реального.
    """
    from src.api.payouts.p2p import P2PAd

    # Цена объявления НИЖЕ базового курса (90 ₽/USDT), чтобы ветка p2p_rate
    # стала решающей: rate = min(price×usd_rub, ad.price×price_usdt).
    ad = P2PAd(
        id="mock-1",
        nickname="TestSeller",
        price=80.0,
        available_usdt=500_000,
        min_amount_rub=1_000,
        max_amount_rub=1_000_000,
        source="mock",
    )

    async def fake_best_buy_ad(*, fiat="RUB"):
        return ad

    service.p2p.best_buy_ad = fake_best_buy_ad

    q = await service.quote(1000.0)
    assert q.ok

    # 80 ₽/USDT × 0.1027881907 USDT/ЦАРЬ = 8.22 ₽ за ЦАРЬ
    # Объявление дешевле базового курса (90 ₽/USDT), значит p2p_rate < rate
    expected = ad.price * TEST_PRICE_USDT
    assert expected < TEST_PRICE_USDT * TEST_USD_RUB
    assert q.payout.rate == pytest.approx(expected, rel=1e-6)
    # Деление дало бы 80/0.1027 ≈ 778 — такого быть не должно
    assert q.payout.rate < 100
