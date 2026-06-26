"""Bekannte Golden-Master-Abweichungen pro DOG-Tenant (Stand: Fibu 04/2026).

Aktualisieren, wenn sich IST nach Code-Änderungen bewusst unterscheidet.
Unerwartete Abweichungen → Baseline ergänzen oder ETL/Regeln fixen.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TenantBaseline:
    """Erwartete compare_final-Meldungen und EXTRA-Zeilen (BU, Beleg2, Buchungstext)."""

    deviations: frozenset[str]
    extra_rows: frozenset[tuple[str, str, str]] = frozenset()
    ignore_beleg2: bool = False


# ---------------------------------------------------------------------------
# CTM — Summe OK; strukturelle Telekom/VL/Massion-Diffs (bewusst offen)
# ---------------------------------------------------------------------------
CTM = TenantBaseline(
    deviations=frozenset({
        "Umsatz: SOLL=-1219.95 IST=-191.11 | ZA-Telekom Deutschland",
        "Datum: SOLL=2026-04-07 IST=2026-04-29 | ZA-Telekom Deutschland",
        "FEHLT in IST: BU=1750 B2= | VL 04 2026",
        "FEHLT in IST: BU=71904 B2= | ZA-Telekom Deutschland",
        "FEHLT in IST: BU=1740 B2=4 | F. Massion 01 - 04 2026",
        "Umsatz: SOLL=-1321.16 IST=-321.16 | P. Massion 04 2026",
        "EXTRA in IST: BU=1750 B2=4 | VL 04 2026",
        "EXTRA in IST: BU=1740 B2=4 | F. Massion 04 2026",
    }),
)

# ---------------------------------------------------------------------------
# Ramtel12 — Display-Split (Umsatz Zeile 1); NK-Zeilen ohne Betrag; Telekom/KSK Monat
# ---------------------------------------------------------------------------
RAMTEL12 = TenantBaseline(
    deviations=frozenset({
        "Umsatz: SOLL=-73.35 IST=-183.74 | Stadtwerke Leonberg Wasser 04 2026",
        "FEHLT in IST: BU=4240 B2=36 | Stadtwerke Leonberg Abwasser 04 2026",
        "Umsatz: SOLL=1512.73 IST=2083.93 | Miete D.O.G. GmbH 1. OG 2026 04",
        "FEHLT in IST: BU=8402 B2=36 | NK D.O.G. GmbH 1. OG 2026 04",
        "Umsatz: SOLL=4320.16 IST=5580.97 | Miete D.O.G. GmbH 2. OG 2026 04",
        "FEHLT in IST: BU=8402 B2=36 | NK D.O.G. GmbH 2. OG 2026 04",
        "Umsatz: SOLL=1704.08 IST=2441.88 | Miete Hirotec EG 2026 04",
        "FEHLT in IST: BU=8406 B2=36 | NK  Hirotec EG 2026 04",
        "Umsatz: SOLL=1820.7 IST=2225.9 | Miete systemgruppe integrated 2026 04",
        "FEHLT in IST: BU=8409 B2=37 | NK systemgruppe integrated 2026 04",
        "Umsatz: SOLL=2018.31 IST=3011.96 | Miete Köhler Leonberg 2026 04",
        "FEHLT in IST: BU=8404 B2=39 | NK Miete Köhler Leonberg 2026 04",
        "Datum: SOLL=2026-04-08 IST=2026-04-09 | Die Haftpflichtkasse 03 25 - 02 26",
        "Umsatz: SOLL=1470.84 IST=1887.34 | Miete Bruchmann EG 2026 04",
        "FEHLT in IST: BU=8408 B2=40 | NK Bruchmann EG 2026 04",
        "FEHLT in IST: BU=9 04800 B2=46 | Telekom Alarm Pumpe 03 2026",
        "FEHLT in IST: BU=652 B2=47 | KSK Tilgung 04 202 Merklingen/Dresden",
        "FEHLT in IST: BU= B2= | ",
        "EXTRA in IST: BU=9 04800 B2=46 | Telekom Alarm Pumpe 04 2026",
        "EXTRA in IST: BU=652 B2=47 | KSK Tilgung 04 2026 Merklingen/Dresden",
    }),
    extra_rows=frozenset({
        ("6855", "2", "Bankgebühren Geldmarktkonto"),
    }),
)

# ---------------------------------------------------------------------------
# DOG Holding — 17/17 SOLL semantisch OK; Agenda endet 28.04.; Ping Zhou Datum
# ---------------------------------------------------------------------------
DOG_HOLDING = TenantBaseline(
    deviations=frozenset({
        "Datum: SOLL=2026-04-27 IST=2026-04-28 | ZA-Ping Zhou",
    }),
    extra_rows=frozenset({
        ("1703", "46", "Auszahlung Ramtel12 Darlehen"),
        ("1740", "47", "M. Chen 04 2026"),
        ("1740", "47", "F. Massion 04 2026"),
        ("70104", "47", "ZA-Softwareüberlassung SFirm"),
        ("4970", "47", "Ebics 04 2026"),
        ("4970", "47", "Bankgebühr 04 2026"),
    }),
    ignore_beleg2=True,
)

BASELINES: dict[str, TenantBaseline] = {
    "CTM": CTM,
    "Ramtel12": RAMTEL12,
    "DOG Holding": DOG_HOLDING,
}
