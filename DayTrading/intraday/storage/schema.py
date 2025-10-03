"""Shared Phase 2 schema definition for runtime upgrades."""

from __future__ import annotations

PHASE2_SCHEMA = """
BEGIN IMMEDIATE;
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS bars_intraday (
  symbol TEXT NOT NULL,
  timeframe TEXT NOT NULL,
  ts TEXT NOT NULL,
  open REAL NOT NULL,
  high REAL NOT NULL,
  low REAL NOT NULL,
  close REAL NOT NULL,
  volume REAL NOT NULL,
  vwap REAL,
  source TEXT DEFAULT 'IBKR',
  run_date TEXT,
  PRIMARY KEY (symbol, timeframe, ts)
);

CREATE INDEX IF NOT EXISTS idx_bars_intraday_symbol_tf_ts
  ON bars_intraday(symbol, timeframe, ts);

CREATE TABLE IF NOT EXISTS catalysts (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  symbol TEXT NOT NULL,
  ts TEXT NOT NULL,
  kind TEXT NOT NULL,
  title TEXT,
  source TEXT,
  url TEXT,
  raw_json TEXT,
  dedupe_key TEXT,
  sentiment_score REAL,
  importance REAL,
  UNIQUE(symbol, ts, dedupe_key)
);

CREATE INDEX IF NOT EXISTS idx_catalysts_symbol_ts
  ON catalysts(symbol, ts DESC);

CREATE TABLE IF NOT EXISTS intraday_features (
  symbol TEXT NOT NULL,
  ts TEXT NOT NULL,
  timeframe TEXT NOT NULL,
  features_json TEXT NOT NULL,
  PRIMARY KEY (symbol, ts, timeframe)
);

CREATE INDEX IF NOT EXISTS idx_intraday_features_symbol_ts
  ON intraday_features(symbol, ts);

CREATE TABLE IF NOT EXISTS signals (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  symbol TEXT NOT NULL,
  ts TEXT NOT NULL,
  timeframe TEXT NOT NULL,
  base_score REAL NOT NULL,
  ai_adjustment REAL DEFAULT 0.0,
  final_score REAL NOT NULL,
  decision TEXT NOT NULL,
  reason_tags TEXT,
  details_json TEXT,
  phase1_rank INTEGER,
  run_date TEXT,
  UNIQUE(symbol, ts, timeframe)
);

CREATE INDEX IF NOT EXISTS idx_signals_rank_score
  ON signals(final_score DESC, ts DESC);

CREATE TABLE IF NOT EXISTS ai_provenance (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  symbol TEXT NOT NULL,
  ts TEXT NOT NULL,
  model_name TEXT NOT NULL,
  inputs_json TEXT,
  outputs_json TEXT,
  delta_applied REAL,
  notes TEXT
);

CREATE INDEX IF NOT EXISTS idx_ai_prov_symbol_ts
  ON ai_provenance(symbol, ts);

CREATE TABLE IF NOT EXISTS orders (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  client_order_id TEXT UNIQUE,
  symbol TEXT NOT NULL,
  side TEXT NOT NULL CHECK (side IN ('buy','sell')),
  order_type TEXT NOT NULL CHECK (order_type IN ('limit','market','stop','stop_limit')),
  qty REAL NOT NULL,
  limit_price REAL,
  stop_price REAL,
  tif TEXT DEFAULT 'DAY',
  status TEXT NOT NULL DEFAULT 'new'
         CHECK (status IN ('new','submitted','partially_filled','filled','canceled','rejected')),
  placed_ts TEXT NOT NULL,
  updated_ts TEXT,
  meta_json TEXT,
  signal_id INTEGER,
  FOREIGN KEY (signal_id) REFERENCES signals(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_orders_symbol_status
  ON orders(symbol, status);

CREATE TABLE IF NOT EXISTS fills (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  order_id INTEGER NOT NULL,
  fill_ts TEXT NOT NULL,
  fill_price REAL NOT NULL,
  fill_qty REAL NOT NULL,
  liquidity TEXT,
  venue TEXT,
  FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_fills_order ON fills(order_id);

CREATE TABLE IF NOT EXISTS positions (
  symbol TEXT PRIMARY KEY,
  avg_price REAL NOT NULL,
  qty REAL NOT NULL,
  opened_ts TEXT NOT NULL,
  last_update_ts TEXT NOT NULL,
  meta_json TEXT
);

CREATE TABLE IF NOT EXISTS trade_journal (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  symbol TEXT NOT NULL,
  open_ts TEXT NOT NULL,
  close_ts TEXT,
  side TEXT CHECK (side IN ('long','short')),
  entry_price REAL,
  exit_price REAL,
  qty REAL,
  pnl REAL,
  pnl_pct REAL,
  max_fav_excursion REAL,
  max_adv_excursion REAL,
  reason_open TEXT,
  reason_close TEXT,
  tags TEXT,
  signal_id INTEGER,
  FOREIGN KEY (signal_id) REFERENCES signals(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_trades_symbol_time
  ON trade_journal(symbol, open_ts);

CREATE TABLE IF NOT EXISTS intraday_cycle_run (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  run_started_ts TEXT NOT NULL,
  run_finished_ts TEXT,
  watchlist_count INTEGER,
  evaluated_count INTEGER,
  placed_orders INTEGER,
  errors_count INTEGER,
  timings_json TEXT,
  notes_json TEXT
);

CREATE TABLE IF NOT EXISTS app_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts TEXT NOT NULL,
  level TEXT NOT NULL CHECK (level IN ('DEBUG','INFO','WARN','ERROR')),
  scope TEXT,
  message TEXT NOT NULL,
  context_json TEXT
);

CREATE INDEX IF NOT EXISTS idx_app_events_ts ON app_events(ts);

CREATE VIEW IF NOT EXISTS v_focus_symbols AS
SELECT
  w.run_date,
  w.symbol,
  w.rank,
  w.score AS premarket_score,
  w.tier,
  (SELECT s.ts FROM signals s WHERE s.symbol = w.symbol ORDER BY s.ts DESC LIMIT 1) AS last_signal_ts,
  (SELECT s.final_score FROM signals s WHERE s.symbol = w.symbol ORDER BY s.ts DESC LIMIT 1) AS last_final_score,
  (SELECT s.decision FROM signals s WHERE s.symbol = w.symbol ORDER BY s.ts DESC LIMIT 1) AS last_decision
FROM watchlist w;

CREATE VIEW IF NOT EXISTS v_latest_bars AS
SELECT b.symbol, b.timeframe, b.ts, b.open, b.high, b.low, b.close, b.volume, b.vwap
FROM bars_intraday b
JOIN (
  SELECT symbol, timeframe, MAX(ts) AS max_ts
  FROM bars_intraday
  GROUP BY symbol, timeframe
) t ON b.symbol = t.symbol AND b.timeframe = t.timeframe AND b.ts = t.max_ts;

COMMIT;
"""

