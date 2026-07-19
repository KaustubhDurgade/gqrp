"""Append-only registry writer (spec §6, decision D4).

`RegistryWriter` is the *only* code path that writes the registry. It exposes
append operations and nothing else — there is deliberately no update or delete
method anywhere in this module, so a trial's `run_type` can never be retagged
(decision D7) and no result can ever be revised. DB-level triggers reject
UPDATE/DELETE even against this connection, and the read-only client
(`client.py`) can never write at all.

Deployment intent (D4): run this as its own OS process owning the DB file so the
development process holds no writable handle. That process-isolation seam is not
yet wired — the immutability guarantees above hold regardless of process
topology. See docs/decisions.md.
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .types import (
    DataWindow,
    Level,
    NegativeKnowledge,
    ResearchMemo,
    RunType,
    Trial,
    TrialResult,
    weight_for,
)

_SCHEMA_PATH = Path(__file__).with_name("schema.sql")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_trial_id() -> str:
    return uuid.uuid4().hex


class RegistryWriter:
    """The sole writer. Append-only API; no mutate path exists by construction."""

    def __init__(self, db_path: str | Path) -> None:
        self._path = Path(db_path)
        self._closed = False
        self._conn = sqlite3.connect(self._path)
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._conn.executescript(_SCHEMA_PATH.read_text())
        self._conn.commit()

    # ── context management ──────────────────────────────────────────────────
    def __enter__(self) -> RegistryWriter:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def close(self) -> None:
        """Idempotent. Folds the WAL back into the main DB so a read-only client
        can open it without writable -wal/-shm sidecar files."""
        if self._closed:
            return
        self._closed = True
        try:
            self._conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        except sqlite3.OperationalError:
            pass  # a concurrent reader holds the WAL; harmless — wal stays readable
        self._conn.close()

    # ── trial (config, BEFORE results) ──────────────────────────────────────
    def append_trial(
        self,
        *,
        family_id: str,
        level: Level,
        run_type: RunType,
        config: dict[str, Any],
        config_hash: str,
        data_window: DataWindow,
        parent_trial_id: str | None = None,
        status: str = "created",
    ) -> Trial:
        """Register a trial's config. Weight is derived from level, never passed."""
        weight = weight_for(level)  # validates level; fixes the §6 weight table
        trial = Trial(
            trial_id=_new_trial_id(),
            family_id=family_id,
            parent_trial_id=parent_trial_id,
            level=level,
            weight=weight,
            run_type=run_type,
            config_json=json.dumps(config, sort_keys=True, separators=(",", ":")),
            config_hash=config_hash,
            data_window=data_window,
            created_at=_now_iso(),
            status=status,
        )
        self._conn.execute(
            "INSERT INTO trial (trial_id, family_id, parent_trial_id, level, weight, "
            "run_type, config_json, config_hash, data_window, created_at, status) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                trial.trial_id,
                trial.family_id,
                trial.parent_trial_id,
                trial.level,
                trial.weight,
                trial.run_type,
                trial.config_json,
                trial.config_hash,
                trial.data_window,
                trial.created_at,
                trial.status,
            ),
        )
        self._conn.commit()
        return trial

    # ── trial_result (AFTER trial) ──────────────────────────────────────────
    def append_result(
        self,
        *,
        trial_id: str,
        metrics: dict[str, Any],
        gate_verdicts: dict[str, Any],
    ) -> TrialResult:
        """Record a trial's results. Requires the trial to already exist (config
        before results, spec §6) and refuses a second result for the same trial."""
        result = TrialResult(
            trial_id=trial_id,
            metrics_json=json.dumps(metrics, sort_keys=True, separators=(",", ":")),
            gate_verdicts_json=json.dumps(gate_verdicts, sort_keys=True, separators=(",", ":")),
            created_at=_now_iso(),
        )
        try:
            self._conn.execute(
                "INSERT INTO trial_result (trial_id, metrics_json, gate_verdicts_json, "
                "created_at) VALUES (?, ?, ?, ?)",
                (
                    result.trial_id,
                    result.metrics_json,
                    result.gate_verdicts_json,
                    result.created_at,
                ),
            )
        except sqlite3.IntegrityError as exc:
            # FK failure → trial doesn't exist; PK failure → result already logged.
            raise ValueError(
                f"cannot append result for trial {trial_id!r}: "
                "trial missing (config must precede results) or result already recorded"
            ) from exc
        self._conn.commit()
        return result

    # ── research_memo (hash-locked; spec §4) ────────────────────────────────
    def append_memo(
        self, *, family_id: str, memo_hash: str, memo: dict[str, Any]
    ) -> ResearchMemo:
        """Lock a research memo before implementation (spec §4)."""
        record = ResearchMemo(
            memo_hash=memo_hash,
            family_id=family_id,
            memo_json=json.dumps(memo, sort_keys=True, separators=(",", ":")),
            committed_at=_now_iso(),
        )
        try:
            self._conn.execute(
                "INSERT INTO research_memo (memo_hash, family_id, memo_json, committed_at) "
                "VALUES (?, ?, ?, ?)",
                (record.memo_hash, record.family_id, record.memo_json, record.committed_at),
            )
        except sqlite3.IntegrityError as exc:
            raise ValueError(f"memo {memo_hash!r} already committed (immutable)") from exc
        self._conn.commit()
        return record

    # ── negative_knowledge (spec §11) ───────────────────────────────────────
    def append_negative_knowledge(
        self,
        *,
        family_id: str,
        reason_rejected: str,
        reason_for_reopening: str | None = None,
        material_hypothesis_change: str | None = None,
        why_not_parameter_tuning: str | None = None,
    ) -> NegativeKnowledge:
        """Record why a family was rejected/quarantined (spec §11)."""
        created_at = _now_iso()
        cur = self._conn.execute(
            "INSERT INTO negative_knowledge (family_id, reason_rejected, reason_for_reopening, "
            "material_hypothesis_change, why_not_parameter_tuning, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                family_id,
                reason_rejected,
                reason_for_reopening,
                material_hypothesis_change,
                why_not_parameter_tuning,
                created_at,
            ),
        )
        self._conn.commit()
        return NegativeKnowledge(
            id=int(cur.lastrowid),
            family_id=family_id,
            reason_rejected=reason_rejected,
            reason_for_reopening=reason_for_reopening,
            material_hypothesis_change=material_hypothesis_change,
            why_not_parameter_tuning=why_not_parameter_tuning,
            created_at=created_at,
        )
