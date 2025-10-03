from __future__ import annotations

import logging
from typing import Iterable

from ..settings import AppSettings
from ..storage import models
from ..storage.db import Database

logger = logging.getLogger(__name__)


class OrderClient:
    def __init__(self, settings: AppSettings, db: Database) -> None:
        self.settings = settings
        self.db = db

    def submit_order(self, symbol: str, side: str, qty: float, limit_price: float) -> dict:
        """Simulate an immediate-or-cancel order fill."""

        if not self.settings.is_simulation:
            raise RuntimeError("Live order submission not implemented")

        slippage = 0.001 if side.upper() == "BUY" else -0.001
        fill_price = limit_price * (1 + slippage)
        logger.info("%s order fill for %s @ %.2f (limit %.2f)", side, symbol, fill_price, limit_price)
        return {"status": "FILLED", "avg_fill_price": fill_price}
