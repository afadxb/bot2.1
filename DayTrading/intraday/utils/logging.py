from __future__ import annotations

import logging.config
from pathlib import Path
from typing import Any, Dict

import yaml


def configure_logging(config_path: str) -> None:
    path = Path(config_path)
    if not path.exists():
        logging.basicConfig(level=logging.INFO)
        logging.getLogger(__name__).warning("Logging config %s missing; using basicConfig", config_path)
        return

    with path.open("r", encoding="utf-8") as fh:
        data: Dict[str, Any] = yaml.safe_load(fh)
    logging.config.dictConfig(data)
