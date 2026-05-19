"""Shared core contracts for ETL platform modules."""

from __future__ import annotations

from typing import Protocol

from .models import (
    AuditEvent,
    BankRunRequest,
    CashbookRunRequest,
    ParseRequest,
    ParsedTransaction,
    ProcessedTransaction,
    RuleContext,
    TenantContext,
)


class IParser(Protocol):
    """Contract for all parser adapters."""

    def parse(self, request: ParseRequest) -> list[ParsedTransaction]:
        """Parse source input into canonical transactions."""


class IRule(Protocol):
    """Contract for a single rule."""

    rule_id: str

    def apply(self, tx: ParsedTransaction, context: RuleContext) -> ParsedTransaction:
        """Apply rule to one transaction."""


class IRulePipeline(Protocol):
    """Contract for applying multiple rules in sequence."""

    def run(
        self,
        rows: list[ParsedTransaction],
        context: RuleContext,
    ) -> list[ProcessedTransaction]:
        """Transform parsed rows into processed rows."""


class ITenantResolver(Protocol):
    """Contract for tenant resolution."""

    def resolve(self, tenant_id: str) -> TenantContext:
        """Resolve tenant context by identifier."""


class IBankService(Protocol):
    """Contract for bank ETL orchestration."""

    def run(self, request: BankRunRequest) -> list[ProcessedTransaction]:
        """Run bank ETL flow."""


class ICashbookService(Protocol):
    """Contract for cashbook ETL orchestration."""

    def run(self, request: CashbookRunRequest) -> list[ProcessedTransaction]:
        """Run cashbook ETL flow."""


class IAuditStore(Protocol):
    """Contract for persisting audit events."""

    def record(self, event: AuditEvent) -> None:
        """Persist a single audit event."""

    def list_by_run(self, run_id: str) -> list[AuditEvent]:
        """List events for one ETL run."""
