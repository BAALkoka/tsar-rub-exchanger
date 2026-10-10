"""Telegram-бот обменника ЦАРЬ → RUB.

3 серии ЦАРЬ, у каждого свой DeDust-пул. Все 3 продаются через P2P и СБП.

Версия: 2026-10-09-008 — reply-клавиатура 3 ряда (3×2 + 1), inline site/game, F.text handlers.
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
    ReplyKeyboardMarkup,
    KeyboardButton,
    WebAppInfo,
    Message,
    CallbackQuery,
)

from api.payouts.tokens import (
    TOKENS,
    get_token,
    list_tokens,
    short_master,
)
from api.payouts.config import (
    USD_RUB_FALLBACK,
    SUPPORT_HANDLE,
    USDT_TREASURY_ADDRESS,
)
from api.payouts.price_feed import PriceFeed
from api.payouts.p2p import P2PClient
from api.payouts.service import PayoutService
from api.payouts.models import PayoutMethod

BOT_VERSION = "2026-10-09-008"
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("tsar.bot")

if not BOT_TOKEN:
    raise RuntimeError("TELEGRAM_BOT_TOKEN is required")

SITE_URL = os.getenv("SITE_URL", "https://tsar-rub-lt87ahb9.agent.mira.tg/").strip()
GAME_URL = os.getenv("GAME_URL", "https://tsar-game-lt87ahb9.agent.mira.tg/").strip()

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())
router = Router()

# === Ценовые фиды (DeDust-пулы) ===
feeds: dict[str, PriceFeed] = {
    t.slug: PriceFeed(token_master=t.master, token_pool=t.pool, pool_label=t.pool_label, manual_rate=1.0)
    for t in list_tokens()
}
p2p_client = P2PClient()
ADMIN_CHAT_ID = int(os.getenv("ADMIN_CHAT_ID", "0") or "0")

logger.info("BOT VERSION %s 🎙 feeds: %s, p2p configured: %s",
            BOT_VERSION, list(feeds.keys()), p2p_client.is_configured)
assert hasattr(PriceFeed, 'quote'), "PriceFeed missing quote()"
for slug, f in feeds.items():
    assert hasattr(f, 'quote'), f"PriceFeed for {slug} missing quote()"
logger.info("Sanity check passed: all PriceFeed instances have quote() method")


def _service_for(slug: str) -> PayoutService:
    return PayoutService(p2p_client=p2p_client, price_feed=feeds[slug])


class WithdrawForm(StatesGroup):
    token_slug = State()
    amount = State()
    card = State()
    phone = State()


def token_button(t) -> InlineKeyboardButton:
    return InlineKeyboardButton(
        text=f"{t.emoji} {t.symbol} {t.name}",
        callback_data=f"token:{t.slug}",
    )


def reply_main_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="💰 Курс"), KeyboardButton(text="💸 Продать")],
            [KeyboardButton(text="📊 Калькулятор"), KeyboardButton(text="📜 История")],
            [KeyboardButton(text="🌐 Сайт"), KeyboardButton(text="🎮 Игра")],
            [KeyboardButton(text="♻️ /start")],
        ],
        resize_keyboard=True,
        input_field_placeholder="Выбери действие или введи /start",
    )


def site_game_inline() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🌐 Открыть сайт", url=SITE_URL),
            InlineKeyboardButton(text="🎮 Играть", web_app=WebAppInfo(url=GAME_URL)),
        ],
        [
            InlineKeyboardButton(text="💬 Канал", url="https://t.me/BAAL_NIK"),
            InlineKeyboardButton(text="💬 Чат", url="https://t.me/BAAL_NIK_chat"),
        ],
    ])


def main_menu() -> InlineKeyboardMarkup:
    """Главное меню: 3 царя + P2P/SBP и адреса."""
    buttons = [[token_button(t)] for t in list_tokens()]
    buttons.append([InlineKeyboardButton(text="🌐 P2P предложения", callback_data="pools")])
    buttons.append([InlineKeyboardButton(text="🎮 Сайт", url=SITE_URL)])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


@router.message(CommandStart())
@router.message(F.text == "♻️ /start")
async def cmd_start(message: Message):
    text = (
        f"👑 <b>ЦАРЬ Обменник</b> <i>v{BOT_VERSION}</i>\n\n"
        "Продай любой из 3 царей за RUB.\n"
        "Способы получения: <b>P2P</b> (карта) или <b>СБП</b> (по телефону).\n\n"
        "🌐 <b>Сайт:</b> " + SITE_URL + "\n"
        "🎮 <b>Игра:</b> " + GAME_URL + "\n\n"
        "👇 Жми кнопки внизу экрана ↓"
    )
    await message.answer(text, reply_markup=site_game_inline())
    await message.answer(
        "👇 <b>Главное меню — кнопки внизу:</b>",
        reply_markup=reply_main_keyboard(),
    )


@router.message(F.text == "💰 Курс")
async def on_rate_btn(message: Message):
    lines = [f"💱 <b>Курс DeDust-пулов</b> <i>v{BOT_VERSION}</i>\n"]
    for t in list_tokens():
        try:
            q = await feeds[t.slug].quote(1_000_000)
            if q.ok:
                lines.append(f"{t.emoji} <b>{t.symbol}</b>: 1 000 000 ЦАРЬ = <b>{q.rub_amount:,.4f} ₽</b>")
            else:
                lines.append(f"{t.emoji} {t.symbol}: недоступен")
        except Exception:
            lines.append(f"{t.emoji} {t.symbol}: ошибка")
    await message.answer("\n".join(lines), reply_markup=reply_main_keyboard())


@router.message(F.text == "💸 Продать")
async def on_sell_btn(message: Message):
    await message.answer("⤵ Выбери серию:", reply_markup=main_menu())


@router.message(F.text == "📊 Калькулятор")
async def on_calc_btn(message: Message):
    await message.answer("Отправь: <code>/sell 1000000</code>", reply_markup=reply_main_keyboard())


@router.message(F.text == "📜 История")
async def on_history_btn(message: Message):
    await message.answer("📜 История пуста (mock).", reply_markup=reply_main_keyboard())


@router.message(F.text == "🌐 Сайт")
async def on_site_btn(message: Message):
    await message.answer(f"🌐 {SITE_URL}", reply_markup=reply_main_keyboard())


@router.message(F.text == "🎮 Игра")
async def on_game_btn(message: Message):
    await message.answer(
        f"🎮 Игра: {GAME_URL}",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🎮 Запустить", web_app=WebAppInfo(url=GAME_URL))]
        ]),
    )
