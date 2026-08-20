"""Monatsbericht vs. Final: Umsatz 7 %, 19 %, Trinkgeld (0 %)."""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Iterable, Protocol

import pdfplumber

_EURO = Decimal("0.01")
_ZERO = Decimal("0.00")
_RE_MONATSBERICHT = re.compile(r"Monatsbericht", re.IGNORECASE)
_RE_SUMME_CELL = re.compile(r"^\s*Summe\s*$", re.IGNORECASE)


@dataclass(frozen=True)
class MonatsberichtTotals:
    """Monatsbericht-Summen: Umsatz 7 %, 19 %, 0 % (Trinkgeld)."""

    umsatz_7: Decimal
    umsatz_19: Decimal
    trinkgeld_0: Decimal
    source: str = ""


@dataclass(frozen=True)
class MonatsberichtCheckResult:
    """Vergleich Monatsbericht vs. Final (positive Trinkgeld-Zeilen)."""

    ok: bool
    monatsbericht: MonatsberichtTotals | None
    final_umsatz_7: Decimal
    final_umsatz_19: Decimal
    final_trinkgeld: Decimal
    diff_7: Decimal
    diff_19: Decimal
    diff_trinkgeld: Decimal
    message: str


class _HasTaxFields(Protocol):
    umsatz_euro: Decimal
    buchungstext: str


def _parse_german_amount(value: Any) -> Decimal:
    if value is None:
        return _ZERO
    if isinstance(value, Decimal):
        return value.quantize(_EURO)
    if isinstance(value, (int, float)):
        return Decimal(str(value)).quantize(_EURO)

    text = str(value).replace("€", "").replace("EUR", "").replace("\n", " ")
    text = re.sub(r"\s+", "", text)
    if not text:
        return _ZERO
    if "." in text and "," in text:
        text = text.replace(".", "").replace(",", ".")
    elif "," in text:
        text = text.replace(",", ".")
    try:
        return Decimal(text).quantize(_EURO)
    except InvalidOperation:
        return _ZERO


def _iter_monatsbericht_candidates(base_path: Path) -> Iterable[Path]:
    """base_path rekursiv, danach nur direkte PDFs in bis zu 2 Elternordnern."""
    root = Path(base_path)
    if root.exists():
        yield from sorted(root.rglob("*.pdf"), key=lambda path: path.name.lower())
    parent = root
    for _ in range(2):
        parent = parent.parent
        if not parent.exists():
            break
        yield from sorted(parent.glob("*.pdf"), key=lambda path: path.name.lower())


def find_monatsbericht_pdf(base_path: Path) -> Path | None:
    """Sucht ``*Monatsbericht*.pdf`` unter ``base_path`` und bis zu 2 Elternordnern."""
    if not base_path:
        return None
    seen: set[str] = set()
    for path in _iter_monatsbericht_candidates(Path(base_path)):
        if not _RE_MONATSBERICHT.search(path.name):
            continue
        key = str(path.resolve()).lower()
        if key in seen:
            continue
        return path
    return None


def parse_monatsbericht_totals(pdf_path: Path) -> MonatsberichtTotals | None:
    """Liest die Summenzeile Umsatz 7 % / 19 % / 0 % aus dem Monatsbericht-PDF."""
    try:
        with pdfplumber.open(str(pdf_path)) as pdf:
            for page in pdf.pages:
                for table in page.extract_tables() or []:
                    for row in table or []:
                        if not row or len(row) < 7:
                            continue
                        if not _RE_SUMME_CELL.match(str(row[0] or "").strip()):
                            continue
                        umsatz_7 = _parse_german_amount(row[2])
                        umsatz_19 = _parse_german_amount(row[4])
                        trinkgeld_0 = _parse_german_amount(row[6])
                        if umsatz_7 == 0 and umsatz_19 == 0 and trinkgeld_0 == 0:
                            continue
                        return MonatsberichtTotals(
                            umsatz_7=umsatz_7,
                            umsatz_19=umsatz_19,
                            trinkgeld_0=trinkgeld_0,
                            source=pdf_path.name,
                        )
    except Exception as exc:
        print(
            f"WARNUNG [Monatsbericht]: PDF nicht lesbar ({pdf_path.name}): {exc}",
            file=sys.stderr,
        )
    return None


def sum_final_tax_totals(
    rows: Iterable[_HasTaxFields],
    *,
    text_umsatz_7: str,
    text_umsatz_19: str,
    text_trinkgeld: str,
) -> tuple[Decimal, Decimal, Decimal]:
    """Summiert Final: Umsatz 7 %, 19 %, positive Trinkgeld-Zeilen."""
    sum_7 = sum_19 = sum_tips = Decimal("0")
    labels = {
        text_umsatz_7.strip().lower(): "7",
        text_umsatz_19.strip().lower(): "19",
        text_trinkgeld.strip().lower(): "tips",
    }
    for row in rows:
        kind = labels.get(str(row.buchungstext or "").strip().lower())
        if kind is None:
            continue
        amount = Decimal(str(row.umsatz_euro)).quantize(_EURO)
        if kind == "7":
            sum_7 += amount
        elif kind == "19":
            sum_19 += amount
        elif amount > 0:
            sum_tips += amount
    return sum_7.quantize(_EURO), sum_19.quantize(_EURO), sum_tips.quantize(_EURO)


def _result_without_pdf(
    *,
    final_7: Decimal,
    final_19: Decimal,
    final_tips: Decimal,
    message: str,
) -> MonatsberichtCheckResult:
    return MonatsberichtCheckResult(
        ok=False,
        monatsbericht=None,
        final_umsatz_7=final_7,
        final_umsatz_19=final_19,
        final_trinkgeld=final_tips,
        diff_7=_ZERO,
        diff_19=_ZERO,
        diff_trinkgeld=_ZERO,
        message=message,
    )


def verify_final_against_monatsbericht(
    final_rows: Iterable[_HasTaxFields],
    pdf_base_dir: Path,
    *,
    text_umsatz_7: str,
    text_umsatz_19: str,
    text_trinkgeld: str,
    tolerance: Decimal = Decimal("0.02"),
    monatsbericht_pdf: Path | None = None,
) -> MonatsberichtCheckResult:
    """Vergleicht Final-Summen mit dem Monatsbericht unter ``pdf_base_dir``."""
    final_7, final_19, final_tips = sum_final_tax_totals(
        final_rows,
        text_umsatz_7=text_umsatz_7,
        text_umsatz_19=text_umsatz_19,
        text_trinkgeld=text_trinkgeld,
    )

    pdf_path = monatsbericht_pdf or find_monatsbericht_pdf(pdf_base_dir)
    if pdf_path is None:
        return _result_without_pdf(
            final_7=final_7,
            final_19=final_19,
            final_tips=final_tips,
            message=f"Kein Monatsbericht-PDF unter {pdf_base_dir}",
        )

    totals = parse_monatsbericht_totals(pdf_path)
    if totals is None:
        return _result_without_pdf(
            final_7=final_7,
            final_19=final_19,
            final_tips=final_tips,
            message=f"Monatsbericht nicht auswertbar: {pdf_path.name}",
        )

    diff_7 = (final_7 - totals.umsatz_7).quantize(_EURO)
    diff_19 = (final_19 - totals.umsatz_19).quantize(_EURO)
    diff_tips = (final_tips - totals.trinkgeld_0).quantize(_EURO)
    ok = all(abs(diff) <= tolerance for diff in (diff_7, diff_19, diff_tips))
    if ok:
        message = (
            f"Monatsbericht OK ({totals.source}): "
            f"7%={final_7} 19%={final_19} Trinkgeld={final_tips}"
        )
    else:
        message = (
            f"Monatsbericht Abweichung ({totals.source}): "
            f"7% Diff={diff_7} (Final {final_7} vs {totals.umsatz_7}), "
            f"19% Diff={diff_19} (Final {final_19} vs {totals.umsatz_19}), "
            f"Trinkgeld Diff={diff_tips} (Final {final_tips} vs {totals.trinkgeld_0})"
        )

    return MonatsberichtCheckResult(
        ok=ok,
        monatsbericht=totals,
        final_umsatz_7=final_7,
        final_umsatz_19=final_19,
        final_trinkgeld=final_tips,
        diff_7=diff_7,
        diff_19=diff_19,
        diff_trinkgeld=diff_tips,
        message=message,
    )


def log_monatsbericht_check(result: MonatsberichtCheckResult) -> None:
    """Schreibt Prüfergebnis nach stdout/stderr."""
    stream = sys.stdout if result.ok else sys.stderr
    prefix = "INFO" if result.ok else "WARNUNG"
    print(f"{prefix} [Monatsbericht]: {result.message}", file=stream)


def run_monatsbericht_check(
    final_rows: Iterable[_HasTaxFields],
    pdf_base_dir: Path,
    *,
    text_umsatz_7: str,
    text_umsatz_19: str,
    text_trinkgeld: str,
    tolerance: Decimal = Decimal("0.02"),
) -> MonatsberichtCheckResult:
    """Prüft Final gegen Monatsbericht und loggt das Ergebnis."""
    result = verify_final_against_monatsbericht(
        final_rows,
        pdf_base_dir,
        text_umsatz_7=text_umsatz_7,
        text_umsatz_19=text_umsatz_19,
        text_trinkgeld=text_trinkgeld,
        tolerance=tolerance,
    )
    log_monatsbericht_check(result)
    return result
