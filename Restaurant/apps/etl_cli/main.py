"""CLI entrypoint for minimal ETL pipeline."""

from __future__ import annotations

import argparse
from pathlib import Path

from ...platform.bank.interfaces import BankRunRequest
from ...platform.bank.service import BankService


def main() -> None:
    """Run minimal parser -> rule_engine -> output flow."""
    parser = argparse.ArgumentParser(description="Run minimal ETL pipeline.")
    parser.add_argument("--tenant-id", required=True, help="Tenant identifier.")
    parser.add_argument(
        "--source",
        required=True,
        help="CSV input path or directory containing one CSV file.",
    )
    parser.add_argument("--output", required=True, help="Output CSV path.")
    args = parser.parse_args()

    service = BankService()
    rows = service.run(
        BankRunRequest(
            tenant_id=args.tenant_id,
            source_dir=Path(args.source),
            output_path=Path(args.output),
        )
    )
    print(f"Processed {len(rows)} rows to '{args.output}'.")


if __name__ == "__main__":
    main()

