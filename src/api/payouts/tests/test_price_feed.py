"""Тесты PriceFeed под реальный API.

Реальные методы: get_price_usdt(), get_usd_rub(), close().
"""
from __future__ import annotations

import pytest

from src.api.payouts.price_feed import PriceFeed


@pytest.mark.asyncio
async def test_manual_rate_takes_priority():
    """Заданный вручную курс важнее любых сетевых источников."""
    feed = PriceFeed(manual_rate=1.5)
    assert await feed.get_price_usdt() == 1.5
    await feed.close()


@pytest.mark.asyncio
async def test_manual_rate_avoids_network(monkeypatch):
    """При заданном курсе сеть не дёргается."""
    feed = PriceFeed(manual_rate=2.0)

    async def boom(*args, **kwargs):
        raise AssertionError("сеть не должна вызываться при manual_rate")

    monkeypatch.setattr(feed, "_price_from_geckoterminal", boom)
    assert await feed.get_price_usdt() == 2.0
    await feed.close()


@pytest.mark.asyncio
async def test_fallback_used_when_no_source(monkeypatch):
    """Если ни один источник не ответил — берётся fallback."""
    feed = PriceFeed(manual_rate=0.0, fallback_price=0.000058)

    async def fail(*args, **kwargs):
        raise RuntimeError("network down")

    monkeypatch.setattr(feed, "_price_from_geckoterminal", fail)
    monkeypatch.setattr(feed, "_http", fail)

    assert await feed.get_price_usdt() == 0.000058
    await feed.close()


def test_find_pool_ignores_bulk_response():
    """DeDust /v2/pools отдаёт все пулы сети — нужна ручная выборка."""
    payload = [
        {"address": "EQOther", "assets": [], "reserves": []},
        {
            "address": "EQTarget",
            "assets": [
                {"metadata": {"decimals": 6}},
                {"metadata": {"decimals": 9}},
            ],
            "reserves": ["1000000", "2000000000"],
        },
    ]
    pool = PriceFeed._find_pool(payload, "EQTarget")
    assert pool is not None
    assert pool["address"] == "EQTarget"
    assert PriceFeed._find_pool(payload, "EQMissing") is None


def test_low_liquidity_pool_is_rejected():
    """Пул с резервом $0.02 нельзя использовать как источник цены."""
    feed = PriceFeed(min_liquidity_usd=50.0)
    thin_pool = {
        "address": "EQThin",
        "assets": [{"metadata": {"decimals": 6}}, {"metadata": {"decimals": 9}}],
        "reserves": ["20000", "200000000000"],
    }
    assert feed._pool_is_liquid(thin_pool) is False

    rich_pool = {
        "address": "EQRich",
        "assets": [{"metadata": {"decimals": 6}}, {"metadata": {"decimals": 9}}],
        "reserves": ["500000000", "5000000000000"],
    }
    assert feed._pool_is_liquid(rich_pool) is True


def test_pool_price_from_reserves():
    """Цена = quote/base по резервам с учётом decimals."""
    pool = {
        "assets": [{"metadata": {"decimals": 6}}, {"metadata": {"decimals": 9}}],
        "reserves": ["1000000", "1000000000"],
    }
    # reserves: 1 000 000 / 10^6 = 1 USDT, 1 000 000 000 / 10^9 = 1 ЦАРЬ
    assert PriceFeed._pool_price_usdt(pool) == pytest.approx(1.0, rel=1e-9)
