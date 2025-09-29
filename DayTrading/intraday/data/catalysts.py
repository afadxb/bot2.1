from __future__ import annotations

import logging
from typing import Iterable, List, Tuple

from ..storage import models
from ..storage.db import Database
from ..utils.time import hours_ago

logger = logging.getLogger(__name__)


def merge_catalysts(db: Database, freshness_hours: int, *sources: Iterable[dict]) -> List[models.NewsItem]:
    combined: dict[Tuple[str, str], dict] = {}
    for source_items in sources:
        for item in source_items:
            symbol = item.get("symbol")
            if not isinstance(symbol, str):
                continue
            headline = item.get("headline") or ""
            url = item.get("url") or headline
            key = (symbol.upper(), headline or url)
            ts = int(item.get("ts", 0))
            payload = {**item, "symbol": symbol.upper(), "ts": ts}
            current = combined.get(key)
            if current is None or ts > current["ts"]:
                combined[key] = payload

    threshold_ts = int(hours_ago(freshness_hours).timestamp())
    news_items: List[models.NewsItem] = []
    for (_symbol, _headline), payload in combined.items():
        ts = int(payload.get("ts", 0))
        fresh = ts >= threshold_ts
        meta = {k: v for k, v in payload.items() if k not in {"symbol", "headline", "url", "ts", "source"}}
        meta["fresh"] = fresh
        news_items.append(
            models.NewsItem(
                symbol=payload["symbol"].upper(),
                source=str(payload.get("source", "unknown")),
                headline=str(payload.get("headline", "")),
                url=str(payload.get("url", "")),
                ts=ts,
                sentiment=float(payload.get("sentiment", 0.0)) if payload.get("sentiment") is not None else None,
                meta=meta,
            )
        )

    if news_items:
        db.write_news(news_items)
    return news_items
