"""Hilfsfunktionen: Ausgangsrechnungs-PDF finden und Brutto-Betrag + Datum lesen.

Unterstützte Rechnungsnummer-Formate und Dateibenennungen:
  NNN/YYYY  →  RE NNN-YYYY*.pdf       (z. B. RE 006-2026_DOG Massion.pdf)
  JJJJ-NNN  →  *JJJJ-NNN*.pdf        (z. B. Ping Zhou_2026-008_Fibu 12 2025_ctm.pdf)
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
    r"|Gesamt\s*\(Brutto\)[:\s]+([\d.,]+)"   # "Gesamt (Brutto): 303,45 €"
    r"|Rechnungsendbetrag[:\s]+([\d.,]+)"    # DOG-Ausgangsrechnung
)
# "Rechnungsdatum" kann als Spaltenheader oder mit Doppelpunkt stehen
_RE_RECHNUNG_DATUM = re.compile(
    r"Rechnungsdatum[:\s]+(\d{2}\.\d{2}\.\d{4})"        # gleiche Zeile mit : oder Leer
    r"|Rechnungsdatum\n[^\n]*?(\d{2}\.\d{2}\.\d{4})"    # Datum in nächster Zeile
)
_RE_REF_NNN_YYYY  = re.compile(r"^(\d+)/(\d{4})$")       # "006/2026"
_RE_REF_JJJJ_NNN = re.compile(r"^(20\d{2}-\d{3})$")     # "2026-008"
_RE_FIBU_MONTH = re.compile(r"Fibu\s+(\d{1,2})\s+(20\d{2})", re.IGNORECASE)


def _parse_german_decimal(s: str) -> Decimal:
    """'5.572,18' → Decimal('5572.18')"""
    return Decimal(s.replace(".", "").replace(",", "."))


def _invoice_glob(ref: str, search_dir: Path) -> Path | None:
    """Eine Suche in search_dir; None wenn Ordner fehlt oder kein Treffer."""
    if not search_dir.exists():
        return None
    ref = ref.strip()
    m = _RE_REF_NNN_YYYY.match(ref)
    if m:
        nr, year = m.group(1), m.group(2)
        hits = sorted(search_dir.rglob(f"RE {nr}-{year}*.pdf"))
        return hits[0] if hits else None
    m = _RE_REF_JJJJ_NNN.match(ref)
    if m:
        hits = sorted(search_dir.rglob(f"*{ref}*.pdf"))
        return hits[0] if hits else None
    return None


def _fibu_search_dirs(search_dir: Path) -> list[Path]:
    """Aktueller Fibu-Ordner plus vorherige Monate (ohne Parent-Listing)."""
    dirs: list[Path] = []
    seen: set[str] = set()

    def add(path: Path) -> None:
        key = str(path).lower()
        if key not in seen:
            seen.add(key)
            dirs.append(path)

    add(search_dir)
    fibu = None
    if _RE_FIBU_MONTH.search(search_dir.name):
        fibu = search_dir
    elif _RE_FIBU_MONTH.search(search_dir.parent.name):
        fibu = search_dir.parent
        add(fibu)
    if fibu is None:
        return dirs
    m = _RE_FIBU_MONTH.search(fibu.name)
    mm, yyyy = int(m.group(1)), int(m.group(2))
    parent = fibu.parent
    for delta in range(1, 7):
        month = mm - delta
        year = yyyy
        if month <= 0:
            month += 12
            year -= 1
        for cand in (parent / f"Fibu {month:02d} {year}", parent / f"Fibu {month} {year}"):
            if cand.exists():
                add(cand)
    return dirs


def find_invoice_pdf(ref: str, search_dir: Path) -> Path | None:
    """Findet PDF rekursiv in search_dir passend zur Rechnungsnummer.

    NNN/YYYY  → sucht 'RE NNN-YYYY*.pdf'   (z. B. 006/2026 → RE 006-2026*.pdf)
    JJJJ-NNN  → sucht '*JJJJ-NNN*.pdf'    (z. B. 2026-008 → *2026-008*.pdf)

    Zusätzlich: vorherige Fibu-Monate desselben Mandanten (Zahlung oft später).
    """
    for folder in _fibu_search_dirs(search_dir):
        hit = _invoice_glob(ref, folder)
        if hit is not None:
            return hit
    return None


@lru_cache(maxsize=64)
def read_invoice_pdf(pdf_path: Path) -> tuple[Decimal, date | None]:
    """Liest Rechnungsbetrag (Brutto) und Rechnungsdatum aus einer Rechnungs-PDF.
    Ergebnisse werden gecacht (gleicher Pfad wird nur einmal gelesen)."""
    with pdfplumber.open(str(pdf_path)) as pdf:
        text = "\n".join(p.extract_text() or "" for p in pdf.pages)

    # Betrag
    m = _RE_BRUTTO.search(text)
    raw_amt = next((g for g in m.groups() if g), None) if m else None
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
