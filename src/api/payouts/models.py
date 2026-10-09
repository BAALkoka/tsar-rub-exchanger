"""Pydantic-модели для выплат."""
from __future__ import annotations
from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class PayoutMethod(str, Enum):
    SBP = "sbp"
    CARD_RU = "card_ru"
    CARD_FOREIGN = "card_foreign"


class PayoutStatus(str, Enum):
    PENDING = "pending"
    CREATED = "created"
    KYC_REQUIRED = "kyc_required"
    PROCESSING = "processing"
    SENT = "sent"
    COMPLETED = "completed"
    FAILED = "failed"
    REFUNDED = "refunded"


class Payout(BaseModel):
    id: str = Field(...)
    user_id: int = Field(0)
    amount_rub: float = Field(0, ge=0)
    amount_tzar: float = Field(0, ge=0)
    rate: float = Field(0, ge=0)
    method: PayoutMethod = PayoutMethod.SBP
    recipient: str = Field("")
    status: PayoutStatus = PayoutStatus.PENDING
    external_id: Optional[str] = None
    error: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class PayoutResult(BaseModel):
    ok: bool
    payout: Payout
    error: Optional[str] = None
    stages: list[str] = Field(default_factory=list)
    p2p_ad: Optional[dict] = None
