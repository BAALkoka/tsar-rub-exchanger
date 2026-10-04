"""/start и приветствие."""
from __future__ import annotations

from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message

router = Router(name="start")


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    await message.answer(
        "👑 Привет! Это обменник <b>ЦАРЬ → RUB → карта</b>.\n\n"
        "Что умею:\n"
        "• /balance — показать баланс ЦАРЬ\n"
        "• /withdraw — вывести в рубли на карту\n"
        "• /help — список команд\n\n"
        "Сначала подключи TON-кошелёк.",
    )