"""PDF-Buchungen mit Agenda zusammenführen (inkl. Fruchthaus-Split)."""

from __future__ import annotations

import logging
from typing import Any

import pandas as pd

from .text_normalize import kuerze_stripe_text

logger = logging.getLogger(__name__)

_EDEKA_PAYMENT_MARKERS = ("Union SB-Grosmarkt", "Grosmarkt Sudbayern")
_AMOUNT_TOLERANCE = 0.02


def _is_edeka_payment(text: str) -> bool:
    normalized = text.casefold()
    return any(marker.casefold() in normalized for marker in _EDEKA_PAYMENT_MARKERS)


def _edeka_split_rows_from_agenda(
    df_agenda: pd.DataFrame,
    datum: str,
    payment_amount: float,
) -> pd.DataFrame | None:
    day_rows = df_agenda[df_agenda["Datum"] == datum]
    edeka_rows = day_rows[day_rows["Buchungstext"].str.contains("Edeka", case=False, na=False)]
    if edeka_rows.empty:
        return None

    grouped_sum = round(float(edeka_rows["Umsatz Euro"].sum()), 2)
    if abs(grouped_sum - round(payment_amount, 2)) > _AMOUNT_TOLERANCE:
        return None

    return edeka_rows.sort_values("Buchungstext").reset_index(drop=True)


def lade_agenda(agenda_path: str, sheet: str) -> pd.DataFrame:
    """Lädt Agenda aus Excel-Datei und bereinigt Datentypen."""
    try:
        df = pd.read_excel(agenda_path, sheet_name=sheet)
        df["Datum"] = pd.to_datetime(df["Datum"]).dt.strftime("%d.%m.%Y")
        df["Umsatz Euro"] = pd.to_numeric(df["Umsatz Euro"], errors="coerce").round(2)
        df["BU Gkto"] = df["BU Gkto"].fillna("").astype(str).str.replace(
            r"\.0$", "", regex=True
        )
        df["Buchungstext"] = df["Buchungstext"].astype(str).str.strip()
        return df
    except Exception as e:
        logger.error("Fehler beim Laden der Agenda %s: %s", agenda_path, e)
        raise


def merge_mit_agenda_und_split(
    pdf_rows: list[dict[str, Any]],
    df_agenda: pd.DataFrame,
    config: dict[str, Any],
    *,
    beleg_1: str | int | None = None,
) -> list[dict[str, Any]]:
    """Mergt PDF-Buchungen mit Agenda und teilt Fruchthaus-Zahlungen auf."""
    fruchthaus_pdf = [r for r in pdf_rows if "Fruchthaus" in r["Buchungstext"]]
    fruchthaus_agenda = df_agenda[
        df_agenda["Buchungstext"].str.contains("Fruchthaus", na=False)
    ]

    if len(fruchthaus_pdf) > 1:
        logger.error(
            "Mehrere Fruchthaus-Buchungen im Kontoauszug gefunden. Automatischer Split nicht möglich."
        )
        raise ValueError("Fruchthaus-Validierung fehlgeschlagen")

    if len(fruchthaus_pdf) == 1:
        if len(fruchthaus_agenda) == 0:
            logger.error(
                "Keine Fruchthaus-Zeilen in der Agenda gefunden. Split nicht möglich."
            )
            raise ValueError("Fruchthaus-Split fehlgeschlagen")
        summe_agenda = round(fruchthaus_agenda["Umsatz Euro"].sum(), 2)
        buchungsbetrag = round(fruchthaus_pdf[0]["Umsatz Euro"], 2)
        if abs(summe_agenda - buchungsbetrag) > 0.02:
            logger.error(
                "Summe der Agenda-Fruchthaus-Zeilen (%.2f) stimmt nicht mit Buchungsbetrag (%.2f) überein.",
                summe_agenda,
                buchungsbetrag,
            )
            raise ValueError("Fruchthaus-Summe stimmt nicht überein")
        do_split = True
    else:
        do_split = False

    agenda_by_key: dict[tuple[str, float], Any] = {}
    for _, r in df_agenda.iterrows():
        key = (r["Datum"], round(r["Umsatz Euro"], 2))
        if key not in agenda_by_key:
            agenda_by_key[key] = r

    output_rows: list[dict[str, Any]] = []
    # Agenda SOLL: Beleg = Monatsnummer (z. B. 05), nicht laufende Nummer
    fixed_beleg: str | int | None = beleg_1
    beleg_counter = 1

    def _next_beleg() -> str | int:
        nonlocal beleg_counter
        if fixed_beleg is not None:
            return fixed_beleg
        current = beleg_counter
        beleg_counter += 1
        return current

    def _row(
        *,
        umsatz: Any,
        bu: Any,
        datum_val: Any,
        text_val: Any,
        skip_mapping: bool = False,
    ) -> dict[str, Any]:
        row: dict[str, Any] = {
            "Umsatz Euro": umsatz,
            "BU Gkto": bu,
            "Beleg 1": _next_beleg(),
            "Datum": datum_val,
            "KOST 1": config["KOST"],
            "Bank": config["BANK_KONTO"],
            "Buchungstext": text_val,
        }
        if skip_mapping:
            row["_skip_buchung_mapping"] = True
        return row

    for pdf_row in pdf_rows:
        datum = pdf_row["Datum"]
        gesamt = round(pdf_row["Umsatz Euro"], 2)
        text = pdf_row["Buchungstext"]
        skip_map = bool(pdf_row.get("_skip_buchung_mapping"))
        pre_bu = str(pdf_row.get("BU Gkto") or "")

        if "Fruchthaus" in text and do_split:
            for _, teil in fruchthaus_agenda.iterrows():
                output_rows.append(
                    _row(
                        umsatz=teil["Umsatz Euro"],
                        bu=teil["BU Gkto"],
                        datum_val=teil["Datum"],
                        text_val=teil["Buchungstext"],
                    )
                )
            continue

        if _is_edeka_payment(text):
            edeka_split = _edeka_split_rows_from_agenda(df_agenda, datum, gesamt)
            if edeka_split is not None:
                logger.info(
                    "Edeka-Rechnungsauswertung aus Agenda: %s (%.2f EUR) -> %s Zeilen",
                    datum,
                    gesamt,
                    len(edeka_split),
                )
                for _, teil in edeka_split.iterrows():
                    output_rows.append(
                        _row(
                            umsatz=teil["Umsatz Euro"],
                            bu=teil["BU Gkto"],
                            datum_val=teil["Datum"],
                            text_val=teil["Buchungstext"],
                        )
                    )
                continue
            logger.warning(
                "Edeka %s (%.2f EUR): keine passende Rechnungsauswertung in Agenda – "
                "Final-Split ohne Beträge für WE 19%%/Reinigung.",
                datum,
                gesamt,
            )

        # Bereits gesplittete Darlehenszeilen: Text/BU beibehalten
        if skip_map:
            output_rows.append(
                _row(
                    umsatz=gesamt,
                    bu=pre_bu,
                    datum_val=datum,
                    text_val=text,
                    skip_mapping=True,
                )
            )
            continue

        key = (datum, gesamt)
        if key in agenda_by_key:
            m = agenda_by_key[key]
            output_rows.append(
                _row(
                    umsatz=gesamt,
                    bu=m["BU Gkto"],
                    datum_val=datum,
                    text_val=m["Buchungstext"],
                )
            )
        else:
            output_rows.append(
                _row(
                    umsatz=gesamt,
                    bu="",
                    datum_val=datum,
                    text_val=kuerze_stripe_text(text, datum),
                )
            )

    return output_rows
