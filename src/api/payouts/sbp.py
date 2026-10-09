"""СБП + переводы на карту. 9 банков СБП + 8 банков CARD + mock."""
from __future__ import annotations
import asyncio
import logging
from dataclasses import dataclass
from typing import Optional
import httpx
from .config import SBP_API_KEY, SBP_BASE_URL, SBP_MERCHANT_ID, SBP_PROVIDER

logger = logging.getLogger(__name__)


class SbpError(Exception):
    pass


class CardTransferError(Exception):
    pass


@dataclass
class SbpConfig:
    provider: str
    merchant_id: str
    api_key: str
    base_url: str = "https://api.tochka.ru/v1"
    timeout_sec: float = 8.0
    max_retries: int = 3


@dataclass
class SbpResult:
    external_id: str
    status: str
    provider: str
    amount_rub: float
    phone: str
    raw: dict


@dataclass
class CardTransferResult:
    external_id: str
    status: str
    provider: str
    amount_rub: float
    card: str
    raw: dict


# 9 банков СБП
SBP_PROVIDERS = {
    "tochka":      ("Tochka",      "https://api.tochka.ru/v1",                   "/sbp/payouts"),
    "tinkoff":     ("Tinkoff",     "https://business.tinkoff.ru/openapi/api/v1", "/payments/sbp"),
    "sberbank":    ("SberBank",    "https://api.sberbank.ru/sbp/v1",             "/payouts"),
    "vtb":         ("VTB",         "https://api.vtb.ru/openapi/v1",              "/sbp/payouts"),
    "alfa":        ("AlfaBank",    "https://alfabank.ru/extapi",                 "/b2b/payments/sbp"),
    "psb":         ("PSB",         "https://api.psbank.ru/openapi/v1",           "/sbp/payouts"),
    "raiffeisen":  ("Raiffeisen",  "https://api.raiffeisen.ru/v1",               "/sbp/payouts"),
    "gazprombank": ("Gazprombank", "https://api.gazprombank.ru/v1",              "/sbp/payouts"),
    "robomarket":  ("Robomarket",  "https://api.robomarket.ru/v1",               "/sbp/payout"),
}

# 8 банков CARD
CARD_PROVIDERS = {
    "tochka_card":      ("Tochka",      "https://api.tochka.ru/v1",                   "/payouts/card"),
    "tinkoff_card":     ("Tinkoff",     "https://business.tinkoff.ru/openapi/api/v1", "/payments/card"),
    "sberbank_card":    ("SberBank",    "https://api.sberbank.ru/p2p/v1",             "/transfers"),
    "vtb_card":         ("VTB",         "https://api.vtb.ru/openapi/v1",              "/transfers/card"),
    "alfa_card":        ("AlfaBank",    "https://alfabank.ru/extapi",                 "/b2b/payments/card"),
    "psb_card":         ("PSB",         "https://api.psbank.ru/openapi/v1",           "/transfers/card"),
    "raiffeisen_card":  ("Raiffeisen",  "https://api.raiffeisen.ru/v1",               "/transfers/card"),
    "gazprombank_card": ("Gazprombank", "https://api.gazprombank.ru/v1",              "/transfers/card"),
}


class SbpClient:
    def __init__(self, config: SbpConfig):
        self.config = config
        self._seen_ids: set[str] = set()
        self._client: Optional[httpx.AsyncClient] = None

    async def _http(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=self.config.timeout_sec,
                headers={"accept": "application/json", "User-Agent": "tsar-bot/1.0",
                         "Authorization": f"Bearer {self.config.api_key}"},
            )
        return self._client

    async def close(self):
        if self._client:
            await self._client.aclose()
            self._client = None

    @classmethod
    def from_env(cls) -> "SbpClient":
        return cls(SbpConfig(
            provider=SBP_PROVIDER, merchant_id=SBP_MERCHANT_ID,
            api_key=SBP_API_KEY, base_url=SBP_BASE_URL,
        ))

    def is_live(self) -> bool:
        return self.config.provider != "mock" and bool(self.config.api_key)

    def available_sbp_providers(self) -> list[str]:
        return list(SBP_PROVIDERS.keys())

    async def payout(self, *, amount_rub, phone, idempotency_key, extra=None) -> SbpResult:
        if idempotency_key in self._seen_ids:
            return SbpResult(
                external_id=idempotency_key, status="duplicate",
                provider=self.config.provider, amount_rub=amount_rub,
                phone=phone, raw={"reason": "duplicate"},
            )
        self._seen_ids.add(idempotency_key)

        if self.config.provider == "mock":
            return await self._mock_send(amount_rub, phone, idempotency_key)

        if self.config.provider not in SBP_PROVIDERS:
            raise SbpError(f"Unknown SBP provider: {self.config.provider}")

        last_exc = None
        for attempt in range(1, self.config.max_retries + 1):
            try:
                name, base, path = SBP_PROVIDERS[self.config.provider]
                http = await self._http()
                r = await http.post(
                    f"{base}{path}",
                    json={"merchant_id": self.config.merchant_id, "amount": amount_rub,
                          "phone": phone, "idempotency_key": idempotency_key, "currency": "RUB"},
                    headers={"Idempotency-Key": idempotency_key},
                )
                r.raise_for_status()
                d = r.json()
                return SbpResult(
                    external_id=str(d.get("external_id") or d.get("id") or d.get("PaymentId") or idempotency_key),
                    status=str(d.get("status", "pending")),
                    provider=self.config.provider, amount_rub=amount_rub,
                    phone=phone, raw=d,
                )
            except (TimeoutError, ConnectionError) as e:
                last_exc = e
                await asyncio.sleep(0.5 * attempt)
            except SbpError:
                raise
        raise SbpError(f"SBP failed: {last_exc}")

    async def _mock_send(self, amount_rub, phone, idem) -> SbpResult:
        await asyncio.sleep(0.05)
        return SbpResult(
            external_id=f"sbp_mock_{phone[-4:]}_{int(amount_rub*100)}_{idem[-6:]}",
            status="sent", provider="mock", amount_rub=amount_rub,
            phone=phone, raw={"mock": True},
        )


class CardTransferClient:
    def __init__(self, config: SbpConfig):
        self.config = config
        self._client: Optional[httpx.AsyncClient] = None

    async def _http(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=self.config.timeout_sec,
                headers={"accept": "application/json", "User-Agent": "tsar-bot/1.0",
                         "Authorization": f"Bearer {self.config.api_key}"},
            )
        return self._client

    async def close(self):
        if self._client:
            await self._client.aclose()
            self._client = None

    def is_live(self) -> bool:
        return self.config.provider != "mock" and bool(self.config.api_key)

    def available_card_providers(self) -> list[str]:
        return list(CARD_PROVIDERS.keys())

    async def transfer(self, *, amount_rub, card, idempotency_key) -> CardTransferResult:
        if self.config.provider == "mock":
            return await self._mock_send(amount_rub, card, idempotency_key)

        provider_key = self.config.provider
        if provider_key in SBP_PROVIDERS and provider_key + "_card" in CARD_PROVIDERS:
            provider_key = provider_key + "_card"
        if provider_key not in CARD_PROVIDERS:
            raise CardTransferError(f"Unknown card provider: {self.config.provider}")

        last_exc = None
        for attempt in range(1, self.config.max_retries + 1):
            try:
                name, base, path = CARD_PROVIDERS[provider_key]
                http = await self._http()
                r = await http.post(
                    f"{base}{path}",
                    json={"merchant_id": self.config.merchant_id, "amount": amount_rub,
                          "card": card, "idempotency_key": idempotency_key, "currency": "RUB"},
                    headers={"Idempotency-Key": idempotency_key},
                )
                r.raise_for_status()
                d = r.json()
                return CardTransferResult(
                    external_id=str(d.get("external_id") or d.get("id") or idempotency_key),
                    status=str(d.get("status", "pending")),
                    provider=provider_key, amount_rub=amount_rub, card=card, raw=d,
                )
            except (TimeoutError, ConnectionError) as e:
                last_exc = e
                await asyncio.sleep(0.5 * attempt)
            except CardTransferError:
                raise
        raise CardTransferError(f"Card transfer failed: {last_exc}")

    async def _mock_send(self, amount_rub, card, idem) -> CardTransferResult:
        await asyncio.sleep(0.05)
        return CardTransferResult(
            external_id=f"card_mock_{card[-4:]}_{int(amount_rub*100)}_{idem[-6:]}",
            status="sent", provider="mock", amount_rub=amount_rub, card=card, raw={"mock": True},
        )
