"""SQLite- und SQL-Skript-Export für Buchungen und Allopay."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any


def _norm_bu(bu: Any) -> Any:
    if bu == "" or bu is None:
        return None
    s = str(bu).strip()
    if s.isdigit():
        return int(s)
    return s


def _coerce_umsatz(v: Any) -> float | None:
    if isinstance(v, (int, float)):
        return round(float(v), 2)
    try:
        return round(float(v), 2)
    except (TypeError, ValueError):
        return None


def _row_tuple(row: dict[str, Any], config: dict[str, Any], *, allopay: bool) -> tuple[Any, ...]:
    kost = config["STRIPE_KOST"] if allopay else config["KOST"]
    bank = config["STRIPE_BANK"] if allopay else config["BANK_KONTO"]
    return (
        _coerce_umsatz(row["Umsatz Euro"]),
        _norm_bu(row["BU Gkto"]),
        row["Beleg 1"],
        row["Datum"],
        kost,
        bank,
        row["Buchungstext"],
    )


_DDL = """
CREATE TABLE buchungen (
    umsatz_euro REAL,
    bu_gkto TEXT,
    beleg_1 INTEGER,
    datum TEXT,
    kost_1 INTEGER,
    bank INTEGER,
    buchungstext TEXT
);
CREATE TABLE allopay (
    umsatz_euro REAL,
    bu_gkto TEXT,
    beleg_1 INTEGER,
    datum TEXT,
    kost_1 INTEGER,
    bank INTEGER,
    buchungstext TEXT
);
"""


def exportiere_sqlite(
    rows_buchungen: list[dict[str, Any]],
    rows_allopay: list[dict[str, Any]],
    output_path: str,
    config: dict[str, Any],
) -> None:
    """Schreibt zwei Tabellen (`buchungen`, `allopay`) in eine SQLite-Datei."""
    path = Path(output_path)
    if path.exists():
        path.unlink()
    conn = sqlite3.connect(output_path)
    try:
        conn.executescript(_DDL)
        conn.executemany(
            "INSERT INTO buchungen VALUES (?,?,?,?,?,?,?)",
            (_row_tuple(r, config, allopay=False) for r in rows_buchungen),
        )
        conn.executemany(
            "INSERT INTO allopay VALUES (?,?,?,?,?,?,?)",
            (_row_tuple(r, config, allopay=True) for r in rows_allopay),
        )
        conn.commit()
    finally:
        conn.close()


def _sql_literal(val: Any) -> str:
    if val is None:
        return "NULL"
    if isinstance(val, bool):
        return "1" if val else "0"
    if isinstance(val, int):
        return str(val)
    if isinstance(val, float):
        return repr(val)
    return "'" + str(val).replace("'", "''") + "'"


def exportiere_sql_skript(
    rows_buchungen: list[dict[str, Any]],
    rows_allopay: list[dict[str, Any]],
    output_path: str,
    config: dict[str, Any],
) -> None:
    """Schreibt CREATE TABLE + INSERT als UTF-8-SQL-Datei (SQLite-kompatibel)."""
    lines: list[str] = [
        _DDL.strip(),
        "",
    ]
    for r in rows_buchungen:
        t = _row_tuple(r, config, allopay=False)
        lines.append(
            "INSERT INTO buchungen VALUES ("
            + ", ".join(_sql_literal(x) for x in t)
            + ");"
        )
    for r in rows_allopay:
        t = _row_tuple(r, config, allopay=True)
        lines.append(
            "INSERT INTO allopay VALUES ("
            + ", ".join(_sql_literal(x) for x in t)
            + ");"
        )
    Path(output_path).write_text("\n".join(lines) + "\n", encoding="utf-8")
