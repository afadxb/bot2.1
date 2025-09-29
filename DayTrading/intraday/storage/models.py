from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict


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


@dataclass(slots=True)
class NewsItem:
    symbol: str
    source: str
    headline: str
    url: str
    ts: int
    sentiment: float | None = None
    meta: Dict[str, Any] | None = None


@dataclass(slots=True)
class Trade:
    symbol: str
    side: str
    qty: float
    status: str
    entry_px: float | None = None
    exit_px: float | None = None
    opened_ts: int | None = None
    closed_ts: int | None = None
    stop_px: float | None = None
    trail_mode: str | None = None
    tags: str | None = None
    pnl: float | None = None
    meta: Dict[str, Any] | None = None


@dataclass(slots=True)
class Position:
    symbol: str
    qty: float
    avg_px: float
    opened_ts: int
    stop_px: float | None = None
    trail_mode: str | None = None
    meta: Dict[str, Any] | None = None
