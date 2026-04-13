"""FiBu-Zuordnung aus Rechnungs-Map und Regeln."""

import re

from .config import FIBU_RULES


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
                clean = re.sub(r"\s+SecureGo.*$", "", beschr, flags=re.IGNORECASE).strip()
                m_miete = re.search(r"(Miete \d{2}\.\d{4}.+)", clean, re.IGNORECASE)
                return kto, m_miete.group(1) if m_miete else label

            if "meistro Energie Gas" in label or "meistro Energie Strom" in label:
                m_datum = re.search(r"\((\d{2})/(\d{2})\)", beschr)
                if m_datum:
                    mon = m_datum.group(1)
                    yr = "20" + m_datum.group(2)
                    return kto, f"{label} {mon} {yr}"
                return kto, label

            if kto == "1740" and richtung == "S":
                clean = re.sub(r"\s+SecureGo.*$", "", beschr, re.IGNORECASE).strip()
                m = re.match(r"^(.+?)\s+(Lohn\s+\d{2}\.\d{4})", clean, re.IGNORECASE)
                if m:
                    parts = m.group(1).strip().split()
                    if len(parts) == 2:
                        name_fmt = f"{parts[1]} {parts[0]}"
                    elif len(parts) >= 3:
                        name_fmt = m.group(1).strip()
                    else:
                        name_fmt = m.group(1).strip()
                    monat = m.group(2).strip()
                    return kto, f"{name_fmt} {monat}"
                return kto, clean[:50]
            else:
                return kto, label

    return "", beschr[:50]
