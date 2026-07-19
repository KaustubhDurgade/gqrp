"""Registry tests — proves the immutability guarantees the spec demands (§6, D4).

The CLAUDE.md verification bar for the registry is explicit: *prove immutability
by showing an UPDATE being rejected.* `test_update_is_rejected_by_trigger` and
`test_readonly_client_cannot_write` are that proof.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from gqrp.registry.client import RegistryReader
from gqrp.registry.server import RegistryWriter
from gqrp.registry.types import weight_for


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    return tmp_path / "registry.db"


@pytest.fixture
def writer(db_path: Path):
    w = RegistryWriter(db_path)
    yield w
    w.close()


def _make_trial(writer: RegistryWriter, **overrides):
    kwargs = dict(
        family_id="fam-momentum-xsec",
        level="family",
        run_type="research",
        config={"primitive": "momentum", "lookback": 30},
        config_hash="deadbeef",
        data_window="development",
    )
    kwargs.update(overrides)
    return writer.append_trial(**kwargs)


# ── append + read round-trip ────────────────────────────────────────────────
def test_append_trial_round_trips(writer, db_path):
    trial = _make_trial(writer)
    writer.close()

    with RegistryReader(db_path) as reader:
        loaded = reader.get_trial(trial.trial_id)
    assert loaded is not None
    assert loaded.family_id == "fam-momentum-xsec"
    assert loaded.weight == 1.0
    assert loaded.run_type == "research"


def test_result_written_after_trial(writer, db_path):
    trial = _make_trial(writer)
    writer.append_result(
        trial_id=trial.trial_id,
        metrics={"deflated_sharpe": 0.4},
        gate_verdicts={"statistical": "fail"},
    )
    writer.close()

    with RegistryReader(db_path) as reader:
        result = reader.get_result(trial.trial_id)
    assert result is not None
    assert '"deflated_sharpe":0.4' in result.metrics_json


# ── config BEFORE results (spec §6) ─────────────────────────────────────────
def test_result_without_trial_is_rejected(writer):
    with pytest.raises(ValueError, match="config must precede results"):
        writer.append_result(
            trial_id="does-not-exist", metrics={}, gate_verdicts={}
        )


def test_second_result_for_trial_is_rejected(writer):
    trial = _make_trial(writer)
    writer.append_result(trial_id=trial.trial_id, metrics={"a": 1}, gate_verdicts={})
    with pytest.raises(ValueError, match="already recorded"):
        writer.append_result(trial_id=trial.trial_id, metrics={"a": 2}, gate_verdicts={})


# ── the weight table is fixed & derived from level (spec §6) ─────────────────
def test_weight_is_derived_from_level(writer):
    fam = _make_trial(writer, level="family")
    var = _make_trial(writer, level="variant")
    hyp = _make_trial(writer, level="hyperparam")
    assert (fam.weight, var.weight, hyp.weight) == (1.0, 0.5, 0.2)


def test_weight_for_rejects_unknown_level():
    with pytest.raises(ValueError, match="unknown trial level"):
        weight_for("bogus")  # type: ignore[arg-type]


# ── cumulative weighted N (spec §6, decision D7) ────────────────────────────
def test_cumulative_n_sums_research_weights(writer, db_path):
    _make_trial(writer, level="family")  # 1.0
    _make_trial(writer, level="variant")  # 0.5
    _make_trial(writer, level="hyperparam")  # 0.2
    writer.close()

    with RegistryReader(db_path) as reader:
        assert reader.cumulative_weighted_n() == pytest.approx(1.7)


def test_pipeline_validation_excluded_from_n(writer, db_path):
    _make_trial(writer, level="family", run_type="research")  # counts: 1.0
    _make_trial(writer, level="family", run_type="pipeline-validation")  # excluded
    writer.close()

    with RegistryReader(db_path) as reader:
        assert reader.cumulative_weighted_n() == pytest.approx(1.0)


def test_empty_registry_has_zero_n(writer, db_path):
    writer.close()
    with RegistryReader(db_path) as reader:
        assert reader.cumulative_weighted_n() == 0.0


# ── IMMUTABILITY — the verification bar (CLAUDE.md) ─────────────────────────
def test_update_is_rejected_by_trigger(writer, db_path):
    """Prove immutability: a raw UPDATE against the DB is aborted by the trigger.

    There is no retag path (D7) — this is what makes 'no code retags run_type'
    structural rather than policy."""
    trial = _make_trial(writer, run_type="research")
    writer.close()

    raw = sqlite3.connect(db_path)
    try:
        with pytest.raises(sqlite3.Error, match="append-only"):
            raw.execute(
                "UPDATE trial SET run_type = 'pipeline-validation' WHERE trial_id = ?",
                (trial.trial_id,),
            )
    finally:
        raw.close()


def test_delete_is_rejected_by_trigger(writer, db_path):
    trial = _make_trial(writer)
    writer.close()

    raw = sqlite3.connect(db_path)
    try:
        with pytest.raises(sqlite3.Error, match="append-only"):
            raw.execute("DELETE FROM trial WHERE trial_id = ?", (trial.trial_id,))
    finally:
        raw.close()


def test_result_update_is_rejected_by_trigger(writer, db_path):
    trial = _make_trial(writer)
    writer.append_result(trial_id=trial.trial_id, metrics={"a": 1}, gate_verdicts={})
    writer.close()

    raw = sqlite3.connect(db_path)
    try:
        with pytest.raises(sqlite3.Error, match="append-only"):
            raw.execute(
                "UPDATE trial_result SET metrics_json = '{}' WHERE trial_id = ?",
                (trial.trial_id,),
            )
    finally:
        raw.close()


def test_readonly_client_cannot_write(writer, db_path):
    """The Phase-2-agent-facing client has no write path at all."""
    _make_trial(writer)
    writer.close()

    with RegistryReader(db_path) as reader:
        with pytest.raises(sqlite3.OperationalError, match="readonly"):
            reader._conn.execute(  # noqa: SLF001 — asserting the guarantee
                "UPDATE trial SET status = 'tampered'"
            )


# ── memo + negative knowledge ───────────────────────────────────────────────
def test_memo_is_hash_locked(writer):
    writer.append_memo(family_id="fam-x", memo_hash="abc123", memo={"mechanism": "carry"})
    with pytest.raises(ValueError, match="already committed"):
        writer.append_memo(family_id="fam-x", memo_hash="abc123", memo={"mechanism": "changed"})


def test_negative_knowledge_append(writer):
    nk = writer.append_negative_knowledge(
        family_id="fam-x",
        reason_rejected="fees erase it",
        why_not_parameter_tuning="mechanism itself is fee-fragile",
    )
    assert nk.id >= 1
    assert nk.reason_rejected == "fees erase it"
