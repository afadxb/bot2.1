from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Dict, List

from .ai.sentiment import SentimentAnalyzer
from .ai.regime import current_regime
from .alerts import pushover
from .data.catalysts import merge_catalysts
from .data.finnhub_feed import FinnhubFeed
from .data.ibkr_feed import IBKRFeed
from .data.yahoo_feed import YahooFeed
from .exec.order_client import OrderClient
from .exec.trade_manager import TradeManager
from .ingestion.watchlist_loader import FocusList, WatchlistLoader
from .market_clock import should_flatten
from .settings import AppSettings
from .storage import models
from .storage.db import Database
from .strategy import engine, features
from .utils.time import now_et, to_epoch_seconds

logger = logging.getLogger(__name__)


@dataclass
class CycleArtifacts:
    cycle_id: int
    run_date: str
    ranked: List[engine.RankedSignal]
    trades: List[int]


class Orchestrator:
    def __init__(self, settings: AppSettings, db: Database) -> None:
        self.settings = settings
        self.db = db
        self.loader = WatchlistLoader(settings, db)
        self.ibkr = IBKRFeed(settings, db)
        self.finnhub = FinnhubFeed(settings)
        self.yahoo = YahooFeed(settings)
        self.sentiment = SentimentAnalyzer(settings, db)
        self.order_client = OrderClient(settings, db)
        self.trade_manager = TradeManager(settings, db, self.order_client)
        self._last_watchlist: FocusList | None = None

    def load_or_import_watchlist(self) -> FocusList:
        if self._last_watchlist is None:
            self._last_watchlist = self.loader.load()
        return self._last_watchlist

    def collect_bars(self, focus: FocusList, timeframe: str) -> List:
        bars = self.ibkr.collect_bars(focus.symbols, timeframe)
        source = "SIM" if self.settings.is_simulation else "IBKR"
        self.db.write_intraday_bars(bars, timeframe, source, focus.run_date)
        return bars

    def collect_catalysts(self, symbols: List[str]) -> List[models.Catalyst]:
        finnhub_items = self.finnhub.fetch(symbols)
        yahoo_items = self.yahoo.fetch(symbols) if self.settings.yahoo_rss_enabled else []
        return merge_catalysts(self.settings.catalyst_fresh_hours, finnhub_items, yahoo_items)

    def run_cycle(self, timeframe: str) -> CycleArtifacts:
        logger.info("Starting cycle for %s", timeframe)
        focus = self.load_or_import_watchlist()
        start_ts = to_epoch_seconds(now_et())
        cycle_id = self.db.insert_intraday_cycle_run(
            models.IntradayCycleRun(
                run_started_ts=start_ts,
                run_finished_ts=None,
                watchlist_count=len(focus.symbols),
                evaluated_count=0,
                placed_orders=0,
                errors_count=0,
                timings=None,
                notes={"timeframe": timeframe, "run_date": focus.run_date},
            )
        )

        bars = self.collect_bars(focus, timeframe)
        feature_map = features.build_snapshot(bars, focus.context, self.settings)
        feature_rows = self._persist_features(timeframe, bars, feature_map)

        catalysts = self.collect_catalysts(focus.symbols)
        self.db.write_catalysts(catalysts)

        sentiment_results = self.sentiment.analyze(catalysts)
        ranked = engine.rank_candidates(feature_map, sentiment_results, self.settings)
        regime = current_regime()
        for signal in ranked:
            signal.score *= regime.multiplier
        self._persist_signals(focus, timeframe, ranked, feature_rows)
        trades = self.trade_manager.execute(ranked, feature_map, focus.run_date)
        self.trade_manager.manage_open_positions(feature_map)
        if ranked:
            top = ranked[0]
            pushover.send(self.settings, "Top Candidate", f"{top.symbol} score {top.score:.1f}")
        finished_ts = to_epoch_seconds(now_et())
        self.db.update_intraday_cycle_run(
            cycle_id,
            run_finished_ts=finished_ts,
            evaluated_count=len(feature_rows),
            placed_orders=len(trades),
        )
        return CycleArtifacts(cycle_id=cycle_id, run_date=focus.run_date, ranked=ranked, trades=trades)

    def flatten_guard(self) -> None:
        if should_flatten(self.settings.flatten_dt_today, now_et()):
            focus = self.load_or_import_watchlist()
            bars = self.collect_bars(focus, "5m")
            feature_map = features.build_snapshot(bars, focus.context, self.settings)
            self.trade_manager.flatten_all(feature_map)

    def _persist_features(
        self,
        timeframe: str,
        bars: List[models.Bar],
        feature_map: Dict[str, Dict[str, object]],
    ) -> List[models.IntradayFeatureRow]:
        latest_ts: Dict[str, int] = {}
        for bar in bars:
            latest_ts[bar.symbol] = max(bar.ts, latest_ts.get(bar.symbol, 0))

        rows: List[models.IntradayFeatureRow] = []
        for symbol, data in feature_map.items():
            ts = latest_ts.get(symbol)
            if ts is None:
                continue
            rows.append(
                models.IntradayFeatureRow(
                    symbol=symbol,
                    ts=ts,
                    timeframe=timeframe,
                    features=data,
                )
            )
        self.db.write_intraday_features(rows)
        return rows

    def _persist_signals(
        self,
        focus: FocusList,
        timeframe: str,
        ranked: List[engine.RankedSignal],
        feature_rows: List[models.IntradayFeatureRow],
    ) -> None:
        ts_map = {row.symbol: row.ts for row in feature_rows}
        records = []
        for signal in ranked:
            ts = ts_map.get(signal.symbol)
            if ts is None:
                continue
            records.append(
                models.SignalRecord(
                    symbol=signal.symbol,
                    ts=ts,
                    timeframe=timeframe,
                    base_score=signal.base_score,
                    ai_adjustment=signal.ai_adjustment,
                    final_score=signal.score,
                    decision=signal.decision,
                    reason_tags="|".join(signal.reasons),
                    details={"reasons": signal.reasons},
                    phase1_rank=focus.ranks.get(signal.symbol),
                    run_date=focus.run_date,
                )
            )
        self.db.write_signals(records)
