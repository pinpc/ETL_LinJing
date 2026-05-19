"""Final-Blatt: AllOpay-Zeilen aus Buchungen durch Stripe-Splits ersetzen."""

from __future__ import annotations

import itertools
import logging
from datetime import datetime
from typing import Any

from openpyxl import load_workbook

from .excel_export import UMSATZ_EURO_NUMBERFORMAT, umsatz_zwei_nachkommastellen

logger = logging.getLogger(__name__)


def erstelle_final_blatt(workbook_path: str) -> None:
    """Erstellt Final-Blatt mit intelligenter Ersetzung von AllOpay-Buchungen durch Splits."""
    try:
        wb = load_workbook(workbook_path)
        ws_buchungen = wb["Kontoauszug"]
        ws_allopay = wb["Allopay"]

        if "Final" in wb.sheetnames:
            wb.remove(wb["Final"])
        ws_final = wb.create_sheet("Final")

        for row in [1, 2]:
            for col in range(1, ws_buchungen.max_column + 1):
                ws_final.cell(row, col, ws_buchungen.cell(row, col).value)

        allopay_items: list[dict[str, Any]] = []
        for row in range(2, ws_allopay.max_row + 1):
            datum_cell = ws_allopay.cell(row, 4)
            if not datum_cell.value:
                continue
            if isinstance(datum_cell.value, datetime):
                ap_datum = datum_cell.value.strftime("%d.%m.%Y")
            else:
                ap_datum = str(datum_cell.value).strip()

            betrag_cell = ws_allopay.cell(row, 1)
            betrag = betrag_cell.value
            if not isinstance(betrag, (int, float)):
                continue

            row_values = [
                ws_allopay.cell(row, col).value
                for col in range(1, ws_allopay.max_column + 1)
            ]

            allopay_items.append(
                {
                    "datum": ap_datum,
                    "betrag": betrag,
                    "row_values": row_values,
                    "used": False,
                }
            )

        target_row = 3
        replacements = 0

        for src_row in range(3, ws_buchungen.max_row + 1):
            src_sum_cell = ws_buchungen.cell(src_row, 1)
            if (
                isinstance(src_sum_cell.value, str)
                and src_sum_cell.value.strip().upper().startswith("=SUM")
            ):
                logger.debug(
                    "Überspringe Quell-Summenzeile in Buchungen: Zeile %s", src_row
                )
                continue

            text_cell = ws_buchungen.cell(src_row, 7)
            text = str(text_cell.value).strip() if text_cell.value else ""
            betrag_cell = ws_buchungen.cell(src_row, 1)
            betrag = betrag_cell.value
            datum_cell = ws_buchungen.cell(src_row, 4)
            if isinstance(datum_cell.value, datetime):
                datum = datum_cell.value.strftime("%d.%m.%Y")
            else:
                datum = str(datum_cell.value).strip() if datum_cell.value else ""

            # Sonderfall: Edeka EW im Final-Blatt in drei Zeilen splitten.
            # Nur die erste Zeile behält den Betrag; die Folgezeilen haben leeren Umsatz.
            if text.startswith(("Edeka EW", "Edeka WE")):
                split_rows = [
                    ("3300", "Edeka WE 7 %", True),
                    ("3400", "Edeka WE 19 %", False),
                    ("904250", "Edeka Reinigung", False),
                ]
                for _, (bu_gkto, buch_text, keep_amount) in enumerate(split_rows):
                    for col in range(1, ws_buchungen.max_column + 1):
                        val = ws_buchungen.cell(src_row, col).value
                        if col == 1:
                            val = umsatz_zwei_nachkommastellen(val) if keep_amount else None
                        elif col == 2:
                            val = int(bu_gkto)
                        elif col == 7:
                            val = buch_text
                        ws_final.cell(target_row, col, val)
                    target_row += 1
                continue

            if text.startswith("AllOpay") and isinstance(betrag, (int, float)):
                try:
                    buch_date = datetime.strptime(datum, "%d.%m.%Y")
                except ValueError:
                    logger.warning("Ungültiges Datum format: %s", datum)
                    buch_date = datetime.max

                candidates = [
                    item
                    for item in allopay_items
                    if not item["used"]
                    and datetime.strptime(item["datum"], "%d.%m.%Y") < buch_date
                ]
                target = round(betrag, 2)
                best_comb = _find_best_combination(candidates, target)

                if best_comb:
                    replacements += 1
                    logger.info(
                        "Ersetze %s (%.2f €) durch %s Allopay-Zeilen",
                        text,
                        betrag,
                        len(best_comb),
                    )
                    for item in best_comb:
                        item["used"] = True
                        for col_idx, val in enumerate(item["row_values"], 1):
                            if col_idx == 1:
                                val = umsatz_zwei_nachkommastellen(val)
                            ws_final.cell(target_row, col_idx, val)
                        target_row += 1
                    continue
                logger.warning(
                    "Keine passende Kombination für %s (%.2f €)", text, betrag
                )

            for col in range(1, ws_buchungen.max_column + 1):
                val = ws_buchungen.cell(src_row, col).value
                if col == 1:
                    val = umsatz_zwei_nachkommastellen(val)
                ws_final.cell(target_row, col, val)
            target_row += 1

        logger.info("%s Stripe-Buchungen ersetzt", replacements)

        last_data_row = target_row - 1
        summary_row = target_row

        ws_final.cell(summary_row, 7, "GESAMT")
        ws_final.cell(summary_row, 1, f"=SUM(A3:A{last_data_row})")

        for r in range(3, summary_row + 1):
            ca = ws_final.cell(r, 1)
            v = ca.value
            if isinstance(v, (int, float)) or (
                isinstance(v, str) and v.strip().upper().startswith("=SUM")
            ):
                ca.number_format = UMSATZ_EURO_NUMBERFORMAT

        wb.save(workbook_path)
        logger.info("Final-Blatt erstellt: %s", workbook_path)
    except Exception as e:
        logger.error("Fehler beim Erstellen des Final-Blatts: %s", e)
        raise


def _find_best_combination(
    candidates: list[dict[str, Any]],
    target: float,
    tolerance: float = 0.05,
) -> tuple[Any, ...] | None:
    """Findet beste Kombination von Kandidaten mit optimierter Suche (bis max 20 Kombinationen)."""
    if not candidates:
        return None

    limited_candidates = candidates[:20]
    limited_candidates.sort(key=lambda x: x["betrag"], reverse=True)

    for k in range(1, min(len(limited_candidates) + 1, 6)):
        for comb in itertools.combinations(limited_candidates, k):
            total = sum(c["betrag"] for c in comb)
            if abs(total - target) <= tolerance:
                return comb

    return None
