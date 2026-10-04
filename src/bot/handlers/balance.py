"""/balance — показать баланс ЦАРЬ."""
from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

router = Router(name="balance")


@router.message(Command("balance"))
async def cmd_balance(message: Message) -> None:
    # TODO: запрос в backend /v1/wallet/{user_id}/balance
    await message.answer(
        "💰 Твой баланс: <b>0 ЦАРЬ</b>\n"
        "Курс: 1 ЦАРЬ ≈ 1 ₽ (черновой)\n\n"
        "Подключи кошелёк командой /connect",
    )