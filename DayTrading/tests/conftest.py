from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path
from typing import Iterator

import pytest

from intraday.orchestrator import Orchestrator
from intraday.settings import AppSettings
from intraday.storage.db import Database
from intraday.utils.env import load_environment


@pytest.fixture(autouse=True)
def _configure_env(tmp_path: Path) -> Iterator[None]:
    premarket_db = tmp_path / "premarket.db"
    _create_premarket_db(premarket_db)

    env_path = tmp_path / ".env"
    env_path.write_text(
        """
RUN_MODE=once
SIMULATION=true
WATCHLIST_DB_PATH={watchlist_db}
SQLITE_PATH={db}
""".strip().format(watchlist_db=premarket_db, db=tmp_path / "test.db"),
        encoding="utf-8",
    )
    cwd = Path(__file__).resolve().parents[1]
    os.chdir(cwd)
    load_environment(str(env_path))
    yield


@pytest.fixture
def settings() -> AppSettings:
    return AppSettings()


@pytest.fixture
def db(settings: AppSettings) -> Iterator[Database]:
    db = Database(Path(settings.sqlite_path))
    migrations = Path(__file__).resolve().parents[1] / "intraday" / "storage" / "migrations"
    db.run_migrations(migrations)
    yield db
    db.close()


@pytest.fixture
def orchestrator(settings: AppSettings, db: Database) -> Orchestrator:
    return Orchestrator(settings, db)


def _create_premarket_db(path: Path) -> None:
    conn = sqlite3.connect(path)
    cur = conn.cursor()
    cur.executescript(
        """
        CREATE TABLE IF NOT EXISTS full_watchlist (
            run_date TEXT NOT NULL,
            generated_at TEXT NOT NULL,
            symbol TEXT,
            company TEXT,
            sector TEXT,
            industry TEXT,
            exchange TEXT,
            market_cap TEXT,
            pe TEXT,
            price TEXT,
            change_pct TEXT,
            gap_pct TEXT,
            volume TEXT,
            avg_volume_3m TEXT,
            rel_volume TEXT,
            float_shares TEXT,
            short_float_pct TEXT,
            after_hours_change_pct TEXT,
            week52_range TEXT,
            week52_pos TEXT,
            earnings_date TEXT,
            analyst_recom TEXT,
            features_json TEXT,
            score TEXT,
            tier TEXT,
            tags_json TEXT,
            rejection_reasons_json TEXT,
            insider_transactions TEXT,
            institutional_transactions TEXT
        );
        CREATE TABLE IF NOT EXISTS watchlist (
            run_date TEXT NOT NULL,
            generated_at TEXT NOT NULL,
            rank INTEGER,
            symbol TEXT,
            score TEXT,
            tier TEXT,
            gap_pct TEXT,
            rel_volume TEXT,
            tags_json TEXT,
            why TEXT,
            top_feature1 TEXT,
            top_feature2 TEXT,
            top_feature3 TEXT,
            top_feature4 TEXT,
            top_feature5 TEXT
        );
        """
    )

    full_rows = [
        (
            "2024-04-01",
            "2024-04-01T08:30:00Z",
            "AAPL",
            "Apple Inc.",
            "Technology",
            "Consumer Electronics",
            "NASDAQ",
            "2.8T",
            "25.1",
            "182.12",
            "1.3",
            "1.2",
            "1000000",
            "800000",
            "1.5",
            "16.0",
            "0.20",
            "0.15",
            "120-198",
            "0.72",
            "2024-05-02",
            "Buy",
            json.dumps({"relvol": 1.5, "float_band": "mid", "short_float": 0.02}),
            "9.1",
            "A",
            json.dumps(["tech", "momentum"]),
            json.dumps([]),
            "0",
            "0",
        ),
        (
            "2024-04-01",
            "2024-04-01T08:30:00Z",
            "MSFT",
            "Microsoft Corp.",
            "Technology",
            "Software",
            "NASDAQ",
            "2.5T",
            "30.4",
            "310.50",
            "0.5",
            "0.4",
            "900000",
            "700000",
            "1.1",
            "12.0",
            "0.18",
            "0.05",
            "220-345",
            "0.65",
            "2024-04-24",
            "Hold",
            json.dumps({"relvol": 1.1, "news_fresh": True}),
            "8.5",
            "B",
            json.dumps(["software"]),
            json.dumps([]),
            "0",
            "0",
        ),
        (
            "2024-04-01",
            "2024-04-01T08:30:00Z",
            "TSLA",
            "Tesla Inc.",
            "Automotive",
            "Auto Manufacturers",
            "NASDAQ",
            "800B",
            "70.0",
            "250.20",
            "-0.8",
            "-1.0",
            "1500000",
            "900000",
            "2.2",
            "20.0",
            "0.25",
            "-0.40",
            "120-300",
            "0.55",
            "2024-04-17",
            "Sell",
            json.dumps({"relvol": 2.2, "after_hours": -0.5, "analyst": "downgrade"}),
            "7.9",
            "B",
            json.dumps(["ev"]),
            json.dumps([]),
            "0",
            "0",
        ),
    ]

    watchlist_rows = [
        (
            "2024-04-01",
            "2024-04-01T08:30:00Z",
            1,
            "AAPL",
            "9.1",
            "A",
            "1.2",
            "1.5",
            json.dumps(["gap", "relative-volume"]),
            "Strong premarket gap",
            "Gap > 1%",
            "High relvol",
            "Float mid",
            None,
            None,
        ),
        (
            "2024-04-01",
            "2024-04-01T08:30:00Z",
            2,
            "MSFT",
            "8.5",
            "B",
            "0.4",
            "1.1",
            json.dumps(["software"]),
            "Steady continuation",
            "Software strength",
            None,
            None,
            None,
            None,
        ),
        (
            "2024-04-01",
            "2024-04-01T08:30:00Z",
            3,
            "TSLA",
            "7.9",
            "B",
            "-1.0",
            "2.2",
            json.dumps(["ev"]),
            "Watching after downgrade",
            "Analyst downgrade",
            "After hours dip",
            None,
            None,
            None,
        ),
    ]

    cur.executemany(
        """
        INSERT INTO full_watchlist (
            run_date, generated_at, symbol, company, sector, industry, exchange,
            market_cap, pe, price, change_pct, gap_pct, volume, avg_volume_3m, rel_volume,
            float_shares, short_float_pct, after_hours_change_pct, week52_range, week52_pos,
            earnings_date, analyst_recom, features_json, score, tier, tags_json,
            rejection_reasons_json, insider_transactions, institutional_transactions
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        full_rows,
    )

    cur.executemany(
        """
        INSERT INTO watchlist (
            run_date, generated_at, rank, symbol, score, tier, gap_pct, rel_volume,
            tags_json, why, top_feature1, top_feature2, top_feature3, top_feature4, top_feature5
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        watchlist_rows,
    )

    conn.commit()
    conn.close()
