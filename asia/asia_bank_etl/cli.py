"""CLI: Argumente, Umgebungsvariablen, Logging."""

from __future__ import annotations

import argparse
import logging
import os
import sys

from .config import AsiaEtlConfig, config_from_env
from .runner import run_etl


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Asia Bank ETL: Kontoauszug PDF + Agenda + Stripe-CSV → Excel und/oder SQLite/SQL."
    )
    p.add_argument(
        "--pdf",
        dest="pdf_file",
        default=None,
        help="Kontoauszug-PDF (oder ENV ASIA_PDF_FILE).",
    )
    p.add_argument(
        "--agenda",
        dest="agenda_file",
        default=None,
        help="Agenda-Excel mit Zuordnung BU Gkto (oder ENV ASIA_AGENDA_FILE). Optional.",
    )
    p.add_argument(
        "--output",
        dest="output_file",
        default=None,
        help="Ausgabe: .xlsx (Excel + Final), .sqlite/.db (nur DB), .sql (SQL-Skript). ENV ASIA_OUTPUT_FILE.",
    )
    p.add_argument(
        "--sql-out",
        dest="sql_output_file",
        default=None,
        help="Zusätzliche SQLite-Datei bei Excel-Hauptausgabe (oder ENV ASIA_SQL_OUT).",
    )
    p.add_argument(
        "--agenda-sheet",
        dest="agenda_sheet",
        default=None,
        help="Agenda-Tabellenblatt (oder ENV ASIA_AGENDA_SHEET). Standard: split (2)",
    )
    p.add_argument(
        "--excel-title",
        dest="excel_title",
        default=None,
        help="Titelzeile oben im Blatt Buchungen.",
    )
    return p


def main(argv: list[str] | None = None) -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )

    args = _build_parser().parse_args(argv)

    cfg = config_from_env(AsiaEtlConfig())

    if args.pdf_file:
        cfg.pdf_file = os.path.normpath(args.pdf_file.strip())
    if args.agenda_file is not None:
        cfg.agenda_file = (
            os.path.normpath(args.agenda_file.strip()) if args.agenda_file.strip() else ""
        )
    if args.output_file:
        cfg.output_file = os.path.normpath(args.output_file.strip())
    if args.sql_output_file:
        cfg.sql_output_file = os.path.normpath(args.sql_output_file.strip())
    if args.agenda_sheet:
        cfg.agenda_sheet = args.agenda_sheet.strip()

    try:
        run_etl(cfg, excel_titel=args.excel_title)
    except ValueError:
        sys.exit(1)
