#!/usr/bin/env python3
"""
CLI: Jupiter Bank ETL (Kontoauszug + Rechnungen → Excel, optional SQLite).

  python run_jupiter_bank.py

Pfade unten anpassen oder Umgebungsvariablen nutzen (optional erweiterbar).
"""

import os

from jupiter_bank_etl import JupiterBankETL

if __name__ == "__main__":
    INPUT_DIR = os.path.normpath(
        r"C:\temp_jingling\ALOP\Buchhaltung Jupiter 02.2026\Jupiter Konto 02.2026"
    )
    OUT_FILE = os.path.normpath(
        r"C:\temp_cursor\LinJing\03_Coding\Allop\jupiter_bank_export.xlsx"
    )
    SQLITE_DB = os.path.splitext(OUT_FILE)[0] + ".sqlite"
    KONTOAUSZUG = os.path.normpath(
        r"C:\temp_jingling\ALOP\Buchhaltung Jupiter 02.2026\Jupiter Konto 02.2026\00b Nr.002 Kontoauszug 2026.02.27.pdf"
    )

    JupiterBankETL().run(INPUT_DIR, OUT_FILE, KONTOAUSZUG, sqlite_path=SQLITE_DB)
