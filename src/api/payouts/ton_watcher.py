"""TON watcher: автоопределение токена по входящему переводу.

Отслеживает входящие jetton-транзакции на кошельке казначейства.
Когда кто-то переводит ЦАРЬ (любой из 3 серий) на кошелёк
USDT_TREASURY_ADDRESS — watcher определяет, КАКОЙ ИМЕННО токен был прислан
(по jetton-master) и уведомляет бота + привязывает к заявке на вывод.
"""
from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass
from typing import Awaitable, Callable, Optional

import httpx

from .config import USDT_TREASURY_ADDRESS
from .tokens import find_by_master, TokenMeta, short_master

logger = logging.getLogger(__name__)


TonapiBase = "https://tonapi.io/v2"


@dataclass
class IncomingTransfer:
    """Входящий jetton-перевод на казначейство."""

    tx_hash: str
    jetton_master: str
    amount: float          # в человеческих единицах (с учётом decimals)
    raw_amount: int        # в on-chain единицах
    decimals: int
    sender: str
    timestamp: int
    token: Optional[TokenMeta] = None   # резолвится автоматически


class TonWatcher:
    """Polling-сервис входящих переводов на TON-кошелёк казначейства.

    Использует бесплатный TonAPI (https://tonapi.io/v2) для просмотра
    jetton-истории кошелька. Каждые N секунд опрашивает историю транзакций
    и эмитит событие для каждого нового входящего перевода.
    """

    def __init__(
        self,
        wallet_address: Optional[str] = None,
        *,
        poll_interval_sec: float = 15.0,
        tonapi_token: Optional[str] = None,
        on_transfer: Optional[Callable[[IncomingTransfer], Awaitable[None]]] = None,
    ):
        self.wallet = wallet_address or USDT_TREASURY_ADDRESS
        self.poll_interval = poll_interval_sec
        self.tonapi_token = tonapi_token or os.environ.get("TONAPI_TOKEN")
        self.on_transfer = on_transfer
        self._client: Optional[httpx.AsyncClient] = None
        self._seen_hashes: set[str] = set()
        self._task: Optional[asyncio.Task] = None
        self._stop = asyncio.Event()

    def _headers(self) -> dict:
        h = {"accept": "application/json"}
        if self.tonapi_token:
            h["Authorization"] = f"Bearer {self.tonapi_token}"
        return h

    async def _fetch_recent_events(self, limit: int = 20) -> list[IncomingTransfer]:
        """Получает последние jetton-события на кошельке."""
        if not self._client:
            self._client = httpx.AsyncClient(timeout=10.0)
        url = f"{TonapiBase}/accounts/{self.wallet}/events"
        params = {"limit": limit}
        try:
            r = await self._client.get(url, headers=self._headers(), params=params)
            if r.status_code == 429:
                logger.warning("TonAPI rate limit")
                return []
            if r.status_code != 200:
                logger.warning("TonAPI HTTP %s: %s", r.status_code, r.text[:200])
                return []
            data = r.json()
        except httpx.HTTPError as e:
            logger.warning("TonAPI network error: %s", e)
            return []

        transfers: list[IncomingTransfer] = []
        for ev in data.get("events", []):
            ts = int(ev.get("timestamp", 0))
            for action in ev.get("actions", []):
                # Только входящие jetton-переводы
                if action.get("type") != "JettonTransfer":
                    continue
                jetton = action.get("JettonTransfer", {})
                recipients = jetton.get("recipients", [])
                # Проверяем, что наш кошелёк — получатель
                if not any(rec.get("address") == self.wallet for rec in recipients):
                    continue
                amount_raw = int(jetton.get("amount", "0"))
                jetton_info = jetton.get("jetton", {}) or {}
                master = jetton_info.get("address", "") or ""
                decimals = int(jetton_info.get("decimals", "9") or 9)
                amount = amount_raw / (10 ** decimals)
                sender = (jetton.get("sender") or {}).get("address", "")
                tx_hash = str(ev.get("event_id", ""))
                transfers.append(IncomingTransfer(
                    tx_hash=tx_hash,
                    jetton_master=master,
                    amount=amount,
                    raw_amount=amount_raw,
                    decimals=decimals,
                    sender=sender,
                    timestamp=ts,
                    token=find_by_master(master),
                ))
        return transfers

    async def _poll_loop(self) -> int:
        """Основной цикл: опрашивает кошелёк, эмитит события для новых переводов."""
        logger.info("TonWatcher started for %s", short_master(self.wallet))
        while not self._stop.is_set():
            try:
                transfers = await self._fetch_recent_events()
                for t in transfers:
                    if t.tx_hash in self._seen_hashes:
                        continue
                    self._seen_hashes.add(t.tx_hash)
                    tag = "✓" if t.token else "?"
                    logger.info(
                        "TX %s: %s master=%s amount=%.4f -> token=%s",
                        tag, tag, short_master(t.jetton_master), t.amount,
                        t.token.name if t.token else "UNKNOWN",
                    )
                    if self.on_transfer:
                        try:
                            await self.on_transfer(t)
                        except Exception as e:
                            logger.exception("on_transfer handler failed: %s", e)
            except Exception as e:
                logger.exception("TonWatcher tick failed: %s", e)
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=self.poll_interval)
            except asyncio.TimeoutError:
                pass
        return 0

    def start(self) -> asyncio.Task:
        if self._task and not self._task.done():
            return self._task
        self._stop.clear()
        self._task = asyncio.create_task(self._poll_loop())
        return self._task

    async def stop(self) -> None:
        self._stop.set()
        if self._task:
            try:
                await self._task
            except Exception:
                pass
        if self._client:
            await self._client.aclose()


def detect_token_from_event(event: dict) -> Optional[TokenMeta]:
    """Утилита: найти токен по событию от webhook / ручного вызова."""
    for action in event.get("actions", []):
        if action.get("type") != "JettonTransfer":
            continue
        jetton = action.get("JettonTransfer", {})
        master = (jetton.get("jetton") or {}).get("address", "")
        t = find_by_master(master)
        if t:
            return t
    return None