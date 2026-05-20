"""Unified smoke runner for ETL modules."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def _bootstrap_import_path() -> None:
    package_root = Path(__file__).resolve().parents[2]
    parent = package_root.parent
    if str(parent) not in sys.path:
        sys.path.insert(0, str(parent))


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Unified smoke runner for bank/cashbook ETL.")
    parser.add_argument("--module", required=True, choices=["bank", "cashbook"], help="ETL module to run.")
    parser.add_argument("--tenant-id", required=True, help="Tenant identifier.")
    parser.add_argument("--source", required=True, help="Source input (dir or file) path.")
    parser.add_argument("--output", required=True, help="Workbook output path.")
    parser.add_argument("--statement-pdf", help="Bank only: explicit statement PDF path.")
    parser.add_argument("--agenda-file", help="Bank only: optional agenda path.")
    parser.add_argument("--pdf-base-dir", help="Cashbook only: optional PDF base directory.")
    parser.add_argument("--sheet-name", help="Cashbook only: optional sheet name override.")
    parser.add_argument("--sqlite-output", help="Optional sqlite output path.")
    parser.add_argument("--excel-title", help="Bank only: optional excel title.")
    return parser


def _run_bank(args) -> None:
    from Restaurant.etl_platform.bank.interfaces import BankRunRequest
    from Restaurant.etl_platform.bank.service import BankService

    request = BankRunRequest(
        tenant_id=args.tenant_id,
        source_dir=Path(args.source),
        output_path=Path(args.output),
        statement_pdf=Path(args.statement_pdf) if args.statement_pdf else None,
        agenda_file=Path(args.agenda_file) if args.agenda_file else None,
        sqlite_output_path=Path(args.sqlite_output) if args.sqlite_output else None,
        excel_title=args.excel_title,
    )
    result = BankService().run_with_result(request)
    print(f"module={result.module_name}")
    print(f"tenant={result.tenant_id}")
    print(f"rows={len(result.rows)}")
    print(f"workbook={result.output_path}")
    print(f"canonical_json={result.canonical_json_path}")
    print(f"run_meta={result.run_meta_path}")
    print(f"diagnostics={result.diagnostics_path}")
    if result.warnings:
        print("warnings:")
        for warning in result.warnings:
            print(f" - {warning}")


def _run_cashbook(args) -> None:
    from Restaurant.etl_platform.cashbook.interfaces import CashbookRunRequest
    from Restaurant.etl_platform.cashbook.service import CashbookService

    request = CashbookRunRequest(
        tenant_id=args.tenant_id,
        input_path=Path(args.source),
        output_path=Path(args.output),
        pdf_base_dir=Path(args.pdf_base_dir) if args.pdf_base_dir else None,
        sheet_name=args.sheet_name,
        sqlite_output_path=Path(args.sqlite_output) if args.sqlite_output else None,
    )
    result = CashbookService().run_with_result(request)
    print(f"module=cashbook")
    print(f"tenant={result.tenant_id}")
    print(f"rows={len(result.rows)}")
    print(f"workbook={result.output_path}")
    print(f"canonical_json={result.canonical_json_path}")
    print(f"sqlite={result.sqlite_path}")
    print(f"run_meta={result.run_meta_path}")
    if result.warnings:
        print("warnings:")
        for warning in result.warnings:
            print(f" - {warning}")


def main(argv: list[str] | None = None) -> None:
    _bootstrap_import_path()
    args = _build_parser().parse_args(argv)
    if args.module == "bank":
        _run_bank(args)
        return
    _run_cashbook(args)


if __name__ == "__main__":
    main()
