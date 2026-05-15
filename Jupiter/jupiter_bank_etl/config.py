"""Konstanten: Konten, Excel-Styles, FiBu-Regeln."""

import re

from openpyxl.styles import Font

# Spalte "Bank" im Excel (VR-Konto Jupiter), nicht BU Gkto / Sachkonto
BANK = "1201"
KOST = "2000"

XL_EURO_NUM_FMT = "#,##0.00;[Black]-#,##0.00"
XL_FONT = Font(name="Calibri", size=11, color="000000")
XL_FONT_BOLD = Font(name="Calibri", bold=True, size=11, color="000000")

FIBU_RULES = [
    (re.compile(r"WOLT|Wolt", re.I), "H", "8300", "Wolt Umsatz 7 %"),
    (re.compile(r"Stripe|allO", re.I), "H", "1360", "allO pay"),
    (re.compile(r"UBER|Custodian", re.I), "H", "8300", "Uber Umsatz 7 %"),
    (re.compile(r"TAKEAWAY|LIEFERANDO|DERDENGELDEN", re.I), "H", "8300", "LIEFERANDO.DE Umsatz 7 %"),
    (re.compile(r"EINZAHLUNG|Einzahlung|GS Schwangau|Kontoauszug Nr", re.I), "H", "1360", "von Kasse"),
    (re.compile(r"Ling\s+Jin.*Ausleihen|Ausleihen.*Ling\s+Jin", re.I), "H", "1890", "Ling Jin Ausleihen"),
    (re.compile(r"Ling\s+Jin.*Ausleihen|Ausleihen.*Ling\s+Jin", re.I), "S", "1890", "Ling Jin Ausleihen"),
    (re.compile(r"Vodafone", re.I), "S", "904920", "Vodafone Internet"),
    (
        re.compile(r"Landeshauptstadt\s+München|Landeshauptstadt\s+Munchen", re.I),
        "S",
        "4390",
        "Landeshauptstadt München Parkberechtigungsgebühr",
    ),
    (re.compile(r"OBERHESSISCHE\s+VERSORGUNGS|OVAG", re.I), "S", "904240", "ovag Strom"),
    (re.compile(r"meistro.*65742", re.I), "S", "904240", "meistro Energie Gas"),
    (re.compile(r"meistro.*65741", re.I), "S", "904240", "meistro Energie Strom"),
    (re.compile(r"meistro", re.I), "S", "904240", "meistro Energie"),
    (re.compile(r"ORIENT\s+SHOP\s+TRINH", re.I), "S", "3300", "ORIENT SHOP WE 7%"),
    (re.compile(r"HAMBERGER|Grossmarkt", re.I), "S", "3300", "HAMBERGER Wareneinkauf"),
    (re.compile(r"Paulaner", re.I), "S", "3400", "Paulaner Getränke"),
    (re.compile(r"allO Technology GmbH", re.I), "S", "904930", "allO Technology Gebühr"),
    (re.compile(r"Schankanlagen|Häufle", re.I), "S", "904250", "Schankanlagenwartung"),
    (
        re.compile(r"Wittmann\s+Entsorgungswirtschaft|WEW-RG", re.I),
        "S",
        "904280",
        "Wittmann Entsorgungswirtschaft GmbH Absaugen Fettabscheider",
    ),
    (re.compile(r"A\.R\.Z\.", re.I), "S", "904280", "A.R.Z. GmbH"),
    (re.compile(r"Sani.Blitz|Gallmeier", re.I), "S", "904280", "Sani-Blitz"),
    (re.compile(r"Sheue.Ru Wang.+Rechnung|Wang.+2025", re.I), "S", "904955", "Wang Fibu"),
    (re.compile(r"Kloh", re.I), "S", "3106", "Kloh Entsorgung"),
    (re.compile(r"AVIA|Tankstelle", re.I), "S", "904530", "Avia Tanken"),
    (re.compile(r"JET OLV|PAYONE", re.I), "S", "904530", "JET Tanken"),
    (re.compile(r"AOK[-\\s]?Bayern", re.I), "S", "1743", "AOK Bayern Beitrag"),
    (re.compile(r"AOK[-\\s]?Bayern", re.I), "H", "1743", "AOK Bayern Beitrag"),
    (
        re.compile(r"BGN|Berufsgenossenschaft|Nahrungsmittel und Gastgewerbe", re.I),
        "S",
        "4138",
        "BGN Beitrag",
    ),
    (re.compile(r"M-net", re.I), "S", "904925", "M-net Internet"),
    (re.compile(r"\bMiete\b", re.I), "S", "4210", "Miete"),
    (re.compile(r"Erstattung Lohnkosten", re.I), "S", "1360", "Erstattung Lohnkosten Jupiter"),
    (re.compile(r"\bLohn\b", re.I), "S", "1740", "Lohn"),
    (re.compile(r"Zhou Import", re.I), "S", "3300", "Zhou Wareneinkauf"),
    (re.compile(r"Sheue.Ru Wang.+Lohn|Wang Ping Zhou", re.I), "S", "1740", "Lohn"),
    (re.compile(r"Abschluss|Kontoführung", re.I), "S", "4970", "Bankgebühr"),
]

SQLITE_TABLE_KONTO = "konto_jupiter"
