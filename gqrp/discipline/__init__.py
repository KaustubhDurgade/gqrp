"""Validation discipline (spec §10, decisions D6/D10).

The `Window` object gates all data access (architecture seam 4): backtests never
open files directly, they receive a `Window`. The holdout window is fixed and
hash-locked (D10); `holdout_guard` is the dev-time tripwire that refuses any
access falling inside it (D6). The real enforcement is OS filesystem perms — this
module is the loud, in-process complement to that.
"""
