from __future__ import annotations

from intraday.ingestion.watchlist_loader import load_watchlist


def test_watchlist_loader_reads_focus_list(settings, db):
    focus = load_watchlist(settings, db)
    assert focus.symbols == ["AAPL", "MSFT", "TSLA"]
    assert focus.run_date == "2024-04-01"
    assert "AAPL" in focus.context
    assert "relvol" in focus.context["AAPL"]
