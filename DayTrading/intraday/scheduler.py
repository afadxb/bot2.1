from __future__ import annotations

import logging

from apscheduler.schedulers.background import BackgroundScheduler

from .orchestrator import Orchestrator
from .settings import AppSettings

logger = logging.getLogger(__name__)


def start_scheduler(settings: AppSettings, orchestrator: Orchestrator) -> BackgroundScheduler:
    scheduler = BackgroundScheduler(timezone=settings.tz)
    scheduler.add_job(orchestrator.run_cycle, "interval", minutes=5, args=["5m"], id="cycle_5m")
    scheduler.add_job(orchestrator.run_cycle, "interval", minutes=15, args=["15m"], id="cycle_15m")
    scheduler.add_job(orchestrator.flatten_guard, "cron", hour=int(settings.flatten_et.split(":")[0]), minute=int(settings.flatten_et.split(":")[1]), id="flatten")
    scheduler.start()
    logger.info("Scheduler started with 5m/15m jobs")
    return scheduler
