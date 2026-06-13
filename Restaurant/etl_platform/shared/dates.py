"""Shared date normalization for canonical ETL output."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

_DATE_FORMATS = (
    "%Y-%m-%d",
    "%d.%m.%Y",
    "%d.%m.%y",
    "%d/%m/%Y",
    "%m/%d/%Y",
    "%Y/%m/%d",
)


def normalize_booking_date(value: Any) -> str:
    """Normalize booking dates to ISO ``YYYY-MM-DD`` for JSON/SQLite/canonical rows."""
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()

    text = str(value).strip()
    if not text:
        return ""

    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            continue

    return text
