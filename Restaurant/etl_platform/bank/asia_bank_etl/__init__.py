"""
Asia Bank ETL – Kontoauszug (Sparkasse PDF), Agenda-Excel, Stripe-CSV → Excel.

Verwendung:
    python -m asia_bank_etl --pdf <kontoauszug.pdf> --output <out.xlsx|out.sqlite|out.sql> [--sql-out <extra.sqlite>]

Umgebungsvariablen (optional): ASIA_PDF_FILE, ASIA_AGENDA_FILE, ASIA_OUTPUT_FILE, …
"""

from __future__ import annotations

from .config import AsiaEtlConfig, as_legacy_dict, config_from_env
from .runner import run_etl

__all__ = [
    "AsiaEtlConfig",
    "as_legacy_dict",
    "config_from_env",
    "run_etl",
]
