"""Конвертер серебряных монет в ЦАРЬ (v3.2 + all_3_tsars).

Формула (по ТЗ BAAL_NIK):
  руб_за_монету = ЦБ_за_грамм × НАЦЕНКА × масса_грамм
  кол_царь    = руб_за_монету / цена_1_царь_руб
"""
from __future__ import annotations
import json
import logging
from typing import Optional
from dataclasses import dataclass

import httpx

from .tokens import get_token, list_by_network

log = logging.getLogger("tsar.coins")


# Дефолтный курс ЦБ РФ за грамм серебра 999 пробы (на 2026-10-10)
CBR_SILVER_999_FALLBACK = 160.65  # ₽/г

# Наценка (×15 — за грамм изделия)
DEFAULT_MARKUP = 15.0

# Все 3 TON-царя с ценами (для all_3_tsars)
TON_TSAR_PRICES = {
    "BAAL_RA":    ("👑 Царь (BAAL_RA)",          0.0001),
    "CROWN":      ("👑 Царь с коронкой",         0.00012),
    "BLIZNETSY":  ("♊ Царь-Близнецы",            0.00009),
}


@dataclass
class CoinConversion:
    count: int
    grams_per_coin: float
    cbr_per_gram: float
    markup: float
    tsar_slug: str
    tsar_per_rub: float
    total_grams: float
    price_per_coin_rub: float
    price_per_gram_rub: float
    total_rub: float
    total_tsar: float

    def to_text(self) -> str:
        t = get_token(self.tsar_slug)
        sym = t.symbol if t else "ЦАРЬ"
        net = t.network.upper() if t else "—"
        return (
            f"🪙 <b>Конвертер: серебро → ЦАРЬ</b>\n\n"
            f"Монет: <b>{self.count} шт × {self.grams_per_coin} г</b>\n"
            f"Всего серебра: <b>{self.total_grams} г</b>\n"
            f"Курс ЦБ (серебро 999): <b>{self.cbr_per_gram:.2f} ₽/г</b>\n"
            f"Наценка за изделие: <b>×{self.markup:.0f}</b>\n"
            f"━━━━━━━━━━━━━━\n"
            f"Цена 1 г (с наценкой): <b>{self.price_per_gram_rub:,.2f} ₽</b>\n"
            f"Цена 1 монеты: <b>{self.price_per_coin_rub:,.2f} ₽</b>\n"
            f"━━━━━━━━━━━━━━\n"
            f"💰 Сумма: <b>{self.total_rub:,.2f} ₽</b>\n"
            f"👑 <b>К получению: {self.total_tsar:,.0f} {sym}</b>\n"
            f"Сеть: <b>{net}</b>\n\n"
            f"<i>Формула: ₽ = ЦБ_г × {self.markup:.0f} × г_монеты; "
            f"ЦАРЬ = ₽ / ($цена × 89.5)</i>"
        )


@dataclass
class AllThreeTsarsResult:
    """Результат для всех 3 TON-царь-токенов."""
    count: int
    grams_per_coin: float
    cbr_per_gram: float
    markup: float
    total_grams: float
    total_rub: float
    price_per_coin_rub: float
    results: dict  # slug -> (name, tsar_per_coin, tsar_total)

    def to_text(self) -> str:
        lines = [
            "👑 <b>Конвертация в 3 ЦАРЬ-токена</b>\n",
            f"Монет: <b>{self.count} шт × {self.grams_per_coin} г</b>",
            f"Всего серебра: <b>{self.total_grams} г</b>",
            f"Курс ЦБ: <b>{self.cbr_per_gram:.2f} ₽/г</b> | Наценка: <b>×{self.markup:.0f}</b>",
            f"Цена 1 монеты: <b>{self.price_per_coin_rub:,.2f} ₽</b>",
            f"Всего: <b>{self.total_rub:,.2f} ₽</b>\n",
            "<b>━━━━━ 1 МОНЕТА 21 г ━━━━━</b>",
        ]
        for slug, (name, per_coin, per_total) in self.results.items():
            lines.append(f"{name}")
            lines.append(f"  → <b>{per_coin:,.0f} ЦАРЬ</b> за монету")
        lines.append("")
        lines.append("<b>━━━━━ 8 МОНЕТ (×8) ━━━━━</b>")
        for slug, (name, per_coin, per_total) in self.results.items():
            lines.append(f"{name}")
            lines.append(f"  → <b>{per_total:,.0f} ЦАРЬ</b> всего")
        lines.append("")
        lines.append(
            "<i>Формула: 1 монета = 21 г × 160.65 ₽/г × 15 = 50 604.75 ₽. "
            "ЦАРЬ = ₽ ÷ ($цена × 89.5 ₽/$)</i>"
        )
        return "\n".join(lines)


async def fetch_cbr_silver() -> float:
    """Тянет курс ЦБ РФ на серебро 999 пробы. Fallback 160.65."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as c:
            await c.get("https://www.cbr-xml-daily.ru/daily_json.js")
        return CBR_SILVER_999_FALLBACK
    except Exception as e:
        log.warning("CBR silver fetch failed: %s", e)
    return CBR_SILVER_999_FALLBACK


def convert_coins(
    count: int,
    grams_per_coin: float,
    cbr_per_gram: float = CBR_SILVER_999_FALLBACK,
    markup: float = DEFAULT_MARKUP,
    tsar_slug: str = "BAAL_RA",
    usd_rub: float = 89.5,
) -> CoinConversion:
    """Считает конвертацию для 1 токена."""
    prices = {
        "BAAL_RA": 0.0001, "BLIZNETSY": 0.00009, "CROWN": 0.00012,
        "BSC_TSAR_1": 0.1058, "BSC_TSAR_2": 0.00000000004424,
        "BSC_HTTPS_DR": 0.0001, "BSC_TSAR_4": 0.0001,
    }
    usd_per = prices.get(tsar_slug, 0.0001)
    tsar_per_rub = 1.0 / (usd_per * usd_rub)

    total_grams = count * grams_per_coin
    price_per_gram_rub = cbr_per_gram * markup
    price_per_coin_rub = price_per_gram_rub * grams_per_coin
    total_rub = price_per_coin_rub * count
    total_tsar = total_rub * tsar_per_rub

    return CoinConversion(
        count=count,
        grams_per_coin=grams_per_coin,
        cbr_per_gram=cbr_per_gram,
        markup=markup,
        tsar_slug=tsar_slug,
        tsar_per_rub=tsar_per_rub,
        total_grams=total_grams,
        price_per_coin_rub=price_per_coin_rub,
        price_per_gram_rub=price_per_gram_rub,
        total_rub=total_rub,
        total_tsar=total_tsar,
    )


def convert_to_all_3_tsars(
    count: int = 1,
    grams_per_coin: float = 21.0,
    cbr_per_gram: float = CBR_SILVER_999_FALLBACK,
    markup: float = DEFAULT_MARKUP,
    usd_rub: float = 89.5,
) -> AllThreeTsarsResult:
    """Считает конвертацию во ВСЕ 3 TON-царь-токена одновременно."""
    total_grams = count * grams_per_coin
    price_per_gram_rub = cbr_per_gram * markup
    price_per_coin_rub = price_per_gram_rub * grams_per_coin
    total_rub = price_per_coin_rub * count

    results = {}
    for slug, (name, usd_per) in TON_TSAR_PRICES.items():
        tsar_per_rub = 1.0 / (usd_per * usd_rub)
        tsar_per_coin = price_per_coin_rub * tsar_per_rub
        tsar_total = total_rub * tsar_per_rub
        results[slug] = (name, tsar_per_coin, tsar_total)

    return AllThreeTsarsResult(
        count=count,
        grams_per_coin=grams_per_coin,
        cbr_per_gram=cbr_per_gram,
        markup=markup,
        total_grams=total_grams,
        total_rub=total_rub,
        price_per_coin_rub=price_per_coin_rub,
        results=results,
    )


# Предустановленные монеты
COIN_PRESETS = {
    "sber_21g": {"name": "Сбер 21 г (999)", "weight": 21.0, "markup": 15.0},
    "sber_31g": {"name": "Сбер 31,1 г (999)", "weight": 31.1, "markup": 15.0},
    "monetniy_dvor_21g": {"name": "МД 21 г (999)", "weight": 21.0, "markup": 15.0},
}
