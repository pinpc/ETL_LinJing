"""Rule engine interfaces."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from ..shared.models import ParsedTransaction, ProcessedTransaction, RuleContext


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
class RuleExplainStats:
    """Aggregated rule evaluation counters for one rule id."""

    evaluated: int = 0
    changed: int = 0

    def to_dict(self) -> dict[str, int]:
        """Serialize explain stats into a stable JSON-friendly shape."""
        return {
            "evaluated": self.evaluated,
            "changed": self.changed,
        }


@dataclass(slots=True)
class RuleExplainSummary:
    """Aggregated explain payload for a complete rule pipeline run."""

    by_rule: dict[str, RuleExplainStats] = field(default_factory=dict)
    total_rows: int = 0
    total_evaluations: int = 0
    total_changes: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Serialize explain summary into a stable JSON-friendly payload."""
        return {
            "by_rule": {
                rule_id: stats.to_dict()
                for rule_id, stats in self.by_rule.items()
            },
            "totals": {
                "rows": self.total_rows,
                "evaluations": self.total_evaluations,
                "changes": self.total_changes,
            },
        }


@dataclass(slots=True)
class RulePipelineResult:
    """Rule pipeline result with optional trace details."""

    rows: list[ProcessedTransaction]
    trace: list[RuleTraceEntry] = field(default_factory=list)
    explain: RuleExplainSummary = field(default_factory=RuleExplainSummary)

