from datetime import date, datetime, timezone

from gqrp.data.ohlcv import average_daily_quote_volume, filter_to_lifecycle
from gqrp.data.types import COMPLETE_DAY_SPAN_MS, OhlcvBar, SymbolLifecycle


def _day_ms(d: date) -> int:
    return int(datetime(d.year, d.month, d.day, tzinfo=timezone.utc).timestamp() * 1000)


def _bar(d: date, quote_volume: float = 1.0) -> OhlcvBar:
    o = _day_ms(d)
    return OhlcvBar(
        symbol="SRMUSDT", open_time_ms=o, close_time_ms=o + COMPLETE_DAY_SPAN_MS,
        open=1.0, high=1.0, low=1.0, close=1.0,
        volume=1.0, quote_volume=quote_volume, source="binance-native",
    )


def _lc(delisting: date | None) -> SymbolLifecycle:
    return SymbolLifecycle(
        symbol="SRMUSDT", venue="binance",
        listing_date=date(2020, 8, 11), delisting_date=delisting,
        base_asset="SRM", quote_asset="USDT",
        is_stablecoin=False, is_wrapped=False,
        source="binance-native", verified=False,
    )


def test_filter_drops_post_delisting_bars():
    bars = [_bar(date(2022, 11, 28)), _bar(date(2022, 11, 29)), _bar(date(2023, 1, 1))]
    kept = filter_to_lifecycle(bars, _lc(date(2022, 11, 28)))
    assert [b.date for b in kept] == [date(2022, 11, 28)]  # halt day kept, after dropped


def test_filter_drops_pre_listing_bars():
    bars = [_bar(date(2020, 8, 10)), _bar(date(2020, 8, 11))]
    kept = filter_to_lifecycle(bars, _lc(None))
    assert [b.date for b in kept] == [date(2020, 8, 11)]


def test_filter_keeps_all_for_live_symbol():
    bars = [_bar(date(2021, 1, 1)), _bar(date(2024, 6, 1))]
    assert len(filter_to_lifecycle(bars, _lc(None))) == 2


def test_avg_quote_volume_is_point_in_time():
    bars = [_bar(date(2021, 1, 1), 100.0), _bar(date(2021, 1, 2), 300.0),
            _bar(date(2021, 1, 10), 999.0)]  # after as_of, must be excluded
    avg = average_daily_quote_volume(bars, as_of=date(2021, 1, 5), lookback_days=30)
    assert avg == 200.0


def test_avg_quote_volume_none_when_empty_window():
    bars = [_bar(date(2021, 1, 1), 100.0)]
    assert average_daily_quote_volume(bars, as_of=date(2020, 1, 1), lookback_days=30) is None
