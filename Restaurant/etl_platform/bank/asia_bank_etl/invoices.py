"""Asia bank invoice parsers (PDF) — dispatcher + supplier-specific extractors."""

from __future__ import annotations

import logging
import re
import sys
from dataclasses import dataclass
from pathlib import Path

try:
    from ..pdf_invoice_common import (
        extract_pdf_text,
        last_german_euro_amounts,
        parse_german_euro_amount,
    )
except ImportError:
    _bank_root = Path(__file__).resolve().parent.parent
    if str(_bank_root) not in sys.path:
        sys.path.insert(0, str(_bank_root))
    from pdf_invoice_common import (
        extract_pdf_text,
        last_german_euro_amounts,
        parse_german_euro_amount,
    )

logger = logging.getLogger(__name__)

_EDEKA_CC_GLOB = "*C+C Grossmarkt*.pdf"
_WASH_SECTION = re.compile(r"Wasch/Putz/Reinigung", re.I)
_RE_NR = re.compile(r"Rechnung-Nr\.?\s*:?\s*(\d+)", re.I)
_RE_DATUM = re.compile(r"Rechnungsdatum\s*:\s*(\d{2}\.\d{2}\.\d{4})", re.I)
_MWST_7_LINE = re.compile(r"7\s*,\s*00\s*=\s*1", re.I)
_MWST_19_LINE = re.compile(r"19\s*,\s*00\s*=\s*2", re.I)


@dataclass
class EdekaInvoiceRow:
    """Parsed C+C / EDEKA Grossmarkt invoice row for the EDEKA Excel sheet."""

    datei: str
    rechnung_nr: str
    rechnungsdatum: str
    we_7_gesamt: float | None
    we_19_gesamt: float | None
    we_19_ohne_reinigung: float | None
    reinigung: float
    gesamtbetrag: float | None
    summe_7_19: float | None
    parse_ok: bool
    hinweis: str

    def as_excel_dict(self) -> dict[str, object]:
        return {
            "Datei": self.datei,
            "Rechnung-Nr": self.rechnung_nr,
            "Rechnungsdatum": self.rechnungsdatum,
            "WE 7 % Gesamt": self.we_7_gesamt,
            "WE 19 % Gesamt": self.we_19_gesamt,
            "WE 19 % ohne Reinigung": self.we_19_ohne_reinigung,
            "Reinigung Wash/Putz": self.reinigung if self.reinigung else None,
            "Gesamtbetrag": self.gesamtbetrag,
            "Summe 7 % + 19 %": self.summe_7_19,
            "Parse OK": "Ja" if self.parse_ok else "Nein",
            "Hinweis": self.hinweis,
        }


def load_invoices(source_dir: str | Path) -> list[EdekaInvoiceRow]:
    """Scan *source_dir* and parse all supported supplier invoice PDFs."""
    root = Path(source_dir)
    if not root.is_dir():
        return []

    rows: list[EdekaInvoiceRow] = []
    rows.extend(_scan_edeka_cc_invoices(root))
    logger.info("Asia invoices: %s Rechnung(en) aus %s", len(rows), root)
    return rows


def scan_edeka_invoices(source_dir: str | Path) -> list[EdekaInvoiceRow]:
    """Backward-compatible alias for C+C / EDEKA Grossmarkt invoices only."""
    root = Path(source_dir)
    if not root.is_dir():
        return []
    rows = _scan_edeka_cc_invoices(root)
    logger.info("EDEKA: %s Rechnung(en) aus %s", len(rows), root)
    return rows


def parse_edeka_invoice(filepath: Path) -> EdekaInvoiceRow:
    """Public entry for a single C+C / EDEKA Grossmarkt PDF."""
    return _parse_edeka_cc(filepath)


def _scan_edeka_cc_invoices(root: Path) -> list[EdekaInvoiceRow]:
    files = sorted(root.glob(_EDEKA_CC_GLOB), key=lambda path: path.name.lower())
    return [_parse_edeka_cc(path) for path in files]


def _parse_edeka_cc(filepath: Path) -> EdekaInvoiceRow:
    """Parst eine C+C-Grossmarkt-Rechnung."""
    name = filepath.name
    empty_row = EdekaInvoiceRow(
        datei=name,
        rechnung_nr="",
        rechnungsdatum="",
        we_7_gesamt=None,
        we_19_gesamt=None,
        we_19_ohne_reinigung=None,
        reinigung=0.0,
        gesamtbetrag=None,
        summe_7_19=None,
        parse_ok=False,
        hinweis="",
    )

    try:
        text = extract_pdf_text(filepath, log_prefix="EDEKA")
    except Exception as exc:
        logger.error("EDEKA %s: Lesefehler %s", name, exc)
        empty_row.hinweis = f"Lesefehler: {exc}"
        return empty_row

    if not text.strip():
        empty_row.hinweis = "Kein Text (OCR fehlgeschlagen oder leer)"
        return empty_row

    re_nr_m = _RE_NR.search(text)
    re_datum_m = _RE_DATUM.search(text)
    we7, we19 = _parse_edeka_mwst_summary(text)
    reinigung = _parse_edeka_wasch_zwischensumme(text)
    gesamt = _parse_edeka_gesamtbetrag(text)

    we19_ohne = round(we19 - reinigung, 2) if we19 is not None else None
    summe_7_19 = round(we7 + we19, 2) if we7 is not None and we19 is not None else None

    ok = all(value is not None for value in (we7, we19, gesamt))
    hinweis = ""
    if ok and summe_7_19 is not None and abs(summe_7_19 - gesamt) > 0.05:
        hinweis = f"Summenabweichung: 7%+19%={summe_7_19:.2f} vs Gesamt {gesamt:.2f}"
        ok = False
    elif reinigung > 0 and we19 is not None and we19 > 0 and reinigung > we19 + 0.05:
        hinweis = f"Reinigung {reinigung:.2f} größer als WE 19 % {we19:.2f}"
        ok = False
    elif ok and we19 is not None and we19 < 0:
        hinweis = "WE 19 % negativ (Gutschrift auf Rechnung)"
    elif not ok:
        missing = []
        if we7 is None:
            missing.append("WE 7 %")
        if we19 is None:
            missing.append("WE 19 %")
        if gesamt is None:
            missing.append("Gesamtbetrag")
        hinweis = "Fehlt: " + ", ".join(missing)

    return EdekaInvoiceRow(
        datei=name,
        rechnung_nr=re_nr_m.group(1) if re_nr_m else "",
        rechnungsdatum=re_datum_m.group(1) if re_datum_m else "",
        we_7_gesamt=we7,
        we_19_gesamt=we19,
        we_19_ohne_reinigung=we19_ohne,
        reinigung=reinigung,
        gesamtbetrag=gesamt,
        summe_7_19=summe_7_19,
        parse_ok=ok,
        hinweis=hinweis,
    )


def _parse_edeka_gesamtbetrag(text: str) -> float | None:
    match = re.search(r"Zahlart:\s*Lastschrift:\s*(-?[\d.]+,\d{2})", text, re.I)
    if match:
        return parse_german_euro_amount(match.group(1))

    lines = text.splitlines()
    for index, line in enumerate(lines):
        if "Gesamtwarenwert" in line and "Gesamtbetrag" in line:
            amounts = last_german_euro_amounts(line)
            if amounts:
                return amounts[-1]
            if index + 1 < len(lines):
                amounts = last_german_euro_amounts(lines[index + 1])
                if amounts:
                    return amounts[-1]

    for line in reversed(lines):
        if "Gesamt Mwst Gesamtbetrag" in line or (
            "Gesamtbetrag" in line and re.search(r"(-?[\d.]+,\d{2,3})", line)
        ):
            amounts = last_german_euro_amounts(line)
            if amounts:
                return amounts[-1]
    return None


def _parse_edeka_mwst_summary(text: str) -> tuple[float | None, float | None]:
    """Gesamtbeträge der 7%- und 19%-Zeile (Spalte „Gesamt“)."""
    we7 = we19 = None
    lines = text.splitlines()

    for line in lines:
        if _MWST_7_LINE.search(line):
            amounts = last_german_euro_amounts(line)
            if len(amounts) >= 4:
                we7 = amounts[-1]
        if _MWST_19_LINE.search(line):
            amounts = last_german_euro_amounts(line)
            if len(amounts) >= 4:
                we19 = amounts[-1]

    if we7 is not None and we19 is not None:
        return we7, we19

    for index, line in enumerate(lines):
        if "MwSt Betrag Gesamt" in line:
            gesamt_values: list[float] = []
            for follow in lines[index + 1 : index + 6]:
                if "Gesamt Mwst" in follow:
                    break
                amounts = last_german_euro_amounts(follow)
                if amounts:
                    gesamt_values.append(amounts[-1])
            if we7 is None and gesamt_values:
                we7 = gesamt_values[0]
            if we19 is None and len(gesamt_values) >= 2:
                we19 = gesamt_values[1]
            break

    if we7 is not None and we19 is not None:
        return we7, we19

    for index, line in enumerate(lines):
        if line.strip() == "Gesamt":
            gesamt_values: list[float] = []
            for follow in lines[index + 1 : index + 6]:
                if "Gesamtbetrag" in follow:
                    break
                amounts = last_german_euro_amounts(follow)
                if amounts:
                    gesamt_values.append(amounts[-1])
            if we7 is None and gesamt_values:
                we7 = gesamt_values[0]
            if we19 is None and len(gesamt_values) >= 2:
                we19 = gesamt_values[1]
            break

    return we7, we19


def _parse_edeka_wasch_zwischensumme(text: str) -> float:
    lines = text.splitlines()
    in_section = False
    for line in lines:
        if _WASH_SECTION.search(line):
            in_section = True
            continue
        if in_section:
            stripped = line.strip()
            if stripped.startswith("Übertrag") or re.match(
                r"^[A-Za-zäöüÄÖÜ].*Sortiment", stripped
            ):
                break
            match = re.search(r"Zwischensumme:\s*(-?[\d.]+,\d{2})", line, re.I)
            if match:
                return parse_german_euro_amount(match.group(1))
    return 0.0
