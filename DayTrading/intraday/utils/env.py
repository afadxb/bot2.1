from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

try:  # pragma: no cover - optional dependency
    from dotenv import load_dotenv  # type: ignore
except ImportError:  # pragma: no cover
    load_dotenv = None


def load_environment(dotenv_path: Optional[str] = None) -> None:
    candidate = Path(dotenv_path) if dotenv_path else Path(".env")
    if not candidate.exists():
        return
    if load_dotenv is not None:
        load_dotenv(candidate)
        return
    for line in candidate.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ[key.strip()] = value.strip()
