"""Audit service placeholders."""

from __future__ import annotations

from .interfaces import IAuditStore
from ..shared.models import AuditEvent


class InMemoryAuditStore(IAuditStore):
    """Placeholder audit store implementation."""

    def record(self, event: AuditEvent) -> None:
        raise NotImplementedError("Phase 1 skeleton only.")

    def list_by_run(self, run_id: str):
        raise NotImplementedError("Phase 1 skeleton only.")

