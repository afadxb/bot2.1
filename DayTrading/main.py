from __future__ import annotations

import logging
import sys
import time
from pathlib import Path

from intraday.orchestrator import Orchestrator
from intraday.scheduler import start_scheduler
from intraday.settings import AppSettings
from intraday.storage.db import Database
from intraday.utils.env import load_environment
from intraday.utils.logging import configure_logging


logger = logging.getLogger(__name__)


def setup() -> tuple[AppSettings, Database, Orchestrator]:
    load_environment()
    settings = AppSettings()
    Path("logs").mkdir(exist_ok=True)
    configure_logging(settings.log_cfg)
    db = Database(Path(settings.sqlite_path))
    migrations_dir = Path(__file__).parent / "intraday" / "storage" / "migrations"
    db.run_migrations(migrations_dir)
    orchestrator = Orchestrator(settings, db)
    return settings, db, orchestrator


def main() -> int:
    settings, db, orchestrator = setup()
    try:
        if settings.run_mode == "once":
            orchestrator.run_cycle("5m")
            return 0
        scheduler = start_scheduler(settings, orchestrator)
        logger.info("Running in daemon mode")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("Shutting down daemon")
            scheduler.shutdown()
            return 0
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
