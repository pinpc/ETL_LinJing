"""Zentrale Klasse: Orchestrierung Kontoauszug → Excel/SQLite."""

import os
import re

from . import _logging

_logging.silence_pdfminer()

from .config import BANK, KOST
from .expansion import single_row_from_statement
from .excel_export import build_workbook
from .invoices import load_invoices
from .sqlite_export import save_konto_jupiter
from .statement import extract_statements


class JupiterBankETL:
    """
    FiBu-ETL Jupiter Restaurant.
    Wiederverwendbar: eigene Instanz pro Lauf, konfigurierbare bank/kost.

    Nach run() (bei Erfolg) für Debugging: self.transactions, self.rechnung_map,
    self.stripe_rows, self.all_rows.
    """

    def __init__(self, bank: str | None = None, kost: str | None = None):
        self.bank = bank if bank is not None else BANK
        self.kost = kost if kost is not None else KOST
        self.rechnung_map: dict = {}
        self.stripe_rows: list = []
        self.transactions: list[dict] = []
        self.all_rows: list[tuple] = []

    def extract_statement(self, pdf_path: str) -> list[dict]:
        return extract_statements(pdf_path)

    def load_invoices(self, source_dir: str) -> int:
        return load_invoices(source_dir, self.rechnung_map, self.stripe_rows)

    def build_excel(self, all_rows: list[tuple], output_path: str) -> tuple[int, float]:
        return build_workbook(
            all_rows, output_path, self.bank, self.kost, self.stripe_rows
        )

    def save_sqlite(self, all_rows: list[tuple], db_path: str) -> None:
        save_konto_jupiter(all_rows, db_path, self.bank, self.kost)

    def run(
        self,
        source_dir: str,
        output_path: str,
        kontoauszug_pdf: str | None = None,
        sqlite_path: str | None = None,
    ) -> None:
        source_dir = os.path.normpath(source_dir.strip())
        output_path = os.path.normpath(output_path.strip())
        if kontoauszug_pdf:
            kontoauszug_pdf = os.path.normpath(kontoauszug_pdf.strip())

        if not os.path.exists(source_dir):
            print(f"ERROR: Verzeichnis nicht gefunden: {source_dir}")
            return

        if not kontoauszug_pdf or not os.path.exists(kontoauszug_pdf):
            found = [
                f
                for f in sorted(os.listdir(source_dir))
                if re.match(r"00b", f, re.IGNORECASE) and f.lower().endswith(".pdf")
            ]
            if found:
                kontoauszug_pdf = os.path.join(source_dir, found[0])
                print(f"   Kontoauszug automatisch gefunden: {found[0]}")
            else:
                print("ERROR: Kontoauszug-PDF nicht gefunden. Bitte als 3. Argument angeben.")
                print(f"   Gesucht: 00b*.pdf in {source_dir}")
                return

        print(f"\n{'=' * 60}")
        print(f"Kontoauszug: {os.path.basename(kontoauszug_pdf)}")
        print(f"Rechnungen:  {source_dir}")
        print(f"{'=' * 60}\n")

        self.rechnung_map.clear()
        self.stripe_rows.clear()
        self.transactions.clear()
        self.all_rows.clear()

        self.transactions = self.extract_statement(kontoauszug_pdf)
        print(f"OK: {len(self.transactions)} Buchungen aus Kontoauszug gelesen")

        self.load_invoices(source_dir)

        for tx in self.transactions:
            self.all_rows.extend(single_row_from_statement(tx, self.rechnung_map))

        count, total = self.build_excel(self.all_rows, output_path)

        if sqlite_path:
            self.save_sqlite(self.all_rows, sqlite_path)

        print(f"\n{'=' * 60}")
        print(f"OK: {count} Zeilen -> {os.path.basename(output_path)}")
        print(f"   Kontoauszug-Buchungen: {len(self.transactions)}")
        print(f"   Excel-Zeilen (mit Splits): {count}")
        print(f"   Saldo: {total:,.2f} EUR")

        ohne = [(b, t) for b, bu, d, t in self.all_rows if not bu]
        if ohne:
            print(f"\n   WARN: {len(ohne)} Buchungen ohne BU-Konto (manuell nachbuchen):")
            for b, t in ohne[:10]:
                print(f"     {b:>10.2f}  {t[:50]}")


def run_cli(
    source_dir: str,
    output_path: str,
    kontoauszug_pdf: str | None = None,
    sqlite_path: str | None = None,
    bank: str | None = None,
    kost: str | None = None,
) -> None:
    """Modul-Level Einstieg (ein Lauf, Standard-Instanz)."""
    JupiterBankETL(bank=bank, kost=kost).run(source_dir, output_path, kontoauszug_pdf, sqlite_path)
