from __future__ import annotations

import json
import logging
from collections import OrderedDict
from pathlib import Path
from typing import Dict, List, Tuple

from ..settings import AppSettings
from ..storage.db import Database
from ..utils import time as time_utils

logger = logging.getLogger(__name__)

_FLAT_FIELDS = {
    "sector",
    "industry",
    "price",
    "change_pct",
    "gap_pct",
    "rel_volume",
    "avg_volume_3m",
    "float_shares",
    "short_float_pct",
    "pe",
    "week52_pos",
    "earnings_date",
    "analyst_recom",
    "tags",
    "tier",
    "score",
}

_FEATURE_FIELDS = {
    "relvol",
    "avgvol",
    "float_band",
    "gap",
    "change",
    "after_hours",
    "52w_pos",
    "short_float",
    "analyst",
    "insider_inst",
    "news_fresh",
}


class WatchlistLoader:
    def __init__(self, settings: AppSettings, db: Database) -> None:
        self.settings = settings
        self.db = db

    def load(self, path: Path | None = None) -> tuple[int, list[str], Dict[str, Dict[str, object]]]:
        watchlist_path = path or self.settings.watchlist_path()
        payload = json.loads(watchlist_path.read_text(encoding="utf-8"))
        if not isinstance(payload, list):
            raise ValueError("Watchlist JSON must be a list")

        deduped: "OrderedDict[str, dict]" = OrderedDict()
        flat_map: Dict[str, Dict[str, object]] = {}

        for raw in payload:
            if not isinstance(raw, dict):
                continue
            normalized = {k.lower(): v for k, v in raw.items()}
            symbol_key = self.settings.watchlist_symbol_key.lower()
            symbol = normalized.get(symbol_key)
            if not isinstance(symbol, str) or not symbol:
                logger.warning("Skipping entry missing symbol: %s", raw)
                continue
            symbol = symbol.upper()
            if symbol in deduped:
                logger.info("Duplicate symbol %s detected; keeping first entry", symbol)
                continue
            deduped[symbol] = raw

            flat_context: Dict[str, object] = {}
            for key in _FLAT_FIELDS:
                if key in normalized:
                    flat_context[key] = normalized[key]
            features = normalized.get("features")
            if isinstance(features, dict):
                for key in _FEATURE_FIELDS:
                    if key in features:
                        flat_context[key] = features[key]
            flat_map[symbol] = flat_context

        run_ts = time_utils.to_epoch_seconds(time_utils.now_et())
        run_id = self.db.insert_watchlist_run(run_ts, str(watchlist_path), len(deduped))
        self.db.insert_watchlist_items(run_id, ((symbol, payload) for symbol, payload in deduped.items()))

        return run_id, list(deduped.keys()), flat_map


def load_watchlist(settings: AppSettings, db: Database, path: Path | None = None) -> tuple[int, list[str], Dict[str, Dict[str, object]]]:
    loader = WatchlistLoader(settings, db)
    return loader.load(path)
