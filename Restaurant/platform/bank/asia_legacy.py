"""Tenant-specific wrapper around legacy Asia bank ETL."""

from __future__ import annotations

import importlib
import importlib.util
import sys
import sysconfig
from pathlib import Path

from .interfaces import BankRunRequest

_ASIA_BANK_ROOT = Path(__file__).resolve().parent / "asia_bank_etl"
_ASIA_BANK_ROOT = _ASIA_BANK_ROOT.resolve()


def run_asia_bank(request: BankRunRequest) -> None:
    """Execute the legacy Asia bank ETL with request-driven paths."""
    previous_platform = sys.modules.get("platform")
    _ensure_stdlib_platform()
    try:
        runner = _load_module("asia_bank_etl.runner")
        config_mod = _load_module("asia_bank_etl.config")

        config = config_mod.AsiaEtlConfig(  # type: ignore[attr-defined]
            pdf_file=str(_resolve_pdf_path(request)),
            agenda_file=str(request.agenda_file) if request.agenda_file else "",
            output_file=str(request.output_path),
            sql_output_file=str(_resolve_sqlite_path(request)),
        )

        runner.run_etl(config, excel_titel=request.excel_title)  # type: ignore[attr-defined]
    finally:
        _restore_platform_module(previous_platform)


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
    if request.sqlite_output_path:
        return request.sqlite_output_path
    return request.output_path.with_suffix(".sqlite")


def _load_module(module_name: str):
    # Add package parent so `import asia_bank_etl.*` resolves and relative imports work.
    package_parent = _ASIA_BANK_ROOT.parent
    if str(package_parent) not in sys.path:
        sys.path.insert(0, str(package_parent))
    return importlib.import_module(module_name)


def _ensure_stdlib_platform() -> None:
    """Avoid shadowing stdlib `platform` by local `Restaurant/platform` package."""
    stdlib_platform = Path(sysconfig.get_paths()["stdlib"]) / "platform.py"
    spec = importlib.util.spec_from_file_location("platform", stdlib_platform)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load stdlib platform module from {stdlib_platform}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    sys.modules["platform"] = module


def _restore_platform_module(previous_platform_module) -> None:
    if previous_platform_module is not None and hasattr(previous_platform_module, "python_implementation"):
        sys.modules["platform"] = previous_platform_module
