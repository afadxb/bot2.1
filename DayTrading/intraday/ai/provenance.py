from __future__ import annotations

from dataclasses import dataclass
from typing import List


@dataclass(slots=True)
class ProvenanceRecord:
    symbol: str
    score: float
    gate: str
    reasons: List[str]


__all__ = ["ProvenanceRecord"]
