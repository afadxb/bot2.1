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

    def execute(
        self,
        ranked: Iterable,
        features: Dict[str, Dict[str, object]],
        run_date: str,
    ) -> List[int]:
        trade_ids: List[int] = []
        for signal in ranked:
            if getattr(signal, "decision", "observe") != "enter_long":
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

            order_response = self.order_client.submit_order(signal.symbol, "BUY", qty, price)
            if order_response["status"] != "FILLED":
                continue

            entry_ts = to_epoch_seconds(now_et())
            fill_price = float(order_response["avg_fill_price"])
            order = models.Order(
                symbol=signal.symbol,
                side="buy",
                order_type="market",
                qty=qty,
                limit_price=None,
                stop_price=stop_px,
                tif="DAY",
                status="filled",
                placed_ts=entry_ts,
                updated_ts=entry_ts,
                meta={"reasons": signal.reasons[:3], "run_date": run_date},
                client_order_id=f"{signal.symbol}-{entry_ts}",
                signal_id=None,
            )
            order_id = self.db.insert_order(order)
            self.db.insert_fill(
                models.Fill(
                    order_id=order_id,
                    fill_ts=entry_ts,
                    fill_price=fill_price,
                    fill_qty=qty,
                    liquidity="added",
                    venue="SIM" if self.settings.is_simulation else "IBKR",
                )
            )

            position_meta = {
                "stop_px": stop_px,
                "trail_mode": self.settings.stop_mode,
                "scale_target": fill_price * (1 + self.settings.scale1_pct / 100),
                "final_target": fill_price * (1 + self.settings.target_pct / 100),
                "run_date": run_date,
            }
            position = models.Position(
                symbol=signal.symbol,
                avg_price=fill_price,
                qty=qty,
                opened_ts=entry_ts,
                last_update_ts=entry_ts,
                meta=position_meta,
            )
            self.db.upsert_position(position)

            trade_entry = models.TradeJournalEntry(
                symbol=signal.symbol,
                open_ts=entry_ts,
                close_ts=None,
                side="long",
                entry_price=fill_price,
                exit_price=None,
                qty=qty,
                pnl=None,
                reason_open=";".join(signal.reasons[:3]),
                reason_close=None,
                tags="|".join(signal.reasons[:3]),
                signal_id=None,
            )
            trade_id = self.db.insert_trade_journal(trade_entry)

            self.positions[signal.symbol] = ManagedPosition(trade_id=trade_id, position=position)
            trade_ids.append(trade_id)
            logger.info("Opened position %s size %.0f @ %.2f", signal.symbol, qty, fill_price)
        return trade_ids

    def manage_open_positions(self, features: Dict[str, Dict[str, object]]) -> None:
        for symbol, managed in list(self.positions.items()):
            row = features.get(symbol)
            if not row:
                continue
            price = float(row.get("c", 0.0))
            ema_trail = float(row.get("ema_slow", price))
            position = managed.position
            meta = position.meta or {}
            scale_target = float(meta.get("scale_target", price))
            final_target = float(meta.get("final_target", price))
            stop_px = float(meta.get("stop_px", 0.0))

            if price <= stop_px:
                self._close_position(symbol, price, reason="stop hit")
                continue

            if not managed.scaled and price >= scale_target:
                scaled_qty = position.qty / 2
                self.order_client.submit_order(symbol, "SELL", scaled_qty, price)
                position.qty -= scaled_qty
                managed.scaled = True
                stop_px = max(stop_px, ema_trail)
                meta.update({"qty": position.qty, "stop_px": stop_px})
                position.meta = meta
                position.last_update_ts = to_epoch_seconds(now_et())
                self.db.upsert_position(position)
                logger.info("Scaled position %s to %.0f shares", symbol, position.qty)
                continue

            if price >= final_target:
                self._close_position(symbol, price, reason="target hit")
                continue

            if ema_trail > stop_px:
                meta["stop_px"] = ema_trail
                position.meta = meta
                position.last_update_ts = to_epoch_seconds(now_et())
                self.db.upsert_position(position)

    def flatten_all(self, features: Dict[str, Dict[str, object]]) -> None:
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
        qty = position.qty
        self.order_client.submit_order(symbol, "SELL", qty, price)
        exit_ts = to_epoch_seconds(now_et())
        order = models.Order(
            symbol=symbol,
            side="sell",
            order_type="market",
            qty=qty,
            limit_price=None,
            stop_price=None,
            tif="DAY",
            status="filled",
            placed_ts=exit_ts,
            updated_ts=exit_ts,
            meta={"reason": reason},
            client_order_id=f"{symbol}-close-{exit_ts}",
            signal_id=None,
        )
        order_id = self.db.insert_order(order)
        self.db.insert_fill(
            models.Fill(
                order_id=order_id,
                fill_ts=exit_ts,
                fill_price=price,
                fill_qty=qty,
                liquidity="added",
                venue="SIM" if self.settings.is_simulation else "IBKR",
            )
        )

        pnl = (price - position.avg_price) * qty
        self.db.update_trade_journal(
            managed.trade_id,
            close_ts=exit_ts,
            exit_price=price,
            qty=qty,
            pnl=pnl,
            reason_close=reason,
        )
        self.db.delete_position(symbol)
        logger.info("Closed position %s (%s) @ %.2f", symbol, reason, price)
