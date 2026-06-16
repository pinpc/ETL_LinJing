from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path


@dataclass(frozen=True)
class CashbookTransaction:
    datum: str
    einnahmen: Decimal
    ausgaben: Decimal
    buchungstext: str


@dataclass(frozen=True)
class BuchungRow:
    umsatz_euro: Decimal
    bu_gkto: int
    beleg_1: str
    datum: str
    kost_1: int
    bank: int
    buchungstext: str


@dataclass(frozen=True)
class AllopayPdfData:
    datum: str
    z_nummer: str
    umsatz_7: Decimal
    umsatz_19: Decimal
    allopay_payment_sum: Decimal
    dateiname: str


@dataclass(frozen=True)
class PipelineResult:
    saved_path: Path
    umsatz_count: int
    allopay_count: int
    final_count: int
    pdf_base_dir: Path
