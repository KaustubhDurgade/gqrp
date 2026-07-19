"""Metrics tests — includes the D3 verification bar.

CLAUDE.md verification bar for metrics: *show DSR matching the reference
implementation.* `test_dsr_matches_reference_formula` reconstructs the López de
Prado deflated-Sharpe statistic independently (the rubenbriones reference form)
and asserts our wrapper's output matches to full precision.
"""

from __future__ import annotations

import math

import pytest

pytest.importorskip("purgedcv")  # quant extra; core suite stays stdlib-only
pytest.importorskip("numpy")

import numpy as np  # noqa: E402
from scipy.stats import norm  # noqa: E402

from gqrp.metrics import panel  # noqa: E402

_EULER = 0.5772156649015329


def _reference_dsr(returns: np.ndarray, *, n_trials: int, var_sharpe: float) -> float:
    """Independent López de Prado / rubenbriones DSR port for cross-checking."""
    r = np.asarray(returns, dtype=float)
    n = r.size
    sr = r.mean() / r.std(ddof=1)
    sd0 = r.std(ddof=0)
    skew = ((r - r.mean()) ** 3).mean() / sd0**3
    kurt = ((r - r.mean()) ** 4).mean() / sd0**4
    # Expected maximum Sharpe under the null across n_trials searches.
    sr0 = math.sqrt(var_sharpe) * (
        (1 - _EULER) * norm.ppf(1 - 1 / n_trials)
        + _EULER * norm.ppf(1 - 1 / (n_trials * math.e))
    )
    denom = math.sqrt(1 - skew * sr + ((kurt - 1) / 4) * sr**2)
    return float(norm.cdf((sr - sr0) * math.sqrt(n - 1) / denom))


# ── D3 VERIFICATION BAR ─────────────────────────────────────────────────────
@pytest.mark.parametrize("seed,n_trials,var_sharpe", [(7, 15, 0.04), (42, 5, 0.09), (1, 50, 0.01)])
def test_dsr_matches_reference_formula(seed, n_trials, var_sharpe):
    rng = np.random.default_rng(seed)
    r = rng.normal(0.0005, 0.008, size=1500)
    ours = panel.deflated_sharpe(r, n_trials=n_trials, var_sharpe=var_sharpe)
    reference = _reference_dsr(r, n_trials=n_trials, var_sharpe=var_sharpe)
    assert ours == pytest.approx(reference, abs=1e-12)


def test_dsr_falls_as_n_trials_rises():
    """More trials → lower deflated-Sharpe probability (the multiple-testing bar)."""
    rng = np.random.default_rng(3)
    r = rng.normal(0.0006, 0.007, size=1200)
    few = panel.deflated_sharpe(r, n_trials=2, var_sharpe=0.02)
    many = panel.deflated_sharpe(r, n_trials=200, var_sharpe=0.02)
    assert many < few


# ── return-series metrics ───────────────────────────────────────────────────
def test_sharpe_and_annualization():
    r = [0.01, -0.005, 0.02, 0.0, 0.015]
    per_bar = panel.sharpe_ratio(r)
    annual = panel.sharpe_ratio(r, annualize=True)
    assert annual == pytest.approx(per_bar * math.sqrt(365))


def test_zero_variance_returns_raise():
    with pytest.raises(ValueError, match="zero-variance"):
        panel.sharpe_ratio([0.01, 0.01, 0.01])


def test_max_drawdown_known_path():
    # +10% then -50% → equity 1.1 then 0.55; peak 1.1 → trough 0.55 = -50%.
    r = [0.10, -0.50]
    assert panel.max_drawdown(r) == pytest.approx(-0.5)


def test_max_drawdown_monotonic_up_is_zero():
    assert panel.max_drawdown([0.01, 0.02, 0.03]) == pytest.approx(0.0)


def test_probabilistic_sharpe_in_unit_interval():
    rng = np.random.default_rng(9)
    r = rng.normal(0.001, 0.01, size=500)
    psr = panel.probabilistic_sharpe(r)
    assert 0.0 <= psr <= 1.0


def test_variance_of_trial_sharpes():
    assert panel.variance_of_trial_sharpes([1.0, 1.0, 1.0]) == pytest.approx(0.0)
    assert panel.variance_of_trial_sharpes([0.0, 2.0]) == pytest.approx(2.0)


def test_sharpe_sign_stability():
    # Consistently positive drift → stability 1.0
    rng = np.random.default_rng(5)
    r = rng.normal(0.002, 0.005, size=400)
    assert panel.sharpe_sign_stability(r, n_subperiods=4) == pytest.approx(1.0)


def test_compute_panel_assembles_fields():
    rng = np.random.default_rng(11)
    r = rng.normal(0.0008, 0.009, size=800)
    p = panel.compute_panel(r, n_trials=10, var_sharpe=0.03)
    assert p.n_obs == 800
    assert p.n_trials == 10
    assert 0.0 <= p.deflated_sharpe <= 1.0
    assert p.max_drawdown <= 0.0


def test_returns_validation():
    with pytest.raises(ValueError, match="at least 2"):
        panel.sharpe_ratio([0.01])
    with pytest.raises(ValueError, match="non-finite"):
        panel.max_drawdown([0.01, float("nan"), 0.02])
