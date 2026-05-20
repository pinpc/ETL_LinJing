"""Tenant-specific wrapper around legacy Jupiter bank ETL."""

from __future__ import annotations

from pathlib import Path

from .interfaces import BankRunRequest, ILegacyBankRunner
from .legacy_common import (
    ensure_output_exists,
    load_legacy_module,
    resolve_sqlite_output_path,
    stdlib_platform_guard,
)

_JUPITER_BANK_ROOT = Path(__file__).resolve().parent / "jupiter_bank_etl"
_JUPITER_BANK_ROOT = _JUPITER_BANK_ROOT.resolve()


class JupiterLegacyBankRunner(ILegacyBankRunner):
    """Adapter that executes the legacy Jupiter bank ETL."""

    def run(self, request: BankRunRequest) -> None:
        """Execute the legacy Jupiter bank ETL with request-driven paths."""
        source_dir = _resolve_source_dir(request)
        try:
            with stdlib_platform_guard():
                core = load_legacy_module(_JUPITER_BANK_ROOT, "jupiter_bank_etl.core")
                etl = core.JupiterBankETL()  # type: ignore[attr-defined]
                etl.run(
                    source_dir=str(source_dir),
                    output_path=str(request.output_path),
                    kontoauszug_pdf=str(request.statement_pdf) if request.statement_pdf else None,
                    sqlite_path=str(_resolve_sqlite_path(request)),
                    agenda_path=str(request.agenda_file) if request.agenda_file else None,
                )
        except SystemExit as exc:
            raise RuntimeError(
                f"Jupiter legacy bank ETL exited unexpectedly with code {exc.code!r}."
            ) from exc
        ensure_output_exists(request.output_path, runner_name="Jupiter")


def run_jupiter_bank(request: BankRunRequest) -> None:
    """Backward-compatible function wrapper around `JupiterLegacyBankRunner`."""
    JupiterLegacyBankRunner().run(request)


def _resolve_source_dir(request: BankRunRequest) -> Path:
    if request.source_dir.is_dir():
        return request.source_dir
    if request.source_dir.is_file():
        return request.source_dir.parent
    raise FileNotFoundError(f"Jupiter bank source directory not found: {request.source_dir}")


def _resolve_sqlite_path(request: BankRunRequest) -> Path:
    return resolve_sqlite_output_path(request.sqlite_output_path, request.output_path)
