from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Dict, List, Tuple

from .ai.sentiment import SentimentAnalyzer
from .ai.regime import current_regime
from .alerts import pushover
from .data.catalysts import merge_catalysts
from .data.finnhub_feed import FinnhubFeed
from .data.ibkr_feed import IBKRFeed
from .data.yahoo_feed import YahooFeed
from .exec.order_client import OrderClient
from .exec.trade_manager import TradeManager
from .ingestion.watchlist_loader import WatchlistLoader
from .market_clock import should_flatten
from .settings import AppSettings
from .storage.db import Database
from .strategy import engine, features
from .utils.time import now_et

logger = logging.getLogger(__name__)


@dataclass
class CycleArtifacts:
    run_id: int
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
        self._last_watchlist: Tuple[int, List[str], Dict[str, Dict[str, object]]] | None = None

    def load_or_import_watchlist(self) -> Tuple[int, List[str], Dict[str, Dict[str, object]]]:
        if self._last_watchlist is None:
            self._last_watchlist = self.loader.load()
        return self._last_watchlist

    def collect_bars(self, symbols: List[str]) -> List:
        bars_5m = self.ibkr.collect_bars(symbols, "5m")
        self.ibkr.collect_bars(symbols, "15m")
        return bars_5m

    def collect_catalysts(self, symbols: List[str]) -> List:
        finnhub_items = self.finnhub.fetch(symbols)
        yahoo_items = self.yahoo.fetch(symbols) if self.settings.yahoo_rss_enabled else []
        return merge_catalysts(self.db, self.settings.catalyst_fresh_hours, finnhub_items, yahoo_items)

    def run_cycle(self, timeframe: str) -> CycleArtifacts:
        logger.info("Starting cycle for %s", timeframe)
        run_id, symbols, ctx_map = self.load_or_import_watchlist()
        bars = self.collect_bars(symbols)
        feature_map = features.build_snapshot(bars, ctx_map, self.settings)
        catalysts = self.collect_catalysts(symbols)
        sentiment_results = self.sentiment.analyze(catalysts)
        ranked = engine.rank_candidates(feature_map, sentiment_results, self.settings)
        regime = current_regime()
        for signal in ranked:
            signal.score *= regime.multiplier
        trades = self.trade_manager.execute(ranked, feature_map)
        self.trade_manager.manage_open_positions(feature_map)
        if ranked:
            top = ranked[0]
            pushover.send(self.settings, "Top Candidate", f"{top.symbol} score {top.score:.1f}")
        return CycleArtifacts(run_id=run_id, ranked=ranked, trades=trades)

    def flatten_guard(self) -> None:
        if should_flatten(self.settings.flatten_dt_today, now_et()):
            run_id, symbols, ctx_map = self.load_or_import_watchlist()
            bars = self.collect_bars(symbols)
            feature_map = features.build_snapshot(bars, ctx_map, self.settings)
            self.trade_manager.flatten_all(feature_map)
