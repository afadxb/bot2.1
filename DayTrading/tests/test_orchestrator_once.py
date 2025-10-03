from __future__ import annotations

from intraday.orchestrator import Orchestrator


def test_run_cycle_creates_records(orchestrator: Orchestrator, db):
    artifacts = orchestrator.run_cycle("5m")
    assert artifacts.cycle_id > 0
    assert artifacts.ranked

    bars = db.execute("SELECT COUNT(*) as c FROM bars_intraday").fetchone()["c"]
    catalysts = db.execute("SELECT COUNT(*) as c FROM catalysts").fetchone()["c"]
    ai = db.execute("SELECT COUNT(*) as c FROM ai_provenance").fetchone()["c"]
    signals = db.execute("SELECT COUNT(*) as c FROM signals").fetchone()["c"]

    assert bars > 0
    assert catalysts > 0
    assert ai > 0
    assert signals > 0
