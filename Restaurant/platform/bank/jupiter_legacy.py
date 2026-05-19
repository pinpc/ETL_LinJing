"""Tenant-specific wrapper around legacy Jupiter bank ETL."""

from __future__ import annotations

import importlib
import importlib.util
import sys
import sysconfig
from pathlib import Path

from .interfaces import BankRunRequest

_JUPITER_BANK_ROOT = Path(__file__).resolve().parent / "jupiter_bank_etl"
_JUPITER_BANK_ROOT = _JUPITER_BANK_ROOT.resolve()


def run_jupiter_bank(request: BankRunRequest) -> None:
    """Execute the legacy Jupiter bank ETL with request-driven paths."""
    previous_platform = sys.modules.get("platform")
    _ensure_stdlib_platform()
    try:
        core = _load_module("jupiter_bank_etl.core")
        etl = core.JupiterBankETL()  # type: ignore[attr-defined]

        source_dir = _resolve_source_dir(request)
        etl.run(
            source_dir=str(source_dir),
            output_path=str(request.output_path),
            kontoauszug_pdf=str(request.statement_pdf) if request.statement_pdf else None,
            sqlite_path=str(_resolve_sqlite_path(request)),
            agenda_path=str(request.agenda_file) if request.agenda_file else None,
        )
    finally:
        _restore_platform_module(previous_platform)


def _resolve_source_dir(request: BankRunRequest) -> Path:
    if request.source_dir.is_dir():
        return request.source_dir
    if request.source_dir.is_file():
        return request.source_dir.parent
    raise FileNotFoundError(f"Jupiter bank source directory not found: {request.source_dir}")


def _resolve_sqlite_path(request: BankRunRequest) -> Path:
    if request.sqlite_output_path:
        return request.sqlite_output_path
    return request.output_path.with_suffix(".sqlite")


def _load_module(module_name: str):
    # Add package parent so `import jupiter_bank_etl.*` resolves and relative imports work.
    package_parent = _JUPITER_BANK_ROOT.parent
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
