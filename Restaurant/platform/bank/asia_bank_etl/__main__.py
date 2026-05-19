"""``python -m asia_bank_etl`` oder direktes Starten dieser Datei (Debugger)."""

from __future__ import annotations

import sys
from pathlib import Path


def _main() -> None:
    if __package__:
        from .cli import main as cli_main
    else:
        # Direktausführung: Paket "asia_bank_etl" über Elternordner ``asia`` auf sys.path.
        root = Path(__file__).resolve().parent.parent
        if str(root) not in sys.path:
            sys.path.insert(0, str(root))
        from asia_bank_etl.cli import main as cli_main

    cli_main()


if __name__ == "__main__":
    _main()
