"""Telegram-бот "ЦАРЬ бот обменник" — финальная версия.

UX (как у "ЦАРЬ бот обменник"):
  • Inline-кнопка "ЦАРЬ" в поле ввода для быстрого ввода количества
  • Кнопка "⏪ Назад" в FSM-сообщениях (отмена шага)
  • Двухшаговый flow: ввод суммы → ввод телефона → подтверждение
  • Главное меню: [💰 Курс] [📊 Калькулятор] [💸 Продать] [📜 История] [❓ Помощь]
  • Inline-выбор токена при /quote

Pipeline (наш PayoutService):
  PriceFeed → P2PClient.best_buy_ad → (опц. ton_payout) → SbpClient.payout
  Mock-режим: всё работает без боевых ключей.

Команды:
  /start      — приветствие + меню
  /quote      — курс (с inline-выбором токена)
  /sell N     — расчёт для N ЦАРЬ (без FSM)
  /withdraw   — пошаговый вывод (FSM)
  /history    — история (mock-пусто)
  /help       — справка
"""
import asyncio
import logging
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from aiogram import Bot, Dispatcher, F, types
from aiogram.client.default import DefaultBotProperties
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    KeyboardButton,
    WebAppInfo,
)
from aiogram.enums import ParseMode

from api.payouts.price_feed import PriceFeed
from api.payouts.p2p import P2PClient
from api.payouts.service import PayoutService
from api.payouts.tokens import list_tokens, get_token
from api.payouts.models import PayoutMethod
from api.payouts.config import SUPPORT_HANDLE, MIN_PAYOUT_TSAR

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
ADMIN_CHAT_ID = int(os.getenv("ADMIN_CHAT_ID", "0") or "0")

if not TELEGRAM_BOT_TOKEN:
    sys.exit("❌ TELEGRAM_BOT_TOKEN не задан (GitHub Secrets или export)")


# === FSM ===
class WithdrawFSM(StatesGroup):
    waiting_amount = State()   # ждём количество ЦАРЬ
    waiting_phone = State()    # ждём номер телефона


# === Клиенты (lazy) ===
def make_clients(slug: str = "BAAL_RA"):
    try:
        token = get_token(slug)
        feed = PriceFeed(
            token_master=token.master,
            token_pool=token.pool,
            pool_label=token.pool_label,
        )
    except Exception as e:
        logger.warning("PriceFeed init failed for %s: %s — fallback default", slug, e)
        feed = PriceFeed()
    p2p = P2PClient()
    service = PayoutService(
        p2p_client=p2p, price_feed=feed, sbp_client=None, ton_payout=None,
    )
    return feed, p2p, service


# === Кнопки ===
def main_menu_kb() -> ReplyKeyboardMarkup:
    """Главное меню: 2 кнопки в ряд, компактно (3 ряда)."""
    return ReplyKeyboardMarkup(
        keyboard=[
            # Ряд 1: основные действия
            [KeyboardButton(text="💰 Курс"), KeyboardButton(text="💸 Продать")],
            # Ряд 2: инфо + история
            [KeyboardButton(text="📊 Калькулятор"), KeyboardButton(text="📜 История")],
            # Ряд 3: внешние ссылки (WebApp)
            [
                KeyboardButton(text="🌐 Сайт", web_app=WebAppInfo(url=SITE_URL)),
                KeyboardButton(text="🎮 Игра", web_app=WebAppInfo(url=GAME_URL)),
            ],
        ],
        resize_keyboard=True,
    )


def tokens_inline_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text=f"{t.emoji} {t.name}",
                callback_data=f"quote:{t.slug}",
            )]
            for t in list_tokens()
        ]
    )


def confirm_kb(amount: float, phone: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text="✅ Подтвердить",
                callback_data=f"do:{amount}:{phone}",
            )],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")],
        ]
    )


def back_kb(action: str = "main") -> InlineKeyboardMarkup:
    """Кнопка ⏪ Назад для FSM-сообщений."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⏪ Назад", callback_data=action)],
        ]
    )


# === Бот ===
bot = Bot(
    token=TELEGRAM_BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML),
)
dp = Dispatcher()


# ===== /start =====
@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer(
        f"👑 <b>ЦАРЬ бот обменник</b>\n\n"
        f"Меняю ЦАРЬ на рубли по курсу DeDust-пула.\n"
        f"Вывод через СБП на карту по номеру телефона.\n"
        f"Минимум: {MIN_PAYOUT_TSAR:,.0f} ЦАРЬ.\n\n"
        f"Поддержка: {SUPPORT_HANDLE}",
        reply_markup=main_menu_kb(),
    )
    await message.answer(
        "🌐 <b>Быстрые ссылки:</b>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🌐 Сайт", url=SITE_URL), InlineKeyboardButton(text="🎮 Игра", url=GAME_URL)],
            [InlineKeyboardButton(text="💬 Канал", url="https://t.me/+BAAL_NIK"), InlineKeyboardButton(text="💬 Чат", url="https://t.me/+BAAL_NIK_chat")],
            [InlineKeyboardButton(text="📞 Поддержка", url=f"https://t.me/{SUPPORT_HANDLE.lstrip('@')}")],
        ]),
    )


# ===== /help =====
@dp.message(Command("help"))
async def cmd_help(message: types.Message):
    await message.answer(
        f"👑 <b>Команды</b>\n\n"
        f"/quote — курс (выбор токена)\n"
        f"/sell N — расчёт для N ЦАРЬ (без FSM)\n"
        f"/withdraw — пошаговый вывод (FSM)\n"
        f"/history — история\n"
        f"/help — эта справка\n\n"
        f"💸 <b>Как продать ЦАРЬ</b>\n"
        f"1) Жмёшь «💸 Продать»\n"
        f"2) Вводишь количество (например <code>250000</code>)\n"
        f"3) Вводишь телефон <code>+7XXXXXXXXXX</code>\n"
        f"4) Подтверждаешь\n\n"
        f"Минимум: {MIN_PAYOUT_TSAR:,.0f} ЦАРЬ\n"
        f"Поддержка: {SUPPORT_HANDLE}",
        reply_markup=main_menu_kb(),
    )
    await message.answer(
        f"🌐 <a href="{SITE_URL}">Открыть сайт обменника</a>",
        reply_markup=main_menu_kb(),
    )


# ===== /quote — выбор токена =====
@dp.message(Command("quote"))
async def cmd_quote(message: types.Message):
    await message.answer("👑 Выбери токен:", reply_markup=tokens_inline_kb())


@dp.callback_query(F.data.startswith("quote:"))
async def cb_quote_token(callback: types.CallbackQuery):
    slug = callback.data.split(":", 1)[1]
    feed, p2p, service = make_clients(slug)
    try:
        q = await service.quote(1.0)
        if not q.ok:
            await callback.message.answer(f"❌ Не удалось получить курс: {q.error}")
            await callback.answer()
            return
        ads = await p2p.get_buy_ads(force_refresh=True)
        best = min(ads, key=lambda a: a.price) if ads else None
        token = get_token(slug)
        text = (
            f"💰 <b>Курс: {token.label}</b>\n\n"
            f"1 ЦАРЬ = <b>{q.payout.rate:.4f} ₽</b>\n"
            f"Источник: {q.stages[1] if len(q.stages) > 1 else '—'}\n"
        )
        if best:
            text += f"Лучший P2P: <b>{best.nickname}</b> @ {best.price:.2f} ₽/USDT\n"
        text += f"\nПолучить 100₽ → <code>{(100 / q.payout.rate):.4f}</code> ЦАРЬ"
        await callback.message.answer(text)
    finally:
        await p2p.close()
        await feed.close()
    await callback.answer()


# ===== /sell N — калькулятор =====
@dp.message(Command("sell"))
async def cmd_sell(message: types.Message):
    parts = (message.text or "").split()
    if len(parts) < 2:
        await message.answer(
            "📊 <b>Калькулятор</b>\n\n"
            f"Введи: <code>/sell 250000</code> (количество ЦАРЬ)\n"
            f"Мин. сумма: {MIN_PAYOUT_TSAR:,.0f} ЦАРЬ"
        )
        return
    try:
        amount = float(parts[1].replace(",", ".").replace(" ", ""))
    except ValueError:
        await message.answer("❌ Неверная сумма. Пример: <code>/sell 250000</code>")
        return
    await _show_quote(message, amount)


# ===== /withdraw — запуск FSM =====
@dp.message(Command("withdraw"))
async def cmd_withdraw(message: types.Message, state: FSMContext):
    parts = (message.text or "").split()
    # Быстрый путь: /withdraw 250000 +7...
    if len(parts) >= 3:
        try:
            amount = float(parts[1].replace(",", ".").replace(" ", ""))
        except ValueError:
            await message.answer(
                "❌ Неверная сумма. Пример: <code>/withdraw 250000 +79001234567</code>"
            )
            return
        await state.update_data(amount=amount, recipient=parts[2])
        await _show_confirm(message, state)
        return
    # Пошаговый flow
    await state.set_state(WithdrawFSM.waiting_amount)
    await message.answer(
        f"🏦 <b>Продать ЦАРЬ через СБП</b>\n\n"
        f"Мин. сумма: {MIN_PAYOUT_TSAR:,.0f} ЦАРЬ.\n"
        f"Получишь RUB по номеру телефона через СБП.\n"
        f"Введи количество ЦАРЬ для обмена:",
        reply_markup=back_kb("main"),
    )


# ===== Reply-кнопка "💸 Продать" =====
@dp.message(F.text == "💸 Продать")
async def menu_withdraw(message: types.Message, state: FSMContext):
    await cmd_withdraw(message, state)


# ===== FSM: ждём количество ЦАРЬ =====
@dp.message(StateFilter(WithdrawFSM.waiting_amount))
async def fsm_amount(message: types.Message, state: FSMContext):
    raw = (message.text or "").replace(",", ".").replace(" ", "")
    try:
        amount = float(raw)
    except ValueError:
        await message.answer(
            f"❌ Неверная сумма. Введи число (например <code>250000</code>):",
            reply_markup=back_kb("main"),
        )
        return
    if amount < MIN_PAYOUT_TSAR:
        await message.answer(
            f"❌ Мин. сумма: {MIN_PAYOUT_TSAR:,.0f} ЦАРЬ. Введи больше:",
            reply_markup=back_kb("main"),
        )
        return
    if amount > 1_000_000_000:
        await message.answer(
            "❌ Слишком много. Максимум 1 000 000 000 ЦАРЬ за раз:",
            reply_markup=back_kb("main"),
        )
        return
    await state.update_data(amount=amount)
    await state.set_state(WithdrawFSM.waiting_phone)
    await message.answer(
        f"📱 Сумма: <b>{amount:,.0f} ЦАРЬ</b>.\n"
        f"Введи номер телефона для получения RUB через СБП (формат: <code>+7XXXXXXXXXX</code>):",
        reply_markup=back_kb("back:amount"),
    )


# ===== FSM: ждём телефон =====
@dp.message(StateFilter(WithdrawFSM.waiting_phone))
async def fsm_phone(message: types.Message, state: FSMContext):
    raw = (message.text or "").strip()
    normalized = PayoutService._normalize_phone(raw)
    if not normalized:
        await message.answer(
            "❌ Неверный формат. Введи <code>+7XXXXXXXXXX</code> (11 цифр, начинается с +7):",
            reply_markup=back_kb("back:amount"),
        )
        return
    await state.update_data(recipient=normalized)
    await _show_confirm(message, state)


# === Кнопка ⏪ Назад ===
@dp.callback_query(F.data == "main")
async def cb_back_main(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.answer("Возвращаюсь в главное меню:", reply_markup=main_menu_kb())
    await callback.answer()


@dp.callback_query(F.data == "back:amount")
async def cb_back_amount(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(WithdrawFSM.waiting_amount)
    data = await state.get_data()
    prev_amount = data.get("amount", MIN_PAYOUT_TSAR)
    await callback.message.answer(
        f"⏪ Вернулся к вводу суммы.\n"
        f"Предыдущая: {prev_amount:,.0f} ЦАРЬ.\n"
        f"Введи новое количество ЦАРЬ для обмена:",
        reply_markup=back_kb("main"),
    )
    await callback.answer()


# === Показать расчёт + кнопки подтверждения ===
async def _show_confirm(source_message: types.Message, state: FSMContext):
    data = await state.get_data()
    amount = float(data["amount"])
    phone = data["recipient"]
    feed, p2p, service = make_clients()
    try:
        q = await service.quote(amount)
        if not q.ok:
            await source_message.answer(f"❌ {q.error}", reply_markup=main_menu_kb())
            await state.clear()
            return
        service_fee = q.payout.amount_rub * 0.25 / 100
        sbp_fee = q.payout.amount_rub * 0.40 / 100
        gross = q.payout.amount_rub + service_fee + sbp_fee
        text = (
            f"💸 <b>Подтвердите вывод</b>\n\n"
            f"💰 Курс: {q.payout.rate:.4f} ₽/ЦАРЬ\n"
            f"📊 Сумма: {amount:,.4f} ЦАРЬ\n"
            f"💵 Gross: {gross:.2f} ₽\n"
            f"📉 Сервис 0.25%: −{service_fee:.2f} ₽\n"
            f"📉 СБП 0.40%: −{sbp_fee:.2f} ₽\n"
            f"💎 <b>К получению: {q.payout.amount_rub:.2f} ₽</b>\n"
            f"📞 Телефон: {phone}\n"
            f"🏦 Способ: СБП\n\n"
            f"⚠️ Mock-режим: деньги реально не переводятся."
        )
        await source_message.answer(text, reply_markup=confirm_kb(amount, phone))
    finally:
        await p2p.close()
        await feed.close()


# === Показать расчёт для /sell N (без FSM) ===
async def _show_quote(message: types.Message, amount: float):
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
            f"📊 <b>Расчёт для {amount:,.4f} ЦАРЬ</b>\n\n"
            f"💰 Курс: {q.payout.rate:.4f} ₽/ЦАРЬ\n"
            f"💵 Gross: {gross:.2f} ₽\n"
            f"📉 Сервис 0.25%: −{service_fee:.2f} ₽\n"
            f"📉 СБП 0.40%: −{sbp_fee:.2f} ₽\n"
            f"💎 <b>К получению: {q.payout.amount_rub:.2f} ₽</b>\n\n"
            f"Для вывода нажми «💸 Продать» в меню."
        )
        await message.answer(text)
    finally:
        await p2p.close()
        await feed.close()


# ===== Подтверждение вывода =====
@dp.callback_query(F.data.startswith("do:"))
async def cb_do_withdraw(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
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
                f"💎 Получено: {r.payout.amount_rub:.2f} ₽\n"
                f"📞 На телефон: {recipient}\n"
                f"🆔 External ID: <code>{r.payout.external_id}</code>\n"
                f"📊 Стадии: <i>{' → '.join(r.stages)}</i>\n\n"
                f"⚠️ Mock-режим: деньги реально не переведены."
            )
        else:
            text = f"❌ Ошибка: {r.error}\n\nСтадии: {r.stages}"
        await callback.message.answer(text, reply_markup=main_menu_kb())
    finally:
        await p2p.close()
        await feed.close()
    await callback.answer()


# ===== Отмена =====
@dp.callback_query(F.data == "cancel")
async def cb_cancel(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.answer("❌ Отменено", reply_markup=main_menu_kb())
    await callback.answer()


# ===== /history =====
@dp.message(Command("history"))
async def cmd_history(message: types.Message):
    await message.answer(
        "📜 <b>История обменов</b>\n\n"
        "В mock-режиме история пуста. После первого боевого вывода здесь появятся записи."
    )


# ===== Reply-кнопки (без состояния) =====
@dp.message(F.text == "💰 Курс")
async def menu_quote(message: types.Message):
    await cmd_quote(message)


@dp.message(F.text == "📊 Калькулятор")
async def menu_calc(message: types.Message):
    await message.answer(
        "📊 <b>Калькулятор</b>\n\n"
        "Введи: <code>/sell 250000</code> (количество ЦАРЬ)"
    )


@dp.message(F.text == "📜 История")
async def menu_history(message: types.Message):
    await cmd_history(message)


@dp.message(F.text == "❓ Помощь")
async def menu_help(message: types.Message):
    await cmd_help(message)


async def main():
    logger.info("🚀 ЦАРЬ бот обменник (FSM-mode) starting...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
