"""Telegram-бот обменника ЦАРЬ → RUB с СБП-интеграцией через Тинькофф.

Запуск: TELEGRAM_BOT_TOKEN=... python -m bot.main
Опционально: TINKOFF_TERMINAL_KEY, TINKOFF_PASSWORD — для реальных выплат.
"""
from __future__ import annotations
import asyncio
import logging
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from aiogram import Bot, Dispatcher, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Message

from api.payouts.config import TSAR_MASTER, TSAR_PRIMARY_POOL
from api.payouts.price_feed import PriceFeed
from api.payouts.sbp_adapter import SBPBridge
from integrations.sbp.tinkoff import TinkoffSBPClient

logger = logging.getLogger(__name__)
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError("TELEGRAM_BOT_TOKEN не задан")


class WithdrawFSM(StatesGroup):
    waiting_amount = State()
    waiting_address = State()


router = Router(name="main")
_feed = None
_bridge = None


async def get_feed():
    global _feed
    if _feed is None:
        _feed = PriceFeed(token_master=TSAR_MASTER, token_pool=TSAR_PRIMARY_POOL)
    return _feed


def get_bridge():
    global _bridge
    if _bridge is None:
        tk = os.environ.get("TINKOFF_TERMINAL_KEY")
        pw = os.environ.get("TINKOFF_PASSWORD")
        tinkoff = TinkoffSBPClient(terminal_key=tk, password=pw) if tk and pw else None
        _bridge = SBPBridge(tinkoff=tinkoff)
    return _bridge


@router.message(CommandStart())
async def cmd_start(message: Message):
    bridge = get_bridge()
    sbp_ready = bridge.tinkoff is not None
    await message.answer(
        "👑 <b>ЦАРЬ → RUB</b>\n\n"
        f"SBP-выплаты: {'✅ подключены' if sbp_ready else '⚠️ ручной режим'}\n\n"
        "<b>Команды:</b>\n"
        "/quote — курс\n/withdraw — вывод\n/help — справка",
        parse_mode=ParseMode.HTML,
    )


@router.message(Command("quote"))
async def cmd_quote(message: Message):
    feed = await get_feed()
    q = await feed.get_rate()
    await message.answer(
        f"💱 <b>Курс</b>\n\n"
        f"1 ЦАРЬ ≈ <b>{q.rate:.2f} ₽</b>\n"
        f"Источник: {q.source}\n"
        f"Возраст: {int(q.age_sec)} сек\n\n"
        f"<i>Минималка: 250 000 ЦАРЬ</i>",
        parse_mode=ParseMode.HTML,
    )


@router.message(Command("withdraw"))
async def cmd_withdraw(message: Message, state: FSMContext):
    await state.set_state(WithdrawFSM.waiting_amount)
    await message.answer(
        "💸 Сколько ЦАРЬ хотите обменять?\nМинимум: 250 000",
        parse_mode=ParseMode.HTML,
    )


@router.message(WithdrawFSM.waiting_amount)
async def fsm_amount(message: Message, state: FSMContext):
    text = (message.text or "").replace(" ", "").replace(",", ".")
    try:
        amount = float(text)
    except ValueError:
        await message.answer("❌ Введи число")
        return
    if amount < 250_000:
        await message.answer("❌ Минимум 250 000 ЦАРЬ")
        return
    feed = await get_feed()
    q = await feed.get_rate()
    rub = amount * q.rate
    await state.update_data(amount=amount, rate=q.rate, rub=rub)
    await state.set_state(WithdrawFSM.waiting_address)
    await message.answer(
        f"✅ {amount:,.0f} ЦАРЬ = {rub:,.2f} ₽\n\n"
        f"Куда отправить рубли?\nТелефон (+7...) или карта (2200...)",
        parse_mode=ParseMode.HTML,
    )


@router.message(WithdrawFSM.waiting_address)
async def fsm_address(message: Message, state: FSMContext):
    recipient = (message.text or "").strip()
    data = await state.get_data()
    amount = data.get("amount", 0)
    rub = data.get("rub", 0)
    user_id = message.from_user.id if message.from_user else 0
    order_id = f"tsar-{int(time.time())}-{user_id}"
    bridge = get_bridge()
    result = await bridge.payout_rub(
        amount_rub=rub,
        recipient=recipient,
        order_id=order_id,
        description=f"ЦАРЬ → RUB: {amount:,.0f}",
    )
    await state.clear()
    if result.success:
        await message.answer(
            f"✅ <b>Заявка #{order_id}</b>\n\n"
            f"• Сумма: {amount:,.0f} ЦАРЬ\n"
            f"• К выплате: {rub:,.2f} ₽\n"
            f"• Получатель: {recipient}\n"
            f"• Статус: {result.status}\n\n"
            f"💳 СБП-выплата в обработке.",
            parse_mode=ParseMode.HTML,
        )
    else:
        await message.answer(
            f"⏳ <b>Заявка #{order_id} (manual)</b>\n\n"
            f"• Сумма: {amount:,.0f} ЦАРЬ\n"
            f"• К выплате: {rub:,.2f} ₽\n"
            f"• Получатель: {recipient}\n\n"
            f"<i>СБП не подключён. Менеджер свяжется.\n"
            f"Причина: {result.error}</i>",
            parse_mode=ParseMode.HTML,
        )


@router.message(Command("help"))
async def cmd_help(message: Message):
    await message.answer(
        "📖 <b>Справка</b>\n\n"
        "<b>Цена 1 ЦАРЬ:</b> ~83 ₽ (USDT/ЦАРЬ пул)\n\n"
        "<b>Лимиты:</b>\n"
        "• До 5 000 ₽ — без KYC\n"
        "• 5 000–50 000 ₽ — паспорт\n"
        "• Свыше 50 000 ₽ — полный KYC\n\n"
        "<b>Поддержка:</b> @BAAL_NIK_2505lis\n\n"
        f"<b>Мастер:</b> {TSAR_MASTER[:10]}…{TSAR_MASTER[-6:]}\n"
        f"<b>Пул:</b> {TSAR_PRIMARY_POOL[:10]}…{TSAR_PRIMARY_POOL[-6:]}",
        parse_mode=ParseMode.HTML,
    )


async def main():
    logging.basicConfig(level=logging.INFO)
    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)
    logger.info("Bot polling started")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())