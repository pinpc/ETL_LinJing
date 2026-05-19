"""Buchungstexte bereinigen / Stripe → Kurztext."""

from __future__ import annotations

import re


def bereinige_pdf_text(text: str) -> str:
    """Bereinigt PDF-Text von Buchungstypen und irrelevantem Content."""
    prefixe = [
        r"Abbuchung Lastschrift / Wert: \d{2}\.\d{2}\.\d{4}",
        r"Abbuchung Lastschrift",
        r"Abbuchung Firmen-LS",
        r"Überweisung Online",
        r"Gutschrift einer Überweisung",
        r"Gutschr einer Überw",
        r"Dauerauftrag",
        r"Debitkartenzahl\. EUR",
        r"Bargeldeinzahlung GA",
        r"Sonst ZV preisfrei",
        r"Abrechnung \d{2}\.\d{2}\.\d{4} / Wert: \d{2}\.\d{2}\.\d{4}",
        r"Abrechnung",
    ]
    prefixe.sort(key=len, reverse=True)
    changed = True
    while changed:
        changed = False
        for p in prefixe:
            neu = re.sub(rf"^{p}\s*", "", text, flags=re.IGNORECASE)
            if neu != text:
                text = neu
                changed = True
                break
    text = re.sub(r"Gläubiger-ID:\s*\S+", "", text)
    text = re.sub(r"\b[A-Z0-9]{15,}\b", "", text)
    text = re.sub(r"\s{2,}", " ", text)
    return text.strip()


def kuerze_stripe_text(text: str, buchungs_datum: str) -> str:
    """Kürzt Stripe-Buchungstexte zu \"AllOpay Datum\"."""
    if not text:
        return text
    if "stripe" in text.lower() and (
        "allo" in text.lower() or "technology" in text.lower()
    ):
        m = re.search(r"(\d{4}-\d{2}-\d{2})", text)
        if m:
            y, mth, d = m.group(1).split("-")
            return f"AllOpay {d}.{mth}.{y}"
        m = re.search(r"(\d{2}\.\d{2}\.\d{4})", text)
        if m:
            return f"AllOpay {m.group(1)}"
        if buchungs_datum:
            return f"AllOpay {buchungs_datum}"
        return "AllOpay (Datum unbekannt)"
    return text
