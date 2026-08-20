"""Tests for Monatsbericht vs Final check (Asia/Jupiter cashbook)."""

from __future__ import annotations

import unittest
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

from Restaurant.etl_platform.cashbook.monatsbericht_check import (
    sum_final_tax_totals,
    verify_final_against_monatsbericht,
)


class MonatsberichtCheckTests(unittest.TestCase):
    def test_sum_final_tax_totals_positive_tips_only(self) -> None:
        rows = [
            SimpleNamespace(umsatz_euro=Decimal("100.00"), buchungstext="Umsatz 7 %"),
            SimpleNamespace(umsatz_euro=Decimal("20.00"), buchungstext="Umsatz 19 %"),
            SimpleNamespace(umsatz_euro=Decimal("5.00"), buchungstext="Trinkgeld"),
            SimpleNamespace(umsatz_euro=Decimal("-5.00"), buchungstext="Trinkgeld"),
        ]
        u7, u19, tips = sum_final_tax_totals(
            rows,
            text_umsatz_7="Umsatz 7 %",
            text_umsatz_19="Umsatz 19 %",
            text_trinkgeld="Trinkgeld",
        )
        self.assertEqual(u7, Decimal("100.00"))
        self.assertEqual(u19, Decimal("20.00"))
        self.assertEqual(tips, Decimal("5.00"))

    def test_verify_without_pdf_reports_missing(self) -> None:
        rows = [
            SimpleNamespace(umsatz_euro=Decimal("1.00"), buchungstext="Umsatz 7 %"),
        ]
        result = verify_final_against_monatsbericht(
            rows,
            pdf_base_dir=Path("C:/__missing_monatsbericht__"),
            text_umsatz_7="Umsatz 7 %",
            text_umsatz_19="Umsatz 19 %",
            text_trinkgeld="Trinkgeld",
        )
        self.assertFalse(result.ok)
        self.assertIn("Kein Monatsbericht", result.message)


if __name__ == "__main__":
    unittest.main()
