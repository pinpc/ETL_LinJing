"""Shared tenant id helpers."""

from __future__ import annotations

from typing import TypeVar

_TRunner = TypeVar("_TRunner")


def canonical_tenant_id(value: str) -> str:
    """Normalize tenant id to canonical storage/use form."""
    return value.strip().lower()


def require_tenant_id(value: str, *, field_name: str = "tenant_id") -> str:
    """Normalize and validate tenant id presence."""
    normalized = canonical_tenant_id(value)
    if not normalized:
        raise ValueError(f"{field_name} must not be empty.")
    return normalized


def register_tenant_runner(
    registry: dict[str, _TRunner],
    *,
    tenant_id: str,
    runner: _TRunner,
    field_name: str = "tenant_id",
) -> None:
    """Normalize tenant id and store/override a runner in a registry."""
    normalized = require_tenant_id(tenant_id, field_name=field_name)
    registry[normalized] = runner


def list_registered_tenant_ids(registry: dict[str, object]) -> list[str]:
    """Return sorted tenant ids for a runner registry."""
    return sorted(registry.keys())
