from __future__ import annotations

import logging
from datetime import timedelta
from typing import Iterable, List

from ..settings import AppSettings
from ..utils.time import now_et, to_epoch_seconds

logger = logging.getLogger(__name__)


class YahooFeed:
    def __init__(self, settings: AppSettings) -> None:
        self.settings = settings

    def fetch(self, symbols: Iterable[str]) -> List[dict]:
        base_time = now_et()
        items: List[dict] = []
        for idx, symbol in enumerate(symbols):
            ts = base_time - timedelta(minutes=idx * 11)
            items.append(
                {
                    "symbol": symbol,
                    "headline": f"Yahoo headline for {symbol}",
                    "url": f"https://news.example.com/{symbol.lower()}/yahoo",
                    "ts": to_epoch_seconds(ts),
                    "source": "yahoo",
                }
            )
        return items
