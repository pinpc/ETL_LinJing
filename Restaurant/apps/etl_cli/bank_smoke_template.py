"""Template smoke runner for bank tenant onboarding checks."""

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
    parser = argparse.ArgumentParser(description="Run bank smoke check and print normalized result artifacts.")
    parser.add_argument("--tenant-id", required=True, help="Tenant identifier to run.")
    parser.add_argument("--source-dir", required=True, help="Source directory or input file.")
    parser.add_argument("--output", required=True, help="Target workbook output path.")
    parser.add_argument("--statement-pdf", help="Optional statement PDF path.")
    parser.add_argument("--agenda-file", help="Optional agenda file path.")
    parser.add_argument("--sqlite-output", help="Optional sqlite output path.")
    parser.add_argument("--excel-title", help="Optional Excel title.")
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

    result = BankService().run_with_result(request)
    print(f"tenant={result.tenant_id}")
    print(f"module={result.module_name}")
    print(f"rows={len(result.rows)}")
    print(f"workbook={result.output_path}")
    print(f"canonical_json={result.canonical_json_path}")
    print(f"diagnostics={result.diagnostics_path}")
    if result.warnings:
        print("warnings:")
        for warning in result.warnings:
            print(f" - {warning}")


if __name__ == "__main__":
    main()
