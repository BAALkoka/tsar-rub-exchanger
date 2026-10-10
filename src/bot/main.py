"""Telegram-бот обменника ЦАРЬ → RUB. v2026-10-10-013."""
from __future__ import annotations
import asyncio, json as J, logging, os, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from aiogram import Bot, Dispatcher, Router, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton, WebAppInfo, Message, CallbackQuery
from api.payouts.tokens import list_tokens, get_token
from api.payouts.price_feed import PriceFeed
from api.payouts.p2p import P2PClient

BOT_VERSION = "2026-10-10-013"
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
logging.basicConfig(level=logging.INFO)
log = logging.getLogger("tsar.bot")
if not BOT_TOKEN:
    raise RuntimeError("TELEGRAM_BOT_TOKEN is required")
SITE_URL = os.getenv("SITE_URL", "https://tsar-rub-lt87ahb9.agent.mira.tg/").strip()
GAME_URL = os.getenv("GAME_URL", "https://tsar-game-lt87ahb9.agent.mira.tg/").strip()
NL = "\n"

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())
router = Router()

HISTORY = {}
HF = Path("/tmp/tsar_history.json")

def ld():
    if HF.exists():
        try:
            for k, v in J.loads(HF.read_text(encoding="utf-8")).items():
                HISTORY[int(k)] = v
        except Exception as e:
            log.warning("ld: %s", e)

def sv():
    try:
        HF.write_text(J.dumps({str(k): v for k, v in HISTORY.items()}, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as e:
        log.warning("sv: %s", e)

def ah(uid, slug, amt, rub, m, st):
    HISTORY.setdefault(uid, []).append({"ts": time.time(), "slug": slug, "amount": amt, "rub": rub, "method": m, "status": st})
    HISTORY[uid] = HISTORY[uid][-10:]
    sv()

feeds = {t.slug: PriceFeed(token_master=t.master, token_pool=t.pool, pool_label=t.pool_label, manual_rate=1.0) for t in list_tokens()}
p2p = P2PClient()
log.info("BOT v%s, feeds: %s", BOT_VERSION, list(feeds.keys()))

class W(StatesGroup):
    tok = State()
    amt = State()

def mk():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="💰 Курс"), KeyboardButton(text="💸 Продать")],
        [KeyboardButton(text="📊 Калькулятор"), KeyboardButton(text="📜 История")],
        [KeyboardButton(text="🌐 Сайт"), KeyboardButton(text="🎮 Игра")],
        [KeyboardButton(text="♻️ /start")],
    ], resize_keyboard=True)

def site_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🌐", url=SITE_URL), InlineKeyboardButton(text="🎮", web_app=WebAppInfo(url=GAME_URL))],
        [InlineKeyboardButton(text="🤖", url="https://t.me/BAAL_NIK_BOT"), InlineKeyboardButton(text="💬", url="https://t.me/BAAL_NIK_chat")],
    ])

def menu():
    b = [[InlineKeyboardButton(text=t.emoji + " " + t.symbol + " — " + t.name, callback_data="token:" + t.slug)] for t in list_tokens()]
    b.append([InlineKeyboardButton(text="🌐 Сайт", url=SITE_URL)])
    return InlineKeyboardMarkup(inline_keyboard=b)

@router.message(CommandStart())
@router.message(F.text == "♻️ /start")
async def start(m: Message):
    t = ("👑 <b>ЦАРЬ Обменник</b> <i>v" + BOT_VERSION + "</i>" + NL + NL + "3 серии ЦАРЬ → RUB." + NL + "💳 P2P / 📱 СБП." + NL + NL + "🌐 " + SITE_URL + NL + "🎮 " + GAME_URL + NL + NL + "👇 Кнопки ↓")
    await m.answer(t, reply_markup=site_kb())
    await m.answer("👇 Меню:", reply_markup=mk())

@router.message(F.text == "💰 Курс")
async def rate(m: Message):
    L = ["💱 <b>Курс</b> <i>v" + BOT_VERSION + "</i>" + NL]
    for t in list_tokens():
        try:
            q = await feeds[t.slug].quote(1_000_000)
            L.append(t.emoji + " <b>" + t.symbol + "</b>: 1M = <b>" + f"{q.rub_amount:,.4f}" + " ₽</b>" if q.ok else t.emoji + " " + t.symbol + ": —")
        except Exception:
            L.append(t.emoji + " " + t.symbol + ": err")
    await m.answer(NL.join(L), reply_markup=mk())

@router.message(F.text == "💸 Продать")
async def sell(m: Message):
    await m.answer("⤵ Выбери серию:", reply_markup=menu())

@router.message(F.text == "📊 Калькулятор")
async def calc(m: Message):
    await m.answer("<code>/sell 1000000</code>", reply_markup=mk())

@router.message(F.text == "📜 История")
async def hist(m: Message):
    uid = m.from_user.id if m.from_user else 0
    its = HISTORY.get(uid, [])
    if not its:
        await m.answer("📜 <b>История</b>" + NL + NL + "Пусто. Нажми <b>💸 Продать</b>.", reply_markup=mk())
        return
    L = ["📜 <b>История</b> <i>v" + BOT_VERSION + "</i>" + NL]
    for it in reversed(its):
        tk = next((x for x in list_tokens() if x.slug == it["slug"]), None)
        sm = tk.symbol if tk else it["slug"]
        em = tk.emoji if tk else "👑"
        ts = time.strftime("%d.%m %H:%M", time.localtime(it["ts"]))
        L.append(em + " <b>" + sm + "</b> — " + f"{it['amount']:,}" + " = <b>" + f"{it['rub']:,.2f}" + " ₽</b>" + NL + "   💳 " + it["method"] + " · " + it["status"] + " · " + ts)
    await m.answer(NL + NL.join(L), reply_markup=mk())

@router.message(F.text == "🌐 Сайт")
async def sit(m: Message):
    await m.answer("🌐 " + SITE_URL, reply_markup=mk())

@router.message(F.text == "🎮 Игра")
async def game(m: Message):
    await m.answer("🎮 " + GAME_URL, reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🎮", web_app=WebAppInfo(url=GAME_URL))]]))

@router.message(Command("sell", "withdraw", "quote"))
async def cmd_sell(m: Message, command: Command):
    a = command.args
    uid = m.from_user.id if m.from_user else 0
    if not a or not a[0].isdigit():
        await m.answer("<code>/sell 1000000</code> (мин 250k).", reply_markup=mk())
        return
    amt = int(a[0])
    if amt < 250_000:
        await m.answer("❌ мин 250k", reply_markup=mk())
        return
    t = list_tokens()[0]
    try:
        q = await feeds[t.slug].quote(amt)
        if not q.ok:
            await m.answer("⚠️ Курс —", reply_markup=mk())
            return
        rub = q.rub_amount
        ah(uid, t.slug, amt, rub, "СБП", "✅")
        await m.answer("👑 <b>" + t.symbol + "</b> → <b>" + f"{rub:,.2f}" + " ₽</b>" + NL + "📤 " + f"{amt:,}" + " · 💳 СБП" + NL + NL + "📱 <code>+79285448941</code>" + NL + "💳 WalletBot", reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📱 СБП", url="https://t.me/BAAL_NIK_BOT?start=sbp")],
            [InlineKeyboardButton(text="💳 P2P", url="https://t.me/BAAL_NIK_BOT?start=p2p")],
            [InlineKeyboardButton(text="📜 История", callback_data="show_history")],
        ]))
    except Exception as e:
        log.error("sell: %s", e)
        await m.answer("❌", reply_markup=mk())

@router.callback_query(F.data == "show_history")
async def hist_cb(c: CallbackQuery):
    uid = c.from_user.id
    its = HISTORY.get(uid, [])
    if not its:
        await c.message.answer("📜 Пусто.")
        await c.answer()
        return
    L = ["📜 <b>История</b> <i>v" + BOT_VERSION + "</i>" + NL]
    for it in reversed(its):
        ts = time.strftime("%d.%m %H:%M", time.localtime(it["ts"]))
        L.append("• " + f"{it['amount']:,}" + " = " + f"{it['rub']:,.2f}" + " ₽ · " + it["method"] + " · " + it["status"] + " · " + ts)
    await c.message.answer(NL.join(L))
    await c.answer()

@router.callback_query(F.data.startswith("token:"))
async def tok_cb(c: CallbackQuery, st: FSMContext):
    sl = c.data.split(":", 1)[1]
    await st.set_state(W.amt)
    await st.update_data(tok=sl)
    t = get_token(sl)
    await c.message.answer("👑 <b>" + t.symbol + " " + t.name + "</b>" + NL + "<code>/sell " + sl + " 1000000</code>")
    await c.answer()

async def main():
    ld()
    log.info("start v%s", BOT_VERSION)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
