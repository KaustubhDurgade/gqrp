"""Live integration against data.binance.vision — the GATE 0 spike, codified.

Skipped by default (pyproject addopts filter out `network`). Run explicitly:
    pytest -m network
Proves the delisting-safe sourcing assumption end-to-end on real SRMUSDT data.
"""

from datetime import date

import pytest

from gqrp.data import binance_source, lifecycle

pytestmark = pytest.mark.network

_DELISTED = "SRMUSDT"  # Serum: listed 2020-08-11, halted 2022-11-28 (D11)


def test_delisted_pair_coverage_matches_lifecycle(tmp_path):
    months = binance_source.list_monthly_klines(_DELISTED)
    assert months, "no monthly klines listed for a known-delisted pair"
    assert months[0] == "2020-08"
    assert months[-1] == "2022-11"

    bars = binance_source.load_klines(_DELISTED, months=months, cache_dir=tmp_path)
    assert bars, "no bars loaded"
    # Coverage edges = exchange-native ground truth (checksum-verified in load).
    assert bars[0].date == date(2020, 8, 11)   # Binance listing
    assert bars[-1].date == date(2022, 11, 28)  # trading halt
    assert bars[-1].is_partial is True          # intraday halt signal

    lc = lifecycle.build_lifecycle(_DELISTED, bars, today=date.today())
    assert lc.listing_date == date(2020, 8, 11)
    assert lc.delisting_date == date(2022, 11, 28)
    assert lc.is_delisted is True
