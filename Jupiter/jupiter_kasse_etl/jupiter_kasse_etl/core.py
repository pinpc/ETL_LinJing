from __future__ import annotations

from dataclasses import replace
from decimal import Decimal
from pathlib import Path

from .allopay import build_allopay_rows, read_allopay_pdf_data
from .cashbook import read_cashbook_rows
from .config import BU_GKTO_ALLOPAY_EXPENSE, BU_GKTO_FISCH_FOOD, MERGE_TOLERANCE
from .excel_export import build_workbook
from .models import BuchungRow, PipelineResult
from .utils import sort_rows_by_date


class JupiterKasseETL:
    def __init__(self) -> None:
        self.umsatz_rows: list[BuchungRow] = []
        self.allopay_rows: list[BuchungRow] = []
        self.final_rows: list[BuchungRow] = []

    def merge_final_rows(
        self,
        umsatz_rows: list[BuchungRow],
        allopay_rows: list[BuchungRow],
        allopay_payment_sum_by_date: dict[str, Decimal] | None = None,
    ) -> list[BuchungRow]:
        if allopay_payment_sum_by_date is None:
            allopay_payment_sum_by_date = {}

        if not umsatz_rows:
            return []

        if not allopay_rows:
            return sort_rows_by_date([replace(row, beleg_1="") for row in umsatz_rows])

        allopay_by_date: dict[str, list[BuchungRow]] = {}
        allopay_sum_by_date = {}
        safe_allopay_beleg_by_date = self._build_safe_allopay_beleg_by_date(allopay_rows)

        for row in allopay_rows:
            allopay_by_date.setdefault(row.datum, []).append(row)
            allopay_sum_by_date[row.datum] = allopay_sum_by_date.get(row.datum, 0) + row.umsatz_euro

        final_rows: list[BuchungRow] = []
        for row in umsatz_rows:
            is_allopay_income = row.umsatz_euro > 0 and "allo" in row.buchungstext.lower()
            if is_allopay_income and row.datum in allopay_sum_by_date:
                diff = abs(allopay_sum_by_date[row.datum] - row.umsatz_euro)
                if diff < MERGE_TOLERANCE:
                    final_rows.extend(
                        replace(allopay_row, beleg_1=safe_allopay_beleg_by_date.get(row.datum, ""))
                        for allopay_row in allopay_by_date[row.datum]
                    )
                    continue

            split_rows = self._split_compound_final_row(
                row,
                allopay_payment_sum_by_date,
                safe_allopay_beleg_by_date,
            )
            if split_rows is not None:
                final_rows.extend(split_rows)
                continue

            final_rows.append(self._assign_final_beleg(row, safe_allopay_beleg_by_date))

        return sort_rows_by_date(final_rows)

    def _build_safe_allopay_beleg_by_date(self, allopay_rows: list[BuchungRow]) -> dict[str, str]:
        belege_by_date: dict[str, set[str]] = {}
        for row in allopay_rows:
            beleg = row.beleg_1.strip()
            if beleg == "" or beleg == "Z000":
                continue
            belege_by_date.setdefault(row.datum, set()).add(beleg)

        return {
            datum: next(iter(belege)) if len(belege) == 1 else ""
            for datum, belege in belege_by_date.items()
        }

    def _split_compound_final_row(
        self,
        row: BuchungRow,
        allopay_payment_sum_by_date: dict[str, Decimal],
        safe_allopay_beleg_by_date: dict[str, str],
    ) -> list[BuchungRow] | None:
        text_lower = row.buchungstext.lower()
        is_compound_row = row.umsatz_euro < 0 and "+" in row.buchungstext and "allo" in text_lower
        if not is_compound_row:
            return None

        allopay_total = allopay_payment_sum_by_date.get(row.datum)
        if allopay_total is None or allopay_total <= 0:
            return None

        expense_total = abs(row.umsatz_euro)
        allopay_expense = min(expense_total, allopay_total).quantize(Decimal("0.01"))
        remainder_expense = (expense_total - allopay_expense).quantize(Decimal("0.01"))
        safe_allopay_beleg = safe_allopay_beleg_by_date.get(row.datum, "")

        split_rows = [
            replace(
                row,
                umsatz_euro=-allopay_expense,
                bu_gkto=BU_GKTO_ALLOPAY_EXPENSE,
                beleg_1=safe_allopay_beleg,
                buchungstext=f"alloPay {row.datum}",
            )
        ]

        if remainder_expense <= 0:
            return split_rows

        if "fisch" in text_lower:
            split_rows.append(
                replace(
                    row,
                    umsatz_euro=-remainder_expense,
                    bu_gkto=BU_GKTO_FISCH_FOOD,
                    beleg_1="",
                    buchungstext="Fisch Food",
                )
            )
            return split_rows

        if "bank" in text_lower:
            split_rows.append(
                replace(
                    row,
                    umsatz_euro=-remainder_expense,
                    bu_gkto=BU_GKTO_ALLOPAY_EXPENSE,
                    beleg_1="",
                    buchungstext="An Bank",
                )
            )
            return split_rows

        return None

    def _assign_final_beleg(
        self,
        row: BuchungRow,
        safe_allopay_beleg_by_date: dict[str, str],
    ) -> BuchungRow:
        text_lower = row.buchungstext.lower()
        if text_lower == "allo pay":
            return replace(
                row,
                beleg_1=safe_allopay_beleg_by_date.get(row.datum, ""),
                buchungstext=f"alloPay {row.datum}",
            )
        if "allo" in text_lower:
            return replace(row, beleg_1=safe_allopay_beleg_by_date.get(row.datum, ""))
        return replace(row, beleg_1="")

    def run(
        self,
        input_path: Path,
        output_path: Path,
        pdf_base_dir: Path | None = None,
        sheet_name: str | None = None,
    ) -> PipelineResult:
        if pdf_base_dir is None:
            pdf_base_dir = input_path.parent

        self.umsatz_rows = read_cashbook_rows(input_path, sheet_name=sheet_name)
        allopay_pdf_data = read_allopay_pdf_data(pdf_base_dir)
        self.allopay_rows = build_allopay_rows(allopay_pdf_data)
        self.final_rows = self.merge_final_rows(
            self.umsatz_rows,
            self.allopay_rows,
            {
                item.datum: item.allopay_payment_sum
                for item in allopay_pdf_data
                if item.datum != "" and item.allopay_payment_sum > 0
            },
        )

        saved_path, umsatz_count, allopay_count, final_count = build_workbook(
            self.umsatz_rows,
            self.allopay_rows,
            self.final_rows,
            output_path,
        )

        return PipelineResult(
            saved_path=saved_path,
            umsatz_count=umsatz_count,
            allopay_count=allopay_count,
            final_count=final_count,
            pdf_base_dir=pdf_base_dir,
        )


def run_cli(
    input_path: Path,
    output_path: Path,
    pdf_base_dir: Path | None = None,
    sheet_name: str | None = None,
) -> PipelineResult:
    return JupiterKasseETL().run(
        input_path=input_path,
        output_path=output_path,
        pdf_base_dir=pdf_base_dir,
        sheet_name=sheet_name,
    )
