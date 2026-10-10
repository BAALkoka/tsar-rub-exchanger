"""Telegram-бот "ЦАРЬ бот обменник" — v3.1 (7 токенов: 3 TON + 4 BSC).

UX:
  • Главное меню: [💰 Курс] [📊 Калькулятор] [💸 Продать] [📜 История] [❓ Помощь] [🪙 Токены]
  • /tokens — все 7 токенов TON+BSC
  • /quote — выбор сети → выбор токена → inline-кнопки графиков
  • /withdraw — 4-шаговый FSM (сеть → токен → сумма → способ)
  • Кнопка ⏪ Назад в FSM-сообщениях

Команды:
  /start      — главное меню
  /tokens     — все 7 токенов TON+BSC
  /quote      — узнать курс (с inline-выбором)
  /sell N     — расчёт для N ЦАРЬ
  /withdraw   — пошаговый вывод (FSM)
  /history    — история
  /help       — справка
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

from api.payouts.tokens import (
    TOKENS, get_token, list_tokens, list_by_network, short_address,
)

BOT_VERSION = "2026-10-10-019"
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
SITE_URL = "https://tsar-rub-lt87ahb9.agent.mira.tg/"
SUPPORT_USERNAME = "BAAL_NIK_chat"

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("tsar.bot")

if not BOT_TOKEN:
    raise RuntimeError("TELEGRAM_BOT_TOKEN is required")

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())
router = Router()

USD_RUB = float(os.getenv("USD_RUB", "89.5"))


# ==================== FSM ====================
class WithdrawFSM(StatesGroup):
    waiting_network = State()
    waiting_token = State()
    waiting_amount = State()
    waiting_method = State()


# ==================== Клавиатуры ====================
def main_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="💰 Курс"), KeyboardButton(text="📊 Калькулятор")],
            [KeyboardButton(text="💸 Продать"), KeyboardButton(text="📜 История")],
            [KeyboardButton(text="🪙 Токены"), KeyboardButton(text="❓ Помощь")],
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


# ==================== Расчёт ====================
async def estimate(slug: str, amount: int) -> dict:
    t = get_token(slug)
    if not t:
        return {"ok": False, "error": "Токен не найден"}
    if amount < t.min_tsar:
        return {"ok": False, "error": f"Минимум {t.min_tsar:,} {t.symbol}"}
    # Цена в USD (mock)
    prices = {
        "BAAL_RA": 0.0001,
        "BLIZNETSY": 0.00009,
        "CROWN": 0.00012,
        "BSC_TSAR_1": 0.1058,
        "BSC_TSAR_2": 0.00000000004424,
        "BSC_HTTPS_DR": 0.0001,
        "BSC_TSAR_4": 0.0001,
    }
    usd_per = prices.get(slug, 0.0001)
    gross_rub = amount * usd_per * USD_RUB
    fee = gross_rub * 0.0075
    net_rub = gross_rub - fee
    return {
        "ok": True,
        "token": t,
        "amount": amount,
        "usd_per": usd_per,
        "gross_rub": gross_rub,
        "fee_rub": fee,
        "net_rub": net_rub,
        "usd_rub": USD_RUB,
    }


# ==================== /start ====================
@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    ton = list_by_network("ton")
    bsc = list_by_network("bsc")
    text = (
        "👑 <b>Привет! Я обменник ЦАРЬ → РУБЛЬ</b>\n\n"
        f"У меня <b>{len(ton)} токена в TON</b> и <b>{len(bsc)} токена в BSC</b>.\n\n"
        "Что умею:\n"
        "• <b>💰 Курс</b> — текущий курс всех 7 токенов\n"
        "• <b>📊 Калькулятор</b> — посчитать сколько получишь\n"
        "• <b>💸 Продать</b> — оформить вывод на СБП / карту\n"
        "• <b>🪙 Токены</b> — все 7 токенов с графиками\n"
        "• <b>📜 История</b> — последние заявки\n\n"
        f"🌐 Сайт: {SITE_URL}\n"
        f"💬 Поддержка: @{SUPPORT_USERNAME}"
    )
    await message.answer(text, reply_markup=main_kb())


# ==================== /help ====================
@router.message(F.text == "❓ Помощь")
@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(
        "👑 <b>Помощь по обменнику ЦАРЬ</b>\n\n"
        "<b>Команды:</b>\n"
        "/start — главное меню\n"
        "/tokens — все 7 токенов TON+BSC\n"
        "/quote — узнать курс (выбор сети → токена)\n"
        "/sell 1000000 — расчёт для 1М ЦАРЬ\n"
        "/withdraw — пошаговый вывод (FSM)\n"
        "/history — история\n\n"
        f"<b>Сайт:</b> {SITE_URL}\n"
        f"<b>Поддержка:</b> @{SUPPORT_USERNAME}",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🌐 Открыть сайт", url=SITE_URL)],
            [InlineKeyboardButton(text="💬 Написать в поддержку", url=f"https://t.me/{SUPPORT_USERNAME}")],
        ]),
    )


# ==================== /tokens ====================
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


# ==================== /quote ====================
@router.message(F.text == "💰 Курс")
@router.message(Command("quote"))
async def cmd_quote(message: Message) -> None:
    await message.answer("👑 Выбери сеть для просмотра курса:", reply_markup=network_kb())


# ==================== /sell ====================
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
            f"Токен: {t.emoji} <b>{t.name}</b>\n"
            f"Сеть: <b>{t.network.upper()}</b>\n"
            f"Цена: <code>${r['usd_per']:.10f}</code>\n"
            f"USD/RUB: <code>{r['usd_rub']}</code>\n"
            f"━━━━━━━━━━━━━━\n"
            f"Сумма: <b>{r['gross_rub']:,.2f} ₽</b>\n"
            f"Комиссия: <code>{r['fee_rub']:,.2f} ₽</code>\n"
            f"━━━━━━━━━━━━━━\n"
            f"💵 <b>К получению: {r['net_rub']:,.2f} ₽</b>\n\n"
            f"Чтобы оформить — нажми 💸 Продать",
            reply_markup=back_to_main_kb(),
        )
        return
    await message.answer("📊 Калькулятор. Выбери сеть:", reply_markup=network_kb())


# ==================== /withdraw ====================
@router.message(F.text == "💸 Продать")
@router.message(Command("withdraw"))
async def cmd_withdraw(message: Message, state: FSMContext) -> None:
    await state.set_state(WithdrawFSM.waiting_network)
    await message.answer(
        "💸 <b>Оформление вывода</b>\n\nШаг 1/3: выбери сеть 👇",
        reply_markup=network_kb(),
    )


# ==================== /history ====================
@router.message(F.text == "📜 История")
@router.message(Command("history"))
async def cmd_history(message: Message) -> None:
    await message.answer(
        "📜 <b>История заявок</b>\n\nПока пусто. Оформи первую через /withdraw",
        reply_markup=back_to_main_kb(),
    )


# ==================== CALLBACKS ====================
@router.callback_query(F.data.startswith("net:"))
async def cb_network(call: CallbackQuery, state: FSMContext) -> None:
    network = call.data.split(":")[1]
    tokens = list_by_network(network)
    emoji = "👑" if network == "ton" else "🟨"
    text = f"{emoji} <b>{network.upper()} — {len(tokens)} токенов</b>\n\nВыбери токен 👇"
    await call.message.edit_text(text, reply_markup=tokens_kb(network))
    await call.answer()


@router.callback_query(F.data.startswith("tok:"))
async def cb_token(call: CallbackQuery, state: FSMContext) -> None:
    slug = call.data.split(":")[1]
    t = get_token(slug)
    if not t:
        await call.answer("Токен не найден", show_alert=True)
        return
    text = (
        f"{t.emoji} <b>{t.name}</b>\n\n"
        f"Сеть: <b>{t.network.upper()}</b>\n"
        f"Мастер: <code>{short_address(t.master)}</code>\n"
        f"Пул: <code>{short_address(t.pool)}</code>\n"
        f"Пара: <b>{t.pool_label}</b>\n"
        f"Мин. вывод: <b>{t.min_tsar:,} {t.symbol}</b>\n\n"
        f"📊 <a href=\"{t.gecko_url}\">График GeckoTerminal</a>"
    )
    await call.message.edit_text(text, reply_markup=token_info_kb(slug), disable_web_page_preview=False)
    await call.answer()


@router.callback_query(F.data.startswith("all:"))
async def cb_all_charts(call: CallbackQuery) -> None:
    network = call.data.split(":")[1]
    emoji = "👑" if network == "ton" else "🟨"
    text = f"{emoji} <b>Графики {network.upper()}-пулов</b>\n\nНажми на токен, чтобы открыть график GeckoTerminal 👇"
    await call.message.edit_text(text, reply_markup=all_charts_kb(network))
    await call.answer()


@router.callback_query(F.data.startswith("sell:"))
async def cb_sell(call: CallbackQuery, state: FSMContext) -> None:
    slug = call.data.split(":")[1]
    await state.update_data(slug=slug)
    await state.set_state(WithdrawFSM.waiting_amount)
    t = get_token(slug)
    await call.message.edit_text(
        f"💸 <b>Продать {t.name}</b>\n\n"
        f"Шаг 2/3: введи количество (мин. {t.min_tsar:,} {t.symbol})",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⏪ Назад", callback_data=f"back:tok:{t.network}")],
        ]),
    )
    await call.answer()


@router.callback_query(F.data.startswith("m:"))
async def cb_method(call: CallbackQuery, state: FSMContext) -> None:
    method = call.data.split(":")[1]
    data = await state.get_data()
    slug = data.get("slug", "BAAL_RA")
    amount = data.get("amount", 0)
    t = get_token(slug)
    r = await estimate(slug, amount)
    if not r["ok"]:
        await call.message.edit_text(f"⚠️ {r['error']}")
        await state.clear()
        return
    method_name = {"sbp": "СБП", "card": "Карта", "p2p": "P2P"}[method]
    text = (
        f"✅ <b>Заявка создана!</b>\n\n"
        f"Токен: {t.emoji} <b>{t.name}</b>\n"
        f"Сеть: <b>{t.network.upper()}</b>\n"
        f"Количество: <b>{amount:,} {t.symbol}</b>\n"
        f"Способ: <b>{method_name}</b>\n"
        f"━━━━━━━━━━━━━━\n"
        f"💵 <b>К получению: {r['net_rub']:,.2f} ₽</b>\n\n"
        f"📞 Ожидайте звонка от оператора в течение 5 минут."
    )
    await call.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🌐 Открыть сайт", url=SITE_URL)],
        [InlineKeyboardButton(text="💬 Поддержка", url=f"https://t.me/{SUPPORT_USERNAME}")],
        [InlineKeyboardButton(text="⏪ В главное меню", callback_data="back:main")],
    ]))
    await state.clear()
    await call.answer("Заявка создана ✅")


@router.callback_query(F.data.startswith("back:"))
async def cb_back(call: CallbackQuery, state: FSMContext) -> None:
    parts = call.data.split(":")
    if parts[1] == "main":
        await state.clear()
        await call.message.edit_text(
            "👑 <b>Главное меню</b>\n\nНажми /start для кнопок",
            reply_markup=back_to_main_kb(),
        )
    elif parts[1] == "net":
        await call.message.edit_text("👑 Выбери сеть:", reply_markup=network_kb())
    elif parts[1] == "tok" and len(parts) > 2:
        network = parts[2]
        tokens = list_by_network(network)
        emoji = "👑" if network == "ton" else "🟨"
        await call.message.edit_text(
            f"{emoji} <b>{network.upper()} — {len(tokens)} токенов</b>",
            reply_markup=tokens_kb(network),
        )
    await call.answer()


# ==================== FSM HANDLERS ====================
@router.message(WithdrawFSM.waiting_amount)
async def fsm_amount(message: Message, state: FSMContext) -> None:
    if not message.text.isdigit():
        await message.answer("⚠️ Введи целое число")
        return
    amount = int(message.text)
    data = await state.get_data()
    slug = data.get("slug", "BAAL_RA")
    t = get_token(slug)
    if amount < t.min_tsar:
        await message.answer(f"⚠️ Минимум {t.min_tsar:,}")
        return
    await state.update_data(amount=amount)
    await state.set_state(WithdrawFSM.waiting_method)
    r = await estimate(slug, amount)
    text = (
        f"📊 <b>{amount:,} {t.symbol}</b>\n"
        f"💵 К получению: <b>{r['net_rub']:,.2f} ₽</b>\n\n"
        f"Шаг 3/3: выбери способ вывода 👇"
    )
    await message.answer(text, reply_markup=method_kb())


# ==================== Запуск ====================
async def main() -> None:
    log.info("Tsar bot v%s starting (7 tokens: 3 TON + 4 BSC)", BOT_VERSION)
    dp.include_router(router)
    await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        log.info("Bot stopped")
