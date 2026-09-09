"""Finanzamt-Sammelzeile LOHNST + UMS.ST in zwei Agenda-Zeilen teilen."""

from __future__ import annotations

import logging
import re
from copy import deepcopy
from typing import Any

logger = logging.getLogger(__name__)

_MONAT_MAP = {
    "JAN": "01",
    "FEB": "02",
    "MAR": "03",
    "MÄR": "03",
    "MRZ": "03",
    "APR": "04",
    "MAI": "05",
    "JUN": "06",
    "JUL": "07",
    "AUG": "08",
    "SEP": "09",
    "OKT": "10",
    "NOV": "11",
    "DEZ": "12",
}

_RE_LOHNST = re.compile(
    r"LOHNST\s+([A-ZÄÖÜ]{3})\.?\s*(\d{2})\s+([\d.]+,\d{2})\s*EUR",
    re.IGNORECASE,
)
_RE_UMSST_MONAT = re.compile(
    r"UMS\.ST\s+([A-ZÄÖÜ]{3})\.?\s*(\d{2})\s+([\d.]+,\d{2})\s*EUR",
    re.IGNORECASE,
)


def _parse_de_amount(raw: str) -> float:
    return float(raw.replace(".", "").replace(",", "."))


def _mm_yyyy(mon_abbr: str, yy: str) -> str:
    mm = _MONAT_MAP.get(mon_abbr.upper()) or _MONAT_MAP.get(mon_abbr.upper()[:3])
    if not mm:
        return ""
    return f"{mm} 20{yy}"


def _signed(bank_amt: float, part: float) -> float:
    sign = -1.0 if bank_amt < 0 else 1.0
    return round(sign * abs(part), 2)


def _row_like(base: dict[str, Any], *, amount: float, bu: str, label: str) -> dict[str, Any]:
    row = deepcopy(base)
    row["Umsatz Euro"] = amount
    row["BU Gkto"] = bu
    row["Buchungstext"] = label
    row["_skip_buchung_mapping"] = True
    return row


def expand_finanzamt_lohnst_umsst_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Teilt ``LOHNST … EUR UMS.ST … EUR`` in LSt + USt VA (Beträge aus Banktext)."""
    out: list[dict[str, Any]] = []
    for row in rows:
        text = str(row.get("Buchungstext") or "")
        m_lst = _RE_LOHNST.search(text)
        m_ust = _RE_UMSST_MONAT.search(text)
        if not m_lst or not m_ust:
            out.append(row)
            continue

        bank_amt = float(row.get("Umsatz Euro") or 0)
        lst_amt = _signed(bank_amt, _parse_de_amount(m_lst.group(3)))
        ust_amt = _signed(bank_amt, _parse_de_amount(m_ust.group(3)))
        lst_period = _mm_yyyy(m_lst.group(1), m_lst.group(2))
        ust_period = _mm_yyyy(m_ust.group(1), m_ust.group(2))
        if not lst_period or not ust_period:
            out.append(row)
            continue

        total = round(lst_amt + ust_amt, 2)
        if abs(total - round(bank_amt, 2)) > 0.02:
            logger.warning(
                "Finanzamt LOHNST/UMS.ST: Split-Summe %.2f != Bank %.2f",
                total,
                bank_amt,
            )

        out.append(_row_like(row, amount=lst_amt, bu="1741", label=f"LSt {lst_period}"))
        out.append(_row_like(row, amount=ust_amt, bu="1780", label=f"USt VA {ust_period}"))
        logger.info(
            "Finanzamt gesplittet: LSt %.2f (1741) + USt VA %.2f (1780)",
            lst_amt,
            ust_amt,
        )
    return out
