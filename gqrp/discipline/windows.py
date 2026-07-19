"""Dev / validation / holdout windows (spec §10, decision D10).

The three windows are derived from `config` and **hash-locked** at project start
(D10, locked 2026-07-18): `LOCKED_WINDOWS_HASH` pins their exact boundaries, and
`verify_windows_locked()` trips if any boundary is edited afterward. Extending the
holdout end is a schedule signal, not a config tweak — the lock makes a silent
edit detectable.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date

from .. import config


@dataclass(frozen=True, slots=True)
class Window:
    """A named, closed date interval [start, end]. The object every backtest
    consumes instead of touching files directly (architecture seam 4)."""

    name: str
    start: date
    end: date

    def contains(self, day: date) -> bool:
        return self.start <= day <= self.end

    def overlaps(self, start: date, end: date) -> bool:
        """True if [start, end] intersects this window at all."""
        return start <= self.end and end >= self.start


DEVELOPMENT = Window("development", config.DEV_START, config.DEV_END)
VALIDATION = Window("validation", config.VALIDATION_START, config.VALIDATION_END)
HOLDOUT = Window("holdout", config.HOLDOUT_START, config.HOLDOUT_END)

# Order matters for the hash; do not reorder.
ALL_WINDOWS: tuple[Window, ...] = (DEVELOPMENT, VALIDATION, HOLDOUT)

_BY_NAME = {w.name: w for w in ALL_WINDOWS}


def windows_hash() -> str:
    """sha256 of the exact window boundaries — the D10 lock fingerprint."""
    payload = [
        {"name": w.name, "start": w.start.isoformat(), "end": w.end.isoformat()}
        for w in ALL_WINDOWS
    ]
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode()).hexdigest()


# Locked 2026-07-18 (decision D10). If this constant and windows_hash() diverge,
# a window boundary was changed after the lock — that is the tripwire.
LOCKED_WINDOWS_HASH = "69f421d6b4fb077311f3b4ad693e6a80bfc4b8828a1b1f7933ba412b30c3f354"


def verify_windows_locked() -> None:
    """Raise if the window definitions no longer match the D10 lock."""
    actual = windows_hash()
    if actual != LOCKED_WINDOWS_HASH:
        raise ValueError(
            "window definitions changed since the D10 lock (2026-07-18): "
            f"locked {LOCKED_WINDOWS_HASH}, now {actual}. "
            "Extending the holdout is a schedule signal, not a config edit."
        )


def window_for(name: str) -> Window:
    try:
        return _BY_NAME[name]
    except KeyError as exc:
        raise ValueError(f"unknown window: {name!r}") from exc
