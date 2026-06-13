"""Shared German euro amount parsing for bank ETL modules."""

from __future__ import annotations

import re
from typing import Any

_MILL_DECIMAL = re.compile(r"^-?\d+,\d{3}$")


def de_float(
    value: Any,
    *,
    default: float = 0.0,
    round_to: int | None = None,
    trim_mill_decimal: bool = False,
) -> float:
    """Parse German-formatted amounts such as ``1.234,56`` or ``-12,34``."""
    if value is None:
        return default

    text = str(value).strip().replace("\xa0", "").replace(" ", "").replace('"', "")
    if not text:
        return default

    normalized = text.replace(".", "")
    if trim_mill_decimal and _MILL_DECIMAL.match(normalized):
        normalized = normalized[:-1]

    try:
        result = float(normalized.replace(",", "."))
    except ValueError:
        return default

    if round_to is not None and round_to >= 0:
        return round(result, round_to)
    return result


def parse_german_euro_amount(text: str, *, round_to: int = 2) -> float:
    """Strict invoice parsing: trim ``12,345`` OCR tails and round to cents."""
    return de_float(text, round_to=round_to, trim_mill_decimal=True)
