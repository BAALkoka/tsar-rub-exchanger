"""Тесты нормализации телефонов и определения типа получателя.

Реальные имена методов: PayoutService._norm_phone, detect_recipient_kind.
"""
from __future__ import annotations

import pytest

from src.api.payouts.models import PayoutMethod
from src.api.payouts.service import PayoutService, detect_recipient_kind


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("+79001234567", "+79001234567"),
        ("89001234567", "+79001234567"),
        ("9001234567", "+79001234567"),
        ("7 900 123 45 67", "+79001234567"),
        ("+7 (900) 123-45-67", "+79001234567"),
    ],
)
def test_norm_phone_formats(raw, expected):
    """8, +7, 7 и 10 цифр, с пробелами и скобками — один результат."""
    assert PayoutService._norm_phone(raw) == expected


@pytest.mark.parametrize("raw", ["123", "abc", "", "+7900", "89001234567890"])
def test_norm_phone_rejects_invalid(raw):
    """Некорректные номера не проходят нормализацию."""
    assert PayoutService._norm_phone(raw) is None


def test_detect_recipient_kind_phone():
    """+7, 8 и 10 цифр без префикса — это всё телефон для СБП."""
    assert detect_recipient_kind("+79001234567") == PayoutMethod.SBP
    assert detect_recipient_kind("89001234567") == PayoutMethod.SBP
    assert detect_recipient_kind("9001234567") == PayoutMethod.SBP


def test_detect_recipient_kind_cards():
    assert detect_recipient_kind("4276380000000000") == PayoutMethod.CARD_RU
    assert detect_recipient_kind("DE89370400440532013000") == PayoutMethod.CARD_FOREIGN


def test_detect_recipient_kind_rejects_garbage():
    with pytest.raises(ValueError):
        detect_recipient_kind("не телефон")
