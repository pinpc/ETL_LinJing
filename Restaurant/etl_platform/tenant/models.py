"""Tenant module models."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class TenantContext:
    """Resolved tenant context used across modules."""

    tenant_id: str
    display_name: str
    config_dir: Path
    bank_account: str = ""
    default_kost: str = ""
    options: dict[str, Any] = field(default_factory=dict)

