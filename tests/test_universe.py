from datetime import date, datetime, timedelta, timezone

import pytest

from gqrp.data import universe
from gqrp.data.types import COMPLETE_DAY_SPAN_MS, OhlcvBar, SymbolLifecycle


def _day_ms(d: date) -> int:
    return int(datetime(d.year, d.month, d.day, tzinfo=timezone.utc).timestamp() * 1000)


def _bars(symbol: str, end: date, days: int, quote_volume: float) -> list[OhlcvBar]:
    out = []
    for i in range(days):
        d = end - timedelta(days=i)
        o = _day_ms(d)
        out.append(OhlcvBar(
            symbol=symbol, open_time_ms=o, close_time_ms=o + COMPLETE_DAY_SPAN_MS,
            open=1.0, high=1.0, low=1.0, close=1.0,
            volume=1.0, quote_volume=quote_volume, source="binance-native",
        ))
    return out


def _lc(symbol, base, quote="USDT", delisting=None, is_stable=False, is_wrapped=False):
    return SymbolLifecycle(
        symbol=symbol, venue="binance",
        listing_date=date(2019, 1, 1), delisting_date=delisting,
        base_asset=base, quote_asset=quote,
        is_stablecoin=is_stable, is_wrapped=is_wrapped,
        source="binance-native", verified=False,
    )


AS_OF = date(2021, 6, 1)


def _build(lifecycles, bars, **kw):
    return universe.build_snapshot(AS_OF, lifecycles, bars, **kw)


def test_ranks_by_volume_desc():
    lcs = [_lc("AAAUSDT", "AAA"), _lc("BBBUSDT", "BBB"), _lc("CCCUSDT", "CCC")]
    bars = {
        "AAAUSDT": _bars("AAAUSDT", AS_OF, 30, 5_000_000),
        "BBBUSDT": _bars("BBBUSDT", AS_OF, 30, 9_000_000),
        "CCCUSDT": _bars("CCCUSDT", AS_OF, 30, 1_000_000),
    }
    snap = _build(lcs, bars, min_volume=0)
    assert [r.symbol for r in snap.rows] == ["BBBUSDT", "AAAUSDT", "CCCUSDT"]
    assert [r.rank for r in snap.rows] == [1, 2, 3]


def test_liquidity_floor_sets_eligible():
    lcs = [_lc("AAAUSDT", "AAA"), _lc("BBBUSDT", "BBB")]
    bars = {
        "AAAUSDT": _bars("AAAUSDT", AS_OF, 30, 2_000_000),   # above floor
        "BBBUSDT": _bars("BBBUSDT", AS_OF, 30, 500_000),     # below floor
    }
    snap = _build(lcs, bars, min_volume=1_000_000)
    elig = {r.symbol: r.eligible for r in snap.rows}
    assert elig == {"AAAUSDT": True, "BBBUSDT": False}
    assert snap.eligible_symbols == ("AAAUSDT",)


def test_excludes_stablecoins_wrapped_and_wrong_quote():
    lcs = [
        _lc("AAAUSDT", "AAA"),
        _lc("USDCUSDT", "USDC", is_stable=True),
        _lc("WBTCUSDT", "WBTC", is_wrapped=True),
        _lc("XXXBTC", "XXX", quote="BTC"),
    ]
    bars = {s.symbol: _bars(s.symbol, AS_OF, 30, 5_000_000) for s in lcs}
    snap = _build(lcs, bars, min_volume=0)
    assert [r.symbol for r in snap.rows] == ["AAAUSDT"]


def test_delisted_symbol_included_before_delisting_excluded_after():
    lcs = [_lc("DEADUSDT", "DEAD", delisting=date(2021, 5, 15))]
    bars = {"DEADUSDT": _bars("DEADUSDT", date(2021, 5, 15), 30, 5_000_000)}
    # as_of before delisting → present
    s1 = universe.build_snapshot(date(2021, 5, 10), lcs, bars, min_volume=0)
    assert [r.symbol for r in s1.rows] == ["DEADUSDT"]
    # as_of after delisting → gone
    s2 = universe.build_snapshot(date(2021, 6, 1), lcs, bars, min_volume=0)
    assert s2.rows == ()


def test_symbol_with_no_data_excluded():
    lcs = [_lc("AAAUSDT", "AAA"), _lc("NODATAUSDT", "NODATA")]
    bars = {"AAAUSDT": _bars("AAAUSDT", AS_OF, 30, 5_000_000)}  # NODATA missing
    snap = _build(lcs, bars, min_volume=0)
    assert [r.symbol for r in snap.rows] == ["AAAUSDT"]


def test_top_n_cut():
    lcs = [_lc(f"S{i}USDT", f"S{i}") for i in range(5)]
    bars = {f"S{i}USDT": _bars(f"S{i}USDT", AS_OF, 30, (i + 1) * 1_000_000) for i in range(5)}
    snap = _build(lcs, bars, top_n=2, min_volume=0)
    assert len(snap.rows) == 2
    assert [r.symbol for r in snap.rows] == ["S4USDT", "S3USDT"]  # top 2 by volume


def test_content_hash_deterministic_and_order_independent():
    lcs = [_lc("AAAUSDT", "AAA"), _lc("BBBUSDT", "BBB")]
    bars = {
        "AAAUSDT": _bars("AAAUSDT", AS_OF, 30, 5_000_000),
        "BBBUSDT": _bars("BBBUSDT", AS_OF, 30, 9_000_000),
    }
    h1 = _build(lcs, bars, min_volume=0).content_hash
    h2 = _build(list(reversed(lcs)), bars, min_volume=0).content_hash
    assert h1 == h2


def test_config_change_changes_config_hash():
    lcs = [_lc("AAAUSDT", "AAA")]
    bars = {"AAAUSDT": _bars("AAAUSDT", AS_OF, 30, 5_000_000)}
    a = _build(lcs, bars, min_volume=1_000_000).config_hash
    b = _build(lcs, bars, min_volume=2_000_000).config_hash
    assert a != b


# ── immutability / hash-lock on disk ────────────────────────────────────────
def test_write_is_readonly_and_roundtrips(tmp_path):
    lcs = [_lc("AAAUSDT", "AAA")]
    bars = {"AAAUSDT": _bars("AAAUSDT", AS_OF, 30, 5_000_000)}
    snap = _build(lcs, bars, min_volume=0)
    path = universe.write_snapshot(snap, tmp_path)
    import os
    import stat
    mode = stat.S_IMODE(os.stat(path).st_mode)
    assert mode == 0o444, f"snapshot must be read-only, got {oct(mode)}"
    loaded = universe.load_snapshot(path)
    assert loaded.content_hash == snap.content_hash
    assert loaded.eligible_symbols == snap.eligible_symbols


def test_write_refuses_overwrite(tmp_path):
    snap = _build([_lc("AAAUSDT", "AAA")],
                  {"AAAUSDT": _bars("AAAUSDT", AS_OF, 30, 5_000_000)}, min_volume=0)
    universe.write_snapshot(snap, tmp_path)
    with pytest.raises(FileExistsError):
        universe.write_snapshot(snap, tmp_path)


def test_load_detects_tampering(tmp_path):
    snap = _build([_lc("AAAUSDT", "AAA")],
                  {"AAAUSDT": _bars("AAAUSDT", AS_OF, 30, 5_000_000)}, min_volume=0)
    path = universe.write_snapshot(snap, tmp_path)
    import os
    os.chmod(path, 0o644)
    doc = path.read_text().replace('"rank": 1', '"rank": 2')
    path.write_text(doc)
    with pytest.raises(ValueError, match="hash mismatch"):
        universe.load_snapshot(path)
