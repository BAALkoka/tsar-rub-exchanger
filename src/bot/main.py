"""Telegram-бот обменника ЦАРЬ → RUB.

3 серии ЦАРЬ, у каждого свой DeDust-пул.

Версия: 2026-10-05-003 — кнопки "Контракт + Пул", прямые продажи P2P и СБП.
"""
from __future__ import annotations
import asyncio
import logging
import os
import sys
from pathlib import Path
from datetime import datetime

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

BOT_VERSION = "2026-10-05-003"
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("tsar.bot")

if not BOT_TOKEN:
    raise RuntimeError("TELEGRAM_BOT_TOKEN не задан")

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())
router = Router()

feeds: dict[str, PriceFeed] = {
    t.slug: PriceFeed(token_master=t.master, token_pool=t.pool, pool_label=t.pool_label, manual_rate=1.0)
    for t in list_tokens()
}
p2p_client = P2PClient()

ADMIN_CHAT_ID = int(os.getenv("ADMIN_CHAT_ID", "0") or "0")

logger.info("BOT VERSION %s — feeds: %s, p2p configured: %s",
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


class DirectSaleForm(StatesGroup):
    """Прямая продажа: P2P или СБП."""
    token_slug = State()
    amount = State()
    payment_method = State()  # 'p2p' или 'sbp'
    card_or_phone = State()


# === UI BUILDERS ===

def token_main_button(t) -> InlineKeyboardButton:
    """Главная кнопка токена — открывает карточку с адресами."""
    return InlineKeyboardButton(
        text=f"{t.emoji} {t.symbol} {t.name}",
        callback_data=f"open:{t.slug}",
    )


def main_menu() -> InlineKeyboardMarkup:
    """Главное меню — 3 токена, на каждом открывается карточка."""
    buttons = []
    for t in list_tokens():
        buttons.append([token_main_button(t)])
    buttons.append([InlineKeyboardButton(text="💱 Курс USD/RUB", callback_data="usd_rub")])
    buttons.append([InlineKeyboardButton(text="📊 Все P2P-объявления", callback_data="pools")])
    buttons.append([InlineKeyboardButton(text="🔄 Обновить P2P", callback_data="p2p_refresh")])
    buttons.append([InlineKeyboardButton(text="🆘 Поддержка", callback_data="support")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def token_card_keyboard(slug: str) -> InlineKeyboardMarkup:
    """Карточка токена: контракт + пул + действия (продать)."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📋 Адрес контракта + пула", callback_data=f"addr:{slug}")],
        [InlineKeyboardButton(text="💱 Продать через P2P", callback_data=f"sell:p2p:{slug}")],
        [InlineKeyboardButton(text="⚡ Продать через СБП", callback_data=f"sell:sbp:{slug}")],
        [InlineKeyboardButton(text="🏦 Pull Of the Dust", callback_data=f"pool:{slug}")],
        [InlineKeyboardButton(text="◀ Назад", callback_data="back")],
    ])


# === Handlers ===

@router.message(CommandStart())
async def cmd_start(message: Message):
    await message.answer(
        f"👑 <b>ЦАРЬ Обменник</b> <i>v{BOT_VERSION}</i>\n\n"
        "Обмен ЦАРЬ → USDT → RUB (P2P / СБП).\n\n"
        "<b>Выбери токен — увидишь адрес контракта + пула + кнопки продажи:</b>",
        reply_markup=main_menu(),
    )


@router.message(Command("help"))
async def cmd_help(message: Message):
    await message.answer(
        "<b>Помощь</b>\n\n"
        "/start — главное меню\n"
        "/version — версия бота\n"
        "/tokens — все 3 серии\n"
        "/p2p — P2P-объявления\n"
        "/p2p_refresh — сбросить кэш P2P\n"
        "/withdraw — вывод (передепозит)\n\n"
        "<b>Схема:</b>\n"
        "  ЦАРЬ (TON) → продать через P2P → USDT на карту/СБП → RUB\n\n"
        f"<b>Поддержка:</b> {SUPPORT_HANDLE}\n"
        f"<b>Казначейство:</b> <code>{USDT_TREASURY_ADDRESS}</code>"
    )


@router.message(Command("version"))
async def cmd_version(message: Message):
    await message.answer(
        f"🤖 <b>Версия бота:</b> <code>{BOT_VERSION}</code>\n"
        f"<b>Quote-метод:</b> {'✅ есть' if hasattr(PriceFeed, 'quote') else '❌ отсутствует'}\n"
        f"<b>Фиды:</b> {len(feeds)} ({', '.join(feeds.keys())})\n"
        f"<b>P2P:</b> {'✅ ключ задан' if p2p_client.is_configured else '⚠️ mock (без P2P_API_KEY)'}\n"
        f"<b>P2P кэш:</b> {p2p_client.cache_size} ads, age {p2p_client.cache_age_sec:.1f}s, refreshes #{p2p_client.refresh_count}"
    )


@router.message(Command("tokens"))
async def cmd_tokens(message: Message):
    lines = ["<b>Все серии ЦАРЬ:</b>\n"]
    for t in list_tokens():
        lines.append(
            f"{t.emoji} <b>{t.name}</b> | {t.symbol}\n"
            f"  Master: <code>{t.master}</code>\n"
            f"  DeDust-пул: <code>{t.pool}</code> ({t.pool_label})\n"
        )
    await message.answer("\n".join(lines))


# === ОТКРЫТИЕ КАРТОЧКИ ТОКЕНА (по кнопке) ===

@router.callback_query(F.data.startswith("open:"))
async def on_open_token(callback: CallbackQuery):
    """Открывает карточку токена с адресами и кнопками продажи."""
    slug = callback.data.split(":", 1)[1]
    token = get_token(slug)
    if not token:
        await callback.answer("❌ Токен не найден", show_alert=True)
        return
    try:
        q = await feeds[slug].quote(1_000_000)
        if q.ok:
            price_line = (
                f"\n💰 <b>Курс:</b> 1 000 000 ЦАРЬ = <b>{q.rub_amount:,.4f} ₽</b>\n"
                f"   1 ЦАРЬ ≈ {q.tsar_price_usd*100:.4f} ¢\n"
                f"   USD/RUB: {q.rate_used:.2f} ₽\n"
                f"   Источник: <i>{q.source}</i>"
            )
        else:
            price_line = f"\n⚠️ <i>Курс недоступен: {q.error}</i>"
    except Exception as e:
        price_line = f"\n⚠️ <i>Ошибка: {e}</i>"

    text = (
        f"{token.emoji} <b>{token.name}</b> | <code>{token.symbol}</code>{price_line}\n\n"
        f"<b>📍 Адреса в TON:</b>\n"
        f"  • Контракт (jetton master):\n    <code>{token.master}</code>\n"
        f"  • DeDust-пул ({token.pool_label}):\n    <code>{token.pool}</code>\n\n"
        f"<b>Как продать:</b>\n"
        f"  1. Нажми <b>💱 Продать через P2P</b> — обмен на карту/СБП через P2P-партнёра\n"
        f"  2. Нажми <b>⚡ Продать через СБП</b> — мгновенный перевод через СБП\n\n"
        f"<b>Мин. сумма:</b> {token.min_tsar:,} ЦАРЬ"
    )
    await callback.message.edit_text(text, reply_markup=token_card_keyboard(slug))
    await callback.answer()


# === ПОКАЗ АДРЕСОВ ===

@router.callback_query(F.data.startswith("addr:"))
async def on_show_addr(callback: CallbackQuery):
    """Показывает полные адреса контракта + пула с copy-кнопками."""
    slug = callback.data.split(":", 1)[1]
    token = get_token(slug)
    if not token:
        await callback.answer("❌ Токен не найден", show_alert=True)
        return
    text = (
        f"📋 <b>{token.emoji} {token.symbol} — адреса</b>\n\n"
        f"<b>Контракт (jetton master):</b>\n"
        f"<code>{token.master}</code>\n\n"
        f"<b>DeDust-пул ({token.pool_label}):</b>\n"
        f"<code>{token.pool}</code>\n\n"
        f"<i>Нажми на адрес чтобы скопировать. Это кошельки TON для jetton и для DeDust.</i>"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💱 Продать через P2P", callback_data=f"sell:p2p:{slug}")],
        [InlineKeyboardButton(text="⚡ Продать через СБП", callback_data=f"sell:sbp:{slug}")],
        [InlineKeyboardButton(text="◀ Назад", callback_data=f"open:{slug}")],
    ])
    await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()


# === КУРС ПУЛА ===

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
                f"🏦 <b>{token.symbol} — DeDust {token.pool_label}-пул</b>\n\n"
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
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="◀ Назад", callback_data=f"open:{slug}")]])
    )
    await callback.answer()


# === ПРОДАЖА ЧЕРЕЗ P2P / СБП ===

@router.callback_query(F.data.startswith("sell:"))
async def on_sell(callback: CallbackQuery, state: FSMContext):
    """Начало продажи: спрашиваем количество."""
    _, method, slug = callback.data.split(":")
    token = get_token(slug)
    if not token:
        await callback.answer("❌ Токен не найден", show_alert=True)
        return
    method_name = "P2P" if method == "p2p" else "СБП"
    await state.update_data(token_slug=slug, payment_method=method)
    await state.set_state(DirectSaleForm.amount)
    if method == "p2p":
        info = (
            "💱 <b>Продажа через P2P</b>\n"
            "Обмен ЦАРЬ → USDT → RUB на карту через P2P-партнёра.\n"
            "Курс: лучший ₽/USDT среди 10 продавцов."
        )
    else:
        info = (
            "⚡ <b>Продажа через СБП</b>\n"
            "Прямой перевод RUB через СБП (Тинькофф, Сбер и т.д.).\n"
            "Курс: USDT → RUB по биржевому."
        )
    text = (
        f"{token.emoji} <b>{token.symbol} {token.name}</b>\n\n"
        f"{info}\n\n"
        f"Введи количество ЦАРЬ для продажи (минимум {token.min_tsar:,}):"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀ Назад", callback_data=f"open:{slug}")],
    ])
    await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()


@router.message(DirectSaleForm.amount)
async def on_direct_sale_amount(message: Message, state: FSMContext):
    try:
        amount = float(message.text.replace(",", ".").replace(" ", ""))
    except ValueError:
        await message.answer("❌ Введи число, например 1000000")
        return
    if amount < 250_000:
        await message.answer("❌ Минимум 250 000 ЦАРЬ")
        return
    data = await state.get_data()
    method = data.get("payment_method")
    await state.update_data(amount=amount)
    await state.set_state(DirectSaleForm.card_or_phone)
    if method == "p2p":
        prompt = "💳 <b>Введи номер карты для получения RUB:</b> (16 цифр)"
    else:
        prompt = "📱 <b>Введи номер телефона (СБП):</b> (+7XXXXXXXXXX)"
    await message.answer(prompt)


@router.message(DirectSaleForm.card_or_phone)
async def on_direct_sale_finalize(message: Message, state: FSMContext):
    data = await state.get_data()
    slug = data.get("token_slug")
    amount = data.get("amount")
    method = data.get("payment_method")
    user_input = message.text.strip().replace(" ", "")
    token = get_token(slug)
    if not token:
        await message.answer("❌ Токен не найден")
        await state.clear()
        return

    # Валидация
    if method == "p2p":
        if not (user_input.isdigit() and len(user_input) in (16, 19, 20)):
            await message.answer("❌ Неверный формат. Введи 16 цифр номера карты")
            return
    else:  # sbp
        clean = user_input.lstrip("+")
        if not clean.isdigit() or len(clean) not in (10, 11, 12):
            await message.answer("❌ Неверный формат. Введи телефон +7XXXXXXXXXX")
            return

    # Считаем курс и подбираем лучшего P2P-партнёра
    try:
        q = await feeds[slug].quote(amount)
        if not q.ok:
            await message.answer(f"❌ Курс недоступен: {q.error}")
            await state.clear()
            return
        best_ad = await p2p_client.best_buy_ad() if method == "p2p" else None
        if method == "p2p":
            usdt_amount = q.usdt_amount
            rub_amount = best_ad.price * usdt_amount if best_ad else q.rub_amount
        else:
            usdt_amount = q.usdt_amount
            rub_amount = usdt_amount * USD_RUB_FALLBACK

        ad_line = (
            f"\n🤝 <b>P2P-партнёр:</b> {best_ad.nickname if best_ad else '—'} "
            f"[{best_ad.merchant_level if best_ad else '—'}]\n"
            f"   Курс: {best_ad.price if best_ad else 0:.2f} ₽/USDT"
            if best_ad else ""
        )

        text = (
            f"✅ <b>Заявка создана ({method.upper()})</b>\n\n"
            f"{token.emoji} <b>{token.symbol} {token.name}</b>\n"
            f"Сумма: {amount:,.0f} ЦАРЬ\n"
            f"Получишь: <b>{rub_amount:,.2f} ₽</b>\n"
            f"USDT: {usdt_amount:,.4f}\n"
            f"Курс ЦАРЬ: {q.tsar_price_usd*100:.4f} ¢\n"
            f"USD/RUB: {q.rate_used:.2f} ₽{ad_line}\n\n"
            f"<b>Способ:</b> {'💳 карта' if method == 'p2p' else '📱 СБП'}\n"
            f"<b>Получатель:</b> <code>{user_input}</code>\n\n"
            f"💎 <b>Переведи ЦАРЬ на jetton-адрес проекта:</b>\n"
            f"<code>{token.master}</code>\n\n"
            f"💵 <b>Или отправь напрямую через DeDust:</b>\n"
            f"<code>{token.pool}</code>\n\n"
            f"После прихода ЦАРЬ заявка автоматически связана с тобой."
        )
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀ В главное меню", callback_data="back")],
        ])
        await message.answer(text, reply_markup=kb)
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")
    await state.clear()


# === WITHDRAW (старая форма, через перевод в казначейство) ===

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
        [InlineKeyboardButton(text="🏦 Курс токена (DeDust)", callback_data=f"pool:{slug}")],
        [InlineKeyboardButton(text="◀ Назад", callback_data="back")],
    ])
    await callback.message.edit_text(
        f"{token.emoji} Выбран: <b>{token.symbol} {token.name}</b>\n\n"
        f"Введи количество ЦАРЬ для обмена:"
    , reply_markup=kb)


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
    await message.answer(f"💳 <b>Сумма:</b> {amount:,.0f} ЦАРЬ\n\nВведи номер карты (16 цифр):")


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


# === P2P команды ===

@router.message(Command("p2p"))
async def cmd_p2p(message: Message):
    await show_p2p_ads(message, edit=False)


@router.message(Command("p2p_refresh"))
async def cmd_p2p_refresh(message: Message):
    await do_p2p_refresh(message, edit=False)


@router.callback_query(F.data == "p2p_refresh")
async def on_p2p_refresh(callback: CallbackQuery):
    await do_p2p_refresh(callback.message, edit=True)
    await callback.answer("🔄 Кэш P2P сброшен")


async def do_p2p_refresh(message: Message, *, edit: bool) -> None:
    try:
        await p2p_client.invalidate_cache()
        ads = await p2p_client.refresh()
        text = await _format_p2p_ads(ads, prefix="🔄 <b>P2P обновлён</b>\n\n")
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Обновить ещё раз", callback_data="p2p_refresh")],
            [InlineKeyboardButton(text="◀ Назад", callback_data="back")],
        ])
        if edit:
            await message.edit_text(text, reply_markup=kb)
        else:
            await message.answer(text, reply_markup=kb)
    except Exception as e:
        err = f"❌ Ошибка обновления P2P: {e}"
        if edit:
            await message.edit_text(err)
        else:
            await message.answer(err)


async def show_p2p_ads(message: Message, *, edit: bool) -> None:
    try:
        ads = await p2p_client.get_buy_ads()
        text = await _format_p2p_ads(ads)
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Обновить P2P", callback_data="p2p_refresh")],
            [InlineKeyboardButton(text="◀ Назад", callback_data="back")],
        ])
        if edit:
            await message.edit_text(text, reply_markup=kb)
        else:
            await message.answer(text, reply_markup=kb)
    except Exception as e:
        err = f"❌ P2P ошибка: {e}"
        if edit:
            await message.edit_text(err)
        else:
            await message.answer(err)


async def _format_p2p_ads(ads, *, prefix: str = "") -> str:
    if not ads:
        body = "Нет активных объявлений."
    else:
        lines = [
            f"{prefix}📊 <b>P2P-объявления (покупка USDT)</b>\n"
            f"<i>P2P-API: {'✅ реальный' if p2p_client.is_configured else '⚠️ mock (без P2P_API_KEY)'}</i>"
            f"  |  источник: <code>{p2p_client.last_source or '—'}</code>"
            f"  |  refreshes: <b>#{p2p_client.refresh_count}</b>\n"
        ]
        for i, a in enumerate(ads[:10], 1):
            lines.append(
                f"{i}. <b>{a.nickname}</b> [{a.merchant_level}]\n"
                f"    {a.price:.2f} ₽/USDT  •  {a.available_usdt:,.0f} USDT\n"
                f"    {', '.join(a.payments[:3])}"
            )
        best = min(ads, key=lambda x: x.price)
        lines.append(
            f"\n🏆 <b>Лучший курс:</b> {best.nickname} — {best.price:.2f} ₽/USDT"
        )
        body = "\n".join(lines)
    return body


# === Прочие callback'и ===

@router.callback_query(F.data == "usd_rub")
async def on_usd_rub(callback: CallbackQuery):
    await callback.message.edit_text(
        f"💱 <b>USD/RUB</b>\n\n"
        f"Текущий fallback: {USD_RUB_FALLBACK:.2f} ₽\n"
        f"Источник: exchangerate-api.com",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="◀ Назад", callback_data="back")]])
    )
    await callback.answer()


@router.callback_query(F.data == "pools")
async def on_pools(callback: CallbackQuery):
    await show_p2p_ads(callback.message, edit=True)
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


# === TonWatcher ===

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
    # Pre-warm P2P cache
    try:
        await p2p_client.get_buy_ads()
        logger.info("P2P cache pre-warmed: %d ads", p2p_client.cache_size)
    except Exception as e:
        logger.warning("P2P pre-warm failed: %s", e)
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