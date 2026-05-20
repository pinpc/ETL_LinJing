"""Shared SQLite helpers for ETL transaction storage."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from .models import ProcessedTransaction


def write_processed_transactions_sqlite(
    sqlite_path: Path,
    *,
    table_name: str,
    rows: list[ProcessedTransaction],
) -> None:
    """Persist processed rows into a standardized SQLite transaction table."""
    sqlite_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(sqlite_path)
    try:
        cursor = connection.cursor()
        _ensure_processed_transactions_schema(cursor, table_name)
        run_id = str(uuid4())
        created_at = datetime.now(timezone.utc).isoformat()
        cursor.executemany(
            f"""
            INSERT INTO {table_name} (
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


def _ensure_processed_transactions_schema(cursor, table_name: str) -> None:
    cursor.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {table_name} (
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
    cursor.execute(f"PRAGMA table_info({table_name})")
    columns = {row[1] for row in cursor.fetchall()}
    if "run_id" not in columns:
        cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN run_id TEXT")
    if "created_at" not in columns:
        cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN created_at TEXT")
