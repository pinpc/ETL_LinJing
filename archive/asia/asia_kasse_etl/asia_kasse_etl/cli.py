from __future__ import annotations

import argparse
import os
from pathlib import Path

from .core import AsiaKasseETL


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="asia_kasse_etl", description="Asia Kasse ETL - Cashbook/Allopay -> Excel")
    p.add_argument(
        "--input",
        type=Path,
        default=Path(os.environ.get("ASIA_KASSE_INPUT", "")) if os.environ.get("ASIA_KASSE_INPUT") else None,
        help="Path to input cashbook Excel file",
    )
    p.add_argument(
        "--out",
        type=Path,
        default=Path(os.environ.get("ASIA_KASSE_OUT", "")) if os.environ.get("ASIA_KASSE_OUT") else None,
        help="Path to output Excel workbook",
    )
    p.add_argument(
        "--pdf-base",
        type=Path,
        default=Path(os.environ.get("ASIA_KASSE_PDF_BASE", "")) if os.environ.get("ASIA_KASSE_PDF_BASE") else None,
        help="Optional base directory for Allopay PDFs",
    )
    p.add_argument(
        "--sheet",
        type=str,
        default=os.environ.get("ASIA_KASSE_SHEET", "cashbook"),
        help="Input sheet name (default: cashbook)",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if not args.input or not args.out:
        raise SystemExit(
            "Fehlende Parameter. Beispiel:\n"
            '  python -m asia_kasse_etl --input "<cashbook.xlsx>" --out "<result.xlsx>" --pdf-base "<dir>"\n'
            "oder ENV: ASIA_KASSE_INPUT / ASIA_KASSE_OUT / ASIA_KASSE_PDF_BASE"
        )

    result = AsiaKasseETL().run(
        input_path=args.input,
        output_path=args.out,
        pdf_base_dir=args.pdf_base,
        sheet_name=args.sheet,
    )

    print(f"OK: wrote {result.buchung_count} Buchung row(s)")
    print(f"OK: wrote {result.allopay_count} Allopay row(s) from base {result.pdf_base_dir}")
    print(f"OK: wrote {result.final_count} Final row(s)")
    print(f"OK: saved workbook to {result.saved_path}")
    return 0

