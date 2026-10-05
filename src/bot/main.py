"""Telegram-бот обменника ЦАРЬ -> RUB.

Поддерживает 3 серии ЦАРЬ через inline-кнопки:
  - 👑 BAAL_RA (основной ЦАРЬ)
  - ♊  Царь Гемини
  - 👑 Царь с коронкой

Автоопределение токена по входящему IP-переводу через TonWatcher.
Выплаты через P2P Market API (WalletBot).
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
    TSAR_MASTER,
    TSAR_PRIMARY_POOL,
    USD_RUB_FALLBACK,
    SUPPORT_HANDLE,
    USDT_TREASURY_ADDRESS,
)
from api.payouts.price_feed import PriceFeed
from api.payouts.p2p import P2PClient
from api.payouts.service import PayoutService
from api.payouts.ton_watcher import TonWatcher, IncomingTransfer

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("tsar.bot")

if not BOT_TOKEN:
    raise RuntimeError("TELEGRAM_BOT_TOKEN не задан")

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())
router = Router()

feed = PriceFeed(token_pool=TSAR_PRIMARY_POOL, manual_rate=1.0)
p2p_client = P2PClient()
payout_service = PayoutService(p2p_client=p2p_client, price_feed=feed)
# Админский канал для уведомлений о входящих переводах
ADMIN_CHAT_ID = int(os.getenv("ADMIN_CHAT_ID", "0") or "0")


class WithdrawForm(StatesGroup):
    token_slug = State()
    amount = State()
    card = State()


def token_button(t) -> InlineKeyboardButton:
    return InlineKeyboardButton(
        text=f"{t.emoji} {t.symbol} {t.name} ({short_master(t.master)})",
        callback_data=f"token:{t.slug}",
    )


def main_menu() -> InlineKeyboardMarkup:
    buttons = [[token_button(t)] for t in list_tokens()]
    buttons.append([InlineKeyboardButton(text="💱 Курс ЦАРЬ", callback_data="rate")])
    buttons.append([InlineKeyboardButton(text="📊 P2P-объявления", callback_data="pools")])
    buttons.append([InlineKeyboardButton(text="🏦 Курс DeDust-пула", callback_data="pool_rate")])
    buttons.append([InlineKeyboardButton(text="🆘 Поддержка", callback_data="support")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


@router.message(CommandStart())
async def cmd_start(message: Message):
    await message.answer(
        "👑 <b>ЦАРЬ Обменник</b>\n\n"
        "Обмен ЦАРЬ → USDT → P2P → RUB → карта.\n\n"
        "Все 3 серии:\n"
        "  👑 BAAL_RA — основной ЦАРЬ\n"
        "  ♊  Царь Гемини\n"
        "  👑 Царь с коронкой\n\n"
        "Выбери токен:",
        reply_markup=main_menu(),
    )


@router.message(Command("help"))
async def cmd_help(message: Message):
    await message.answer(
        "<b>Помощь</b>\n\n"
        "/start — главное меню\n"
        "/rate — текущий курс ЦАРЬ\n"
        "/pool — курс DeDust-пула\n"
        "/tokens — список токенов\n"
        "/withdraw — вывод средств\n"
        "/help — эта справка\n\n"
        f"<b>Поддержка:</b> {SUPPORT_HANDLE}\n"
        f"<b>Казначейство ЦАРЬ/USDT:</b> <code>{USDT_TREASURY_ADDRESS}</code>\n\n"
        "<b>Минимальная сумма:</b> 250 000 ЦАРЬ\n"
        "<b>Выплата:</b> P2P Market (WalletBot)"
    )


@router.message(Command("tokens"))
async def cmd_tokens(message: Message):
    lines = ["<b>Все серии ЦАРЬ:</b>\n"]
    for t in list_tokens():
        lines.append(
            f"{t.emoji} <b>{t.name}</b>\n"
            f"  <code>{t.master}</code>\n"
            f"  мин: {t.min_tsar:,} ЦАРЬ | decimals: {t.decimals}\n"
            f"  {t.description}\n"
        )
    await message.answer("\n".join(lines))


@router.message(Command("rate"))
async def cmd_rate(message: Message):
    try:
        q = await feed.quote(1_000_000)
        if q.ok:
            await message.answer(
                f"💱 <b>Курс ЦАРЬ</b>\n\n"
                f"1 000 000 ЦАРЬ = <b>{q.rub_amount:.2f} ₽</b>\n"
                f"1 ЦАРЬ ≈ {q.tsar_price_usd*100:.6f} ¢\n"
                f"Источник: {q.source}\n"
                f"Курс USD/RUB: {q.rate_used:.2f} ₽"
            )
        else:
            await message.answer(f"❌ Ошибка курса: {q.error}")
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")


@router.message(Command("pool"))
async def cmd_pool(message: Message):
    try:
        q = await feed.quote(1_000_000)
        if q.ok:
            await message.answer(
                f"🏦 <b>DeDust-пул TSAR/USDT</b>\n\n"
                f"1 000 000 ЦАРЬ = <b>{q.rub_amount:.2f} ₽</b>\n"
                f"1 ЦАРЬ ≈ {q.tsar_price_usd*100:.6f} ¢\n"
                f"Источник: {q.source}\n"
                f"Пул: <code>{short_master(TSAR_PRIMARY_POOL)}</code>"
            )
        else:
            await message.answer(f"❌ Ошибка пула: {q.error}")
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")


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
    await callback.message.edit_text(
        f"{token.emoji} Выбран: <b>{token.symbol} {token.name}</b>\n\n"
        f"Адрес (jetton-master): <code>{token.master}</code>\n"
        f"Минимальная сумма: {token.min_tsar:,} ЦАРЬ\n\n"
        "Введи количество ЦАРЬ для обмена:"
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
    token_slug = data.get("token_slug")
    amount = data.get("amount")
    user_id = message.from_user.id
    token = get_token(token_slug)
    try:
        from api.payouts.models import PayoutMethod
        result = await payout_service.payout(
            user_id=user_id,
            tsar_amount=amount,
            recipient=card,
            method=PayoutMethod.CARD_RU,
        )
        if result.ok:
            payout = result.payout
            ad = result.p2p_ad
            await message.answer(
                f"✅ <b>Заявка создана</b>\n\n"
                f"Токен: {token.emoji if token else '👑'} {token.name if token else ''}\n"
                f"ID: <code>{payout.id}</code>\n"
                f"Сумма: {amount:,.0f} ЦАРЬ\n"
                f"Получишь: <b>{payout.amount_rub:.2f} ₽</b>\n"
                f"На карту: <code>{card[:6]}****{card[-4:]}</code>\n\n"
                f"🤝 P2P-партнёр: {ad.nickname if ad else '—'}\n"
                f"Курс: {ad.price if ad else 0:.2f} ₽/USDT\n\n"
                f"Переведи ЦАРЬ на:\n<code>{USDT_TREASURY_ADDRESS}</code>\n"
                f"После прихода ЦАРЬ бот сам определит серию и свяжет с заявкой."
            )
        else:
            await message.answer(f"❌ Ошибка: {result.error}")
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")
    await state.clear()


@router.callback_query(F.data == "rate")
async def on_rate(callback: CallbackQuery):
    try:
        q = await feed.quote(1_000_000)
        if q.ok:
            await callback.message.edit_text(
                f"💱 <b>Курс ЦАРЬ</b>\n\n"
                f"1 000 000 ЦАРЬ = <b>{q.rub_amount:.2f} ₽</b>\n"
                f"1 ЦАРЬ ≈ {q.tsar_price_usd*100:.6f} ¢\n"
                f"Источник: {q.source}\n"
                f"Курс USD/RUB: {q.rate_used:.2f} ₽",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="◀ Назад", callback_data="back")]])
            )
        else:
            await callback.message.edit_text(f"❌ Ошибка: {q.error}")
    except Exception as e:
        await callback.message.edit_text(f"❌ Ошибка: {e}")
    await callback.answer()


@router.callback_query(F.data == "pool_rate")
async def on_pool_rate(callback: CallbackQuery):
    try:
        q = await feed.quote(1_000_000)
        if q.ok:
            await callback.message.edit_text(
                f"🏦 <b>DeDust TSAR/USDT</b>\n\n"
                f"1 000 000 ЦАРЬ = <b>{q.rub_amount:.2f} ₽</b>\n"
                f"1 ЦАРЬ ≈ {q.tsar_price_usd*100:.6f} ¢\n"
                f"Источник: {q.source}\n"
                f"Пул: <code>{short_master(TSAR_PRIMARY_POOL)}</code>",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="◀ Назад", callback_data="back")]])
            )
        else:
            await callback.message.edit_text(f"❌ Ошибка пула: {q.error}")
    except Exception as e:
        await callback.message.edit_text(f"❌ Ошибка: {e}")
    await callback.answer()


@router.callback_query(F.data == "pools")
async def on_pools(callback: CallbackQuery):
    try:
        ads = await p2p_client.get_buy_ads(crypto="USDT", fiat="RUB", side="BUY", page_size=5)
        if not ads:
            text = "📊 <b>P2P-объявления (BUY USDT)</b>\n\nНет активных объявлений."
        else:
            lines = ["📊 <b>P2P-объявления (покупка USDT)</b>\n"]
            for a in ads[:5]:
                lines.append(
                    f"• <b>{a.nickname}</b> — {a.price:.2f} ₽/USDT\n"
                    f"  доступно: {a.available_usdt:,.0f} USDT\n"
                    f"  способы: {', '.join(a.payments[:3])}\n"
                )
            text = "\n".join(lines)
        await callback.message.edit_text(
            text,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="◀ Назад", callback_data="back")]])
        )
    except Exception as e:
        await callback.message.edit_text(
            f"❌ P2P недоступен: {e}\n"
            f"<i>Когда добавишь P2P_API_KEY в секреты — кнопка заработает.</i>",
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
        "👑 <b>ЦАРЬ Обменник</b>\n\n"
        "Выбери токен:",
        reply_markup=main_menu()
    )
    await callback.answer()


# === TonWatcher: автоопределение токена по входящему IP-переводу ===
async def on_incoming_transfer(t: IncomingTransfer) -> None:
    """Уведомляет админа (или пишет в лог), когда кто-то переводит ЦАРЬ на казну."""
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
    logger.info("Bot starting...")
    await bot.delete_webhook(drop_pending_updates=True)
    # Запускаем TON-watcher для автодетекта IP-переводов
    watcher = TonWatcher(poll_interval_sec=15.0, on_transfer=on_incoming_transfer)
    watcher.start()
    logger.info("TonWatcher started")
    try:
        await dp.start_polling(bot, skip_updates=True)
    finally:
        await watcher.stop()


if __name__ == "__main__":
    asyncio.run(main())