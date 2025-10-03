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

    signal = RankedSignal(
        symbol="AAPL",
        base_score=80.0,
        ai_adjustment=0.0,
        context_bias=0.0,
        score=80.0,
        decision="enter_long",
        reasons=["test"],
        gate="PASS",
    )
    trade_ids = manager.execute([signal], feature_map, run_date="2024-04-01")
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

    journal = db.execute("SELECT reason_close, exit_price FROM trade_journal").fetchone()
    assert journal["reason_close"] == "target hit"
    assert journal["exit_price"] > 0
