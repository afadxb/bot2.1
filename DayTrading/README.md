# DayTrading Intraday Signal Engine

DayTrading is a standalone, simulation-friendly intraday signal engine that can ingest a daily
watchlist JSON file, simulate or collect intraday bars, evaluate technical and catalyst rules,
optionally apply AI sentiment, and manage simulated trade execution. The project is structured to
run either as a one-off process or as a daemon managed by APScheduler.

## Features

- **Watchlist ingestion** – Load and normalize JSON payloads, persist runs and items to SQLite.
- **Data collection** – Deterministic simulated 5m/15m bar and news feeds when running in
  simulation mode. Stubs are in place for IBKR and other data providers.
- **Strategy pipeline** – Compute indicators, evaluate technical rules, merge catalysts, apply
  sentiment, and produce ranked trade candidates.
- **Risk & execution** – Apply strict per-trade risk limits, scale-out logic, and EOD flattening in
  simulation mode.
- **Storage** – SQLite database with migrations, WAL mode, and helper utilities for persisting
  domain objects.
- **Dashboard** – Minimal Streamlit dashboard summarizing ranked candidates and positions.

## Getting Started

### Prerequisites

- Python 3.11
- [Poetry](https://python-poetry.org/) for dependency management (optional but recommended).

### Installation

```bash
cd DayTrading
poetry install
```

Create a `.env` file based on `.env.example` and configure your runtime preferences.

### Running the Engine

The application entry point is `main.py`. It inspects environment variables to determine run mode
and whether to operate in simulation or live mode.

```bash
poetry run python main.py
```

- `RUN_MODE=once` executes a single 5-minute cycle and exits.
- `RUN_MODE=daemon` starts APScheduler jobs (5m/15m) and a daily flatten guard.

### Watchlist Ingestion

Point `WATCHLIST_DB_PATH` at the shared pre-market SQLite database and the engine will pull the
latest symbols directly. If you receive a JSON export instead, you can manually import it into the
engine's SQLite store with:

```bash
poetry run python scripts/import_watchlist.py --path ./incoming/full_watchlist.json
```

### Simulation vs Live

When `SIMULATION=true`, the engine uses deterministic data feeds and order execution. This makes it
safe to run without an IBKR connection while still exercising the full pipeline. Set
`SIMULATION=false` only when an IBKR gateway is available and you have configured credentials.

### Testing and Linting

```bash
poetry run pytest
poetry run mypy intraday
poetry run ruff check .
poetry run black --check .
```

### Troubleshooting

- **Missing watchlist data** – Ensure `WATCHLIST_DB_PATH` points to the shared SQLite database. If
  you're importing JSON manually, run `scripts/import_watchlist.py` first so the latest symbols are
  present in the local store.
- **Empty symbols** – The loader requires a non-empty string `symbol`. Duplicate symbols are
  deduplicated with a log entry.
- **DB permissions** – The SQLite file is created at `SQLITE_PATH`; ensure the directory exists and
  is writable.
- **Scheduler not firing** – Confirm `RUN_MODE=daemon` and that your environment supports long-lived
  processes. Review logs in `logs/daytrading.log` for details.

## License

MIT
