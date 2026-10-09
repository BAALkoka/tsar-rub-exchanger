"""TON-перевод ЦАРЬ с кошелька пользователя на кошелёк обменника.

Требует:
  - ton-core или tonweb
  - мнемонику кошелька пользователя (24 слова) — для подписи транзакции
  - jetton-адрес ЦАРЬ (TSAR_MASTER)
  - кошелёк обменника (TSAR_TREASURY_ADDRESS)

Mock-режим: возвращает фейковый tx_hash без подписи.
Боевой режим: реальная jetton-транзакция через ton-core.
"""
from __future__ import annotations
import asyncio
import logging
import os
import time
import uuid
from dataclasses import dataclass
from typing import Optional

from .config import TSAR_DECIMALS, TSAR_MASTER, TSAR_TREASURY_ADDRESS

logger = logging.getLogger(__name__)


class TonPayoutError(Exception):
    pass


@dataclass
class TonTx:
    """Результат TON jetton-перевода."""
    tx_hash: str
    src: str               # кошелёк отправителя
    dst: str               # кошелёк получателя
    jetton: str            # master jetton
    amount: float          # в jetton-единицах
    amount_raw: int        # в on-chain units (с учётом decimals)
    lt: Optional[int] = None
    source: str = "mock"   # mock | ton-core | tonweb
    created_at: float = 0.0


class TonPayout:
    """Jetton-перевод ЦАРЬ через TON.

    Mock-режим (по умолчанию): возвращает фейковый tx_hash.
    Боевой: через ton-core (async) или tonweb (sync).
    """

    def __init__(
        self,
        *,
        mnemonic: Optional[str] = None,
        jetton_master: str = TSAR_MASTER,
        treasury: str = TSAR_TREASURY_ADDRESS,
        decimals: int = TSAR_DECIMALS,
        rpc_url: str = "https://toncenter.com/api/v2/jsonRPC",
        api_key: Optional[str] = None,
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
        self._wallet_address: Optional[str] = None

    @property
    def is_configured(self) -> bool:
        return bool(self.mnemonic)

    async def get_wallet_address(self) -> str:
        """Возвращает адрес нашего кошелька (деривация из мнемоники)."""
        if self._wallet_address:
            return self._wallet_address
        if not self.is_configured:
            # Mock-адрес для тестов
            self._wallet_address = "EQDrLq-X6jKZ3D4MjBQK2c6dAR3wK1D7c7-3X-4Y-5Z-6A-7B"
            return self._wallet_address
        try:
            from ton_core import Wallet  # type: ignore
            w = Wallet.from_mnemonic(mnemonics=self.mnemonic.split())
            self._wallet_address = w.address.to_str()
            return self._wallet_address
        except ImportError:
            logger.warning("ton-core не установлен — fallback на mock-адрес")
            self._wallet_address = "EQDrLq-X6jKZ3D4MjBQK2c6dAR3wK1D7c7-3X-4Y-5Z-6A-7B"
            return self._wallet_address

    async def send_tsar(self, *, amount: float) -> TonTx:
        """Отправляет amount ЦАРЬ на кошелёк обменника.

        Args:
            amount: количество ЦАРЬ (например 1.2)

        Returns:
            TonTx с tx_hash, lt, etc.

        Raises:
            TonPayoutError: при ошибке перевода
        """
        if amount <= 0:
            raise TonPayoutError(f"amount must be positive, got {amount}")

        amount_raw = int(amount * (10 ** self.decimals))
        src = await self.get_wallet_address()
        now = time.time()

        if not self.is_configured:
            # === MOCK-режим ===
            tx_hash = f"mock_{uuid.uuid4().hex}"
            logger.info("TON mock payout: %.4f ЦАРЬ (%d raw) %s → %s", amount, amount_raw, src, self.treasury)
            return TonTx(
                tx_hash=tx_hash,
                src=src,
                dst=self.treasury,
                jetton=self.jetton_master,
                amount=amount,
                amount_raw=amount_raw,
                lt=int(now * 1e6),
                source="mock",
                created_at=now,
            )

        # === БОЕВОЙ РЕЖИМ через ton-core ===
        try:
            from ton_core import Wallet, Address  # type: ignore
            w = Wallet.from_mnemonic(mnemonics=self.mnemonic.split())
            jetton_wallet = w.create_wallet(
                jetton_master=Address(self.jetton_master),
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
                jetton=self.jetton_master,
                amount=amount,
                amount_raw=amount_raw,
                lt=getattr(tx, "lt", None),
                source="ton-core",
                created_at=now,
            )
        except ImportError:
            raise TonPayoutError("ton-core не установлен. pip install ton-core")
        except Exception as e:
            raise TonPayoutError(f"TON transfer failed: {e}") from e

    async def close(self) -> None:
        """Закрыть ресурсы (для совместимости с другими клиентами)."""
        pass
