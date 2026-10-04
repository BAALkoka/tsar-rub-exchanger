"""Клиент Тинькофф СБП API для выплат на карты и по телефону.

Нужны переменные окружения:
  TINKOFF_TERMINAL_KEY, TINKOFF_PASSWORD, TINKOFF_API_URL (опц.)
"""
from __future__ import annotations
import hashlib
import logging
import os
import time
from dataclasses import dataclass
from typing import Optional
import httpx

logger = logging.getLogger(__name__)


@dataclass
class PayoutResult:
    success: bool
    payment_id: Optional[str] = None
    status: str = "unknown"
    error: Optional[str] = None
    raw: Optional[dict] = None


class TinkoffSBPClient:
    API_URL = "https://api.tinkoff.ru/v1"

    def __init__(self, terminal_key=None, password=None, api_url=None, timeout=10.0):
        self.terminal_key = terminal_key or os.environ.get("TINKOFF_TERMINAL_KEY", "")
        self.password = password or os.environ.get("TINKOFF_PASSWORD", "")
        self.api_url = api_url or os.environ.get("TINKOFF_API_URL", self.API_URL)
        self.timeout = timeout
        self._client = httpx.AsyncClient(timeout=timeout)

    async def close(self):
        await self._client.aclose()

    def _sign(self, params: dict) -> str:
        values = [str(v) for v in params.values() if v is not None]
        return hashlib.sha256(("".join(values) + self.password).encode()).hexdigest()

    async def create_payout(self, *, amount_kopecks, recipient, description, order_id=None, payment_type="SBP") -> PayoutResult:
        if not self.terminal_key or not self.password:
            return PayoutResult(success=False, error="TINKOFF keys not set")

        order_id = order_id or f"tsar-{int(time.time())}"
        params = {
            "TerminalKey": self.terminal_key,
            "Amount": amount_kopecks,
            "OrderId": order_id,
            "Description": description,
            "Recipient": recipient,
            "PaymentType": payment_type,
        }
        params["Token"] = self._sign(params)
        try:
            r = await self._client.post(f"{self.api_url}/SbpPayOut", json=params)
            data = r.json()
        except Exception as e:
            return PayoutResult(success=False, error=str(e))

        success = data.get("Success") is True
        return PayoutResult(
            success=success,
            payment_id=data.get("PaymentId"),
            status=data.get("Status", "UNKNOWN"),
            error=data.get("Message") if not success else None,
            raw=data,
        )

    async def get_status(self, payment_id):
        params = {"TerminalKey": self.terminal_key, "PaymentId": payment_id}
        params["Token"] = self._sign(params)
        r = await self._client.post(f"{self.api_url}/GetSbpPayOutStatus", json=params)
        data = r.json()
        success = data.get("Success") is True
        return PayoutResult(
            success=success,
            payment_id=payment_id,
            status=data.get("Status", "UNKNOWN"),
            error=data.get("Message") if not success else None,
            raw=data,
        )