"""Shared option/value resolution helpers."""

from __future__ import annotations

from typing import TypeVar

_T = TypeVar("_T")


def first_defined(*values: _T | None) -> _T | None:
    """Return the first value that is not None."""
    for value in values:
        if value is not None:
            return value
    return None
