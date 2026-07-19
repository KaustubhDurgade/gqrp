"""Read-only registry client (spec §6, decision D4).

The connection is opened `mode=ro`, so SQLite rejects any write at the driver
level — this client has no way to mutate history. It is the *same* interface a
Phase-2 agent would get: there is never a write path to add (architecture seam
1). Cumulative weighted N is computed live from rows, never read from a stored
counter.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from .types import Trial, TrialResult


class RegistryReader:
    """Read-only view over the registry. Cannot write, by construction."""

    def __init__(self, db_path: str | Path) -> None:
        self._path = Path(db_path)
        # mode=ro → the OS/driver rejects every write; nfailover=immutability.
        self._conn = sqlite3.connect(f"file:{self._path}?mode=ro", uri=True)
        self._conn.row_factory = sqlite3.Row

    def __enter__(self) -> RegistryReader:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def close(self) -> None:
        self._conn.close()

    # ── the statistical bar (spec §6, §8) ───────────────────────────────────
    def cumulative_weighted_n(self) -> float:
        """Σ weight over research trials — the deflated-Sharpe multiple-testing
        count. Computed live; `pipeline-validation` is excluded (decision D7)."""
        row = self._conn.execute(
            "SELECT COALESCE(SUM(weight), 0.0) AS n FROM trial WHERE run_type = 'research'"
        ).fetchone()
        return float(row["n"])

    def family_trial_count(self, family_id: str) -> int:
        """Number of trials logged under a family (research + pipeline-validation)."""
        row = self._conn.execute(
            "SELECT COUNT(*) AS c FROM trial WHERE family_id = ?", (family_id,)
        ).fetchone()
        return int(row["c"])

    # ── record access ───────────────────────────────────────────────────────
    def get_trial(self, trial_id: str) -> Trial | None:
        row = self._conn.execute(
            "SELECT * FROM trial WHERE trial_id = ?", (trial_id,)
        ).fetchone()
        return _row_to_trial(row) if row else None

    def get_result(self, trial_id: str) -> TrialResult | None:
        row = self._conn.execute(
            "SELECT * FROM trial_result WHERE trial_id = ?", (trial_id,)
        ).fetchone()
        return _row_to_result(row) if row else None

    def list_trials(self) -> tuple[Trial, ...]:
        rows = self._conn.execute("SELECT * FROM trial ORDER BY created_at").fetchall()
        return tuple(_row_to_trial(r) for r in rows)


def _row_to_trial(row: sqlite3.Row) -> Trial:
    return Trial(
        trial_id=row["trial_id"],
        family_id=row["family_id"],
        parent_trial_id=row["parent_trial_id"],
        level=row["level"],
        weight=float(row["weight"]),
        run_type=row["run_type"],
        config_json=row["config_json"],
        config_hash=row["config_hash"],
        data_window=row["data_window"],
        created_at=row["created_at"],
        status=row["status"],
    )


def _row_to_result(row: sqlite3.Row) -> TrialResult:
    return TrialResult(
        trial_id=row["trial_id"],
        metrics_json=row["metrics_json"],
        gate_verdicts_json=row["gate_verdicts_json"],
        created_at=row["created_at"],
    )
