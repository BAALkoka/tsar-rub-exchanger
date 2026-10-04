"""/quote — текущий курс ЦАРЬ."""
from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

router = Router(name="quote")


@router.message(Command("quote"))
async def cmd_quote(message: Message) -> None:
    # TODO: запрос в backend /v1/quote
    text = (
        "💱 <b>Текущий курс</b>\n\n"
        "1 ЦАРЬ ≈ 0.000004 ₽\n"
        "Источник: DeDust TON/ЦАРЬ пул\n\n"
        "Чтобы получить 1 ₽, нужно отправить ≈250 000 ЦАРЬ.\n"
        "Минималка обменника: 250 000 ЦАРЬ.\n\n"
        "Команда: /withdraw"
    )
    await message.answer(text)