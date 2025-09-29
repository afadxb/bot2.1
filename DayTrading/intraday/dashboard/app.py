from __future__ import annotations

import sqlite3
from pathlib import Path

import streamlit as st

from ..settings import AppSettings


def query_rows(conn: sqlite3.Connection, query: str) -> list[dict]:
    conn.row_factory = sqlite3.Row
    cursor = conn.execute(query)
    return [dict(row) for row in cursor.fetchall()]


def main(settings: AppSettings) -> None:
    st.title("DayTrading Dashboard")
    path = Path(settings.sqlite_path)
    if not path.exists():
        st.warning("Database not found")
        return
    conn = sqlite3.connect(path)

    st.subheader("Ranked Candidates")
    candidates = query_rows(
        conn,
        "SELECT symbol, score, gate, reasons FROM ai_provenance ORDER BY run_ts DESC LIMIT 20",
    )
    if candidates:
        st.table(candidates)
    else:
        st.info("No AI provenance yet")

    st.subheader("Open Positions")
    positions = query_rows(conn, "SELECT symbol, qty, avg_px, stop_px FROM positions")
    if positions:
        st.table(positions)
    else:
        st.info("No open positions")

    st.subheader("Recent Catalysts")
    news = query_rows(conn, "SELECT symbol, source, headline, sentiment, ts FROM news ORDER BY ts DESC LIMIT 20")
    if news:
        st.table(news)
    else:
        st.info("No news available")

    st.subheader("AI Lift")
    metrics = query_rows(conn, "SELECT ts, value FROM metrics WHERE metric='ai_lift' ORDER BY ts DESC LIMIT 5")
    if metrics:
        st.line_chart({"ts": [m["ts"] for m in metrics], "value": [m["value"] for m in metrics]})
    else:
        st.info("No metrics recorded")

    conn.close()


if __name__ == "__main__":
    settings = AppSettings()
    main(settings)
