from __future__ import annotations

from dataclasses import replace
from decimal import Decimal
from pathlib import Path

from .allopay import read_allopay_rows
from .cashbook import read_cashbook_rows
from .config import MERGE_TOLERANCE
from .excel_export import build_workbook
from .models import BuchungRow, PipelineResult
from .utils import date_sort_key, sort_rows_by_date


class AsiaKasseETL:
    def __init__(self) -> None:
        self.buchung_rows: list[BuchungRow] = []
        self.allopay_rows: list[BuchungRow] = []
        self.final_rows: list[BuchungRow] = []

    def merge_final_rows(self, buchung_rows: list[BuchungRow], allopay_rows: list[BuchungRow]) -> list[BuchungRow]:
        def normalize_final_text(row: BuchungRow) -> BuchungRow:
            if row.buchungstext.strip().lower() == "bankeinzahlung":
                return replace(row, buchungstext="an Bank")
            return row

        if not buchung_rows:
            return []

        if not allopay_rows:
            return sort_rows_by_date([normalize_final_text(row) for row in buchung_rows])

        allopay_by_date: dict[tuple[int, int, int], list[BuchungRow]] = {}
        allopay_sum_by_date: dict[tuple[int, int, int], Decimal] = {}

        for row in allopay_rows:
            key = date_sort_key(row.datum)[:3]
            allopay_by_date.setdefault(key, []).append(row)
            allopay_sum_by_date[key] = allopay_sum_by_date.get(key, Decimal("0")) + row.umsatz_euro

        final_rows: list[BuchungRow] = []
        for row in buchung_rows:
            key = date_sort_key(row.datum)[:3]
            is_allopay_income = row.umsatz_euro > 0 and "allo" in row.buchungstext.lower()

            if is_allopay_income and key in allopay_sum_by_date:
                diff = abs(allopay_sum_by_date[key] - row.umsatz_euro)
                if diff <= MERGE_TOLERANCE:
                    final_rows.extend(normalize_final_text(allopay_row) for allopay_row in allopay_by_date[key])
                    continue

            final_rows.append(normalize_final_text(row))

        return sort_rows_by_date(final_rows)

    def run(
        self,
        input_path: Path,
        output_path: Path,
        pdf_base_dir: Path | None = None,
        sheet_name: str = "cashbook",
    ) -> PipelineResult:
        if pdf_base_dir is None:
            pdf_base_dir = input_path.parents[2]

        self.buchung_rows = read_cashbook_rows(input_path, sheet_name=sheet_name)
        self.allopay_rows = read_allopay_rows(pdf_base_dir)
        self.final_rows = self.merge_final_rows(self.buchung_rows, self.allopay_rows)

        saved_path, buchung_count, allopay_count, final_count = build_workbook(
            self.buchung_rows,
            self.allopay_rows,
            self.final_rows,
            output_path,
        )

        return PipelineResult(
            saved_path=saved_path,
            buchung_count=buchung_count,
            allopay_count=allopay_count,
            final_count=final_count,
            pdf_base_dir=pdf_base_dir,
        )


def run_cli(
    input_path: Path,
    output_path: Path,
    pdf_base_dir: Path | None = None,
    sheet_name: str = "cashbook",
) -> PipelineResult:
    return AsiaKasseETL().run(input_path, output_path, pdf_base_dir=pdf_base_dir, sheet_name=sheet_name)

