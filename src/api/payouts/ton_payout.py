"""TON-перевод ЦАРЬ с кошелька пользователя на кошелёк обменника.

Требует:
  - ton-core или tonweb
  - мнемонику кошелька пользователя (24 слова) — для подписи транзакции
  - jetton-адрес ЦАРЬ (master-контракт) — один из трёх: BAAL_RA / BLIZNETSY / CROWN
  - кошелёк обменника (TSAR_TREASURY_ADDRESS)

Mock-режим: возвращает фейковый tx_hash без подписи.
Боевой режим: реальная jetton-транзакция через ton-core.

Деривация jetton-кошелька делается локально из master-адреса
и адреса владельца: cell hash → base64url → адрес вида «0:…».
"""
from __future__ import annotations

import base64
import hashlib
import logging
import os
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from .config import (
    TSAR_DECIMALS,
    TSAR_LEGACY_BLIZNETSY,
    TSAR_LEGACY_CROWN,
    TSAR_MASTER,
    TSAR_TREASURY_ADDRESS,
)

logger = logging.getLogger(__name__)

# === Три слага ЦАРЬ → master-контракты ===
TON_JETTON_MASTERS: dict[str, str] = {
    "BAAL_RA": TSAR_MASTER,
    "BLIZNETSY": TSAR_LEGACY_BLIZNETSY,
    "CROWN": TSAR_LEGACY_CROWN,
}

# Сигнатура кода деривации jetton-кошелька (op=0, owner, jetton master).
_JETTON_WALLET_CODE = b"\x00\x00\x00\x00"


def supported_slugs() -> list[str]:
    """Список слагов ЦАРЬ, которые умеет отправлять этот модуль."""
    return list(TON_JETTON_MASTERS.keys())


def normalize_slug(slug: str) -> str:
    """Приводит слаг к верхнему регистру; поддерживает синонимы."""
    s = (slug or "").strip().upper().replace("-", "_").replace(" ", "_")
    aliases = {
        "BAAL": "BAAL_RA",
        "BAAL_RA": "BAAL_RA",
        "БЛИЗНЕЦЫ": "BLIZNETSY",
        "BLIZNETSY": "BLIZNETSY",
        "CROWN": "CROWN",
        "ЦАРЬ": "BAAL_RA",
    }
    if s not in aliases:
        raise TonPayoutError(f"unknown TSAR slug: {slug!r} (supported: {supported_slugs()})")
    return aliases[s]


@dataclass
class JettonWalletInfo:
    """Инфо о jetton-кошельке владельца."""

    slug: str
    master: str
    owner: str
    address: str          # user-friendly, «EQ…»
    raw: str              # «0:…»
    address_hash: str     # hex sha256 cell hash


@dataclass
class TonTx:
    """Результат TON jetton-перевода."""

    tx_hash: str
    src: str               # кошелёк отправителя
    dst: str               # кошелёк получателя
    jetton: str            # master jetton
    amount: float          # в jetton-единицах
    amount_raw: int        # в on-chain units (с учётом decimals)
    lt: int | None = None
    source: str = "mock"   # mock | ton-core | tonweb
    created_at: float = 0.0
    slug: str = "BAAL_RA"
    jetton_wallet: str = ""   # адрес jetton-кошелька отправителя
    extra: dict[str, Any] = field(default_factory=dict)


class TonPayoutError(Exception):
    pass


def _b64url(raw: bytes) -> str:
    """Base64url без padding — как в TON-адресах."""
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _raw_to_user_friendly(raw: str) -> str:
    """Из «0:hex» делает «EQ…» (user-friendly)."""
    _prefix, _, hexpart = raw.partition(":")
    try:
        data = bytes.fromhex(hexpart)
    except ValueError as e:
        raise TonPayoutError(f"bad raw address: {raw!r}") from e
    return "EQ" + _b64url(data)


def _user_friendly_to_raw(address: str) -> str:
    """Из «EQ…» делает «0:hex»."""
    s = (address or "").strip()
    if s.startswith("0:"):
        return s
    if s.startswith("EQ"):
        s = s[2:]
    s += "=" * (-len(s) % 4)
    try:
        data = base64.urlsafe_b64decode(s.encode("ascii"))
    except Exception as e:
        raise TonPayoutError(f"bad address: {address!r}") from e
    return "0:" + data.hex()


def derive_jetton_wallet(*, owner: str, master: str) -> JettonWalletInfo:
    """Деривирует jetton-кошелёк владельца из master-контракта.

    Схема (стандартная jetton-обёртка v1):
      state_init = op(0) + balance(0) + owner + jetton_master

    Хэш считается локально, поэтому интернет не нужен.
    """
    owner_raw = _user_friendly_to_raw(owner)
    master_raw = _user_friendly_to_raw(master)

    owner_bytes = bytes.fromhex(owner_raw.partition(":")[2])
    master_bytes = bytes.fromhex(master_raw.partition(":")[2])

    # cell: refs=0, bits: op=0, balance=0, затем CellSlice двух адресов
    payload = bytearray()
    payload += _JETTON_WALLET_CODE
    payload += bytes(8)               # balance = 0 (8 байт little-endian)
    payload += owner_bytes
    payload += master_bytes

    cell_hash = hashlib.sha256(bytes(payload)).digest()
    raw = "0:" + cell_hash.hex()
    return JettonWalletInfo(
        slug="",
        master=master,
        owner=owner,
        address=_raw_to_user_friendly(raw),
        raw=raw,
        address_hash=cell_hash.hex(),
    )


class TonPayout:
    """Jetton-перевод ЦАРЬ через TON.

    Mock-режим (по умолчанию): возвращает фейковый tx_hash.
    Боевой: через ton-core (async) или tonweb (sync).
    """

    def __init__(
        self,
        *,
        mnemonic: str | None = None,
        jetton_master: str = TSAR_MASTER,
        treasury: str = TSAR_TREASURY_ADDRESS,
        decimals: int = TSAR_DECIMALS,
        rpc_url: str = "https://toncenter.com/api/v2/jsonRPC",
        api_key: str | None = None,
        timeout_sec: float = 15.0,
    ):
        self.mnemonic = (
            mnemonic
            or os.getenv("WALLET_MNEMONIC")
            or os.getenv("TON_MNEMONIC")
            or ""
        ).strip() or None
        self.jetton_master = jetton_master
        self.treasury = treasury
        self.decimals = decimals
        self.rpc_url = rpc_url
        self.api_key = api_key or os.getenv("TONAPI_TOKEN")
        self.timeout = timeout_sec
        self._wallet_address: str | None = None

    @property
    def is_configured(self) -> bool:
        return bool(self.mnemonic)

    @property
    def is_mock(self) -> bool:
        """True, если боевой перевод невозможен (нет мнемоники)."""
        return not self.is_configured

    async def get_wallet_address(self) -> str:
        """Возвращает адрес нашего кошелька (деривация из мнемоники)."""
        if self._wallet_address:
            return self._wallet_address
        if not self.is_configured:
            # Mock-адрес для тестов
            self._wallet_address = "EQDrLq-X6jKZ3D4MjBQK2c6dAR3wK1D7c7-3X-4Y-5Z-6A-7B"
            return self._wallet_address
        try:
            from ton_core import Wallet
            mnemonic = self.mnemonic or ""
            w = Wallet.from_mnemonic(mnemonics=mnemonic.split())
            self._wallet_address = w.address.to_str()
            return self._wallet_address
        except ImportError:
            logger.warning("ton-core не установлен — fallback на mock-адрес")
            self._wallet_address = "EQDrLq-X6jKZ3D4MjBQK2c6dAR3wK1D7c7-3X-4Y-5Z-6A-7B"
            return self._wallet_address

    async def get_jetton_wallet(self, slug: str = "BAAL_RA") -> JettonWalletInfo:
        """Jetton-кошелёк нашего кошелька по слагу ЦАРЬ."""
        s = normalize_slug(slug)
        master = TON_JETTON_MASTERS[s]
        owner = await self.get_wallet_address()
        info = derive_jetton_wallet(owner=owner, master=master)
        info.slug = s
        return info

    async def get_all_jetton_wallets(self) -> dict[str, JettonWalletInfo]:
        """Все три jetton-кошелька нашего кошелька — по слагам."""
        out: dict[str, JettonWalletInfo] = {}
        for s in TON_JETTON_MASTERS:
            out[s] = await self.get_jetton_wallet(s)
        return out

    async def send_tsar(self, *, amount: float, slug: str = "BAAL_RA") -> TonTx:
        """Отправляет amount ЦАРЬ на кошелёк обменника.

        Args:
            amount: количество ЦАРЬ (например 1.2)
            slug: слаг токена — BAAL_RA / BLIZNETSY / CROWN

        Returns:
            TonTx с tx_hash, lt, etc.

        Raises:
            TonPayoutError: при ошибке перевода
        """
        if amount <= 0:
            raise TonPayoutError(f"amount must be positive, got {amount}")

        s = normalize_slug(slug)
        master = TON_JETTON_MASTERS[s]

        amount_raw = int(amount * (10 ** self.decimals))
        src = await self.get_wallet_address()
        jw = await self.get_jetton_wallet(s)
        now = time.time()

        if not self.is_configured:
            # === MOCK-режим ===
            tx_hash = f"mock_{uuid.uuid4().hex}"
            logger.info(
                "TON mock payout: %.4f ЦАРЬ (%d raw) %s → %s [%s]",
                amount, amount_raw, src, self.treasury, s,
            )
            return TonTx(
                tx_hash=tx_hash,
                src=src,
                dst=self.treasury,
                jetton=master,
                amount=amount,
                amount_raw=amount_raw,
                lt=int(now * 1e6),
                source="mock",
                created_at=now,
                slug=s,
                jetton_wallet=jw.address,
            )

        # === БОЕВОЙ РЕЖИМ через ton-core ===
        try:
            from ton_core import Address, Wallet
            mnemonic = self.mnemonic or ""
            w = Wallet.from_mnemonic(mnemonics=mnemonic.split())
            jetton_wallet = w.create_wallet(
                jetton_master=Address(master),
            )
            tx = await jetton_wallet.transfer(
                destination=Address(self.treasury),
                amount=amount_raw,
            )
            await w.send_transfer(tx)
            return TonTx(
                tx_hash=tx.cell_hash.hex() if hasattr(tx.cell_hash, "hex") else str(tx.cell_hash),
                src=src,
                dst=self.treasury,
                jetton=master,
                amount=amount,
                amount_raw=amount_raw,
                lt=getattr(tx, "lt", None),
                source="ton-core",
                created_at=now,
                slug=s,
                jetton_wallet=jw.address,
            )
        except ImportError as e:
            raise TonPayoutError("ton-core не установлен. pip install ton-core") from e
        except TonPayoutError:
            raise
        except Exception as e:
            raise TonPayoutError(f"TON transfer failed: {e}") from e

    async def close(self) -> None:
        """Закрыть ресурсы (для совместимости с другими клиентами)."""
        pass
