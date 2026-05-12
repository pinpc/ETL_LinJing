"""Debugger-Wrapper fuer den Start aus dem Projekt-Root."""

from __future__ import annotations

import sys
from pathlib import Path


def main() -> int:
    project_root = Path(__file__).resolve().parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    from jupiter_kasse_etl.cli import main as cli_main

    return cli_main()


if __name__ == "__main__":
    raise SystemExit(main())
