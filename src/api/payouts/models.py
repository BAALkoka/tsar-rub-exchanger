"""Pydantic-модели для выплат."""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class PayoutMethod(str, Enum):
    """Способ выплаты."""

    SBP = "sbp"               # Система быстрых платежей
    CARD_RU = "card_ru"       # Банковская карта РФ (МИР/Visa/MC)
    CARD_FOREIGN = "card_foreign"  # Зарубежная карта (через партнёров)


class PayoutStatus(str, Enum):
    """Жизненный цикл выплаты."""

    CREATED = "created"
    KYC_REQUIRED = "kyc_required"
    PROCESSING = "processing"
    SENT = "sent"
    COMPLETED = "completed"
    FAILED = "failed"
    REFUNDED = "refunded"


class Payout(BaseModel):
    """Заявка на выплату."""

    id: str = Field(..., description="Внутренний UUID")
    user_id: int = Field(..., description="Telegram user id")
    amount_rub: float = Field(..., gt=0, description="Сумма в RUB")
    amount_tzar: float = Field(..., gt=0, description="Сумма в ЦАРЬ")
    rate: float = Field(..., gt=0, description="Курс ЦАРЬ→RUB на момент создания")
    method: PayoutMethod
    recipient: str = Field(..., description="Телефон СБП / номер карты / IBAN")
    status: PayoutStatus = PayoutStatus.CREATED
    external_id: Optional[str] = None  # id операции у банка/СБП
    error: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)