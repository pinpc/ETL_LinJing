from __future__ import annotations

import argparse
import os
from pathlib import Path

from .config import DEFAULT_BASE_PATH, DEFAULT_CASHBOOK_CANDIDATES, DEFAULT_OUTPUT_PATH
from .core import JupiterKasseETL


def _default_input() -> Path | None:
    env_value = os.environ.get("JUPITER_KASSE_INPUT")
    if env_value:
        return Path(env_value)

    for candidate in DEFAULT_CASHBOOK_CANDIDATES:
        if candidate.exists():
            return candidate

    return DEFAULT_CASHBOOK_CANDIDATES[0] if DEFAULT_CASHBOOK_CANDIDATES else None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="jupiter_kasse_etl",
        description="Jupiter Kasse ETL - Cashbook/Allopay -> Excel",
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=_default_input(),
        help="Path to input cashbook PDF or Excel file",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path(os.environ.get("JUPITER_KASSE_OUT", "")) if os.environ.get("JUPITER_KASSE_OUT") else DEFAULT_OUTPUT_PATH,
        help="Path to output Excel workbook",
    )
    parser.add_argument(
        "--pdf-base",
        type=Path,
        default=Path(os.environ.get("JUPITER_KASSE_PDF_BASE", "")) if os.environ.get("JUPITER_KASSE_PDF_BASE") else DEFAULT_BASE_PATH,
        help="Optional base directory for Allopay PDFs",
    )
    parser.add_argument(
        "--sheet",
        type=str,
        default=os.environ.get("JUPITER_KASSE_SHEET"),
        help="Optional sheet name for Excel cashbook input",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not args.input or not args.out:
        raise SystemExit(
            "Fehlende Parameter. Beispiel:\n"
            '  python -m jupiter_kasse_etl --input "<cashbook.pdf|cashbook.xlsx>" --out "<result.xlsx>" --pdf-base "<dir>"\n'
            "oder ENV: JUPITER_KASSE_INPUT / JUPITER_KASSE_OUT / JUPITER_KASSE_PDF_BASE"
        )

    result = JupiterKasseETL().run(
        input_path=args.input,
        output_path=args.out,
        pdf_base_dir=args.pdf_base,
        sheet_name=args.sheet,
    )

    print("=" * 60)
    print("VERARBEITUNG ABGESCHLOSSEN")
    print("=" * 60)
    print(f"OK: wrote {result.umsatz_count} Umsatz row(s)")
    print(f"OK: wrote {result.allopay_count} Allopay row(s) from base {result.pdf_base_dir}")
    print(f"OK: wrote {result.final_count} Final row(s)")
    print(f"OK: saved workbook to {result.saved_path}")
    return 0
