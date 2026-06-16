"""
Asia Kasse ETL - Cashbook + Allopay PDF -> Excel.

Verwendung:
    from asia_kasse_etl import AsiaKasseETL
    AsiaKasseETL().run(input_path, output_path)
"""

from .core import AsiaKasseETL, run_cli

__all__ = ["AsiaKasseETL", "run_cli"]

