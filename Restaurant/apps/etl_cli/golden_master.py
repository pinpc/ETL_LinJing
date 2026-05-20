"""Golden-master runner for bank/cashbook regression checks."""

from __future__ import annotations

import argparse
import difflib
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


def _bootstrap_import_path() -> None:
    package_root = Path(__file__).resolve().parents[2]
    parent = package_root.parent
    if str(parent) not in sys.path:
        sys.path.insert(0, str(parent))


@dataclass(slots=True)
class GoldenCase:
    case_id: str
    module: str
    tenant_id: str
    source: str
    output: str
    expected: str
    statement_pdf: str | None = None
    agenda_file: str | None = None
    pdf_base_dir: str | None = None
    sheet_name: str | None = None
    sqlite_output: str | None = None
    excel_title: str | None = None
    ignore_fields: list[str] | None = None


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run golden-master checks for ETL outputs.")
    parser.add_argument(
        "--mode",
        choices=["record", "verify"],
        default="verify",
        help="record: write expected snapshots, verify: compare against snapshots.",
    )
    parser.add_argument(
        "--scenarios",
        required=True,
        help="Path to JSON scenarios file (see tenants/golden_master_scenarios.template.json).",
    )
    parser.add_argument(
        "--case",
        dest="case_ids",
        action="append",
        help="Optional case id filter. Can be passed multiple times.",
    )
    return parser


def _load_cases(path: Path) -> list[GoldenCase]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Golden scenarios file must contain a JSON object.")
    raw_cases = payload.get("cases")
    if not isinstance(raw_cases, list):
        raise ValueError("Golden scenarios file must contain a 'cases' list.")

    cases: list[GoldenCase] = []
    for entry in raw_cases:
        if not isinstance(entry, dict):
            raise ValueError("Each golden scenario case must be a JSON object.")
        cases.append(
            GoldenCase(
                case_id=str(entry["id"]),
                module=str(entry["module"]).strip().lower(),
                tenant_id=str(entry["tenant_id"]),
                source=str(entry["source"]),
                output=str(entry["output"]),
                expected=str(entry["expected"]),
                statement_pdf=_optional_text(entry.get("statement_pdf")),
                agenda_file=_optional_text(entry.get("agenda_file")),
                pdf_base_dir=_optional_text(entry.get("pdf_base_dir")),
                sheet_name=_optional_text(entry.get("sheet_name")),
                sqlite_output=_optional_text(entry.get("sqlite_output")),
                excel_title=_optional_text(entry.get("excel_title")),
                ignore_fields=_normalize_optional_field_list(entry.get("ignore_fields")),
            )
        )
    return cases


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


def _normalize_optional_field_list(value: Any) -> list[str] | None:
    if value is None:
        return None
    if not isinstance(value, list):
        raise ValueError("Case field 'ignore_fields' must be a list of strings.")
    normalized: list[str] = []
    for entry in value:
        field = str(entry).strip()
        if field:
            normalized.append(field)
    return normalized or None


def _expand_path(value: str) -> Path:
    package_root = Path(__file__).resolve().parents[2]
    workspace_root = package_root.parent
    expanded = value.replace("${WORKSPACE_ROOT}", str(workspace_root))
    expanded = expanded.replace("${PROJECT_ROOT}", str(package_root))
    return Path(expanded)


def _run_bank_case(case: GoldenCase) -> list[dict[str, Any]]:
    from Restaurant.etl_platform.bank.interfaces import BankRunRequest
    from Restaurant.etl_platform.bank.service import BankService
    from Restaurant.etl_platform.shared.serialization import serialize_processed_transaction

    result = BankService().run_with_result(
        BankRunRequest(
            tenant_id=case.tenant_id,
            source_dir=_expand_path(case.source),
            output_path=_expand_path(case.output),
            statement_pdf=_expand_path(case.statement_pdf) if case.statement_pdf else None,
            agenda_file=_expand_path(case.agenda_file) if case.agenda_file else None,
            sqlite_output_path=_expand_path(case.sqlite_output) if case.sqlite_output else None,
            excel_title=case.excel_title,
        )
    )
    return [serialize_processed_transaction(row) for row in result.rows]


def _run_cashbook_case(case: GoldenCase) -> list[dict[str, Any]]:
    from Restaurant.etl_platform.cashbook.interfaces import CashbookRunRequest
    from Restaurant.etl_platform.cashbook.service import CashbookService
    from Restaurant.etl_platform.shared.serialization import serialize_processed_transaction

    result = CashbookService().run_with_result(
        CashbookRunRequest(
            tenant_id=case.tenant_id,
            input_path=_expand_path(case.source),
            output_path=_expand_path(case.output),
            pdf_base_dir=_expand_path(case.pdf_base_dir) if case.pdf_base_dir else None,
            sheet_name=case.sheet_name,
            sqlite_output_path=_expand_path(case.sqlite_output) if case.sqlite_output else None,
        )
    )
    return [serialize_processed_transaction(row) for row in result.rows]


def _run_case(case: GoldenCase) -> list[dict[str, Any]]:
    if case.module == "bank":
        return _run_bank_case(case)
    if case.module == "cashbook":
        return _run_cashbook_case(case)
    raise ValueError(f"Unsupported module '{case.module}' for case '{case.case_id}'.")


def _record_case(case: GoldenCase) -> None:
    from Restaurant.etl_platform.shared.jsonio import write_json_file

    actual = _normalize_rows(_run_case(case), ignore_fields=case.ignore_fields)
    expected_path = _expand_path(case.expected)
    write_json_file(expected_path, actual)
    print(f"[record] {case.case_id}: wrote {expected_path}")


def _verify_case(case: GoldenCase) -> bool:
    actual = _normalize_rows(_run_case(case), ignore_fields=case.ignore_fields)
    expected_path = _expand_path(case.expected)
    if not expected_path.exists():
        print(f"[verify] {case.case_id}: missing expected snapshot: {expected_path}")
        return False
    expected = _normalize_rows(json.loads(expected_path.read_text(encoding="utf-8")), ignore_fields=case.ignore_fields)
    if expected == actual:
        print(f"[verify] {case.case_id}: ok")
        return True

    expected_text = json.dumps(expected, indent=2, ensure_ascii=False, sort_keys=True)
    actual_text = json.dumps(actual, indent=2, ensure_ascii=False, sort_keys=True)
    diff = "\n".join(
        difflib.unified_diff(
            expected_text.splitlines(),
            actual_text.splitlines(),
            fromfile=f"{case.case_id}:expected",
            tofile=f"{case.case_id}:actual",
            lineterm="",
        )
    )
    print(f"[verify] {case.case_id}: mismatch")
    print(diff)
    return False


def _normalize_rows(rows: Any, *, ignore_fields: list[str] | None) -> list[dict[str, Any]]:
    if not isinstance(rows, list):
        raise ValueError("Golden snapshot rows must be a list.")

    normalized_rows: list[dict[str, Any]] = []
    for entry in rows:
        if not isinstance(entry, dict):
            raise ValueError("Golden snapshot entries must be JSON objects.")
        row = dict(entry)
        if ignore_fields:
            for field in ignore_fields:
                row.pop(field, None)
        normalized_rows.append(row)

    return sorted(
        normalized_rows,
        key=lambda row: (
            str(row.get("tenant_id", "")),
            str(row.get("module_name", "")),
            str(row.get("booking_date", "")),
            str(row.get("booking_text", "")),
            str(row.get("bu_gkto", "")),
            str(row.get("beleg_1", "")),
            str(row.get("amount", "")),
        ),
    )


def main(argv: list[str] | None = None) -> None:
    _bootstrap_import_path()
    args = _build_parser().parse_args(argv)
    cases = _load_cases(_expand_path(args.scenarios))
    if args.case_ids:
        allowed = {case_id.strip() for case_id in args.case_ids if case_id.strip()}
        cases = [case for case in cases if case.case_id in allowed]
    if not cases:
        raise SystemExit("No golden-master cases selected.")

    if args.mode == "record":
        print(f"[record] selected_cases={len(cases)}")
        for case in cases:
            _record_case(case)
        return

    print(f"[verify] selected_cases={len(cases)}")
    has_failures = False
    failed_cases: list[str] = []
    for case in cases:
        if not _verify_case(case):
            has_failures = True
            failed_cases.append(case.case_id)
    if failed_cases:
        print(f"[verify] failed_cases={','.join(failed_cases)}")
    else:
        print("[verify] all_cases_ok")
    if has_failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
