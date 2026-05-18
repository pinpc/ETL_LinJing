"""Bank module interfaces."""

from __future__ import annotations

from dataclasses import dataclass
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


class IBankService(Protocol):
    """Contract for bank ETL orchestration."""

    def run(self, request: BankRunRequest) -> list[ProcessedTransaction]:
        """Run bank ETL flow."""

