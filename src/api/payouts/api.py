"""FastAPI эндпоинты: /v1/quote, /v1/payouts, /health, /ton/notify."""
from __future__ import annotations
import logging
from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from .config import TSAR_MASTER, TSAR_PRIMARY_POOL, USDT_TREASURY_ADDRESS
from .price_feed import PriceFeed
from .p2p import P2PClient, P2PError, P2PNoAds
from .service import PayoutService
from .models import Payout, PayoutMethod, PayoutStatus
from .tokens import find_by_master, short_master

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("tsar.api")

app = FastAPI(title="Tsar API", version="1.0.0")
# Цена через GeckoTerminal (DeDust USDT-пул) с fallback
feed = PriceFeed(token_pool=TSAR_PRIMARY_POOL, manual_rate=1.0)
p2p_client = P2PClient()
payout_service = PayoutService(p2p_client=p2p_client, price_feed=feed)


class QuoteRequest(BaseModel):
    tsar_amount: float = Field(..., gt=0)
    slippage_pct: float = Field(2.0, ge=0, le=50)


class QuoteResponse(BaseModel):
    tsar_amount: float
    tsar_price_usd: float
    usd_amount: float
    rub_amount: float
    rate_used: float
    source: str


class PayoutCreateRequest(BaseModel):
    user_id: int = Field(..., gt=0)
    tsar_amount: float = Field(..., gt=0)
    recipient: str = Field(..., min_length=16, max_length=20)


class PayoutCreateResponse(BaseModel):
    ok: bool
    payout_id: str
    amount_rub: float
    p2p_partner: Optional[str] = None
    p2p_price: Optional[float] = None
    error: Optional[str] = None


class TonNotifyRequest(BaseModel):
    event: dict
    source: str = "tonapi.io"


class TonNotifyResponse(BaseModel):
    ok: bool
    token: Optional[str] = None
    jetton_master: Optional[str] = None
    amount: Optional[float] = None
    error: Optional[str] = None


@app.get("/health")
async def health() -> dict:
    return {
        "status": "ok",
        "tsar_master": TSAR_MASTER,
        "pool": TSAR_PRIMARY_POOL,
        "treasury": USDT_TREASURY_ADDRESS,
    }


@app.get("/v1/pools")
async def pools() -> dict:
    """Реальные P2P-объявления (DeDust / walletbot)."""
    try:
        ads = await p2p_client.get_buy_ads(crypto="USDT", fiat="RUB", side="BUY", page_size=10)
        return {
            "ok": True,
            "count": len(ads),
            "ads": [
                {
                    "id": a.id,
                    "nickname": a.nickname,
                    "price": a.price,
                    "available_usdt": a.available_usdt,
                    "min_amount_rub": a.min_amount_rub,
                    "max_amount_rub": a.max_amount_rub,
                    "payments": a.payments,
                    "merchant_level": a.merchant_level,
                    "is_online": a.is_online,
                }
                for a in ads
            ],
        }
    except P2PError as e:
        return {"ok": False, "error": str(e)}


@app.post("/v1/quote", response_model=QuoteResponse)
async def quote(req: QuoteRequest):
    q = await feed.quote(req.tsar_amount)
    if not q.ok:
        raise HTTPException(503, f"price feed error: {q.error}")
    return QuoteResponse(
        tsar_amount=req.tsar_amount,
        tsar_price_usd=q.tsar_price_usd,
        usd_amount=q.usd_amount,
        rub_amount=q.rub_amount,
        rate_used=q.rate_used,
        source=q.source,
    )


@app.post("/v1/payouts", response_model=PayoutCreateResponse)
async def create_payout(req: PayoutCreateRequest):
    result = await payout_service.payout(
        user_id=req.user_id,
        tsar_amount=req.tsar_amount,
        recipient=req.recipient,
        method=PayoutMethod.CARD_RU,
    )
    if not result.ok:
        return PayoutCreateResponse(
            ok=False,
            payout_id=result.payout.id,
            amount_rub=result.payout.amount_rub,
            error=result.error,
        )
    return PayoutCreateResponse(
        ok=True,
        payout_id=result.payout.id,
        amount_rub=result.payout.amount_rub,
        p2p_partner=(result.p2p_ad.nickname if result.p2p_ad else None),
        p2p_price=(result.p2p_ad.price if result.p2p_ad else None),
    )


@app.post("/ton/notify", response_model=TonNotifyResponse)
async def ton_notify(req: TonNotifyRequest):
    """Webhook для TonAPI (или ручного вызова): определить токен ЦАРЬ.

    Если на казначейство пришёл jetton, у которого master известен
    (любой из 3 серий ЦАРЬ) — возвращаем, какой это токен.
    Используется для автодетекта по IP-переводу.
    """
    try:
        event = req.event
        master = ""
        amount = 0.0
        decimals = 9
        for act in event.get("actions", []):
            if act.get("type") != "JettonTransfer":
                continue
            jt = act.get("JettonTransfer", {})
            master = (jt.get("jetton") or {}).get("address", "")
            raw = int(jt.get("amount", "0"))
            decimals = int((jt.get("jetton") or {}).get("decimals", "9") or 9)
            amount = raw / (10 ** decimals)
            break
        token = find_by_master(master)
        if not token:
            return TonNotifyResponse(ok=False, jetton_master=master, amount=amount,
                                     error=f"unknown jetton master {short_master(master)}")
        return TonNotifyResponse(
            ok=True,
            token=token.name,
            jetton_master=master,
            amount=amount,
        )
    except Exception as e:
        return TonNotifyResponse(ok=False, error=str(e))