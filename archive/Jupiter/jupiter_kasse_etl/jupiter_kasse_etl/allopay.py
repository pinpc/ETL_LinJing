from __future__ import annotations

import os
from pathlib import Path
import re

import pdfplumber

from .config import BU_GKTO_ALLOPAY_19, BU_GKTO_ALLOPAY_7, STANDARD_BANK, STANDARD_KOST
from .models import AllopayPdfData, BuchungRow
from decimal import Decimal

from .utils import convert_german_number, parse_money_amount, sort_rows_by_date


def _table_gross_amount(row: list) -> Decimal:
    """Rightmost amount column in Jupiter PDF tables (index 3)."""
    if not row:
        return Decimal("0")
    if len(row) >= 4 and row[3] is not None and str(row[3]).strip():
        value = parse_money_amount(row[3])
        if value != 0:
            return value
    for cell in reversed(row[1:]):
        if cell is None:
            continue
        value = parse_money_amount(cell)
        if value != 0:
            return value
    return Decimal("0")


def _find_allopay_pdfs(base_path: Path) -> list[Path]:
    pattern = re.compile(r"jupiter \d{2}-\d{2}-\d{4}\.pdf$", re.IGNORECASE)
    matched: list[Path] = []

    for root, _dirs, files in os.walk(base_path):
        for filename in files:
            if pattern.match(filename):
                matched.append(Path(root) / filename)

    return sorted(matched)


def _extract_allopay_from_pdf(pdf_path: Path) -> AllopayPdfData:
    umsatz_7 = convert_german_number(0)
    umsatz_19 = convert_german_number(0)
    allopay_payment_sum = convert_german_number(0)
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

        generiert_match = re.search(r"Generiert um:\s*(\d{2})-(\d{2})-(\d{4})", full_text)
        if generiert_match:
            datum = f"{generiert_match.group(1)}.{generiert_match.group(2)}.{generiert_match.group(3)}"
        else:
            date_match = re.search(r"jupiter (\d{2})-(\d{2})-(\d{4})\.pdf", pdf_path.name, re.IGNORECASE)
            if date_match:
                datum = f"{date_match.group(1)}.{date_match.group(2)}.{date_match.group(3)}"

        for page in pdf.pages:
            for table in page.extract_tables() or []:
                for row in table or []:
                    if not row or len(row) < 4:
                        continue

                    row_text = " ".join(str(cell) if cell else "" for cell in row)
                    first_cell = str(row[0]).strip().lower() if row[0] else ""
                    gross = _table_gross_amount(row)

                    if "Umsatz 7%" in row_text or "Umsatz 7 %" in row_text:
                        if gross > 0:
                            umsatz_7 = gross
                    if "Umsatz 19%" in row_text or "Umsatz 19 %" in row_text:
                        if gross > 0:
                            umsatz_19 = gross
                    if "allo" in first_cell and "pay" in first_cell:
                        if gross > 0:
                            allopay_payment_sum = max(allopay_payment_sum, gross)

        if umsatz_7 == 0 and umsatz_19 == 0:
            match_7 = re.search(
                r"Umsatz\s*7\s*%\D*([\d.,]+)\D+([\d.,]+)\D+([\d.,]+)",
                full_text,
                re.IGNORECASE,
            )
            if match_7:
                umsatz_7 = parse_money_amount(match_7.group(3))

            match_19 = re.search(
                r"Umsatz\s*19\s*%\D*([\d.,]+)\D+([\d.,]+)\D+([\d.,]+)",
                full_text,
                re.IGNORECASE,
            )
            if match_19:
                umsatz_19 = parse_money_amount(match_19.group(3))

        if allopay_payment_sum == 0:
            payment_match = re.search(
                r"allO\s*Pay\D*([\d.,]+)\D+([\d.,]+)\D+([\d.,]+)",
                full_text,
                re.IGNORECASE,
            )
            if payment_match:
                allopay_payment_sum = parse_money_amount(payment_match.group(3))

    return AllopayPdfData(
        datum=datum,
        z_nummer=z_nummer,
        umsatz_7=umsatz_7,
        umsatz_19=umsatz_19,
        allopay_payment_sum=allopay_payment_sum,
        dateiname=pdf_path.name,
    )


def read_allopay_pdf_data(pdf_base_dir: Path) -> list[AllopayPdfData]:
    data_items: list[AllopayPdfData] = []

    for pdf_path in _find_allopay_pdfs(pdf_base_dir):
        data = _extract_allopay_from_pdf(pdf_path)
        if data.datum != "":
            data_items.append(data)

    return sorted(data_items, key=lambda item: item.datum)


def build_allopay_rows(allopay_pdf_data: list[AllopayPdfData]) -> list[BuchungRow]:
    rows: list[BuchungRow] = []

    for data in allopay_pdf_data:
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
