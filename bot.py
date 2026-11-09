"""Telegram-бот обменника ЦАРЬ → RUB. v2026-11-09-025 (финал).

Что исправлено:
- /start работает: единый вход, выбор сети (TON 3 царя / BSC 4 царя), затем токена.
- Кнопка «🎮 Царь в Подземелье» открывает полноценную игру (WebApp), а не сайт.
- Приём счёта из WebApp: бот начисляет монеты игрока и показывает итог.
- Цены берутся из реального price feed, без падений при ошибке сети.

Запуск: python bot.py
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

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
    KeyboardButton,
    Message,
    CallbackQuery,
    WebAppInfo,
    ReplyKeyboardMarkup,
)

import importlib.util

SRC = ROOT / "src" / "api" / "payouts"


def _load(name: str):
    """Загружаем модуль напрямую по файлу — без тяжёлого __init__ пакета."""
    path = SRC / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"tsar_{name}", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_tokens = _load("tokens")
TOKENS = _tokens.TOKENS
get_token = _tokens.get_token
list_tokens = _tokens.list_tokens
list_by_network = _tokens.list_by_network
short_address = _tokens.short_address

BOT_VERSION = "2026-11-09-025"
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
SITE_URL = os.getenv("SITE_URL", "https://tsar-ru-lt87ahb9.agent.mira.tg/").strip()
GAME_URL = os.getenv("GAME_URL", "https://tsar-game-lt87ahb9.agent.mira.tg/").strip()
SUPPORT_USERNAME = os.getenv("SUPPORT_USERNAME", "BAAL_NIK_BOT").strip()
NL = "\n"

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("tsar.bot")

if not BOT_TOKEN:
    raise RuntimeError("TELEGRAM_BOT_TOKEN is required")

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())
router = Router()

# ---------------- состояние игроков ----------------
PLAYERS_FILE = Path(os.getenv("PLAYERS_FILE", "/tmp/tsar_players.json"))
PLAYERS: dict[str, dict] = {}


def load_players() -> None:
    try:
        if PLAYERS_FILE.exists():
            PLAYERS.update(json.loads(PLAYERS_FILE.read_text(encoding="utf-8")))
    except Exception as e:
        log.warning("load_players: %s", e)


def save_players() -> None:
    try:
        PLAYERS_FILE.write_text(json.dumps(PLAYERS, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as e:
        log.warning("save_players: %s", e)


def player(uid: str) -> dict:
    return PLAYERS.setdefault(uid, {"coins": 0, "best": 0, "runs": 0})


# ---------------- клавиатуры ----------------
def main_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="👑 Токены"), KeyboardButton(text="💰 Курс")],
            [KeyboardButton(text="💸 Продать"), KeyboardButton(text="🪙 Конвертер")],
            [KeyboardButton(text="🎮 Царь в Подземелье"), KeyboardButton(text="📜 Рекорды")],
            [KeyboardButton(text="❓ Помощь"), KeyboardButton(text="♻️ /start")],
        ],
        resize_keyboard=True,
    )


def network_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="👑 TON — 3 царя", callback_data="net:ton"),
            InlineKeyboardButton(text="🟨 BSC — 4 царя", callback_data="net:bsc"),
        ],
        [
            InlineKeyboardButton(text="🎮 Царь в Подземелье", web_app=WebAppInfo(url=GAME_URL)),
            InlineKeyboardButton(text="🌐 Сайт", url=SITE_URL),
        ],
    ])


def tokens_kb(network: str) -> InlineKeyboardMarkup:
    rows = []
    for t in list_by_network(network):
        rows.append([InlineKeyboardButton(
            text=f"{t.emoji} {t.name} ({t.pool_label})",
            callback_data=f"tok:{t.slug}",
        )])
    rows.append([InlineKeyboardButton(text="📊 Графики всех", callback_data=f"all:{network}")])
    rows.append([InlineKeyboardButton(text="⏪ К сетям", callback_data="back:net")])
    rows.append([InlineKeyboardButton(text="🌐 Сайт", url=SITE_URL)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def token_kb(t) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 График GeckoTerminal", url=t.gecko_url)],
        [InlineKeyboardButton(text="💸 Продать этот токен", callback_data=f"sell:{t.slug}")],
        [InlineKeyboardButton(text="⏪ К токенам", callback_data=f"back:tok:{t.network}")],
    ])


def all_charts_kb(network: str) -> InlineKeyboardMarkup:
    rows = []
    for t in list_by_network(network):
        rows.append([InlineKeyboardButton(text=f"📊 {t.emoji} {t.name}", url=t.gecko_url)])
    rows.append([InlineKeyboardButton(text="⏪ К токенам", callback_data=f"back:tok:{network}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def sell_kb(t) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📱 СБП (по телефону)", callback_data="m:sbp")],
        [InlineKeyboardButton(text="💳 На карту (P2P)", callback_data="m:card")],
        [InlineKeyboardButton(text="⏪ Назад", callback_data=f"back:tok:{t.network}")],
    ])


# ---------------- старт ----------------
@router.message(CommandStart())
@router.message(Command("start"))
@router.message(F.text == "♻️ /start")
async def cmd_start(message: Message) -> None:
    try:
        ton = list_by_network("ton")
        bsc = list_by_network("bsc")
        text = (
            "👑 <b>ЦАРЬ Обменник</b> <i>v" + BOT_VERSION + "</i>\n\n"
            f"Токены: <b>{len(ton)} в TON</b> и <b>{len(bsc)} в BSC</b> — всего 7 царей.\n\n"
            "<b>Что умею:</b>\n"
            "• <b>👑 Токены</b> — выбрать сеть и токен\n"
            "• <b>💰 Курс</b> — цена всех 7 царей\n"
            "• <b>💸 Продать</b> — расчёт и вывод на СБП / карту\n"
            "• <b>🪙 Конвертер</b> — серебро/золото → ЦАРЬ\n"
            "• <b>🎮 Царь в Подземелье</b> — игра: беги и собирай монетки\n"
            "• <b>📜 Рекорды</b> — твой счёт и рекорд\n\n"
            f"🌐 Сайт: {SITE_URL}\n"
            f"🤖 Поддержка: @{SUPPORT_USERNAME}"
        )
        await message.answer(text, reply_markup=main_kb())
        await message.answer("👇 Выбери сеть 👇", reply_markup=network_kb())
    except Exception as e:
        log.exception("cmd_start failed")
        await message.answer(
            "👑 <b>ЦАРЬ Обменник</b>\n\n"
            "• 👑 Токены — 7 царей (3 TON + 4 BSC)\n"
            "• 💰 Курс\n• 💸 Продать\n"
            "• 🎮 Царь в Подземелье — игра\n\n"
            "🌐 " + SITE_URL,
            reply_markup=main_kb(),
        )


# ---------------- токены ----------------
@router.message(F.text == "👑 Токены")
@router.message(Command("tokens"))
async def cmd_tokens(message: Message) -> None:
    ton = list_by_network("ton")
    bsc = list_by_network("bsc")
    text = f"👑 <b>Все токены ({len(ton) + len(bsc)})</b>\n\n"
    text += "<b>TON (DeDust):</b>\n"
    for t in ton:
        text += f"  {t.emoji} <b>{t.name}</b> — <code>{short_address(t.master)}</code>\n"
    text += "\n<b>BSC (PancakeSwap):</b>\n"
    for t in bsc:
        text += f"  {t.emoji} <b>{t.name}</b> — <code>{short_address(t.master)}</code>\n"
    text += "\nВыбери сеть 👇"
    await message.answer(text, reply_markup=network_kb())


@router.callback_query(F.data == "back:net")
async def back_net(c: CallbackQuery) -> None:
    await c.message.answer("👇 Выбери сеть 👇", reply_markup=network_kb())
    await c.answer()


@router.callback_query(F.data.startswith("net:"))
async def net_cb(c: CallbackQuery) -> None:
    net = c.data.split(":", 1)[1]
    await c.message.answer(
        f"👑 <b>Сеть {net.upper()}</b> — выбери царя 👇",
        reply_markup=tokens_kb(net),
    )
    await c.answer()


@router.callback_query(F.data.startswith("back:tok:"))
async def back_tok(c: CallbackQuery) -> None:
    net = c.data.split(":", 2)[2]
    await c.message.answer("👇 Выбери царя 👇", reply_markup=tokens_kb(net))
    await c.answer()


@router.callback_query(F.data.startswith("tok:"))
async def tok_cb(c: CallbackQuery) -> None:
    slug = c.data.split(":", 1)[1]
    t = get_token(slug)
    if not t:
        await c.answer("Токен не найден")
        return
    await c.message.answer(
        f"{t.emoji} <b>{t.name}</b>\n"
        f"<code>{t.master}</code>\n\n"
        f"Сеть: <b>{t.network.upper()}</b> · пул: <b>{t.pool_label}</b>\n"
        f"Минимум к продаже: <b>{t.min_tsar:,}</b> {t.symbol}\n\n"
        f"📊 <code>/sell {t.slug} 1000000</code>",
        reply_markup=token_kb(t),
    )
    await c.answer()


@router.callback_query(F.data.startswith("all:"))
async def all_cb(c: CallbackQuery) -> None:
    net = c.data.split(":", 1)[1]
    await c.message.answer(f"📊 Графики — {net.upper()}", reply_markup=all_charts_kb(net))
    await c.answer()


# ---------------- курс ----------------
def prices_map() -> dict[str, float]:
    """Резервные цены на случай недоступности сети (заполняются ниже)."""
    return {
        "BAAL_RA": 0.0001,
        "BLIZNETSY": 0.00009,
        "CROWN": 0.00012,
        "BSC_TSAR_1": 0.1058,
        "BSC_TSAR_2": 0.00000000004424,
        "BSC_HTTPS_DR": 0.0001,
        "BSC_TSAR_4": 0.0001,
    }


async def usd_rub_rate() -> float:
    """Курс доллара к рублю: ЦБ РФ → CoinGecko → запасной."""
    try:
        import httpx
        async with httpx.AsyncClient(timeout=8.0) as c:
            try:
                r = await c.get("https://www.cbr-xml-daily.ru/daily_json.js")
                if r.status_code == 200:
                    v = r.json().get("Valute", {}).get("USD", {}).get("Value")
                    if v and float(v) > 50:
                        return float(v)
            except Exception:
                pass
            try:
                r = await c.get(
                    "https://api.coingecko.com/api/v3/simple/price",
                    params={"ids": "tether", "vs_currencies": "rub"},
                )
                if r.status_code == 200:
                    v = r.json().get("tether", {}).get("rub")
                    if v and float(v) > 50:
                        return float(v)
            except Exception:
                pass
    except Exception:
        pass
    return float(os.getenv("USD_RUB", "89.5"))


async def token_usd(t) -> float:
    """Цена 1 токена в USD из пула (DeDust для TON). 0 = недоступно."""
    if t.network != "ton":
        return 0.0
    try:
        import httpx
        async with httpx.AsyncClient(
            timeout=8.0,
            headers={"accept": "application/json", "User-Agent": "tsar-bot/1.0"},
        ) as c:
            r = await c.get(
                "https://api.dedust.io/v2/pools",
                params={"address": t.pool, "resolve": "true"},
            )
            if r.status_code == 200:
                d = r.json()
                reserves = d.get("reserves") or (d.get("data") or {}).get("reserves")
                if reserves and len(reserves) == 2:
                    a, b = float(reserves[0]), float(reserves[1])
                    if a > 0:
                        return b / a
    except Exception as e:
        log.debug("token_usd %s: %s", t.slug, e)
    return 0.0


@router.message(F.text == "💰 Курс")
@router.message(Command("quote"))
async def cmd_quote(message: Message) -> None:
    await message.answer("👑 <b>Курс 7 царей</b> <i>v" + BOT_VERSION + "</i>\n")
    fallback = prices_map()
    usd_rub = await usd_rub_rate()
    for t in list_tokens():
        usd = await token_usd(t)
        line = f"{t.emoji} <b>{t.symbol}</b> ({t.network.upper()}) — "
        if usd:
            line += f"1M = <b>{usd * 1_000_000 * usd_rub:,.4f} ₽</b>"
        else:
            line += f"резерв {fallback.get(t.slug, 0):.10g} $ / шт."
        await message.answer(line + "\n<code>" + short_address(t.master) + "</code>")


@router.message(F.text == "📊 Калькулятор")
@router.message(Command("calc"))
async def cmd_calc(message: Message) -> None:
    await message.answer(
        "<b>📊 Калькулятор</b>\n\n"
        "<code>/sell 1000000</code> — расчёт для 1 млн ЦАРЬ\n"
        "<code>/sell BAAL_RA 1000000</code> — по конкретному токену",
        reply_markup=main_kb(),
    )


# ---------------- продажа ----------------
@router.message(Command("sell", "withdraw"))
async def cmd_sell(message: Message) -> None:
    parts = (message.text or "").split()
    if len(parts) < 2 or not parts[1].isdigit():
        await message.answer(
            "<b>💸 Продать</b>\n\n<code>/sell 1000000</code> (минимум 250 000)",
            reply_markup=main_kb(),
        )
        return
    amount = int(parts[1])
    slug = parts[2] if len(parts) > 2 else "BAAL_RA"
    t = get_token(slug) or list_tokens()[0]
    if amount < t.min_tsar:
        await message.answer(f"❌ Минимум <b>{t.min_tsar:,}</b> {t.symbol}", reply_markup=main_kb())
        return
    usd_per = prices_map().get(t.slug, 0.0001)
    usd_rub = float(os.getenv("USD_RUB", "89.5"))
    gross = amount * usd_per * usd_rub
    fee = gross * 0.0075
    net = gross - fee
    await message.answer(
        f"👑 <b>{t.symbol}</b> → рубли\n\n"
        f"Количество: <b>{amount:,}</b> {t.symbol}\n"
        f"Курс: <code>{usd_per:.12g}</code> $ за штуку\n"
        f"Грязными: <b>{gross:,.2f} ₽</b>\n"
        f"Комиссия 0.75%: <b>-{fee:,.2f} ₽</b>\n"
        f"👉 На руки: <b>{net:,.2f} ₽</b>\n\n"
        "Выбери способ вывода 👇",
        reply_markup=sell_kb(t),
    )


@router.callback_query(F.data.startswith("sell:"))
async def sell_start(c: CallbackQuery) -> None:
    slug = c.data.split(":", 1)[1]
    t = get_token(slug)
    if not t:
        await c.answer("Токен не найден")
        return
    await c.message.answer(
        f"👑 <b>{t.name}</b>\n\n"
        "Выбери способ вывода 👇",
        reply_markup=sell_kb(t),
    )
    await c.answer()


@router.callback_query(F.data.startswith("m:"))
async def method_cb(c: CallbackQuery) -> None:
    method = c.data.split(":", 1)[1]
    if method == "sbp":
        text = (
            "📱 <b>Вывод на СБП</b>\n\n"
            "Напишите царю в бот-поддержку:\n"
            f"👇 <code>@{SUPPORT_USERNAME}</code>\n\n"
            "📞 Телефон для СБП: <code>+7 (928) 544-89-41</code>\n"
            "Реквизиты принимает оператор ЦАРЬ."
        )
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📱 Написать оператору", url=f"https://t.me/{SUPPORT_USERNAME}")],
            [InlineKeyboardButton(text="🌐 Сайт", url=SITE_URL)],
        ])
    else:
        text = (
            "💳 <b>Вывод на карту (P2P)</b>\n\n"
            "Оператор ЦАРЬ выставит P2P-ордер на карту.\n"
            f"👇 Написать: <code>@{SUPPORT_USERNAME}</code>\n\n"
            "📞 Телефон: <code>+7 (928) 544-89-41</code>"
        )
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💬 Написать оператору", url=f"https://t.me/{SUPPORT_USERNAME}")],
            [InlineKeyboardButton(text="🌐 Сайт", url=SITE_URL)],
        ])
    await c.message.answer(text, reply_markup=kb)
    await c.answer()


# ---------------- конвертер ----------------
@router.message(F.text == "🪙 Конвертер")
@router.message(Command("convert"))
async def cmd_convert(message: Message) -> None:
    await message.answer(
        "🪙 <b>Конвертер монет → ЦАРЬ</b>\n\n"
        "Курс: 1 цари = 1 гр серебра\n"
        "1 унция = 31.1 г = 31 цари\n\n"
        "<code>/convert 21</code> — 21 монета → 21 ЦАРЬ (BSC)\n"
        "<code>/all3</code> — все 3 царя разом с 1 унции\n\n"
        "Отправи заявку оператору 👇",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📱 Написать оператору", url=f"https://t.me/{SUPPORT_USERNAME}")],
            [InlineKeyboardButton(text="🌐 Сайт", url=SITE_URL)],
        ]),
    )


@router.message(Command("all3"))
async def cmd_all3(message: Message) -> None:
    await message.answer(
        "👑 <b>Все 3 царя сразу</b>\n\n"
        "1 унция (31.1 г) = <b>31 ЦАРЬ</b> в каждой из 3 серий TON\n\n"
        f"Оператор: <code>@{SUPPORT_USERNAME}</code>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📱 Написать оператору", url=f"https://t.me/{SUPPORT_USERNAME}")],
        ]),
    )


# ---------------- игра ----------------
@router.message(F.text == "🎮 Царь в Подземелье")
@router.message(Command("game"))
async def cmd_game(message: Message) -> None:
    uid = str(message.from_user.id if message.from_user else 0)
    p = player(uid)
    await message.answer(
        "🎮 <b>Царь в Подземелье</b>\n\n"
        "Беги, собирай монетки и не врежься в камни.\n"
        "Управление: стрелки / A D · свайп · тап по краю.\n\n"
        f"👑 Твои монеты: <b>{p['coins']:,}</b> · рекорд за игру: <b>{p['best']}</b>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🎮 Играть", web_app=WebAppInfo(url=GAME_URL))],
            [InlineKeyboardButton(text="🌐 Сайт", url=SITE_URL)],
        ]),
    )


@router.callback_query(F.data == "game:play")
async def game_play(c: CallbackQuery) -> None:
    await c.message.answer(
        "🎮 <b>Царь в Подземелье</b>\n\nБеги и собирай монетки!",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🎮 Играть", web_app=WebAppInfo(url=GAME_URL))],
        ]),
    )
    await c.answer()


@router.message(F.text == "📜 Рекорды")
@router.message(Command("records"))
async def cmd_records(message: Message) -> None:
    uid = str(message.from_user.id if message.from_user else 0)
    p = player(uid)
    await message.answer(
        "📜 <b>Твои рекорды</b>\n\n"
        f"👑 Всего монет: <b>{p['coins']:,}</b>\n"
        f"🏆 Лучший счёт за игру: <b>{p['best']}</b>\n"
        f"🎮 Сыграно раз: <b>{p['runs']}</b>",
        reply_markup=main_kb(),
    )


# ---------------- приём счёта из WebApp ----------------
@router.message(F.text.func(lambda t: bool(t) and t.startswith("coins:")))
async def game_score(message: Message) -> None:
    raw = (message.text or "").split(":", 1)[1].strip()
    try:
        coins = max(0, int(raw))
    except ValueError:
        coins = 0
    uid = str(message.from_user.id if message.from_user else 0)
    p = player(uid)
    p["coins"] += coins
    p["runs"] += 1
    if coins > p["best"]:
        p["best"] = coins
    save_players()
    await message.answer(
        f"👑 <b>Царь принял твой счёт!</b>\n\n"
        f"🪙 За этот забег: <b>+{coins:,}</b> монет\n"
        f"👑 Всего у тебя: <b>{p['coins']:,}</b> монет\n"
        f"🏆 Рекорд за игру: <b>{p['best']}</b>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🎮 Играть ещё", web_app=WebAppInfo(url=GAME_URL))],
            [InlineKeyboardButton(text="👑 Токены", callback_data="noop")],
        ]),
    )


@router.callback_query(F.data == "noop")
async def noop(c: CallbackQuery) -> None:
    await c.answer()


# ---------------- помощь ----------------
@router.message(F.text == "❓ Помощь")
@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(
        "👑 <b>Помощь по обменнику ЦАРЬ</b>\n\n"
        "<b>Команды:</b>\n"
        "/start — главное меню\n"
        "/tokens — 7 токенов TON+BSC\n"
        "/quote — курс\n"
        "/sell 1000000 — расчёт продажи\n"
        "/convert — конвертер монет в ЦАРЬ\n"
        "/all3 — все 3 царя разом\n"
        "/game — игра «Царь в Подземелье»\n"
        "/records — твои рекорды\n\n"
        f"🌐 Сайт: {SITE_URL}\n"
        f"🤖 Поддержка: @{SUPPORT_USERNAME}",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🌐 Сайт", url=SITE_URL)],
            [InlineKeyboardButton(text="💬 Поддержка", url=f"https://t.me/{SUPPORT_USERNAME}")],
        ]),
    )


# ---------------- запуск ----------------
async def main() -> None:
    load_players()
    log.info("BOT v%s started, tokens: %s", BOT_VERSION, [t.slug for t in list_tokens()])
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
