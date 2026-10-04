"""Telegram-бот обменника ЦАРЬ -> RUB.

Поддерживает 3 серии ЦАРЬ через inline-кнопки:
  - BAAL_RA (основной, АНО ЦЕНТР БЛИЗНЕЦЫ)
  - GEMINI (Царь Гемини)
  - CROWN  (Царь с коронкой)
"""
from __future__ import annotations
import asyncio
import logging
import os
import sys
import time
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

from api.payouts.config import TSAR_MASTER
from api.payouts.price_feed import PriceFeed
from api.payouts.sbp_adapter import SBPBridge
from api.payouts.site_meta import EMITTER_SITE_URL
from api.payouts.tokens import TOKENS, DEFAULT_TOKEN, get_token, list_tokens
from integrations.sbp.tinkoff import TinkoffSBPClient

logger = logging.getLogger(__name__)
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError("TELEGRAM_BOT_TOKEN не задан")


class WithdrawFSM(StatesGroup):
    waiting_amount = State()
    waiting_address = State()


router = Router(name="main")

_user_token: dict[int, str] = {}
_feed_cache: dict[str, PriceFeed] = {}
_bridge: SBPBridge | None = None


def get_feed(token_code: str) -> PriceFeed:
    if token_code not in _feed_cache:
        tok = get_token(token_code)
        _feed_cache[token_code] = PriceFeed(token_master=tok.master, token_pool=tok.pool)
    return _feed_cache[token_code]


def get_bridge() -> SBPBridge:
    global _bridge
    if _bridge is None:
        tk = os.environ.get("TINKOFF_TERMINAL_KEY")
        pw = os.environ.get("TINKOFF_PASSWORD")
        tinkoff = TinkoffSBPClient(terminal_key=tk, password=pw) if tk and pw else None
        _bridge = SBPBridge(tinkoff=tinkoff)
    return _bridge


def current_token(user_id: int):
    code = _user_token.get(user_id, DEFAULT_TOKEN)
    return get_token(code), code


def tokens_keyboard(user_id: int) -> InlineKeyboardMarkup:
    """Кнопки для выбора токена + действия."""
    cur_code = _user_token.get(user_id, DEFAULT_TOKEN)
    rows = []
    for t in list_tokens():
        mark = "✅ " if t.code == cur_code else "  "
        rows.append([InlineKeyboardButton(
            text=f"{mark}{t.emoji} {t.symbol} — {t.name}",
            callback_data=f"tok:{t.code}",
        )])
    rows.append([
        InlineKeyboardButton(text="💱 Курс", callback_data="act:quote"),
        InlineKeyboardButton(text="💸 Вывести", callback_data="act:withdraw"),
    ])
    rows.append([InlineKeyboardButton(text="📖 Справка", callback_data="act:help")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def action_keyboard(token_code: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💱 Курс", callback_data=f"act:quote:{token_code}")],
        [InlineKeyboardButton(text="💸 Вывести", callback_data=f"act:withdraw:{token_code}")],
        [InlineKeyboardButton(text="🔙 Назад к выбору токена", callback_data="act:back")],
    ])


@router.message(CommandStart())
async def cmd_start(message: Message):
    bridge = get_bridge()
    sbp_ready = bridge.tinkoff is not None
    tok, _ = current_token(message.from_user.id if message.from_user else 0)
    await message.answer(
        f"👑 <b>ЦАРЬ → RUB</b>\n\n"
        f"Текущий токен: <b>{tok.symbol}</b>\n"
        f"SBP: {'✅ подключены' if sbp_ready else '⚠️ ручной режим'}\n\n"
        f"<b>Выбери серию ЦАРЬ для обмена:</b>",
        parse_mode=ParseMode.HTML,
        reply_markup=tokens_keyboard(message.from_user.id if message.from_user else 0),
    )


@router.message(Command("tokens"))
async def cmd_tokens(message: Message):
    await message.answer(
        "👑 <b>Все серии ЦАРЬ</b>\n\nВыбери нужную:",
        parse_mode=ParseMode.HTML,
        reply_markup=tokens_keyboard(message.from_user.id if message.from_user else 0),
    )


@router.message(Command("quote"))
async def cmd_quote(message: Message):
    tok, code = current_token(message.from_user.id if message.from_user else 0)
    feed = get_feed(code)
    q = await feed.get_rate()
    await message.answer(
        f"💱 <b>Курс {tok.symbol}</b>\n\n"
        f"1 токен ≈ <b>{q.rate:.2f} ₽</b>\n"
        f"Источник: {q.source}\n"
        f"Возраст: {int(q.age_sec)} сек\n\n"
        f"<i>Минималка: 250 000 токенов</i>",
        parse_mode=ParseMode.HTML,
        reply_markup=action_keyboard(code),
    )


@router.message(Command("withdraw"))
async def cmd_withdraw(message: Message, state: FSMContext):
    tok, _ = current_token(message.from_user.id if message.from_user else 0)
    await state.set_state(WithdrawFSM.waiting_amount)
    await message.answer(
        f"💸 Сколько <b>{tok.symbol}</b> обменять?\n"
        f"Минимум: 250 000\n\n"
        f"Сменить токен: /tokens",
        parse_mode=ParseMode.HTML,
    )


@router.message(Command("help"))
async def cmd_help(message: Message):
    await message.answer(
        "📖 <b>Справка</b>\n\n"
        "<b>Команды:</b>\n"
        "/quote — курс\n/tokens — все серии (с кнопками)\n"
        "/withdraw — вывод\n/help — справка\n\n"
        "<b>Лимиты:</b>\n"
        "• До 5 000 ₽ — без KYC\n"
        "• 5 000–50 000 ₽ — паспорт\n"
        "• Свыше 50 000 ₽ — полный KYC\n\n"
        "<b>Поддержка:</b> @BAAL_NIK_2505lis\n\n"
        f"<b>Эмитент:</b> {EMITTER_SITE_URL}\n"
        f"<b>Мастер (основной):</b> <code>{TSAR_MASTER}</code>",
        parse_mode=ParseMode.HTML,
        reply_markup=tokens_keyboard(message.from_user.id if message.from_user else 0),
    )


@router.callback_query(F.data.startswith("tok:"))
async def on_token_pick(cb: CallbackQuery):
    code = cb.data.split(":", 1)[1].upper()
    if code not in TOKENS:
        await cb.answer("❌ Неизвестный токен")
        return
    uid = cb.from_user.id
    _user_token[uid] = code
    tok = get_token(code)
    await cb.answer(f"Токен: {tok.symbol}")
    await cb.message.answer(
        f"✅ Токен: <b>{tok.symbol}</b> ({tok.code})\n"
        f"Мастер: <code>{tok.master}</code>\n\n"
        f"Что дальше?",
        parse_mode=ParseMode.HTML,
        reply_markup=action_keyboard(code),
    )


@router.callback_query(F.data.startswith("act:quote"))
async def on_quote_btn(cb: CallbackQuery):
    parts = cb.data.split(":")
    code = parts[2] if len(parts) > 2 else _user_token.get(cb.from_user.id, DEFAULT_TOKEN)
    if code not in TOKENS:
        code = DEFAULT_TOKEN
    tok = get_token(code)
    feed = get_feed(code)
    q = await feed.get_rate()
    await cb.answer()
    await cb.message.answer(
        f"💱 <b>{tok.symbol}</b>\n"
        f"1 ≈ <b>{q.rate:.2f} ₽</b>\n"
        f"Источник: {q.source}",
        parse_mode=ParseMode.HTML,
        reply_markup=action_keyboard(code),
    )


@router.callback_query(F.data.startswith("act:withdraw"))
async def on_withdraw_btn(cb: CallbackQuery, state: FSMContext):
    parts = cb.data.split(":")
    code = parts[2] if len(parts) > 2 else _user_token.get(cb.from_user.id, DEFAULT_TOKEN)
    if code not in TOKENS:
        code = DEFAULT_TOKEN
    tok = get_token(code)
    _user_token[cb.from_user.id] = code
    await state.set_state(WithdrawFSM.waiting_amount)
    await cb.answer()
    await cb.message.answer(
        f"💸 Сколько <b>{tok.symbol}</b> обменять?\nМинимум: 250 000",
        parse_mode=ParseMode.HTML,
    )


@router.callback_query(F.data == "act:back")
async def on_back(cb: CallbackQuery):
    await cb.answer()
    await cb.message.answer(
        "👑 Выбери токен:",
        parse_mode=ParseMode.HTML,
        reply_markup=tokens_keyboard(cb.from_user.id),
    )


@router.callback_query(F.data == "act:help")
async def on_help_btn(cb: CallbackQuery):
    await cb.answer()
    await cb.message.answer(
        "📖 <b>Справка</b>\n\n"
        "Команды: /quote /tokens /withdraw /help\n"
        f"Эмитент: {EMITTER_SITE_URL}\n"
        "Поддержка: @BAAL_NIK_2505lis",
        parse_mode=ParseMode.HTML,
    )


@router.message(WithdrawFSM.waiting_amount)
async def fsm_amount(message: Message, state: FSMContext):
    tok, code = current_token(message.from_user.id if message.from_user else 0)
    text = (message.text or "").replace(" ", "").replace(",", ".")
    try:
        amount = float(text)
    except ValueError:
        await message.answer("❌ Введи число")
        return
    if amount < 250_000:
        await message.answer("❌ Минимум 250 000")
        return
    feed = get_feed(code)
    q = await feed.get_rate()
    rub = amount * q.rate
    await state.update_data(amount=amount, rate=q.rate, rub=rub, token_code=code)
    await state.set_state(WithdrawFSM.waiting_address)
    await message.answer(
        f"✅ {amount:,.0f} {tok.symbol} = {rub:,.2f} ₽\n\n"
        f"Куда отправить рубли?\nТелефон (+7...) или карта (2200...)",
        parse_mode=ParseMode.HTML,
    )


@router.message(WithdrawFSM.waiting_address)
async def fsm_address(message: Message, state: FSMContext):
    recipient = (message.text or "").strip()
    data = await state.get_data()
    amount = data.get("amount", 0)
    rub = data.get("rub", 0)
    code = data.get("token_code", DEFAULT_TOKEN)
    tok = get_token(code)
    user_id = message.from_user.id if message.from_user else 0
    order_id = f"tsar-{code.lower()}-{int(time.time())}-{user_id}"
    bridge = get_bridge()
    result = await bridge.payout_rub(
        amount_rub=rub,
        recipient=recipient,
        order_id=order_id,
        description=f"{tok.symbol} → RUB: {amount:,.0f}",
    )
    await state.clear()
    if result.success:
        await message.answer(
            f"✅ <b>Заявка #{order_id}</b>\n\n"
            f"• Токен: {tok.symbol}\n"
            f"• Сумма: {amount:,.0f}\n"
            f"• К выплате: {rub:,.2f} ₽\n"
            f"• Получатель: {recipient}\n"
            f"• Статус: {result.status}",
            parse_mode=ParseMode.HTML,
            reply_markup=tokens_keyboard(user_id),
        )
    else:
        await message.answer(
            f"⏳ <b>Заявка #{order_id} (manual)</b>\n\n"
            f"• Токен: {tok.symbol}\n"
            f"• Сумма: {amount:,.0f}\n"
            f"• К выплате: {rub:,.2f} ₽\n"
            f"• Получатель: {recipient}\n\n"
            f"<i>СБП не подключён. Причина: {result.error}</i>",
            parse_mode=ParseMode.HTML,
            reply_markup=tokens_keyboard(user_id),
        )


async def main():
    logging.basicConfig(level=logging.INFO)
    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)
    logger.info("Bot polling started — tokens: %s", ", ".join(TOKENS.keys()))
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())