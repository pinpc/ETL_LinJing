"""Shared artifact writers for ETL modules."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping

from .jsonio import write_json_file


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
    write_json_file(run_meta_path, payload)
    return run_meta_path
