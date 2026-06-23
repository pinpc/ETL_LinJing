"""Kreissparkasse Waiblingen PDF-Kontoauszug → Liste von KskTransaction."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

import pdfplumber

# ---------------------------------------------------------------------------
# Datenmodell
# ---------------------------------------------------------------------------

@dataclass
class KskTransaction:
    datum: date
    betrag: Decimal        # negativ = Soll (Ausgabe), positiv = Haben (Einnahme)
    buchungstext: str      # vollständiger Text (für Regelmatching)
    vorgang_typ: str       # Lastschrift, GutschriftÜberweisung, …
    auszug_nr: str         # Kontoauszug-Nummer aus Dateiname z.B. "4"


# ---------------------------------------------------------------------------
# Hilfsfunktionen
# ---------------------------------------------------------------------------

_RE_TX = re.compile(
    r"^(\d{2}\.\d{2}\.\d{4})"           # Datum DD.MM.YYYY
    r"(.+?)\s+"                          # Vorgangtyp + erster Beschreibungstext
    r"(-?\d{1,3}(?:\.\d{3})*,\d{2})"    # Betrag  z.B. -1.234,56 oder 14.547,76
    r"\s*$"
)

_RE_KONTOSTAND = re.compile(
    r"^Kontostand\s+am\b|^Gesamtumsatzsummen|^Anzahl\s+Anlagen|"
    r"^Der\s+Kontostand|^Datum\s+Erl|"
    r"^\.\s+-[\d.,]+\s+\d+\s+[\d.,]+\s+\d+"   # Summenzeilenformat ". -16.967,85 23 ..."
    , re.IGNORECASE,
)

_RE_SECTION_SKIP = re.compile(
    r"^Entgeltabschluss:\s+Anlage|^Hinweise\s+zum\s+Kontoauszug|"
    r"^Bitte\s+beachten\s+Sie|^Sehr\s+geehrte|^Rechnungsabschl|"
    r"^Einwendungen|^Gutschriften\s+aus|^Schecks\s+und|^Soweit\s+als|"
    r"^Dieser\s+Kontoauszug",
    re.IGNORECASE,
)

_RE_HEADER = re.compile(
    r"^S\s+Kreissparkasse|^Kreissparkasse\s+Waiblingen|"
    r"^Alter\s+Postplatz|^Anstalt\s+des|^Sparkassen-Finanzgruppe|"
    r"^GiroBusiness\s+\d|^Kontoauszug\s+\d|^\d+\.\s+\w+\s+20\d\d$|"
    r"^Vorstand:|^Telefon\s+07|^Fax\s+07|^www\.|^USt-IdNr|"
    r"^Frau$|^Herr$|^Firmenkundenberater|^David\s+Blatz|"
    r"^Stettiner\s+Str\.|^Neue\s+Ramtelstr\.|^\d{5}\s+\w",
    re.IGNORECASE,
)

_VORGANG_PREFIXES = (
    "GutschriftÜberweisung",
    "Gutschrift Überweisung",
    "Gutschrift",
    "Lastschrift",
    "Überweisung online",
    "Überweisung",
    "Dauerauftrag",
    "Dauerauftrag online",
    "Entgeltabrechnung",
    "Rechnung",
    "Darlehensrate",
    "Kartenzahlung",
    "Einzahlung",
    "Auszahlung",
)


def _parse_betrag(s: str) -> Decimal:
    """'1.234,56' oder '-1.234,56' → Decimal."""
    cleaned = s.replace(".", "").replace(",", ".")
    try:
        return Decimal(cleaned)
    except InvalidOperation:
        return Decimal("0")


def _extract_vorgang(raw: str) -> tuple[str, str]:
    """Trennt Vorgangtyp-Präfix vom Rest der Beschreibung."""
    for prefix in _VORGANG_PREFIXES:
        if raw.startswith(prefix):
            rest = raw[len(prefix):].strip()
            return prefix.rstrip(), rest
    return "", raw.strip()


def _parse_date(s: str, year_hint: int) -> date:
    """'DD.MM.YYYY' → date; falls Jahr fehlt, year_hint nutzen."""
    parts = s.split(".")
    if len(parts) == 3:
        return date(int(parts[2]), int(parts[1]), int(parts[0]))
    return date(year_hint, int(parts[1]), int(parts[0]))


# ---------------------------------------------------------------------------
# Hauptparser
# ---------------------------------------------------------------------------

_RE_AUSZUG_NR = re.compile(r"Auszug_\d+_(\d+)", re.IGNORECASE)


def _extract_auszug_nr(pdf_path: Path) -> str:
    """Extrahiert Kontoauszug-Nummer aus Dateiname, z.B. 'Auszug_2026_0004.PDF' → '4'."""
    m = _RE_AUSZUG_NR.search(pdf_path.name)
    if m:
        return str(int(m.group(1)))   # "0004" → "4"
    return ""


def parse_pdf(pdf_path: str | Path) -> list[KskTransaction]:
    """Liest alle Buchungen aus einem KSK-Kontoauszug-PDF."""
    pdf_path = Path(pdf_path)
    auszug_nr = _extract_auszug_nr(pdf_path)
    transactions: list[KskTransaction] = []

    try:
        with pdfplumber.open(str(pdf_path)) as pdf:
            all_lines: list[str] = []
            in_appendix = False
            for page in pdf.pages:
                text = page.extract_text() or ""
                page_lines = text.split("\n")
                for line in page_lines:
                    stripped = line.strip()
                    if _RE_SECTION_SKIP.match(stripped):
                        in_appendix = True
                    if in_appendix:
                        # appendix-Seiten enthalten nur Entgeltdetails – überspringen
                        # aber Seitenumbruch zurücksetzen wenn neue TX-Zeile kommt
                        if _RE_TX.match(stripped):
                            in_appendix = False
                        else:
                            continue
                    all_lines.append(stripped)
    except Exception as exc:
        raise RuntimeError(f"PDF lesen fehlgeschlagen: {pdf_path.name}: {exc}") from exc

    # Transaktionen aus Zeilenliste extrahieren
    i = 0
    while i < len(all_lines):
        line = all_lines[i]
        m = _RE_TX.match(line)
        if not m:
            i += 1
            continue

        datum_str, raw_desc, betrag_str = m.group(1), m.group(2).strip(), m.group(3)

        # Kontostand-Zeilen überspringen
        if re.match(r"Kontostand", raw_desc, re.IGNORECASE):
            i += 1
            continue

        vorgang_typ, first_desc = _extract_vorgang(raw_desc)
        desc_lines = [first_desc] if first_desc else []

        # Folgezeilen sammeln (bis nächste TX-Zeile oder Abschnitts-Stopper)
        j = i + 1
        while j < len(all_lines):
            nl = all_lines[j]
            if _RE_TX.match(nl):
                break
            if _RE_KONTOSTAND.match(nl) or _RE_HEADER.match(nl) or not nl:
                j += 1
                continue
            desc_lines.append(nl)
            j += 1

        desc_text = "\n".join(line for line in desc_lines if line)
        # Vorgang-Typ dem Buchungstext voranstellen, damit Regex-Regeln ihn matchen können
        buchungstext = f"{vorgang_typ}\n{desc_text}".strip() if vorgang_typ else desc_text
        betrag = _parse_betrag(betrag_str)
        datum = _parse_date(datum_str, 2026)

        transactions.append(KskTransaction(
            datum=datum,
            betrag=betrag,
            buchungstext=buchungstext,
            vorgang_typ=vorgang_typ,
            auszug_nr=auszug_nr,
        ))
        i = j

    return transactions


def parse_directory(source_dir: str | Path) -> list[KskTransaction]:
    """Liest alle PDF-Kontoauszüge aus einem Verzeichnis, sortiert nach Dateiname."""
    source_dir = Path(source_dir)
    pdfs = sorted(
        p for p in source_dir.iterdir()
        if p.suffix.upper() == ".PDF"
    )
    result: list[KskTransaction] = []
    for pdf in pdfs:
        result.extend(parse_pdf(pdf))
    return result
