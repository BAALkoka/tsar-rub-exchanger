"""Telegram-бот обменника ЦАРЬ -> RUB.

Поддерживает 3 серии ЦАРЬ через inline-кнопки:
  - BAAL_RA (основной)
  - GEMINI (Царь Гемини)
  - CROWN  (Царь с коронкой)
"""
from __future__ import annotations
import asyncio
import logging
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from aiogram import Bot, Dispatcher, Router, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    CallbackQuery,
)

from api.payouts.tokens import TOKENS, DEFAULT_TOKEN, get_token, list_tokens
from api.payouts.config import TSAR_MASTER, TSAR_PRIMARY_POOL, USD_RUB_FALLBACK
from api.payouts.price_feed import PriceFeed

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
SUPPORT_HANDLE = "@BAAL_NIK"

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("tsar.bot")

if not BOT_TOKEN:
    raise RuntimeError("TELEGRAM_BOT_TOKEN не задан")

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())
router = Router()

feed = PriceFeed(token_pool=TSAR_PRIMARY_POOL, manual_rate=1.0)


class WithdrawForm(StatesGroup):
    token_slug = State()
    amount = State()
    card = State()
    confirm = State()


def main_menu() -> InlineKeyboardMarkup:
    buttons = []
    for t in list_tokens():
        buttons.append([InlineKeyboardButton(text=f"{t.symbol} {t.name}", callback_data=f"token:{t.slug}")])
    buttons.append([InlineKeyboardButton(text="💱 Курс", callback_data="rate")])
    buttons.append([InlineKeyboardButton(text="📊 Балансы пулов", callback_data="pools")])
    buttons.append([InlineKeyboardButton(text="🆘 Поддержка", callback_data="support")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


@router.message(CommandStart())
async def cmd_start(message: Message):
    await message.answer(
        "👑 <b>ЦАРЬ Обменник</b>\n\n"
        "Обмен токенов ЦАРЬ → RUB → вывод на карту.\n\n"
        "Выбери токен:",
        reply_markup=main_menu(),
    )


@router.message(Command("help"))
async def cmd_help(message: Message):
    await message.answer(
        "<b>Помощь</b>\n\n"
        "/start — главное меню\n"
        "/rate — текущий курс\n"
        "/withdraw — вывод средств\n"
        "/help — эта справка\n\n"
        f"<b>Поддержка:</b> {SUPPORT_HANDLE}\n\n"
        "<b>Минимальная сумма:</b> 250 000 ЦАРЬ\n"
        "<b>Комиссия:</b> 0.25%"
    )


@router.message(Command("rate"))
async def cmd_rate(message: Message):
    try:
        q = await feed.quote(1_000_000)
        if q.ok:
            await message.answer(
                f"<b>Курс ЦАРЬ</b>\n\n"
                f"1 000 000 ЦАРЬ = {q.rub_amount:.2f} ₽\n"
                f"1 ЦАРЬ ≈ {q.tsar_price_usd*100:.6f} ¢\n"
                f"Источник: {q.source}\n"
                f"Курс USD: {q.rate_used:.2f} ₽"
            )
        else:
            await message.answer(f"❌ Ошибка получения курса: {q.error}")
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")


@router.message(Command("withdraw"))
async def cmd_withdraw(message: Message, state: FSMContext):
    await state.set_state(WithdrawForm.token_slug)
    await message.answer("Выбери токен для вывода:", reply_markup=main_menu())


@router.callback_query(F.data.startswith("token:"))
async def on_token_select(callback: CallbackQuery, state: FSMContext):
    slug = callback.data.split(":", 1)[1]
    token = get_token(slug)
    if not token:
        await callback.message.answer("❌ Токен не найден")
        return
    await state.update_data(token_slug=slug)
    await state.set_state(WithdrawForm.amount)
    await callback.message.edit_text(
        f"Выбран: {token.symbol} {token.name}\n\n"
        f"Минимальная сумма: {token.min_tsar:,} ЦАРЬ\n\n"
        "Введи количество ЦАРЬ для обмена:"
    )
    await callback.answer()


@router.callback_query(F.data == "rate")
async def on_rate(callback: CallbackQuery):
    try:
        q = await feed.quote(1_000_000)
        if q.ok:
            await callback.message.edit_text(
                f"<b>Курс ЦАРЬ</b>\n\n"
                f"1 000 000 ЦАРЬ = {q.rub_amount:.2f} ₽\n"
                f"1 ЦАРЬ ≈ {q.tsar_price_usd*100:.6f} ¢\n"
                f"Источник: {q.source}\n"
                f"Курс USD: {q.rate_used:.2f} ₽",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="◀ Назад", callback_data="back")]])
            )
        else:
            await callback.message.edit_text(f"❌ Ошибка: {q.error}")
    except Exception as e:
        await callback.message.edit_text(f"❌ Ошибка: {e}")
    await callback.answer()


@router.callback_query(F.data == "pools")
async def on_pools(callback: CallbackQuery):
    await callback.message.edit_text(
        "<b>Балансы пулов</b>\n\n"
        "Данные загружаются из DeDust...\n\n"
        "<i>Функция в разработке</i>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="◀ Назад", callback_data="back")]])
    )
    await callback.answer()


@router.callback_query(F.data == "support")
async def on_support(callback: CallbackQuery):
    await callback.message.edit_text(
        f"<b>Поддержка:</b> {SUPPORT_HANDLE}\n\n"
        "По всем вопросам пиши @BAAL_NIK",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="◀ Назад", callback_data="back")]])
    )
    await callback.answer()


@router.callback_query(F.data == "back")
async def on_back(callback: CallbackQuery):
    await callback.message.edit_text(
        "👑 <b>ЦАРЬ Обменник</b>\n\n"
        "Выбери токен:",
        reply_markup=main_menu()
    )
    await callback.answer()


async def main():
    dp.include_router(router)
    logger.info("Bot starting...")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot, skip_updates=True)


if __name__ == "__main__":
    asyncio.run(main())