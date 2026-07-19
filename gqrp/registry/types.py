"""Registry domain types (spec §A / §6).

Immutable by default (coding-style). The registry stores config and results as
opaque JSON blobs; these types are the typed view over the columns. `weight` is
never set by callers — it is derived from `level` via the fixed weight table so
the two can never diverge (spec §6).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Level = Literal["family", "variant", "hyperparam"]
RunType = Literal["research", "pipeline-validation"]
DataWindow = Literal["development", "validation", "holdout"]

# Fixed trial-accounting weights (spec §6) — never adjusted, derived from level.
LEVEL_WEIGHTS: dict[Level, float] = {"family": 1.0, "variant": 0.5, "hyperparam": 0.2}


def weight_for(level: Level) -> float:
    """The declared weight for a trial level (spec §6 weight table)."""
    try:
        return LEVEL_WEIGHTS[level]
    except KeyError as exc:  # noqa: PERF203 — boundary validation, fail loud
        raise ValueError(f"unknown trial level: {level!r}") from exc


@dataclass(frozen=True, slots=True)
class Trial:
    """A registered trial (spec §A `trial`) — config, logged before results."""

    trial_id: str
    family_id: str
    parent_trial_id: str | None
    level: Level
    weight: float
    run_type: RunType
    config_json: str
    config_hash: str
    data_window: DataWindow
    created_at: str
    status: str


@dataclass(frozen=True, slots=True)
class TrialResult:
    """A trial's results (spec §A `trial_result`) — written after the trial."""

    trial_id: str
    metrics_json: str
    gate_verdicts_json: str
    created_at: str


@dataclass(frozen=True, slots=True)
class ResearchMemo:
    """A hash-locked research memo (spec §A `research_memo`, §4 fields)."""

    memo_hash: str
    family_id: str
    memo_json: str
    committed_at: str


@dataclass(frozen=True, slots=True)
class NegativeKnowledge:
    """A quarantine record (spec §A `negative_knowledge`, §11 fields)."""

    id: int
    family_id: str
    reason_rejected: str
    reason_for_reopening: str | None
    material_hypothesis_change: str | None
    why_not_parameter_tuning: str | None
    created_at: str
