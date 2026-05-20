"""Shared JSON read/write helpers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def write_json_file(path: Path, payload: Any) -> None:
    """Write JSON payload with UTF-8 and stable formatting."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
