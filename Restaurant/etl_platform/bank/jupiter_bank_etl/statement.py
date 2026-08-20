"""Kontoauszug-PDF → Liste von Buchungs-Dicts."""

import os
import re
from datetime import datetime

import pdfplumber

from .utils import de_float

_TX = re.compile(
    r"^(\d{2}\.\d{2})\. +(\d{2}\.\d{2})\. +(.+?)\s+([\d.]+,\d{2}(?:-)?)\s+([HS])$"
)
_SKIP = re.compile(
    r"^(Übertrag|Bu-Tag|Wert|Telefon|www\.|kunden|VR |EUR-Konto|IBAN|Herrn?|"
    r"Jing|Jupiter|Gschrifter|87629|alter|neuer|Blatt|erstellt|Bitte|0552|000|K000|5M)",
    re.IGNORECASE,
)
# Nach Buchungskopf oft Auftraggeber – nicht wie Briefkopf verwerfen.
_REMITTER_KEEP = re.compile(r"^Jing(\s+Ling)?\s*$", re.IGNORECASE)
_VORGANG = re.compile(
    r"^(GUTSCHRIFT|Basislastschrift|Firmenlastschrift|EURO-ÜBERWEISUNG|"
    r"Kartenzahlung girocard|EINZAHLUNG|Einzahlung)\s*",
    re.IGNORECASE,
)
_VORGANG_TYP = re.compile(
    r"^(GUTSCHRIFT|Basislastschrift|Firmenlastschrift|EURO-ÜBERWEISUNG|"
    r"Kartenzahlung girocard|EINZAHLUNG|Einzahlung)",
    re.IGNORECASE,
)
_META_LINE = re.compile(r"^(EREF|MREF|CRED|ABWE|SVWZ):")
_REF_TAIL = re.compile(r"\s+(EREF|MREF|CRED|REF)\s*:.*$")


def extract_statements(pdf_path: str) -> list[dict]:
    """
    Liest alle Buchungen aus dem Kontoauszug-PDF.
    Rückgabe: [{bu_tag, betrag, beschreibung, vorgang_typ}, ...]
    """
    transactions: list[dict] = []
    year_m = re.search(r"(\d{4})", os.path.basename(pdf_path))
    year = int(year_m.group(1)) if year_m else 2026

    try:
        with pdfplumber.open(pdf_path) as pdf:
            all_lines: list[str] = []
            for page in pdf.pages[:-1]:
                text = page.extract_text()
                if text:
                    all_lines.extend(text.split("\n"))
    except Exception as e:
        print(f"ERROR: Kontoauszug lesen fehlgeschlagen: {e}")
        return transactions

    i = 0
    while i < len(all_lines):
        line = all_lines[i].strip()
        m = _TX.match(line)
        if not m:
            i += 1
            continue

        bu_str = m.group(1)
        vorgang = m.group(3).strip()
        betrag_s = m.group(4)
        richtung = m.group(5)

        if any(s in vorgang for s in ["Übertrag", "alter Kontostand", "neuer Kontostand"]):
            i += 1
            continue

        typ_m = _VORGANG_TYP.match(vorgang)
        vorgang_typ = typ_m.group(1) if typ_m else ""
        clean = _VORGANG.sub("", vorgang).strip()

        desc_lines = [clean] if clean else []
        j = i + 1
        while j < len(all_lines):
            nl = all_lines[j].strip()
            if _TX.match(nl):
                break
            if not nl:
                j += 1
                continue
            if _SKIP.match(nl):
                if _REMITTER_KEEP.match(nl) and not any(desc_lines):
                    desc_lines.append(nl)
                j += 1
                continue
            if _META_LINE.match(nl):
                j += 1
                continue
            desc_lines.append(nl)
            j += 1

        beschreibung = _REF_TAIL.sub("", " ".join(desc_lines[:3]).strip()).strip()

        betrag = de_float(betrag_s)
        if richtung == "S":
            betrag = -betrag

        try:
            bu_tag = datetime.strptime(f"{bu_str}.{year}", "%d.%m.%Y").date()
        except Exception:
            bu_tag = None

        transactions.append(
            {
                "bu_tag": bu_tag,
                "betrag": betrag,
                "beschreibung": beschreibung,
                "vorgang_typ": vorgang_typ,
            }
        )
        i = j

    return transactions
