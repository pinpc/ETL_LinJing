"""CLI entrypoint for minimal ETL pipeline."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

from ...etl_platform.bank.interfaces import BankRunRequest
from ...etl_platform.bank.service import BankService


def _build_minimal_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run minimal ETL pipeline.")
    parser.add_argument("--tenant-id", required=True, help="Tenant identifier.")
    parser.add_argument(
        "--source",
        required=True,
        help="CSV input path or directory containing one CSV file.",
    )
    parser.add_argument("--output", required=True, help="Output CSV path.")
    return parser


def _run_minimal_pipeline(argv: list[str]) -> int:
    """Run minimal parser -> rule_engine -> output flow."""
    args = _build_minimal_parser().parse_args(argv)

    service = BankService()
    rows = service.run(
        BankRunRequest(
            tenant_id=args.tenant_id,
            source_dir=Path(args.source),
            output_path=Path(args.output),
        )
    )
    print(f"Processed {len(rows)} rows to '{args.output}'.")
    return 0


def _run_tool(command: str, argv: list[str]) -> int:
    if command == "etl-smoke":
        from .etl_smoke import main as etl_smoke_main

        etl_smoke_main(argv)
        return 0
    if command == "ci-smoke":
        from .ci_smoke import main as ci_smoke_main

        ci_smoke_main(argv)
        return 0
    if command == "rules-smoke":
        from .rules_smoke import main as rules_smoke_main

        return rules_smoke_main()
    if command == "health-check":
        from .health_check import main as health_check_main

        return health_check_main(argv)
    if command == "golden-master":
        from .golden_master import main as golden_master_main

        golden_master_main(argv)
        return 0
    raise ValueError(f"Unsupported command: {command}")


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if args and args[0] in {"etl-smoke", "ci-smoke", "rules-smoke", "health-check", "golden-master"}:
        return _run_tool(args[0], args[1:])
    return _run_minimal_pipeline(args)


if __name__ == "__main__":
    raise SystemExit(main())

