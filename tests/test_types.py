from datetime import date

from gqrp.data.types import COMPLETE_DAY_SPAN_MS, OhlcvBar, SymbolLifecycle, ms_to_date


def _bar(open_ms: int, span_ms: int) -> OhlcvBar:
    return OhlcvBar(
        symbol="SRMUSDT",
        open_time_ms=open_ms,
        close_time_ms=open_ms + span_ms,
        open=1.0, high=2.0, low=0.5, close=1.5,
        volume=100.0, quote_volume=150.0, source="binance-native",
    )


def test_ms_to_date_is_utc():
    # 1597104000000 = 2020-08-11 00:00:00 UTC (SRM/USDT Binance listing)
    assert ms_to_date(1597104000000) == date(2020, 8, 11)


def test_bar_date_derives_from_open_time():
    assert _bar(1597104000000, COMPLETE_DAY_SPAN_MS).date == date(2020, 8, 11)


def test_complete_daily_bar_is_not_partial():
    assert _bar(1597104000000, COMPLETE_DAY_SPAN_MS).is_partial is False


def test_truncated_final_bar_is_partial():
    # SRMUSDT last bar: open 00:00, close 02:59:59.999 = intraday halt (D11)
    three_hours = 3 * 3600 * 1000 - 1
    assert _bar(1669593600000, three_hours).is_partial is True


def test_lifecycle_tradable_window():
    lc = SymbolLifecycle(
        symbol="SRMUSDT", venue="binance",
        listing_date=date(2020, 8, 11), delisting_date=date(2022, 11, 28),
        base_asset="SRM", quote_asset="USDT",
        is_stablecoin=False, is_wrapped=False,
        source="binance-native", verified=False,
    )
    assert lc.is_delisted is True
    assert lc.was_tradable_on(date(2020, 8, 10)) is False   # before listing
    assert lc.was_tradable_on(date(2020, 8, 11)) is True    # listing day
    assert lc.was_tradable_on(date(2021, 6, 1)) is True     # mid-life
    assert lc.was_tradable_on(date(2022, 11, 28)) is True   # halt day, still counts
    assert lc.was_tradable_on(date(2022, 11, 29)) is False  # after delisting


def test_still_listed_symbol_tradable_open_ended():
    lc = SymbolLifecycle(
        symbol="BTCUSDT", venue="binance",
        listing_date=date(2017, 8, 17), delisting_date=None,
        base_asset="BTC", quote_asset="USDT",
        is_stablecoin=False, is_wrapped=False,
        source="binance-native", verified=False,
    )
    assert lc.is_delisted is False
    assert lc.was_tradable_on(date(2099, 1, 1)) is True
