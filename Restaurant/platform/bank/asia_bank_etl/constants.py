"""Gemeinsame Konstanten für Sparkasse-PDF und CSV-Lesen."""

# CSV-Encoding-Fallbacks für robusteres Lesen
CSV_ENCODINGS = ("utf-8", "latin-1", "cp1252", "iso-8859-1")

BUCHUNGSTYPEN = (
    "Abbuchung Lastschrift",
    "Abbuchung Firmen-LS",
    "Überweisung Online",
    "Gutschr einer Überw",
    "Dauerauftrag",
    "Debitkartenzahl. EUR",
    "Bargeldeinzahlung GA",
    "Sonst ZV preisfrei",
    "Abrechnung",
)

STOPP_MUSTER = (
    "Kontostand am",
    "Anzahl Anlagen",
    "siehe Anlage",
    "Sparkasse Allgäu",
    "Residenzplatz",
    "Anstalt des",
    "Sparkassen-Finanzgruppe",
)
