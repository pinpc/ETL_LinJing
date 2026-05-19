"""CI smoke runner for ETL services without local tenant files."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from tempfile import TemporaryDirectory


def _bootstrap_import_path() -> None:
    package_root = Path(__file__).resolve().parents[2]
    parent = package_root.parent
    if str(parent) not in sys.path:
        sys.path.insert(0, str(parent))


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run CI-friendly smoke checks for bank and cashbook services.")
    parser.add_argument("--module", choices=["bank", "cashbook"], required=True, help="Service module to smoke-test.")
    return parser


def _run_bank_smoke() -> None:
    from Restaurant.etl_platform.bank.interfaces import BankRunRequest
    from Restaurant.etl_platform.bank.service import BankService
    from Restaurant.etl_platform.shared.models import ProcessedTransaction
    from Restaurant.etl_platform.tenant.models import TenantContext

    class _StubTenantResolver:
        def resolve(self, tenant_id: str) -> TenantContext:
            return TenantContext(
                tenant_id=tenant_id,
                display_name=f"Tenant {tenant_id}",
                config_dir=Path("."),
                options={},
            )

    class _StubBankRunner:
        def run(self, request: BankRunRequest) -> None:
            request.output_path.parent.mkdir(parents=True, exist_ok=True)
            request.output_path.write_text("stub workbook", encoding="utf-8")

    with TemporaryDirectory() as tmp:
        base = Path(tmp)
        source_dir = base / "source"
        source_dir.mkdir(parents=True, exist_ok=True)
        output_path = base / "bank_ci_smoke.xlsx"

        service = BankService(tenant_resolver=_StubTenantResolver())
        service.register_legacy_runner("ci", _StubBankRunner())

        original_loader = getattr(sys.modules[BankService.__module__], "_load_processed_from_bank_workbook")
        original_json_writer = getattr(sys.modules[BankService.__module__], "_write_bank_canonical_json")
        try:
            def _fake_loader(_output_path: Path, tenant_id: str) -> list[ProcessedTransaction]:
                return [
                    ProcessedTransaction(
                        tenant_id=tenant_id,
                        module_name="bank",
                        amount=12.34,
                        booking_date="2026-01-01",
                        booking_text="ci smoke bank",
                        bu_gkto="1000",
                        beleg_1="CI",
                    )
                ]

            def _fake_json_writer(path: Path, rows: list[ProcessedTransaction]) -> None:
                path.with_suffix(".processed.json").write_text("[]", encoding="utf-8")

            setattr(sys.modules[BankService.__module__], "_load_processed_from_bank_workbook", _fake_loader)
            setattr(sys.modules[BankService.__module__], "_write_bank_canonical_json", _fake_json_writer)

            result = service.run_with_result(
                BankRunRequest(
                    tenant_id="ci",
                    source_dir=source_dir,
                    output_path=output_path,
                )
            )
        finally:
            setattr(sys.modules[BankService.__module__], "_load_processed_from_bank_workbook", original_loader)
            setattr(sys.modules[BankService.__module__], "_write_bank_canonical_json", original_json_writer)

        if len(result.rows) != 1:
            raise RuntimeError(f"Bank CI smoke expected 1 row, got {len(result.rows)}")
        if not result.output_path.exists():
            raise RuntimeError("Bank CI smoke output workbook was not created.")
        if result.run_meta_path is None or not result.run_meta_path.exists():
            raise RuntimeError("Bank CI smoke run_meta artifact is missing.")
        print("bank_ci_smoke_ok")


def _run_cashbook_smoke() -> None:
    from Restaurant.etl_platform.cashbook.interfaces import CashbookRunRequest
    from Restaurant.etl_platform.cashbook.service import CashbookService
    from Restaurant.etl_platform.shared.models import ProcessedTransaction
    from Restaurant.etl_platform.tenant.models import TenantContext

    class _StubTenantResolver:
        def resolve(self, tenant_id: str) -> TenantContext:
            return TenantContext(
                tenant_id=tenant_id,
                display_name=f"Tenant {tenant_id}",
                config_dir=Path("."),
                options={},
            )

    class _StubCashbookRunner:
        def run(self, request: CashbookRunRequest, tenant_pdf_base: Path | None, tenant_sheet_name: str | None):
            _ = tenant_pdf_base
            _ = tenant_sheet_name
            request.output_path.parent.mkdir(parents=True, exist_ok=True)
            request.output_path.write_text("stub workbook", encoding="utf-8")
            return [
                ProcessedTransaction(
                    tenant_id=request.tenant_id,
                    module_name="cashbook",
                    amount=45.67,
                    booking_date="2026-01-02",
                    booking_text="ci smoke cashbook",
                    bu_gkto="2000",
                    beleg_1="CI",
                )
            ]

    with TemporaryDirectory() as tmp:
        base = Path(tmp)
        input_path = base / "cashbook_source.xlsx"
        input_path.write_text("stub input", encoding="utf-8")
        output_path = base / "cashbook_ci_smoke.xlsx"

        service = CashbookService(tenant_resolver=_StubTenantResolver())
        service.register_legacy_runner("ci", _StubCashbookRunner())
        result = service.run_with_result(
            CashbookRunRequest(
                tenant_id="ci",
                input_path=input_path,
                output_path=output_path,
            )
        )

        if len(result.rows) != 1:
            raise RuntimeError(f"Cashbook CI smoke expected 1 row, got {len(result.rows)}")
        if not result.output_path.exists():
            raise RuntimeError("Cashbook CI smoke output workbook was not created.")
        if result.run_meta_path is None or not result.run_meta_path.exists():
            raise RuntimeError("Cashbook CI smoke run_meta artifact is missing.")
        print("cashbook_ci_smoke_ok")


def main(argv: list[str] | None = None) -> None:
    _bootstrap_import_path()
    args = _build_parser().parse_args(argv)
    if args.module == "bank":
        _run_bank_smoke()
        return
    _run_cashbook_smoke()


if __name__ == "__main__":
    main()
