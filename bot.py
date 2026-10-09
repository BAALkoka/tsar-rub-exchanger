"""Telegram-бот для обмена ЦАРЬ → RUB → карта.

Команды:
  /start    — приветствие + меню
  /quote    — текущий курс (с inline-выбором токена)
  /sell N   — расчёт для N ЦАРЬ
  /withdraw N +7... — вывести N ЦАРЬ на карту/СБП
  /history  — последние 10 обменов
  /help     — справка

Кнопки:
  Главное меню: [💰 Курс] [📊 Калькулятор] [💸 Вывести] [📜 История] [❓ Помощь]
  Токены:       [👑 Царь] [👑👑 С коронкой] [👑💎 Близнецы]

Запуск:
  export TELEGRAM_BOT_TOKEN=...    # от @BotFather
  export P2P_API_KEY=...            # от @wallet (опц., mock без него)
  export WALLET_MNEMONIC="..."      # 24 слова (опц., mock без него)
  python bot.py
"""
import asyncio
import logging
import os
import sys
from pathlib import Path

# /src в sys.path
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from aiogram import Bot, Dispatcher, types
from aiogram.client.default import DefaultBotProperties
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from aiogram.enums import ParseMode

from api.payouts.price_feed import PriceFeed
from api.payouts.p2p import P2PClient
from api.payouts.service import PayoutService
from api.payouts.tokens import list_tokens, get_token
from api.payouts.models import PayoutMethod
from api.payouts.config import SUPPORT_HANDLE, MIN_PAYOUT_TSAR

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# === Конфиг ===
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
ADMIN_CHAT_ID = int(os.getenv("ADMIN_CHAT_ID", "0") or "0")

if not TELEGRAM_BOT_TOKEN:
    sys.exit("❌ TELEGRAM_BOT_TOKEN не задан (задай через GitHub Secrets или export)")

# === Клиенты (создаются по требованию) ===
def make_clients(slug: str = "BAAL_RA"):
    try:
        token = get_token(slug)
        feed = PriceFeed(token_master=token.master, token_pool=token.pool, pool_label=token.pool_label)
    except Exception as e:
        logger.warning("PriceFeed init failed for %s: %s — fallback default", slug, e)
        feed = PriceFeed()
    p2p = P2PClient()
    service = PayoutService(p2p_client=p2p, price_feed=feed, sbp_client=None, ton_payout=None)
    return feed, p2p, service


# === Кнопки ===
def main_menu_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="💰 Курс"), KeyboardButton(text="📊 Калькулятор")],
            [KeyboardButton(text="💸 Вывести"), KeyboardButton(text="📜 История")],
            [KeyboardButton(text="❓ Помощь")],
        ],
        resize_keyboard=True,
    )


def tokens_inline_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=f"{t.emoji} {t.label}", callback_data=f"quote:{t.slug}")]
            for t in list_tokens()
        ]
    )


# === Бот ===
bot = Bot(
    token=TELEGRAM_BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML),
)
dp = Dispatcher()


@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer(
        f"👑 <b>ЦАРЬ → РУБЛЬ</b>\n\n"
        f"Обмен ЦАРЬ на рубли с выводом на карту/СБП.\n"
        f"Курс обновляется по DeDust-пулу.\n\n"
        f"Поддержка: {SUPPORT_HANDLE}",
        reply_markup=main_menu_kb(),
    )


@dp.message(Command("help"))
async def cmd_help(message: types.Message):
    await message.answer(
        f"👑 <b>Команды</b>\n\n"
        f"/quote — текущий курс (выбор токена)\n"
        f"/sell N — расчёт для N ЦАРЬ\n"
        f"/withdraw N +7... — вывод на СБП\n"
        f"/history — последние 10 обменов\n"
        f"/help — эта справка\n\n"
        f"Минимум к выводу: {MIN_PAYOUT_TSAR:,.0f} ЦАРЬ\n"
        f"Поддержка: {SUPPORT_HANDLE}",
        reply_markup=main_menu_kb(),
    )


@dp.message(Command("quote"))
async def cmd_quote(message: types.Message):
    await message.answer("👑 Выбери токен:", reply_markup=tokens_inline_kb())


@dp.callback_query(lambda c: c.data and c.data.startswith("quote:"))
async def cb_quote_token(callback: types.CallbackQuery):
    slug = callback.data.split(":", 1)[1]
    feed, p2p, service = make_clients(slug)
    try:
        q = await service.quote(1.0)
        if not q.ok:
            await callback.message.answer(f"❌ Не удалось получить курс: {q.error}")
            await callback.answer()
            return
        rate = q.payout.rate
        ads = await p2p.get_buy_ads(force_refresh=True)
        best = min(ads, key=lambda a: a.price) if ads else None
        text = f"💰 <b>Курс: {get_token(slug).label}</b>\n\n"
        text += f"1 ЦАРЬ = <b>{rate:.4f} ₽</b>\n"
        text += f"Источник: {q.stages[1] if len(q.stages) > 1 else '—'}\n"
        if best:
            text += f"Лучший P2P: <b>{best.nickname}</b> @ {best.price:.2f} ₽/USDT\n"
        text += f"\nПолучить 100₽ → <code>{(100 / rate):.4f}</code> ЦАРЬ"
        await callback.message.answer(text)
    finally:
        await p2p.close()
        await feed.close()
    await callback.answer()


@dp.message(Command("sell"))
async def cmd_sell(message: types.Message):
    parts = (message.text or "").split()
    if len(parts) < 2:
        await message.answer("📊 <b>Калькулятор</b>\n\nВведи: /sell 1.2 (где 1.2 — количество ЦАРЬ)")
        return
    try:
        amount = float(parts[1].replace(",", "."))
    except ValueError:
        await message.answer("❌ Неверная сумма. Пример: /sell 1.2")
        return

    feed, p2p, service = make_clients()
    try:
        q = await service.quote(amount)
        if not q.ok:
            await message.answer(f"❌ {q.error}")
            return
        service_fee = q.payout.amount_rub * 0.25 / 100
        sbp_fee = q.payout.amount_rub * 0.40 / 100
        gross = q.payout.amount_rub + service_fee + sbp_fee
        text = (
            f"📊 <b>Расчёт для {amount} ЦАРЬ</b>\n\n"
            f"Курс: {q.payout.rate:.4f} ₽/ЦАРЬ\n"
            f"Gross: {gross:.2f} ₽ (до комиссий)\n"
            f"Комиссия сервиса 0.25%: -{service_fee:.2f} ₽\n"
            f"Комиссия СБП 0.40%: -{sbp_fee:.2f} ₽\n"
            f"💵 <b>К получению: {q.payout.amount_rub:.2f} ₽</b>\n\n"
            f"Для вывода: /withdraw {amount} +7XXXXXXXXXX"
        )
        await message.answer(text)
    finally:
        await p2p.close()
        await feed.close()


@dp.message(Command("withdraw"))
async def cmd_withdraw(message: types.Message):
    parts = (message.text or "").split()
    if len(parts) < 3:
        await message.answer(
            f"💸 <b>Вывод</b>\n\n"
            f"Формат: /withdraw СУММА ТЕЛЕФОН\n"
            f"Пример: /withdraw 250000 +79001234567"
        )
        return
    try:
        amount = float(parts[1].replace(",", "."))
    except ValueError:
        await message.answer("❌ Неверная сумма")
        return
    recipient = parts[2]

    feed, p2p, service = make_clients()
    try:
        q = await service.quote(amount)
        if not q.ok:
            await message.answer(f"❌ {q.error}")
            return
        text = (
            f"💸 <b>Подтвердите вывод</b>\n\n"
            f"Сумма: {amount} ЦАРЬ\n"
            f"Курс: {q.payout.rate:.4f} ₽/ЦАРЬ\n"
            f"Получите: <b>{q.payout.amount_rub:.2f} ₽</b>\n"
            f"На: {recipient}\n"
            f"Способ: СБП\n\n"
            f"⚠️ В mock-режиме деньги реально не переводятся.\n"
            f"Для боевого режима нужен P2P_API_KEY + СБП-провайдер."
        )
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"do:{amount}:{recipient}")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")],
        ])
        await message.answer(text, reply_markup=kb)
    finally:
        await p2p.close()
        await feed.close()


@dp.callback_query(lambda c: c.data and c.data.startswith("do:"))
async def cb_do_withdraw(callback: types.CallbackQuery):
    _, amount_str, recipient = callback.data.split(":", 2)
    amount = float(amount_str)
    feed, p2p, service = make_clients()
    try:
        r = await service.execute(
            user_id=callback.from_user.id,
            tsar_amount=amount,
            recipient=recipient,
            method=PayoutMethod.SBP,
        )
        if r.ok:
            text = (
                f"✅ <b>Готово!</b>\n\n"
                f"Сумма: {r.payout.amount_rub:.2f} ₽\n"
                f"External ID: {r.payout.external_id}\n"
                f"Статусы: {' → '.join(r.stages)}\n\n"
                f"⚠️ Mock-режим: деньги реально не переведены."
            )
        else:
            text = f"❌ Ошибка: {r.error}\n\nСтатусы: {r.stages}"
        await callback.message.answer(text)
    finally:
        await p2p.close()
        await feed.close()
    await callback.answer()


@dp.callback_query(lambda c: c.data == "cancel")
async def cb_cancel(callback: types.CallbackQuery):
    await callback.message.answer("❌ Отменено")
    await callback.answer()


@dp.message(Command("history"))
async def cmd_history(message: types.Message):
    await message.answer("📜 История обменов появится здесь (mock-режим: пусто)")


# === Reply-кнопки ===
@dp.message(lambda m: m.text == "💰 Курс")
async def menu_quote(message: types.Message):
    await cmd_quote(message)


@dp.message(lambda m: m.text == "📊 Калькулятор")
async def menu_calc(message: types.Message):
    await message.answer("📊 Введи: /sell 1.2 (количество ЦАРЬ)")


@dp.message(lambda m: m.text == "💸 Вывести")
async def menu_withdraw(message: types.Message):
    await message.answer(
        f"💸 <b>Вывод на СБП</b>\n\n"
        f"Формат: /withdraw СУММА +7XXXXXXXXXX\n"
        f"Пример: /withdraw 250000 +79001234567\n\n"
        f"Мин. сумма: {MIN_PAYOUT_TSAR:,.0f} ЦАРЬ"
    )


@dp.message(lambda m: m.text == "📜 История")
async def menu_history(message: types.Message):
    await cmd_history(message)


@dp.message(lambda m: m.text == "❓ Помощь")
async def menu_help(message: types.Message):
    await cmd_help(message)


async def main():
    logger.info("🚀 Tsar-bot starting...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
