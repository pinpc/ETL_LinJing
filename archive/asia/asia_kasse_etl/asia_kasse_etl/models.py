from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path


@dataclass(frozen=True)
class BuchungRow:
    umsatz_euro: Decimal
    bu_gkto: str
    beleg_1: str
    datum: str
    kost_1: str
    bank: str
    buchungstext: str


@dataclass(frozen=True)
class PipelineResult:
    saved_path: Path
    buchung_count: int
    allopay_count: int
    final_count: int
    pdf_base_dir: Path

