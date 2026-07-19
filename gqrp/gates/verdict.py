"""Shared gate verdict type."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class GateVerdict:
    """The outcome of a single gate. `reasons` explain a failure (empty on pass)."""

    name: str
    passed: bool
    value: float
    threshold: float
    reasons: tuple[str, ...] = field(default_factory=tuple)
