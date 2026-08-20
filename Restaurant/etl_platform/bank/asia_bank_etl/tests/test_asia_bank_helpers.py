"""Unit tests for Asia bank helpers (Beleg, Darlehen-Split, Mapping)."""

from __future__ import annotations

import unittest

from Restaurant.etl_platform.bank.asia_bank_etl.beleg import beleg_month_from_pdf
from Restaurant.etl_platform.bank.asia_bank_etl.buchungstext_mapping import (
    apply_buchungs_mapping,
)
from Restaurant.etl_platform.bank.asia_bank_etl.darlehen_split import (
    expand_sparkasse_darlehen_rows,
)
from Restaurant.etl_platform.bank.asia_bank_etl.final_sheet import (
    _find_best_combination,
    _format_allopay_day_range,
)


class BelegMonthTests(unittest.TestCase):
    def test_from_filename_underscore(self) -> None:
        self.assertEqual(
            beleg_month_from_pdf(r"C:\data\01b Kontoauszug 2026_05.pdf"),
            "05",
        )

    def test_from_filename_dash(self) -> None:
        self.assertEqual(
            beleg_month_from_pdf(r"C:\data\Kontoauszug 2026-04.pdf"),
            "04",
        )

    def test_fallback_from_first_row(self) -> None:
        rows = [{"Datum": "15.07.2026"}]
        self.assertEqual(beleg_month_from_pdf(r"C:\data\auszug.pdf", rows), "07")


class DarlehenSplitTests(unittest.TestCase):
    def test_split_tilgung_zins(self) -> None:
        text = (
            "Abbuchung Lastschrift SPARKASSE ALLGAEU Rechnung Darl.-Leistung 6205679498 "
            "Tilgung 1.130,01 Zinsen 27,11 Für 01.05.2026-31.05.2026"
        )
        rows = expand_sparkasse_darlehen_rows(
            [{"Umsatz Euro": -1157.12, "Datum": "29.05.2026", "Buchungstext": text}]
        )
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["Umsatz Euro"], -1130.01)
        self.assertEqual(rows[0]["BU Gkto"], "631")
        self.assertIn("Tilgung 05 2026", rows[0]["Buchungstext"])
        self.assertEqual(rows[1]["Umsatz Euro"], -27.11)
        self.assertEqual(rows[1]["BU Gkto"], "2120")
        self.assertIn("Zins 05 2026", rows[1]["Buchungstext"])
        self.assertTrue(rows[0]["_skip_buchung_mapping"])

    def test_no_split_without_amounts(self) -> None:
        rows = expand_sparkasse_darlehen_rows(
            [
                {
                    "Umsatz Euro": -100.0,
                    "Datum": "01.05.2026",
                    "Buchungstext": "SPARKASSE ALLGAEU Rechnung Darl ohne Beträge",
                }
            ]
        )
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["Umsatz Euro"], -100.0)


class BuchungstextMappingTests(unittest.TestCase):
    def test_kfz_period_from_bank_text(self) -> None:
        rows = [
            {
                "Umsatz Euro": -154.0,
                "Datum": "04.05.2026",
                "Buchungstext": (
                    "Abbuchung Lastschrift Bundeskasse Kfz-Steuer fuer FUES LJ 888 "
                    "fuer di e Zeit vom 02.05.2026 bis zum 01.05 .2027 Kassenzeichen"
                ),
            }
        ]
        apply_buchungs_mapping(rows)
        self.assertEqual(rows[0]["BU Gkto"], "4510")
        self.assertEqual(
            rows[0]["Buchungstext"],
            "Kfz-Steuer fuer FUES LJ 888 05 2026 - 04 2027",
        )

    def test_aok_single_row_no_hardcoded_split(self) -> None:
        rows = [
            {
                "Umsatz Euro": -5705.75,
                "Datum": "15.05.2026",
                "Buchungstext": (
                    "Überweisung Online AOK Bayern Betriebsnummer 95739729, "
                    "01.04.2026 --30.04.2026 DATUM 15.05.2026, 00.20 UHR"
                ),
            }
        ]
        apply_buchungs_mapping(rows)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["BU Gkto"], "1743")
        self.assertEqual(rows[0]["Buchungstext"], "AOK Bayern Beitrag 04 2026")
        self.assertEqual(rows[0]["Umsatz Euro"], -5705.75)


class AllopaySammelTests(unittest.TestCase):
    def test_three_day_net_match(self) -> None:
        candidates = [
            {"datum": "27.06.2026", "betrag": 78.0, "row_values": [], "used": False},
            {"datum": "27.06.2026", "betrag": -2.8, "row_values": [], "used": False},
            {"datum": "28.06.2026", "betrag": 109.5, "row_values": [], "used": False},
            {"datum": "28.06.2026", "betrag": -1.22, "row_values": [], "used": False},
            {"datum": "29.06.2026", "betrag": 392.0, "row_values": [], "used": False},
            {"datum": "29.06.2026", "betrag": -13.64, "row_values": [], "used": False},
        ]
        items, days = _find_best_combination(candidates, 561.84)
        self.assertIsNotNone(items)
        self.assertEqual(days, ["27.06.2026", "28.06.2026", "29.06.2026"])
        self.assertEqual(len(items), 6)
        self.assertEqual(_format_allopay_day_range(days), "27-29.06.2026")

    def test_max_three_days_only(self) -> None:
        candidates = [
            {"datum": f"{d:02d}.06.2026", "betrag": 10.0, "row_values": [], "used": False}
            for d in range(1, 5)
        ]
        items, days = _find_best_combination(candidates, 40.0)
        self.assertIsNone(items)
        self.assertEqual(days, [])


if __name__ == "__main__":
    unittest.main()
