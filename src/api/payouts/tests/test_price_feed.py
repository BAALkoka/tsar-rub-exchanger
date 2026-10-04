"""Тесты для PriceFeed."""
import pytest

from src.api.payouts.price_feed import PriceFeed, PriceFeedError


@pytest.mark.asyncio
async def test_manual_rate_works():
    feed = PriceFeed(manual_rate=1.5)
    quote = await feed.get_rate()
    assert quote.rate == 1.5
    assert quote.source == "manual"
    await feed.close()


@pytest.mark.asyncio
async def test_fresh_cache():
    feed = PriceFeed(manual_rate=2.0)
    q1 = await feed.get_rate()
    q2 = await feed.get_rate()  # должен вернуть кэш
    assert q1.fetched_at == q2.fetched_at
    await feed.close()


@pytest.mark.asyncio
async def test_no_sources_fails():
    feed = PriceFeed()
    with pytest.raises(PriceFeedError):
        await feed.get_rate()
    await feed.close()