from datetime import date

from scripts.build_universe import _HOLDOUT_MONTH, _month_starts, main


def test_month_starts_inclusive_range():
    assert _month_starts("2021-11", "2022-02") == [
        date(2021, 11, 1), date(2021, 12, 1), date(2022, 1, 1), date(2022, 2, 1),
    ]


def test_month_starts_single():
    assert _month_starts("2021-01", "2021-01") == [date(2021, 1, 1)]


def test_holdout_month_is_2025_01():
    assert _HOLDOUT_MONTH == "2025-01"


def test_main_refuses_holdout_end(capsys):
    rc = main(["--symbols", "BTCUSDT", "--start", "2024-12", "--end", "2025-01"])
    assert rc == 2
    assert "holdout" in capsys.readouterr().err.lower()
