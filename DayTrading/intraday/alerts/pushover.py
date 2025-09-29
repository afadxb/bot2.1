from __future__ import annotations

import logging
from typing import Optional

from ..settings import AppSettings

logger = logging.getLogger(__name__)


def send(settings: AppSettings, title: str, message: str) -> None:
    if not settings.pushover_user_key or not settings.pushover_api_token:
        logger.debug("Pushover keys missing; skipping alert %s", title)
        return
    # In real life this would POST to the Pushover API. We log instead.
    logger.info("Pushover: %s - %s", title, message)
