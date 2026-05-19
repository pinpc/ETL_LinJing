"""Cashbook service placeholders."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from .asia_legacy import AsiaKasseETL
from .interfaces import CashbookRunRequest, ICashbookService
from .jupiter_legacy import JupiterKasseETL
from ..tenant.service import TenantResolver, resolve_option_path, resolve_option_str
from ..shared.models import ProcessedTransaction


class CashbookService(ICashbookService):
    """Adapter service wrapping legacy tenant-specific cashbook ETLs."""

    def __init__(self, tenant_resolver: TenantResolver | None = None) -> None:
        self._tenant_resolver = tenant_resolver or TenantResolver()

    def run(self, request: CashbookRunRequest) -> list[ProcessedTransaction]:
        tenant_id = request.tenant_id.strip().lower()
        tenant_context = self._tenant_resolver.resolve(tenant_id)
        tenant_pdf_base = resolve_option_path(tenant_context, "cashbook_pdf_base_dir")
        tenant_sheet_name = resolve_option_str(tenant_context.options, "cashbook_sheet_name")
        tenant_sqlite_output = resolve_option_path(tenant_context, "cashbook_sqlite_output_path")

        if tenant_id == "asia":
            engine = AsiaKasseETL()
            engine.run(
                input_path=request.input_path,
                output_path=request.output_path,
                pdf_base_dir=_resolve_pdf_base_dir(
                    request,
                    tenant_pdf_base,
                    request.input_path.parents[2] if request.input_path.exists() else Path("."),
                ),
                sheet_name=_resolve_sheet_name(
                    request,
                    tenant_sheet_name,
                    "cashbook",
                ),
            )
            processed = _result_to_processed_transactions(engine.final_rows, tenant_id, "cashbook")
            _write_sqlite(
                _resolve_sqlite_output_path(
                    request,
                    tenant_sqlite_output,
                    request.output_path.with_suffix(".sqlite"),
                ),
                processed,
            )
            return processed

        if tenant_id == "jupiter":
            engine = JupiterKasseETL()
            engine.run(
                input_path=request.input_path,
                output_path=request.output_path,
                pdf_base_dir=_resolve_pdf_base_dir(
                    request,
                    tenant_pdf_base,
                    request.input_path.parent if request.input_path.exists() else Path("."),
                ),
                sheet_name=_resolve_sheet_name(
                    request,
                    tenant_sheet_name,
                    None,
                ),
            )
            processed = _result_to_processed_transactions(engine.final_rows, tenant_id, "cashbook")
            _write_sqlite(
                _resolve_sqlite_output_path(
                    request,
                    tenant_sqlite_output,
                    request.output_path.with_suffix(".sqlite"),
                ),
                processed,
            )
            return processed

        raise ValueError(f"Unsupported cashbook tenant '{request.tenant_id}'. Expected: asia, jupiter.")


def _result_to_processed_transactions(rows: list, tenant_id: str, module_name: str) -> list[ProcessedTransaction]:
    processed: list[ProcessedTransaction] = []
    for row in rows:
        processed.append(
            ProcessedTransaction(
                tenant_id=tenant_id,
                module_name=module_name,
                amount=float(row.umsatz_euro),
                booking_date=str(row.datum),
                booking_text=str(row.buchungstext),
                bu_gkto=str(row.bu_gkto),
                beleg_1=str(row.beleg_1),
            )
        )
    return processed


def _resolve_pdf_base_dir(
    request: CashbookRunRequest,
    tenant_value: Path | None,
    fallback: Path,
) -> Path:
    if request.pdf_base_dir is not None:
        return request.pdf_base_dir
    if tenant_value is not None:
        return tenant_value
    return fallback


def _resolve_sheet_name(
    request: CashbookRunRequest,
    tenant_value: str | None,
    fallback: str | None,
) -> str | None:
    if request.sheet_name is not None:
        return request.sheet_name
    if tenant_value is not None:
        return tenant_value
    return fallback


def _resolve_sqlite_output_path(
    request: CashbookRunRequest,
    tenant_value: Path | None,
    fallback: Path,
) -> Path:
    if request.sqlite_output_path is not None:
        return request.sqlite_output_path
    if tenant_value is not None:
        return tenant_value
    return fallback


def _write_sqlite(sqlite_path: Path, rows: list[ProcessedTransaction]) -> None:
    sqlite_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(sqlite_path)
    try:
        cursor = connection.cursor()
        _ensure_cashbook_sqlite_schema(cursor)
        run_id = str(uuid4())
        created_at = datetime.now(timezone.utc).isoformat()
        cursor.executemany(
            """
            INSERT INTO cashbook_transactions (
                run_id, created_at, tenant_id, module_name, amount, booking_date, booking_text, bu_gkto, beleg_1
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    run_id,
                    created_at,
                    row.tenant_id,
                    row.module_name,
                    row.amount,
                    row.booking_date,
                    row.booking_text,
                    row.bu_gkto,
                    row.beleg_1,
                )
                for row in rows
            ],
        )
        connection.commit()
    finally:
        connection.close()


def _ensure_cashbook_sqlite_schema(cursor) -> None:
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS cashbook_transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id TEXT,
            created_at TEXT,
            tenant_id TEXT NOT NULL,
            module_name TEXT NOT NULL,
            amount REAL NOT NULL,
            booking_date TEXT NOT NULL,
            booking_text TEXT NOT NULL,
            bu_gkto TEXT,
            beleg_1 TEXT
        )
        """
    )
    cursor.execute("PRAGMA table_info(cashbook_transactions)")
    columns = {row[1] for row in cursor.fetchall()}
    if "run_id" not in columns:
        cursor.execute("ALTER TABLE cashbook_transactions ADD COLUMN run_id TEXT")
    if "created_at" not in columns:
        cursor.execute("ALTER TABLE cashbook_transactions ADD COLUMN created_at TEXT")

