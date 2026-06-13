"""Shared PDF text extraction and German euro amount parsing for bank invoice parsers."""

from __future__ import annotations

import logging
import re
from pathlib import Path

import pdfplumber

logger = logging.getLogger(__name__)

_EURO_TOKEN = re.compile(r"(-?[\d.]+,\d{2,3})\s*(?:€|&|\u20ac)?")


def parse_german_euro_amount(text: str, *, round_to: int = 2) -> float:
    """Parse German-formatted amounts such as ``1.234,56`` or ``12,345`` (3 decimals)."""
    normalized = str(text).replace(".", "").replace(" ", "")
    if re.match(r"^-?\d+,\d{3}$", normalized):
        normalized = normalized[:-1]
    value = float(normalized.replace(",", "."))
    return round(value, round_to) if round_to >= 0 else value


def last_german_euro_amounts(line: str) -> list[float]:
    """Return all euro amounts found in a single PDF text line."""
    return [parse_german_euro_amount(match.group(1)) for match in _EURO_TOKEN.finditer(line)]


def extract_pdf_text(filepath: Path, *, log_prefix: str = "PDF") -> str:
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

    logger.info("%s %s: OCR (gescanntes PDF)", log_prefix, filepath.name)
    images = convert_from_path(str(filepath), dpi=300)
    ocr_parts = [pytesseract.image_to_string(image, lang="deu+eng") for image in images]
    return "\n".join(ocr_parts)
