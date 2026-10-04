"""Payouts: обмен ЦАРЬ → RUB → карта.

Модуль инкапсулирует логику выплат через СБП / банковские карты РФ.
Поддерживает три сценария (см. ROADMAP.md Q1-2027):
  - малый (до 5 000 ₽, без KYC, моментально)
  - средний (5 000 – 50 000 ₽, упрощённый KYC)
  - крупный (> 50 000 ₽, через менеджера)
"""
from .service import PayoutService, PayoutResult
from .models import Payout, PayoutMethod, PayoutStatus
from .sbp import SbpClient, SbpError

__all__ = [
    "PayoutService",
    "PayoutResult",
    "Payout",
    "PayoutMethod",
    "PayoutStatus",
    "SbpClient",
    "SbpError",
]