"""Economic viability gate (spec §9) — run after metrics, before forward test.

"Statistically fine" is not "a business." This gate rejects edges that survive
the statistical bar but die on costs, capacity, or turnover. The canonical death
(spec §9): Sharpe 1.1, 5% annual, 800% turnover, $30k capacity — the numbers are
fine and it is still not worth trading.

Thresholds are declared in `config`; this module only reads them (spec §16).
"""

from __future__ import annotations

from dataclasses import dataclass

from .. import config
from .verdict import GateVerdict

_NAME = "economic"


@dataclass(frozen=True, slots=True)
class EconomicInputs:
    """Portfolio economics from a backtest.

    `annual_turnover` is total traded notional / capital per year, counting each
    side (2.0 = the book is fully bought and fully sold once). `cost_per_side`
    defaults to the declared taker fee + slippage (spec §1).
    """

    capacity_usd: float
    gross_annual_return: float
    annual_turnover: float
    cost_per_side: float = config.COST_PER_SIDE

    @property
    def annual_cost_drag(self) -> float:
        return self.annual_turnover * self.cost_per_side

    @property
    def net_annual_return(self) -> float:
        return self.gross_annual_return - self.annual_cost_drag


def evaluate(
    inputs: EconomicInputs, *, min_capacity_usd: float = config.MIN_CAPACITY_USD
) -> GateVerdict:
    """Pass iff capacity clears the floor AND cost-of-trading doesn't erase the edge.

    Reported `value` is net annual return (after cost drag) against a threshold of
    0.0; capacity failures are surfaced in `reasons` alongside it.
    """
    reasons: list[str] = []

    if inputs.capacity_usd < min_capacity_usd:
        reasons.append(
            f"capacity ${inputs.capacity_usd:,.0f} < floor ${min_capacity_usd:,.0f}"
        )

    net = inputs.net_annual_return
    if net <= 0:
        reasons.append(
            f"fees erase the edge: gross {inputs.gross_annual_return:.2%} − cost drag "
            f"{inputs.annual_cost_drag:.2%} (turnover {inputs.annual_turnover:.1f}× × "
            f"{inputs.cost_per_side:.2%}/side) = net {net:.2%}"
        )

    return GateVerdict(
        name=_NAME,
        passed=not reasons,
        value=net,
        threshold=0.0,
        reasons=tuple(reasons),
    )
