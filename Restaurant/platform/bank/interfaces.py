"""Bank module interfaces."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from ..shared.models import ProcessedTransaction


@dataclass(slots=True)
class BankRunRequest:
    """Input for bank use case."""

    tenant_id: str
    source_dir: Path
    output_path: Path
    statement_pdf: Path | None = None
    agenda_file: Path | None = None
    sqlite_output_path: Path | None = None
    excel_title: str | None = None


class IBankService(Protocol):
    """Contract for bank ETL orchestration."""

    def run(self, request: BankRunRequest) -> list[ProcessedTransaction]:
        """Run bank ETL flow."""


class ILegacyBankRunner(Protocol):
    """Common adapter contract for tenant-specific legacy bank runners."""

    def run(self, request: BankRunRequest) -> None:
        """Execute a tenant-specific legacy bank ETL pipeline."""


@dataclass(slots=True)
class BankPipelineResult:
    """Standardized bank pipeline result for GUI/API consumption."""

    tenant_id: str
    module_name: str
    rows: list[ProcessedTransaction]
    output_path: Path
    canonical_json_path: Path
    diagnostics_path: Path | None = None
    warnings: list[str] = field(default_factory=list)

