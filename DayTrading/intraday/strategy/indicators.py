from __future__ import annotations

from typing import List, Sequence

from ..storage import models


def ema(values: Sequence[float], period: int) -> List[float]:
    result: List[float] = []
    alpha = 2.0 / (period + 1)
    ema_val: float | None = None
    for value in values:
        if ema_val is None:
            ema_val = value
        else:
            ema_val = alpha * value + (1 - alpha) * ema_val
        result.append(ema_val)
    return result


def vwap(bars: Sequence[models.Bar]) -> List[float]:
    cum_vol = 0.0
    cum_tp = 0.0
    result: List[float] = []
    for bar in bars:
        typical = (bar.h + bar.l + bar.c) / 3.0
        cum_vol += bar.v
        cum_tp += typical * bar.v
        result.append(cum_tp / cum_vol if cum_vol else typical)
    return result


def atr(bars: Sequence[models.Bar], period: int) -> List[float]:
    trs: List[float] = []
    prev_close: float | None = None
    for bar in bars:
        range_high_low = bar.h - bar.l
        range_high_close = abs(bar.h - prev_close) if prev_close is not None else range_high_low
        range_low_close = abs(bar.l - prev_close) if prev_close is not None else range_high_low
        tr = max(range_high_low, range_high_close, range_low_close)
        trs.append(tr)
        prev_close = bar.c
    smoothed: List[float] = []
    for idx in range(len(trs)):
        start = max(0, idx - period + 1)
        window = trs[start : idx + 1]
        smoothed.append(sum(window) / len(window))
    return smoothed


def consolidation_score(bars: Sequence[models.Bar], lookback: int) -> List[float]:
    closes = [bar.c for bar in bars]
    highs = [bar.h for bar in bars]
    lows = [bar.l for bar in bars]
    scores: List[float] = []
    for idx in range(len(bars)):
        start = max(0, idx - lookback + 1)
        window_high = max(highs[start : idx + 1])
        window_low = min(lows[start : idx + 1])
        window_mean = sum(closes[start : idx + 1]) / (idx - start + 1)
        range_ = window_high - window_low
        scores.append(range_ / window_mean if window_mean else 0.0)
    return scores


def volume_baseline(volumes: Sequence[float], lookback: int) -> List[float]:
    baseline: List[float] = []
    for idx in range(len(volumes)):
        start = max(0, idx - lookback + 1)
        window = volumes[start : idx + 1]
        baseline.append(sum(window) / len(window))
    return baseline


def volume_spike(volumes: Sequence[float], baseline: Sequence[float]) -> List[float]:
    spikes: List[float] = []
    for vol, base in zip(volumes, baseline):
        spikes.append(vol / base if base else 0.0)
    return spikes
