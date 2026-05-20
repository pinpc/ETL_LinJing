"""Shared artifact writers for ETL modules."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping


def write_run_meta(
    *,
    tenant_id: str,
    module_name: str,
    output_path: Path,
    row_count: int,
    artifacts: Mapping[str, str | Path],
) -> Path:
    """Write standardized run metadata JSON beside the output workbook."""
    run_meta_path = output_path.with_suffix(".run_meta.json")
    run_meta_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "tenant_id": tenant_id,
        "module_name": module_name,
        "row_count": row_count,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "artifacts": {
            key: str(value)
            for key, value in artifacts.items()
        },
    }
    run_meta_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return run_meta_path
