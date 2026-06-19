"""python -m etl_platform.bank.dog_bank_etl <tenant_id>"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from .runner import run

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

_TENANTS_DIR = Path(__file__).parents[3] / "tenants"


def main(argv: list[str] | None = None) -> None:
    args = argv if argv is not None else sys.argv[1:]
    if not args:
        print("Usage: python -m etl_platform.bank.dog_bank_etl <tenant_id>")
        print(f"Available tenants: {[d.name for d in _TENANTS_DIR.iterdir() if d.is_dir()]}")
        sys.exit(1)

    for tenant_id in args:
        tenant_dir = _TENANTS_DIR / tenant_id
        if not tenant_dir.exists():
            print(f"ERROR: Tenant-Verzeichnis nicht gefunden: {tenant_dir}", file=sys.stderr)
            sys.exit(1)
        out = run(tenant_dir)
        print(f"OK  [{tenant_id}] → {out}")


if __name__ == "__main__":
    main()
