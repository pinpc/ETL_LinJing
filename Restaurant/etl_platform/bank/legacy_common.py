"""Shared helpers for tenant-specific legacy bank adapters."""

from __future__ import annotations

import importlib
import importlib.util
import sys
import sysconfig
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


def resolve_sqlite_output_path(sqlite_output_path: Path | None, output_path: Path) -> Path:
    """Use request sqlite path if provided, otherwise derive from output path."""
    if sqlite_output_path:
        return sqlite_output_path
    return output_path.with_suffix(".sqlite")


def load_legacy_module(package_root: Path, module_name: str):
    """Load legacy module after adding its package parent to ``sys.path``."""
    package_parent = package_root.parent
    if str(package_parent) not in sys.path:
        sys.path.insert(0, str(package_parent))
    return importlib.import_module(module_name)


@contextmanager
def stdlib_platform_guard() -> Iterator[None]:
    """
    Temporarily enforce stdlib ``platform`` module.

    This avoids shadowing by local ``Restaurant/platform`` package paths.
    """
    previous_platform = sys.modules.get("platform")
    _ensure_stdlib_platform()
    try:
        yield
    finally:
        _restore_platform_module(previous_platform)


def _ensure_stdlib_platform() -> None:
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
