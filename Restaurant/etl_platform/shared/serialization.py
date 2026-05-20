"""Shared serializers for canonical ETL models."""

from __future__ import annotations

from typing import Any

from .models import ProcessedTransaction

PROCESSED_TRANSACTION_FIELDS: tuple[str, ...] = (
    "tenant_id",
    "module_name",
    "amount",
    "booking_date",
    "booking_text",
    "bu_gkto",
    "beleg_1",
)


def serialize_processed_transaction(row: ProcessedTransaction) -> dict[str, Any]:
    """Convert a processed row into canonical dictionary form."""
    return {
        "tenant_id": row.tenant_id,
        "module_name": row.module_name,
        "amount": row.amount,
        "booking_date": row.booking_date,
        "booking_text": row.booking_text,
        "bu_gkto": row.bu_gkto,
        "beleg_1": row.beleg_1,
    }


def legacy_rows_to_processed_transactions(
    rows: list[object],
    *,
    tenant_id: str,
    module_name: str,
) -> list[ProcessedTransaction]:
    """Convert legacy row objects with expected attributes to canonical processed rows."""
    return [
        ProcessedTransaction(
            tenant_id=tenant_id,
            module_name=module_name,
            amount=float(getattr(row, "umsatz_euro")),
            booking_date=str(getattr(row, "datum")),
            booking_text=str(getattr(row, "buchungstext")),
            bu_gkto=str(getattr(row, "bu_gkto")),
            beleg_1=str(getattr(row, "beleg_1")),
        )
        for row in rows
    ]
