"""Shared PDF text extraction and German euro amount parsing for bank invoice parsers."""

from __future__ import annotations

import logging
import os
import re
from pathlib import Path

import pdfplumber

try:
    from .money_utils import parse_german_euro_amount
except ImportError:
    from money_utils import parse_german_euro_amount

logger = logging.getLogger(__name__)

DEFAULT_OCR_DPI = 250
_EURO_TOKEN = re.compile(r"(-?[\d.]+,\d{2,3})\s*(?:€|&|\u20ac)?")


def resolve_ocr_dpi(override: int | None = None) -> int:
    """OCR-Auflösung: Parameter > ``EDEKA_OCR_DPI`` > ``DEFAULT_OCR_DPI`` (250)."""
    if override is not None:
        return override
    raw = os.environ.get("EDEKA_OCR_DPI", "").strip()
    if raw:
        return int(raw)
    return DEFAULT_OCR_DPI


def last_german_euro_amounts(line: str) -> list[float]:
    """Return all euro amounts found in a single PDF text line."""
    return [parse_german_euro_amount(match.group(1)) for match in _EURO_TOKEN.finditer(line)]


def extract_pdf_text(
    filepath: Path,
    *,
    log_prefix: str = "PDF",
    ocr_dpi: int | None = None,
) -> str:
    """Read PDF text layer; fall back to OCR for scanned documents."""
    parts: list[str] = []
    with pdfplumber.open(str(filepath)) as pdf:
        for page in pdf.pages:
            parts.append(page.extract_text() or "")
    text = "\n".join(parts).strip()
    if text:
        return text

    try:
        from pdf2image import convert_from_path
        import pytesseract
    except ImportError as exc:
        logger.warning(
            "%s %s: kein Textlayer, OCR-Pakete fehlen (%s)",
            log_prefix,
            filepath.name,
            exc,
        )
        return ""

    dpi = resolve_ocr_dpi(ocr_dpi)
    logger.info("%s %s: OCR (gescanntes PDF, %s dpi)", log_prefix, filepath.name, dpi)
    images = convert_from_path(str(filepath), dpi=dpi)
    ocr_parts = [pytesseract.image_to_string(image, lang="deu+eng") for image in images]
    return "\n".join(ocr_parts)
