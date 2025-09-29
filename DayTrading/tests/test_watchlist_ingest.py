from __future__ import annotations

from intraday.ingestion.watchlist_loader import load_watchlist


def test_watchlist_loader_inserts(settings, db):
    run_id, symbols, context = load_watchlist(settings, db)
    assert run_id > 0
    assert symbols == ["AAPL", "MSFT", "TSLA"]
    assert "AAPL" in context
    assert "relvol" in context["AAPL"]

    cur = db.execute("SELECT COUNT(*) as c FROM watchlist_items")
    assert cur.fetchone()["c"] == 3

    run_row = db.execute("SELECT row_count FROM watchlist_runs WHERE id = ?", (run_id,)).fetchone()
    assert run_row["row_count"] == 3
