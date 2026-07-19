"""Delisting-aware OHLCV loading (spec §2, §7 audit item).

The one guarantee this module adds over the raw adapter: **no bar is ever served
after a symbol's `delisting_date`**, and bars up to that date are retained (the
loss is realized, not survivorship-erased). Loading is always scoped by a
`SymbolLifecycle` so point-in-time correctness is structural, not incidental.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from . import binance_source
from .types import OhlcvBar, SymbolLifecycle


def filter_to_lifecycle(bars: list[OhlcvBar], lifecycle: SymbolLifecycle) -> list[OhlcvBar]:
    """Drop any bar outside the symbol's tradable window (defense in depth).

    The Binance dump already stops at delisting, but a later/second source could
    over-report; this keeps the invariant enforced at the domain boundary.
    """
    return [b for b in bars if lifecycle.was_tradable_on(b.date)]


def _in_range(day: date, start: date | None, end: date | None) -> bool:
    if start is not None and day < start:
        return False
    if end is not None and day > end:
        return False
    return True


def load_bars(
    lifecycle: SymbolLifecycle,
    *,
    start: date | None = None,
    end: date | None = None,
    interval: str = "1d",
    cache_dir: Path | None = None,
) -> list[OhlcvBar]:
    """Load a symbol's bars, clamped to its lifecycle and an optional date range.

    Never returns bars after `delisting_date` — a delisted asset contributes its
    real history (including the terminal loss) and nothing beyond.
    """
    raw = binance_source.load_klines(
        lifecycle.symbol, interval=interval, cache_dir=cache_dir
    )
    scoped = filter_to_lifecycle(raw, lifecycle)
    if start is None and end is None:
        return scoped
    return [b for b in scoped if _in_range(b.date, start, end)]


def average_daily_quote_volume(
    bars: list[OhlcvBar], *, as_of: date, lookback_days: int
) -> float | None:
    """Mean daily quote (USD) volume over the `lookback_days` ending at `as_of`.

    Point-in-time by construction: only bars with date <= `as_of` are considered.
    Returns None if there is no data in the window (asset not yet tradable / gap).
    """
    from datetime import timedelta

    window_start = as_of - timedelta(days=lookback_days)
    window = [b for b in bars if window_start < b.date <= as_of]
    if not window:
        return None
    return sum(b.quote_volume for b in window) / len(window)
