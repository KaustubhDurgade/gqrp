"""Return-series metrics + deflated/probabilistic Sharpe (spec §8, decision D3).

`purgedcv` is called only from this module. The deflated Sharpe ratio is the
López de Prado statistic that deflates the observed Sharpe by the *expected
maximum* Sharpe from N trials under the null — this is what makes the multiple-
testing bar (spec §6/§8) real. Its formula agreement with the rubenbriones
reference is asserted in `tests/test_metrics.py` (D3 verification bar).

Portfolio-level metrics (turnover, capacity, exposure/factor concentration) need
position data from the backtest engine and attach once that lands (spec §8);
this module covers everything computable from a return series.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
import purgedcv

from .. import config

_MIN_OBS = 2


def _as_returns(returns: np.ndarray | list[float]) -> np.ndarray:
    arr = np.asarray(returns, dtype=float)
    if arr.ndim != 1:
        raise ValueError(f"returns must be 1-D, got shape {arr.shape}")
    if arr.size < _MIN_OBS:
        raise ValueError(f"need at least {_MIN_OBS} return observations, got {arr.size}")
    if not np.all(np.isfinite(arr)):
        raise ValueError("returns contain non-finite values")
    return arr


def sharpe_ratio(returns: np.ndarray | list[float], *, annualize: bool = False) -> float:
    """Per-bar Sharpe (mean/std, sample std). Annualized by √bars_per_year."""
    arr = _as_returns(returns)
    sd = arr.std(ddof=1)
    if sd == 0:
        raise ValueError("zero-variance returns: Sharpe undefined")
    sr = arr.mean() / sd
    return sr * math.sqrt(config.BARS_PER_YEAR) if annualize else sr


def deflated_sharpe(
    returns: np.ndarray | list[float],
    *,
    n_trials: int,
    var_sharpe: float,
) -> float:
    """P(true Sharpe > the deflated benchmark) given `n_trials` searches (spec §8).

    `n_trials` is the cumulative weighted N from the registry; `var_sharpe` is the
    variance of the Sharpe estimates *across those trials* — it must be estimated
    from the real trial distribution, never chosen to clear the gate (guardrail
    spec §16). Returned value is a probability in [0, 1]; the gate passes at
    ≥ `DEFLATED_SHARPE_CONFIDENCE`.
    """
    arr = _as_returns(returns)
    if n_trials < 1:
        raise ValueError(f"n_trials must be ≥ 1, got {n_trials}")
    if var_sharpe < 0:
        raise ValueError(f"var_sharpe must be ≥ 0, got {var_sharpe}")
    return float(purgedcv.deflated_sharpe_ratio(arr, n_trials=n_trials, var_sharpe=var_sharpe))


def probabilistic_sharpe(
    returns: np.ndarray | list[float], *, benchmark_sharpe: float = 0.0
) -> float:
    """P(true Sharpe > `benchmark_sharpe`), accounting for skew/kurtosis (spec §8)."""
    arr = _as_returns(returns)
    return float(purgedcv.probabilistic_sharpe_ratio(arr, benchmark_skill=benchmark_sharpe))


def variance_of_trial_sharpes(trial_sharpes: list[float]) -> float:
    """`var_sharpe` for deflation: the sample variance of Sharpe estimates observed
    across a family's trials. The honest input to `deflated_sharpe` — computed from
    what was actually run, not tuned (spec §16)."""
    arr = np.asarray(trial_sharpes, dtype=float)
    if arr.size < _MIN_OBS:
        raise ValueError("need ≥ 2 trial Sharpes to estimate their variance")
    return float(arr.var(ddof=1))


def max_drawdown(returns: np.ndarray | list[float]) -> float:
    """Worst peak-to-trough decline of the compounded equity curve, as a negative
    fraction (0.0 = no drawdown)."""
    arr = _as_returns(returns)
    equity = np.cumprod(1.0 + arr)
    running_peak = np.maximum.accumulate(equity)
    drawdowns = equity / running_peak - 1.0
    return float(drawdowns.min())


def skewness(returns: np.ndarray | list[float]) -> float:
    arr = _as_returns(returns)
    sd = arr.std(ddof=0)
    if sd == 0:
        raise ValueError("zero-variance returns: skew undefined")
    return float(((arr - arr.mean()) ** 3).mean() / sd**3)


def kurtosis(returns: np.ndarray | list[float]) -> float:
    """Non-excess (normal ≈ 3.0)."""
    arr = _as_returns(returns)
    sd = arr.std(ddof=0)
    if sd == 0:
        raise ValueError("zero-variance returns: kurtosis undefined")
    return float(((arr - arr.mean()) ** 4).mean() / sd**4)


def subperiod_sharpes(returns: np.ndarray | list[float], *, n_subperiods: int) -> tuple[float, ...]:
    """Per-bar Sharpe within each of `n_subperiods` contiguous chunks — the raw
    material for a stability check (an edge that lives in one subperiod is fragile,
    spec §5/§8)."""
    arr = _as_returns(returns)
    if n_subperiods < 2:
        raise ValueError("need ≥ 2 subperiods")
    if arr.size < n_subperiods * _MIN_OBS:
        raise ValueError(f"too few observations ({arr.size}) for {n_subperiods} subperiods")
    out: list[float] = []
    for chunk in np.array_split(arr, n_subperiods):
        sd = chunk.std(ddof=1)
        out.append(float(chunk.mean() / sd) if sd != 0 else 0.0)
    return tuple(out)


def sharpe_sign_stability(returns: np.ndarray | list[float], *, n_subperiods: int = 4) -> float:
    """Fraction of subperiods whose Sharpe shares the full-sample Sharpe's sign
    (1.0 = edge present in every subperiod). A blunt but honest fragility signal."""
    full = sharpe_ratio(returns)
    subs = subperiod_sharpes(returns, n_subperiods=n_subperiods)
    if full == 0:
        return 0.0
    same = sum(1 for s in subs if (s > 0) == (full > 0) and s != 0)
    return same / len(subs)


@dataclass(frozen=True, slots=True)
class MetricsPanel:
    """The return-series slice of the §8 panel. Portfolio metrics attach later."""

    n_obs: int
    sharpe: float
    sharpe_annualized: float
    deflated_sharpe: float
    probabilistic_sharpe: float
    max_drawdown: float
    skew: float
    kurtosis: float
    sharpe_sign_stability: float
    n_trials: int
    var_sharpe: float


def compute_panel(
    returns: np.ndarray | list[float],
    *,
    n_trials: int,
    var_sharpe: float,
    n_subperiods: int = 4,
) -> MetricsPanel:
    """Assemble the return-series metrics panel (spec §8)."""
    arr = _as_returns(returns)
    return MetricsPanel(
        n_obs=int(arr.size),
        sharpe=sharpe_ratio(arr),
        sharpe_annualized=sharpe_ratio(arr, annualize=True),
        deflated_sharpe=deflated_sharpe(arr, n_trials=n_trials, var_sharpe=var_sharpe),
        probabilistic_sharpe=probabilistic_sharpe(arr),
        max_drawdown=max_drawdown(arr),
        skew=skewness(arr),
        kurtosis=kurtosis(arr),
        sharpe_sign_stability=sharpe_sign_stability(arr, n_subperiods=n_subperiods),
        n_trials=n_trials,
        var_sharpe=var_sharpe,
    )
