"""Parser module interfaces."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from ..shared.models import ParsedTransaction


@dataclass(slots=True)
class ParseRequest:
    """Input request for parser components."""

    tenant_id: str
    source_type: str
    source_path: Path


class IParser(Protocol):
    """Contract for all parser adapters."""

    def parse(self, request: ParseRequest) -> list[ParsedTransaction]:
        """Parse source input into canonical transactions."""

