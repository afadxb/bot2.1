from __future__ import annotations

from typing import Dict, Iterable, List

from ..settings import AppSettings
from ..storage import models
from . import indicators


def build_snapshot(
    bars: Iterable[models.Bar],
    context: Dict[str, Dict[str, object]],
    settings: AppSettings,
) -> Dict[str, Dict[str, object]]:
    grouped: Dict[str, List[models.Bar]] = {}
    for bar in bars:
        grouped.setdefault(bar.symbol, []).append(bar)

    snapshot: Dict[str, Dict[str, float]] = {}
    for symbol, symbol_bars in grouped.items():
        symbol_bars.sort(key=lambda b: b.ts)
        closes = [bar.c for bar in symbol_bars]
        highs = [bar.h for bar in symbol_bars]
        lows = [bar.l for bar in symbol_bars]
        volumes = [bar.v for bar in symbol_bars]

        ema_fast = indicators.ema(closes, settings.ema_fast)
        ema_slow = indicators.ema(closes, settings.ema_slow)
        vwap_vals = indicators.vwap(symbol_bars)
        atr_vals = indicators.atr(symbol_bars, settings.ema_slow)
        baseline = indicators.volume_baseline(volumes, settings.cons_lookback_min)
        spikes = indicators.volume_spike(volumes, baseline)
        consolidation_vals = indicators.consolidation_score(symbol_bars, settings.cons_lookback_min)

        latest = {
            "symbol": symbol,
            "c": closes[-1],
            "h": highs[-1],
            "l": lows[-1],
            "v": volumes[-1],
            "ema_fast": ema_fast[-1],
            "ema_slow": ema_slow[-1],
            "vwap": vwap_vals[-1],
            "atr": atr_vals[-1],
            "volume_spike": spikes[-1],
            "consolidation": consolidation_vals[-1],
            "context_bias": 0.0,
        }

        ctx_row = context.get(symbol, {})
        if ctx_row:
            latest["context_bias"] = _compute_context_bias(ctx_row)
            for key, value in ctx_row.items():
                latest[f"ctx_{key}"] = value

        snapshot[symbol] = latest

    return snapshot


def _compute_context_bias(row: Dict[str, object]) -> float:
    bias = 0.0
    week52 = row.get("week52_pos")
    if isinstance(week52, (int, float)):
        bias += float(week52) * 0.1
    gap_pct = row.get("gap_pct")
    if isinstance(gap_pct, (int, float)):
        bias += float(gap_pct) * 0.05
    rel_volume = row.get("rel_volume")
    if isinstance(rel_volume, (int, float)):
        bias += (float(rel_volume) - 1.0) * 0.05
    return float(bias)
