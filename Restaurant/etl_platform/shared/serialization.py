"""Shared serializers for canonical ETL models."""

from __future__ import annotations

from typing import Any

from .models import ProcessedTransaction


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
