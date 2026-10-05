"""FastAPI приложение: /v1/quote, /v1/payouts, /v1/pools, /ton/notify, /health."""
from __future__ import annotations
import asyncio
import logging
import os
from typing import Optional

from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel, Field

from .config import (
    USD_RUB_FALLBACK,
    USDT_TREASURY_ADDRESS,
    SUPPORT_HANDLE,
    ADMIN_CHAT_ID,
)
from .tokens import list_tokens, get_token, find_by_master, short_master, TOKENS
from .price_feed import PriceFeed
from .p2p import P2PClient, P2PError
from .service import PayoutService
from .models import PayoutMethod

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Tsar RUB Exchanger",
    description="Off-ramp ЦАРЬ → USDT → P2P → RUB → карта. 3 серии ЦАРЬ с разными DeDust-пулами.",
    version="1.0.0",
)

# Создаём по фиду на каждый токен (с его DeDust-пулом)
feeds: dict[str, PriceFeed] = {
    t.slug: PriceFeed(token_master=t.master, token_pool=t.pool, pool_label=t.pool_label)
    for t in list_tokens()
}
p2p = P2PClient()


def _service(slug: str) -> PayoutService:
    return PayoutService(p2p_client=p2p, price_feed=feeds[slug])


class QuoteRequest(BaseModel):
    tsar_amount: float = Field(..., gt=0, description="Количество ЦАРЬ")
    token: str = Field(default="BAAL_RA", description="Слаг токена: BAAL_RA, GEMINI, CROWN")


class QuoteResponse(BaseModel):
    ok: bool
    token: str
    token_label: str
    pool: str
    pool_label: str
    tsar_amount: float
    tsar_price_usd: float
    usd_amount: float
    rub_amount: float
    usd_rub: float
    source: str
    error: Optional[str] = None


@app.get("/health")
async def health():
    return {"ok": True, "service": "tsar-rub-exchanger", "version": "1.0.0"}


@app.get("/v1/pools")
async def list_pools():
    """Список всех 3 DeDust-пулов ЦАРЬ с ценами."""
    out = []
    for t in list_tokens():
        try:
            q = await feeds[t.slug].quote(1)
            out.append({
                "token": t.slug,
                "name": t.name,
                "symbol": t.symbol,
                "emoji": t.emoji,
                "master": t.master,
                "pool": t.pool,
                "pool_label": t.pool_label,
                "tsar_price_usd": q.tsar_price_usd if q.ok else 0,
                "tsar_price_rub": q.rate if q.ok else 0,
                "ok": q.ok,
                "source": q.source,
                "error": q.error if not q.ok else None,
            })
        except Exception as e:
            out.append({"token": t.slug, "ok": False, "error": str(e)})
    return {"pools": out, "usd_rub_fallback": USD_RUB_FALLBACK}


@app.post("/v1/quote", response_model=QuoteResponse)
async def quote(req: QuoteRequest):
    token = get_token(req.token)
    if not token:
        raise HTTPException(404, f"unknown token: {req.token}")
    q = await feeds[token.slug].quote(req.tsar_amount)
    return QuoteResponse(
        ok=q.ok,
        token=token.slug,
        token_label=f"{token.emoji} {token.name}",
        pool=token.pool,
        pool_label=token.pool_label,
        tsar_amount=req.tsar_amount,
        tsar_price_usd=q.tsar_price_usd,
        usd_amount=q.usd_amount,
        rub_amount=q.rub_amount,
        usd_rub=q.rate_used,
        source=q.source,
        error=q.error,
    )


class PayoutRequest(BaseModel):
    user_id: int
    token: str = "BAAL_RA"
    tsar_amount: float = Field(..., gt=0)
    recipient: str
    method: PayoutMethod = PayoutMethod.CARD_RU


class PayoutResponse(BaseModel):
    ok: bool
    payout_id: Optional[str] = None
    amount_rub: float = 0
    p2p_partner: Optional[str] = None
    p2p_price: float = 0
    error: Optional[str] = None


@app.post("/v1/payouts", response_model=PayoutResponse)
async def create_payout(req: PayoutRequest):
    token = get_token(req.token)
    if not token:
        raise HTTPException(404, f"unknown token: {req.token}")
    if req.tsar_amount < token.min_tsar:
        raise HTTPException(
            400,
            f"min amount for {token.slug}: {token.min_tsar}",
        )
    result = await _service(token.slug).payout(
        user_id=req.user_id,
        tsar_amount=req.tsar_amount,
        recipient=req.recipient,
        method=req.method,
    )
    if not result.ok:
        return PayoutResponse(ok=False, error=result.error)
    ad = result.p2p_ad
    return PayoutResponse(
        ok=True,
        payout_id=result.payout.id,
        amount_rub=result.payout.amount_rub,
        p2p_partner=ad.nickname if ad else None,
        p2p_price=ad.price if ad else 0,
    )


class TonNotifyEvent(BaseModel):
    tx_hash: str
    sender: str
    jetton_master: str
    amount: float


@app.post("/ton/notify")
async def ton_notify(event: TonNotifyEvent):
    """Webhook от TonAPI: уведомление о входящем jetton-переводе."""
    token = find_by_master(event.jetton_master)
    if not token:
        raise HTTPException(404, f"unknown jetton master: {event.jetton_master}")
    return {
        "ok": True,
        "token": token.slug,
        "name": token.name,
        "emoji": token.emoji,
        "master_short": short_master(event.jetton_master),
        "amount": event.amount,
        "sender_short": short_master(event.sender),
    }


@app.on_event("shutdown")
async def _shutdown():
    for f in feeds.values():
        await f.close()
    await p2p.close()