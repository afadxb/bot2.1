from __future__ import annotations

from intraday.exec.trade_manager import TradeManager
from intraday.exec.order_client import OrderClient
from intraday.strategy.engine import RankedSignal


def test_trade_lifecycle(settings, db):
    order_client = OrderClient(settings, db)
    manager = TradeManager(settings, db, order_client)

    feature_map = {
        "AAPL": {
            "c": 100.0,
            "atr": 1.0,
            "ema_slow": 99.5,
            "context_bias": 0.0,
        }
    }

    signal = RankedSignal(symbol="AAPL", score=80.0, reasons=["test"], gate="PASS")
    trade_ids = manager.execute([signal], feature_map)
    assert trade_ids

    position = manager.positions["AAPL"].position
    assert position.qty > 0

    scale_target = position.meta["scale_target"]
    feature_map["AAPL"]["c"] = scale_target + 0.1
    manager.manage_open_positions(feature_map)
    assert manager.positions["AAPL"].scaled

    final_target = manager.positions["AAPL"].position.meta["final_target"]
    feature_map["AAPL"]["c"] = final_target + 0.1
    manager.manage_open_positions(feature_map)
    assert "AAPL" not in manager.positions

    status = db.execute("SELECT status FROM trades").fetchone()["status"]
    assert status == "CLOSED"
