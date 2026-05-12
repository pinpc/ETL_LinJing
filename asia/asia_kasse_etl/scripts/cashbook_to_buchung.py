from __future__ import annotations

import sys
from pathlib import Path


def _bootstrap_import_path() -> None:
    project_root = Path(__file__).resolve().parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))


def main() -> int:
    _bootstrap_import_path()

    from asia_kasse_etl import AsiaKasseETL

    input_path = Path(
        r"C:\temp_cursor\LinJing\01_Asia\Asia Kasse 03.2026\01 allO现金簿导出2026.03\cashbook_china_restaurant_asia__01_03_2026_31_03_2026.xlsx"
    )
    output_path = Path(
        r"C:\temp_cursor\LinJing\03_Coding\ETL_LinJing\asia\asia_kasse_etl\result\asia_kasse_etl_03_2026.xlsx"
    )

    result = AsiaKasseETL().run(input_path=input_path, output_path=output_path, sheet_name="cashbook")

    print(f"OK: wrote {result.buchung_count} Buchung row(s)")
    print(f"OK: wrote {result.allopay_count} Allopay row(s) from base {result.pdf_base_dir}")
    print(f"OK: wrote {result.final_count} Final row(s)")
    print(f"OK: saved workbook to {result.saved_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

