"""Sparkasse-Kontoauszug (PDF) → strukturierte Buchungszeilen."""

from __future__ import annotations

import logging
import re
from typing import Any

import pdfplumber

from .constants import BUCHUNGSTYPEN, STOPP_MUSTER

logger = logging.getLogger(__name__)


def normalize_line(line: str) -> str:
    """Normalisiert Datumsformat in Textzeilen."""
    return re.sub(r"^(\d)\s(\d{1,2}\.\d{2}\.\d{4})", r"\1\2", line)


def ist_buchungszeile(line: str) -> tuple[str, str, float] | None:
    """Prüft, ob eine Zeile eine gültige Buchung ist. Gibt (Datum, Text, Betrag) zurück oder None."""
    if any(s in line for s in STOPP_MUSTER):
        return None
    m = re.match(
        r"^(\d{2}\.\d{2}\.\d{4})(.+?)\s+([-]?\d{1,3}(?:\.\d{3})*,\d{2})\s*$",
        line,
    )
    if not m:
        return None
    if not any(bt in m.group(2) for bt in BUCHUNGSTYPEN):
        return None
    try:
        betrag = float(m.group(3).replace(".", "").replace(",", "."))
        return m.group(1), m.group(2).strip(), betrag
    except ValueError:
        logger.warning("Konnte Betrag nicht konvertieren: %s", m.group(3))
        return None


def parse_sparkasse_pdf(pdf_path: str) -> list[dict[str, Any]]:
    """Extrahiert Buchungen aus Sparkasse-PDF-Kontoauszug."""
    rows: list[dict[str, Any]] = []
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                text = page.extract_text() or ""
                lines = [normalize_line(l) for l in text.splitlines()]
                i = 0
                while i < len(lines):
                    buchung = ist_buchungszeile(lines[i])
                    if buchung:
                        datum_str, buchungstyp, betrag = buchung
                        detail_lines = [buchungstyp]
                        j = i + 1
                        while j < len(lines):
                            nl = lines[j]
                            if any(s in nl for s in STOPP_MUSTER):
                                break
                            if re.match(r"^\d{2}\.\d{2}\.\d{4}", nl):
                                if ist_buchungszeile(nl):
                                    break
                                detail_lines.append(nl.strip())
                                j += 1
                                continue
                            if re.match(
                                r"^Sparkasse Allgäu|^Residenzplatz|^Anstalt|^Sparkassen-",
                                nl,
                            ):
                                break
                            if re.match(r"^[A-Z0-9]{15,}\s*$", nl.strip()):
                                j += 1
                                continue
                            if "Gläubiger-ID:" in nl:
                                j += 1
                                continue
                            if nl.strip():
                                detail_lines.append(nl.strip())
                            j += 1
                        rows.append(
                            {
                                "Datum": datum_str,
                                "Buchungstext": " ".join(detail_lines),
                                "Umsatz Euro": betrag,
                            }
                        )
                        i = j
                    else:
                        i += 1
    except Exception as e:
        logger.error("Fehler beim Parsen der PDF %s: %s", pdf_path, e)
        raise
    return rows
