"""Telegram-бот "ЦАРЬ бот обменник" — improved start handler and diagnostics.

Changes made:
- Added support for both CommandStart() and Command('start') to handle /start in different aiogram versions/environments.
- Added more robust logging and startup/shutdown hooks.
- Added global error handler to log unexpected exceptions.
- Minor text improvements in the main/back handlers so users see buttons and guidance.
- Kept original logic intact; no secrets or external changes.
"""
import asyncio
import logging
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from aiogram import Bot, Dispatcher, Router, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    InlineKeyboardButton, InlineKeyboardMarkup,
    ReplyKeyboardMarkup, KeyboardButton,
    Message, CallbackQuery,
)

# local imports (keep as in original project)
from api.payouts.tokens import (
    TOKENS, get_token, list_tokens, list_by_network, short_address,
)
from api.payouts.coins_to_tsar import (
    convert_coins, convert_to_all_3_tsars,
    fetch_cbr_silver, COIN_PRESETS,
)

BOT_VERSION = "2026-10-10-021"
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
SITE_URL = os.getenv("SITE_URL", "https://tsar-rub-lt87ahb9.agent.mira.tg/")
SUPPORT_USERNAME = os.getenv("SUPPORT_USERNAME", "BAAL_NIK_chat")

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("tsar.bot")

if not BOT_TOKEN:
    raise RuntimeError("TELEGRAM_BOT_TOKEN is required")

# Create bot and dispatcher
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())
router = Router()

USD_RUB = float(os.getenv("USD_RUB", "89.5"))


class WithdrawFSM(StatesGroup):
    waiting_network = State()
    waiting_token = State()
    waiting_amount = State()
    waiting_method = State()


class ConvertFSM(StatesGroup):
    waiting_count = State()
    waiting_grams = State()
    waiting_markup = State()
    waiting_tsar = State()


def main_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="💰 Курс"), KeyboardButton(text="📊 Калькулятор")],
            [KeyboardButton(text="💸 Продать"), KeyboardButton(text="🪙 Конвертер")],
            [KeyboardButton(text="🪙 Токены"), KeyboardButton(text="📜 История")],
            [KeyboardButton(text="❓ Помощь")],
        ],
        resize_keyboard=True,
    )


def network_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="👑 TON (3 царя)", callback_data="net:ton"),
            InlineKeyboardButton(text="🟨 BSC (4 царя)", callback_data="net:bsc"),
        ],
        [InlineKeyboardButton(text="🌐 Открыть сайт", url=SITE_URL)],
    ])


def tokens_kb(network: str) -> InlineKeyboardMarkup:
    tokens = list_by_network(network)
    rows = []
    for t in tokens:
        label = f"{t.emoji} {t.name} ({t.pool_label})"
        rows.append([InlineKeyboardButton(text=label, callback_data=f"tok:{t.slug}")])
    rows.append([InlineKeyboardButton(text="📊 Графики всех", callback_data=f"all:{network}")])
    rows.append([InlineKeyboardButton(text="⏪ К сетям", callback_data="back:net")])
    rows.append([InlineKeyboardButton(text="🌐 Сайт", url=SITE_URL)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def token_info_kb(slug: str) -> InlineKeyboardMarkup:
    t = get_token(slug)
    if not t:
        return InlineKeyboardMarkup(inline_keyboard=[])
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 График GeckoTerminal", url=t.gecko_url)],
        [InlineKeyboardButton(text="💸 Продать этот токен", callback_data=f"sell:{slug}")],
        [InlineKeyboardButton(text="⏪ К токенам", callback_data=f"back:tok:{t.network}")],
    ])


def all_charts_kb(network: str) -> InlineKeyboardMarkup:
    tokens = list_by_network(network)
    rows = []
    for t in tokens:
        rows.append([InlineKeyboardButton(
            text=f"📊 {t.emoji} {t.name} ({t.pool_label})",
            url=t.gecko_url,
        )])
    rows.append([InlineKeyboardButton(text="⏪ К токенам", callback_data=f"back:tok:{network}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def method_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📱 СБП (по телефону)", callback_data="m:sbp"),
            InlineKeyboardButton(text="💳 На карту", callback_data="m:card"),
        ],
        [InlineKeyboardButton(text="🤖 P2P (mock)", callback_data="m:p2p")],
        [InlineKeyboardButton(text="⏪ Назад", callback_data="back:net")],
    ])


def back_to_main_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⏪ В главное меню", callback_data="back:main")],
    ])


def tsar_choose_kb(prefix: str) -> InlineKeyboardMarkup:
    rows = []
    for t in TOKENS.values():
        rows.append([InlineKeyboardButton(
            text=f"{t.emoji} {t.name} ({t.network.upper()})",
            callback_data=f"{prefix}:{t.slug}",
        )])
    rows.append([InlineKeyboardButton(text="⏪ В главное меню", callback_data="back:main")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def estimate(slug: str, amount: int) -> dict:
    t = get_token(slug)
    if not t:
        return {"ok": False, "error": "Токен не найден"}
    if amount < t.min_tsar:
        return {"ok": False, "error": f"Минимум {t.min_tsar:,} {t.symbol}"}
    prices = {
        "BAAL_RA": 0.0001, "BLIZNETSY": 0.00009, "CROWN": 0.00012,
        "BSC_TSAR_1": 0.1058, "BSC_TSAR_2": 0.00000000004424,
        "BSC_HTTPS_DR": 0.0001, "BSC_TSAR_4": 0.0001,
    }
    usd_per = prices.get(slug, 0.0001)
    gross_rub = amount * usd_per * USD_RUB
    fee = gross_rub * 0.0075
    net_rub = gross_rub - fee
    return {
        "ok": True, "token": t, "amount": amount, "usd_per": usd_per,
        "gross_rub": gross_rub, "fee_rub": fee, "net_rub": net_rub, "usd_rub": USD_RUB,
    }


# Start handler: support both CommandStart() and Command('start')
@router.message(CommandStart())
@router.message(Command("start"))
async def cmd_start(message: Message) -> None:
    try:
        ton = list_by_network("ton")
        bsc = list_by_network("bsc")
        text = (
            "👑 <b>Привет! Я обменник ЦАРЬ → РУБЛЬ</b>\n\n"
            f"У меня <b>{len(ton)} токена в TON</b> и <b>{len(bsc)} токена в BSC</b>.\n\n"
            "Что умею:\n"
            "• <b>💰 Курс</b> — текущий курс всех 7 токенов\n"
            "• <b>📊 Калькулятор</b> — ЦАРЬ → рубли\n"
            "• <b>🪙 Конвертер</b> — серебро/золото → ЦАРЬ (новое!)\n"
            "• <b>💸 Продать</b> — оформить вывод на СБП / карту\n"
            "• <b>🪙 Токены</b> — все 7 токенов с графиками\n\n"
            f"🌐 Сайт: {SITE_URL}\n"
            f"💬 Поддержка: @{SUPPORT_USERNAME}"
        )
        await message.answer(text, reply_markup=main_kb())
    except Exception as e:
        log.exception("cmd_start failed")
        # fallback minimal reply so the user sees something
        await message.answer("Привет! Произошла внутренняя ошибка — обновите бота или напишите в поддержку.")


@router.message(F.text == "❓ Помощь")
@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(
        "👑 <b>Помощь по обменнику ЦАРЬ</b>\n\n"
        "<b>Команды:</b>\n"
        "/start — главное меню\n"
        "/tokens — все 7 токенов TON+BSC\n"
        "/quote — узнать курс\n"
        "/sell 1000000 — расчёт для 1М ЦАРЬ\n"
        "/withdraw — пошаговый вывод (FSM)\n"
        "/convert — конвертер монет в ЦАРЬ (новое!)\n"
        "/all3 — все 3 царя разом для 1 монеты 21г\n"
        "/history — история\n\n"
        f"<b>Сайт:</b> {SITE_URL}\n"
        f"<b>Поддержка:</b> @{SUPPORT_USERNAME}",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🌐 Открыть сайт", url=SITE_URL)],
            [InlineKeyboardButton(text="💬 Написать в поддержку", url=f"https://t.me/{SUPPORT_USERNAME}")],
        ]),
    )


@router.message(F.text == "🪙 Токены")
@router.message(Command("tokens"))
async def cmd_tokens(message: Message) -> None:
    ton = list_by_network("ton")
    bsc = list_by_network("bsc")
    text = f"👑 <b>Все токены ({len(ton) + len(bsc)})</b>\n\n"
    text += "<b>TON (DeDust):</b>\n"
    for t in ton:
        text += f"  {t.emoji} <b>{t.name}</b> — <code>{short_address(t.master)}</code>\n"
    text += f"\n<b>BSC (PancakeSwap):</b>\n"
    for t in bsc:
        text += f"  {t.emoji} <b>{t.name}</b> — <code>{short_address(t.master)}</code>\n"
    text += "\nВыбери сеть для графиков 👇"
    await message.answer(text, reply_markup=network_kb())


@router.message(F.text == "💰 Курс")
@router.message(Command("quote"))
async def cmd_quote(message: Message) -> None:
    await message.answer("👑 Выбери сеть для просмотра курса:", reply_markup=network_kb())


@router.message(F.text == "📊 Калькулятор")
@router.message(Command("sell"))
async def cmd_sell(message: Message) -> None:
    args = message.text.split()
    if len(args) >= 2 and args[1].isdigit():
        amt = int(args[1])
        r = await estimate("BAAL_RA", amt)
        if not r["ok"]:
            await message.answer(f"⚠️ {r['error']}")
            return
        t = r["token"]
        await message.answer(
            f"📊 <b>Расчёт для {amt:,} {t.symbol}</b>\n\n"
... (file continues)
