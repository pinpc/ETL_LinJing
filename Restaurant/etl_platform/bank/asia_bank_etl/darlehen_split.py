"""Zeilen-Splits aus Banktext (z. B. Sparkasse Darlehen Tilgung/Zins)."""

from __future__ import annotations

import logging
import re
from copy import deepcopy
from typing import Any

logger = logging.getLogger(__name__)

_RE_TILGUNG = re.compile(r"Tilgung\s+([\d.]+,\d{2})", re.IGNORECASE)
_RE_ZINSEN = re.compile(r"Zinsen\s+([\d.]+,\d{2})", re.IGNORECASE)
_RE_DARL = re.compile(r"Rechnung\s+Darl|Darl\.-Leistung", re.IGNORECASE)
_RE_DARL_NR = re.compile(r"Darl\.-Leistung\s+(\d+)", re.IGNORECASE)
_RE_PERIOD = re.compile(
    r"F[uü]r\s+(\d{2})\.(\d{2})\.(\d{4})\s*[-–]\s*\d{2}\.(\d{2})\.(\d{4})",
    re.IGNORECASE,
)


def _parse_de_amount(raw: str) -> float:
    return float(raw.replace(".", "").replace(",", "."))


def _signed_parts(bank_amt: float, tilgung: float, zinsen: float) -> tuple[float, float]:
    sign = -1.0 if bank_amt < 0 else 1.0
    return round(sign * tilgung, 2), round(sign * zinsen, 2)


def _period_label(text: str) -> str:
    period = _RE_PERIOD.search(text)
    if not period:
        return ""
    return f"{period.group(2)} {period.group(3)}"


def _darlehen_prefix(text: str) -> str:
    nr_m = _RE_DARL_NR.search(text)
    if nr_m:
        return f"Sparkasse Darlehen {nr_m.group(1)}"
    return "Sparkasse Darlehen"


def _split_row(
    base: dict[str, Any],
    *,
    amount: float,
    bu: str,
    label: str,
) -> dict[str, Any]:
    row = deepcopy(base)
    row["Umsatz Euro"] = amount
    row["BU Gkto"] = bu
    row["Buchungstext"] = label
    row["_skip_buchung_mapping"] = True
    return row


def expand_sparkasse_darlehen_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Teilt Darlehensrate in Tilgung (631) + Zinsen (2120), Beträge aus Banktext."""
    out: list[dict[str, Any]] = []
    for row in rows:
        text = str(row.get("Buchungstext") or "")
        if not _RE_DARL.search(text):
            out.append(row)
            continue

        m_tilg = _RE_TILGUNG.search(text)
        m_zins = _RE_ZINSEN.search(text)
        if not m_tilg or not m_zins:
            logger.warning(
                "Sparkasse Darlehen: Tilgung/Zinsen nicht im Text – keine Aufteilung (%s)",
                text[:80],
            )
            out.append(row)
            continue

        bank_amt = float(row.get("Umsatz Euro") or 0)
        tilgung_signed, zinsen_signed = _signed_parts(
            bank_amt,
            _parse_de_amount(m_tilg.group(1)),
            _parse_de_amount(m_zins.group(1)),
        )
        prefix = _darlehen_prefix(text)
        period = _period_label(text)
        tilg_label = f"{prefix} Tilgung {period}".strip()
        zins_label = f"{prefix} Zins {period}".strip()

        total = round(tilgung_signed + zinsen_signed, 2)
        if abs(total - round(bank_amt, 2)) > 0.02:
            logger.warning(
                "Sparkasse Darlehen: Split-Summe %.2f != Bank %.2f",
                total,
                bank_amt,
            )

        out.append(_split_row(row, amount=tilgung_signed, bu="631", label=tilg_label))
        out.append(_split_row(row, amount=zinsen_signed, bu="2120", label=zins_label))
        logger.info(
            "Sparkasse Darlehen gesplittet: Tilgung %.2f (631) + Zins %.2f (2120)",
            tilgung_signed,
            zinsen_signed,
        )

    return out
