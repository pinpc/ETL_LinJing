"""Debugger-friendly runner for tenant cashbook ETL."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def _bootstrap_import_path() -> None:
    """Ensure parent folder of the Restaurant package is importable."""
    package_root = Path(__file__).resolve().parents[2]
    parent = package_root.parent
    if str(parent) not in sys.path:
        sys.path.insert(0, str(parent))


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run tenant cashbook ETL via Restaurant CashbookService.")
    parser.add_argument("--tenant-id", required=True, choices=["asia", "jupiter"], help="Tenant identifier.")
    parser.add_argument("--input", required=True, help="Input cashbook file path.")
    parser.add_argument("--output", required=True, help="Output Excel path.")
    parser.add_argument("--pdf-base-dir", help="Optional base directory for Allopay PDF discovery.")
    parser.add_argument("--sheet-name", help="Optional sheet name override.")
    parser.add_argument("--sqlite-output", help="Optional SQLite output path.")
    return parser


def main(argv: list[str] | None = None) -> None:
    _bootstrap_import_path()
    args = _build_parser().parse_args(argv)

    from Restaurant.etl_platform.cashbook.interfaces import CashbookRunRequest
    from Restaurant.etl_platform.cashbook.service import CashbookService

    request = CashbookRunRequest(
        tenant_id=args.tenant_id,
        input_path=Path(args.input),
        output_path=Path(args.output),
        pdf_base_dir=Path(args.pdf_base_dir) if args.pdf_base_dir else None,
        sheet_name=args.sheet_name,
        sqlite_output_path=Path(args.sqlite_output) if args.sqlite_output else None,
    )

    rows = CashbookService().run(request)
    sqlite_out = request.sqlite_output_path or request.output_path.with_suffix(".sqlite")
    print(
        f"Cashbook ETL finished for tenant '{args.tenant_id}' -> {args.output} "
        f"({len(rows)} rows, sqlite: {sqlite_out})."
    )


if __name__ == "__main__":
    main()
