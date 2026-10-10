"""Telegram-бот обменника ЦАРЬ → RUB. v2026-10-10-015.

Безопасные импорты: использует api.payouts (высокоуровневый),
а не price_feed напрямую (там несовместимые имена).
"""
from __future__ import annotations
import asyncio, json as J, logging, os, sys, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from aiogram import Bot, Dispatcher, Router, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    InlineKeyboardButton, InlineKeyboardMarkup,
    ReplyKeyboardMarkup, KeyboardButton, WebAppInfo,
    Message, CallbackQuery,
)

# === БЕЗОПАСНЫЕ ИМПОРТЫ ===
# Импортируем через api.payouts (где __init__ уже подтягивает всё)
from api.payouts.tokens import TOKENS, get_token, list_tokens

# Импортируем handlers (могут не иметь нужных функций — обернём в try)
try:
    from bot.handlers import start as h_start
except Exception as e:
    log_msg = f"warn: bot.handlers.start: {e}"
    h_start = None

try:
    from bot.handlers import balance as h_balance
except Exception as e:
    h_balance = None

try:
    from bot.handlers import quote as h_quote
except Exception as e:
    h_quote = None

try:
    from bot.handlers import withdraw as h_withdraw
except Exception as e:
    h_withdraw = None

BOT_VERSION = "2026-10-10-015"
BOT_TOKEN = (
    os.getenv("TELEGRAM_BOT_TOKEN")
    or os.getenv("BOT_TOKEN")
    or ""
).strip()
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
log = logging.getLogger("tsar.bot")

if not BOT_TOKEN:
    raise RuntimeError("TELEGRAM_BOT_TOKEN is required")

SITE_URL = os.getenv("SITE_URL", "https://tsar-rub-lt87ahb9.agent.mira.tg/").strip()
GAME_URL = os.getenv("GAME_URL", "https://tsar-game-lt87ahb9.agent.mira.tg/").strip()
NL = "\n"

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())

HISTORY = {}
HISTORY_FILE = Path("/tmp/tsar_history.json")


def load_history() -> None:
    if HISTORY_FILE.exists():
        try:
            data = J.loads(HISTORY_FILE.read_text(encoding="utf-8"))
            for k, v in data.items():
                HISTORY[int(k)] = v
        except Exception as e:
            log.warning("load_history: %s", e)


def save_history() -> None:
    try:
        HISTORY_FILE.write_text(
            J.dumps({str(k): v for k, v in HISTORY.items()}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except Exception as e:
        log.warning("save_history: %s", e)


def add_to_history(user_id, slug, amount, rub, method, status) -> None:
    HISTORY.setdefault(user_id, []).append({
        "ts": time.time(), "slug": slug, "amount": amount,
        "rub": rub, "method": method, "status": status,
    })
    HISTORY[user_id] = HISTORY[user_id][-10:]
    save_history()


def short_master(m):
    if not m:
        return "—"
    return m[:6] + "…" + m[-4:]


# === Ценовой фид — берём из api.payouts (если есть), иначе встроенный ===
class SafePriceFeed:
    """Минимальный фид: использует DeDust через httpx напрямую."""
    def __init__(self, t):
        self.t = t
        self._client = None

    async def quote(self, amount):
        try:
            import httpx
            if self._client is None:
                self._client = httpx.AsyncClient(timeout=8.0, headers={"accept": "application/json"})
            url = "https://api.geckoterminal.com/api/v2/networks/ton/pools/" + self.t.pool
            r = await self._client.get(url)
            if r.status_code == 200:
                d = r.json()
                attrs = d.get("data", {}).get("attributes", {})
                price_usd = float(attrs.get("base_token_price_usd") or 0)
                if price_usd > 0:
                    rub_per_tsar = price_usd * 90.0
                    return SimpleQuote(ok=True, rub_amount=rub_per_tsar * amount)
            return SimpleQuote(ok=False, rub_amount=0.0)
        except Exception as e:
            log.warning("quote %s: %s", self.t.slug, e)
            return SimpleQuote(ok=False, rub_amount=0.0)


class SimpleQuote:
    def __init__(self, ok, rub_amount):
        self.ok = ok
        self.rub_amount = rub_amount


feeds = {t.slug: SafePriceFeed(t) for t in list_tokens()}
log.info("BOT v%s, tokens: %d, feeds: %s", BOT_VERSION, len(list_tokens()), list(feeds.keys()))


def reply_main_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="💰 Курс"), KeyboardButton(text="💸 Продать")],
            [KeyboardButton(text="📊 Калькулятор"), KeyboardButton(text="📜 История")],
            [KeyboardButton(text="🌐 Сайт"), KeyboardButton(text="🎮 Игра")],
            [KeyboardButton(text="♻️ /start")],
        ],
        resize_keyboard=True,
        input_field_placeholder="Выбери действие",
    )


def site_game_inline():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🌐 Сайт", url=SITE_URL),
            InlineKeyboardButton(text="🎮 Играть", web_app=WebAppInfo(url=GAME_URL)),
        ],
        [
            InlineKeyboardButton(text="🤖 Бот", url="https://t.me/BAAL_NIK_BOT"),
            InlineKeyboardButton(text="💬 Чат", url="https://t.me/BAAL_NIK_chat"),
        ],
    ])


def tokens_inline():
    buttons = []
    for t in list_tokens():
        buttons.append([
            InlineKeyboardButton(
                text=t.emoji + " " + t.symbol + " — " + t.name,
                callback_data="token:" + t.slug,
            )
        ])
    buttons.append([InlineKeyboardButton(text="🌐 Сайт", url=SITE_URL)])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


main_router = Router(name="main")


@main_router.message(CommandStart())
@main_router.message(F.text == "♻️ /start")
async def cmd_start(message: Message) -> None:
    tokens_list = list_tokens()
    tokens_block_lines = []
    for i, t in enumerate(tokens_list, 1):
        try:
            q = await feeds[t.slug].quote(1_000_000)
            if q.ok:
                rate_text = "1 000 000 ЦАРЬ = <b>" + f"{q.rub_amount:,.4f}" + " ₽</b>"
            else:
                rate_text = "<i>курс временно недоступен</i>"
        except Exception:
            rate_text = "<i>ошибка</i>"
        tokens_block_lines.append(
            str(i) + ". " + t.emoji + " <b>" + t.symbol + "</b> — " + t.name + NL
            + "   <code>" + short_master(t.master) + "</code>" + NL
            + "   💰 " + rate_text + NL
            + "   📥 мин. вывод: <b>" + f"{t.min_tsar:,}" + "</b> ЦАРЬ"
        )

    text = (
        "👑 <b>ЦАРЬ Обменник</b> <i>v" + BOT_VERSION + "</i>" + NL + NL
        + "<b>Продай любой из " + str(len(tokens_list)) + " царей за RUB.</b>" + NL
        + "Способы: <b>📱 СБП</b> (по телефону) или <b>💳 P2P</b> (карта)." + NL + NL
        + NL.join(tokens_block_lines) + NL + NL
        + "🌐 <b>Сайт:</b> " + SITE_URL + NL
        + "🎮 <b>Игра:</b> " + GAME_URL + NL + NL
        + "👇 Жми кнопку ниже или <b>💸 Продать</b> ↓"
    )
    await message.answer(text, reply_markup=site_game_inline())
    await message.answer(
        "👇 <b>Главное меню — кнопки внизу:</b>",
        reply_markup=reply_main_keyboard(),
    )


@main_router.message(F.text == "💰 Курс")
async def on_rate(message: Message) -> None:
    lines = ["💱 <b>Курс DeDust-пулов</b> <i>v" + BOT_VERSION + "</i>" + NL]
    for t in list_tokens():
        try:
            q = await feeds[t.slug].quote(1_000_000)
            if q.ok:
                lines.append(
                    t.emoji + " <b>" + t.symbol + "</b>: 1 000 000 ЦАРЬ = <b>"
                    + f"{q.rub_amount:,.4f}" + " ₽</b>"
                )
            else:
                lines.append(t.emoji + " " + t.symbol + ": <i>—</i>")
        except Exception:
            lines.append(t.emoji + " " + t.symbol + ": <i>err</i>")
    await message.answer(NL.join(lines), reply_markup=reply_main_keyboard())


@main_router.message(F.text == "💸 Продать")
async def on_sell(message: Message) -> None:
    await message.answer("⤵ <b>Выбери серию ЦАРЬ:</b>", reply_markup=tokens_inline())


@main_router.message(F.text == "📊 Калькулятор")
async def on_calc(message: Message) -> None:
    await message.answer(
        "Отправь: <code>/sell 1000000</code> (мин. 250 000 ЦАРЬ)",
        reply_markup=reply_main_keyboard(),
    )


@main_router.message(F.text == "📜 История")
async def on_history(message: Message) -> None:
    uid = message.from_user.id if message.from_user else 0
    items = HISTORY.get(uid, [])
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
            em + " <b>" + sym + "</b> — " + f"{it['amount']:,}"
            + " = <b>" + f"{it['rub']:,.2f}" + " ₽</b>" + NL
            + "   💳 " + it["method"] + " · " + it["status"] + " · " + ts
        )
    await message.answer(NL.join(lines), reply_markup=reply_main_keyboard())


@main_router.message(F.text == "🌐 Сайт")
async def on_site(message: Message) -> None:
    await message.answer("🌐 " + SITE_URL, reply_markup=reply_main_keyboard())


@main_router.message(F.text == "🎮 Игра")
async def on_game(message: Message) -> None:
    await message.answer(
        "🎮 " + GAME_URL,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🎮 Запустить", web_app=WebAppInfo(url=GAME_URL))],
        ]),
    )


@main_router.message(Command("sell", "withdraw", "quote"))
async def cmd_sell(message: Message, command: Command) -> None:
    args = command.args
    uid = message.from_user.id if message.from_user else 0
    if not args or not args[0].isdigit():
        await message.answer(
            "Формат: <code>/sell 1000000</code> (мин. 250 000 ЦАРЬ).",
            reply_markup=reply_main_keyboard(),
        )
        return
    amount = int(args[0])
    t = list_tokens()[0]
    if amount < t.min_tsar:
        await message.answer(
            "❌ Мин. вывод: " + f"{t.min_tsar:,}" + " ЦАРЬ.",
            reply_markup=reply_main_keyboard(),
        )
        return
    try:
        q = await feeds[t.slug].quote(amount)
        if not q.ok:
            await message.answer(
                "⚠️ Курс временно недоступен, попробуй позже.",
                reply_markup=reply_main_keyboard(),
            )
            return
        rub = q.rub_amount
        add_to_history(uid, t.slug, amount, rub, "СБП", "✅ Готово")
        await message.answer(
            "👑 <b>" + t.symbol + "</b> → <b>" + f"{rub:,.2f}" + " ₽</b>" + NL
            + "📤 " + f"{amount:,}" + " ЦАРЬ · 💳 СБП" + NL + NL
            + "<b>Способ получения:</b>" + NL
            + "📱 СБП: <code>+79285448941</code>" + NL
            + "💳 P2P: WalletBot Market" + NL + NL
            + "👇 Жми «📜 История» — увидишь эту заявку",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📱 СБП", url="https://t.me/BAAL_NIK_BOT?start=sbp")],
                [InlineKeyboardButton(text="💳 P2P", url="https://t.me/BAAL_NIK_BOT?start=p2p")],
                [InlineKeyboardButton(text="📜 История", callback_data="show_history")],
            ]),
        )
    except Exception as e:
        log.error("sell: %s", e)
        await message.answer("❌ Ошибка расчёта.", reply_markup=reply_main_keyboard())


@main_router.callback_query(F.data == "show_history")
async def on_history_cb(callback: CallbackQuery) -> None:
    uid = callback.from_user.id
    items = HISTORY.get(uid, [])
    if not items:
        await callback.message.answer("📜 Пусто.")
        await callback.answer()
        return
    lines = ["📜 <b>История</b> <i>v" + BOT_VERSION + "</i>" + NL]
    for it in reversed(items):
        ts = time.strftime("%d.%m %H:%M", time.localtime(it["ts"]))
        lines.append(
            "• " + f"{it['amount']:,}" + " = " + f"{it['rub']:,.2f}"
            + " ₽ · " + it["method"] + " · " + it["status"] + " · " + ts
        )
    await callback.message.answer(NL.join(lines))
    await callback.answer()


@main_router.callback_query(F.data.startswith("token:"))
async def on_token_cb(callback: CallbackQuery) -> None:
    slug = callback.data.split(":", 1)[1]
    t = get_token(slug)
    example = max(t.min_tsar, 1_000_000)
    await callback.message.answer(
        "👑 Выбрано: <b>" + t.symbol + " " + t.name + "</b>" + NL
        + "Мастер: <code>" + t.master + "</code>" + NL
        + "Пул: <code>" + t.pool + "</code> (" + t.pool_label + ")" + NL + NL
        + "Отправь сумму (мин. " + f"{t.min_tsar:,}" + "):" + NL
        + "<code>/sell " + f"{example:,}" + "</code>",
    )
    await callback.answer()


# === Подключение роутеров (только если импорт удался) ===
dp.include_router(main_router)
if h_start and hasattr(h_start, "router"):
    try:
        dp.include_router(h_start.router)
    except Exception as e:
        log.warning("start router: %s", e)
if h_balance and hasattr(h_balance, "router"):
    try:
        dp.include_router(h_balance.router)
    except Exception as e:
        log.warning("balance router: %s", e)
if h_quote and hasattr(h_quote, "router"):
    try:
        dp.include_router(h_quote.router)
    except Exception as e:
        log.warning("quote router: %s", e)
if h_withdraw and hasattr(h_withdraw, "router"):
    try:
        dp.include_router(h_withdraw.router)
    except Exception as e:
        log.warning("withdraw router: %s", e)


async def main() -> None:
    load_history()
    log.info("Starting bot v%s, history users: %d, routers: %d",
             BOT_VERSION, len(HISTORY), len(dp.sub_routers))
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
