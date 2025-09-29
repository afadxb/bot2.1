from __future__ import annotations

import time
from collections import defaultdict
from typing import Callable, Dict, TypeVar

T = TypeVar("T")


class Throttle:
    """Simple token bucket style throttle keyed by identifier."""

    def __init__(self, min_interval: float) -> None:
        self.min_interval = min_interval
        self._last: Dict[str, float] = defaultdict(float)

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        last = self._last[key]
        if now - last >= self.min_interval:
            self._last[key] = now
            return True
        return False


def throttle(min_interval: float) -> Callable[[Callable[..., T]], Callable[..., T]]:
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        last_called = 0.0

        def wrapped(*args, **kwargs):  # type: ignore[no-untyped-def]
            nonlocal last_called
            now = time.monotonic()
            if now - last_called < min_interval:
                time.sleep(min_interval - (now - last_called))
            last_called = time.monotonic()
            return func(*args, **kwargs)

        return wrapped

    return decorator
