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

# Agenda-Spaltenreihenfolge
_HEADERS = ("Umsatz", "BU Gkto", "Beleg1", "Beleg2", "Datum", "Konto", "Buchungstext", "Skonto Euro")
_COL_WIDTHS = (14, 10, 12, 12, 12, 10, 70, 12)

_HEADER_FILL = PatternFill(fill_type=None)
_HEADER_FONT = Font(bold=True, color="000000")

_DATE_FMT = "DD.MM.YYYY"
_AMOUNT_FMT = '#,##0.00;-#,##0.00'


class ExportRow(NamedTuple):
    umsatz: Decimal       # Betrag (negativ = Ausgabe, positiv = Einnahme)
    bu_gkto: str          # Gegenkonto / BU-Konto
    beleg1: str           # Belegnummer 1 (leer wenn unbekannt)
    beleg2: str           # Belegnummer 2 (leer wenn unbekannt)
    datum: date
    konto: str            # Bankkonto des Tenants (z.B. "1200")
    buchungstext: str
    skonto_euro: Decimal  # Skonto-Betrag (meist 0,00)


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

    _TOP = Alignment(vertical="top")

    # Datenzeilen
    for row_idx, row in enumerate(rows, start=2):
        umsatz_cell = ws.cell(row=row_idx, column=1, value=float(row.umsatz))
        umsatz_cell.number_format = _AMOUNT_FMT
        umsatz_cell.alignment = _TOP

        cell_bu = ws.cell(row=row_idx, column=2, value=str(row.bu_gkto))
        cell_bu.number_format = "@"
        cell_bu.alignment = _TOP

        cell_b1 = ws.cell(row=row_idx, column=3, value=str(row.beleg1))
        cell_b1.number_format = "@"
        cell_b1.alignment = _TOP

        cell_b2 = ws.cell(row=row_idx, column=4, value=str(row.beleg2))
        cell_b2.number_format = "@"
        cell_b2.alignment = _TOP

        datum_cell = ws.cell(row=row_idx, column=5, value=row.datum)
        datum_cell.number_format = _DATE_FMT
        datum_cell.alignment = _TOP

        cell_kto = ws.cell(row=row_idx, column=6, value=str(row.konto))
        cell_kto.number_format = "@"
        cell_kto.alignment = _TOP

        bt_cell = ws.cell(row=row_idx, column=7, value=row.buchungstext)
        bt_cell.alignment = Alignment(wrap_text=True, vertical="top")

        skonto_cell = ws.cell(row=row_idx, column=8, value=float(row.skonto_euro))
        skonto_cell.number_format = _AMOUNT_FMT
        skonto_cell.alignment = _TOP

    wb.save(str(output_path))
    return output_path
