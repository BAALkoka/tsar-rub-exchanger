"""Telegram-бот обменника ЦАРЬ → RUB.

3 серии ЦАРЬ, у каждого свой DeDust-пул. Все 3 продаются через P2P и СБП.

Версия: 2026-10-10-014 — кнопка История с реальной логикой.
"""
from __future__ import annotations
import asyncio
import json as _json
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
    InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup,
    KeyboardButton, WebAppInfo, Message, CallbackQuery,
)
from api.payouts.tokens import TOKENS, get_token, list_tokens, short_master
from api.payouts.config import USD_RUB_FALLBACK, SUPPORT_HANDLE, USDT_TREASURY_ADDRESS
from api.payouts.price_feed import PriceFeed
from api.payouts.p2p import P2PClient
from api.payouts.service import PayoutService
from api.payouts.models import PayoutMethod

BOT_VERSION = "2026-10-10-014"
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

HISTORY = {}
HISTORY_FILE = Path("/tmp/tsar_history.json")


def load_history():
    if HISTORY_FILE.exists():
        try:
            data = _json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
            for k, v in data.items():
                HISTORY[int(k)] = v
        except Exception as e:
            logger.warning("load_history: %s", e)


def save_history():
    try:
        HISTORY_FILE.write_text(
            _json.dumps({str(k): v for k, v in HISTORY.items()}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except Exception as e:
        logger.warning("save_history: %s", e)


def add_to_history(user_id, slug, amount, rub, method, status):
    HISTORY.setdefault(user_id, []).append({
        "ts": time.time(), "slug": slug, "amount": amount,
        "rub": rub, "method": method, "status": status,
    })
    HISTORY[user_id] = HISTORY[user_id][-10:]
    save_history()


feeds = {
    t.slug: PriceFeed(token_master=t.master, token_pool=t.pool, pool_label=t.pool_label, manual_rate=1.0)
    for t in list_tokens()
}
p2p_client = P2PClient()
ADMIN_CHAT_ID = int(os.getenv("ADMIN_CHAT_ID", "0") or "0")

logger.info("BOT VERSION %s, feeds: %s, p2p configured: %s",
            BOT_VERSION, list(feeds.keys()), p2p_client.is_configured)
assert hasattr(PriceFeed, 'quote'), "PriceFeed missing quote()"


def _service_for(slug):
    return PayoutService(p2p_client=p2p_client, price_feed=feeds[slug])


class WithdrawForm(StatesGroup):
    token_slug = State()
    amount = State()


def reply_main_keyboard():
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


def site_game_inline():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🌐 Открыть сайт", url=SITE_URL),
            InlineKeyboardButton(text="🎮 Играть", web_app=WebAppInfo(url=GAME_URL)),
        ],
        [
            InlineKeyboardButton(text="🤖 Бот @BAAL_NIK_BOT", url="https://t.me/BAAL_NIK_BOT"),
            InlineKeyboardButton(text="💬 Чат", url="https://t.me/BAAL_NIK_chat"),
        ],
    ])


def main_menu():
    buttons = []
    for t in list_tokens():
        buttons.append([InlineKeyboardButton(text=t.emoji + " " + t.symbol + " — " + t.name, callback_data="token:" + t.slug)])
    buttons.append([InlineKeyboardButton(text="🌐 Сайт обменника", url=SITE_URL)])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


NL = "\n"


@router.message(CommandStart())
@router.message(F.text == "♻️ /start")
async def cmd_start(message: Message):
    text = (
        "👑 <b>ЦАРЬ Обменник</b> <i>v" + BOT_VERSION + "</i>" + NL + NL
        + "Продай любой из 3 царей за RUB." + NL
        + "Способы получения: <b>P2P</b> (карта) или <b>СБП</b> (по телефону)." + NL + NL
        + "🌐 <b>Сайт:</b> " + SITE_URL + NL
        + "🎮 <b>Игра:</b> " + GAME_URL + NL + NL
        + "👇 Жми кнопки внизу экрана ↓"
    )
    await message.answer(text, reply_markup=site_game_inline())
    await message.answer(
        "👇 <b>Главное меню — кнопки внизу:</b>",
        reply_markup=reply_main_keyboard(),
    )


@router.message(F.text == "💰 Курс")
async def on_rate_btn(message: Message):
    lines = ["💱 <b>Курс DeDust-пулов</b> <i>v" + BOT_VERSION + "</i>" + NL]
    for t in list_tokens():
        try:
            q = await feeds[t.slug].quote(1_000_000)
            if q.ok:
                lines.append(t.emoji + " <b>" + t.symbol + "</b>: 1 000 000 ЦАРЬ = <b>" + f"{q.rub_amount:,.4f}" + " ₽</b>")
            else:
                lines.append(t.emoji + " " + t.symbol + ": недоступен")
        except Exception:
            lines.append(t.emoji + " " + t.symbol + ": ошибка")
    await message.answer(NL.join(lines), reply_markup=reply_main_keyboard())


@router.message(F.text == "💸 Продать")
async def on_sell_btn(message: Message):
    await message.answer("⤵ Выбери серию:", reply_markup=main_menu())


@router.message(F.text == "📊 Калькулятор")
async def on_calc_btn(message: Message):
    await message.answer("Отправь: <code>/sell 1000000</code>", reply_markup=reply_main_keyboard())


@router.message(F.text == "📜 История")
async def on_history_btn(message: Message):
    user_id = message.from_user.id if message.from_user else 0
    items = HISTORY.get(user_id, [])
    if not items:
        await message.answer(
            "📜 <b>История выводов</b>" + NL + NL
            + "Пока пусто. Сделай первый вывод: нажми <b>💸 Продать</b>.",
            reply_markup=reply_main_keyboard(),
        )
        return
    lines = ["📜 <b>История выводов</b> <i>v" + BOT_VERSION + "</i>" + NL]
    for it in reversed(items):
        t = next((x for x in list_tokens() if x.slug == it["slug"]), None)
        sym = t.symbol if t else it["slug"]
        em = t.emoji if t else "👑"
        ts = time.strftime("%d.%m %H:%M", time.localtime(it["ts"]))
        lines.append(
            em + " <b>" + sym + "</b> — " + f"{it['amount']:,}" + " = <b>" + f"{it['rub']:,.2f}" + " ₽</b>" + NL
            + "   💳 " + it["method"] + " · " + it["status"] + " · " + ts
        )
    await message.answer(NL + NL.join(lines), reply_markup=reply_main_keyboard())


@router.message(F.text == "🌐 Сайт")
async def on_site_btn(message: Message):
    await message.answer("🌐 " + SITE_URL, reply_markup=reply_main_keyboard())


@router.message(F.text == "🎮 Игра")
async def on_game_btn(message: Message):
    await message.answer(
        "🎮 Игра: " + GAME_URL,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🎮 Запустить", web_app=WebAppInfo(url=GAME_URL))]
        ]),
    )


@router.message(Command("sell", "withdraw", "quote"))
async def cmd_sell(message: Message, command: Command):
    args = command.args
    user_id = message.from_user.id if message.from_user else 0
    if not args or not args[0].isdigit():
        await message.answer(
            "Формат: <code>/sell 1000000</code> (ЦАРЬ). Минимум 250 000.",
            reply_markup=reply_main_keyboard(),
        )
        return
    amount = int(args[0])
    if amount < 250_000:
        await message.answer("❌ Минимальный вывод: 250 000 ЦАРЬ.", reply_markup=reply_main_keyboard())
        return
    t = list_tokens()[0]
    try:
        q = await feeds[t.slug].quote(amount)
        if not q.ok:
            await message.answer("⚠️ Курс недоступен, попробуй позже.", reply_markup=reply_main_keyboard())
            return
        rub = q.rub_amount
        method = "СБП"
        status = "✅ Готово к выводу"
        add_to_history(user_id, t.slug, amount, rub, method, status)
        await message.answer(
            "👑 <b>" + t.symbol + "</b> → <b>" + f"{rub:,.2f}" + " ₽</b>" + NL
            + "📤 " + f"{amount:,}" + " ЦАРЬ · 💳 " + method + NL + NL
            + "<b>Способ получения:</b>" + NL
            + "📱 СБП: <code>+79285448941</code>" + NL
            + "💳 P2P: WalletBot Market" + NL + NL
            + "👇 Жми «📜 История» — увидишь эту заявку",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📱 СБП +79285448941", url="https://t.me/BAAL_NIK_BOT?start=sbp")],
                [InlineKeyboardButton(text="💳 P2P карта", url="https://t.me/BAAL_NIK_BOT?start=p2p")],
                [InlineKeyboardButton(text="📜 Открыть историю", callback_data="show_history")],
            ]),
        )
    except Exception as e:
        logger.error("quote error: %s", e)
        await message.answer("❌ Ошибка расчёта. Попробуй позже.", reply_markup=reply_main_keyboard())


@router.callback_query(F.data == "show_history")
async def on_history_cb(callback: CallbackQuery):
    user_id = callback.from_user.id
    items = HISTORY.get(user_id, [])
    if not items:
        await callback.message.answer("📜 История пуста.")
        await callback.answer()
        return
    lines = ["📜 <b>История</b> <i>v" + BOT_VERSION + "</i>" + NL]
    for it in reversed(items):
        ts = time.strftime("%d.%m %H:%M", time.localtime(it["ts"]))
        lines.append("• " + f"{it['amount']:,}" + " = " + f"{it['rub']:,.2f}" + " ₽ · " + it["method"] + " · " + it["status"] + " · " + ts)
    await callback.message.answer(NL.join(lines))
    await callback.answer()


@router.callback_query(F.data.startswith("token:"))
async def on_token_cb(callback: CallbackQuery, state: FSMContext):
    slug = callback.data.split(":", 1)[1]
    await state.set_state(WithdrawForm.amount)
    await state.update_data(token_slug=slug)
    t = get_token(slug)
    await callback.message.answer(
        "👑 Выбрано: <b>" + t.symbol + " " + t.name + "</b>" + NL
        + "Отправь сумму (мин 250 000):" + NL
        + "<code>/sell " + slug + " 1000000</code>"
    )
    await callback.answer()


async def main():
    load_history()
    logger.info("Starting bot v%s, history users: %d", BOT_VERSION, len(HISTORY))
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
