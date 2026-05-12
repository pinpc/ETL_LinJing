from __future__ import annotations

from decimal import Decimal


TARGET_COLUMNS = [
    "Umsatz Euro",
    "BU Gkto",
    "Beleg 1",
    "Datum",
    "KOST 1",
    "Bank",
    "Buchungstext",
]

STANDARD_KOST = "1000"
STANDARD_BANK = "1000"

BU_GKTO_POSITIVE = "8000"
BU_GKTO_NEGATIVE = "1360"
BU_GKTO_ALLOPAY_19 = "8400"
BU_GKTO_ALLOPAY_7 = "8300"

MERGE_TOLERANCE = Decimal("0.01")
XL_EURO_NUM_FMT = "#,##0.00"

