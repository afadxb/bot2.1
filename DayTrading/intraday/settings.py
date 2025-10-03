from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from datetime import datetime

from .utils.time import ET

logger = logging.getLogger(__name__)


@dataclass
class AppSettings:
    run_mode: str = "once"
    tz: str = "America/Toronto"
    simulation: bool = True
    watchlist_db_path: str | None = None
    focus_run_date: str | None = None
    watchlist_symbol_key: str = "symbol"
    sqlite_path: str = "premarket.db"
    ema_fast: int = 9
    ema_slow: int = 21
    vol_spike_mult: float = 2.0
    cons_lookback_min: int = 20
    vwap_enforce: bool = True
    catalyst_fresh_hours: int = 6
    top_k_execute: int = 20
    risk_pct_per_trade: float = 1.0
    stop_mode: str = "ema21_or_swing"
    atr_mult: float = 1.5
    scale1_pct: float = 4.0
    target_pct: float = 8.0
    max_trades_per_day: int = 8
    daily_drawdown_halt_pct: float = 4.0
    flatten_et: str = "15:55"
    ai_sentiment_enabled: bool = True
    ai_model: str = "finbert"
    ai_soft_veto: bool = True
    finnhub_token: str | None = None
    yahoo_rss_enabled: bool = True
    pushover_user_key: str | None = None
    pushover_api_token: str | None = None
    log_cfg: str = "config/logging.yaml"
    ibkr_host: str = "127.0.0.1"
    ibkr_port: int = 4002
    ibkr_client_id: int = 1776
    ibkr_exchange: str = "SMART"
    ibkr_primary_exchange: str | None = None
    ibkr_currency: str = "USD"
    ibkr_use_rth: bool = True
    ibkr_connect_timeout: float = 4.0
    ibkr_historical_duration_5m: str = "2 D"
    ibkr_historical_duration_15m: str = "5 D"

    def __post_init__(self) -> None:
        env = os.getenv
        self.run_mode = env("RUN_MODE", self.run_mode).lower()
        if self.run_mode not in {"once", "daemon"}:
            raise ValueError("RUN_MODE must be 'once' or 'daemon'")

        self.tz = env("TZ", self.tz)
        self.simulation = env("SIMULATION", str(self.simulation)).lower() == "true"
        self.sqlite_path = env("SQLITE_PATH", self.sqlite_path)
        self.watchlist_db_path = env(
            "WATCHLIST_DB_PATH", self.watchlist_db_path or self.sqlite_path
        )
        self.watchlist_symbol_key = env("WATCHLIST_SYMBOL_KEY", self.watchlist_symbol_key)
        self.focus_run_date = env("FOCUS_RUN_DATE", self.focus_run_date)

        if self.focus_run_date:
            try:
                datetime.fromisoformat(self.focus_run_date)
            except ValueError as exc:  # pragma: no cover - guard clause
                raise ValueError("FOCUS_RUN_DATE must be YYYY-MM-DD") from exc

        self.ema_fast = int(env("EMA_FAST", str(self.ema_fast)))
        self.ema_slow = int(env("EMA_SLOW", str(self.ema_slow)))
        if self.ema_fast <= 0 or self.ema_slow <= 0 or self.ema_fast >= self.ema_slow:
            raise ValueError("EMA settings invalid")

        self.vol_spike_mult = float(env("VOL_SPIKE_MULT", str(self.vol_spike_mult)))
        self.cons_lookback_min = int(env("CONS_LOOKBACK_MIN", str(self.cons_lookback_min)))
        self.vwap_enforce = env("VWAP_ENFORCE", str(self.vwap_enforce)).lower() == "true"
        self.catalyst_fresh_hours = int(env("CATALYST_FRESH_HOURS", str(self.catalyst_fresh_hours)))
        self.top_k_execute = int(env("TOP_K_EXECUTE", str(self.top_k_execute)))

        self.risk_pct_per_trade = float(env("RISK_PCT_PER_TRADE", str(self.risk_pct_per_trade)))
        self.stop_mode = env("STOP_MODE", self.stop_mode)
        self.atr_mult = float(env("ATR_MULT", str(self.atr_mult)))
        self.scale1_pct = float(env("SCALE1_PCT", str(self.scale1_pct)))
        self.target_pct = float(env("TARGET_PCT", str(self.target_pct)))
        self.max_trades_per_day = int(env("MAX_TRADES_PER_DAY", str(self.max_trades_per_day)))
        self.daily_drawdown_halt_pct = float(env("DAILY_DRAWDOWN_HALT_PCT", str(self.daily_drawdown_halt_pct)))
        self.flatten_et = env("FLATTEN_ET", self.flatten_et)

        self.ai_sentiment_enabled = env("AI_SENTIMENT_ENABLED", str(self.ai_sentiment_enabled)).lower() == "true"
        self.ai_model = env("AI_MODEL", self.ai_model)
        self.ai_soft_veto = env("AI_SOFT_VETO", str(self.ai_soft_veto)).lower() == "true"

        self.finnhub_token = env("FINNHUB_TOKEN", self.finnhub_token)
        self.yahoo_rss_enabled = env("YAHOO_RSS_ENABLED", str(self.yahoo_rss_enabled)).lower() == "true"
        self.pushover_user_key = env("PUSHOVER_USER_KEY", self.pushover_user_key)
        self.pushover_api_token = env("PUSHOVER_API_TOKEN", self.pushover_api_token)
        self.log_cfg = env("LOG_CFG", self.log_cfg)
        self.ibkr_host = env("IBKR_HOST", self.ibkr_host)
        self.ibkr_port = int(env("IBKR_PORT", str(self.ibkr_port)))
        self.ibkr_client_id = int(env("IBKR_CLIENT_ID", str(self.ibkr_client_id)))
        self.ibkr_exchange = env("IBKR_EXCHANGE", self.ibkr_exchange)
        primary_exchange = env("IBKR_PRIMARY_EXCHANGE", self.ibkr_primary_exchange or "")
        self.ibkr_primary_exchange = primary_exchange or None
        self.ibkr_currency = env("IBKR_CURRENCY", self.ibkr_currency)
        self.ibkr_use_rth = env("IBKR_USE_RTH", str(self.ibkr_use_rth)).lower() == "true"
        self.ibkr_connect_timeout = float(env("IBKR_CONNECT_TIMEOUT", str(self.ibkr_connect_timeout)))
        self.ibkr_historical_duration_5m = env(
            "IBKR_HIST_DURATION_5M", self.ibkr_historical_duration_5m
        )
        self.ibkr_historical_duration_15m = env(
            "IBKR_HIST_DURATION_15M", self.ibkr_historical_duration_15m
        )

        hour_minute = self.flatten_et.split(":")
        if len(hour_minute) != 2:
            raise ValueError("FLATTEN_ET must be HH:MM")
        hour, minute = map(int, hour_minute)
        if not (0 <= hour < 24 and 0 <= minute < 60):
            raise ValueError("FLATTEN_ET must be HH:MM")

    @property
    def is_simulation(self) -> bool:
        return self.simulation

    @property
    def flatten_dt_today(self) -> datetime:
        hour, minute = map(int, self.flatten_et.split(":"))
        return datetime.now(tz=ET).replace(hour=hour, minute=minute, second=0, microsecond=0)

def load_settings() -> AppSettings:
    return AppSettings()
