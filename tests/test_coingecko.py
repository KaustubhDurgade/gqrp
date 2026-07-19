from datetime import date

import pytest

from gqrp.data import coingecko
from gqrp.data.coingecko import AggregatorError, list_coin_symbols
from gqrp.data.lifecycle import cross_check_existence
from gqrp.data.types import SymbolLifecycle


def _lc(base: str, verified: bool = False) -> SymbolLifecycle:
    return SymbolLifecycle(
        symbol=f"{base}USDT", venue="binance",
        listing_date=date(2020, 8, 11), delisting_date=None,
        base_asset=base, quote_asset="USDT",
        is_stablecoin=False, is_wrapped=False,
        source="binance-native", verified=verified,
    )


def test_list_coin_symbols_lowercases_and_dedupes(monkeypatch):
    payload = [
        {"id": "serum", "symbol": "SRM", "name": "Serum"},
        {"id": "bitcoin", "symbol": "btc", "name": "Bitcoin"},
        {"id": "other-srm", "symbol": "srm", "name": "Other"},  # ticker collision
        {"id": "no-symbol"},  # skipped
    ]
    monkeypatch.setattr(coingecko, "_http_get_json", lambda url: payload)
    assert list_coin_symbols() == {"srm", "btc"}


def test_list_coin_symbols_raises_on_bad_payload(monkeypatch):
    monkeypatch.setattr(coingecko, "_http_get_json", lambda url: {"not": "a list"})
    with pytest.raises(AggregatorError):
        list_coin_symbols()


def test_cross_check_marks_verified_when_found():
    lc = cross_check_existence(_lc("SRM"), {"srm", "btc"})
    assert lc.verified is True
    assert lc.source == "binance-native"  # dates untouched — existence check only


def test_cross_check_unverified_when_absent():
    lc = cross_check_existence(_lc("GHOSTCOIN"), {"srm", "btc"})
    assert lc.verified is False  # flag for review, not a drop


def test_cross_check_is_immutable():
    original = _lc("SRM", verified=False)
    result = cross_check_existence(original, {"srm"})
    assert original.verified is False  # unchanged
    assert result is not original


def test_cross_check_case_insensitive():
    assert cross_check_existence(_lc("Btc"), {"btc"}).verified is True
