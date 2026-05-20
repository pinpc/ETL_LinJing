"""Rule engine interfaces."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from ..shared.models import ParsedTransaction, ProcessedTransaction


@dataclass(slots=True)
class RuleContext:
    """Context passed through rule execution."""

    tenant_id: str
    module_name: str
    options: dict[str, Any] = field(default_factory=dict)


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

    def run_with_trace(
        self,
        rows: list[ParsedTransaction],
        context: RuleContext,
    ) -> "RulePipelineResult":
        """Transform rows and return optional rule-application trace."""


@dataclass(slots=True)
class RuleTraceEntry:
    """Trace entry for one rule application attempt."""

    row_index: int
    rule_id: str
    changed: bool


@dataclass(slots=True)
class RulePipelineResult:
    """Rule pipeline result with optional trace details."""

    rows: list[ProcessedTransaction]
    trace: list[RuleTraceEntry] = field(default_factory=list)

