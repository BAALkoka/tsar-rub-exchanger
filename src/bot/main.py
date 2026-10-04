"""Точка входа Telegram-бота на aiogram v3."""
from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

from src.bot.config import BotConfig
from src.bot.handlers import start, balance, withdraw
from src.bot.middlewares import LoggingMiddleware

logger = logging.getLogger(__name__)


async def main() -> None:
    cfg = BotConfig.from_env()

    bot = Bot(
        token=cfg.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher()
    dp.message.middleware(LoggingMiddleware())

    dp.include_routers(
        start.router,
        balance.router,
        withdraw.router,
    )

    logger.info("Bot starting… polling")
    await dp.start_polling(bot)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())