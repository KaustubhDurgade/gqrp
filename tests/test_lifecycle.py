from datetime import date

import pytest

from gqrp.data.lifecycle import build_lifecycle, classify_symbol, infer_delisting_date
from gqrp.data.types import COMPLETE_DAY_SPAN_MS, OhlcvBar


def _bar(open_ms: int, span_ms: int = COMPLETE_DAY_SPAN_MS) -> OhlcvBar:
    return OhlcvBar(
        symbol="X", open_time_ms=open_ms, close_time_ms=open_ms + span_ms,
        open=1.0, high=1.0, low=1.0, close=1.0,
        volume=1.0, quote_volume=1.0, source="binance-native",
    )


def _day_ms(d: date) -> int:
    from datetime import datetime, timezone
    return int(datetime(d.year, d.month, d.day, tzinfo=timezone.utc).timestamp() * 1000)


# ── classify_symbol ─────────────────────────────────────────────────────────
@pytest.mark.parametrize(
    "symbol,expected",
    [
        ("SRMUSDT", ("SRM", "USDT", False, False)),
        ("BTCUSDT", ("BTC", "USDT", False, False)),
        ("ETHBTC", ("ETH", "BTC", False, False)),
        ("USDCUSDT", ("USDC", "USDT", True, False)),   # stablecoin base
        ("WBTCUSDT", ("WBTC", "USDT", False, True)),   # wrapped base
    ],
)
def test_classify_symbol(symbol, expected):
    assert classify_symbol(symbol) == expected


def test_classify_symbol_unparseable_raises():
    with pytest.raises(ValueError):
        classify_symbol("WEIRD")


# ── infer_delisting_date ────────────────────────────────────────────────────
def test_partial_final_bar_marks_delisting():
    bars = [_bar(_day_ms(date(2022, 11, 27))), _bar(_day_ms(date(2022, 11, 28)), 3 * 3600 * 1000 - 1)]
    assert infer_delisting_date(bars, today=date(2026, 7, 18)) == date(2022, 11, 28)


def test_stale_coverage_marks_delisting():
    bars = [_bar(_day_ms(date(2021, 1, 1)))]  # complete bar, but coverage stops in 2021
    assert infer_delisting_date(bars, today=date(2026, 7, 18)) == date(2021, 1, 1)


def test_fresh_complete_coverage_is_not_delisted():
    today = date(2026, 7, 18)
    bars = [_bar(_day_ms(date(2026, 7, 17)))]  # yesterday, complete
    assert infer_delisting_date(bars, today=today) is None


def test_empty_bars_no_delisting():
    assert infer_delisting_date([], today=date(2026, 7, 18)) is None


# ── build_lifecycle ─────────────────────────────────────────────────────────
def test_build_lifecycle_delisted_symbol():
    bars = [
        _bar(_day_ms(date(2020, 8, 11))),
        _bar(_day_ms(date(2022, 11, 28)), 3 * 3600 * 1000 - 1),
    ]
    lc = build_lifecycle("SRMUSDT", bars, today=date(2026, 7, 18))
    assert lc.listing_date == date(2020, 8, 11)
    assert lc.delisting_date == date(2022, 11, 28)
    assert lc.base_asset == "SRM" and lc.quote_asset == "USDT"
    assert lc.is_delisted is True
    assert lc.source == "binance-native" and lc.verified is False


def test_build_lifecycle_empty_raises():
    with pytest.raises(ValueError, match="exclude"):
        build_lifecycle("SRMUSDT", [], today=date(2026, 7, 18))


def test_build_lifecycle_sorts_unordered_bars():
    bars = [_bar(_day_ms(date(2020, 8, 13))), _bar(_day_ms(date(2020, 8, 11)))]
    lc = build_lifecycle("BTCUSDT", bars, today=date(2020, 8, 14))
    assert lc.listing_date == date(2020, 8, 11)
