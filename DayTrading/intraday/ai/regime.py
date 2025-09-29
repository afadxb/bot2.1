from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class RegimeContext:
    multiplier: float = 1.0
    description: str = "neutral"


def current_regime() -> RegimeContext:
    """Return a neutral regime multiplier.

    The placeholder keeps the strategy extensible while remaining deterministic
    for tests.
    """

    return RegimeContext()
