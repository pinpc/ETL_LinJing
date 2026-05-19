"""Standardized bank error model for GUI/API surfaces."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class BankErrorCode(StrEnum):
    """Stable error codes for bank ETL failures."""

    INPUT_MISSING = "INPUT_MISSING"
    PARSER_FAILED = "PARSER_FAILED"
    LEGACY_RUN_FAILED = "LEGACY_RUN_FAILED"
    OUTPUT_NOT_CREATED = "OUTPUT_NOT_CREATED"
    TENANT_UNSUPPORTED = "TENANT_UNSUPPORTED"
    UNKNOWN = "UNKNOWN"


@dataclass(slots=True)
class BankServiceError(RuntimeError):
    """Typed service error with stable code for downstream handling."""

    code: BankErrorCode
    message: str

    def __str__(self) -> str:
        return f"[{self.code}] {self.message}"
