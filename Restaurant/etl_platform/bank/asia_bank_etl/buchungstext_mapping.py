"""PDF-Buchungstext → Kürzel + BU Gkto gemäß Parser-Tabelle (Substring- oder Wildcard-Treffer)."""

from __future__ import annotations

import logging
import re
from typing import Any

from .text_normalize import bereinige_pdf_text

logger = logging.getLogger(__name__)

# (Suchtext im Buchungstext, BU Gkto oder None, Kürzel)
# Im Kürzel: „tt.mm.jjjj“ → erste DD.MM.JJJJ-Zahl; „mm.jjjj“ / „mm yyyy“ → Monat/Jahr.
# Reihenfolge unwichtig – Anwendung sortiert nach Suchlänge (länger zuerst).
BUCHUNG_PARSER_RULES: list[tuple[str, str | None, str]] = [
    # --- Olivia / Miete / NK (Agenda Mai 2026 Konten) ---
    ("Olivia Dang-Huang Nebenkosten 2024", "904228", "NK 2024 Asia"),
    ("Olivia Dang-Huang Vorauszahlung", "904228", "NK Asia mm yyyy"),
    ("Olivia Dang-Huang Pacht", "904210", "Pacht Asia mm yyyy"),
    # --- Darlehen: Split erfolgt in darlehen_split.py; Fallback falls kein Split ---
    ("SPARKASSE ALLGAEU Rechnung Darl", "4360", "Sparkasse Darlehen"),
    ("Knittel GmbH Abfallentsorgung", "3106", "Knittel GmbH Essensreste Entsorgung mm yyyy"),
    ("DEVK Allgemeine Versicherungs", "4360", "DEVK KFZ"),
    ("Elektrizitätswerke Reutte", "904240", "Strom mm yyyy"),
    ("Knappschaft-Bahn-See", "1743", "Knappschaft mm yyyy"),
    ("Ling Jin privat benutzen", "1800", "Privat Ling Jin"),
    ("V-BAUMARKT FUESSEN ELV", None, "V-BAUMARKT WE"),
    ("SB-EINZAHLUNG", "1360", "von Kasse"),
    ("HISEAS INTERNATIONAL", "1360", "HISEAS von Kasse"),
    ("Hiseas International", "1360", "HISEAS von Kasse"),
    ("GREAT LINE OU", "1360", "GREAT LINE OU von Kasse"),
    ("Wanyun Chen Ausleihen", "1800", "Darlehen Chen"),
    ("Yuzhong Zhao Darlehen", "1800", "Darlehen Zhao"),
    ("Telefonica Germany", "904925", "Telefonica Mobil mm yyyy"),
    # Jupiter: Erstattung (Haben) vs. Lohn (Soll)
    ("Erstattung Lohnkosten Jupiter", "1361", "vom Jupiter"),
    ("Jupiter Restaurant", "4120", "Lohn Jupiter"),
    # Finanzamt: Jahres-Erstattung / LOHNST-Split vor generischem UmSt
    ("LOHNST", "1741", "LSt mm yyyy"),
    ("ERSTATT .* UMS.ST 20", "1791", "UST yyyy"),
    ("UMS.ST 20", "1791", "UST yyyy"),
    ("ERSTATT .* UMS.ST", "1780", "UST VA mm yyyy"),
    ("UMS.ST", "1780", "UST VA mm yyyy"),
    ("Finanzamt Kaufbeuren", "4830", "Finanzamt UmSt"),
    ("Rundfunk ARD", "4830", "Rundfunk ARD, ZDF, DRadio Beitrag"),
    # Vodafone: Mobil vs. Internet
    ("Vodafone GmbH 40549", "904925", "Vodafone GmbH Mobil mm yyyy"),
    ("Vodafone GmbH", "904925", "Vodafone GmbH Internet mm yyyy"),
    ("Union SB-Grosmarkt", "4800", "Edeka WE"),
    ("Fruchthaus Stöckl", "4800", "Fruchthaus Stöckl"),
    ("STRIPE CO A L GOODBODY", "4970", "AllOpay"),
    ("DEHOGA Bayern e.V", "4380", "DEHOGA Bayern e.V Beitrag Q q"),
    ("AOK Bayern", "1743", "AOK Bayern Beitrag mm yyyy"),
    ("ERGO Vorsorge LV AG R71390271.3", "1748", "ERGO LV Linjing mm yyyy"),
    ("Huizhen Lyu Lohn", "4120", "Lohn Huizhen Lyu mm yyyy"),
    ("Fan Peng Lohn", "1740", "Lohn Fan Peng mm yyyy"),
    ("Ling Jin Lohn", "1740", "Lohn Ling Jin mm yyyy"),
    ("Ze Peng Lohn", "4120", "Lohn Ze Peng mm yyyy"),
    ("Ping Zhou Lohn", "1740", "Ping Zhou Lohn mm yyyy"),
    ("Sheue-Ru Wang Ping Zhou", "1740", "Ping Zhou Lohn mm yyyy"),
    ("V-MARKT TANKA", "904530", "V-MARKT Tank"),
    ("ESSO", "904530", "ESSO Tanken"),
    ("ARAL", "904530", "ARAL Tank"),
    ("JET", "904530", "JET Tank"),
    ("AllOpay", "4970", "AllOpay"),
    ("Abrechnung", "4970", "Bankgebühr"),
    ("EXPERT", None, "EXPERT WE"),
    ("IKEA", None, "IKEA WE"),
    ("LIDL", None, "LIDL WE"),
    ("AMAZON", "3400", "AMAZON WE 19%"),
    ("allO Technology GmbH ALLO TECHNOLOGY GMBH", "904930", "allO Technology GmbH Nutzungsgebühr mm yyyy"),
    ("allO Technology GmbH", "904930", "allO Technology GmbH Nutzungsgebühr mm yyyy"),
    ("Bortz & Dr. Führer Steuerberatungsg esellschaft", "904955", "Bortz & Dr. Fuehrer Gehaltskosten mm yyyy"),
    ("ACV Automobil-Club", None, "ACV Automobil-Club"),
    ("ABK Betriebsgesellschaft", "3400", "ABK Getränke WE 19 %"),
    ("H.I.S. DEUTSCHLAND TOURISTIK GMBH", "1360", "H.I.S. DEUTSCHLAND"),
    ("Ling Jin ausleihen", "1800", "Jing Ling Privat"),
    ("GÜSCHO Feinkost GmbH", "3300", "GÜSCHO Food WE 7%"),
    ("Bundeskasse 1062 4146 8329", "2308", "Zoll Bußgeld Raten von 03 bis 06 2026"),
    ("Bußgeld Raten von 03 bis 06 2026", "2308", "Zoll Bußgeld Raten von 03 bis 06 2026"),
    ("Bundeskasse Kfz-Steuer", "4510", "Kfz-Steuer fuer FUES LJ 888 mm1 yyyy1 - mm2 yyyy2"),
    ("Kfz-Steuer fuer FUES LJ 888", "4510", "Kfz-Steuer fuer FUES LJ 888 mm1 yyyy1 - mm2 yyyy2"),
    ("Fliesenstudio Deutschmann Bad 2000 GmbH", "4260", "Fliesenstudio Deutschmann Bad 2000 Fliesenverlegung Ratenzahlung"),
    ("KreuterMedeleSchäfer GmbH", None, "Werkstatt F ÜS-LJ 888 F ÜS-LJ 888  tt.mm.jjjj"),
    ("Theurer + Partner GbR", "904955", "Theurer + Partner GbR Lohndatenübertrag + 4.Q"),
    ("DEURAG Deutsche Rechtsschutz", "0980", "DEURAG Rechtsschutz"),
    ("Mielich Haustechnik GmbH", "904280", "Mielich Haustechnik Anlagen WE 19%"),
    ("Dorr GmbH", "904250", "Dörr GmbH & Co. KG"),
    ("Dörr GmbH", "904250", "Dörr GmbH & Co. KG"),
    ("Ragaller", "904250", "Ragaller GmbH + Co. Betriebs KG"),
    ("Gemeinde Schwangau", "4390", "Gemeinde Schwangau Kurtaxe 2023"),
    ("Fremdenv", "4390", "Gemeinde Schwangau Kurtaxe 2023"),
    ("Allianz Versicherungs-AG", "4360", "Allianz Versicherungs-AG Vertrag AS-9835199105 Betriebshaftpflicht 2025"),
    ("Isabella Ebentheuer", "904280", "Ebentheuer Schornsteinprüfung"),
    ("Ebentheuer", "904280", "Ebentheuer Schornsteinprüfung"),
    ("Staatsoberkasse Bayern", "2010", "Überbrückungshilfe Corona UBH3XR-57164 Rückzahlung"),
    ("Sheue-Ru Wang Rechnung", "904955", "Fibu"),
    ("Check24 .* Kfz-Ve rsicherungen GmbH", None, "Kfz-Versicherung"),
    ("Jing Ling privat benutzen", "1800", "Jing Ling Privat"),
    ("Jing Ling DATUM", "1800", "Jing Ling Privat"),
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
_KUERZEL_MONAT_DOT = "mm.jjjj"
_KUERZEL_MONAT_SPACE = "mm yyyy"
_KUERZEL_JAHR = "yyyy"
_KUERZEL_QUARTAL = "Q q"
_DATUM_ERSTES = re.compile(r"\d{2}\.\d{2}\.\d{4}")
_RE_BEITRAG_MMYY = re.compile(r"BEITRAG\s+(\d{2})(\d{2})", re.IGNORECASE)
_RE_MONAT_ABBR = re.compile(
    r"\b(JAN|FEB|MÄR|MAR|APR|MAI|JUN|JUL|AUG|SEP|OKT|NOV|DEZ|MRZ)\.?\s*(\d{2})\b",
    re.IGNORECASE,
)
_RE_MM_YYYY = re.compile(r"(?<!\d)(\d{2})\.(\d{4})\b")
_RE_DATUM_KURZ = re.compile(r"\b(\d{2})\.(\d{2})\.(\d{2})\b")
_RE_UMST_JAHR = re.compile(r"UMS\.ST\s+(20\d{2})", re.IGNORECASE)
_RE_BTRG_QUARTAL = re.compile(r"Btrg\s+(\d{2})-(\d{2})/(\d{2})", re.IGNORECASE)
_RE_LOHN_MMYYYY = re.compile(r"Lohn\s+(\d{2})\.(\d{4})", re.IGNORECASE)
_MONAT_MAP = {
    "JAN": "01",
    "FEB": "02",
    "MAR": "03",
    "MÄR": "03",
    "MRZ": "03",
    "APR": "04",
    "MAI": "05",
    "JUN": "06",
    "JUL": "07",
    "AUG": "08",
    "SEP": "09",
    "OKT": "10",
    "NOV": "11",
    "DEZ": "12",
}
# Bank-PDF kann Leerzeichen in Datumsbruchstücken haben: „01.05 .2027“
_RE_KFZ_PERIOD = re.compile(
    r"vom\s+(\d{2})\.(\d{2})\.(\d{4})\s+bis\s+zum\s+(\d{2})\.(\d{2})\s*\.\s*(\d{4})",
    re.IGNORECASE,
)


def _kfz_end_month(day: int, month: int, year: int) -> tuple[str, str]:
    """„bis zum 01.MM.JJJJ“ → Periode endet am Vortag → Vormonat."""
    if day == 1:
        if month == 1:
            return "12", str(year - 1)
        return f"{month - 1:02d}", str(year)
    return f"{month:02d}", str(year)


def _datum_tt_mm_jjjj_aus_text(text: str) -> str | None:
    """Erste Datumzahl DD.MM.JJJJ im Buchungstext."""
    m = _DATUM_ERSTES.search(text)
    return m.group(0) if m else None


def _monat_jahr_aus_text(text: str, fallback_datum: str | None = None) -> tuple[str, str] | None:
    """Monat/Jahr als (MM, YYYY) aus Lohn-MM.YYYY, BEITRAG, Monats-Kürzel oder Datum."""
    m = _RE_LOHN_MMYYYY.search(text)
    if m:
        return m.group(1), m.group(2)

    m = _RE_BEITRAG_MMYY.search(text)
    if m:
        return m.group(1), f"20{m.group(2)}"

    m = _RE_MONAT_ABBR.search(text)
    if m:
        raw = m.group(1).upper()
        mon = _MONAT_MAP.get(raw) or _MONAT_MAP.get(raw[:3])
        if mon:
            return mon, f"20{m.group(2)}"

    # MM.YYYY ohne Tag (nach Entfernen voller DD.MM.YYYY, damit DATUM nicht gewinnt)
    ohne_voll = _DATUM_ERSTES.sub(" ", text)
    m = _RE_MM_YYYY.search(ohne_voll)
    if m:
        return m.group(1), m.group(2)

    m = _RE_DATUM_KURZ.search(text)
    if m:
        return m.group(2), f"20{m.group(3)}"

    d = _datum_tt_mm_jjjj_aus_text(text)
    if d:
        _tag, monat, jahr = d.split(".")
        return monat, jahr

    if fallback_datum:
        fb = _datum_tt_mm_jjjj_aus_text(str(fallback_datum))
        if fb:
            _tag, monat, jahr = fb.split(".")
            return monat, jahr
        # ISO YYYY-MM-DD
        m = re.match(r"(\d{4})-(\d{2})-(\d{2})", str(fallback_datum).strip())
        if m:
            return m.group(2), m.group(1)

    return None


def _jahr_aus_text(text: str, fallback_datum: str | None = None) -> str | None:
    m = _RE_UMST_JAHR.search(text)
    if m:
        return m.group(1)
    mj = _monat_jahr_aus_text(text, fallback_datum=fallback_datum)
    return mj[1] if mj else None


def _quartal_label_aus_text(text: str, fallback_datum: str | None = None) -> str | None:
    """``Q 3 2026`` aus ``Btrg 07-09/26`` oder Buchungsdatum."""
    m = _RE_BTRG_QUARTAL.search(text)
    if m:
        start_m = int(m.group(1))
        q = (start_m - 1) // 3 + 1
        return f"Q {q} 20{m.group(3)}"
    mj = _monat_jahr_aus_text(text, fallback_datum=fallback_datum)
    if not mj:
        return None
    q = (int(mj[0]) - 1) // 3 + 1
    return f"Q {q} {mj[1]}"


def _kuerzel_mit_datum(
    kuerzel: str,
    text: str,
    fallback_datum: str | None = None,
) -> str:
    """Ersetzt Datums-Platzhalter im Kürzel durch Werte aus dem Buchungstext."""
    # Kfz-Periode zuerst (eigene Platzhalter mm1/yyyy1/mm2/yyyy2)
    if "mm1" in kuerzel or "yyyy1" in kuerzel or "mm2" in kuerzel:
        km = _RE_KFZ_PERIOD.search(text)
        if km:
            mm2, yyyy2 = _kfz_end_month(int(km.group(4)), int(km.group(5)), int(km.group(6)))
            kuerzel = (
                kuerzel.replace("mm1", km.group(2))
                .replace("yyyy1", km.group(3))
                .replace("mm2", mm2)
                .replace("yyyy2", yyyy2)
            )
        else:
            kuerzel = re.sub(r"\s*mm1\s*yyyy1\s*-\s*mm2\s*yyyy2", "", kuerzel).strip()

    if _KUERZEL_DATUM_PLATZ in kuerzel:
        d = _datum_tt_mm_jjjj_aus_text(text) or (
            _datum_tt_mm_jjjj_aus_text(str(fallback_datum)) if fallback_datum else None
        )
        if d:
            kuerzel = kuerzel.replace(_KUERZEL_DATUM_PLATZ, d)
        else:
            kuerzel = (
                kuerzel.replace(_KUERZEL_DATUM_PLATZ, "")
                .replace("  ", " ")
                .strip(" -–—")
            )

    if _KUERZEL_QUARTAL in kuerzel:
        qlab = _quartal_label_aus_text(text, fallback_datum=fallback_datum)
        if qlab:
            kuerzel = kuerzel.replace(_KUERZEL_QUARTAL, qlab)
        else:
            kuerzel = kuerzel.replace(_KUERZEL_QUARTAL, "").replace("  ", " ").strip()

    mj = _monat_jahr_aus_text(text, fallback_datum=fallback_datum)
    if _KUERZEL_MONAT_DOT in kuerzel:
        if mj:
            kuerzel = kuerzel.replace(_KUERZEL_MONAT_DOT, f"{mj[0]}.{mj[1]}")
        else:
            kuerzel = (
                kuerzel.replace(_KUERZEL_MONAT_DOT, "")
                .replace("  ", " ")
                .strip(" -–—")
            )
    if _KUERZEL_MONAT_SPACE in kuerzel:
        if mj:
            kuerzel = kuerzel.replace(_KUERZEL_MONAT_SPACE, f"{mj[0]} {mj[1]}")
        else:
            kuerzel = (
                kuerzel.replace(_KUERZEL_MONAT_SPACE, "")
                .replace("  ", " ")
                .strip(" -–—")
            )

    # Jahres-Platzhalter zuletzt (nicht Teil von mm yyyy / mm.jjjj)
    if _KUERZEL_JAHR in kuerzel and _KUERZEL_MONAT_SPACE not in kuerzel and _KUERZEL_MONAT_DOT not in kuerzel:
        jahr = _jahr_aus_text(text, fallback_datum=fallback_datum)
        if jahr:
            kuerzel = kuerzel.replace(_KUERZEL_JAHR, jahr)
        else:
            kuerzel = kuerzel.replace(_KUERZEL_JAHR, "").replace("  ", " ").strip()

    return kuerzel


def apply_buchungs_mapping(rows: list[dict[str, Any]]) -> int:
    """
    Ersetzt ``Buchungstext`` durch das Kürzel und setzt ``BU Gkto``, wenn die
    Regel ein Konto vorsieht. Erster Treffer nach absteigender Suchlänge gewinnt.
    Vor dem Abgleich werden typische Bank-Vorsätze (z. B. „Abbuchung Lastschrift“,
    „Überweisung Online“, „Gutschr einer Überw“) aus ``Buchungstext`` entfernt.
    Ohne ``.*`` im Suchtext: Vergleich als Teilstring, ohne Groß-/Kleinschreibung.
    Mit ``.*``: beliebiger Text zwischen den durch ``.*`` getrennten Teilstücken.
    Enthält das Kürzel ``tt.mm.jjjj`` bzw. ``mm.jjjj`` / ``mm yyyy``, wird es durch
    Datum bzw. Monat/Jahr aus dem Buchungstext (sonst Zeilen-Datum) ersetzt.
    """
    rules = sorted(BUCHUNG_PARSER_RULES, key=lambda t: len(t[0]), reverse=True)
    n = 0
    for row in rows:
        if row.get("_skip_buchung_mapping"):
            continue
        raw = str(row.get("Buchungstext") or "").strip()
        if not raw:
            continue
        cleaned = bereinige_pdf_text(raw)
        text = cleaned if cleaned.strip() else raw
        row["Buchungstext"] = text
        fallback_datum = str(row.get("Datum") or "")
        for parser, bu, kuerzel in rules:
            if _pattern_matches(parser, text):
                row["Buchungstext"] = _kuerzel_mit_datum(
                    kuerzel, text, fallback_datum=fallback_datum
                )
                if bu:
                    row["BU Gkto"] = bu
                n += 1
                break
    if n:
        logger.info("Buchungstext-Mapping: %s Zeilen auf Kürzel/BU gesetzt", n)
    return n
