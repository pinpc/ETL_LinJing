"""Shared export pipeline for canonical processed transactions."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

from .jsonio import write_json_file
from .models import ProcessedTransaction
from .serialization import PROCESSED_TRANSACTION_FIELDS, serialize_processed_transaction
from .sqlite_store import write_processed_transactions_sqlite


@dataclass(slots=True)
class ProcessedExportTargets:
    """Optional targets for exporting processed transaction rows."""

    csv_output_path: Path | None = None
    json_output_path: Path | None = None
    sqlite_output_path: Path | None = None
    sqlite_table_name: str = "processed_transactions"


def export_processed_rows(rows: list[ProcessedTransaction], targets: ProcessedExportTargets) -> None:
    """Export processed rows to one or more configured targets."""
    if targets.csv_output_path is not None:
        _write_processed_csv(targets.csv_output_path, rows)
    if targets.json_output_path is not None:
        _write_processed_json(targets.json_output_path, rows)
    if targets.sqlite_output_path is not None:
        write_processed_transactions_sqlite(
            targets.sqlite_output_path,
            table_name=targets.sqlite_table_name,
            rows=rows,
        )


def sidecar_json_path(output_path: Path, suffix: str) -> Path:
    """Resolve a sidecar JSON artifact path from a base output path."""
    return output_path.with_suffix(suffix)


def write_sidecar_json(output_path: Path, suffix: str, payload: object) -> Path:
    """Write sidecar JSON artifact and return its resolved path."""
    path = sidecar_json_path(output_path, suffix)
    write_json_file(path, payload)
    return path


def _write_processed_csv(output_path: Path, rows: list[ProcessedTransaction]) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=list(PROCESSED_TRANSACTION_FIELDS))
        writer.writeheader()
        for row in rows:
            writer.writerow(serialize_processed_transaction(row))


def _write_processed_json(output_path: Path, rows: list[ProcessedTransaction]) -> None:
    payload = [serialize_processed_transaction(row) for row in rows]
    write_json_file(output_path, payload)
