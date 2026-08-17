"""FiBu-Zuordnung aus Rechnungs-Map und Regeln."""

import re

from .config import FIBU_RULES

_DE_MONTHS = {
    "januar": "01",
    "februar": "02",
    "märz": "03",
    "maerz": "03",
    "april": "04",
    "mai": "05",
    "juni": "06",
    "juli": "07",
    "august": "08",
    "september": "09",
    "oktober": "10",
    "november": "11",
    "dezember": "12",
}

_RE_SECUREGO = re.compile(r"\s+SecureGo.*$", re.IGNORECASE)
_RE_ECHTZEIT = re.compile(r"^Überweisung\s+Echtzeit\s+", re.IGNORECASE)
_RE_LOHN = re.compile(r"^(.+?)\s+(Lohn\s+\d{2}\.\d{4})", re.IGNORECASE)
_RE_DE_MONTH = re.compile(
    r"(Januar|Februar|März|Maerz|April|Mai|Juni|Juli|August|"
    r"September|Oktober|November|Dezember)\s+(\d{4})",
    re.IGNORECASE,
)
_RE_MM_YYYY_SLASH = re.compile(r"(\d{2})/(\d{4})")
_RE_RECHNUNG_YYMM = re.compile(r"Rechnung\s+(\d{2})(\d{2})-", re.IGNORECASE)
_RE_ADSA_RE = re.compile(r"(RE-\d+)", re.IGNORECASE)


def _clean_bank_text(beschr: str) -> str:
    return _RE_SECUREGO.sub("", beschr).strip()


def _mm_yyyy_from_booking(tx: dict) -> str:
    d = tx.get("bu_tag")
    if d is None:
        return ""
    return f"{d.strftime('%m')} {d.year}"


def _lohn_text(beschr: str) -> str:
    clean = _RE_ECHTZEIT.sub("", _clean_bank_text(beschr)).strip()
    m = _RE_LOHN.match(clean)
    if not m:
        return clean[:50]
    name = m.group(1).strip()
    monat = m.group(2).strip()
    if re.search(r"Ping\s+Zhou", name, re.I):
        name = "Ping Zhou"
    return f"{name} {monat}"


def map_booking(
    tx: dict, rechnung_map: dict, *, ignore_invoice_splits: bool = False
) -> tuple[str, str]:
    """
    (bu_kto, buchungstext) für eine Kontoauszug-Buchung.
    Priorität: 1. Rechnung (ohne SPLIT, wenn ignore_invoice_splits), 2. FIBU_RULES, 3. leer.
    """
    key = round(abs(tx["betrag"]), 2)
    beschr = tx["beschreibung"]
    richtung = "S" if tx["betrag"] < 0 else "H"

    if key in rechnung_map:
        tag, payload = rechnung_map[key]
        is_split = isinstance(tag, str) and tag.endswith("_SPLIT")
        if is_split and ignore_invoice_splits:
            pass
        else:
            return tag, payload

    for pattern, richt, kto, label in FIBU_RULES:
        if richt == richtung and pattern.search(beschr):
            if label == "Miete":
                clean = _clean_bank_text(beschr)
                m_miete = re.search(r"(Miete \d{2}\.\d{4}.+)", clean, re.IGNORECASE)
                return kto, m_miete.group(1) if m_miete else label

            if "meistro Energie Gas" in label or "meistro Energie Strom" in label:
                m_datum = re.search(r"\((\d{2})/(\d{2})\)", beschr)
                if m_datum:
                    mon = m_datum.group(1)
                    yr = "20" + m_datum.group(2)
                    return kto, f"{label} {mon} {yr}"
                return kto, label

            if label == "Nebenkosten Jupiter":
                m_year = re.search(r"Nebenkosten\s+(\d{4})", beschr, re.I)
                year = m_year.group(1) if m_year else ""
                if not year:
                    d = tx.get("bu_tag")
                    year = str(d.year) if d else ""
                if re.search(r"Wasser/Abwasser", beschr, re.I):
                    return kto, f"Nebenkosten {year} Wasser/Abwasser".strip()
                return kto, f"Nebenkosten {year}".strip()

            if label == "ovag Strom":
                period = _mm_yyyy_from_booking(tx)
                return kto, f"{label} {period}".strip()

            if label == "BGN Beitrag":
                d = tx.get("bu_tag")
                if d:
                    q = min(4, d.month // 3 + 1)
                    return kto, f"BGN Beitrag {d.year} Q {q}"
                m_y = re.search(r"Vorschuss\s+(\d{4})", beschr, re.I)
                if m_y:
                    return kto, f"BGN Beitrag {m_y.group(1)} Q 2"
                return kto, label

            if label == "A.R.Z. GmbH":
                m_rg = re.search(r"Rg\.-Nr\.\s*(\d+)", beschr, re.I)
                rg = m_rg.group(1) if m_rg else ""
                if rg:
                    return kto, f"A.R.Z. GmbH Rg.-Nr. {rg} Küchenreinigung Dunstabzugsanlage"
                return kto, "A.R.Z. GmbH Küchenreinigung Dunstabzugsanlage"

            if label == "Vodafone Internet":
                m = _RE_MM_YYYY_SLASH.search(beschr)
                if m:
                    return kto, f"Vodafone Internet {m.group(1)} {m.group(2)}"
                period = _mm_yyyy_from_booking(tx)
                return kto, f"Vodafone Internet {period}".strip()

            if label == "Kloh Entsorgung":
                m = _RE_DE_MONTH.search(beschr)
                if m:
                    mm = _DE_MONTHS.get(m.group(1).lower().replace("ä", "ae"), "")
                    if mm:
                        return kto, f"Kloh Entsorgung Essensreste {mm} {m.group(2)}"
                period = _mm_yyyy_from_booking(tx)
                return kto, f"Kloh Entsorgung Essensreste {period}".strip()

            if label == "Schankanlagenwartung":
                m = _RE_RECHNUNG_YYMM.search(beschr)
                if m:
                    return kto, f"Häufle Schankanlagenwartung {m.group(2)} 20{m.group(1)}"
                period = _mm_yyyy_from_booking(tx)
                return kto, f"Häufle Schankanlagenwartung {period}".strip()

            if label == "Bankgebühr":
                period = _mm_yyyy_from_booking(tx)
                return kto, f"Bankgebühr {period}".strip()

            if label == "ADSA":
                m = _RE_ADSA_RE.search(beschr)
                if m:
                    return kto, f"ADSA GmbH {m.group(1)}"
                return kto, "ADSA GmbH"

            if kto == "1740" and richtung == "S":
                return kto, _lohn_text(beschr)
            return kto, label

    return "", beschr[:50]
