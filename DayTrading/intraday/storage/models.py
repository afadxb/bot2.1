from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, Mapping, Sequence


@dataclass(slots=True)
class Bar:
    symbol: str
    tf: str
    ts: int
    o: float
    h: float
    l: float
    c: float
    v: float
    vwap: float | None = None


@dataclass(slots=True)
class Catalyst:
    symbol: str
    ts: int
    kind: str
    title: str
    source: str
    url: str | None = None
    sentiment_score: float | None = None
    importance: float | None = None
    dedupe_key: str | None = None
    raw_json: Mapping[str, Any] | None = None


@dataclass(slots=True)
class IntradayFeatureRow:
    symbol: str
    ts: int
    timeframe: str
    features: Mapping[str, Any]


@dataclass(slots=True)
class SignalRecord:
    symbol: str
    ts: int
    timeframe: str
    base_score: float
    ai_adjustment: float
    final_score: float
    decision: str
    reason_tags: str
    details: Mapping[str, Any]
    phase1_rank: int | None = None
    run_date: str | None = None


@dataclass(slots=True)
class AIProvenanceRecord:
    symbol: str
    ts: int
    model_name: str
    inputs: Mapping[str, Any] | None
    outputs: Mapping[str, Any] | None
    delta_applied: float | None
    notes: str | None = None


@dataclass(slots=True)
class Order:
    symbol: str
    side: str
    order_type: str
    qty: float
    limit_price: float | None
    stop_price: float | None
    tif: str
    status: str
    placed_ts: int
    updated_ts: int | None
    meta: Mapping[str, Any] | None = None
    client_order_id: str | None = None
    signal_id: int | None = None


@dataclass(slots=True)
class Fill:
    order_id: int
    fill_ts: int
    fill_price: float
    fill_qty: float
    liquidity: str | None = None
    venue: str | None = None


@dataclass(slots=True)
class Position:
    symbol: str
    avg_price: float
    qty: float
    opened_ts: int
    last_update_ts: int
    meta: Dict[str, Any] | None = None


@dataclass(slots=True)
class TradeJournalEntry:
    symbol: str
    open_ts: int
    close_ts: int | None
    side: str
    entry_price: float
    exit_price: float | None
    qty: float
    pnl: float | None
    reason_open: str | None
    reason_close: str | None
    tags: str | None
    signal_id: int | None = None


@dataclass(slots=True)
class IntradayCycleRun:
    run_started_ts: int
    run_finished_ts: int | None
    watchlist_count: int
    evaluated_count: int
    placed_orders: int
    errors_count: int
    timings: Mapping[str, float] | None = None
    notes: Mapping[str, Any] | None = None


PayloadSequence = Iterable[Sequence[Any]]
