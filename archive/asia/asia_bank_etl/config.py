"""Konfiguration Asia Bank ETL (Pfade, Konten, Agenda-Blatt)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any


@dataclass
class AsiaEtlConfig:
    """Typisierte Konfiguration; für bestehende Hilfsfunktionen → `as_legacy_dict`."""

    pdf_file: str = r"C:\temp_jingling\ALOP\Asia Buchhaltung 03.2026\Asia Konto 03.2026\01b Kontoauszug 2026_03.pdf"
    agenda_file: str = ""
    output_file: str = r"C:\temp_cursor\LinJing\03_Coding\ETL_LinJing\asia\asia_bank_etl\result\asia_bank_etl_0326.xlsx"
    sql_output_file: str = r"C:\temp_cursor\LinJing\03_Coding\ETL_LinJing\asia\asia_bank_etl\result\asia_bank_etl_0326.sqlite"
    agenda_sheet: str = "split (2)"
    bank_konto: int = 1200
    kost: int = 1000
    stripe_bank: int = 1200
    stripe_kost: int = 1000
    stripe_konto_umsatz: str = "1360"
    stripe_konto_gebuehr: str = "4970"


def as_legacy_dict(c: AsiaEtlConfig) -> dict[str, Any]:
    """Gleiche Schlüssel wie im ursprünglichen Skript (Kompatibilität)."""
    return {
        "PDF_FILE": c.pdf_file,
        "AGENDA_FILE": c.agenda_file,
        "OUTPUT_FILE": c.output_file,
        "SQL_OUTPUT_FILE": c.sql_output_file,
        "AGENDA_SHEET": c.agenda_sheet,
        "BANK_KONTO": c.bank_konto,
        "KOST": c.kost,
        "STRIPE_BANK": c.stripe_bank,
        "STRIPE_KOST": c.stripe_kost,
        "STRIPE_KONTO_UMSATZ": c.stripe_konto_umsatz,
        "STRIPE_KONTO_GEBUEHR": c.stripe_konto_gebuehr,
    }


def _env_str(key: str, fallback: str) -> str:
    v = os.environ.get(key)
    if v is None or not str(v).strip():
        return fallback
    return str(v).strip()


def _env_int(key: str, fallback: int) -> int:
    v = os.environ.get(key)
    if v is None or not str(v).strip():
        return fallback
    return int(str(v).strip())


def config_from_env(overrides: AsiaEtlConfig | None = None) -> AsiaEtlConfig:
    """Erzeugt Konfiguration aus optionalen Defaults plus Umgebungsvariablen."""

    base = overrides or AsiaEtlConfig()
    return AsiaEtlConfig(
        pdf_file=_env_str("ASIA_PDF_FILE", base.pdf_file),
        agenda_file=_env_str("ASIA_AGENDA_FILE", base.agenda_file),
        output_file=_env_str("ASIA_OUTPUT_FILE", base.output_file),
        sql_output_file=_env_str("ASIA_SQL_OUT", base.sql_output_file),
        agenda_sheet=_env_str("ASIA_AGENDA_SHEET", base.agenda_sheet),
        bank_konto=_env_int("ASIA_BANK_KONTO", base.bank_konto),
        kost=_env_int("ASIA_KOST", base.kost),
        stripe_bank=_env_int("ASIA_STRIPE_BANK", base.stripe_bank),
        stripe_kost=_env_int("ASIA_STRIPE_KOST", base.stripe_kost),
        stripe_konto_umsatz=_env_str(
            "ASIA_STRIPE_KONTO_UMSATZ", base.stripe_konto_umsatz
        ),
        stripe_konto_gebuehr=_env_str(
            "ASIA_STRIPE_KONTO_GEBUEHR", base.stripe_konto_gebuehr
        ),
    )
