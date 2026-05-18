"""Rule registry placeholders."""

from __future__ import annotations

from dataclasses import dataclass

from ..shared.models import ParsedTransaction, ProcessedTransaction
from .interfaces import IRule, IRulePipeline, RuleContext


class RuleSetRegistry:
    """Registry for module-level rule sets (no tenant overrides yet)."""

    _DEFAULT_SCOPE = "__default__"

    def __init__(self) -> None:
        self._rule_sets: dict[tuple[str, str], list[IRule]] = {}

    def register(self, tenant_id: str, module_name: str, rules: list[IRule]) -> None:
        scope = self._DEFAULT_SCOPE if tenant_id == "*" else tenant_id
        self._rule_sets[(scope, module_name)] = rules

    def resolve(self, tenant_id: str, module_name: str) -> list[IRule]:
        # Phase 3: no tenant overrides, only default/module rules.
        return self._rule_sets.get((self._DEFAULT_SCOPE, module_name), [])


class RulePipeline(IRulePipeline):
    """Apply rules to parsed rows and map to output transaction shape."""

    def __init__(self, rule_registry: RuleSetRegistry) -> None:
        self._rule_registry = rule_registry

    def run(
        self,
        rows: list[ParsedTransaction],
        context: RuleContext,
    ) -> list[ProcessedTransaction]:
        rules = self._rule_registry.resolve(context.tenant_id, context.module_name)
        processed: list[ProcessedTransaction] = []
        for row in rows:
            current = row
            for rule in rules:
                current = rule.apply(current, context)
            processed.append(
                ProcessedTransaction(
                    tenant_id=current.tenant_id,
                    module_name=context.module_name,
                    amount=current.amount,
                    booking_date=current.booking_date,
                    booking_text=current.text,
                    metadata=current.metadata,
                )
            )
        return processed


@dataclass(slots=True)
class IdentityRule(IRule):
    """No-op rule for minimal pipeline execution."""

    rule_id: str = "identity"

    def apply(self, tx: ParsedTransaction, context: RuleContext) -> ParsedTransaction:
        return tx

