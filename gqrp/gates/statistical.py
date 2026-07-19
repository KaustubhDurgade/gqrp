"""Statistical gate (spec §8) — deflated Sharpe > 0 at 95% given cumulative N.

The number of trials fed to the deflation is the registry's **live cumulative
weighted N** (Σ weight over research trials, decision D7). As more research
families are logged, N rises and this bar rises automatically (architecture seam
2) — the gate gets harder the more you search, which is the entire point.
"""

from __future__ import annotations

import math

import numpy as np

from .. import config
from ..metrics import panel
from .verdict import GateVerdict

_NAME = "statistical"


def n_trials_from_cumulative_n(cumulative_n: float) -> int:
    """Weighted N (a float) → an integer trial count for deflation.

    Round *up*: a fractional trial still counts against you, and rounding up can
    only make the bar stricter (never a way to sneak past it, spec §16). Floors
    at 1 — the strategy under test is itself a trial."""
    return max(1, math.ceil(cumulative_n))


def evaluate(
    returns: np.ndarray | list[float],
    *,
    cumulative_n: float,
    var_sharpe: float,
    confidence: float = config.DEFLATED_SHARPE_CONFIDENCE,
) -> GateVerdict:
    """Pass iff the deflated Sharpe probability ≥ `confidence` (default 95%).

    `cumulative_n` comes from `registry.client.RegistryReader.cumulative_weighted_n()`;
    `var_sharpe` is the variance of the family's trial Sharpes (see
    `metrics.panel.variance_of_trial_sharpes`) — an honest input, not a knob.
    """
    n_trials = n_trials_from_cumulative_n(cumulative_n)
    dsr = panel.deflated_sharpe(returns, n_trials=n_trials, var_sharpe=var_sharpe)

    passed = dsr >= confidence
    reasons: tuple[str, ...] = ()
    if not passed:
        reasons = (
            f"deflated Sharpe probability {dsr:.4f} < {confidence:.2f} "
            f"at cumulative weighted N={cumulative_n:g} (n_trials={n_trials}, "
            f"var_sharpe={var_sharpe:g})",
        )
    return GateVerdict(
        name=_NAME, passed=passed, value=dsr, threshold=confidence, reasons=reasons
    )
