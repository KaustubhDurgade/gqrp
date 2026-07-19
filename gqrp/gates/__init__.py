"""Gates — the statistical (§8) and economic (§9) rejection tests.

Gates exist to *reject*. Their thresholds are declared in `config` and fixed in
advance; nothing here is ever tuned toward letting a strategy pass (guardrail
spec §16). A gate returns a `GateVerdict`, never mutates anything.
"""

from .verdict import GateVerdict

__all__ = ["GateVerdict"]
