from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List

from ..ai.sentiment import SentimentResult
from ..settings import AppSettings
from . import rules


@dataclass(slots=True)
class RankedSignal:
    symbol: str
    base_score: float
    ai_adjustment: float
    context_bias: float
    score: float
    decision: str
    reasons: List[str]
    gate: str


def rank_candidates(features: Dict[str, Dict[str, float]], sentiment: Dict[str, SentimentResult], settings: AppSettings) -> List[RankedSignal]:
    results: List[RankedSignal] = []
    for symbol, row in features.items():
        ema_res = rules.ema_cross_ok(row)
        vwap_res = rules.vwap_ok(row, settings.vwap_enforce)
        vol_res = rules.volume_ok(row, settings.vol_spike_mult)
        cons_res = rules.not_consolidating(row, threshold=0.05)
        base_score = sum(25 for flag in (ema_res.passed, vwap_res.passed, vol_res.passed, cons_res.passed) if flag)

        sentiment_res = sentiment.get(symbol, SentimentResult(score=0.0, gate="PASS", reasons=["no news"]))
        ai_component = max(min(sentiment_res.score, 1.0), -1.0) * 30
        context_bias = float(row.get("context_bias", 0.0)) * 10
        if sentiment_res.gate == "VETO":
            results.append(
                RankedSignal(
                    symbol=symbol,
                    base_score=base_score,
                    ai_adjustment=ai_component,
                    context_bias=context_bias,
                    score=0.0,
                    decision="skip_ai_veto",
                    reasons=["AI veto"],
                    gate="VETO",
                )
            )
            continue
        total = max(base_score + ai_component + context_bias, 0.0)
        reasons = [ema_res.reason, vwap_res.reason, vol_res.reason, cons_res.reason]
        reasons.extend(sentiment_res.reasons)
        decision = "enter_long" if total > 0 else "observe"
        results.append(
            RankedSignal(
                symbol=symbol,
                base_score=base_score,
                ai_adjustment=ai_component,
                context_bias=context_bias,
                score=total,
                decision=decision,
                reasons=reasons,
                gate=sentiment_res.gate,
            )
        )

    results.sort(key=lambda item: item.score, reverse=True)
    return results[: settings.top_k_execute]
