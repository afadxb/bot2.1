from __future__ import annotations

import json
import logging
import sqlite3
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List

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


@dataclass(slots=True)
class FocusList:
    run_date: str
    generated_at: str
    symbols: List[str]
    context: Dict[str, Dict[str, object]]
    ranks: Dict[str, int | None]


class WatchlistLoader:
    def __init__(self, settings: AppSettings, db: Database) -> None:
        self.settings = settings
        self.db = db

    def load(self, path: Path | None = None) -> FocusList:
        if path is not None:
            logger.info("Loading watchlist from JSON file: %s", path)
            return self._load_from_json(path)

        db_path = self.settings.watchlist_db_path
        if not db_path:
            logger.error(
                "WATCHLIST_DB_PATH is not configured; unable to load watchlist database"
            )
            raise ValueError(
                "WATCHLIST_DB_PATH must be configured when no explicit watchlist path is provided"
            )

        candidate = Path(db_path)
        if not candidate.exists():
            logger.error("Watchlist database not found at path: %s", candidate)
            raise FileNotFoundError(f"Watchlist database not found: {candidate}")
        logger.info("Loading watchlist from SQLite database: %s", candidate)
        return self._load_from_sqlite(candidate)

    def _load_from_json(
        self, path: Path
    ) -> tuple[int, list[str], Dict[str, Dict[str, object]]]:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, list):
            raise ValueError("Watchlist JSON must be a list")

        deduped: "OrderedDict[str, dict]" = OrderedDict()
        flat_map: Dict[str, Dict[str, object]] = {}

        for raw in payload:
            if not isinstance(raw, dict):
                continue
            symbol_key = self.settings.watchlist_symbol_key.lower()
            normalized = {k.lower(): v for k, v in raw.items()}
            symbol = normalized.get(symbol_key)
            if not isinstance(symbol, str) or not symbol:
                logger.warning("Skipping entry missing symbol: %s", raw)
                continue
            symbol = symbol.upper()
            if symbol in deduped:
                logger.info("Duplicate symbol %s detected; keeping first entry", symbol)
                continue
            deduped[symbol] = raw
            flat_map[symbol] = self._build_flat_context(normalized)

        run_date = self.settings.focus_run_date or time_utils.today_et().strftime("%Y-%m-%d")
        return FocusList(
            run_date=run_date,
            generated_at=str(path),
            symbols=list(deduped.keys()),
            context=flat_map,
            ranks={symbol: None for symbol in deduped.keys()},
        )

    def _load_from_sqlite(
        self, db_path: Path
    ) -> FocusList:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        try:
            latest_watchlist = conn.execute(
                "SELECT run_date, generated_at FROM watchlist ORDER BY generated_at DESC LIMIT 1"
            ).fetchone()
            latest_full = conn.execute(
                "SELECT run_date, generated_at FROM full_watchlist ORDER BY generated_at DESC LIMIT 1"
            ).fetchone()

            if latest_watchlist is None and latest_full is None:
                raise ValueError("No watchlist data found in database")

            run_date = self.settings.focus_run_date or (latest_watchlist or latest_full)["run_date"]
            generated_at = (latest_watchlist or latest_full)["generated_at"]

            watch_rows = conn.execute(
                """
                SELECT *
                FROM watchlist
                WHERE run_date = ? AND generated_at = ?
                ORDER BY COALESCE(rank, 1e9), symbol
                """,
                (run_date, generated_at),
            ).fetchall()

            watch_map: Dict[str, sqlite3.Row] = {}
            symbol_order: List[str] = []
            for row in watch_rows:
                symbol = row["symbol"]
                if not symbol:
                    continue
                symbol = symbol.upper()
                if symbol not in symbol_order:
                    symbol_order.append(symbol)
                watch_map[symbol] = row

            full_generated_at = generated_at
            if latest_full is not None:
                full_generated_at = latest_full["generated_at"]

            full_rows = conn.execute(
                """
                SELECT *
                FROM full_watchlist
                WHERE run_date = ? AND generated_at = ?
                """,
                (run_date, full_generated_at),
            ).fetchall()

            if not full_rows and latest_full is not None:
                full_rows = conn.execute(
                    "SELECT * FROM full_watchlist WHERE run_date = ? ORDER BY generated_at DESC",
                    (run_date,),
                ).fetchall()

            full_map: Dict[str, dict] = {}
            for row in full_rows:
                symbol = row["symbol"]
                if not symbol:
                    continue
                symbol = symbol.upper()
                full_map[symbol] = self._row_to_payload(
                    row,
                    {
                        "features_json": "features",
                        "tags_json": "tags",
                        "rejection_reasons_json": "rejection_reasons",
                    },
                )

            if not symbol_order:
                scored_symbols: List[tuple[float, str]] = []
                for symbol, payload in full_map.items():
                    score = payload.get("score")
                    try:
                        score_value = float(score)
                    except (TypeError, ValueError):
                        score_value = float("-inf")
                    scored_symbols.append((score_value, symbol))
                scored_symbols.sort(key=lambda item: (-item[0], item[1]))
                symbol_order = [symbol for _, symbol in scored_symbols]
                if not symbol_order:
                    symbol_order = sorted(full_map.keys())

            remaining_symbols = [
                symbol for symbol in full_map.keys() if symbol not in symbol_order
            ]
            if remaining_symbols:
                scored_remaining: List[tuple[float, str]] = []
                for symbol in remaining_symbols:
                    score = full_map[symbol].get("score")
                    try:
                        score_value = float(score)
                    except (TypeError, ValueError):
                        score_value = float("-inf")
                    scored_remaining.append((score_value, symbol))
                scored_remaining.sort(key=lambda item: (-item[0], item[1]))
                symbol_order.extend(symbol for _, symbol in scored_remaining)

            deduped: "OrderedDict[str, dict]" = OrderedDict()
            flat_map: Dict[str, Dict[str, object]] = {}
            rank_map: Dict[str, int | None] = {}

            for symbol in symbol_order:
                payload: dict = {}
                if symbol in full_map:
                    payload.update(full_map[symbol])
                if symbol in watch_map:
                    payload.update(
                        self._row_to_payload(
                            watch_map[symbol],
                            {
                                "tags_json": "tags",
                            },
                        )
                    )
                payload.setdefault("symbol", symbol)
                deduped[symbol] = payload
                flat_map[symbol] = self._build_flat_context(
                    {k.lower(): v for k, v in payload.items()}
                )
                rank_map[symbol] = _safe_int(payload.get("rank"))

            return FocusList(
                run_date=run_date,
                generated_at=str(generated_at),
                symbols=list(deduped.keys()),
                context=flat_map,
                ranks=rank_map,
            )
        finally:
            conn.close()

    def _row_to_payload(self, row: sqlite3.Row, json_fields: Dict[str, str]) -> dict:
        payload: dict = {}
        for key in row.keys():
            alias = json_fields.get(key)
            value = row[key]
            if alias:
                parsed = self._parse_json_field(value)
                if parsed is not None:
                    payload[alias] = parsed
            else:
                payload[key] = value
        return payload

    def _build_flat_context(self, normalized: Dict[str, object]) -> Dict[str, object]:
        flat_context: Dict[str, object] = {}
        for key in _FLAT_FIELDS:
            if key in normalized:
                flat_context[key] = normalized[key]
        features = normalized.get("features")
        if isinstance(features, dict):
            for key in _FEATURE_FIELDS:
                if key in features:
                    flat_context[key] = features[key]
        return flat_context

    def _parse_json_field(self, value: str | None) -> object | None:
        if value is None:
            return None
        if isinstance(value, (dict, list)):
            return value
        if isinstance(value, str):
            text = value.strip()
            if not text:
                return None
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                logger.warning("Failed to decode JSON field: %s", value)
                return text
        return value

def load_watchlist(settings: AppSettings, db: Database, path: Path | None = None) -> FocusList:
    loader = WatchlistLoader(settings, db)
    return loader.load(path)


def _safe_int(value: object) -> int | None:
    try:
        if value is None:
            return None
        return int(value)
    except (TypeError, ValueError):
        return None
