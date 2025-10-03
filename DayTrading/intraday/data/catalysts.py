from __future__ import annotations

import logging
from typing import Iterable, List, Tuple

from ..storage import models
from ..utils.time import hours_ago

logger = logging.getLogger(__name__)


def merge_catalysts(freshness_hours: int, *sources: Iterable[dict]) -> List[models.Catalyst]:
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
    catalysts: List[models.Catalyst] = []
    for (_symbol, _headline), payload in combined.items():
        ts = int(payload.get("ts", 0))
        fresh = ts >= threshold_ts
        catalysts.append(
            models.Catalyst(
                symbol=payload["symbol"].upper(),
                ts=ts,
                kind=str(payload.get("kind", "headline")),
                title=str(payload.get("headline", "")),
                source=str(payload.get("source", "unknown")),
                url=str(payload.get("url", "")),
                sentiment_score=_safe_float(payload.get("sentiment") or payload.get("sentiment_score")),
                importance=_safe_float(payload.get("importance")),
                dedupe_key=str(payload.get("dedupe_key") or f"{payload['symbol'].upper()}_{ts}"),
                raw_json={**payload, "fresh": fresh},
            )
        )

    return catalysts


def _safe_float(value: object) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None
