"""Canonical ETL platform namespace (stage 3)."""

from __future__ import annotations

import importlib
import sys

_SUBPACKAGES = ["audit", "auth", "bank", "cashbook", "parser", "rule_engine", "shared", "tenant"]
_ROOT = __name__.rsplit(".", 1)[0]

for _name in _SUBPACKAGES:
    _target = importlib.import_module(f"{_ROOT}.platform.{_name}")
    sys.modules[f"{__name__}.{_name}"] = _target

__all__ = list(_SUBPACKAGES)
