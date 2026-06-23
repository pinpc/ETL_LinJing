"""Hilfsfunktionen: Ausgangsrechnungs-PDF finden und Brutto-Betrag + Datum lesen.

Namenskonvention der RE-Dateien:  RE NNN-YYYY<beliebig>.pdf
Beispiel:  RE 006-2026_DOG Massion.pdf  →  Rechnungsnr. 006/2026
"""

from __future__ import annotations

import re
from datetime import date
from decimal import Decimal
from functools import lru_cache
from pathlib import Path

import pdfplumber

_RE_BRUTTO = re.compile(
    r"(?:Gesamt\s*\(Brutto\)\s*/?\s*)?Rechnungsbetrag\s+([\d.,]+)"
    r"|Gesamt\s*\(Brutto\)\s+([\d.,]+)"
)
# "Rechnungsdatum" kann als Spaltenheader stehen; Datum dann in nächster Zeile am Ende
_RE_RECHNUNG_DATUM = re.compile(
    r"Rechnungsdatum\s+(\d{2}\.\d{2}\.\d{4})"          # Datum gleiche Zeile
    r"|Rechnungsdatum\n[^\n]*?(\d{2}\.\d{2}\.\d{4})"   # Datum nächste Zeile
)
_RE_INVOICE_REF = re.compile(r"^(\d+)/(\d{4})$")


def _parse_german_decimal(s: str) -> Decimal:
    """'5.572,18' → Decimal('5572.18')"""
    return Decimal(s.replace(".", "").replace(",", "."))


def find_invoice_pdf(ref: str, search_dir: Path) -> Path | None:
    """Findet PDF für Rechnungsnummer '006/2026' (Muster: RE 006-2026*.pdf).
    Sucht rekursiv in search_dir."""
    m = _RE_INVOICE_REF.match(ref.strip())
    if not m:
        return None
    nr, year = m.group(1), m.group(2)
    pattern = f"RE {nr}-{year}*.pdf"
    hits = list(search_dir.rglob(pattern))
    return hits[0] if hits else None


@lru_cache(maxsize=64)
def read_invoice_pdf(pdf_path: Path) -> tuple[Decimal, date | None]:
    """Liest Rechnungsbetrag (Brutto) und Rechnungsdatum aus Ausgangsrechnung-PDF.
    Gibt (betrag, datum) zurück; datum=None wenn nicht gefunden.
    Ergebnisse werden gecacht (gleicher Pfad wird nur einmal gelesen)."""
    with pdfplumber.open(str(pdf_path)) as pdf:
        text = "\n".join(p.extract_text() or "" for p in pdf.pages)

    # Betrag
    m = _RE_BRUTTO.search(text)
    raw_amt = (m.group(1) or m.group(2)) if m else None
    betrag = _parse_german_decimal(raw_amt) if raw_amt else Decimal("0")

    # Datum (Gruppe 1 = gleiche Zeile, Gruppe 2 = nächste Zeile)
    dm = _RE_RECHNUNG_DATUM.search(text)
    rechnung_date: date | None = None
    if dm:
        date_str = dm.group(1) or dm.group(2)
        d, mo, y = date_str.split(".")
        rechnung_date = date(int(y), int(mo), int(d))

    return betrag, rechnung_date


def lookup_invoice(ref: str, search_dir: Path) -> tuple[Decimal, date | None]:
    """Findet PDF für ref und gibt (brutto_betrag, rechnungsdatum) zurück.
    Falls PDF nicht gefunden: (Decimal('0'), None)."""
    pdf_path = find_invoice_pdf(ref, search_dir)
    if pdf_path is None:
        return Decimal("0"), None
    return read_invoice_pdf(pdf_path)
