from __future__ import annotations

import os
from pathlib import Path
from typing import Iterator

import pytest

from intraday.orchestrator import Orchestrator
from intraday.settings import AppSettings
from intraday.storage.db import Database
from intraday.utils.env import load_environment


@pytest.fixture(autouse=True)
def _configure_env(tmp_path: Path) -> Iterator[None]:
    env_path = tmp_path / ".env"
    env_path.write_text(
        """
RUN_MODE=once
SIMULATION=true
WATCHLIST_FILE=samples/watchlist_minimal.json
SQLITE_PATH={db}
""".strip().format(db=tmp_path / "test.db"),
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
