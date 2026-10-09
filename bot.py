"""Telegram-бот «ЦАРЬ обменник».

UX:
  • Inline-кнопки «ЦАРЬ» (4) + «Игра» (раннер) + «График» (DeDust)
  • Сайт обменника с заявкой P2P-сначала + СБП fallback
  • Inline-кнопки «Открыть сайт», «Играть», «График DeDust», «Купить/Продать»
  • Команды:
      /start     — приветствие + меню
      /quote     — курс (выбор токена)
      /sell N    — расчёт для N ЦАРЬ (без FSM)
      /withdraw  — пошаговый вывод (FSM)
      /history   — история (mock)
      /help      — эта справка

Pipeline (PayoutService):
  PriceFeed → P2PClient.best_buy_ad → ton_payout → SbpClient.payout
  Mock:   PriceFeed → P2PClient.payout → SbpClient.payout
"""
import asyncio
import logging
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from aiogram import Bot, Dispatcher, F, types
from aiogram.client.default import DefaultBotProperties
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    KeyboardButton,
    WebAppInfo,
)
from aiogram.enums import ParseMode

from api.payouts.price_feed import PriceFeed
from api.payouts.p2p import P2PClient
from api.payouts.service import PayoutService
from api.payouts.tokens import list_tokens, get_token
from api.payouts.models import PayoutMethod
from api.payouts.config import SUPPORT_HANDLE, MIN_PAYOUT_TSAR

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
ADMIN_CHAT_ID = int(os.getenv("ADMIN_CHAT_ID", "0") or "0")

if not TELEGRAM_BOT_TOKEN:
    sys.exit("⛔ TELEGRAM_BOT_TOKEN не задан (GitHub Secrets или export)")


# === FSM ===
class WithdrawFSM(StatesGroup):
    waiting_amount = State()  # ждём количество
    waiting_phone = State()   # ждём телефон СБП


# === Клиенты (lazy) ===
def make_clients(slug: str = "BAAL_RA"):
    try:
        token = get_token(slug)
        feed = PriceFeed(
            token_master=token.master,
            token_pool=token.pool,
            pool_label=token.pool_label,
        )
    except Exception as e:
        logger.warning("PriceFeed init failed for %s: %s — fallback default", slug, e)
        feed = PriceFeed()
    p2p = P2PClient()
    service = PayoutService(
        p2p_client=p2p, price_feed=feed, sbp_client=None, ton_payout=None,
    )
    return feed, p2p, service


# === Главное меню ===
def main_menu_kb() -> ReplyKeyboardMarkup:
    """Главное меню: 2 кнопки в ряд, компактно (3 ряда)."""
    return ReplyKeyboardMarkup(
        keyboard=[
            # Ряд 1: основные действия
            [KeyboardButton(text="💰 Курс"), KeyboardButton(text="💸 Продать")],
            # Ряд 2: инфо + история
            [KeyboardButton(text="📊 Калькулятор"), KeyboardButton(text="📜 История")],
            # Ряд 3: внешние ссылки
            [
                KeyboardButton(text="🌐 Сайт", web_app=WebAppInfo(url=SITE_URL)),
                KeyboardButton(text="🎮 Игра", web_app=WebAppInfo(url=GAME_URL)),
            ],
        ],
        resize_keyboard=True,
    )


def tokens_inline_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text=f"{t.icon} {t.label} ({t.slug})",
                callback_data=f"tok:{t.slug}",
            )],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="back:main")],
        ]
    )


def confirm_kb(amount: float, phone: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text=f"✅ Подтвердить {amount:,.0f} ЦАРЬ → {phone}",
                callback_data="confirm",
            )],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")],
        ]
    )


def back_kb(action: str = "main") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⏪ Назад", callback_data=action)],
        ]
    )


# ===== /start =====
@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer(
        f"👑 <b>ЦАРЬ бот обменник</b>\n\n"
        f"Меняю ЦАРЬ на рубли по курсу DeDust-пула.\n"
        f"Вывод через СБП на карту по номеру телефона.\n"
        f"Минимум: {MIN_PAYOUT_TSAR:,.0f} ЦАРЬ.\n\n"
        f"Поддержка: {SUPPORT_HANDLE}",
        reply_markup=main_menu_kb(),
    )
    await message.answer(
        "🌐 <b>Быстрые ссылки:</b>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🌐 Сайт", url=SITE_URL), InlineKeyboardButton(text="🎮 Игра", url=GAME_URL)],
            [InlineKeyboardButton(text="💬 Канал", url="https://t.me/+BAAL_NIK"), InlineKeyboardButton(text="💬 Чат", url="https://t.me/+BAAL_NIK_chat")],
            [InlineKeyboardButton(text="📞 Поддержка", url=f"https://t.me/{SUPPORT_HANDLE.lstrip('@')}")],
        ]),
    )


# ===== /help =====
@dp.message(Command("help"))
async def cmd_help(message: types.Message):
    await message.answer(
        f"👑 <b>Команды</b>\n\n"
        f"/quote — курс (выбор токена)\n"
        f"/sell N — расчёт для N ЦАРЬ (без FSM)\n"
        f"/withdraw — пошаговый вывод (FSM)\n"
        f"/history — история\n"
        f"/help — эта справка\n\n"
        f"💸 <b>Как продать ЦАРЬ</b>\n"
        f"1) Жмёшь «💸 Продать»\n"
        f"2) Вводишь количество (например <code>250000</code>)\n"
        f"3) Вводишь телефон <code>+7XXXXXXXXXX</code>\n"
        f"4) Подтверждаешь\n\n"
        f"Минимум: {MIN_PAYOUT_TSAR:,.0f} ЦАРЬ\n"
        f"Поддержка: {SUPPORT_HANDLE}",
        reply_markup=main_menu_kb(),
    )
