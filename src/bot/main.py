"""Telegram-бот обменника ЦАРЬ → RUB.

3 серии ЦАРЬ, у каждого свой DeDust-пул. Все 3 продаются через P2P и СБП.

Версия: 2026-10-05-003 — упрощённое меню: 3 царя × (P2P + СБП + адреса).
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
    get_token,
    list_tokens,
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

# === Отдельный PriceFeed для каждого царя (свой DeDust-пул) ===
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
    phone = State()


def token_button(t) -> InlineKeyboardButton:
    return InlineKeyboardButton(
        text=f"{t.emoji} {t.symbol} {t.name}",
        callback_data=f"token:{t.slug}",
    )


def main_menu() -> InlineKeyboardMarkup:
    """Главное меню: выбор одной из 3 серий ЦАРЬ."""
    buttons = [[token_button(t)] for t in list_tokens()]
    buttons.append([InlineKeyboardButton(text="📊 P2P-объявления", callback_data="pools")])
    buttons.append([InlineKeyboardButton(text="🔄 Обновить P2P", callback_data="p2p_refresh")])
    buttons.append([InlineKeyboardButton(text="🆘 Поддержка", callback_data="support")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def token_menu(slug: str) -> InlineKeyboardMarkup:
    """Меню токена: курс DeDust-пула + 2 действия (P2P / СБП) + адреса."""
    t = get_token(slug)
    if not t:
        return main_menu()
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=f"💰 Продать {t.symbol} через P2P",
            callback_data=f"sell_p2p:{t.slug}",
        )],
        [InlineKeyboardButton(
            text=f"📲 Продать {t.symbol} через СБП",
            callback_data=f"sell_sbp:{t.slug}",
        )],
        [InlineKeyboardButton(
            text=f"📋 Адреса {t.symbol}",
            callback_data=f"addresses:{t.slug}",
        )],
        [InlineKeyboardButton(
            text=f"🏦 Курс DeDust-пула {t.symbol} ({t.pool_label})",
            callback_data=f"pool:{t.slug}",
        )],
        [InlineKeyboardButton(text="◀ Назад к 3 царям", callback_data="back")],
    ])


@router.message(CommandStart())
async def cmd_start(message: Message):
    text = (
        f"👑 <b>ЦАРЬ Обменник</b> <i>v{BOT_VERSION}</i>\n\n"
        "Продай любой из 3 царей за RUB.\n"
        "Способы получения: <b>P2P</b> (карта) или <b>СБП</b> (по телефону).\n\n"
        "<b>3 серии ЦАРЬ — каждая со своим DeDust-пулом:</b>\n"
        "  👑 BAAL_RA — DeDust USD₮-пул\n"
        "  ♊  Гемини — DeDust TON-пул\n"
        "  👑 С коронкой — DeDust TON-пул\n\n"
        "Выбери серию ЦАРЬ:"
    )
    await message.answer(text, reply_markup=main_menu())


@router.message(Command("help"))
async def cmd_help(message: Message):
    await message.answer(
        "<b>Помощь</b>\n\n"
        "/start — главное меню (3 царя)\n"
        "/rate — общий курс ЦАРЬ\n"
        "/tokens — все 3 серии + DeDust-пулы\n"
        "/p2p — P2P-объявления RUB/USDT\n"
        "/p2p_refresh — сбросить кэш P2P\n"
        "/version — версия бота\n\n"
        f"<b>Поддержка:</b> {SUPPORT_HANDLE}"
    )


@router.message(Command("version"))
async def cmd_version(message: Message):
    await message.answer(
        f"🤖 <b>Версия бота:</b> <code>{BOT_VERSION}</code>\n"
        f"<b>Царей в меню:</b> {len(list_tokens())} ({', '.join(t.slug for t in list_tokens())})\n"
        f"<b>Quote-метод:</b> {'✅ есть' if hasattr(PriceFeed, 'quote') else '❌ отсутствует'}\n"
        f"<b>P2P:</b> {'✅ ключ задан' if p2p_client.is_configured else '⚠️ mock (без P2P_API_KEY)'}\n"
        f"<b>P2P кэш:</b> {p2p_client.cache_size} ads, age {p2p_client.cache_age_sec:.1f}s, refreshes #{p2p_client.refresh_count}"
    )


@router.message(Command("tokens"))
async def cmd_tokens(message: Message):
    lines = [f"<b>Все серии ЦАРЬ + DeDust-пулы</b> <i>v{BOT_VERSION}</i>\n"]
    for t in list_tokens():
        lines.append(
            f"{t.emoji} <b>{t.name}</b> | {t.symbol}\n"
            f"  Master: <code>{t.master}</code>\n"
            f"  DeDust-пул: <code>{t.pool}</code> ({t.pool_label})\n"
            f"  Мин. сумма: {t.min_tsar:,} ЦАРЬ"
        )
    await message.answer("\n\n".join(lines), reply_markup=main_menu())


@router.message(Command("rate"))
async def cmd_rate(message: Message):
    lines = [f"💱 <b>Курс DeDust-пулов</b> <i>v{BOT_VERSION}</i>\n"]
    for t in list_tokens():
        try:
            q = await feeds[t.slug].quote(1_000_000)
            if q.ok:
                lines.append(
                    f"{t.emoji} <b>{t.symbol}</b> ({t.pool_label})\n"
                    f"  1 000 000 ЦАРЬ = <b>{q.rub_amount:,.4f} ₽</b>\n"
                    f"  источник: {q.source}"
                )
            else:
                lines.append(f"{t.emoji} {t.symbol}: ❌ {q.error or 'недоступен'}")
        except Exception as e:
            lines.append(f"{t.emoji} {t.symbol}: ❌ {e}")
    await message.answer("\n\n".join(lines), reply_markup=main_menu())


# === TOKEN MENU ===
@router.callback_query(F.data.startswith("token:"))
async def on_token_select(callback: CallbackQuery, state: FSMContext):
    slug = callback.data.split(":", 1)[1]
    t = get_token(slug)
    if not t:
        await callback.message.edit_text("❌ Токен не найден")
        return
    # Показываем мини-сводку + кнопки P2P/СБП/адреса/курс
    try:
        q = await feeds[slug].quote(1_000_000)
        rate_text = f"1 000 000 ЦАРЬ ≈ <b>{q.rub_amount:,.4f} ₽</b>" if q.ok else f"❌ {q.error}"
    except Exception as e:
        rate_text = f"❌ {e}"
    text = (
        f"{t.emoji} <b>{t.symbol} {t.name}</b>\n\n"
        f"DeDust-пул ({t.pool_label}): {rate_text}\n\n"
        f"Выбери способ получения RUB:"
    )
    await callback.message.edit_text(text, reply_markup=token_menu(slug))
    await callback.answer()


# === P2P SELL ===
@router.callback_query(F.data.startswith("sell_p2p:"))
async def on_sell_p2p(callback: CallbackQuery, state: FSMContext):
    slug = callback.data.split(":", 1)[1]
    t = get_token(slug)
    if not t:
        await callback.message.edit_text("❌ Токен не найден")
        return
    await state.update_data(token_slug=slug, sell_method="P2P")
    await state.set_state(WithdrawForm.amount)
    await callback.message.edit_text(
        f"{t.emoji} <b>Продать {t.symbol} через P2P</b>\n\n"
        f"Мин. сумма: {t.min_tsar:,} ЦАРЬ\n"
        f"Получишь RUB на карту.\n\n"
        "Введи количество ЦАРЬ для обмена:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀ Назад", callback_data=f"token:{slug}")],
        ]),
    )
    await callback.answer()


# === СБП SELL ===
@router.callback_query(F.data.startswith("sell_sbp:"))
async def on_sell_sbp(callback: CallbackQuery, state: FSMContext):
    slug = callback.data.split(":", 1)[1]
    t = get_token(slug)
    if not t:
        await callback.message.edit_text("❌ Токен не найден")
        return
    await state.update_data(token_slug=slug, sell_method="SBP")
    await state.set_state(WithdrawForm.amount)
    await callback.message.edit_text(
        f"{t.emoji} <b>Продать {t.symbol} через СБП</b>\n\n"
        f"Мин. сумма: {t.min_tsar:,} ЦАРЬ\n"
        f"Получишь RUB по номеру телефона через СБП.\n\n"
        "Введи количество ЦАРЬ для обмена:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀ Назад", callback_data=f"token:{slug}")],
        ]),
    )
    await callback.answer()


# === ADDRESSES ===
@router.callback_query(F.data.startswith("addresses:"))
async def on_addresses(callback: CallbackQuery):
    slug = callback.data.split(":", 1)[1]
    t = get_token(slug)
    if not t:
        await callback.message.edit_text("❌ Токен не найден")
        return
    # Tonviewer-ссылки
    pool_url = f"https://tonviewer.com/{t.pool}"
    master_url = f"https://tonviewer.com/{t.master}"
    treasury_url = f"https://tonviewer.com/{USDT_TREASURY_ADDRESS}"
    await callback.message.edit_text(
        f"📋 <b>Адреса {t.symbol} {t.name}</b>\n\n"
        f"<b>Jetton master (контракт):</b>\n<code>{t.master}</code>\n"
        f"🔗 <a href=\"{master_url}\">Открыть в Tonviewer</a>\n\n"
        f"<b>DeDust-пул ({t.pool_label}):</b>\n<code>{t.pool}</code>\n"
        f"🔗 <a href=\"{pool_url}\">Открыть в Tonviewer</a>\n\n"
        f"<b>Казначейство (куда переводить ЦАРЬ):</b>\n<code>{USDT_TREASURY_ADDRESS}</code>\n"
        f"🔗 <a href=\"{treasury_url}\">Открыть в Tonviewer</a>\n\n"
        f"<i>Минималка: {t.min_tsar:,} ЦАРЬ</i>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀ Назад", callback_data=f"token:{slug}")],
        ]),
        disable_web_page_preview=True,
    )
    await callback.answer()


# === POOL DETAIL ===
@router.callback_query(F.data.startswith("pool:"))
async def on_pool(callback: CallbackQuery):
    slug = callback.data.split(":", 1)[1]
    t = get_token(slug)
    if not t:
        await callback.message.edit_text("❌ Токен не найден")
        return
    try:
        q = await feeds[slug].quote(1_000_000)
        if q.ok:
            text = (
                f"🏦 <b>{t.symbol} — DeDust {t.pool_label}-пул</b>\n\n"
                f"Адрес пула: <code>{t.pool}</code>\n"
                f"🔗 <a href=\"https://tonviewer.com/{t.pool}\">Открыть в Tonviewer</a>\n\n"
                f"Jetton master: <code>{t.master}</code>\n\n"
                f"1 000 000 ЦАРЬ = <b>{q.rub_amount:,.4f} ₽</b>\n"
                f"1 ЦАРЬ ≈ {q.tsar_price_usd*100:.4f} ¢\n"
                f"USD/RUB: {q.rate_used:.2f} ₽\n"
                f"Источник: <i>{q.source}</i>"
            )
        else:
            text = f"❌ Не удалось получить курс {t.symbol}: {q.error}"
    except Exception as e:
        text = f"❌ Ошибка: {e}"
    await callback.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀ Назад", callback_data=f"token:{slug}")],
        ]),
        disable_web_page_preview=True,
    )
    await callback.answer()


# === AMOUNT ===
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
    data = await state.get_data()
    sell_method = data.get("sell_method", "P2P")
    await state.update_data(amount=amount)
    if sell_method == "SBP":
        await state.set_state(WithdrawForm.phone)
        await message.answer(
            f"📱 <b>Сумма:</b> {amount:,.0f} ЦАРЬ\n\n"
            "Введи номер телефона для получения RUB через СБП\n"
            "(формат: +7XXXXXXXXXX):"
        )
    else:
        await state.set_state(WithdrawForm.card)
        await message.answer(
            f"💳 <b>Сумма:</b> {amount:,.0f} ЦАРЬ\n\n"
            "Введи номер карты для получения RUB (16 цифр):"
        )


# === CARD (P2P) ===
@router.message(WithdrawForm.card)
async def on_card(message: Message, state: FSMContext):
    card = message.text.strip().replace(" ", "")
    if not (card.isdigit() and len(card) in (16, 19, 20)):
        await message.answer("❌ Неверный формат. Введи 16 цифр номера карты")
        return
    await _create_payout(message, state, method=PayoutMethod.CARD_RU, recipient=card, method_label="P2P")


# === PHONE (СБП) ===
@router.message(WithdrawForm.phone)
async def on_phone(message: Message, state: FSMContext):
    phone = message.text.strip().replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
    if not (phone.startswith("+") and phone[1:].isdigit() and 10 <= len(phone) <= 15):
        await message.answer("❌ Неверный формат. Введи +7XXXXXXXXXX")
        return
    await _create_payout(message, state, method=PayoutMethod.SBP, recipient=phone, method_label="СБП")


async def _create_payout(message: Message, state: FSMContext, *, method, recipient: str, method_label: str) -> None:
    data = await state.get_data()
    slug = data.get("token_slug")
    amount = data.get("amount")
    user_id = message.from_user.id
    t = get_token(slug)
    if not t:
        await message.answer("❌ Токен не найден")
        await state.clear()
        return
    try:
        result = await _service_for(slug).payout(
            user_id=user_id,
            tsar_amount=amount,
            recipient=recipient,
            method=method,
        )
        if result.ok:
            ad = result.payout
            await message.answer(
                f"✅ <b>Заявка создана</b> <i>({method_label})</i>\n\n"
                f"Токен: {t.emoji} {t.symbol} {t.name}\n"
                f"ID: <code>{ad.id}</code>\n"
                f"Сумма: {amount:,.0f} ЦАРЬ\n"
                f"Получишь: <b>{ad.amount_rub:.2f} ₽</b>\n"
                f"Получатель: <code>{recipient}</code>\n\n"
                f"🤝 P2P-партнёр: {getattr(ad, 'p2p_partner', 'mock')}\n"
                f"Переведи ЦАРЬ на:\n<code>{USDT_TREASURY_ADDRESS}</code>"
            )
        else:
            await message.answer(f"❌ Ошибка: {result.error}")
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")
    await state.clear()


# === P2P LIST ===
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
        "Выбери серию ЦАРЬ:",
        reply_markup=main_menu()
    )
    await callback.answer()


async def main():
    dp.include_router(router)
    logger.info("🚀 Bot %s starting...", BOT_VERSION)
    logger.info("feeds: %s", list(feeds.keys()))
    logger.info("p2p: configured=%s, refresh=%s",
                p2p_client.is_configured, hasattr(p2p_client, 'refresh'))
    try:
        await p2p_client.get_buy_ads()
        logger.info("P2P cache pre-warmed: %d ads", p2p_client.cache_size)
    except Exception as e:
        logger.warning("P2P pre-warm failed: %s", e)
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot, skip_updates=True)
    for f in feeds.values():
        await f.close()
    await p2p_client.close()


if __name__ == "__main__":
    asyncio.run(main())