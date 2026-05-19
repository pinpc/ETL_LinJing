"""SQLite-Export (Tabelle konto_jupiter)."""

import os
import sqlite3

from .config import SQLITE_TABLE_KONTO
from .utils import datum_iso


def save_konto_jupiter(all_rows: list[tuple], db_path: str, bank: str, kost: str) -> None:
    db_path = os.path.normpath(db_path)
    db_dir = os.path.dirname(db_path)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            f"""CREATE TABLE IF NOT EXISTS {SQLITE_TABLE_KONTO} (
                umsatz_euro REAL,
                bu_gkto TEXT,
                beleg_1 TEXT,
                datum TEXT,
                bank TEXT,
                kost_1 TEXT,
                buchungstext TEXT
            )"""
        )
        conn.execute(f"DELETE FROM {SQLITE_TABLE_KONTO}")
        rows = [
            (betrag, bu or "", "01", datum_iso(datum), bank, kost, text or "")
            for betrag, bu, datum, text in all_rows
        ]
        conn.executemany(
            f"""INSERT INTO {SQLITE_TABLE_KONTO}
               (umsatz_euro, bu_gkto, beleg_1, datum, bank, kost_1, buchungstext)
               VALUES (?,?,?,?,?,?,?)""",
            rows,
        )
        conn.commit()
    finally:
        conn.close()
    print(f"   SQLite: {len(all_rows)} Zeilen -> {os.path.basename(db_path)}")
