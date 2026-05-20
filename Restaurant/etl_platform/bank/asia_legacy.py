"""Tenant-specific wrapper around legacy Asia bank ETL."""

from __future__ import annotations

from pathlib import Path

from .interfaces import BankRunRequest, ILegacyBankRunner
from .legacy_common import (
    ensure_output_exists,
    load_legacy_module,
    resolve_sqlite_output_path,
    stdlib_platform_guard,
)

_ASIA_BANK_ROOT = Path(__file__).resolve().parent / "asia_bank_etl"
_ASIA_BANK_ROOT = _ASIA_BANK_ROOT.resolve()


class AsiaLegacyBankRunner(ILegacyBankRunner):
    """Adapter that executes the legacy Asia bank ETL."""

    def run(self, request: BankRunRequest) -> None:
        """Execute the legacy Asia bank ETL with request-driven paths."""
        with stdlib_platform_guard():
            runner = load_legacy_module(_ASIA_BANK_ROOT, "asia_bank_etl.runner")
            config_mod = load_legacy_module(_ASIA_BANK_ROOT, "asia_bank_etl.config")

            config = config_mod.AsiaEtlConfig(  # type: ignore[attr-defined]
                pdf_file=str(_resolve_pdf_path(request)),
                agenda_file=str(request.agenda_file) if request.agenda_file else "",
                output_file=str(request.output_path),
                sql_output_file=str(_resolve_sqlite_path(request)),
            )

            runner.run_etl(config, excel_titel=request.excel_title)  # type: ignore[attr-defined]
        ensure_output_exists(request.output_path, runner_name="Asia")


def run_asia_bank(request: BankRunRequest) -> None:
    """Backward-compatible function wrapper around `AsiaLegacyBankRunner`."""
    AsiaLegacyBankRunner().run(request)


def _resolve_pdf_path(request: BankRunRequest) -> Path:
    if request.statement_pdf:
        return request.statement_pdf

    if request.source_dir.is_file() and request.source_dir.suffix.lower() == ".pdf":
        return request.source_dir

    pdf_candidates = sorted(request.source_dir.glob("*.pdf"))
    if not pdf_candidates:
        raise FileNotFoundError(
            "Asia bank ETL requires a statement PDF. Pass 'statement_pdf' or provide a source directory containing one."
        )
    return pdf_candidates[0]


def _resolve_sqlite_path(request: BankRunRequest) -> Path:
    return resolve_sqlite_output_path(request.sqlite_output_path, request.output_path)
