"""Cashbook module interfaces."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from ..shared.models import ProcessedTransaction


@dataclass(slots=True)
class CashbookRunRequest:
    """Input for cashbook use case."""

    tenant_id: str
    input_path: Path
    output_path: Path
    pdf_base_dir: Path | None = None
    sheet_name: str | None = None
    sqlite_output_path: Path | None = None


class ICashbookService(Protocol):
    """Contract for cashbook ETL orchestration."""

    def run(self, request: CashbookRunRequest) -> list[ProcessedTransaction]:
        """Run cashbook ETL flow."""


class ILegacyCashbookRunner(Protocol):
    """Common adapter contract for tenant-specific legacy cashbook runners."""

    def run(
        self,
        request: CashbookRunRequest,
        tenant_pdf_base: Path | None,
        tenant_sheet_name: str | None,
    ) -> list[ProcessedTransaction]:
        """Execute a tenant-specific legacy cashbook ETL pipeline."""


@dataclass(slots=True)
class CashbookPipelineResult:
    """Standardized cashbook pipeline result for GUI/API consumption."""

    tenant_id: str
    module_name: str
    rows: list[ProcessedTransaction]
    output_path: Path
    sqlite_path: Path
    run_meta_path: Path | None = None
    warnings: list[str] = field(default_factory=list)

