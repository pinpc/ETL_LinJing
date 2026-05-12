from __future__ import annotations

from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Iterable

from .models import BuchungRow


def as_text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def norm_header(value: Any) -> str:
    return as_text(value)


def parse_amount(value: Any) -> Decimal:
    if value is None:
        return Decimal("0")
    if isinstance(value, (int, float, Decimal)):
        try:
            return Decimal(str(value))
        except InvalidOperation:
            return Decimal("0")

    text = str(value).strip()
    if text.count(",") == 1 and text.count(".") >= 1:
        text = text.replace(".", "").replace(",", ".")
    else:
        text = text.replace(",", ".")

    if text == "":
        return Decimal("0")

    try:
        return Decimal(text)
    except InvalidOperation:
        return Decimal("0")


def convert_number(value: str) -> Decimal:
    text = (value or "").strip().replace("EUR", "").replace("€", "").strip()
    if text == "":
        return Decimal("0")

    if "," in text and "." in text:
        text = text.replace(",", "")
    elif "," in text:
        parts = text.split(",")
        if len(parts) == 2 and len(parts[1]) == 2:
            text = text.replace(",", ".")
        else:
            text = text.replace(",", "")
    elif "." in text:
        parts = text.split(".")
        if len(parts) == 2 and len(parts[1]) != 2:
            text = text.replace(".", "")

    try:
        return Decimal(str(float(text)))
    except Exception:
        return Decimal("0")


def parse_date(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.date().isoformat()

    text = str(value).strip()
    if text == "":
        return ""

    for fmt in ("%d.%m.%Y", "%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            pass

    return text


def format_beleg(value: Any) -> str:
    text = as_text(value)
    if text == "":
        return ""

    if text.upper().startswith("Z") and any(ch.isdigit() for ch in text):
        digits = "".join(ch for ch in text if ch.isdigit())
        if digits:
            return f"Z{int(digits):03d}"

    digits = "".join(ch for ch in text if ch.isdigit())
    if digits == "":
        return text.upper() if text.upper().startswith("Z") else text
    return f"Z{int(digits):03d}"


def date_sort_key(value: str) -> tuple[int, int, int, str]:
    text = as_text(value)
    if text == "":
        return (9999, 12, 31, text)

    for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%Y/%m/%d", "%d/%m/%Y"):
        try:
            dt = datetime.strptime(text, fmt)
            return (dt.year, dt.month, dt.day, text)
        except ValueError:
            pass

    return (9999, 12, 31, text)


def sort_rows_by_date(rows: Iterable[BuchungRow]) -> list[BuchungRow]:
    return sorted(rows, key=lambda row: (date_sort_key(row.datum), row.beleg_1, row.buchungstext))

