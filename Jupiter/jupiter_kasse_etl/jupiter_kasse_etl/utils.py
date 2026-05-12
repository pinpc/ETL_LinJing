from __future__ import annotations

from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Iterable

from .models import BuchungRow


def as_text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def convert_german_number(value: Any) -> Decimal:
    if value is None:
        return Decimal("0")
    if isinstance(value, Decimal):
        return value
    if isinstance(value, (int, float)):
        return Decimal(str(value))

    text = str(value).strip().replace("EUR", "").replace("€", "").strip()
    if text == "":
        return Decimal("0")

    text = text.replace(" ", "")
    if "." in text and "," in text:
        text = text.replace(".", "").replace(",", ".")
    elif "," in text:
        parts = text.split(",")
        if len(parts) == 2 and len(parts[1]) == 2:
            text = text.replace(",", ".")
        else:
            text = text.replace(",", ".")
    elif "." in text:
        if text.count(".") > 1:
            text = text.replace(".", "")
        else:
            parts = text.split(".")
            if len(parts) == 2 and len(parts[1]) != 2:
                text = text.replace(".", "")

    try:
        return Decimal(text)
    except InvalidOperation:
        return Decimal("0")


def parse_date(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.strftime("%d.%m.%Y")

    text = str(value).strip()
    if text == "":
        return ""

    for fmt in ("%d.%m.%Y", "%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(text, fmt).strftime("%d.%m.%Y")
        except ValueError:
            pass

    return text


def date_sort_key(value: str) -> tuple[int, int, int, str]:
    text = as_text(value)
    if text == "":
        return (9999, 12, 31, text)

    for fmt in ("%d.%m.%Y", "%Y-%m-%d", "%Y/%m/%d", "%d/%m/%Y"):
        try:
            dt = datetime.strptime(text, fmt)
            return (dt.year, dt.month, dt.day, text)
        except ValueError:
            pass

    return (9999, 12, 31, text)


def sort_rows_by_date(rows: Iterable[BuchungRow]) -> list[BuchungRow]:
    return sorted(rows, key=lambda row: (date_sort_key(row.datum), row.beleg_1, row.buchungstext))
