from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
import os
from pathlib import Path
import re

import pdfplumber

from .config import BU_GKTO_ALLOPAY_19, BU_GKTO_ALLOPAY_7, STANDARD_BANK, STANDARD_KOST
from .models import BuchungRow
from .utils import as_text, convert_number, sort_rows_by_date


@dataclass(frozen=True)
class AllopayPdfData:
    datum: str
    z_nummer: str
    umsatz_7: Decimal
    umsatz_19: Decimal
    dateiname: str


def _find_allopay_pdfs(base_path: Path) -> list[Path]:
    pattern = re.compile(r"asia[ _]\d{2}[-_.]\d{2}[-_.]\d{4}\.pdf$", re.IGNORECASE)
    matched: list[Path] = []

    for root, _dirs, files in os.walk(base_path):
        for filename in files:
            if not filename.lower().endswith(".pdf"):
                continue
            if pattern.match(filename):
                matched.append(Path(root) / filename)

    return sorted(matched)


def _extract_allopay_from_pdf(pdf_path: Path) -> AllopayPdfData:
    umsatz_7 = Decimal("0")
    umsatz_19 = Decimal("0")
    datum = ""
    z_nummer = ""

    with pdfplumber.open(str(pdf_path)) as pdf:
        full_text = ""
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                full_text += text + "\n"

        z_match = re.search(r"Z-Nummer\s*\(Berichtnummer\):\s*(\d+)", full_text, re.IGNORECASE)
        if z_match:
            z_nummer = z_match.group(1)

        gen_match = re.search(r"Generiert um:\s*(\d{2})-(\d{2})-(\d{4})", full_text)
        if gen_match:
            datum = f"{gen_match.group(1)}.{gen_match.group(2)}.{gen_match.group(3)}"
        else:
            name_match = re.search(r"asia[ _](\d{2})-(\d{2})-(\d{4})\.pdf", pdf_path.name, re.IGNORECASE)
            if name_match:
                datum = f"{name_match.group(1)}.{name_match.group(2)}.{name_match.group(3)}"

        for page in pdf.pages:
            for table in page.extract_tables() or []:
                for table_row in table or []:
                    if not table_row:
                        continue
                    row_text = " ".join(str(cell) if cell else "" for cell in table_row)
                    if "Umsatz 7%" in row_text or "Umsatz 7 %" in row_text:
                        numbers = re.findall(r"(\d+(?:[.,]\d+)?)", row_text)
                        if numbers:
                            umsatz_7 = convert_number(numbers[-1])
                    if "Umsatz 19%" in row_text or "Umsatz 19 %" in row_text:
                        numbers = re.findall(r"(\d+(?:[.,]\d+)?)", row_text)
                        if numbers:
                            umsatz_19 = convert_number(numbers[-1])

        if umsatz_7 == 0:
            match_7 = re.search(
                r"Umsatz\s*7\s*%\s*(?:€\s*)?([\d.,]+)\s*(?:€\s*)?([\d.,]+)\s*(?:€\s*)?([\d.,]+)",
                full_text,
            )
            if match_7:
                umsatz_7 = convert_number(match_7.group(3))

        if umsatz_19 == 0:
            match_19 = re.search(
                r"Umsatz\s*19\s*%\s*(?:€\s*)?([\d.,]+)\s*(?:€\s*)?([\d.,]+)\s*(?:€\s*)?([\d.,]+)",
                full_text,
            )
            if match_19:
                umsatz_19 = convert_number(match_19.group(3))

    return AllopayPdfData(
        datum=datum,
        z_nummer=z_nummer,
        umsatz_7=umsatz_7,
        umsatz_19=umsatz_19,
        dateiname=pdf_path.name,
    )


def read_allopay_rows(pdf_base_dir: Path) -> list[BuchungRow]:
    rows: list[BuchungRow] = []

    for pdf_path in _find_allopay_pdfs(pdf_base_dir):
        data = _extract_allopay_from_pdf(pdf_path)
        if as_text(data.datum) == "":
            continue

        beleg = f"Z{str(data.z_nummer).zfill(3)}" if data.z_nummer else "Z000"

        if data.umsatz_19 > 0:
            rows.append(
                BuchungRow(
                    umsatz_euro=data.umsatz_19,
                    bu_gkto=BU_GKTO_ALLOPAY_19,
                    beleg_1=beleg,
                    datum=data.datum,
                    kost_1=STANDARD_KOST,
                    bank=STANDARD_BANK,
                    buchungstext="Umsatz 19 %",
                )
            )

        if data.umsatz_7 > 0:
            rows.append(
                BuchungRow(
                    umsatz_euro=data.umsatz_7,
                    bu_gkto=BU_GKTO_ALLOPAY_7,
                    beleg_1=beleg,
                    datum=data.datum,
                    kost_1=STANDARD_KOST,
                    bank=STANDARD_BANK,
                    buchungstext="Umsatz 7 %",
                )
            )

    return sort_rows_by_date(rows)

