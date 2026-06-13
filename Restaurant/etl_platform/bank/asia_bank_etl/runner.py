"""Orchestrierung: PDF → Agenda-Merge → Excel → Final."""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Any

from .config import AsiaEtlConfig, as_legacy_dict
from .invoices import load_invoices
from .excel_export import exportiere_excel
from .final_sheet import erstelle_final_blatt
from .sql_export import exportiere_sql_skript, exportiere_sqlite
from .buchungstext_mapping import apply_buchungs_mapping
from .merge_agenda import lade_agenda, merge_mit_agenda_und_split
from .pdf_statement import parse_sparkasse_pdf
from .stripe_csv import verarbeite_stripe_csvs
from .text_normalize import kuerze_stripe_text

logger = logging.getLogger(__name__)


def run_etl(config: AsiaEtlConfig, *, excel_titel: str | None = None) -> None:
    """
    Führt den kompletten Asia-Bank-ETL-Lauf aus.

    ``AGENDA_FILE`` ist optional: fehlt die Datei, werden Buchungen ohne Agenda-Zuordnung exportiert
    (BU Gkto leer außer Stripe-Kürzung).
    """
    _ = excel_titel  # API-kompatibel; Kontoauszug-Blatt hat keine Titelzeile mehr
    cfg = as_legacy_dict(config)

    if not cfg["PDF_FILE"] or not Path(cfg["PDF_FILE"]).exists():
        msg = f"PDF-Datei fehlt oder existiert nicht: {cfg.get('PDF_FILE')!r}"
        logger.error(msg)
        raise ValueError(msg)
    if not cfg["OUTPUT_FILE"]:
        msg = "Ausgabe-Pfad ist leer (--output oder ASIA_OUTPUT_FILE)."
        logger.error(msg)
        raise ValueError(msg)

    try:
        logger.info("Lese PDF: %s", cfg["PDF_FILE"])
        pdf_rows = parse_sparkasse_pdf(cfg["PDF_FILE"])
        logger.info("%s Buchungen extrahiert", len(pdf_rows))

        if not pdf_rows:
            logger.error("Keine Buchungen extrahiert!")
            return

        agenda_raw = (cfg.get("AGENDA_FILE") or "").strip()
        if not agenda_raw:
            logger.warning(
                "Keine Agenda-Datei angegeben – BU Gkto wird nicht aus Agenda befüllt."
            )
            df_agenda = None
        elif not Path(agenda_raw).exists():
            logger.warning(
                "Agenda-Datei nicht gefunden (%s) – BU Gkto wird nicht aus Agenda befüllt.",
                agenda_raw,
            )
            df_agenda = None
        else:
            df_agenda = lade_agenda(agenda_raw, cfg["AGENDA_SHEET"])
            logger.info("%s Agenda-Zeilen geladen", len(df_agenda))

        if df_agenda is not None:
            buchungen_rows = merge_mit_agenda_und_split(pdf_rows, df_agenda, cfg)
        else:
            buchungen_rows = [
                {
                    "Umsatz Euro": r["Umsatz Euro"],
                    "BU Gkto": "",
                    "Beleg 1": i + 1,
                    "Datum": r["Datum"],
                    "KOST 1": cfg["KOST"],
                    "Bank": cfg["BANK_KONTO"],
                    "Buchungstext": kuerze_stripe_text(r["Buchungstext"], r["Datum"]),
                }
                for i, r in enumerate(pdf_rows)
            ]

        apply_buchungs_mapping(buchungen_rows)

        verzeichnis = str(Path(cfg["PDF_FILE"]).parent)
        edeka_rows = [row.as_excel_dict() for row in load_invoices(verzeichnis)]
        allopay_rows = verarbeite_stripe_csvs(verzeichnis, cfg)
        logger.info(
            "%s Zeilen aus Stripe-CSVs für Allopay erzeugt", len(allopay_rows)
        )
        logger.info("Blatt 'EDEKA': %s Rechnung(en)", len(edeka_rows))

        out_path = Path(cfg["OUTPUT_FILE"])
        suf = out_path.suffix.lower()
        sql_extra = (cfg.get("SQL_OUTPUT_FILE") or "").strip()

        logger.info("Exportiere nach: %s", cfg["OUTPUT_FILE"])

        if suf in (".sqlite", ".db"):
            exportiere_sqlite(
                buchungen_rows, allopay_rows, str(out_path), cfg
            )
            logger.info("Nur SQLite – kein Excel, kein Final-Blatt.")
        elif suf == ".sql":
            exportiere_sql_skript(
                buchungen_rows, allopay_rows, str(out_path), cfg
            )
            logger.info("Nur SQL-Skript – kein Excel, kein Final-Blatt.")
        else:
            exportiere_excel(
                buchungen_rows,
                allopay_rows,
                cfg["OUTPUT_FILE"],
                cfg,
                edeka_rows=edeka_rows,
            )
            erstelle_final_blatt(cfg["OUTPUT_FILE"])

        if sql_extra:
            logger.info("Zusätzliche SQLite-Datei: %s", sql_extra)
            exportiere_sqlite(buchungen_rows, allopay_rows, sql_extra, cfg)

        ohne_bu = sum(1 for r in buchungen_rows if not r["BU Gkto"])
        ein = sum(
            r["Umsatz Euro"]
            for r in buchungen_rows
            if isinstance(r["Umsatz Euro"], (int, float)) and r["Umsatz Euro"] > 0
        )
        aus = sum(
            r["Umsatz Euro"]
            for r in buchungen_rows
            if isinstance(r["Umsatz Euro"], (int, float)) and r["Umsatz Euro"] < 0
        )
        logger.info("Blatt 'Buchungen': %s Zeilen", len(buchungen_rows))
        logger.info(
            "  BU Gkto befüllt: %s / %s",
            len(buchungen_rows) - ohne_bu,
            len(buchungen_rows),
        )
        logger.info("  BU Gkto leer (gelb): %s", ohne_bu)
        logger.info("Einnahmen: %s €", format(ein, ",.2f"))
        logger.info("Ausgaben:  %s €", format(aus, ",.2f"))
        logger.info("Netto:     %s €", format(ein + aus, ",.2f"))

        summe_allopay = sum(
            r["Umsatz Euro"]
            for r in allopay_rows
            if isinstance(r["Umsatz Euro"], (int, float))
        )
        logger.info("Blatt 'Allopay': %s Zeilen", len(allopay_rows))
        logger.info("  Summe: %s €", format(float(summe_allopay), ",.2f"))

        logger.info("Verarbeitung abgeschlossen.")

    except Exception as e:
        logger.error("Fehler bei der Verarbeitung: %s", e, exc_info=True)
        sys.exit(1)
