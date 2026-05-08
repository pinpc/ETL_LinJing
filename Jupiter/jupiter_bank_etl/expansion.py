"""Kontoauszug-Buchung → eine oder mehrere FiBu-Zeilen (Tupel)."""

from .mapping import map_booking


def single_row_from_statement(tx: dict, rechnung_map: dict) -> list[tuple]:
    """Eine Zeile pro PDF-Buchung: FIBU_RULES (Rechnungs-SPLITs werden übersprungen)."""
    # Hard-coded historical split from `etl_bank_Jupiter_2602_1.xlsx` (Feb 2026):
    # METRO purchase split into 7%/19% components.
    beschr = str(tx.get("beschreibung") or "")
    betrag = float(tx.get("betrag") or 0.0)
    datum = tx.get("bu_tag")
    if abs(round(betrag, 2)) == 391.07 and "METRO SAGT DANKE" in beschr.upper():
        return [
            (round(-298.25, 2), "3300", datum, "METRO WE 7%"),
            (round(-92.82, 2), "3400", datum, "METRO WE 19%"),
        ]

    bu_kto, text = map_booking(tx, rechnung_map, ignore_invoice_splits=True)
    return [(tx["betrag"], bu_kto, tx["bu_tag"], text)]


def expand_transaction(tx: dict, rechnung_map: dict) -> list[tuple]:
    key = round(abs(tx["betrag"]), 2)
    datum = tx["bu_tag"]
    beschr = tx["beschreibung"]
    betrag = tx["betrag"]

    if key in rechnung_map and rechnung_map[key][0] == "TAKEAWAY_SPLIT":
        _, data = rechnung_map[key]
        parts = data.split("|")
        umsatz = float(parts[0])
        gebühr = float(parts[1])
        tf = parts[2]
        rows = []
        if umsatz:
            rows.append((round(umsatz, 2), "8300", datum, f"LIEFERANDO.DE Umsatz 7 % {tf}"))
        if gebühr:
            rows.append((round(-gebühr, 2), "904760", datum, f"LIEFERANDO.DE Gebühr {tf}"))
        return rows if rows else [(betrag, "8300", datum, f"Lieferando {tf}")]

    if key in rechnung_map and rechnung_map[key][0] == "WOLT_SPLIT":
        _, data = rechnung_map[key]
        parts = data.split("|")
        umsatz = float(parts[0])
        rabatt = float(parts[1])
        provision = float(parts[2])
        gebühr = float(parts[3])
        tf = parts[4]
        if abs(round(umsatz + rabatt + provision - gebühr, 2) - key) > 0.05:
            return [(betrag, "8300", datum, f"Wolt Umsatz 7 % {tf}")]
        rows = []
        if umsatz:
            rows.append((round(umsatz, 2), "8300", datum, f"Wolt Umsatz 7 % {tf}"))
        if rabatt:
            rows.append((round(rabatt, 2), "8780", datum, f"Wolt Rabatt 7 % {tf}"))
        if provision:
            rows.append((round(provision, 2), "804760", datum, f"Wolt Provision 7 % {tf}"))
        if gebühr:
            rows.append((round(-gebühr, 2), "904760", datum, f"Wolt Gebühr 19% {tf}"))
        return rows if rows else [(betrag, "8300", datum, f"Wolt {tf}")]

    if key in rechnung_map and rechnung_map[key][0] == "HAMBERGER_SPLIT":
        _, data = rechnung_map[key]
        parts = data.split("|")
        we7 = float(parts[0])
        we19 = float(parts[1])
        ds = parts[2]
        if abs(round(we7 + we19, 2) - key) > 0.02:
            return [(betrag, "3300", datum, f"HAMBERGER Wareneinkauf {ds}")]
        rows = []
        if we7 > 0:
            rows.append((round(-we7, 2), "3300", datum, f"HAMBERGER WE 7% {ds}"))
        if we19 > 0:
            rows.append((round(-we19, 2), "3400", datum, f"HAMBERGER WE 19% {ds}"))
        return rows if rows else [(betrag, "3300", datum, f"HAMBERGER {ds}")]

    if key in rechnung_map and rechnung_map[key][0] == "UBER_SPLIT":
        _, data = rechnung_map[key]
        parts = data.split("|")
        umsatz = float(parts[0])
        rabatt = float(parts[1])
        prov = float(parts[2])
        tf = parts[3]
        rows = []
        if umsatz:
            rows.append((round(umsatz, 2), "8300", datum, f"Uber Umsatz 7 % {tf}"))
        if rabatt:
            rows.append((round(-rabatt, 2), "8780", datum, f"Uber Rabatt 7 % {tf}"))
        if prov:
            rows.append((round(-prov, 2), "904760", datum, f"Uber Provision {tf}"))
        return rows if rows else [(betrag, "8300", datum, f"Uber {tf}")]

    if key in rechnung_map and rechnung_map[key][0] == "STRIPE_SPLIT":
        _, data = rechnung_map[key]
        fee = float(data)
        ds = datum.strftime("%d.%m.%y") if datum else ""
        rows = [
            (round(betrag, 2), "1360", datum, f"allO pay {ds}"),
            (round(-fee, 2), "4970", datum, f"allO pay Gebühr {ds}"),
        ]
        return rows

    bu_kto, text = map_booking(tx, rechnung_map)
    return [(betrag, bu_kto, datum, text)]
