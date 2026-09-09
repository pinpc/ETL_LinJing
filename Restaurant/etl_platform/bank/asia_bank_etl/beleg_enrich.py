"""Bankzeilen aus Beleg-PDFs anreichern (Produktkürzel / BU), ohne Betrags-Hardcoding."""

from __future__ import annotations

import logging
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_AMOUNT_TOLERANCE = 0.02
_EURO = re.compile(r"(-?\d{1,3}(?:\.\d{3})+,\d{2}|-?\d+,\d{2})")


def _norm_name(name: str) -> str:
    nfkd = unicodedata.normalize("NFKD", name)
    return "".join(c for c in nfkd if not unicodedata.combining(c)).casefold()


def _parse_euro_token(token: str) -> float:
    return float(token.replace(".", "").replace(",", "."))


def _pdf_text_fast(path: Path) -> str:
    try:
        from pypdf import PdfReader
    except ImportError:
        return ""
    try:
        reader = PdfReader(str(path))
        return "\n".join((page.extract_text() or "") for page in reader.pages)
    except Exception as exc:  # noqa: BLE001
        logger.debug("Beleg %s: Textlesen fehlgeschlagen (%s)", path.name, exc)
        return ""


def _amounts_from_text(text: str) -> list[float]:
    return [_parse_euro_token(m.group(1)) for m in _EURO.finditer(text)]


@dataclass(frozen=True)
class BelegHint:
    path: Path
    amount: float
    bu_gkto: str
    buchungstext: str


def _hint_from_filename(path: Path, amount: float) -> BelegHint | None:
    stem = path.stem
    # drop leading index like ``05 `` / ``12a ``
    stem_clean = re.sub(r"^\d+[a-z]?\s+", "", stem, flags=re.I).strip()
    key = _norm_name(stem_clean)

    if "pepita" in key:
        return BelegHint(path, amount, "904985", "PEPITA WEBSHOP 3 x Standventilator weiss")
    if "bottcher" in key or "boettcher" in key:
        return BelegHint(path, amount, "904985", "BOETTCHER AG Reiskocher Bartscher")
    if "buerostuhl" in key or "burostuhl" in key:
        bu = "904980" if "songmics" in key else "904985"
        return BelegHint(path, amount, bu, "AMAZON Bürostuhl")
    if "rollwagen" in key:
        return BelegHint(path, amount, "904985", "AMAZON Rollwagen")
    if "eierkocher" in key:
        return BelegHint(path, amount, "904985", "AMAZON Eierkocher")
    if key.startswith("o2") or "telefonica" in key:
        return BelegHint(path, amount, "904925", "Telefonica Mobil")
    if "hiseas" in key:
        return BelegHint(path, amount, "1360", "HISEAS von Kasse")
    if "great line" in key:
        return BelegHint(path, amount, "1360", "GREAT LINE OU von Kasse")
    if "knittel" in key:
        return BelegHint(path, amount, "3106", "Knittel GmbH Essensreste Entsorgung")
    return None


def _best_amount_for_hint(amounts: list[float], path: Path) -> float | None:
    """Wählt den Beleg-Gesamtbetrag: bevorzugt Brutto-/Gesamt-Nähe, sonst größten Betrag."""
    if not amounts:
        return None
    abs_vals = [round(abs(a), 2) for a in amounts if abs(a) > 0.009]
    if not abs_vals:
        return None
    # Häufig steht der Rechnungsbetrag mehrfach; Mode der größten sinnvollen Werte.
    from collections import Counter

    counts = Counter(abs_vals)
    # Pepita o.ä.: Betrag der am häufigsten vorkommt und > 1
    candidates = [(c, v) for v, c in counts.items() if v >= 1.0]
    if candidates:
        candidates.sort(key=lambda t: (t[0], t[1]), reverse=True)
        return candidates[0][1]
    return max(abs_vals)


def scan_beleg_hints(source_dir: str | Path) -> list[BelegHint]:
    root = Path(source_dir)
    if not root.is_dir():
        return []
    hints: list[BelegHint] = []
    for path in sorted(root.glob("*.pdf")):
        if _norm_name(path.name).startswith("01b ") or "kontoauszug" in _norm_name(path.name):
            continue
        text = _pdf_text_fast(path)
        amounts = _amounts_from_text(text)
        amount = _best_amount_for_hint(amounts, path)
        if amount is None:
            continue
        hint = _hint_from_filename(path, amount)
        if hint is not None:
            hints.append(hint)
    if hints:
        logger.info("Beleg-Anreicherung: %s Hinweis(e) aus %s", len(hints), root)
    return hints


def _amount_matches_pdf(umsatz: float, path: Path) -> bool:
    text = _pdf_text_fast(path)
    amounts = {round(abs(a), 2) for a in _amounts_from_text(text)}
    return any(abs(a - umsatz) <= _AMOUNT_TOLERANCE for a in amounts)


def enrich_rows_from_belege(rows: list[dict[str, Any]], source_dir: str | Path) -> int:
    """
    Setzt BU/Kürzel für Karten-/Belegzeilen, wenn |Umsatz| zu einem Beleg-PDF passt.
    Überschreibt keine Zeilen mit ``_skip_buchung_mapping``.
    """
    root = Path(source_dir)
    if not root.is_dir():
        return 0

    # Alle relevanten Beleg-PDFs (auch wenn „bester“ Betrag nicht der Bankbetrag ist)
    beleg_paths: list[tuple[Path, BelegHint]] = []
    for path in sorted(root.glob("*.pdf")):
        if _norm_name(path.name).startswith("01b ") or "kontoauszug" in _norm_name(path.name):
            continue
        # amount nur Platzhalter; Match erfolgt über PDF-Inhalt
        hint = _hint_from_filename(path, 0.0)
        if hint is not None:
            beleg_paths.append((path, hint))

    if not beleg_paths:
        return 0

    used: set[Path] = set()
    n = 0
    for row in rows:
        if row.get("_skip_buchung_mapping"):
            continue
        try:
            umsatz = round(abs(float(row.get("Umsatz Euro") or 0)), 2)
        except (TypeError, ValueError):
            continue
        if umsatz <= 0:
            continue
        text = str(row.get("Buchungstext") or "")
        text_key = _norm_name(text)
        # Nur anreichern wenn noch Rohtext / generisches Amazon / HISEAS-Fehlzuordnung.
        generic = (
            "amazon we 19" in text_key
            or "pepita" in text_key
            or "boettcher" in text_key
            or "bottcher" in text_key
            or text_key.startswith("hiseas")
            or "great line" in text_key
            or "knittel" in text_key
            or "telefonica" in text_key
            or "debitmastercard" in text_key
            or "debitk." in text_key
            or not str(row.get("BU Gkto") or "").strip()
            or "www.amazon" in text_key
            or text_key.startswith("amazon")
        )
        if not generic and "amazon" not in text_key:
            continue

        for path, hint in beleg_paths:
            if path in used:
                continue
            if not _amount_matches_pdf(umsatz, path):
                continue
            # Dateiname muss zur Bankzeile passen (Amazon↔Amazon, Pepita↔Pepita, …)
            if "amazon" in text_key and "amazon" not in _norm_name(hint.buchungstext) and "amazon" not in _norm_name(path.name):
                # Amazon-Debit nur mit Amazon-/Produktbelegen
                if not any(
                    k in _norm_name(path.name)
                    for k in ("buerostuhl", "burostuhl", "rollwagen", "eierkocher", "amazon")
                ):
                    continue
            if "pepita" in text_key and "pepita" not in _norm_name(path.name):
                continue
            if ("boettcher" in text_key or "bottcher" in text_key) and not (
                "bottcher" in _norm_name(path.name) or "boettcher" in _norm_name(path.name)
            ):
                continue

            label = hint.buchungstext
            if hint.buchungstext == "Telefonica Mobil":
                from .buchungstext_mapping import _kuerzel_mit_datum

                pdf_txt = _pdf_text_fast(path)
                # Rechnungsmonat oft in „ZahlungLastschrift-DD.MM.YYYY“, nicht Buchungsdatum
                mon_src = pdf_txt or text
                m_pay = re.search(
                    r"Lastschrift\s*-\s*(\d{2})\.(\d{2})\.(\d{4})",
                    mon_src,
                    flags=re.I,
                )
                if m_pay:
                    mon_src = f"BEITRAG {m_pay.group(2)}{m_pay.group(3)[2:]}"
                label = _kuerzel_mit_datum(
                    "Telefonica Mobil mm yyyy",
                    mon_src,
                    fallback_datum=str(row.get("Datum") or ""),
                )
            elif hint.buchungstext.startswith("Knittel GmbH Essensreste"):
                from .buchungstext_mapping import _kuerzel_mit_datum

                pdf_txt = _pdf_text_fast(path)
                label = _kuerzel_mit_datum(
                    "Knittel GmbH Essensreste Entsorgung mm yyyy",
                    pdf_txt or text,
                    fallback_datum=str(row.get("Datum") or ""),
                )
            row["BU Gkto"] = hint.bu_gkto
            row["Buchungstext"] = label
            used.add(path)
            n += 1
            break
    if n:
        logger.info("Beleg-Anreicherung: %s Zeile(n) angepasst", n)
    return n
