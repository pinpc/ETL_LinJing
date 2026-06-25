"""Golden-Master-Vergleich: IST-Excel (Final) vs. SOLL-Agenda-Datei."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

import openpyxl

from .runner import run

# Bekannte Abweichungen (Display-Split: Umsatz nur Zeile 1; Geldmarktkonto extra)
_KNOWN_EXTRA = {
    ("6855", "2", "Bankgebühren Geldmarktkonto"),
}


@dataclass(frozen=True)
class FinalRow:
    umsatz: Decimal | None
    bu_gkto: str
    beleg1: str
    beleg2: str
    datum: date
    konto: str
    buchungstext: str


def _norm_text(v: str) -> str:
    return re.sub(r"\s+", " ", (v or "").strip())


def _norm_bu(v) -> str:
    return _norm_text(str(v or "")).replace(" ", "")


def _norm_beleg1(v) -> str:
    if v is None:
        return ""
    s = str(v).strip()
    if s.lower() in ("none", ""):
        return ""
    if s.isdigit():
        return str(int(s))
    return s


def _row_key(row: FinalRow) -> tuple:
    return (_norm_bu(row.bu_gkto), row.beleg2, _norm_text(row.buchungstext))


def _read_final(path: Path, sheet: str | None = None) -> list[FinalRow]:
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    ws = wb[sheet or wb.sheetnames[0]]
    headers = [c.value for c in next(ws.iter_rows(min_row=1, max_row=1))]
    idx = {h: i for i, h in enumerate(headers)}
    rows: list[FinalRow] = []
    for r in ws.iter_rows(min_row=2, values_only=True):
        if not r or all(v is None for v in r[:7]):
            continue
        bt = r[idx["Buchungstext"]]
        if not bt or str(bt).startswith("Summe"):
            continue
        u = r[idx["Umsatz"]]
        beleg2_raw = r[idx["Beleg2"]]
        beleg2 = str(int(beleg2_raw)) if beleg2_raw is not None else ""
        rows.append(FinalRow(
            umsatz=Decimal(str(u)) if u is not None else None,
            bu_gkto=str(r[idx["BU Gkto"]] or "").strip(),
            beleg1=_norm_beleg1(r[idx["Beleg1"]]),
            beleg2=beleg2,
            datum=r[idx["Datum"]].date() if isinstance(r[idx["Datum"]], datetime) else r[idx["Datum"]],
            konto=str(r[idx["Konto"]] or "").strip(),
            buchungstext=str(bt).strip(),
        ))
    wb.close()
    return rows


def compare_final(ist_path: Path, soll_path: Path, soll_sheet: str | None = None) -> list[str]:
    """Vergleicht Final-Blatt IST vs. SOLL. Gibt Liste der Abweichungen zurück."""
    ist = _read_final(ist_path, "Final")
    soll = _read_final(soll_path, soll_sheet)

    errors: list[str] = []
    soll_keys = {_row_key(r): r for r in soll}
    ist_keys = {_row_key(r): r for r in ist}

    for key, s_row in soll_keys.items():
        if key not in ist_keys:
            errors.append(f"FEHLT in IST: BU={s_row.bu_gkto} B2={s_row.beleg2} | {s_row.buchungstext}")
            continue
        i_row = ist_keys[key]
        # Display-Split: Folgezeile ohne Umsatz → kein Betragsvergleich
        if s_row.umsatz is not None and i_row.umsatz is not None:
            if abs(s_row.umsatz - i_row.umsatz) > Decimal("0.01"):
                errors.append(
                    f"Umsatz: SOLL={s_row.umsatz} IST={i_row.umsatz} | {s_row.buchungstext}"
                )
        if s_row.datum != i_row.datum:
            errors.append(f"Datum: SOLL={s_row.datum} IST={i_row.datum} | {s_row.buchungstext}")

    for key, i_row in ist_keys.items():
        if key not in soll_keys:
            raw = (i_row.bu_gkto, i_row.beleg2, i_row.buchungstext)
            if raw not in _KNOWN_EXTRA:
                errors.append(f"EXTRA in IST: BU={i_row.bu_gkto} B2={i_row.beleg2} | {i_row.buchungstext}")

    # Summe: nur Zeilen mit Umsatz (Display-Split-Zeile 2 zählt nicht)
    ist_sum = sum(r.umsatz for r in ist if r.umsatz is not None)
    # SOLL-Summe entspricht Bank-Summe minus fehlende Geldmarkt-Zeile (+14.26 extra in IST)
    konto_sum = sum(r.umsatz for r in _read_final(ist_path, "Kontoauszug") if r.umsatz is not None)
    if abs(ist_sum - konto_sum) > Decimal("0.01"):
        errors.append(f"Summe Final vs Kontoauszug: Final={ist_sum:.2f} Konto={konto_sum:.2f}")

    return errors


def run_golden_master() -> int:
    """Führt ETL + Golden-Master aus. Exit-Code 0 = OK."""
    cases = [
        (
            "CTM",
            "tenants/ctm",
            Path(r"C:\temp_cursor\DOG\2026\CTM\Fibu 04 2026\Kontoauszug_CTM_04_2026.xlsx"),
            Path(r"C:\temp_cursor\DOG\2026\CTM\Fibu 04 2026\Agenda_CTM_Bank_2026 04.xlsx"),
            None,
        ),
        (
            "Ramtel12",
            "tenants/ramtel12",
            Path(r"C:\temp_cursor\DOG\2026\Ramtel12\Fibu 04 2026\Kontoauszug_Ramtel12_04_2026.xlsx"),
            Path(r"C:\temp_cursor\DOG\2026\Ramtel12\Fibu 04 2026\Agenda_Bank_Ramtel12_04 2026.xlsx"),
            "tmp6A99",
        ),
    ]
    failed = 0
    for name, tenant, ist_path, soll_path, sheet in cases:
        print(f"\n=== {name} ===")
        try:
            run(tenant)
        except PermissionError:
            print(f"WARN: {ist_path.name} gesperrt – vergleiche vorhandene Datei")
        errs = compare_final(ist_path, soll_path, sheet)
        if errs:
            failed += 1
            print(f"FAIL ({len(errs)} Abweichungen):")
            for e in errs[:25]:
                print(f"  - {e}")
            if len(errs) > 25:
                print(f"  ... und {len(errs) - 25} weitere")
        else:
            print("OK – Final entspricht SOLL")
    return failed


if __name__ == "__main__":
    raise SystemExit(run_golden_master())
