#!/usr/bin/env python3
"""Build immutable, hash-locked monthly universe snapshots (spec §2 — BLOCKING).

The first real deliverable of Phase 1. Discovers (or takes) Binance spot symbols,
constructs survivorship-safe lifecycles, and writes one immutable universe file
per month over a date range.

Holdout safety (decision D6, interim): this driver never fetches or uses data on
or after HOLDOUT_START. Downloads are capped to pre-holdout months and the holdout
boundary is the lifecycle reference horizon, so a symbol still trading at the dev
edge is not mislabeled delisted. OS-level enforcement lands in
discipline/holdout_guard.py; this is the honest stand-in until then.

Examples:
    # smoke test: 3 discovered symbols, one snapshot
    python -m scripts.build_universe --discover --limit 3 \
        --start 2021-01 --end 2021-01 --min-volume 0

    # explicit symbols across a range
    python -m scripts.build_universe --symbols BTCUSDT,ETHUSDT,SRMUSDT \
        --start 2021-01 --end 2021-06
"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

from gqrp import config
from gqrp.data import binance_source, universe
from gqrp.data.lifecycle import build_lifecycle
from gqrp.data.types import OhlcvBar, SymbolLifecycle

_HOLDOUT_MONTH = config.HOLDOUT_START.strftime("%Y-%m")
# Lifecycle reference horizon: "still trading as of the dev edge?" (see module docstring).
_REFERENCE_HORIZON = config.HOLDOUT_START


def _month_starts(start: str, end: str) -> list[date]:
    """First-of-month dates from `start` to `end` inclusive (YYYY-MM strings)."""
    sy, sm = (int(x) for x in start.split("-"))
    ey, em = (int(x) for x in end.split("-"))
    out: list[date] = []
    y, m = sy, sm
    while (y, m) <= (ey, em):
        out.append(date(y, m, 1))
        m += 1
        if m > 12:
            y, m = y + 1, 1
    return out


def _pre_holdout_months(symbol: str) -> list[str]:
    return [m for m in binance_source.list_monthly_klines(symbol) if m < _HOLDOUT_MONTH]


def _load_symbol(
    symbol: str, cache_dir: Path
) -> tuple[SymbolLifecycle, list[OhlcvBar]] | None:
    """Load pre-holdout bars + build a lifecycle, or None if unsourceable (skip)."""
    months = _pre_holdout_months(symbol)
    if not months:
        return None
    bars = binance_source.load_klines(symbol, months=months, cache_dir=cache_dir)
    if not bars:
        return None
    lifecycle = build_lifecycle(symbol, bars, today=_REFERENCE_HORIZON)
    return lifecycle, bars


def _parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Build hash-locked universe snapshots.")
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("--symbols", help="comma-separated symbols, e.g. BTCUSDT,ETHUSDT")
    src.add_argument("--discover", action="store_true", help="discover all Binance spot symbols")
    p.add_argument("--limit", type=int, default=None, help="cap discovered symbols (smoke tests)")
    p.add_argument("--start", required=True, help="first snapshot month, YYYY-MM")
    p.add_argument("--end", required=True, help="last snapshot month, YYYY-MM")
    p.add_argument("--out-dir", type=Path, default=Path("data/universe"))
    p.add_argument("--cache-dir", type=Path, default=Path("data/raw"))
    p.add_argument("--lookback", type=int, default=universe.DEFAULT_LOOKBACK_DAYS)
    p.add_argument("--top-n", type=int, default=config.UNIVERSE_SIZE)
    p.add_argument("--min-volume", type=float, default=config.MIN_AVG_DAILY_QUOTE_VOLUME_USD)
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)

    if args.end >= _HOLDOUT_MONTH:
        print(
            f"REFUSED: --end {args.end} touches the holdout window "
            f"(>= {_HOLDOUT_MONTH}). Development must stay pre-holdout (decision D6/D10).",
            file=sys.stderr,
        )
        return 2

    if args.discover:
        symbols = binance_source.list_all_symbols()
        if args.limit:
            symbols = symbols[: args.limit]
    else:
        symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]

    print(f"Loading {len(symbols)} symbol(s) (pre-holdout history only)...", file=sys.stderr)
    lifecycles: list[SymbolLifecycle] = []
    bars_by_symbol: dict[str, list[OhlcvBar]] = {}
    skipped: list[str] = []
    for sym in symbols:
        loaded = _load_symbol(sym, args.cache_dir)
        if loaded is None:
            skipped.append(sym)
            continue
        lifecycle, bars = loaded
        lifecycles.append(lifecycle)
        bars_by_symbol[sym] = bars
    if skipped:
        print(f"  skipped {len(skipped)} unsourceable: {', '.join(skipped)}", file=sys.stderr)

    written = 0
    for snap_date in _month_starts(args.start, args.end):
        snap = universe.build_snapshot(
            snap_date, lifecycles, bars_by_symbol,
            lookback_days=args.lookback, top_n=args.top_n, min_volume=args.min_volume,
        )
        path = universe.write_snapshot(snap, args.out_dir)
        n_elig = len(snap.eligible_symbols)
        print(f"  {snap_date}  rows={len(snap.rows):3d}  eligible={n_elig:3d}  "
              f"hash={snap.content_hash[:12]}  -> {path}", file=sys.stderr)
        written += 1

    print(f"Done. {written} snapshot(s) written to {args.out_dir}.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
