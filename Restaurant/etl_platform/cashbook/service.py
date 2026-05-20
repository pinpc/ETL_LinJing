"""Cashbook service placeholders."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from .asia_legacy import AsiaKasseETL
from .errors import CashbookErrorCode, CashbookServiceError
from .interfaces import (
    CashbookPipelineResult,
    CashbookRunRequest,
    ICashbookService,
    ILegacyCashbookRunner,
)
from .jupiter_legacy import JupiterKasseETL
from ..shared.artifacts import write_run_meta
from ..shared.export_pipeline import ProcessedExportTargets, export_processed_rows
from ..shared.options import first_defined
from ..shared.serialization import legacy_rows_to_processed_transactions
from ..shared.tenancy import canonical_tenant_id, list_registered_tenant_ids, register_tenant_runner
from ..tenant.service import TenantResolver, resolve_option_path, resolve_option_str
from ..tenant.models import TenantContext
from ..shared.models import ProcessedTransaction

_DEFAULT_LEGACY_CASHBOOK_RUNNERS: dict[str, ILegacyCashbookRunner] = {}


class CashbookService(ICashbookService):
    """Adapter service wrapping legacy tenant-specific cashbook ETLs."""

    def __init__(self, tenant_resolver: TenantResolver | None = None) -> None:
        self._tenant_resolver = tenant_resolver or TenantResolver()
        self._legacy_cashbook_runners = dict(_DEFAULT_LEGACY_CASHBOOK_RUNNERS)
        if not self._legacy_cashbook_runners:
            self.register_legacy_runner("asia", _AsiaLegacyCashbookRunner())
            self.register_legacy_runner("jupiter", _JupiterLegacyCashbookRunner())

    def run(self, request: CashbookRunRequest) -> list[ProcessedTransaction]:
        return self.run_with_result(request).rows

    def run_with_result(self, request: CashbookRunRequest) -> CashbookPipelineResult:
        tenant_id = canonical_tenant_id(request.tenant_id)
        try:
            tenant_context = self._tenant_resolver.resolve(tenant_id)
            runner_tenant_id = _resolve_runner_tenant_id(tenant_context, tenant_id)
            tenant_pdf_base = resolve_option_path(tenant_context, "cashbook_pdf_base_dir")
            tenant_sheet_name = resolve_option_str(tenant_context.options, "cashbook_sheet_name")
            tenant_sqlite_output = resolve_option_path(tenant_context, "cashbook_sqlite_output_path")
            sqlite_path = _resolve_sqlite_output_path(
                request,
                tenant_sqlite_output,
                request.output_path.with_suffix(".sqlite"),
            )

            runner = self._legacy_cashbook_runners.get(runner_tenant_id)
            if runner is None:
                raise CashbookServiceError(
                    CashbookErrorCode.TENANT_UNSUPPORTED,
                    f"Unsupported cashbook tenant '{request.tenant_id}'.",
                )

            processed = runner.run(request, tenant_pdf_base, tenant_sheet_name)
            _write_sqlite(sqlite_path, processed)
            run_meta_path = _write_cashbook_run_meta(tenant_id, request.output_path, sqlite_path, len(processed))
            return CashbookPipelineResult(
                tenant_id=tenant_id,
                module_name="cashbook",
                rows=processed,
                output_path=request.output_path,
                sqlite_path=sqlite_path,
                run_meta_path=run_meta_path,
            )
        except CashbookServiceError:
            raise
        except FileNotFoundError as exc:
            raise CashbookServiceError(CashbookErrorCode.INPUT_MISSING, str(exc)) from exc
        except ValueError as exc:
            raise CashbookServiceError(CashbookErrorCode.PARSER_FAILED, str(exc)) from exc
        except RuntimeError as exc:
            message = str(exc)
            if "without producing output workbook" in message:
                raise CashbookServiceError(CashbookErrorCode.OUTPUT_NOT_CREATED, message) from exc
            raise CashbookServiceError(CashbookErrorCode.LEGACY_RUN_FAILED, message) from exc
        except Exception as exc:
            raise CashbookServiceError(CashbookErrorCode.UNKNOWN, str(exc)) from exc

    def register_legacy_runner(self, tenant_id: str, runner: ILegacyCashbookRunner) -> None:
        """Register or override a tenant-specific legacy cashbook runner."""
        register_tenant_runner(
            self._legacy_cashbook_runners,
            tenant_id=tenant_id,
            runner=runner,
            field_name="tenant_id",
        )

    def list_registered_tenants(self) -> list[str]:
        """Return currently registered tenant ids for cashbook legacy runners."""
        return list_registered_tenant_ids(self._legacy_cashbook_runners)


class _AsiaLegacyCashbookRunner(ILegacyCashbookRunner):
    """Runner adapter for Asia cashbook legacy implementation."""

    def run(
        self,
        request: CashbookRunRequest,
        tenant_pdf_base: Path | None,
        tenant_sheet_name: str | None,
    ) -> list[ProcessedTransaction]:
        return _run_legacy_cashbook_engine(
            engine=AsiaKasseETL(),
            request=request,
            tenant_pdf_base=tenant_pdf_base,
            tenant_sheet_name=tenant_sheet_name,
            fallback_pdf_base=request.input_path.parents[2] if request.input_path.exists() else Path("."),
            fallback_sheet_name="cashbook",
        )


class _JupiterLegacyCashbookRunner(ILegacyCashbookRunner):
    """Runner adapter for Jupiter cashbook legacy implementation."""

    def run(
        self,
        request: CashbookRunRequest,
        tenant_pdf_base: Path | None,
        tenant_sheet_name: str | None,
    ) -> list[ProcessedTransaction]:
        return _run_legacy_cashbook_engine(
            engine=JupiterKasseETL(),
            request=request,
            tenant_pdf_base=tenant_pdf_base,
            tenant_sheet_name=tenant_sheet_name,
            fallback_pdf_base=request.input_path.parent if request.input_path.exists() else Path("."),
            fallback_sheet_name=None,
        )


def _run_legacy_cashbook_engine(
    *,
    engine,
    request: CashbookRunRequest,
    tenant_pdf_base: Path | None,
    tenant_sheet_name: str | None,
    fallback_pdf_base: Path,
    fallback_sheet_name: str | None,
) -> list[ProcessedTransaction]:
    engine.run(
        input_path=request.input_path,
        output_path=request.output_path,
        pdf_base_dir=_resolve_pdf_base_dir(
            request,
            tenant_pdf_base,
            fallback_pdf_base,
        ),
        sheet_name=_resolve_sheet_name(
            request,
            tenant_sheet_name,
            fallback_sheet_name,
        ),
    )
    return _result_to_processed_transactions(
        engine.final_rows,
        canonical_tenant_id(request.tenant_id),
        "cashbook",
    )


def _result_to_processed_transactions(rows: list, tenant_id: str, module_name: str) -> list[ProcessedTransaction]:
    return legacy_rows_to_processed_transactions(
        rows,
        tenant_id=tenant_id,
        module_name=module_name,
    )


def _resolve_pdf_base_dir(
    request: CashbookRunRequest,
    tenant_value: Path | None,
    fallback: Path,
) -> Path:
    return first_defined(request.pdf_base_dir, tenant_value, fallback)


def _resolve_runner_tenant_id(tenant_context: TenantContext, fallback_tenant_id: str) -> str:
    configured = resolve_option_str(tenant_context.options, "cashbook_runner_tenant_id")
    if configured:
        return canonical_tenant_id(configured)
    return fallback_tenant_id


def _resolve_sheet_name(
    request: CashbookRunRequest,
    tenant_value: str | None,
    fallback: str | None,
) -> str | None:
    return first_defined(request.sheet_name, tenant_value, fallback)


def _resolve_sqlite_output_path(
    request: CashbookRunRequest,
    tenant_value: Path | None,
    fallback: Path,
) -> Path:
    return first_defined(request.sqlite_output_path, tenant_value, fallback)


def _write_sqlite(sqlite_path: Path, rows: list[ProcessedTransaction]) -> None:
    export_processed_rows(
        rows,
        ProcessedExportTargets(
            sqlite_output_path=sqlite_path,
            sqlite_table_name="cashbook_transactions",
        ),
    )


def _write_cashbook_run_meta(
    tenant_id: str,
    output_path: Path,
    sqlite_path: Path,
    row_count: int,
) -> Path:
    return write_run_meta(
        tenant_id=tenant_id,
        module_name="cashbook",
        output_path=output_path,
        row_count=row_count,
        artifacts={
            "workbook": output_path,
            "sqlite": sqlite_path,
        },
    )

