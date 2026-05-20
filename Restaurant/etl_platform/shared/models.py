"""Shared data models for ETL platform."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from ..tenant.models import TenantContext

@dataclass(slots=True)
class ParsedTransaction:
    """Canonical transaction format after parsing."""

    tenant_id: str
    source_type: str
    amount: float
    booking_date: str
    text: str
    reference: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ProcessedTransaction:
    """Canonical transaction format after rule processing."""

    tenant_id: str
    module_name: str
    amount: float
    booking_date: str
    booking_text: str
    bu_gkto: str = ""
    beleg_1: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class AuditEvent:
    """Single audit trail event."""

    run_id: str
    tenant_id: str
    event_type: str
    message: str
    created_at: datetime
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ParseRequest:
    """Input request for parser components."""

    tenant_id: str
    source_type: str
    source_path: Path


@dataclass(slots=True)
class RuleContext:
    """Context passed through rule execution."""

    tenant_id: str
    module_name: str
    options: dict[str, Any] = field(default_factory=dict)

