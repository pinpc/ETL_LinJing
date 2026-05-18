"""Bank service placeholders."""

from __future__ import annotations

import csv
from pathlib import Path

from ..parser.registry import CsvParser, ParserRegistry
from ..rule_engine.registry import IdentityRule, RulePipeline, RuleSetRegistry
from ..shared.models import ParseRequest, RuleContext
from .interfaces import BankRunRequest, IBankService


class BankService(IBankService):
    """Minimal bank orchestration for parser -> rules -> output."""

    def __init__(self) -> None:
        parser_registry = ParserRegistry()
        parser_registry.register("csv", CsvParser())
        self._parser_registry = parser_registry

        rule_registry = RuleSetRegistry()
        rule_registry.register("*", "bank", [IdentityRule()])
        self._rule_pipeline = RulePipeline(rule_registry)

    def run(self, request: BankRunRequest):
        parse_request = ParseRequest(
            tenant_id=request.tenant_id,
            source_type="csv",
            source_path=_resolve_source_file(request.source_dir),
        )
        parsed_rows = self._parser_registry.parse(parse_request)
        context = RuleContext(tenant_id=request.tenant_id, module_name="bank")
        processed_rows = self._rule_pipeline.run(parsed_rows, context)
        _write_output_csv(request.output_path, processed_rows)
        return processed_rows


def _resolve_source_file(source_dir: Path) -> Path:
    if source_dir.is_file():
        return source_dir

    csv_files = sorted(source_dir.glob("*.csv"))
    if not csv_files:
        raise FileNotFoundError(f"No CSV input file found in: {source_dir}")
    return csv_files[0]


def _write_output_csv(output_path: Path, rows) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=[
                "tenant_id",
                "module_name",
                "amount",
                "booking_date",
                "booking_text",
                "bu_gkto",
                "beleg_1",
            ],
        )
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "tenant_id": row.tenant_id,
                    "module_name": row.module_name,
                    "amount": row.amount,
                    "booking_date": row.booking_date,
                    "booking_text": row.booking_text,
                    "bu_gkto": row.bu_gkto,
                    "beleg_1": row.beleg_1,
                }
            )

