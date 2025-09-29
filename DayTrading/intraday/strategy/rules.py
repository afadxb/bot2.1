from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Tuple


@dataclass(slots=True)
class RuleResult:
    passed: bool
    reason: str


def ema_cross_ok(row: Dict[str, float]) -> RuleResult:
    fast = row.get("ema_fast")
    slow = row.get("ema_slow")
    close = row.get("c") or row.get("close")
    if fast is None or slow is None or close is None:
        return RuleResult(False, "missing EMA data")
    passed = fast > slow and close > fast
    reason = "EMA fast above slow" if passed else "EMA alignment missing"
    return RuleResult(passed, reason)


def vwap_ok(row: Dict[str, float], enforce: bool = True) -> RuleResult:
    vwap_val = row.get("vwap")
    close = row.get("c") or row.get("close")
    if vwap_val is None or close is None:
        return RuleResult(not enforce, "vwap unavailable")
    passed = close >= vwap_val or not enforce
    reason = "Price above VWAP" if passed else "Below VWAP"
    return RuleResult(passed, reason)


def volume_ok(row: Dict[str, float], spike_mult: float) -> RuleResult:
    spike = row.get("volume_spike")
    if spike is None:
        return RuleResult(False, "volume data missing")
    passed = spike >= spike_mult
    reason = "Volume spike" if passed else "Volume muted"
    return RuleResult(passed, reason)


def not_consolidating(row: Dict[str, float], threshold: float = 0.02) -> RuleResult:
    score = row.get("consolidation")
    if score is None:
        return RuleResult(False, "consolidation unknown")
    passed = score <= threshold
    reason = "Range expansion ok" if passed else "Still consolidating"
    return RuleResult(passed, reason)
