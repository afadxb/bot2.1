from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Dict, Iterable, List

from ..settings import AppSettings
from ..storage import models
from ..storage.db import Database
from ..utils.time import now_et, to_epoch_seconds
from .order_client import OrderClient

logger = logging.getLogger(__name__)


@dataclass
class ManagedPosition:
    trade_id: int
    position: models.Position
    scaled: bool = False


class TradeManager:
    def __init__(self, settings: AppSettings, db: Database, order_client: OrderClient) -> None:
        self.settings = settings
        self.db = db
        self.order_client = order_client
        self.account_equity = 100_000.0
        self.positions: Dict[str, ManagedPosition] = {}

    def execute(self, ranked: Iterable, features: Dict[str, Dict[str, float]]) -> List[int]:
        trade_ids: List[int] = []
        for signal in ranked:
            if signal.gate == "VETO":
                continue
            if signal.symbol in self.positions:
                continue
            row = features.get(signal.symbol)
            if not row:
                continue
            price = float(row.get("c", 0.0))
            atr_value = float(row.get("atr", price * 0.02))
            stop_distance = atr_value * self.settings.atr_mult
            stop_px = max(price - stop_distance, 0.01)
            qty = self._position_size(price, stop_px)
            if qty <= 0:
                continue
            order = self.order_client.submit_order(signal.symbol, "BUY", qty, price)
            if order["status"] != "FILLED":
                continue
            fill_price = order["avg_fill_price"]
            trade = models.Trade(
                symbol=signal.symbol,
                side="BUY",
                qty=qty,
                status="OPEN",
                entry_px=fill_price,
                opened_ts=to_epoch_seconds(now_et()),
                stop_px=stop_px,
                trail_mode=self.settings.stop_mode,
                tags=",".join(signal.reasons[:3]),
            )
            trade_id = self.db.write_trade(trade)
            position = models.Position(
                symbol=signal.symbol,
                qty=qty,
                avg_px=fill_price,
                opened_ts=trade.opened_ts or 0,
                stop_px=stop_px,
                trail_mode=self.settings.stop_mode,
                meta={
                    "scale_target": fill_price * (1 + self.settings.scale1_pct / 100),
                    "final_target": fill_price * (1 + self.settings.target_pct / 100),
                },
            )
            self.db.upsert_position(position)
            self.positions[signal.symbol] = ManagedPosition(trade_id=trade_id, position=position)
            trade_ids.append(trade_id)
            logger.info("Opened position %s size %.0f @ %.2f", signal.symbol, qty, fill_price)
        return trade_ids

    def manage_open_positions(self, features: Dict[str, Dict[str, float]]) -> None:
        for symbol, managed in list(self.positions.items()):
            row = features.get(symbol)
            if not row:
                continue
            price = float(row.get("c", 0.0))
            ema_trail = float(row.get("ema_slow", price))
            position = managed.position
            scale_target = position.meta.get("scale_target", price)
            final_target = position.meta.get("final_target", price)

            if price <= (position.stop_px or 0):
                self._close_position(symbol, price, reason="stop hit")
                continue

            if not managed.scaled and price >= scale_target:
                scaled_qty = position.qty / 2
                self.order_client.submit_order(symbol, "SELL", scaled_qty, price)
                position.qty -= scaled_qty
                managed.scaled = True
                position.stop_px = max(position.stop_px or 0, ema_trail)
                self.db.upsert_position(position)
                self.db.log_metric("scale", to_epoch_seconds(now_et()), scaled_qty, {"symbol": symbol})
                logger.info("Scaled position %s to %.0f shares", symbol, position.qty)
                continue

            if price >= final_target:
                self._close_position(symbol, price, reason="target hit")
                continue

            if ema_trail > (position.stop_px or 0):
                position.stop_px = ema_trail
                self.db.upsert_position(position)

    def flatten_all(self, features: Dict[str, Dict[str, float]]) -> None:
        for symbol in list(self.positions.keys()):
            price = float(features.get(symbol, {}).get("c", 0.0))
            self._close_position(symbol, price, reason="flatten")

    def _position_size(self, price: float, stop_px: float) -> float:
        risk_amount = self.account_equity * (self.settings.risk_pct_per_trade / 100.0)
        risk_per_share = max(price - stop_px, 0.01)
        qty = risk_amount / risk_per_share
        return float(round(qty))

    def _close_position(self, symbol: str, price: float, reason: str) -> None:
        managed = self.positions.pop(symbol, None)
        if not managed:
            return
        position = managed.position
        self.order_client.submit_order(symbol, "SELL", position.qty, price)
        trade_id = managed.trade_id
        pnl = (price - (position.avg_px or 0.0)) * position.qty
        self.db.update_trade(
            trade_id,
            status="CLOSED",
            exit_px=price,
            closed_ts=to_epoch_seconds(now_et()),
            pnl=pnl,
        )
        self.db.execute("DELETE FROM positions WHERE symbol = ?", (symbol,))
        logger.info("Closed position %s (%s) @ %.2f", symbol, reason, price)
