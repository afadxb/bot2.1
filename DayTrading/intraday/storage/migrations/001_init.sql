PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS watchlist_runs (
  id INTEGER PRIMARY KEY,
  run_ts INTEGER NOT NULL,
  source_path TEXT NOT NULL,
  row_count INTEGER NOT NULL,
  notes TEXT
);

CREATE TABLE IF NOT EXISTS watchlist_items (
  id INTEGER PRIMARY KEY,
  run_id INTEGER NOT NULL REFERENCES watchlist_runs(id) ON DELETE CASCADE,
  symbol TEXT NOT NULL,
  payload JSON,
  UNIQUE(run_id, symbol)
);

CREATE TABLE IF NOT EXISTS bars (
  id INTEGER PRIMARY KEY,
  symbol TEXT NOT NULL,
  tf TEXT NOT NULL,
  ts INTEGER NOT NULL,
  o REAL, h REAL, l REAL, c REAL, v REAL,
  UNIQUE(symbol, tf, ts)
);

CREATE TABLE IF NOT EXISTS news (
  id INTEGER PRIMARY KEY,
  symbol TEXT NOT NULL,
  source TEXT NOT NULL,
  headline TEXT,
  url TEXT,
  ts INTEGER NOT NULL,
  sentiment REAL,
  meta JSON
);

CREATE TABLE IF NOT EXISTS trades (
  id INTEGER PRIMARY KEY,
  symbol TEXT NOT NULL,
  side TEXT NOT NULL,
  qty REAL NOT NULL,
  entry_px REAL,
  exit_px REAL,
  status TEXT NOT NULL,
  opened_ts INTEGER,
  closed_ts INTEGER,
  stop_px REAL,
  trail_mode TEXT,
  tags TEXT,
  pnl REAL,
  meta JSON
);

CREATE TABLE IF NOT EXISTS positions (
  id INTEGER PRIMARY KEY,
  symbol TEXT UNIQUE,
  qty REAL NOT NULL,
  avg_px REAL NOT NULL,
  opened_ts INTEGER,
  stop_px REAL,
  trail_mode TEXT,
  meta JSON
);

CREATE TABLE IF NOT EXISTS ai_provenance (
  id INTEGER PRIMARY KEY,
  symbol TEXT NOT NULL,
  run_ts INTEGER NOT NULL,
  raw_text TEXT,
  model TEXT,
  score REAL,
  gate TEXT,
  reasons JSON
);

CREATE TABLE IF NOT EXISTS metrics (
  id INTEGER PRIMARY KEY,
  metric TEXT NOT NULL,
  ts INTEGER NOT NULL,
  value REAL,
  labels JSON
);

CREATE TABLE IF NOT EXISTS orchestrator_state (
  id INTEGER PRIMARY KEY,
  trade_count INTEGER DEFAULT 0,
  dd_start_equity REAL,
  dd_low_equity REAL,
  session_date TEXT
);
