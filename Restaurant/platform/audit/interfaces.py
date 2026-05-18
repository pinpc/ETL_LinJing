"""Audit module interfaces."""

from __future__ import annotations

from typing import Protocol

from ..shared.models import AuditEvent


class IAuditStore(Protocol):
    """Contract for persisting audit events."""

    def record(self, event: AuditEvent) -> None:
        """Persist a single audit event."""

    def list_by_run(self, run_id: str) -> list[AuditEvent]:
        """List events for one ETL run."""

