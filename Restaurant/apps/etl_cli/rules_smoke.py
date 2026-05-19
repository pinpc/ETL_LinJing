"""Quick smoke checks for tenant YAML rule activation."""

from __future__ import annotations

import sys
from pathlib import Path


def _bootstrap_import_path() -> None:
    package_root = Path(__file__).resolve().parents[2]
    parent = package_root.parent
    if str(parent) not in sys.path:
        sys.path.insert(0, str(parent))


def main() -> int:
    _bootstrap_import_path()
    from Restaurant.platform.rule_engine.registry import RulePipeline, RuleSetRegistry
    from Restaurant.platform.shared.models import ParsedTransaction, RuleContext

    registry = RuleSetRegistry()
    pipeline = RulePipeline(registry)

    checks: list[tuple[str, str, ParsedTransaction, str]] = [
        (
            "asia",
            "bank",
            ParsedTransaction(
                tenant_id="asia",
                source_type="csv",
                amount=25.0,
                booking_date="2026-03-10",
                text="allO daily payout",
            ),
            "1360",
        ),
        (
            "jupiter",
            "bank",
            ParsedTransaction(
                tenant_id="jupiter",
                source_type="csv",
                amount=-12.0,
                booking_date="2026-03-10",
                text="bank fee",
            ),
            "4970",
        ),
        (
            "asia",
            "cashbook",
            ParsedTransaction(
                tenant_id="asia",
                source_type="csv",
                amount=100.0,
                booking_date="2026-03-10",
                text="cash income",
            ),
            "8000",
        ),
        (
            "jupiter",
            "cashbook",
            ParsedTransaction(
                tenant_id="jupiter",
                source_type="csv",
                amount=-5.0,
                booking_date="2026-03-10",
                text="cash out",
            ),
            "1360",
        ),
    ]

    failures: list[str] = []
    for tenant_id, module_name, tx, expected_bu in checks:
        out = pipeline.run([tx], RuleContext(tenant_id=tenant_id, module_name=module_name))
        actual = out[0].bu_gkto
        if actual != expected_bu:
            failures.append(
                f"{tenant_id}/{module_name}: expected bu_gkto={expected_bu}, got {actual!r}"
            )

    if failures:
        print("RULE SMOKE FAILED")
        for item in failures:
            print(f" - {item}")
        return 1

    print("RULE SMOKE OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
