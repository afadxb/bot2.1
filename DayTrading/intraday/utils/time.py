from __future__ import annotations

from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/Toronto")


def now_et() -> datetime:
    return datetime.now(tz=ET)


def to_epoch_seconds(dt: datetime) -> int:
    return int(dt.timestamp())


def combine_date_time(date: datetime, t: time) -> datetime:
    return datetime.combine(date.date(), t, tzinfo=date.tzinfo or ET)


def minutes_until(target: datetime) -> int:
    delta = target - now_et()
    return max(int(delta.total_seconds() // 60), 0)


def hours_ago(hours: float) -> datetime:
    return now_et() - timedelta(hours=hours)


def today_et() -> datetime:
    now = now_et()
    return now.replace(hour=0, minute=0, second=0, microsecond=0)
