"""Stripe-CSV-Dateien (*Asia-Stripe*.csv) für das Allopay-Blatt auswerten."""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

import pandas as pd

from .constants import CSV_ENCODINGS

logger = logging.getLogger(__name__)


def verarbeite_stripe_csvs(verzeichnis: str, config: dict[str, Any]) -> list[dict[str, Any]]:
    """Verarbeitet Stripe-CSV-Dateien und aggregiert Zahlungen und Gebühren."""
    stripe_rows: list[dict[str, Any]] = []
    path = Path(verzeichnis)
    csv_files = sorted(path.glob("*Asia-Stripe*.csv"))
    logger.info("Gefundene CSV-Dateien: %s", len(csv_files))

    for csv_file in csv_files:
        logger.info("  Verarbeite: %s", csv_file.name)
        match = re.search(r"(\d{4}-\d{2}-\d{2})", csv_file.name)
        if not match:
            logger.warning("Kein Datum im Dateinamen: %s", csv_file.name)
            continue
        datum_iso = match.group(1)
        y, m, d = datum_iso.split("-")
        datum_ddmmyyyy = f"{d}.{m}.{y}"

        df = None
        for encoding in CSV_ENCODINGS:
            try:
                df = pd.read_csv(csv_file, encoding=encoding, sep=None, engine="python")
                logger.debug("CSV erfolgreich mit Encoding '%s' gelesen", encoding)
                break
            except Exception as e:
                logger.debug("Encoding '%s' fehlgeschlagen: %s", encoding, e)
                continue

        if df is None:
            logger.error("CSV konnte mit keinem Encoding gelesen werden: %s", csv_file.name)
            continue

        amount_col = None
        fee_col = None
        for col in df.columns:
            if col.lower() == "amount":
                amount_col = col
            if col.lower() == "feeamount":
                fee_col = col
        if amount_col is None or fee_col is None:
            logger.warning(
                "Spalten 'amount' oder 'feeAmount' nicht gefunden in %s", csv_file.name
            )
            logger.debug("Gefundene Spalten: %s", list(df.columns))
            continue

        try:
            amount_sum = pd.to_numeric(df[amount_col], errors="coerce").sum()
            fee_sum = pd.to_numeric(df[fee_col], errors="coerce").sum()
            logger.info(
                "  %s: amount=%.2f €, fee=%.2f €",
                csv_file.name,
                amount_sum,
                fee_sum,
            )
        except Exception as e:
            logger.error("Fehler bei Summenberechnung für %s: %s", csv_file.name, e)
            continue

        if amount_sum != 0:
            stripe_rows.append(
                {
                    "Umsatz Euro": round(amount_sum, 2),
                    "BU Gkto": config["STRIPE_KONTO_UMSATZ"],
                    "Beleg 1": 1,
                    "Datum": datum_ddmmyyyy,
                    "KOST 1": config["STRIPE_KOST"],
                    "Bank": config["STRIPE_BANK"],
                    "Buchungstext": f"allopay {datum_ddmmyyyy}",
                }
            )
        if fee_sum != 0:
            fee_neg = -fee_sum
            stripe_rows.append(
                {
                    "Umsatz Euro": round(fee_neg, 2),
                    "BU Gkto": config["STRIPE_KONTO_GEBUEHR"],
                    "Beleg 1": 1,
                    "Datum": datum_ddmmyyyy,
                    "KOST 1": config["STRIPE_KOST"],
                    "Bank": config["STRIPE_BANK"],
                    "Buchungstext": f"allopay Gebühr {datum_ddmmyyyy}",
                }
            )

    for i, row in enumerate(stripe_rows, 1):
        row["Beleg 1"] = i

    return stripe_rows
