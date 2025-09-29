from __future__ import annotations

from intraday.storage.models import Bar
from intraday.strategy import indicators, rules


def test_indicator_suite_produces_expected_values():
    bars = [
        Bar(symbol="A", tf="5m", ts=i, o=10 + i, h=11 + i, l=9 + i * 0.5, c=10 + i * 0.8, v=100 + i * 10)
        for i in range(5)
    ]
    closes = [bar.c for bar in bars]
    ema_fast = indicators.ema(closes, 2)
    ema_slow = indicators.ema(closes, 3)
    vwap_vals = indicators.vwap(bars)
    atr_vals = indicators.atr(bars, 3)
    cons = indicators.consolidation_score(bars, 3)
    baseline = indicators.volume_baseline([bar.v for bar in bars], 3)
    spike = indicators.volume_spike([bar.v for bar in bars], baseline)

    assert len(ema_fast) == len(bars)
    assert vwap_vals[-1] > 0
    assert atr_vals[-1] > 0
    assert cons[-1] >= 0
    assert spike[-1] >= 0


def test_rules_cover_positive_and_negative_cases():
    row = {
        "ema_fast": 12,
        "ema_slow": 10,
        "c": 13,
        "vwap": 12,
        "volume_spike": 3.0,
        "consolidation": 0.01,
    }
    assert rules.ema_cross_ok(row).passed
    assert rules.vwap_ok(row).passed
    assert rules.volume_ok(row, 2.0).passed
    assert rules.not_consolidating(row, 0.05).passed

    row["ema_fast"] = 8
    assert not rules.ema_cross_ok(row).passed
