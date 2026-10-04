"""Клиент СБП.

Заглушка с архитектурой для подключения реального банка-партнёра.
Для MVP можно использовать:
  - Альфа-Бизнес API
  - Тинькофф API
  - ЮMoney / ЮKassa
  - Tochka
  - Robomarket / A3V (агрегаторы)

Интерфейс спроектирован так, чтобы подмена провайдера не меняла код сервиса.
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


class SbpError(Exception):
    """Ошибка СБП."""


@dataclass
class SbpConfig:
    """Конфиг подключающего банка."""

    merchant_id: str
    api_key: str
    base_url: str = "https://api.tochka.ru/v1"  # пример
    timeout_sec: float = 5.0
    max_retries: int = 3


class SbpClient:
    """Клиент СБП с ретраями и идемпотентностью."""

    def __init__(self, config: SbpConfig):
        self.config = config
        self._seen_ids: set[str] = set()  # простейший анти-дубль

    async def payout(
        self,
        *,
        amount_rub: float,
        phone: str,
        idempotency_key: str,
        extra: Optional[dict] = None,
    ) -> str:
        """Отправить выплату по номеру телефона.

        Возвращает external_id операции у банка.
        """
        if idempotency_key in self._seen_ids:
            logger.info("SBP duplicate payout id=%s — skip", idempotency_key)
            return idempotency_key

        self._seen_ids.add(idempotency_key)

        last_exc: Optional[Exception] = None
        for attempt in range(1, self.config.max_retries + 1):
            try:
                # ---- реальный запрос ----
                # POST {base_url}/sbp/payouts
                # headers: Authorization, Idempotency-Key
                # body: {amount, phone, merchant_id}
                # response: {external_id, status}
                #
                # Для MVP — заглушка. Замените на httpx.AsyncClient().
                external_id = await self._mock_send(amount_rub, phone)
                logger.info(
                    "SBP payout OK amount=%.2f phone=%s ext_id=%s attempt=%d",
                    amount_rub, phone, external_id, attempt,
                )
                return external_id
            except (TimeoutError, ConnectionError) as e:
                last_exc = e
                logger.warning("SBP attempt %d failed: %s", attempt, e)
                await asyncio.sleep(0.5 * attempt)
            except SbpError:
                raise

        raise SbpError(f"SBP payout failed after {self.config.max_retries} retries: {last_exc}")

    async def _mock_send(self, amount_rub: float, phone: str) -> str:
        """Заглушка вместо реального API. Вернёт фейковый external_id."""
        await asyncio.sleep(0.05)  # имитация сетевого запроса
        return f"sbp_mock_{phone[-4:]}_{int(amount_rub * 100)}"