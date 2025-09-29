from __future__ import annotations

import logging
import math
from datetime import timedelta
from typing import Dict, Iterable, List

from ..settings import AppSettings
from ..storage import models
from ..storage.db import Database
from ..utils.time import now_et, to_epoch_seconds

logger = logging.getLogger(__name__)


class IBKRFeed:
    def __init__(self, settings: AppSettings, db: Database) -> None:
        self.settings = settings
        self.db = db

    def collect_bars(self, symbols: Iterable[str], tf: str) -> List[models.Bar]:
        if self.settings.is_simulation:
            bars = self._generate_sim_bars(symbols, tf)
            self.db.write_bars(bars)
            return bars
        raise RuntimeError("Live IBKR collection is not supported in tests")

    def _generate_sim_bars(self, symbols: Iterable[str], tf: str) -> List[models.Bar]:
        now = now_et()
        if tf == "5m":
            step = timedelta(minutes=5)
            periods = 30
        else:
            step = timedelta(minutes=15)
            periods = 20
        bars: List[models.Bar] = []
        for symbol in symbols:
            seed = (abs(hash(symbol)) % 1000) / 100.0
            base = 50 + seed
            for idx in range(periods):
                ts = now - step * (periods - idx)
                ts_epoch = to_epoch_seconds(ts)
                drift = idx * 0.15
                noise = (math.sin(idx + seed) + 1) * 0.5
                open_px = base + drift + noise
                close_px = open_px + math.sin(idx) * 0.3
                high_px = max(open_px, close_px) + 0.2
                low_px = min(open_px, close_px) - 0.2
                volume = 1000 + idx * 25 + int(seed * 10)
                bars.append(
                    models.Bar(
                        symbol=symbol,
                        tf=tf,
                        ts=ts_epoch,
                        o=round(open_px, 2),
                        h=round(high_px, 2),
                        l=round(low_px, 2),
                        c=round(close_px, 2),
                        v=float(volume),
                    )
                )
        bars.sort(key=lambda b: (b.symbol, b.ts))
        return bars

    def quotes_snapshot(self, symbols: Iterable[str]) -> Dict[str, float]:
        snapshot = {}
        for symbol in symbols:
            seed = (abs(hash(symbol)) % 1000) / 100.0
            snapshot[symbol] = 50 + seed + 0.5
        return snapshot
