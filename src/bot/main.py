"""Telegram-бот обменника ЦАРЬ -> RUB.

Поддерживает 3 серии ЦАРЬ через inline-кнопки:
  - BAAL_RA (основной)
  - GEMINI (Царь Гемини)
  - CROWN  (Царь с коронкой)

Выплаты через P2P Market API (WalletBot).
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
from api.payouts.p2p import P2PClient
from api.payouts.service import PayoutService

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
p2p_client = P2PClient()
payout_service = PayoutService(p2p_client=p2p_client, price_feed=feed)


class WithdrawForm(StatesGroup):
    token_slug = State()
    amount = State()
    card = State()


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
        "Обмен токенов ЦАРЬ → RUB → вывод на карту.\n"
        "Выплаты через P2P Market.\n\n"
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
        "<b>Комиссия:</b> 0.25%\n"
        "<b>Выплата:</b> P2P (USDT → RUB на карту)"
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


@router.message(WithdrawForm.amount)
async def on_amount(message: Message, state: FSMContext):
    try:
        amount = float(message.text.replace(",", ".").replace(" ", ""))
    except ValueError:
        await message.answer("❌ Введи число, например 1000000")
        return
    if amount < 250_000:
        await message.answer("❌ Минимум 250 000 ЦАРЬ")
        return
    await state.update_data(amount=amount)
    await state.set_state(WithdrawForm.card)
    await message.answer(
        f"💳 <b>Сумма:</b> {amount:,.0f} ЦАРЬ\n\n"
        "Введи номер карты для получения RUB\n(только цифры, 16 знаков):"
    )


@router.message(WithdrawForm.card)
async def on_card(message: Message, state: FSMContext):
    card = message.text.strip().replace(" ", "")
    if not (card.isdigit() and len(card) in (16, 19, 20)):
        await message.answer("❌ Неверный формат. Введи 16 цифр номера карты")
        return
    data = await state.get_data()
    token_slug = data.get("token_slug")
    amount = data.get("amount")
    user_id = message.from_user.id
    try:
        from api.payouts.models import PayoutMethod
        result = await payout_service.payout(
            user_id=user_id,
            tsar_amount=amount,
            recipient=card,
            method=PayoutMethod.CARD_RU,
        )
        if result.ok:
            payout = result.payout
            ad = result.p2p_ad
            await message.answer(
                f"✅ <b>Заявка создана</b>\n\n"
                f"ID: {payout.id}\n"
                f"Сумма: {amount:,.0f} ЦАРЬ\n"
                f"Получишь: {payout.amount_rub:.2f} ₽\n"
                f"На карту: {card[:6]}****{card[-4:]}\n\n"
                f"🤝 <b>P2P-партнёр:</b> {ad.nickname if ad else '—'}\n"
                f"Курс: {ad.price if ad else 0:.2f} ₽/USDT\n\n"
                "Переведи ЦАРЬ на кошелёк казначейства (см. /help), "
                "после этого P2P-партнёр переведёт RUB на карту."
            )
        else:
            await message.answer(f"❌ Ошибка: {result.error}")
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")
    await state.clear()


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
    try:
        ads = await p2p_client.get_buy_ads(crypto="USDT", fiat="RUB", side="BUY", page_size=5)
        if not ads:
            text = "📊 <b>P2P-объявления (BUY USDT)</b>\n\nНет активных объявлений."
        else:
            lines = ["📊 <b>P2P-объявления (покупка USDT)</b>\n"]
            for a in ads[:5]:
                lines.append(
                    f"• <b>{a.nickname}</b> — {a.price:.2f} ₽/USDT\n"
                    f"  доступно: {a.available_usdt:,.0f} USDT\n"
                    f"  способы: {', '.join(a.payments[:3])}\n"
                )
            text = "\n".join(lines)
        await callback.message.edit_text(
            text,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="◀ Назад", callback_data="back")]])
        )
    except Exception as e:
        await callback.message.edit_text(
            f"❌ Ошибка P2P: {e}",
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