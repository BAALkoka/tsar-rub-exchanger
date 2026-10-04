"""Middleware для логирования и rate-limit."""
from __future__ import annotations

import logging
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import Message, TelegramObject

logger = logging.getLogger(__name__)


class LoggingMiddleware(BaseMiddleware):
    """Логирует входящие сообщения + измеряет latency."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        if isinstance(event, Message):
            logger.info(
                "msg from user=%s chat=%s text=%r",
                event.from_user.id if event.from_user else "?",
                event.chat.id,
                (event.text or "")[:120],
            )
        return await handler(event, data)