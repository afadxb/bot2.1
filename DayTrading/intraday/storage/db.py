from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Iterable, Sequence

from ..storage import models


class Database:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row

    def close(self) -> None:
        self.conn.close()

    # Migration helpers -------------------------------------------------
    def run_migrations(self, migrations_dir: Path) -> None:
        files = sorted(p for p in migrations_dir.glob("*.sql"))
        cursor = self.conn.cursor()
        for file in files:
            with file.open("r", encoding="utf-8") as fh:
                cursor.executescript(fh.read())
        self.conn.commit()

    # Generic helpers ---------------------------------------------------
    def execute(self, sql: str, params: Sequence | None = None) -> sqlite3.Cursor:
        cur = self.conn.cursor()
        cur.execute(sql, params or [])
        self.conn.commit()
        return cur

    def executemany(self, sql: str, seq: Iterable[Sequence]) -> None:
        cur = self.conn.cursor()
        cur.executemany(sql, seq)
        self.conn.commit()

    # Domain operations -------------------------------------------------
    def insert_watchlist_run(self, run_ts: int, source_path: str, row_count: int) -> int:
        cur = self.execute(
            "INSERT INTO watchlist_runs(run_ts, source_path, row_count) VALUES (?, ?, ?)",
            (run_ts, source_path, row_count),
        )
        return int(cur.lastrowid)

    def insert_watchlist_items(self, run_id: int, items: Iterable[tuple[str, dict]]) -> None:
        payloads = [(run_id, symbol, json.dumps(payload)) for symbol, payload in items]
        self.executemany(
            "INSERT OR IGNORE INTO watchlist_items(run_id, symbol, payload) VALUES (?, ?, ?)",
            payloads,
        )

    def write_bars(self, bars: Iterable[models.Bar]) -> None:
        rows = [
            (bar.symbol, bar.tf, bar.ts, bar.o, bar.h, bar.l, bar.c, bar.v)
            for bar in bars
        ]
        self.executemany(
            "INSERT OR REPLACE INTO bars(symbol, tf, ts, o, h, l, c, v) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            rows,
        )

    def write_news(self, items: Iterable[models.NewsItem]) -> None:
        rows = [
            (
                item.symbol,
                item.source,
                item.headline,
                item.url,
                item.ts,
                item.sentiment,
                json.dumps(item.meta or {}),
            )
            for item in items
        ]
        self.executemany(
            "INSERT OR REPLACE INTO news(symbol, source, headline, url, ts, sentiment, meta) VALUES (?, ?, ?, ?, ?, ?, ?)",
            rows,
        )

    def write_trade(self, trade: models.Trade) -> int:
        cur = self.execute(
            """
            INSERT INTO trades(symbol, side, qty, entry_px, exit_px, status, opened_ts, closed_ts, stop_px, trail_mode, tags, pnl, meta)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                trade.symbol,
                trade.side,
                trade.qty,
                trade.entry_px,
                trade.exit_px,
                trade.status,
                trade.opened_ts,
                trade.closed_ts,
                trade.stop_px,
                trade.trail_mode,
                trade.tags,
                trade.pnl,
                json.dumps(trade.meta or {}),
            ),
        )
        return int(cur.lastrowid)

    def update_trade(self, trade_id: int, **fields) -> None:
        if not fields:
            return
        columns = ", ".join(f"{key} = ?" for key in fields)
        params = list(fields.values())
        params.append(trade_id)
        self.execute(f"UPDATE trades SET {columns} WHERE id = ?", params)

    def upsert_position(self, position: models.Position) -> None:
        self.execute(
            """
            INSERT INTO positions(symbol, qty, avg_px, opened_ts, stop_px, trail_mode, meta)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(symbol) DO UPDATE SET
              qty=excluded.qty,
              avg_px=excluded.avg_px,
              opened_ts=excluded.opened_ts,
              stop_px=excluded.stop_px,
              trail_mode=excluded.trail_mode,
              meta=excluded.meta
            """,
            (
                position.symbol,
                position.qty,
                position.avg_px,
                position.opened_ts,
                position.stop_px,
                position.trail_mode,
                json.dumps(position.meta or {}),
            ),
        )

    def log_metric(self, metric: str, ts: int, value: float, labels: dict | None = None) -> None:
        self.execute(
            "INSERT INTO metrics(metric, ts, value, labels) VALUES (?, ?, ?, ?)",
            (metric, ts, value, json.dumps(labels or {})),
        )
