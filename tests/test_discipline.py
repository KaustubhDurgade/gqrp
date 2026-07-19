"""Discipline-layer tests — the holdout lock (D10) and access guard (D6).

CLAUDE.md verification bar for the holdout: it's enforced structurally, not by
honor system. `test_range_into_holdout_is_rejected` and
`test_locked_hash_trips_on_boundary_change` are that proof.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from gqrp import config
from gqrp.discipline import holdout_guard, windows
from gqrp.discipline.holdout_guard import HoldoutAccessError
from gqrp.discipline.windows import HOLDOUT, Window


# ── Window object ───────────────────────────────────────────────────────────
def test_window_contains_boundaries_inclusive():
    w = Window("x", date(2020, 1, 1), date(2020, 12, 31))
    assert w.contains(date(2020, 1, 1))
    assert w.contains(date(2020, 12, 31))
    assert not w.contains(date(2019, 12, 31))
    assert not w.contains(date(2021, 1, 1))


def test_window_overlaps():
    w = Window("x", date(2020, 1, 1), date(2020, 12, 31))
    assert w.overlaps(date(2019, 6, 1), date(2020, 6, 1))  # straddles start
    assert w.overlaps(date(2020, 6, 1), date(2021, 6, 1))  # straddles end
    assert w.overlaps(date(2020, 3, 1), date(2020, 4, 1))  # inside
    assert not w.overlaps(date(2019, 1, 1), date(2019, 12, 31))  # fully before
    assert not w.overlaps(date(2021, 1, 1), date(2021, 12, 31))  # fully after


def test_window_for_unknown_name():
    with pytest.raises(ValueError, match="unknown window"):
        windows.window_for("bogus")


# ── D10 hash-lock ───────────────────────────────────────────────────────────
def test_windows_match_locked_hash():
    windows.verify_windows_locked()  # must not raise on the committed boundaries
    assert windows.windows_hash() == windows.LOCKED_WINDOWS_HASH


def test_locked_hash_trips_on_boundary_change(monkeypatch):
    """Editing any window boundary must break the lock (the D10 tripwire)."""
    tampered = Window("holdout", HOLDOUT.start, date(2027, 12, 31))  # extended end
    monkeypatch.setattr(
        windows, "ALL_WINDOWS", (windows.DEVELOPMENT, windows.VALIDATION, tampered)
    )
    assert windows.windows_hash() != windows.LOCKED_WINDOWS_HASH
    with pytest.raises(ValueError, match="changed since the D10 lock"):
        windows.verify_windows_locked()


# ── D6 access guard: dates ──────────────────────────────────────────────────
def test_dev_range_is_allowed():
    holdout_guard.assert_range_allowed(config.DEV_START, config.DEV_END)  # no raise


def test_validation_range_is_allowed():
    holdout_guard.assert_range_allowed(config.VALIDATION_START, config.VALIDATION_END)


def test_range_into_holdout_is_rejected():
    """A backtest range that crosses into holdout fails at the call site (D6)."""
    with pytest.raises(HoldoutAccessError, match="holdout"):
        holdout_guard.assert_range_allowed(date(2024, 6, 1), date(2025, 6, 1))


def test_range_fully_in_holdout_is_rejected():
    with pytest.raises(HoldoutAccessError):
        holdout_guard.assert_range_allowed(config.HOLDOUT_START, config.HOLDOUT_END)


def test_holdout_day_is_rejected():
    with pytest.raises(HoldoutAccessError):
        holdout_guard.assert_day_allowed(date(2025, 6, 15))


def test_dev_day_is_allowed():
    holdout_guard.assert_day_allowed(date(2020, 6, 15))


def test_inverted_range_is_a_value_error():
    with pytest.raises(ValueError, match="start .* after end"):
        holdout_guard.assert_range_allowed(date(2021, 1, 1), date(2020, 1, 1))


# ── D6 access guard: paths ──────────────────────────────────────────────────
def test_path_inside_holdout_partition_is_rejected(tmp_path: Path):
    root = tmp_path / "holdout"
    root.mkdir()
    target = root / "2025" / "bars.parquet"
    with pytest.raises(HoldoutAccessError, match="holdout partition"):
        holdout_guard.assert_path_outside_holdout(target, root)


def test_path_outside_holdout_partition_is_allowed(tmp_path: Path):
    root = tmp_path / "holdout"
    root.mkdir()
    dev = tmp_path / "development" / "bars.parquet"
    holdout_guard.assert_path_outside_holdout(dev, root)  # no raise


def test_missing_partition_counts_as_locked(tmp_path: Path):
    assert holdout_guard.is_partition_os_locked(tmp_path / "does-not-exist")
