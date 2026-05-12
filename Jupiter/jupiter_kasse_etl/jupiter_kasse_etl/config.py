from __future__ import annotations

from decimal import Decimal
from pathlib import Path

TARGET_COLUMNS = [
    "Umsatz Euro",
    "BU Gkto",
    "Beleg 1",
    "Datum",
    "KOST 1",
    "Bank",
    "Buchungstext",
]

COLUMN_WIDTHS = {"A": 15, "B": 12, "C": 10, "D": 12, "E": 10, "F": 10, "G": 40}

STANDARD_KOST = 2000
STANDARD_BANK = 1001

BU_GKTO_ALLOPAY_EXPENSE = 1360
BU_GKTO_BAUMARKT_EXPENSE = 904280
BU_GKTO_FISCH_FOOD = 3300
BU_GKTO_INCOME = 8000
BU_GKTO_ALLOPAY_19 = 8400
BU_GKTO_ALLOPAY_7 = 8300

MERGE_TOLERANCE = Decimal("0.01")
XL_EURO_NUM_FMT = "#,##0.00"

DEFAULT_BASE_PATH = Path(r"C:\temp_cursor\LinJing\02_Jupiter\Buchhaltung Jupiter 03.2026\Jupiter Kasse 03.2026")
DEFAULT_CASHBOOK_CANDIDATES = [
    DEFAULT_BASE_PATH / "02b Kassenbuch_Jupiter 03.2026.xlsx",
    DEFAULT_BASE_PATH / "02a Kassenbuch Jupiter 03.2026.pdf",
]
DEFAULT_OUTPUT_PATH = (
    Path(r"C:\temp_cursor\LinJing\03_Coding\ETL_LinJing\Jupiter\jupiter_kasse_etl")
    / "result"
    / "etl_umsatz_jupiter_2603.xlsx"
)
