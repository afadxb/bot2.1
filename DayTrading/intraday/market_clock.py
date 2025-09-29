from __future__ import annotations

from datetime import datetime, time

from .utils.time import ET, combine_date_time, now_et

MARKET_OPEN = time(9, 30)
MARKET_CLOSE = time(16, 0)


def session_bounds(day: datetime | None = None) -> tuple[datetime, datetime]:
    ref = day or now_et()
    open_dt = ref.replace(hour=MARKET_OPEN.hour, minute=MARKET_OPEN.minute, second=0, microsecond=0)
    close_dt = ref.replace(hour=MARKET_CLOSE.hour, minute=MARKET_CLOSE.minute, second=0, microsecond=0)
    return open_dt, close_dt


def is_market_open(current: datetime | None = None) -> bool:
    now = current or now_et()
    open_dt, close_dt = session_bounds(now)
    return open_dt <= now <= close_dt


def minutes_until_close(current: datetime | None = None) -> int:
    now = current or now_et()
    _, close_dt = session_bounds(now)
    delta = close_dt - now
    return max(int(delta.total_seconds() // 60), 0)


def should_flatten(flatten_dt: datetime, current: datetime | None = None) -> bool:
    now = current or now_et()
    return now >= flatten_dt
