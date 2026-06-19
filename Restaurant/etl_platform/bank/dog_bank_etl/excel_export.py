"""Schreibt ein Agenda-kompatibles Excel-Blatt 'Kontoauszug'."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import NamedTuple

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

SHEET_NAME = "Kontoauszug"

_HEADERS = ("Datum", "Betrag", "Gegenkonto", "Konto", "Buchungstext")
_COL_WIDTHS = (12, 14, 14, 10, 70)

_HEADER_FILL = PatternFill("solid", fgColor="4472C4")
_HEADER_FONT = Font(bold=True, color="FFFFFF")

_DATE_FMT = "DD.MM.YYYY"
_AMOUNT_FMT = '#,##0.00;[Red]-#,##0.00'


class ExportRow(NamedTuple):
    datum: date
    betrag: Decimal
    gegenkonto: str   # leer wenn unbekannt
    konto: str        # Bankkonto des Tenants (z.B. "1200")
    buchungstext: str


def write_excel(rows: list[ExportRow], output_path: str | Path) -> Path:
    """Schreibt rows in ein neues Excel-File mit Sheet 'Kontoauszug'."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    wb = Workbook()
    ws = wb.active
    ws.title = SHEET_NAME

    # Header
    for col, (header, width) in enumerate(zip(_HEADERS, _COL_WIDTHS), start=1):
        cell = ws.cell(row=1, column=col, value=header)
        cell.font = _HEADER_FONT
        cell.fill = _HEADER_FILL
        cell.alignment = Alignment(horizontal="center")
        ws.column_dimensions[get_column_letter(col)].width = width

    ws.freeze_panes = "A2"

    # Datenzeilen
    for row_idx, row in enumerate(rows, start=2):
        ws.cell(row=row_idx, column=1, value=row.datum).number_format = _DATE_FMT
        amount_cell = ws.cell(row=row_idx, column=2, value=float(row.betrag))
        amount_cell.number_format = _AMOUNT_FMT
        ws.cell(row=row_idx, column=3, value=row.gegenkonto)
        ws.cell(row=row_idx, column=4, value=row.konto)
        ws.cell(row=row_idx, column=5, value=row.buchungstext)

    wb.save(str(output_path))
    return output_path
