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
from .options import first_defined
from .sqlite_store import write_processed_transactions_sqlite
from .serialization import (
    PROCESSED_TRANSACTION_FIELDS,
    legacy_rows_to_processed_transactions,
    serialize_processed_transaction,
)
from .tenancy import (
    canonical_tenant_id,
    list_registered_tenant_ids,
    register_tenant_runner,
    require_tenant_id,
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
    "PROCESSED_TRANSACTION_FIELDS",
    "canonical_tenant_id",
    "first_defined",
    "legacy_rows_to_processed_transactions",
    "list_registered_tenant_ids",
    "register_tenant_runner",
    "require_tenant_id",
    "serialize_processed_transaction",
    "write_processed_transactions_sqlite",
    "write_run_meta",
]

