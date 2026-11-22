"""Тесты TON-перевода ЦАРЬ: слаги, деривация jetton-кошелька, mock-режим."""
from __future__ import annotations

import pytest

from src.api.payouts.ton_payout import (
    TON_JETTON_MASTERS,
    TonPayout,
    TonPayoutError,
    _raw_to_user_friendly,
    _user_friendly_to_raw,
    derive_jetton_wallet,
    normalize_slug,
    supported_slugs,
)

# --- слаги ---------------------------------------------------

def test_supported_slugs_contains_three_tokens():
    slugs = supported_slugs()
    assert "BAAL_RA" in slugs
    assert "BLIZNETSY" in slugs
    assert "CROWN" in slugs
    assert len(slugs) == 3


def test_masters_are_distinct():
    masters = list(TON_JETTON_MASTERS.values())
    assert len(masters) == len(set(masters))


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("baal_ra", "BAAL_RA"),
        ("BAAL", "BAAL_RA"),
        ("близнецы", "BLIZNETSY"),
        ("bliznetsy", "BLIZNETSY"),
        ("crown", "CROWN"),
        ("  crown  ", "CROWN"),
        ("BAAL-RA", "BAAL_RA"),
    ],
)
def test_normalize_slug(raw, expected):
    assert normalize_slug(raw) == expected


def test_normalize_slug_rejects_unknown():
    with pytest.raises(TonPayoutError):
        normalize_slug("НЕТ_ТАКОГО")


# --- адреса --------------------------------------------------

def test_raw_user_friendly_roundtrip():
    raw = "0:b90f75c8adcefbedb72bf04390dbf64130fb9e3d4a93fb3cd64ebf7ea491287b"
    uf = _raw_to_user_friendly(raw)
    assert uf.startswith("EQ")
    assert _user_friendly_to_raw(uf) == raw


def test_user_friendly_to_raw_accepts_raw_asis():
    raw = "0:b90f75c8adcefbedb72bf04390dbf64130fb9e3d4a93fb3cd64ebf7ea491287b"
    assert _user_friendly_to_raw(raw) == raw


def test_user_friendly_to_raw_rejects_garbage():
    with pytest.raises(TonPayoutError):
        _user_friendly_to_raw("EQне-мусор!!!")


# --- деривация jetton-кошелька -------------------------------

OWNER = "EQDrLq-X6jKZ3D4MjBQK2c6dAR3wK1D7c7-3X-4Y-5Z-6A-7B"


def test_derive_jetton_wallet_is_deterministic():
    a = derive_jetton_wallet(owner=OWNER, master=TON_JETTON_MASTERS["BAAL_RA"])
    b = derive_jetton_wallet(owner=OWNER, master=TON_JETTON_MASTERS["BAAL_RA"])
    assert a.address == b.address
    assert a.raw == b.raw
    assert a.address_hash == b.address_hash


def test_derive_jetton_wallet_differs_per_master():
    a = derive_jetton_wallet(owner=OWNER, master=TON_JETTON_MASTERS["BAAL_RA"])
    b = derive_jetton_wallet(owner=OWNER, master=TON_JETTON_MASTERS["CROWN"])
    assert a.address != b.address


def test_derive_jetton_wallet_shape():
    info = derive_jetton_wallet(owner=OWNER, master=TON_JETTON_MASTERS["BLIZNETSY"])
    assert info.address.startswith("EQ")
    assert info.raw.startswith("0:")
    assert len(info.address_hash) == 64
    assert info.master == TON_JETTON_MASTERS["BLIZNETSY"]


# --- сам клиент ----------------------------------------------

async def test_mock_mode_without_mnemonic():
    p = TonPayout()
    assert p.is_mock is True
    assert p.is_configured is False


async def test_get_jetton_wallet_per_slug():
    p = TonPayout()
    for slug in supported_slugs():
        info = await p.get_jetton_wallet(slug)
        assert info.slug == slug
        assert info.master == TON_JETTON_MASTERS[slug]
        assert info.address.startswith("EQ")


async def test_get_all_jetton_wallets_returns_three():
    p = TonPayout()
    wallets = await p.get_all_jetton_wallets()
    assert set(wallets) == set(supported_slugs())
    addresses = {w.address for w in wallets.values()}
    assert len(addresses) == 3


async def test_send_tsar_mock_returns_tx():
    p = TonPayout()
    tx = await p.send_tsar(amount=1.5, slug="BAAL_RA")
    assert tx.source == "mock"
    assert tx.tx_hash.startswith("mock_")
    assert tx.amount == 1.5
    assert tx.amount_raw == 1_500_000_000
    assert tx.slug == "BAAL_RA"
    assert tx.jetton == TON_JETTON_MASTERS["BAAL_RA"]
    assert tx.jetton_wallet.startswith("EQ")


async def test_send_tsar_rejects_non_positive():
    p = TonPayout()
    with pytest.raises(TonPayoutError):
        await p.send_tsar(amount=0, slug="BAAL_RA")
    with pytest.raises(TonPayoutError):
        await p.send_tsar(amount=-1, slug="BAAL_RA")


async def test_send_tsar_unknown_slug():
    p = TonPayout()
    with pytest.raises(TonPayoutError):
        await p.send_tsar(amount=1, slug="НЕТ_ТАКОГО")
