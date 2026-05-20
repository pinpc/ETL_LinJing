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
from .artifacts import write_run_meta
from .sqlite_store import write_processed_transactions_sqlite
from .serialization import serialize_processed_transaction
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
    "serialize_processed_transaction",
    "write_processed_transactions_sqlite",
    "write_run_meta",
]

