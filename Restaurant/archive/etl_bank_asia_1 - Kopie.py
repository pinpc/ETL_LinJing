"""
Legacy-Startdatei: kann direkt ausgeführt werden (fügt das übergeordnete Verzeichnis zu sys.path hinzu).

Bevorzugt: vom Ordner ``asia`` aus ``python -m asia_bank_etl`` oder die gleichnamige Datei eine Ebene höher.
"""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from asia_bank_etl.cli import main  # noqa: E402

if __name__ == "__main__":
    main()
