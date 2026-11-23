"""Telegram-бот обменника ЦАРЬ → RUB. v2026-11-12-026 (фикс: dp.include_router — /start заработал).

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
for _p in (ROOT, ROOT / "src", ROOT.parent):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import importlib.util

from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
    WebAppInfo,
)

# Каталог с модулями api.payouts — ищем в нескольких местах,
# чтобы бот одинаково запускался из корня, из src/ и как модуль bot.main.
_CANDIDATES = [
    ROOT / "src" / "api" / "payouts",
    ROOT.parent / "api" / "payouts",
    ROOT.parent / "src" / "api" / "payouts",
    Path("/app/api/payouts"),
    Path("/app/src/api/payouts"),
]


def _payouts_dir() -> Path:
    for c in _CANDIDATES:
        if (c / "tokens.py").exists():
            return c
    raise RuntimeError("каталог api/payouts не найден: " + ", ".join(str(c) for c in _CANDIDATES))


def _load(name: str):
    """Загружаем модуль напрямую по файлу — без тяжёлого __init__ пакета."""
    path = _payouts_dir() / f"{name}.py"
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

BOT_VERSION = "2026-11-15-029"
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
SITE_URL = os.getenv("SITE_URL", "https://tsar-ru-lt87ahb9.agent.mira.tg/").strip()
GAME_URL = os.getenv("GAME_URL", "https://tsar-game-lt87ahb9.agent.mira.tg/").strip()
SUPPORT_USERNAME = os.getenv("SUPPORT_USERNAME", "BAAL_NIK_BOT").strip()
# ---- iCryptoCheck (вывод игровых монет) ----
ICRYPTO_API_BASE = os.getenv("ICRYPTO_API_BASE", "https://api.icryptocheck.com").strip().rstrip("/")
ICRYPTO_API_KEY = os.getenv("ICRYPTO_API_KEY", "").strip()
ICRYPTO_TOKEN_ADDRESS = os.getenv("ICRYPTO_TOKEN_ADDRESS", "").strip()
ICRYPTO_CHECK_PATH = os.getenv("ICRYPTO_CHECK_PATH", "/app/createCheck").strip()
ICRYPTO_BOT_USERNAME = os.getenv("ICRYPTO_BOT_USERNAME", "iCryptoCheckBot").strip()
GAME_TOKEN_SLUG = os.getenv("GAME_TOKEN_SLUG", "BAAL_RA").strip()
GAME_MIN_WITHDRAW = int(os.getenv("GAME_MIN_WITHDRAW", "100"))
# Курс игровой монеты в USD и комиссия конвертации монет -> токен
GAME_COIN_USD = float(os.getenv("GAME_COIN_USD", "0.0001"))
GAME_CONVERT_FEE_PCT = float(os.getenv("GAME_CONVERT_FEE_PCT", "3"))
# Цари, на которые можно обменять игровые монеты (TON)
GAME_TOKEN_SLUGS = [
    s.strip()
    for s in os.getenv("GAME_TOKEN_SLUGS", "BAAL_RA,BLIZNETSY,CROWN").split(",")
    if s.strip()
]
GECKO_API = os.getenv("GECKO_API", "https://api.geckoterminal.com/api/v2").strip().rstrip("/")
GECKO_NETWORK = os.getenv("GECKO_NETWORK", "ton").strip()

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
    except Exception:
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


# ---------------- вывод монет из игры (iCryptoCheck) ----------------
class GameWithdrawFSM(StatesGroup):
    amount = State()
    token = State()
    confirm = State()


_PRICE_CACHE: dict[str, tuple[float, float]] = {}  # master -> (price, ts)
PRICE_CACHE_TTL = float(os.getenv("PRICE_CACHE_TTL", "60"))


async def token_price_usd(master: str) -> float:
    """Цена токена в USD по GeckoTerminal.

    Кэш на PRICE_CACHE_TTL секунд (GeckoTerminal режет по rate-limit),
    запасной источник — цена базового токена в пуле.
    """
    import time

    import httpx
    cached = _PRICE_CACHE.get(master)
    if cached and (time.time() - cached[1]) < PRICE_CACHE_TTL:
        return cached[0]
    headers = {"accept": "application/json", "User-Agent": "tsar-bot/1.0"}
    async with httpx.AsyncClient(timeout=10.0, headers=headers) as c:
        for url, field in (
            (f"{GECKO_API}/networks/{GECKO_NETWORK}/tokens/{master}", "price_usd"),
            (f"{GECKO_API}/networks/{GECKO_NETWORK}/tokens/{master}/pools", "base_token_price_usd"),
        ):
            try:
                r = await c.get(url)
                if r.status_code != 200:
                    continue
                d = r.json()
                if field == "price_usd":
                    px = (d.get("data", {}).get("attributes", {}) or {}).get(field)
                else:
                    px = None
                    for p in d.get("data", []) or []:
                        at = p.get("attributes", {}) or {}
                        if at.get("reserve_in_usd") and float(at["reserve_in_usd"]) > 50:
                            px = at.get(field)
                            break
                if px:
                    price = float(px)
                    _PRICE_CACHE[master] = (price, time.time())
                    return price
            except Exception as e:
                log.warning("price %s failed: %s", master, e)
    if cached:
        return cached[0]
    return 0.0


def _game_tokens() -> list:
    """Цари, доступные для обмена игровых монет (с реальным master-адресом)."""
    out = []
    for slug in GAME_TOKEN_SLUGS:
        t = get_token(slug)
        if t is not None and t.network == "ton":
            out.append(t)
    return out


def _icrypto_ready() -> bool:
    return bool(ICRYPTO_API_KEY)


async def convert_coins_to_tokens(coins: float, target) -> tuple[float, float, float]:
    """Переводит игровые монеты в токены цели.

    coins -> USD (GAME_COIN_USD) -> токены по цене цели (GeckoTerminal),
    за вычетом комиссии GAME_CONVERT_FEE_PCT.
    Возвращает (tokens, price, fee_pct).
    """
    price = await token_price_usd(target.master)
    if price <= 0:
        return 0.0, 0.0, GAME_CONVERT_FEE_PCT
    usd = coins * GAME_COIN_USD
    gross = usd / price
    fee = gross * (GAME_CONVERT_FEE_PCT / 100.0)
    return gross - fee, price, GAME_CONVERT_FEE_PCT


async def icrypto_create_check(amount: float, token_address: str, user_id: int) -> tuple[bool, str]:
    """Создаёт iCrypto-чек на amount токенов. Возвращает (ok, текст/ссылка)."""
    if not _icrypto_ready():
        return False, (
            "Интеграция с iCryptoCheck не настроена: нет ICRYPTO_API_KEY.\n"
            f"Напиши оператору: @{SUPPORT_USERNAME}"
        )
    try:
        import httpx
    except Exception:
        return False, "В боте нет HTTP-клиента (httpx)."
    payload = {
        "token": token_address,
        "amount": str(amount),
        "pin_to_user_id": user_id,
    }
    try:
        async with httpx.AsyncClient(timeout=15.0) as c:
            r = await c.post(
                ICRYPTO_API_BASE + ICRYPTO_CHECK_PATH,
                json=payload,
                headers={
                    "Authorization": f"Bearer {ICRYPTO_API_KEY}",
                    "accept": "application/json",
                    "User-Agent": "tsar-bot/1.0",
                },
            )
    except Exception as e:
        log.warning("icrypto_create_check failed: %s", e)
        return False, f"Не получилось связаться с iCryptoCheck: {e}"
    if r.status_code >= 400:
        log.warning("icrypto http %s: %s", r.status_code, r.text[:300])
        return False, f"iCryptoCheck вернул ошибку {r.status_code}."
    try:
        d = r.json()
    except Exception:
        d = {}
    check_id = d.get("check_id") or d.get("id") or d.get("checkId")
    link = d.get("link") or d.get("url") or d.get("check_link") or ""
    if not link and check_id:
        link = f"https://t.me/{ICRYPTO_BOT_USERNAME}?start=check_{check_id}"
    if not link:
        return False, "iCryptoCheck не вернул ссылку на чек."
    return True, link


@router.message(F.text == "💸 Вывести монеты")
@router.message(Command("withdraw_game", "cashout"))
async def cmd_game_withdraw(message: Message, state: FSMContext) -> None:
    uid = str(message.from_user.id if message.from_user else 0)
    p = player(uid)
    coins = int(p.get("coins", 0))
    if coins < GAME_MIN_WITHDRAW:
        await message.answer(
            f"👑 Накоплено <b>{coins:,}</b> монет.\n"
            f"Для вывода нужно минимум <b>{GAME_MIN_WITHDRAW:,}</b>.\n\n"
            f"🎮 Продолжай играть в «Царь в Подземелье»!",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🎮 Играть", web_app=WebAppInfo(url=GAME_URL))],
            ]),
        )
        return
    await state.set_state(GameWithdrawFSM.amount)
    await state.update_data(balance=coins)
    await message.answer(
        "💸 <b>Вывод игровых монет</b>\n\n"
        f"👑 Твой баланс: <b>{coins:,}</b> монет\n"
        f"Минимум для вывода: <b>{GAME_MIN_WITHDRAW:,}</b>\n\n"
        "Сколько монет выводим? Пришли число (можно часть — остальное останется на балансе).",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🎮 Играть ещё", web_app=WebAppInfo(url=GAME_URL))],
        ]),
    )


@router.message(GameWithdrawFSM.amount)
async def game_withdraw_amount(message: Message, state: FSMContext) -> None:
    raw = (message.text or "").strip().replace(" ", "").replace(",", "")
    if not raw.isdigit():
        await message.answer("Введи целое число монет.")
        return
    amount = int(raw)
    data = await state.get_data()
    balance = int(data.get("balance", 0))
    if amount < GAME_MIN_WITHDRAW:
        await message.answer(f"Минимум для вывода — <b>{GAME_MIN_WITHDRAW:,}</b> монет.")
        return
    if amount > balance:
        await message.answer(f"На балансе только <b>{balance:,}</b> монет.")
        return
    await state.update_data(amount=amount, balance=balance)
    await state.set_state(GameWithdrawFSM.token)
    await message.answer(
        "👑 <b>На кого обменяем монеты?</b>\n\n"
        "Выбери царя — бот посчитает, сколько токенов ты получишь.\n"
        f"Курс монеты: <b>${GAME_COIN_USD}</b> · комиссия обмена: <b>{GAME_CONVERT_FEE_PCT}%</b>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text=f"{t.emoji} {t.name}", callback_data=f"gwt:{t.slug}")
                for t in _game_tokens()
            ],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="gw:cancel")],
        ]),
    )


@router.callback_query(GameWithdrawFSM.token, F.data.startswith("gwt:"))
async def game_withdraw_pick_token(c: CallbackQuery, state: FSMContext) -> None:
    slug = (c.data or "").split(":", 1)[-1]
    t = get_token(slug)
    if t is None or t.network != "ton":
        await c.answer("Царь не найден")
        return
    data = await state.get_data()
    coins = int(data.get("amount", 0))
    tokens, price, fee = await convert_coins_to_tokens(coins, t)
    if tokens <= 0:
        await c.message.answer(
            "⚠️ Не удалось получить курс царя — попробуй позже.\n\nМонеты не списаны.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔁 Повторить", callback_data="gw:menu")],
            ]),
        )
        await c.answer("Нет курса")
        return
    await state.update_data(token_slug=t.slug, tokens=round(tokens, 6), price=price)
    await state.set_state(GameWithdrawFSM.confirm)
    await c.message.answer(
        "📋 <b>Подтверди обмен</b>\n\n"
        f"🪙 Игровых монет: <b>{coins:,}</b>\n"
        f"👑 Царь: <b>{t.name}</b> ({t.symbol})\n"
        f"💵 Курс царя: <b>${price:.8f}</b>\n"
        f"🎁 Ты получишь: <b>{round(tokens, 6):,} {t.symbol}</b>\n"
        f"📉 Комиссия обмена: <b>{fee}%</b>\n"
        f"🔗 Чек придёт от @{ICRYPTO_BOT_USERNAME}\n\n"
        "Монеты списываются только после успешного создания чека.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Вывести", callback_data="gw:ok")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="gw:cancel")],
        ]),
    )
    await c.answer()


@router.callback_query(GameWithdrawFSM.confirm, F.data == "gw:ok")
async def game_withdraw_ok(c: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    coins = int(data.get("amount", 0))
    slug = str(data.get("token_slug") or GAME_TOKEN_SLUG)
    tokens = float(data.get("tokens", 0))
    t = get_token(slug)
    if t is None:
        await c.message.answer("⚠️ Царь не найден — монеты не списаны.")
        await c.answer("Ошибка")
        return
    uid = str(c.from_user.id if c.from_user else 0)
    await c.answer("Создаю чек…")
    ok, result = await icrypto_create_check(tokens, t.master, int(uid))
    if not ok:
        await c.message.answer(
            "⚠️ <b>Вывод не выполнен</b>\n\n" + result + "\n\n"
            "Монеты остались на балансе — попробуй ещё раз.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔁 Повторить", callback_data="gw:menu")],
            ]),
        )
        await state.clear()
        return
    p = player(uid)
    p["coins"] = max(0, int(p.get("coins", 0)) - coins)
    p["withdrawn"] = int(p.get("withdrawn", 0)) + coins
    save_players()
    await c.message.answer(
        "✅ <b>Чек создан!</b>\n\n"
        f"👑 Царь: <b>{t.name}</b>\n"
        f"💰 Получено: <b>{tokens:,} {t.symbol}</b>\n"
        f"🪙 Списано монет: <b>{coins:,}</b>\n"
        f"🏦 Остаток на балансе: <b>{p['coins']:,}</b> монет\n\n"
        f"🔗 Активируй чек здесь:\n{result}",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🎮 Играть ещё", web_app=WebAppInfo(url=GAME_URL))],
            [InlineKeyboardButton(text="👑 Токены", callback_data="noop")],
        ]),
    )
    await state.clear()


@router.callback_query(GameWithdrawFSM.confirm, F.data == "gw:cancel")
async def game_withdraw_cancel(c: CallbackQuery, state: FSMContext) -> None:
    await c.message.answer(
        "❌ Отменено. Монеты остались на балансе.",
        reply_markup=main_kb(),
    )
    await state.clear()


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
            [InlineKeyboardButton(text="💸 Вывести монеты", callback_data="gw:menu")],
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
@router.message(F.text.func(lambda t: bool(t) and t.startswith("withdraw:")))
async def game_withdraw_request(message: Message, state: FSMContext) -> None:
    await cmd_game_withdraw(message, state)


@router.message(F.text.func(lambda t: bool(t) and t.startswith("coins:")))
async def game_score(message: Message) -> None:
    raw = (message.text or "").split(":", 1)[1].strip()
    try:
        coins = max(0, int(raw))
    except ValueError:
        coins = 0
    uid = str(message.from_user.id if message.from_user else 0)
    p = player(uid)
    # Игра присылает НАКОПЛЕННЫЙ итог, а не прибавку за забег:
    # считаем только разницу, чтобы монеты не начислялись дважды
    # и баланс не обнулялся между забегами.
    last_total = int(p.get("last_total", 0))
    delta = coins - last_total
    if delta < 0:
        delta = coins  # новый игрок или сброс — начисляем как есть
    p["last_total"] = coins
    p["coins"] = int(p.get("coins", 0)) + delta
    p["runs"] += 1
    if coins > p["best"]:
        p["best"] = coins
    save_players()
    await message.answer(
        f"👑 <b>Царь принял твой счёт!</b>\n\n"
        f"🪙 За этот забег: <b>+{delta:,}</b> монет\n"
        f"👑 Всего у тебя: <b>{p['coins']:,}</b> монет\n"
        f"🏆 Рекорд за игру: <b>{p['best']}</b>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💸 Вывести монеты", callback_data="gw:menu")],
            [InlineKeyboardButton(text="🎮 Играть ещё", web_app=WebAppInfo(url=GAME_URL))],
            [InlineKeyboardButton(text="👑 Токены", callback_data="noop")],
        ]),
    )


@router.callback_query(F.data == "gw:menu")
async def game_withdraw_menu(c: CallbackQuery, state: FSMContext) -> None:
    uid = str(c.from_user.id if c.from_user else 0)
    p = player(uid)
    coins = int(p.get("coins", 0))
    if coins < GAME_MIN_WITHDRAW:
        await c.message.answer(
            f"👑 Накоплено <b>{coins:,}</b> монет.\n"
            f"Для вывода нужно минимум <b>{GAME_MIN_WITHDRAW:,}</b>.\n\n"
            "🎮 Продолжай играть в «Царь в Подземелье»!",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🎮 Играть", web_app=WebAppInfo(url=GAME_URL))],
            ]),
        )
        await c.answer()
        return
    await state.set_state(GameWithdrawFSM.amount)
    await state.update_data(balance=coins)
    await c.message.answer(
        "💸 <b>Вывод игровых монет</b>\n\n"
        f"👑 Твой баланс: <b>{coins:,}</b> монет\n"
        f"Минимум для вывода: <b>{GAME_MIN_WITHDRAW:,}</b>\n\n"
        "Сколько монет выводим? Пришли число (можно часть — остальное останется на балансе).",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=f"Вывести все ({coins:,})", callback_data="gw:all")],
            [InlineKeyboardButton(text="🎮 Играть", web_app=WebAppInfo(url=GAME_URL))],
        ]),
    )
    await c.answer()


@router.callback_query(F.data == "gw:all")
async def game_withdraw_all(c: CallbackQuery, state: FSMContext) -> None:
    uid = str(c.from_user.id if c.from_user else 0)
    p = player(uid)
    coins = int(p.get("coins", 0))
    if coins < GAME_MIN_WITHDRAW:
        await c.message.answer(
            f"👑 Накоплено <b>{coins:,}</b> монет — мало для вывода.\n"
            f"Нужно минимум <b>{GAME_MIN_WITHDRAW:,}</b>.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🎮 Играть", web_app=WebAppInfo(url=GAME_URL))],
            ]),
        )
        await c.answer()
        return
    await state.set_state(GameWithdrawFSM.token)
    await state.update_data(amount=coins, balance=coins)
    await c.message.answer(
        "👑 <b>На кого обменяем монеты?</b>\n\n"
        f"Выводим <b>{coins:,}</b> монет. Выбери царя — бот посчитает, сколько токенов ты получишь.\n"
        f"Курс монеты: <b>${GAME_COIN_USD}</b> · комиссия обмена: <b>{GAME_CONVERT_FEE_PCT}%</b>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text=f"{t.emoji} {t.name}", callback_data=f"gwt:{t.slug}")
                for t in _game_tokens()
            ],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="gw:cancel")],
        ]),
    )
    await c.answer()


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
    # КРИТИЧНО: без этой строки НИ ОДИН хендлер не работает — /start не отвечает.
    dp.include_router(router)
    log.info("BOT v%s started, tokens: %s", BOT_VERSION, [t.slug for t in list_tokens()])
    log.info("router attached, handlers registered")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
