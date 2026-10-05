"""Telegram-бот обменника ЦАРЬ → RUB.

3 серии ЦАРЬ, у каждого свой DeDust-пул и кнопка курса.

Версия: 2026-10-05-001 — PriceFeed с quote() для всех 3 царей.
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
    Message,
    CallbackQuery,
)

from api.payouts.tokens import (
    TOKENS,
    DEFAULT_TOKEN,
    get_token,
    list_tokens,
    find_by_master,
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
from api.payouts.ton_watcher import TonWatcher, IncomingTransfer
from api.payouts.models import PayoutMethod

BOT_VERSION = "2026-10-05-001"
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("tsar.bot")

if not BOT_TOKEN:
    raise RuntimeError("TELEGRAM_BOT_TOKEN не задан")

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())
router = Router()

# === Отдельный PriceFeed для каждого царя (свой DeDust-пул) ===
feeds: dict[str, PriceFeed] = {
    t.slug: PriceFeed(token_master=t.master, token_pool=t.pool, pool_label=t.pool_label, manual_rate=1.0)
    for t in list_tokens()
}
p2p_client = P2PClient()

ADMIN_CHAT_ID = int(os.getenv("ADMIN_CHAT_ID", "0") or "0")

logger.info("BOT VERSION %s — feeds: %s, p2p configured: %s",
            BOT_VERSION, list(feeds.keys()), p2p_client.is_configured)
# Sanity check
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


def token_button(t) -> InlineKeyboardButton:
    return InlineKeyboardButton(
        text=f"{t.emoji} {t.symbol} {t.name}",
        callback_data=f"token:{t.slug}",
    )


def pool_button(t) -> InlineKeyboardButton:
    return InlineKeyboardButton(
        text=f"🏦 Пуль {t.symbol} ({t.pool_label})",
        callback_data=f"pool:{t.slug}",
    )


def main_menu() -> InlineKeyboardMarkup:
    buttons = []
    for t in list_tokens():
        buttons.append([token_button(t)])
        buttons.append([pool_button(t)])
    buttons.append([InlineKeyboardButton(text="💱 Общий курс USD/RUB", callback_data="usd_rub")])
    buttons.append([InlineKeyboardButton(text="📊 P2P-объявления", callback_data="pools")])
    buttons.append([InlineKeyboardButton(text="🆘 Поддержка", callback_data="support")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


@router.message(CommandStart())
async def cmd_start(message: Message):
    await message.answer(
        f"👑 <b>ЦАРЬ Обменник</b> <i>v{BOT_VERSION}</i>\n\n"
        "Обмен ЦАРЬ → USDT → P2P → RUB → карта.\n\n"
        "<b>3 серии ЦАРЬ — каждая со своим DeDust-пулом:</b>\n"
        "  👑 BAAL_RA — DeDust USD₮-пул\n"
        "  ♊  Гемини — DeDust TON-пул\n"
        "  👑 С коронкой — DeDust TON-пул\n\n"
        "Нажми на токен, чтобы узнать курс или сделать вывод:",
        reply_markup=main_menu(),
    )


@router.message(Command("help"))
async def cmd_help(message: Message):
    await message.answer(
        "<b>Помощь</b>\n\n"
        "/start — главное меню\n"
        "/rate — общий курс ЦАРЬ\n"
        "/pool BAAL_RA — USD₮-пул ЦАРЬ\n"
        "/pool GEMINI — TON-пул Гемини\n"
        "/pool CROWN — TON-пул С коронкой\n"
        "/tokens — все 3 серии\n"
        "/withdraw — вывод средств\n"
        "/help — эта справка\n"
        "/version — версия бота\n\n"
        f"<b>Поддержка:</b> {SUPPORT_HANDLE}\n"
        f"<b>Казначейство:</b> <code>{USDT_TREASURY_ADDRESS}</code>"
    )


@router.message(Command("version"))
async def cmd_version(message: Message):
    await message.answer(
        f"🤖 <b>Версия бота:</b> <code>{BOT_VERSION}</code>\n"
        f"<b>Quote-метод:</b> {'✅ есть' if hasattr(PriceFeed, 'quote') else '❌ отсутствует'}\n"
        f"<b>Фиды:</b> {len(feeds)} ({', '.join(feeds.keys())})\n"
        f"<b>P2P:</b> {'✅ ключ задан' if p2p_client.is_configured else '⚠️ mock (без P2P_API_KEY)'}"
    )


@router.message(Command("tokens"))
async def cmd_tokens(message: Message):
    lines = ["<b>Все серии ЦАРЬ + DeDust-пулы:</b>\n"]
    for t in list_tokens():
        lines.append(
            f"{t.emoji} <b>{t.name}</b> | {t.symbol}\n"
            f"  Master: <code>{t.master}</code>\n"
            f"  DeDust-пул: <code>{t.pool}</code> ({t.pool_label})\n"
            f"  Мин. сумма: {t.min_tsar:,} ЦАРЬ\n"
        )
    await message.answer("\n".join(lines))


@router.message(Command("rate"))
async def cmd_rate(message: Message):
    await cmd_pool_main(message)


async def cmd_pool_main(message: Message):
    lines = [f"💱 <b>Общий курс ЦАРЬ</b> <i>v{BOT_VERSION}</i>\n"]
    for t in list_tokens():
        try:
            q = await feeds[t.slug].quote(1_000_000)
            if q.ok:
                lines.append(
                    f"{t.emoji} <b>{t.symbol} {t.name}</b> ({t.pool_label})\n"
                    f"  1 000 000 ЦАРЬ = <b>{q.rub_amount:,.4f} ₽</b>\n"
                    f"  1 ЦАРЬ ≈ {q.tsar_price_usd*100:.4f} ¢\n"
                    f"  источник: {q.source}\n"
                )
            else:
                lines.append(f"{t.emoji} {t.symbol}: ❌ {q.error or 'недоступен'}\n")
        except Exception as e:
            lines.append(f"{t.emoji} {t.symbol}: ❌ {e}\n")
    lines.append(f"\n<i>USD/RUB: {USD_RUB_FALLBACK:.2f} ₽</i>")
    await message.answer("\n".join(lines), reply_markup=main_menu())


@router.callback_query(F.data.startswith("pool:"))
async def on_pool(callback: CallbackQuery):
    slug = callback.data.split(":", 1)[1]
    token = get_token(slug)
    if not token:
        await callback.message.edit_text("❌ Токен не найден")
        return
    try:
        q = await feeds[slug].quote(1_000_000)
        if q.ok:
            text = (
                f"🏦 <b>{token.symbol} {token.name} — DeDust {token.pool_label}-пул</b>\n\n"
                f"Адрес пула: <code>{token.pool}</code>\n"
                f"Jetton master: <code>{token.master}</code>\n\n"
                f"1 000 000 ЦАРЬ = <b>{q.rub_amount:,.4f} ₽</b>\n"
                f"1 ЦАРЬ ≈ {q.tsar_price_usd*100:.4f} ¢ ({q.tsar_price_usd:.10f} USD)\n"
                f"USD/RUB: {q.rate_used:.2f} ₽\n"
                f"Источник: <i>{q.source}</i>"
            )
        else:
            text = f"❌ Не удалось получить курс {token.symbol}: {q.error}"
    except Exception as e:
        text = f"❌ Ошибка: {e}"
    await callback.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="◀ Назад", callback_data="back")]])
    )
    await callback.answer()


@router.message(Command("pool"))
async def cmd_pool(message: Message):
    args = (message.text or "").split()
    if len(args) > 1:
        slug = args[1].upper()
        token = get_token(slug)
        if not token:
            await message.answer(f"❌ Неизвестный токен: {slug}")
            return
        try:
            q = await feeds[slug].quote(1_000_000)
            if q.ok:
                await message.answer(
                    f"🏦 <b>{token.symbol} — DeDust {token.pool_label}-пул</b>\n\n"
                    f"Адрес пула: <code>{token.pool}</code>\n"
                    f"1 000 000 ЦАРЬ = <b>{q.rub_amount:,.4f} ₽</b>\n"
                    f"1 ЦАРЬ ≈ {q.tsar_price_usd*100:.4f} ¢\n"
                    f"USD/RUB: {q.rate_used:.2f} ₽\n"
                    f"Источник: <i>{q.source}</i>"
                )
            else:
                await message.answer(f"❌ {q.error}")
        except Exception as e:
            await message.answer(f"❌ {e}")
    else:
        await cmd_pool_main(message)


@router.callback_query(F.data == "usd_rub")
async def on_usd_rub(callback: CallbackQuery):
    await callback.message.edit_text(
        f"💱 <b>USD/RUB</b>\n\n"
        f"Текущий fallback: {USD_RUB_FALLBACK:.2f} ₽\n"
        f"Источник: exchangerate-api.com",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="◀ Назад", callback_data="back")]])
    )
    await callback.answer()


@router.message(Command("withdraw"))
async def cmd_withdraw(message: Message, state: FSMContext):
    await state.set_state(WithdrawForm.token_slug)
    await message.answer("👑 Выбери токен для вывода:", reply_markup=main_menu())


@router.callback_query(F.data.startswith("token:"))
async def on_token_select(callback: CallbackQuery, state: FSMContext):
    slug = callback.data.split(":", 1)[1]
    token = get_token(slug)
    if not token:
        await callback.message.answer("❌ Токен не найден")
        return
    await state.update_data(token_slug=slug)
    await state.set_state(WithdrawForm.amount)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"🏦 Курс {token.symbol} (DeDust {token.pool_label})", callback_data=f"pool:{slug}")],
        [InlineKeyboardButton(text="◀ Назад", callback_data="back")],
    ])
    await callback.message.edit_text(
        f"{token.emoji} Выбран: <b>{token.symbol} {token.name}</b>\n\n"
        f"Master: <code>{token.master}</code>\n"
        f"DeDust-пул: <code>{token.pool}</code> ({token.pool_label})\n"
        f"Минимальная сумма: {token.min_tsar:,} ЦАРЬ\n\n"
        "Введи количество ЦАРЬ для обмена:",
        reply_markup=kb,
    )
    await callback.answer()


@router.message(WithdrawForm.amount)
async def on_amount(message: Message, state: FSMContext):
    try:
        amount = float(message.text.replace(",", ".").replace(" ", ""))
    except ValueError:
        await message.answer("❌ Введи число, например 1000000")
        return
    if amount < 250_000:
        await message.answer("❌ Минимум 250 000 ЦАРЬ")
        return
    await state.update_data(amount=amount)
    await state.set_state(WithdrawForm.card)
    await message.answer(
        f"💳 <b>Сумма:</b> {amount:,.0f} ЦАРЬ\n\n"
        "Введи номер карты для получения RUB (16 цифр):"
    )


@router.message(WithdrawForm.card)
async def on_card(message: Message, state: FSMContext):
    card = message.text.strip().replace(" ", "")
    if not (card.isdigit() and len(card) in (16, 19, 20)):
        await message.answer("❌ Неверный формат. Введи 16 цифр номера карты")
        return
    data = await state.get_data()
    slug = data.get("token_slug")
    amount = data.get("amount")
    user_id = message.from_user.id
    token = get_token(slug)
    try:
        result = await _service_for(slug).payout(
            user_id=user_id,
            tsar_amount=amount,
            recipient=card,
            method=PayoutMethod.CARD_RU,
        )
        if result.ok:
            ad = result.p2p_ad
            await message.answer(
                f"✅ <b>Заявка создана</b>\n\n"
                f"Токен: {token.emoji} {token.symbol} {token.name}\n"
                f"ID: <code>{result.payout.id}</code>\n"
                f"Сумма: {amount:,.0f} ЦАРЬ\n"
                f"Получишь: <b>{result.payout.amount_rub:.2f} ₽</b>\n"
                f"На карту: <code>{card[:6]}****{card[-4:]}</code>\n\n"
                f"🤝 P2P-партнёр: {ad.nickname if ad else 'mock'}\n"
                f"Курс: {ad.price if ad else 0:.2f} ₽/USDT\n\n"
                f"Переведи ЦАРЬ на:\n<code>{USDT_TREASURY_ADDRESS}</code>\n"
                f"После прихода ЦАРЬ бот сам определит серию и свяжет с заявкой."
            )
        else:
            await message.answer(f"❌ Ошибка: {result.error}")
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")
    await state.clear()


@router.callback_query(F.data == "pools")
async def on_pools(callback: CallbackQuery):
    try:
        ads = await p2p_client.get_buy_ads(crypto="USDT", fiat="RUB", side="BUY", page_size=5)
        if not ads:
            text = "📊 <b>P2P-объявления (BUY USDT)</b>\n\nНет активных объявлений."
        else:
            lines = [f"📊 <b>P2P-объявления (покупка USDT)</b>\n<i>P2P-API: {'✅ реальный' if p2p_client.is_configured else '⚠️ mock (без P2P_API_KEY)'}</i>\n"]
            for a in ads[:5]:
                lines.append(
                    f"• <b>{a.nickname}</b> — {a.price:.2f} ₽/USDT\n"
                    f"  доступно: {a.available_usdt:,.0f} USDT\n"
                    f"  способы: {', '.join(a.payments[:3])}\n"
                )
            text = "\n".join(lines)
    except Exception as e:
        text = f"❌ P2P ошибка: {e}"
    await callback.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="◀ Назад", callback_data="back")]])
    )
    await callback.answer()


@router.callback_query(F.data == "support")
async def on_support(callback: CallbackQuery):
    await callback.message.edit_text(
        f"🆘 <b>Поддержка:</b> {SUPPORT_HANDLE}",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="◀ Назад", callback_data="back")]])
    )
    await callback.answer()


@router.callback_query(F.data == "back")
async def on_back(callback: CallbackQuery):
    await callback.message.edit_text(
        f"👑 <b>ЦАРЬ Обменник</b> <i>v{BOT_VERSION}</i>\n\n"
        "Выбери токен:",
        reply_markup=main_menu()
    )
    await callback.answer()


# === TonWatcher: автоопределение токена по входящему IP-переводу ===
async def on_incoming_transfer(t: IncomingTransfer) -> None:
    emoji = t.token.emoji if t.token else "❓"
    name = t.token.name if t.token else "НЕИЗВЕСТНЫЙ ТОКЕН"
    text = (
        f"{emoji} <b>Входящий перевод: {name}</b>\n\n"
        f"Master: <code>{short_master(t.jetton_master)}</code>\n"
        f"Сумма: <b>{t.amount:,.4f}</b>\n"
        f"Sender: <code>{short_master(t.sender)}</code>\n"
        f"TX: <code>{t.tx_hash[:16]}…</code>"
    )
    if ADMIN_CHAT_ID:
        try:
            await bot.send_message(ADMIN_CHAT_ID, text)
        except Exception as e:
            logger.warning("send to admin failed: %s", e)
    else:
        logger.info("incoming: %s", text.replace("<b>", "").replace("</b>", ""))


async def main():
    dp.include_router(router)
    logger.info("🚀 Bot %s starting...", BOT_VERSION)
    logger.info("feeds: %s", {k: f"manual={f.manual_rate}" for k, f in feeds.items()})
    logger.info("p2p: configured=%s", p2p_client.is_configured)
    await bot.delete_webhook(drop_pending_updates=True)
    watcher = TonWatcher(poll_interval_sec=15.0, on_transfer=on_incoming_transfer)
    watcher.start()
    logger.info("TonWatcher started")
    try:
        await dp.start_polling(bot, skip_updates=True)
    finally:
        await watcher.stop()
        for f in feeds.values():
            await f.close()
        await p2p_client.close()


if __name__ == "__main__":
    asyncio.run(main())