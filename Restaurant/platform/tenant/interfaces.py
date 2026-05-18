"""Tenant module interfaces."""

from __future__ import annotations

from typing import Protocol

from .models import TenantContext


class ITenantResolver(Protocol):
    """Contract for tenant resolution."""

    def resolve(self, tenant_id: str) -> TenantContext:
        """Resolve tenant context by identifier."""

