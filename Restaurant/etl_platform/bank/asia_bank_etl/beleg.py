"""Beleg-Nummer aus Kontoauszug-Dateiname (Monatsnummer)."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

_RE_YYYY_MM = re.compile(r"(20\d{2})[_-](\d{2})")
_RE_DATUM_DE = re.compile(r"\d{2}\.(\d{2})\.(20\d{2})")
_RE_DATUM_ISO = re.compile(r"(20\d{2})-(\d{2})-\d{2}")


def beleg_month_from_pdf(
    pdf_path: str,
    pdf_rows: list[dict[str, Any]] | None = None,
) -> str:
    """
    Liefert Beleg 1 als Monatsnummer (z. B. ``05``).

    Primär aus Dateiname ``Kontoauszug 2026_05.pdf``, sonst aus erster Buchungszeile.
    """
    m = _RE_YYYY_MM.search(Path(pdf_path).name)
    if m:
        return m.group(2)

    if pdf_rows:
        datum = str(pdf_rows[0].get("Datum") or "")
        m = _RE_DATUM_DE.search(datum)
        if m:
            return m.group(1)
        m = _RE_DATUM_ISO.search(datum)
        if m:
            return m.group(2)

    return "01"
