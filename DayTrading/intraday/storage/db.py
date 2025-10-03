from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Iterable, Mapping, Sequence

from . import models
from .schema import PHASE2_SCHEMA


class Database:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys=ON;")
        self._lock = Lock()

    def close(self) -> None:
        with self._lock:
            self.conn.close()

    # Migration helpers -------------------------------------------------
    def run_migrations(self, _migrations_dir: Path | None = None) -> None:
        """Apply the Phase 2 schema to the configured database."""

        with self._lock:
            self.conn.executescript(PHASE2_SCHEMA)

    # Generic helpers ---------------------------------------------------
    def execute(self, sql: str, params: Sequence | None = None) -> sqlite3.Cursor:
        with self._lock:
            cur = self.conn.cursor()
            cur.execute(sql, params or [])
            self.conn.commit()
            return cur

    def executemany(self, sql: str, seq: Iterable[Sequence]) -> None:
        with self._lock:
            cur = self.conn.cursor()
            cur.executemany(sql, seq)
            self.conn.commit()

    # Phase 2 persistence helpers --------------------------------------
    def write_intraday_bars(
        self,
        bars: Iterable[models.Bar],
        timeframe: str,
        source: str,
        run_date: str | None,
    ) -> None:
        rows = [
            (
                bar.symbol,
                timeframe,
                self._epoch_to_iso(bar.ts),
                bar.o,
                bar.h,
                bar.l,
                bar.c,
                bar.v,
                bar.vwap,
                source,
                run_date,
            )
            for bar in bars
        ]
        if not rows:
            return
        self.executemany(
            """
            INSERT OR REPLACE INTO bars_intraday
            (symbol, timeframe, ts, open, high, low, close, volume, vwap, source, run_date)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )

    def write_catalysts(self, items: Iterable[models.Catalyst]) -> None:
        rows = [
            (
                item.symbol,
                self._epoch_to_iso(item.ts),
                item.kind,
                item.title,
                item.source,
                item.url,
                json.dumps(item.raw_json or {}),
                item.dedupe_key,
                item.sentiment_score,
                item.importance,
            )
            for item in items
        ]
        if not rows:
            return
        self.executemany(
            """
            INSERT OR REPLACE INTO catalysts
            (symbol, ts, kind, title, source, url, raw_json, dedupe_key, sentiment_score, importance)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )

    def write_intraday_features(self, rows: Iterable[models.IntradayFeatureRow]) -> None:
        payload = [
            (
                row.symbol,
                self._epoch_to_iso(row.ts),
                row.timeframe,
                json.dumps(row.features),
            )
            for row in rows
        ]
        if not payload:
            return
        self.executemany(
            """
            INSERT OR REPLACE INTO intraday_features(symbol, ts, timeframe, features_json)
            VALUES (?, ?, ?, ?)
            """,
            payload,
        )

    def write_signals(self, records: Iterable[models.SignalRecord]) -> None:
        payload = [
            (
                row.symbol,
                self._epoch_to_iso(row.ts),
                row.timeframe,
                row.base_score,
                row.ai_adjustment,
                row.final_score,
                row.decision,
                row.reason_tags,
                json.dumps(row.details),
                row.phase1_rank,
                row.run_date,
            )
            for row in records
        ]
        if not payload:
            return
        self.executemany(
            """
            INSERT INTO signals
            (symbol, ts, timeframe, base_score, ai_adjustment, final_score, decision, reason_tags, details_json, phase1_rank, run_date)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(symbol, ts, timeframe) DO UPDATE SET
              base_score=excluded.base_score,
              ai_adjustment=excluded.ai_adjustment,
              final_score=excluded.final_score,
              decision=excluded.decision,
              reason_tags=excluded.reason_tags,
              details_json=excluded.details_json,
              phase1_rank=excluded.phase1_rank,
              run_date=excluded.run_date
            """,
            payload,
        )

    def write_ai_provenance(self, records: Iterable[models.AIProvenanceRecord]) -> None:
        payload = [
            (
                row.symbol,
                self._epoch_to_iso(row.ts),
                row.model_name,
                json.dumps(row.inputs or {}),
                json.dumps(row.outputs or {}),
                row.delta_applied,
                row.notes,
            )
            for row in records
        ]
        if not payload:
            return
        self.executemany(
            """
            INSERT INTO ai_provenance(symbol, ts, model_name, inputs_json, outputs_json, delta_applied, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            payload,
        )

    def insert_order(self, order: models.Order) -> int:
        cur = self.execute(
            """
            INSERT INTO orders
            (client_order_id, symbol, side, order_type, qty, limit_price, stop_price, tif, status, placed_ts, updated_ts, meta_json, signal_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                order.client_order_id,
                order.symbol,
                order.side,
                order.order_type,
                order.qty,
                order.limit_price,
                order.stop_price,
                order.tif,
                order.status,
                self._epoch_to_iso(order.placed_ts),
                self._epoch_to_iso(order.updated_ts) if order.updated_ts else None,
                json.dumps(order.meta or {}),
                order.signal_id,
            ),
        )
        return int(cur.lastrowid)

    def insert_fill(self, fill: models.Fill) -> int:
        cur = self.execute(
            """
            INSERT INTO fills(order_id, fill_ts, fill_price, fill_qty, liquidity, venue)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                fill.order_id,
                self._epoch_to_iso(fill.fill_ts),
                fill.fill_price,
                fill.fill_qty,
                fill.liquidity,
                fill.venue,
            ),
        )
        return int(cur.lastrowid)

    def upsert_position(self, position: models.Position) -> None:
        self.execute(
            """
            INSERT INTO positions(symbol, avg_price, qty, opened_ts, last_update_ts, meta_json)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(symbol) DO UPDATE SET
              avg_price=excluded.avg_price,
              qty=excluded.qty,
              opened_ts=excluded.opened_ts,
              last_update_ts=excluded.last_update_ts,
              meta_json=excluded.meta_json
            """,
            (
                position.symbol,
                position.avg_price,
                position.qty,
                self._epoch_to_iso(position.opened_ts),
                self._epoch_to_iso(position.last_update_ts),
                json.dumps(position.meta or {}),
            ),
        )

    def delete_position(self, symbol: str) -> None:
        self.execute("DELETE FROM positions WHERE symbol = ?", (symbol,))

    def insert_trade_journal(self, entry: models.TradeJournalEntry) -> int:
        cur = self.execute(
            """
            INSERT INTO trade_journal(
              symbol, open_ts, close_ts, side, entry_price, exit_price, qty, pnl, pnl_pct,
              max_fav_excursion, max_adv_excursion, reason_open, reason_close, tags, signal_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                entry.symbol,
                self._epoch_to_iso(entry.open_ts),
                self._epoch_to_iso(entry.close_ts) if entry.close_ts else None,
                entry.side,
                entry.entry_price,
                entry.exit_price,
                entry.qty,
                entry.pnl,
                None,
                None,
                None,
                entry.reason_open,
                entry.reason_close,
                entry.tags,
                entry.signal_id,
            ),
        )
        return int(cur.lastrowid)

    def update_trade_journal(self, entry_id: int, **fields: object) -> None:
        if not fields:
            return
        updates = []
        params: list[object] = []
        for key, value in fields.items():
            updates.append(f"{key} = ?")
            if key.endswith("_ts") and isinstance(value, int):
                params.append(self._epoch_to_iso(value))
            else:
                params.append(value)
        params.append(entry_id)
        sql = f"UPDATE trade_journal SET {', '.join(updates)} WHERE id = ?"
        self.execute(sql, params)

    def insert_intraday_cycle_run(self, cycle: models.IntradayCycleRun) -> int:
        cur = self.execute(
            """
            INSERT INTO intraday_cycle_run(
              run_started_ts, run_finished_ts, watchlist_count, evaluated_count,
              placed_orders, errors_count, timings_json, notes_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                self._epoch_to_iso(cycle.run_started_ts),
                self._epoch_to_iso(cycle.run_finished_ts) if cycle.run_finished_ts else None,
                cycle.watchlist_count,
                cycle.evaluated_count,
                cycle.placed_orders,
                cycle.errors_count,
                json.dumps(cycle.timings or {}),
                json.dumps(cycle.notes or {}),
            ),
        )
        return int(cur.lastrowid)

    def update_intraday_cycle_run(self, cycle_id: int, **fields: object) -> None:
        if not fields:
            return
        updates = []
        params: list[object] = []
        for key, value in fields.items():
            updates.append(f"{key} = ?")
            if key.endswith("_ts") and isinstance(value, int):
                params.append(self._epoch_to_iso(value))
            elif key.endswith("_json") and isinstance(value, Mapping):
                params.append(json.dumps(value))
            else:
                params.append(value)
        params.append(cycle_id)
        sql = f"UPDATE intraday_cycle_run SET {', '.join(updates)} WHERE id = ?"
        self.execute(sql, params)

    def insert_app_event(
        self,
        ts: int,
        level: str,
        scope: str | None,
        message: str,
        context: Mapping[str, object] | None = None,
    ) -> None:
        self.execute(
            "INSERT INTO app_events(ts, level, scope, message, context_json) VALUES (?, ?, ?, ?, ?)",
            (
                self._epoch_to_iso(ts),
                level,
                scope,
                message,
                json.dumps(context or {}),
            ),
        )

    # Utility helpers ---------------------------------------------------
    @staticmethod
    def _epoch_to_iso(ts: int) -> str:
        dt = datetime.fromtimestamp(ts, tz=timezone.utc)
        return dt.replace(tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")
