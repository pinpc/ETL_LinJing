"""Shared core contracts and data models."""

from .interfaces import (
    IAuditStore,
    IBankService,
    ICashbookService,
    IParser,
    IRule,
    IRulePipeline,
    ITenantResolver,
)
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

__all__ = [
    "AuditEvent",
    "BankRunRequest",
    "CashbookRunRequest",
    "IAuditStore",
    "IBankService",
    "ICashbookService",
    "IParser",
    "IRule",
    "IRulePipeline",
    "ITenantResolver",
    "ParseRequest",
    "ParsedTransaction",
    "ProcessedTransaction",
    "RuleContext",
    "TenantContext",
]

