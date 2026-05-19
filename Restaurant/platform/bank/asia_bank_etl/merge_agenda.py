"""PDF-Buchungen mit Agenda zusammenführen (inkl. Fruchthaus-Split)."""

from __future__ import annotations

import logging
from typing import Any

import pandas as pd

from .text_normalize import kuerze_stripe_text

logger = logging.getLogger(__name__)


def lade_agenda(agenda_path: str, sheet: str) -> pd.DataFrame:
    """Lädt Agenda aus Excel-Datei und bereinigt Datentypen."""
    try:
        df = pd.read_excel(agenda_path, sheet_name=sheet)
        df["Datum"] = pd.to_datetime(df["Datum"]).dt.strftime("%d.%m.%Y")
        df["Umsatz Euro"] = pd.to_numeric(df["Umsatz Euro"], errors="coerce").round(2)
        df["BU Gkto"] = df["BU Gkto"].fillna("").astype(str).str.replace(
            r"\.0$", "", regex=True
        )
        df["Buchungstext"] = df["Buchungstext"].astype(str).str.strip()
        return df
    except Exception as e:
        logger.error("Fehler beim Laden der Agenda %s: %s", agenda_path, e)
        raise


def merge_mit_agenda_und_split(
    pdf_rows: list[dict[str, Any]],
    df_agenda: pd.DataFrame,
    config: dict[str, Any],
) -> list[dict[str, Any]]:
    """Mergt PDF-Buchungen mit Agenda und teilt Fruchthaus-Zahlungen auf."""
    fruchthaus_pdf = [r for r in pdf_rows if "Fruchthaus" in r["Buchungstext"]]
    fruchthaus_agenda = df_agenda[
        df_agenda["Buchungstext"].str.contains("Fruchthaus", na=False)
    ]

    if len(fruchthaus_pdf) > 1:
        logger.error(
            "Mehrere Fruchthaus-Buchungen im Kontoauszug gefunden. Automatischer Split nicht möglich."
        )
        raise ValueError("Fruchthaus-Validierung fehlgeschlagen")

    if len(fruchthaus_pdf) == 1:
        if len(fruchthaus_agenda) == 0:
            logger.error(
                "Keine Fruchthaus-Zeilen in der Agenda gefunden. Split nicht möglich."
            )
            raise ValueError("Fruchthaus-Split fehlgeschlagen")
        summe_agenda = round(fruchthaus_agenda["Umsatz Euro"].sum(), 2)
        buchungsbetrag = round(fruchthaus_pdf[0]["Umsatz Euro"], 2)
        if abs(summe_agenda - buchungsbetrag) > 0.02:
            logger.error(
                "Summe der Agenda-Fruchthaus-Zeilen (%.2f) stimmt nicht mit Buchungsbetrag (%.2f) überein.",
                summe_agenda,
                buchungsbetrag,
            )
            raise ValueError("Fruchthaus-Summe stimmt nicht überein")
        do_split = True
    else:
        do_split = False

    agenda_by_key: dict[tuple[str, float], Any] = {}
    for _, r in df_agenda.iterrows():
        key = (r["Datum"], round(r["Umsatz Euro"], 2))
        if key not in agenda_by_key:
            agenda_by_key[key] = r

    output_rows: list[dict[str, Any]] = []
    beleg_counter = 1

    for pdf_row in pdf_rows:
        datum = pdf_row["Datum"]
        gesamt = round(pdf_row["Umsatz Euro"], 2)
        text = pdf_row["Buchungstext"]

        if "Fruchthaus" in text and do_split:
            for _, teil in fruchthaus_agenda.iterrows():
                output_rows.append(
                    {
                        "Umsatz Euro": teil["Umsatz Euro"],
                        "BU Gkto": teil["BU Gkto"],
                        "Beleg 1": beleg_counter,
                        "Datum": teil["Datum"],
                        "KOST 1": config["KOST"],
                        "Bank": config["BANK_KONTO"],
                        "Buchungstext": teil["Buchungstext"],
                    }
                )
                beleg_counter += 1
            continue

        key = (datum, gesamt)
        if key in agenda_by_key:
            m = agenda_by_key[key]
            output_rows.append(
                {
                    "Umsatz Euro": gesamt,
                    "BU Gkto": m["BU Gkto"],
                    "Beleg 1": beleg_counter,
                    "Datum": datum,
                    "KOST 1": config["KOST"],
                    "Bank": config["BANK_KONTO"],
                    "Buchungstext": m["Buchungstext"],
                }
            )
        else:
            fallback_text = kuerze_stripe_text(text, datum)
            output_rows.append(
                {
                    "Umsatz Euro": gesamt,
                    "BU Gkto": "",
                    "Beleg 1": beleg_counter,
                    "Datum": datum,
                    "KOST 1": config["KOST"],
                    "Bank": config["BANK_KONTO"],
                    "Buchungstext": fallback_text,
                }
            )
        beleg_counter += 1

    return output_rows
