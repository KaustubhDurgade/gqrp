"""Gate tests — statistical (§8) and economic (§9).

Proves the bar rises with cumulative N (seam 2) and that a statistically-fine but
uneconomic strategy is still rejected (§9's canonical death).
"""

from __future__ import annotations

import pytest

pytest.importorskip("purgedcv")
pytest.importorskip("numpy")

import numpy as np  # noqa: E402

from gqrp.gates import economic, statistical  # noqa: E402
from gqrp.gates.economic import EconomicInputs  # noqa: E402


# ── statistical gate ────────────────────────────────────────────────────────
def test_n_trials_rounds_up_and_floors_at_one():
    assert statistical.n_trials_from_cumulative_n(0.0) == 1
    assert statistical.n_trials_from_cumulative_n(1.2) == 2
    assert statistical.n_trials_from_cumulative_n(7.0) == 7


def test_strong_edge_passes_at_low_n():
    rng = np.random.default_rng(2)
    r = rng.normal(0.002, 0.006, size=2000)  # strong, clean edge
    v = statistical.evaluate(r, cumulative_n=1.0, var_sharpe=0.01)
    assert v.passed
    assert v.value >= 0.95
    assert v.reasons == ()


def test_same_edge_fails_once_n_is_large():
    """Seam 2: the identical return series fails as cumulative N grows."""
    rng = np.random.default_rng(2)
    r = rng.normal(0.002, 0.006, size=2000)
    v = statistical.evaluate(r, cumulative_n=500.0, var_sharpe=0.25)
    assert not v.passed
    assert v.reasons  # explains the rejection


def test_verdict_carries_threshold():
    rng = np.random.default_rng(4)
    r = rng.normal(0.001, 0.01, size=500)
    v = statistical.evaluate(r, cumulative_n=3.0, var_sharpe=0.02, confidence=0.95)
    assert v.name == "statistical"
    assert v.threshold == 0.95


# ── economic gate ───────────────────────────────────────────────────────────
def test_canonical_death_is_rejected():
    """Spec §9 example: Sharpe 1.1, 5% annual, 800% turnover, $30k capacity."""
    v = economic.evaluate(
        EconomicInputs(capacity_usd=30_000, gross_annual_return=0.05, annual_turnover=8.0)
    )
    assert not v.passed
    assert any("capacity" in r for r in v.reasons)


def test_healthy_strategy_passes():
    v = economic.evaluate(
        EconomicInputs(capacity_usd=250_000, gross_annual_return=0.30, annual_turnover=4.0)
    )
    assert v.passed
    assert v.reasons == ()


def test_fees_erasing_edge_is_rejected():
    # gross 3% but 20× turnover × 0.25%/side = 5% cost drag → net negative.
    v = economic.evaluate(
        EconomicInputs(capacity_usd=1_000_000, gross_annual_return=0.03, annual_turnover=20.0)
    )
    assert not v.passed
    assert any("fees erase" in r for r in v.reasons)
    assert v.value < 0


def test_net_return_and_cost_drag_math():
    e = EconomicInputs(capacity_usd=100_000, gross_annual_return=0.20, annual_turnover=10.0)
    assert e.annual_cost_drag == pytest.approx(10.0 * (0.001 + 0.0015))
    assert e.net_annual_return == pytest.approx(0.20 - 0.025)
