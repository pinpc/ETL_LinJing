"""Shared tenant id helpers."""

from __future__ import annotations


def canonical_tenant_id(value: str) -> str:
    """Normalize tenant id to canonical storage/use form."""
    return value.strip().lower()


def require_tenant_id(value: str, *, field_name: str = "tenant_id") -> str:
    """Normalize and validate tenant id presence."""
    normalized = canonical_tenant_id(value)
    if not normalized:
        raise ValueError(f"{field_name} must not be empty.")
    return normalized
