"""Debugger-friendly runner for tenant bank ETL."""

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
    parser = argparse.ArgumentParser(description="Run tenant bank ETL via Restaurant BankService.")
    parser.add_argument("--tenant-id", required=True, choices=["asia", "jupiter"], help="Tenant identifier.")
    parser.add_argument("--source-dir", required=True, help="Input source directory for tenant bank ETL.")
    parser.add_argument("--output", required=True, help="Output Excel path.")
    parser.add_argument("--statement-pdf", help="Optional explicit statement PDF path.")
    parser.add_argument("--agenda-file", help="Optional agenda file path.")
    parser.add_argument("--sqlite-output", help="Optional SQLite output path.")
    parser.add_argument("--excel-title", help="Optional Excel title (Asia).")
    return parser


def main(argv: list[str] | None = None) -> None:
    _bootstrap_import_path()
    args = _build_parser().parse_args(argv)

    from Restaurant.platform.bank.interfaces import BankRunRequest
    from Restaurant.platform.bank.service import BankService

    request = BankRunRequest(
        tenant_id=args.tenant_id,
        source_dir=Path(args.source_dir),
        output_path=Path(args.output),
        statement_pdf=Path(args.statement_pdf) if args.statement_pdf else None,
        agenda_file=Path(args.agenda_file) if args.agenda_file else None,
        sqlite_output_path=Path(args.sqlite_output) if args.sqlite_output else None,
        excel_title=args.excel_title,
    )

    BankService().run(request)
    print(f"Bank ETL finished for tenant '{args.tenant_id}' -> {args.output}")


if __name__ == "__main__":
    main()
