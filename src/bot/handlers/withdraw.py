"""/withdraw — FSM для вывода ЦАРЬ → RUB → карта."""
from __future__ import annotations

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup

router = Router(name="withdraw")


class WithdrawFSM(StatesGroup):
    amount = State()
    recipient = State()
    confirm = State()


@router.message(Command("withdraw"))
async def cmd_withdraw(message: Message, state: FSMContext) -> None:
    await state.set_state(WithdrawFSM.amount)
    await message.answer(
        "💸 Сколько <b>ЦАРЬ</b> вывести?\n"
        "Минимум — 100 ЦАРЬ (≈ 100 ₽).\n"
        "До 5 000 ₽ — без KYC, мгновенно.",
    )


@router.message(WithdrawFSM.amount)
async def process_amount(message: Message, state: FSMContext) -> None:
    raw = (message.text or "").strip().replace(" ", "")
    if not raw.isdigit():
        await message.answer("Введи целое число без точек и запятых.")
        return
    n = int(raw)
    if n < 100 or n > 1_000_000:
        await message.answer("Сумма должна быть от 100 до 1 000 000 ЦАРЬ.")
        return
    await state.update_data(amount=n, rate_rub=1.0)
    await state.set_state(WithdrawFSM.recipient)
    await message.answer(
        f"💳 Куда отправить <b>{n * 1.0:.0f} ₽</b>?\n"
        "Пришли номер телефона (для СБП) или «карта: 2200…»",
    )


@router.message(WithdrawFSM.recipient)
async def process_recipient(message: Message, state: FSMContext) -> None:
    recipient = (message.text or "").strip()
    data = await state.get_data()
    n = data["amount"]
    rub = n * data["rate_rub"]

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Подтвердить", callback_data="ok")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")],
    ])
    await state.set_state(WithdrawFSM.confirm)
    await state.update_data(recipient=recipient)
    await message.answer(
        f"📋 Подтверди:\n"
        f"• Отдаёшь: <b>{n} ЦАРЬ</b>\n"
        f"• Получаешь: <b>{rub:.0f} ₽</b>\n"
        f"• Куда: <code>{recipient}</code>\n"
        f"• Курс: 1 ЦАРЬ = 1 ₽ (черновой)",
        reply_markup=kb,
    )


@router.callback_query(WithdrawFSM.confirm, F.data == "ok")
async def confirm_ok(call: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    # TODO: POST /v1/payouts
    await call.message.answer(
        f"✅ Заявка создана. Скоро пришлю статус.\n"
        f"ID: <code>{data}</code>"
    )
    await state.clear()


@router.callback_query(WithdrawFSM.confirm, F.data == "cancel")
async def confirm_cancel(call: CallbackQuery, state: FSMContext) -> None:
    await call.message.answer("Отменено.")
    await state.clear()