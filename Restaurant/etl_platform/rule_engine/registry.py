"""Rule registry placeholders."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Any

from ..shared.errors import ConfigurationError, ValidationError
from ..shared.models import ParsedTransaction, ProcessedTransaction
from .interfaces import IRule, IRulePipeline, RuleContext, RulePipelineResult, RuleTraceEntry


class RuleSetRegistry:
    """Registry for module-level rules with tenant YAML loading."""

    _DEFAULT_SCOPE = "__default__"

    def __init__(self, tenants_root: Path | None = None) -> None:
        self._rule_sets: dict[tuple[str, str], list[IRule]] = {}
        self._loaded_yaml_scopes: set[tuple[str, str]] = set()
        self._tenants_root = tenants_root or Path(__file__).resolve().parents[2] / "tenants"

    def register(self, tenant_id: str, module_name: str, rules: list[IRule]) -> None:
        scope = self._DEFAULT_SCOPE if tenant_id == "*" else tenant_id
        self._rule_sets[(scope, module_name)] = rules

    def resolve(self, tenant_id: str, module_name: str) -> list[IRule]:
        # Tenant-specific rules first.
        tenant_scope = (tenant_id, module_name)
        if tenant_scope not in self._rule_sets:
            self._load_tenant_yaml_rules(tenant_id, module_name)
        if tenant_scope in self._rule_sets:
            return self._rule_sets[tenant_scope]

        # Fallback to default module rules.
        return self._rule_sets.get((self._DEFAULT_SCOPE, module_name), [])

    def _load_tenant_yaml_rules(self, tenant_id: str, module_name: str) -> None:
        scope = (tenant_id, module_name)
        if scope in self._loaded_yaml_scopes:
            return
        self._loaded_yaml_scopes.add(scope)

        yaml_path = self._tenants_root / tenant_id / f"rules_{module_name}.yaml"
        yml_path = self._tenants_root / tenant_id / f"rules_{module_name}.yml"
        path = yaml_path if yaml_path.exists() else yml_path
        if not path.exists():
            return

        payload = _read_yaml(path)
        if not payload:
            # Explicitly cache as empty to avoid repeated file reads.
            self._rule_sets[scope] = []
            return
        rules = [_parse_rule_entry(entry, module_name) for entry in payload]
        self._rule_sets[scope] = rules


class RulePipeline(IRulePipeline):
    """Apply rules to parsed rows and map to output transaction shape."""

    def __init__(self, rule_registry: RuleSetRegistry) -> None:
        self._rule_registry = rule_registry

    def run(
        self,
        rows: list[ParsedTransaction],
        context: RuleContext,
    ) -> list[ProcessedTransaction]:
        return self.run_with_trace(rows, context).rows

    def run_with_trace(
        self,
        rows: list[ParsedTransaction],
        context: RuleContext,
    ) -> RulePipelineResult:
        rules = self._rule_registry.resolve(context.tenant_id, context.module_name)
        processed: list[ProcessedTransaction] = []
        trace: list[RuleTraceEntry] = []
        for row in rows:
            current = row
            row_idx = len(processed)
            for rule in rules:
                before = current
                current = rule.apply(current, context)
                trace.append(
                    RuleTraceEntry(
                        row_index=row_idx,
                        rule_id=rule.rule_id,
                        changed=not _parsed_transactions_equal(before, current),
                    )
                )
            metadata = dict(current.metadata)
            processed.append(
                ProcessedTransaction(
                    tenant_id=current.tenant_id,
                    module_name=context.module_name,
                    amount=current.amount,
                    booking_date=current.booking_date,
                    booking_text=str(metadata.get("booking_text") or current.text),
                    bu_gkto=str(metadata.get("bu_gkto") or ""),
                    beleg_1=str(metadata.get("beleg_1") or ""),
                    metadata=metadata,
                )
            )
        return RulePipelineResult(rows=processed, trace=trace)

    @staticmethod
    def summarize_trace(trace: list[RuleTraceEntry]) -> dict[str, dict[str, int]]:
        """Summarize rule trace by rule id with total/applied counters."""
        summary: dict[str, dict[str, int]] = {}
        for entry in trace:
            stats = summary.setdefault(entry.rule_id, {"evaluated": 0, "changed": 0})
            stats["evaluated"] += 1
            if entry.changed:
                stats["changed"] += 1
        return summary


@dataclass(slots=True)
class IdentityRule(IRule):
    """No-op rule for minimal pipeline execution."""

    rule_id: str = "identity"

    def apply(self, tx: ParsedTransaction, context: RuleContext) -> ParsedTransaction:
        return tx


@dataclass(slots=True)
class YamlRule(IRule):
    """Simple configurable rule loaded from tenant YAML files."""

    rule_id: str
    text_contains: str | None = None
    text_regex: str | None = None
    amount_gt: float | None = None
    amount_lt: float | None = None
    set_bu_gkto: str | None = None
    set_beleg_1: str | None = None
    set_booking_text: str | None = None

    def apply(self, tx: ParsedTransaction, context: RuleContext) -> ParsedTransaction:
        if not self._matches(tx):
            return tx
        metadata = dict(tx.metadata)
        if self.set_bu_gkto is not None:
            metadata["bu_gkto"] = self.set_bu_gkto
        if self.set_beleg_1 is not None:
            metadata["beleg_1"] = self.set_beleg_1
        if self.set_booking_text is not None:
            metadata["booking_text"] = self.set_booking_text
        return ParsedTransaction(
            tenant_id=tx.tenant_id,
            source_type=tx.source_type,
            amount=tx.amount,
            booking_date=tx.booking_date,
            text=tx.text,
            reference=tx.reference,
            metadata=metadata,
        )

    def _matches(self, tx: ParsedTransaction) -> bool:
        text = tx.text or ""
        if self.text_contains:
            if self.text_contains.lower() not in text.lower():
                return False
        if self.text_regex:
            if re.search(self.text_regex, text, re.IGNORECASE) is None:
                return False
        if self.amount_gt is not None and not (tx.amount > self.amount_gt):
            return False
        if self.amount_lt is not None and not (tx.amount < self.amount_lt):
            return False
        return True


def _read_yaml(path: Path) -> list[dict[str, Any]]:
    try:
        import yaml
    except ModuleNotFoundError as exc:
        raise ConfigurationError(
            "PyYAML is required for rule loading. Install with 'pip install pyyaml'."
        ) from exc

    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    if loaded is None:
        return []
    if not isinstance(loaded, list):
        raise ValidationError(f"Rules file must be a list in: {path}")
    normalized: list[dict[str, Any]] = []
    for index, item in enumerate(loaded):
        if not isinstance(item, dict):
            raise ValidationError(f"Rule entry at index {index} in {path} must be a mapping.")
        normalized.append(item)
    return normalized


def _parse_rule_entry(entry: dict[str, Any], module_name: str) -> YamlRule:
    rule_id = str(entry.get("id") or f"{module_name}_yaml_rule_{abs(hash(str(entry))) % 100000}")
    when = entry.get("when") or {}
    set_values = entry.get("set") or {}
    if not isinstance(when, dict):
        raise ValidationError(f"Rule '{rule_id}' has invalid 'when' section (must be mapping).")
    if not isinstance(set_values, dict):
        raise ValidationError(f"Rule '{rule_id}' has invalid 'set' section (must be mapping).")

    def _as_float(value: Any) -> float | None:
        if value is None:
            return None
        if isinstance(value, (int, float)):
            return float(value)
        text = str(value).strip()
        if not text:
            return None
        try:
            return float(text)
        except ValueError as exc:
            raise ValidationError(f"Rule '{rule_id}' has invalid numeric value '{value}'.") from exc

    return YamlRule(
        rule_id=rule_id,
        text_contains=str(when.get("text_contains")).strip() if when.get("text_contains") is not None else None,
        text_regex=str(when.get("text_regex")).strip() if when.get("text_regex") is not None else None,
        amount_gt=_as_float(when.get("amount_gt")),
        amount_lt=_as_float(when.get("amount_lt")),
        set_bu_gkto=str(set_values.get("bu_gkto")).strip() if set_values.get("bu_gkto") is not None else None,
        set_beleg_1=str(set_values.get("beleg_1")).strip() if set_values.get("beleg_1") is not None else None,
        set_booking_text=str(set_values.get("booking_text")).strip()
        if set_values.get("booking_text") is not None
        else None,
    )


def _parsed_transactions_equal(left: ParsedTransaction, right: ParsedTransaction) -> bool:
    return (
        left.tenant_id == right.tenant_id
        and left.source_type == right.source_type
        and left.amount == right.amount
        and left.booking_date == right.booking_date
        and left.text == right.text
        and left.reference == right.reference
        and left.metadata == right.metadata
    )

