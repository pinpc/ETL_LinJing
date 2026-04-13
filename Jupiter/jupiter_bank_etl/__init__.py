"""
Jupiter Bank FiBu-ETL — Paket für Kontoauszug + Rechnungen → Excel/SQLite.

Verwendung:
    from jupiter_bank_etl import JupiterBankETL
    JupiterBankETL().run(rechnungen_dir, ausgabe.xlsx, kontoauszug.pdf)

oder CLI: ``python run_jupiter_bank.py``
"""

from .core import JupiterBankETL, run_cli

__all__ = ["JupiterBankETL", "run_cli"]
