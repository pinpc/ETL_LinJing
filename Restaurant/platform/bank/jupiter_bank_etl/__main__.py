"""
Module entrypoint for `python -m jupiter_bank_etl`.

Kept intentionally small; mirrors `run_jupiter_bank.py` but lives inside the package.
"""

from __future__ import annotations

import argparse
import os

from .core import JupiterBankETL


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Jupiter Bank ETL - Excel/SQLite")
    p.add_argument(
        "--input",
        dest="input_dir",
        default=os.environ.get("JUPITER_INPUT_DIR", ""),
        help="Verzeichnis mit Rechnungen (oder ENV JUPITER_INPUT_DIR).",
    )
    p.add_argument(
        "--out",
        dest="out_file",
        default=os.environ.get("JUPITER_OUT_FILE", ""),
        help="Ausgabe-Excel-Pfad (oder ENV JUPITER_OUT_FILE).",
    )
    p.add_argument(
        "--pdf",
        dest="kontoauszug_pdf",
        default=os.environ.get("JUPITER_KONTOAUSZUG_PDF", ""),
        help="Kontoauszug-PDF-Pfad (oder ENV JUPITER_KONTOAUSZUG_PDF).",
    )
    p.add_argument(
        "--sqlite",
        dest="sqlite_db",
        default=os.environ.get("JUPITER_SQLITE_DB", ""),
        help="Optional: SQLite DB Pfad (oder ENV JUPITER_SQLITE_DB).",
    )
    p.add_argument(
        "--agenda",
        dest="agenda_file",
        default=os.environ.get("JUPITER_AGENDA_FILE", ""),
        help="Optional: Agenda-Excel fuer BU-Vergleich (oder ENV JUPITER_AGENDA_FILE).",
    )
    return p


def main(argv: list[str] | None = None) -> None:
    args = _build_parser().parse_args(argv)

    if not args.input_dir or not args.out_file:
        raise SystemExit(
            "Fehlende Parameter. Beispiel:\n"
            '  python -m jupiter_bank_etl --input "<dir>" --out "<file.xlsx>" --pdf "<kontoauszug.pdf>"\n'
            "oder ENV: JUPITER_INPUT_DIR / JUPITER_OUT_FILE / JUPITER_KONTOAUSZUG_PDF"
        )

    input_dir = os.path.normpath(args.input_dir.strip())
    out_file = os.path.normpath(args.out_file.strip())
    kontoauszug = os.path.normpath(args.kontoauszug_pdf.strip()) if args.kontoauszug_pdf else None
    sqlite_db = os.path.normpath(args.sqlite_db.strip()) if args.sqlite_db else None
    if sqlite_db is None and out_file:
        sqlite_db = os.path.splitext(out_file)[0] + ".sqlite"

    agenda_file = os.path.normpath(args.agenda_file.strip()) if args.agenda_file else None

    JupiterBankETL().run(
        input_dir,
        out_file,
        kontoauszug,
        sqlite_path=sqlite_db,
        agenda_path=agenda_file,
    )


if __name__ == "__main__":
    main()
