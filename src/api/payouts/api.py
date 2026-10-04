from __future__ import annotations
import logging

from fastapi import FastAPI
from pydantic import BaseModel, Field

from .config import TSAR_MASTER, TSAR_PRIMARY_POOL
from .price_feed import PriceFeed

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("tsar.api")

app = FastAPI(title="Tsar API", version="1.0.0")
feed = PriceFeed(geckoterminal_pool_address=TSAR_PRIMARY_POOL, manual_rate=1.0)


class QuoteRequest(BaseModel):
    tsar_amount: float = Field(..., gt=0, description="Количество ЦАРЬ")
    slippage_pct: float = Field(2.0, ge=0, le=50)


class QuoteResponse(BaseModel):
    tsar_amount: float
    tsar_price_usd: float
    usd_amount: float
    rub_amount: float
    rate_used: float
    source: str


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "tsar_master": TSAR_MASTER, "pool": TSAR_PRIMARY_POOL}
