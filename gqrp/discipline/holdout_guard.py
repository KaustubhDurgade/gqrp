"""Holdout access guard (spec §10, decision D6).

"One evaluation ever" is meaningless if development code can read holdout data.
The real enforcement is OS filesystem perms (the holdout partition is owned by a
different user / mode 000, outside the dev process's readable path). This module
is the loud in-process complement: any date or path that falls inside the holdout
window raises `HoldoutAccessError` immediately, so a mistake fails at the call
site instead of silently contaminating a result.

Nothing here can *grant* access — it only refuses. Forward-test tooling operates
strictly after `HOLDOUT.end` and never calls the backtest path.
"""

from __future__ import annotations

import os
from datetime import date
from pathlib import Path

from .windows import HOLDOUT


class HoldoutAccessError(RuntimeError):
    """Raised when development code touches the holdout window (D6)."""


def assert_day_allowed(day: date) -> None:
    """Refuse a single date that lands in the holdout window."""
    if HOLDOUT.contains(day):
        raise HoldoutAccessError(
            f"{day.isoformat()} is inside the holdout window "
            f"[{HOLDOUT.start.isoformat()} .. {HOLDOUT.end.isoformat()}] — "
            "no development access (decision D6)."
        )


def assert_range_allowed(start: date, end: date) -> None:
    """Refuse a date range that overlaps the holdout window at all.

    The primary dev-time tripwire: every backtest/data request carries a range,
    and any intersection with holdout is a hard error — not a clamp, not a warn."""
    if start > end:
        raise ValueError(f"invalid range: start {start} after end {end}")
    if HOLDOUT.overlaps(start, end):
        raise HoldoutAccessError(
            f"range [{start.isoformat()} .. {end.isoformat()}] overlaps the holdout "
            f"window [{HOLDOUT.start.isoformat()} .. {HOLDOUT.end.isoformat()}] — "
            "no development access (decision D6)."
        )


def assert_path_outside_holdout(path: str | Path, holdout_root: str | Path) -> None:
    """Refuse to touch anything under the OS-locked holdout partition.

    Belt-and-suspenders against the fs perms: even if the partition were somehow
    readable, resolving a path into it here still raises before any open."""
    resolved = Path(path).resolve()
    root = Path(holdout_root).resolve()
    if resolved == root or root in resolved.parents:
        raise HoldoutAccessError(
            f"{resolved} is under the holdout partition {root} — "
            "no development access (decision D6)."
        )


def is_partition_os_locked(holdout_root: str | Path) -> bool:
    """True if the holdout partition is not readable by this (dev) process — the
    real D6 enforcement. A missing partition counts as locked (nothing to read)."""
    root = Path(holdout_root)
    if not root.exists():
        return True
    return not os.access(root, os.R_OK)
