from __future__ import annotations

import logging
import math
from datetime import datetime, timedelta
from typing import Dict, Iterable, List

from ..settings import AppSettings
from ..storage import models
from ..storage.db import Database
from ..utils.time import now_et, to_epoch_seconds

logger = logging.getLogger(__name__)


class IBKRFeed:
    def __init__(self, settings: AppSettings, db: Database) -> None:
        self.settings = settings
        self.db = db

    def _duration_for(self, tf: str) -> str:
        if tf == "5m":
            return self.settings.ibkr_historical_duration_5m
        if tf == "15m":
            return self.settings.ibkr_historical_duration_15m
        raise ValueError(f"Unsupported timeframe {tf}")

    def _bar_size_for(self, tf: str) -> str:
        if tf == "5m":
            return "5 mins"
        if tf == "15m":
            return "15 mins"
        raise ValueError(f"Unsupported timeframe {tf}")

    def _build_contract(self, symbol: str):
        from ib_insync import Stock  # type: ignore

        if self.settings.ibkr_primary_exchange:
            return Stock(
                symbol,
                self.settings.ibkr_exchange,
                self.settings.ibkr_currency,
                primaryExchange=self.settings.ibkr_primary_exchange,
            )
        return Stock(symbol, self.settings.ibkr_exchange, self.settings.ibkr_currency)

    def collect_bars(self, symbols: Iterable[str], tf: str) -> List[models.Bar]:
        if self.settings.is_simulation:
            return self._generate_sim_bars(symbols, tf)

        try:
            from ib_insync import IB  # type: ignore
        except ImportError as exc:  # pragma: no cover - optional dependency guard
            raise RuntimeError("ib_insync must be installed to collect live IBKR data") from exc

        bars: List[models.Bar] = []
        ib = IB()
        logger.info(
            "Connecting to IBKR at %s:%s (client id %s)",
            self.settings.ibkr_host,
            self.settings.ibkr_port,
            self.settings.ibkr_client_id,
        )
        try:
            ib.connect(
                self.settings.ibkr_host,
                self.settings.ibkr_port,
                clientId=self.settings.ibkr_client_id,
                timeout=self.settings.ibkr_connect_timeout,
            )
        except Exception as exc:  # pragma: no cover - network dependency
            logger.error("Failed to connect to IBKR: %s", exc)
            raise RuntimeError("Unable to connect to IBKR gateway") from exc
        try:
            duration = self._duration_for(tf)
            bar_size = self._bar_size_for(tf)
            for symbol in symbols:
                contract = self._build_contract(symbol)
                try:
                    qualified = ib.qualifyContracts(contract)
                except Exception as exc:  # pragma: no cover - network dependency
                    logger.error("Failed to qualify contract for %s: %s", symbol, exc)
                    continue
                if not qualified:
                    logger.warning("IBKR could not qualify contract for %s; skipping", symbol)
                    continue
                contract = qualified[0]
                logger.info(
                    "Requesting %s bars for %s (duration %s)",
                    bar_size,
                    symbol,
                    duration,
                )
                try:
                    hist = ib.reqHistoricalData(
                        contract,
                        endDateTime="",
                        durationStr=duration,
                        barSizeSetting=bar_size,
                        whatToShow="TRADES",
                        useRTH=self.settings.ibkr_use_rth,
                        formatDate=2,
                    )
                except Exception as exc:  # pragma: no cover - network dependency
                    logger.error("Historical data request failed for %s: %s", symbol, exc)
                    continue
                for bar in hist:
                    dt = bar.date
                    if isinstance(dt, str):  # pragma: no cover - defensive guard
                        dt = datetime.fromtimestamp(int(dt))
                    ts_epoch = to_epoch_seconds(dt)
                    bars.append(
                        models.Bar(
                            symbol=symbol,
                            tf=tf,
                            ts=ts_epoch,
                            o=float(bar.open),
                            h=float(bar.high),
                            l=float(bar.low),
                            c=float(bar.close),
                            v=float(bar.volume),
                            vwap=float(bar.average) if bar.average is not None else None,
                        )
                    )
        finally:
            if ib.isConnected():
                ib.disconnect()
        bars.sort(key=lambda b: (b.symbol, b.ts))
        return bars

    def _generate_sim_bars(self, symbols: Iterable[str], tf: str) -> List[models.Bar]:
        now = now_et()
        if tf == "5m":
            step = timedelta(minutes=5)
            periods = 30
        else:
            step = timedelta(minutes=15)
            periods = 20
        bars: List[models.Bar] = []
        for symbol in symbols:
            seed = (abs(hash(symbol)) % 1000) / 100.0
            base = 50 + seed
            for idx in range(periods):
                ts = now - step * (periods - idx)
                ts_epoch = to_epoch_seconds(ts)
                drift = idx * 0.15
                noise = (math.sin(idx + seed) + 1) * 0.5
                open_px = base + drift + noise
                close_px = open_px + math.sin(idx) * 0.3
                high_px = max(open_px, close_px) + 0.2
                low_px = min(open_px, close_px) - 0.2
                volume = 1000 + idx * 25 + int(seed * 10)
                bars.append(
                    models.Bar(
                        symbol=symbol,
                        tf=tf,
                        ts=ts_epoch,
                        o=round(open_px, 2),
                        h=round(high_px, 2),
                        l=round(low_px, 2),
                        c=round(close_px, 2),
                        v=float(volume),
                        vwap=round((open_px + high_px + low_px + close_px) / 4, 2),
                    )
                )
        bars.sort(key=lambda b: (b.symbol, b.ts))
        return bars

    def quotes_snapshot(self, symbols: Iterable[str]) -> Dict[str, float]:
        snapshot = {}
        for symbol in symbols:
            seed = (abs(hash(symbol)) % 1000) / 100.0
            snapshot[symbol] = 50 + seed + 0.5
        return snapshot
