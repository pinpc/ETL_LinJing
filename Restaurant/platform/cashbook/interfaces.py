"""Cashbook module interfaces."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from ..shared.models import ProcessedTransaction


@dataclass(slots=True)
class CashbookRunRequest:
    """Input for cashbook use case."""

    tenant_id: str
    input_path: Path
    output_path: Path


class ICashbookService(Protocol):
    """Contract for cashbook ETL orchestration."""

    def run(self, request: CashbookRunRequest) -> list[ProcessedTransaction]:
        """Run cashbook ETL flow."""

