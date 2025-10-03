"""Schema upgrade script to apply Phase 2 tables and views to ``premarket.db``.

The Phase 2 upgrade introduces the following data structures while preserving the
Phase 1 outputs (``full_watchlist``, ``top_n``, ``watchlist``, ``run_summary``)
that downstream tools already rely on:

- ``bars_intraday``: Stores intraday OHLCV bars and derived metrics for a
  symbol/timeframe pair so that live scoring has a canonical price history.
- ``catalysts``: Tracks qualitative catalysts such as news headlines along with
  metadata, sentiment, and dedupe keys used during intraday decisioning.
- ``intraday_features``: Persists serialized feature vectors generated during
  intraday analysis runs; these extend the engineered ``features_json`` that
  Phase 1 emits in ``full_watchlist`` so AI models can rescore symbols quickly.
- ``signals``: Records algorithmic trade signals, including AI adjustments,
  provenance metadata, and links back to the Phase 1 ranking (``phase1_rank``).
- ``ai_provenance``: Captures supporting model I/O that influenced
  AI-driven adjustments to signals for compliance and debugging.
- ``orders``: Maintains broker order submissions and status changes tied back
  to originating signals.
- ``fills``: Logs order execution fills received from the broker with
  price/venue information.
- ``positions``: Represents the current live position book including quantity
  and cost basis per symbol.
- ``trade_journal``: Archives completed or in-flight trades for post-trade
  analysis, linking back to ``signals`` to maintain a full audit trail.
- ``intraday_cycle_run``: Summarizes each intraday automation cycle with
  timing diagnostics so the ``run_summary`` audit trail stays consistent across
  phases.
- ``app_events``: Stores structured application logs for observability and
  troubleshooting during automated runs.
- ``v_focus_symbols``: View exposing the current focus list by selecting
  ranked symbols from ``watchlist``/``top_n`` and annotating them with the most
  recent Phase 2 signal metadata.
- ``v_latest_bars``: View surfacing the freshest intraday bar per
  symbol/timeframe combination for quick lookups.
"""

from __future__ import annotations

import sqlite3

from DayTrading.intraday.storage.schema import PHASE2_SCHEMA

def upgrade_schema(db_path: str = "premarket.db") -> None:
    """Apply the Phase 2 schema extension to the specified SQLite database.

    The upgrade enables foreign key enforcement and executes the Phase 2 DDL
    within a transaction so it can safely run multiple times without disrupting
    Phase 1 tables or views.
    """
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("PRAGMA foreign_keys=ON;")
        conn.executescript(PHASE2_SCHEMA)
        conn.commit()
    finally:
        conn.close()
    print("Phase 2 schema applied successfully to", db_path)


if __name__ == "__main__":
    upgrade_schema()

    # --- Usage examples ---
    with sqlite3.connect("premarket.db") as conn:
        conn.execute("PRAGMA foreign_keys=ON;")
        cur = conn.cursor()

        # Insert a new 5m bar sourced from the live market feed.
        cur.execute(
            """
            INSERT OR REPLACE INTO bars_intraday
            (symbol,timeframe,ts,open,high,low,close,volume,vwap)
            VALUES (?,?,?,?,?,?,?,?,?)
            """,
            ("NVDA", "5m", "2025-10-03T14:30:00Z", 450.0, 455.0, 448.0, 454.5, 1_200_000, 452.0),
        )

        # Insert a catalyst headline that will influence the focus ranking.
        cur.execute(
            """
            INSERT INTO catalysts (symbol,ts,kind,title,source,url,sentiment_score,importance,dedupe_key)
            VALUES (?,?,?,?,?,?,?,?,?)
            """,
            (
                "NVDA",
                "2025-10-03T14:35:00Z",
                "news",
                "NVIDIA beats earnings",
                "Yahoo",
                "https://finance.yahoo.com/nvda",
                0.8,
                0.9,
                "nvda_beat_20251003",
            ),
        )

        # Insert a signal with an AI adjustment sourced from intraday features.
        cur.execute(
            """
            INSERT OR REPLACE INTO signals
            (symbol,ts,timeframe,base_score,ai_adjustment,final_score,decision,reason_tags,details_json)
            VALUES (?,?,?,?,?,?,?,?,?)
            """,
            (
                "NVDA",
                "2025-10-03T14:40:00Z",
                "5m",
                0.65,
                0.1,
                0.75,
                "enter_long",
                "EMA_cross|Volume_spike",
                '{"feature_snapshot_id": 123}',
            ),
        )

        # Query today's focus list sourced from the Phase 1 watchlist/top_n tables.
        try:
            rows = list(cur.execute("SELECT * FROM v_focus_symbols WHERE run_date=date('now');"))
        except sqlite3.OperationalError as exc:
            print("Focus list unavailable until Phase 1 tables are populated:", exc)
        else:
            for row in rows:
                print(row)
