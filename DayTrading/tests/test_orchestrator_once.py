from __future__ import annotations

from intraday.orchestrator import Orchestrator


def test_run_cycle_creates_records(orchestrator: Orchestrator, db):
    artifacts = orchestrator.run_cycle("5m")
    assert artifacts.run_id > 0
    assert artifacts.ranked

    bars = db.execute("SELECT COUNT(*) as c FROM bars").fetchone()["c"]
    news = db.execute("SELECT COUNT(*) as c FROM news").fetchone()["c"]
    ai = db.execute("SELECT COUNT(*) as c FROM ai_provenance").fetchone()["c"]

    assert bars > 0
    assert news > 0
    assert ai > 0
