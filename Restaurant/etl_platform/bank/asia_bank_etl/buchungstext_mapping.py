"""PDF-Buchungstext → Kürzel + BU Gkto gemäß Parser-Tabelle (Substring- oder Wildcard-Treffer)."""

from __future__ import annotations

import logging
import re
import sys
from pathlib import Path
from typing import Any

if __package__ in (None, ""):
    _asia_root = Path(__file__).resolve().parent.parent
    if str(_asia_root) not in sys.path:
        sys.path.insert(0, str(_asia_root))
    from asia_bank_etl.text_normalize import bereinige_pdf_text
else:
    from .text_normalize import bereinige_pdf_text

logger = logging.getLogger(__name__)

# (Suchtext im Buchungstext, BU Gkto oder None, Kürzel)
# Im Kürzel: „tt.mm.jjjj“ → erste DD.MM.JJJJ-Zahl; „mm.jjjj“ → MM.JJJJ daraus.
# Reihenfolge unwichtig – Anwendung sortiert nach Suchlänge (länger zuerst).
BUCHUNG_PARSER_RULES: list[tuple[str, str | None, str]] = [
    ("Olivia Dang-Huang Vorauszahlung", "4130", "Nebenkosten ASIA"),
    ("Olivia Dang-Huang Pacht", "4830", "Pacht ASIA"),
    ("SPARKASSE ALLGAEU Rechnung Darl", "4360", "Sparkasse Darlehen"),
    ("Knittel GmbH Abfallentsorgung", "3106", "Knittel GmbH Abfallentsorgung Essensre"),
    ("DEVK Allgemeine Versicherungs", "4360", "DEVK KFZ"),
    ("Elektrizitätswerke Reutte", "904280", "Elektrizitaetswerke Reutte GmbH und Co"),
    ("Knappschaft-Bahn-See", "4360", "Knappschaft"),
    ("Ling Jin privat benutzen", "1800", "Privat Ling Jin"),
    ("V-BAUMARKT FUESSEN ELV", None, "V-BAUMARKT WE"),
    ("SB-EINZAHLUNG", "1360", "von Kasse"),
    ("HISEAS INTERNATIONAL", "1360", "HISEAS"),
    ("Wanyun Chen Ausleihen", "1800", "Darlehen Chen"),
    ("Yuzhong Zhao Darlehen", "1800", "Darlehen Zhao"),
    ("Telefonica Germany", "4360", "Telefonica"),
    ("Jupiter Restaurant", "4120", "Lohn Jupiter"),
    ("Finanzamt Kaufbeuren", "4830", "Finanzamt UmSt"),
    ("Vodafone GmbH", "904925", "Vodafone GmbH Internet"),
    ("Union SB-Grosmarkt", "4800", "Edeka WE"),
    ("Fruchthaus Stöckl", "4800", "Fruchthaus Stöckl"),
    ("STRIPE CO A L GOODBODY", "4970", "AllOpay"),
    ("DEHOGA Bayern e.V", "1743", "DEHOGA Bayern e.V Beitrag"),
    ("AOK Bayern", "1743", "AOK Bayern Beitrag"),
    ("ERGO Vorsorge LV AG R71390271.3", "1748", "ERGO Vorsorge LV AG R71390271.3 Linjing mm.jjjj"),
    ("Huizhen Lyu Lohn", "4120", "Lohn Huizhen Lyu"),
    ("Fan Peng Lohn", "4120", "Lohn Fan Peng"),
    ("Ling Jin Lohn", "4120", "Lohn Ling Jin"),
    ("Ze Peng Lohn", "4120", "Lohn Ze Peng"),
    ("V-MARKT TANKA", "904530", "V-MARKT Tank"),
    ("ESSO", "904530", "ESSO Tanken tt.mm.jjjj"),
    ("AllOpay", "4970", "AllOpay"),
    ("Abrechnung", "4360", "Abrechnung Bank"),
    ("EXPERT", None, "EXPERT WE"),
    ("IKEA", None, "IKEA WE"),
    ("LIDL", None, "LIDL WE"),
    # Parser-Tabelle: Spalten BU Gkto · Kürzel · Suchtext (PDF)
    ("allO Technology GmbH ALLO TECHNOLOGY GMBH", "904930", "allO Technology GmbH Nutzungsgebühr"),
    ("Bortz & Dr. Führer Steuerberatungsg esellschaft", "904955", "Bortz & Dr. Fuehrer Datenübertragung"),
    ("ACV Automobil-Club", None, "ACV Automobil-Club"),
    ("ABK Betriebsgesellschaft", "3400", "ABK Getränke WE 19 %"),
    ("H.I.S. DEUTSCHLAND TOURISTIK GMBH", "1360", "H.I.S. DEUTSCHLAND"),
    ("Ling Jin ausleihen", "1800", "Jing Ling Privat"),
    ("GÜSCHO Feinkost GmbH", "3300", "GÜSCHO Feinkost WE 7%"),
    ("Bundeskasse 1062 4146 8329", "2308", "Bußgeld Raten von 03 bis 06 2026"),
    ("Bußgeld Raten von 03 bis 06 2026", "2308", "Bußgeld Raten von 03 bis 06 2026"),
    ("Fliesenstudio Deutschmann Bad 2000 GmbH", "4260", "Fliesenstudio Deutschmann Bad 2000 Fliesenverlegung tt.mm.jjjj"),
    ("KreuterMedeleSchäfer GmbH", None, "Werkstatt F ÜS-LJ 888 F ÜS-LJ 888  tt.mm.jjjj"),
    ("Theurer + Partner GbR", "904955", "Theurer + Partner GbR Lohndatenübertrag + 4.Q"),
    ("DEURAG Deutsche Rechtsschutz", "0980", "DEURAG Rechtsschutz"),
    ("Mielich Haustechnik GmbH", "3400", "Mielich Haustechnik Anlagen WE 19%"),
    ("KAUFBEUREN .* UMS.ST", "4830", "Finanzamt UmSt"),
    ("Check24 .* Kfz-Ve rsicherungen GmbH", None, "Kfz-Versicherung"),
    ("Sheue-Ru Wang Rechnung", "904955", "Sheue-Ru Wang Rechnung tt.mm.jjjj"),
    ("Jing Ling privat benutzen", "1800", "Privat Ling Jin tt.mm.jjjj"),
   
]


def _pattern_matches(parser: str, text: str) -> bool:
    """
    Substring-Match (wie bisher). Enthält ``parser`` die Zeichenfolge ``.*``,
    gilt das als Platzhalter für beliebigen Text zwischen den angrenzenden
    Teilstücken (nicht als Regex-Metazeichen in den Teilstücken selbst).
    """
    if ".*" not in parser:
        return parser.lower() in text.lower()
    parts = [p.strip() for p in parser.split(".*")]
    literals = [p for p in parts if p]
    if len(literals) < 2:
        return parser.replace(".*", "").lower() in text.lower()
    pattern = r".*?".join(re.escape(p) for p in literals)
    return re.search(pattern, text, flags=re.IGNORECASE | re.DOTALL) is not None


_KUERZEL_DATUM_PLATZ = "tt.mm.jjjj"
_KUERZEL_MONAT_PLATZ = "mm.jjjj"
_DATUM_ERSTES = re.compile(r"\d{2}\.\d{2}\.\d{4}")


def _datum_tt_mm_jjjj_aus_text(text: str) -> str | None:
    """Erste Datumzahl DD.MM.JJJJ im Buchungstext."""
    m = _DATUM_ERSTES.search(text)
    return m.group(0) if m else None


def _monat_jahr_aus_text(text: str) -> str | None:
    """Erstes Datum als MM.JJJJ (Monat/Jahr der Versicherungsperiode)."""
    d = _datum_tt_mm_jjjj_aus_text(text)
    if not d:
        return None
    _tag, monat, jahr = d.split(".")
    return f"{monat}.{jahr}"


def _kuerzel_mit_datum(kuerzel: str, text: str) -> str:
    """Ersetzt Datums-Platzhalter im Kürzel durch Werte aus dem Buchungstext."""
    if _KUERZEL_DATUM_PLATZ in kuerzel:
        d = _datum_tt_mm_jjjj_aus_text(text)
        if d:
            kuerzel = kuerzel.replace(_KUERZEL_DATUM_PLATZ, d)
        else:
            kuerzel = (
                kuerzel.replace(_KUERZEL_DATUM_PLATZ, "")
                .replace("  ", " ")
                .strip(" -–—")
            )
    if _KUERZEL_MONAT_PLATZ in kuerzel:
        mj = _monat_jahr_aus_text(text)
        if mj:
            kuerzel = kuerzel.replace(_KUERZEL_MONAT_PLATZ, mj)
        else:
            kuerzel = (
                kuerzel.replace(_KUERZEL_MONAT_PLATZ, "")
                .replace("  ", " ")
                .strip(" -–—")
            )
    return kuerzel


def apply_buchungs_mapping(rows: list[dict[str, Any]]) -> int:
    """
    Ersetzt ``Buchungstext`` durch das Kürzel und setzt ``BU Gkto``, wenn die
    Regel ein Konto vorsieht. Erster Treffer nach absteigender Suchlänge gewinnt.
    Vor dem Abgleich werden typische Bank-Vorsätze (z. B. „Abbuchung Lastschrift“,
    „Überweisung Online“, „Gutschr einer Überw“) aus ``Buchungstext`` entfernt.
    Ohne ``.*`` im Suchtext: Vergleich als Teilstring, ohne Groß-/Kleinschreibung.
    Mit ``.*``: beliebiger Text zwischen den durch ``.*`` getrennten Teilstücken.
    Enthält das Kürzel ``tt.mm.jjjj`` bzw. ``mm.jjjj``, wird es durch Datum bzw. Monat.Jahr
    aus dem Buchungstext ersetzt (erstes DD.MM.JJJJ).
    """
    rules = sorted(BUCHUNG_PARSER_RULES, key=lambda t: len(t[0]), reverse=True)
    n = 0
    for row in rows:
        raw = str(row.get("Buchungstext") or "").strip()
        if not raw:
            continue
        cleaned = bereinige_pdf_text(raw)
        text = cleaned if cleaned.strip() else raw
        row["Buchungstext"] = text
        for parser, bu, kuerzel in rules:
            if _pattern_matches(parser, text):
                row["Buchungstext"] = _kuerzel_mit_datum(kuerzel, text)
                if bu:
                    row["BU Gkto"] = bu
                n += 1
                break
    if n:
        logger.info("Buchungstext-Mapping: %s Zeilen auf Kürzel/BU gesetzt", n)
    return n
