"""FastAPI HTTP-слой для обменника."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from .config import TSAR_MASTER, TSAR_TON_POOL
from .price_feed import PriceFeed
from .service import PayoutService
from .sbp import SbpClient, SbpConfig

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    feed = PriceFeed(geckoterminal_pool_address=TSAR_TON_POOL, manual_rate=1.0)
    sbp = SbpClient(SbpConfig(merchant_id="demo", api_key="demo"))
    app.state.service = PayoutService(sbp_client=sbp, price_feed=feed)
    app.state.feed = feed
    yield
    await feed.close()


app = FastAPI(title="TSAR → RUB Off-ramp", lifespan=lifespan)


class QuoteRequest(BaseModel):
    amount_tzar: float


class QuoteResponse(BaseModel):
    amount_tzar: float
    amount_rub: float
    rate: float
    source: str
    allowed: bool
    min_tsar: float


class PayoutRequest(BaseModel):
    user_id: int
    amount_tzar: float
    recipient: str


class PayoutResponse(BaseModel):
    payout_id: str
    status: str
    amount_rub: float
    error: str | None = None


@app.get("/health")
async def health():
    return {"status": "ok", "tsar_master": TSAR_MASTER, "pool": TSAR_TON_POOL}


@app.post("/v1/quote", response_model=QuoteResponse)
async def quote(req: QuoteRequest):
    svc: PayoutService = app.state.service
    q = await svc.quote(req.amount_tzar)
    rub = req.amount_tzar * q.rate
    return QuoteResponse(
        amount_tzar=req.amount_tzar,
        amount_rub=rub,
        rate=q.rate,
        source=q.source,
        allowed=svc.is_amount_allowed(req.amount_tzar, q.rate),
        min_tsar=svc.MIN_TSAR,
    )


@app.post("/v1/payouts", response_model=PayoutResponse)
async def create_payout(req: PayoutRequest):
    svc: PayoutService = app.state.service
    result = await svc.create(
        user_id=req.user_id,
        amount_tzar=req.amount_tzar,
        method=req.method if hasattr(req, "method") else __import__("src.api.payouts.models", fromlist=["PayoutMethod"]).PayoutMethod.SBP,
        recipient=req.recipient,
    )
    if not result.ok:
        raise HTTPException(status_code=400, detail=result.error or "payout_failed")
    return PayoutResponse(
        payout_id=result.payout.id,
        status=result.payout.status.value,
        amount_rub=result.payout.amount_rub,
    )