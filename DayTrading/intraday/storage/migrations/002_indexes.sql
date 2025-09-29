CREATE INDEX IF NOT EXISTS idx_watchlist_items_run_symbol ON watchlist_items(run_id, symbol);
CREATE INDEX IF NOT EXISTS idx_bars_symbol_tf_ts ON bars(symbol, tf, ts);
CREATE INDEX IF NOT EXISTS idx_news_symbol_ts ON news(symbol, ts);
CREATE INDEX IF NOT EXISTS idx_trades_symbol_status ON trades(symbol, status);
CREATE INDEX IF NOT EXISTS idx_ai_symbol_runts ON ai_provenance(symbol, run_ts);
