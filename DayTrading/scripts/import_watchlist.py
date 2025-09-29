from __future__ import annotations

from pathlib import Path

import typer

from intraday.ingestion.watchlist_loader import load_watchlist
from intraday.settings import AppSettings
from intraday.storage.db import Database

app = typer.Typer()


@app.command()
def main(path: Path = typer.Option(..., exists=True, readable=True)) -> None:
    settings = AppSettings()
    db = Database(Path(settings.sqlite_path))
    migrations = Path(__file__).parent.parent / "intraday" / "storage" / "migrations"
    db.run_migrations(migrations)
    run_id, symbols, _ = load_watchlist(settings, db, path)
    typer.echo(f"Imported run {run_id} with {len(symbols)} symbols")


if __name__ == "__main__":
    app()
