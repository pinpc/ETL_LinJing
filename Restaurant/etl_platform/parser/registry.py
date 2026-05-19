"""Parser registry placeholders."""

from __future__ import annotations

import csv
from pathlib import Path

from ..shared.errors import ConfigurationError, ValidationError
from ..shared.models import ParsedTransaction
from .interfaces import IParser, ParseRequest


class ParserRegistry:
    """Registry to resolve parser adapters by source type."""

    def __init__(self) -> None:
        self._parsers: dict[str, IParser] = {}

    def register(self, source_type: str, parser: IParser) -> None:
        self._parsers[source_type.lower()] = parser

    def parse(self, request: ParseRequest) -> list[ParsedTransaction]:
        parser = self._parsers.get(request.source_type.lower())
        if parser is None:
            raise ConfigurationError(f"No parser registered for source_type='{request.source_type}'.")
        return parser.parse(request)


class CsvParser(IParser):
    """Minimal CSV parser with canonical normalization."""

    def parse(self, request: ParseRequest) -> list[ParsedTransaction]:
        if not request.source_path.exists():
            raise ValidationError(f"Source file not found: {request.source_path}")
        if request.source_path.suffix.lower() != ".csv":
            raise ValidationError("Minimal parser currently supports only CSV input.")

        rows: list[ParsedTransaction] = []
        with request.source_path.open("r", encoding="utf-8-sig", newline="") as csv_file:
            reader = csv.DictReader(csv_file)
            for raw_row in reader:
                rows.append(_normalize_row(raw_row, request))
        return rows


def _normalize_row(raw_row: dict[str, str], request: ParseRequest) -> ParsedTransaction:
    """Normalize heterogeneous source columns into ParsedTransaction."""

    def _get(*keys: str) -> str:
        for key in keys:
            value = raw_row.get(key)
            if value is not None and str(value).strip():
                return str(value).strip()
        return ""

    amount_raw = _get("amount", "betrag", "value", "umsatz")
    booking_date = _get("booking_date", "date", "buchungsdatum")
    text = _get("text", "booking_text", "verwendungszweck", "description")
    reference = _get("reference", "ref", "beleg", "txn_id")

    if not amount_raw:
        raise ValidationError("Missing amount in source row.")
    if not booking_date:
        raise ValidationError("Missing booking date in source row.")

    amount = _parse_amount(amount_raw)
    return ParsedTransaction(
        tenant_id=request.tenant_id,
        source_type=request.source_type,
        amount=amount,
        booking_date=booking_date,
        text=text,
        reference=reference,
        metadata={"source_path": str(Path(request.source_path))},
    )


def _parse_amount(raw: str) -> float:
    normalized = raw.strip().replace(" ", "")
    if "," in normalized and "." in normalized:
        # Decide decimal separator by last occurrence, remove the other as thousands separator.
        if normalized.rfind(",") > normalized.rfind("."):
            normalized = normalized.replace(".", "").replace(",", ".")
        else:
            normalized = normalized.replace(",", "")
    elif "," in normalized:
        normalized = normalized.replace(",", ".")
    try:
        return float(normalized)
    except ValueError as exc:
        raise ValidationError(f"Invalid amount value: '{raw}'") from exc

