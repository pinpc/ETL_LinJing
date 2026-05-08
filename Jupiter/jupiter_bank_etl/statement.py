"""Kontoauszug-PDF → Liste von Buchungs-Dicts."""

import os
import re
from datetime import datetime

from .utils import de_float
import pdfplumber


def extract_statements(pdf_path: str) -> list[dict]:
    """
    Liest alle Buchungen aus dem Kontoauszug-PDF.
    Rückgabe: [{bu_tag, betrag, beschreibung, vorgang_typ}, ...]
    """
    transactions: list[dict] = []
    year_m = re.search(r"(\d{4})", os.path.basename(pdf_path))
    year = int(year_m.group(1)) if year_m else 2026

    TX = re.compile(
        r"^(\d{2}\.\d{2})\. +(\d{2}\.\d{2})\. +(.+?)\s+([\d.]+,\d{2}(?:-)?)\s+([HS])$"
    )
    SKIP = re.compile(
        r"^(Übertrag|Bu-Tag|Wert|Telefon|www\.|kunden|VR |EUR-Konto|IBAN|Herrn?|"
        r"Jing|Jupiter|Gschrifter|87629|alter|neuer|Blatt|erstellt|Bitte|0552|000|K000|5M)",
        re.IGNORECASE,
    )
    VORGANG = re.compile(
        r"^(GUTSCHRIFT|Basislastschrift|Firmenlastschrift|EURO-ÜBERWEISUNG|"
        r"Kartenzahlung girocard|EINZAHLUNG|Einzahlung)\s*",
        re.IGNORECASE,
    )

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
        m = TX.match(line)
        if m:
            bu_str = m.group(1)
            vorgang = m.group(3).strip()
            betrag_s = m.group(4)
            richtung = m.group(5)

            if any(s in vorgang for s in ["Übertrag", "alter Kontostand", "neuer Kontostand"]):
                i += 1
                continue

            vorgang_typ = re.match(
                r"^(GUTSCHRIFT|Basislastschrift|Firmenlastschrift|EURO-ÜBERWEISUNG|"
                r"Kartenzahlung girocard|EINZAHLUNG|Einzahlung)",
                vorgang,
                re.IGNORECASE,
            )
            vorgang_typ = vorgang_typ.group(1) if vorgang_typ else ""
            clean = VORGANG.sub("", vorgang).strip()

            desc_lines = [clean] if clean else []
            j = i + 1
            while j < len(all_lines):
                nl = all_lines[j].strip()
                if TX.match(nl):
                    break
                if SKIP.match(nl) or not nl:
                    j += 1
                    continue
                if re.match(r"^(EREF|MREF|CRED|ABWE|SVWZ):", nl):
                    j += 1
                    continue
                desc_lines.append(nl)
                j += 1

            beschreibung = " ".join(desc_lines[:3]).strip()
            beschreibung = re.sub(r"\s+(EREF|MREF|CRED|REF)\s*:.*$", "", beschreibung).strip()

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
        else:
            i += 1

    return transactions
