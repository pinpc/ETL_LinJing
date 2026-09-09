"""Fruchthaus/Stöckl- und Yiu-Splits aus Beleg-PDFs (ohne Betrags-Hardcoding)."""

from __future__ import annotations

import logging
import re
import unicodedata
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_AMOUNT_TOLERANCE = 0.05
_EURO = re.compile(r"(-?\d{1,3}(?:\.\d{3})+,\d{2}|-?\d+,\d{2})")


def _norm(name: str) -> str:
    nfkd = unicodedata.normalize("NFKD", name)
    return "".join(c for c in nfkd if not unicodedata.combining(c)).casefold()


def _pdf_text(path: Path) -> str:
    try:
        from pypdf import PdfReader
    except ImportError:
        return ""
    try:
        reader = PdfReader(str(path))
        return "\n".join((page.extract_text() or "") for page in reader.pages)
    except Exception as exc:  # noqa: BLE001
        logger.debug("Split-Beleg %s: %s", path.name, exc)
        return ""


def _euros(text: str) -> list[float]:
    out: list[float] = []
    for match in _EURO.finditer(text):
        out.append(float(match.group(1).replace(".", "").replace(",", ".")))
    return out


def _find_pdf(root: Path, *needles: str) -> Path | None:
    for path in sorted(root.glob("*.pdf")):
        key = _norm(path.name)
        if all(n in key for n in needles):
            return path
    return None


def _row_like(template: dict[str, Any], *, umsatz: float, bu: str, text: str) -> dict[str, Any]:
    row = dict(template)
    row["Umsatz Euro"] = round(umsatz, 2)
    row["BU Gkto"] = bu
    row["Buchungstext"] = text
    row.pop("_skip_buchung_mapping", None)
    return row


def _fruchthaus_parts(text: str, payment: float) -> list[tuple[str, str, float]] | None:
    """WE 7 % + optional Pfandkiste (positiv), Summe = Bankzahlung."""
    amounts = _euros(text)
    if not amounts:
        return None
    target = round(payment, 2)
    # Suche Paar (we7 negativ/absolut, pfand positiv) mit we7 - pfand ≈ payment
    # payment ist negativ; |payment| = we7_abs - pfand
    abs_pay = abs(target)
    candidates = sorted({round(abs(a), 2) for a in amounts if abs(a) > 0.01})
    for we7 in candidates:
        for pfand in candidates:
            if pfand >= we7:
                continue
            if abs((we7 - pfand) - abs_pay) <= _AMOUNT_TOLERANCE:
                parts = [("3300", "Stöckl WE 7 %", -we7)]
                if pfand > 0:
                    parts.append(("903830", "Stöckl Pfandkiste", pfand))
                return parts
    # nur WE ohne Pfand
    for we7 in candidates:
        if abs(we7 - abs_pay) <= _AMOUNT_TOLERANCE:
            return [("3300", "Stöckl WE 7 %", -we7 if target < 0 else we7)]
    return None


def _yiu_parts(text: str, payment: float) -> list[tuple[str, str, float]] | None:
    amounts = _euros(text)
    if not amounts:
        return None
    target = round(payment, 2)
    abs_pay = abs(target)
    candidates = sorted({round(abs(a), 2) for a in amounts if abs(a) > 0.01})
    for we7 in candidates:
        for we19 in candidates:
            if abs(we7 + we19 - abs_pay) <= _AMOUNT_TOLERANCE:
                # Agenda: WE 19 zuerst klein, dann WE 7
                return [
                    ("4800", "Yiu WE 19 %", -we19 if target < 0 else we19),
                    ("4800", "Yiu WE 7 %", -we7 if target < 0 else we7),
                ]
    return None


def expand_supplier_invoice_splits(
    rows: list[dict[str, Any]],
    source_dir: str | Path,
) -> list[dict[str, Any]]:
    """Ersetzt Fruchthaus-/Yiu-Sammelzeilen durch Beleg-Splits."""
    root = Path(source_dir)
    frucht_pdf = _find_pdf(root, "fruchthaus")
    yiu_pdf = _find_pdf(root, "yiu")
    frucht_text = _pdf_text(frucht_pdf) if frucht_pdf else ""
    yiu_text = _pdf_text(yiu_pdf) if yiu_pdf else ""

    out: list[dict[str, Any]] = []
    for row in rows:
        if row.get("_skip_buchung_mapping"):
            out.append(row)
            continue
        text = str(row.get("Buchungstext") or "")
        try:
            umsatz = float(row.get("Umsatz Euro") or 0)
        except (TypeError, ValueError):
            out.append(row)
            continue

        if "Fruchthaus" in text and frucht_text:
            parts = _fruchthaus_parts(frucht_text, umsatz)
            if parts:
                logger.info(
                    "Fruchthaus/Stöckl %.2f → %s Zeilen aus %s",
                    umsatz,
                    len(parts),
                    frucht_pdf.name if frucht_pdf else "?",
                )
                for bu, label, amount in parts:
                    out.append(_row_like(row, umsatz=amount, bu=bu, text=label))
                continue

        if text.startswith("Yiu") or "Yiu UG" in text:
            parts = _yiu_parts(yiu_text, umsatz) if yiu_text else None
            if parts:
                logger.info(
                    "Yiu %.2f → %s Zeilen aus %s",
                    umsatz,
                    len(parts),
                    yiu_pdf.name if yiu_pdf else "?",
                )
                for bu, label, amount in parts:
                    out.append(_row_like(row, umsatz=amount, bu=bu, text=label))
                continue
            # Rohtext → generisches Kürzel ohne Split
            if "Yiu UG" in text:
                out.append(_row_like(row, umsatz=umsatz, bu="4800", text="Yiu WE 7 %"))
                continue

        out.append(row)
    return out
