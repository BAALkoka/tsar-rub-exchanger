"""Общие фикстуры для тестов payouts.

Тесты детерминированы: сеть не используется, курс и P2P-объявления
подменяются фиксированными значениями (manual_rate + mock-объявления).
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# Корень репозитория, чтобы работал импорт `src.api.payouts.*`
ROOT = Path(__file__).resolve().parents[4]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Дефолты окружения ДО импорта config: config читает их при импорте модуля.
os.environ.setdefault("MIN_PAYOUT_TSAR", "1")
os.environ.setdefault("SERVICE_FEE_PCT", "0.25")
os.environ.setdefault("SBP_FEE_PCT", "0.40")
os.environ.setdefault("P2P_FEE_PCT", "0.20")
os.environ.setdefault("P2P_API_KEY", "")
os.environ.setdefault("SBP_PROVIDER", "mock")
os.environ.setdefault("USD_RUB_FALLBACK", "90.0")

import pytest  # noqa: E402

from src.api.payouts.p2p import P2PClient  # noqa: E402
from src.api.payouts.price_feed import PriceFeed  # noqa: E402
from src.api.payouts.sbp import CardTransferClient, SbpClient, SbpConfig  # noqa: E402
from src.api.payouts.service import PayoutService  # noqa: E402

# Фиксированные значения для детерминизма
TEST_PRICE_USDT = 0.1027881907
TEST_USD_RUB = 90.0


@pytest.fixture
def price_feed():
    """PriceFeed с фиксированным курсом — без обращений к сети.

    Курс USD/RUB тоже фиксирован: get_usd_rub() в реальном коде тянет
    живые данные ЦБ РФ, из-за чего расчёты в тестах плавали.
    """
    feed = PriceFeed(manual_rate=TEST_PRICE_USDT, fallback_price=TEST_PRICE_USDT)

    async def fixed_usd_rub() -> float:
        return TEST_USD_RUB

    feed.get_usd_rub = fixed_usd_rub
    yield feed


@pytest.fixture
def p2p_client():
    client = P2PClient(api_key="")
    yield client


@pytest.fixture
def service(price_feed, p2p_client):
    """PayoutService в mock-режиме: P2P без ключа, СБП — mock-провайдер."""
    sbp = SbpClient(SbpConfig(provider="mock", merchant_id="test", api_key="test"))
    card = CardTransferClient(SbpConfig(provider="mock", merchant_id="test", api_key="test"))
    svc = PayoutService(
        p2p_client=p2p_client,
        price_feed=price_feed,
        sbp_client=sbp,
        card_client=card,
        ton_payout=None,
    )
    yield svc
