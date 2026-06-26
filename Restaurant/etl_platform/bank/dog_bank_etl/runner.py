"""DOG-Bank ETL Runner: Konfiguration laden → PDFs parsen → Excel schreiben."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from pathlib import Path

import yaml

from .excel_export import ExportRow, write_excel
from .invoice_lookup import _parse_german_decimal, lookup_invoice
from .kspark_parser import KskTransaction, parse_directory

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Konfigurationsmodell
# ---------------------------------------------------------------------------

@dataclass
class FixedSplitRow:
    """Feste Aufteilung einer Buchung: ein Eintrag im Final-Sheet.

    Umsatz-Quelle (Priorität):
      amount_regex  → Betrag(e) aus Buchungstext extrahieren (Regex-Gruppe 1, summiert)
      use_tx_betrag → echter Bankbetrag (Display-Split, nur Zeile 1)
      betrag=None   → leere Umsatz-Zelle (Display-Split, Folgezeilen)
    """
    gegenkonto: str
    kuerzel: str
    use_tx_betrag: bool = True
    betrag: Decimal | None = None
    amount_regex: list[str] = field(default_factory=list)
    beleg1: str = ""
    no_prefix: bool = False


@dataclass
class BuchungstextRule:
    """Eine Zeile aus buchungstext.yaml."""
    pattern: re.Pattern[str]
    gegenkonto: str
    kuerzel: str              # Anzeigename / Kürzel im Buchungstext (optional)
    beleg1: str | None = None # None = auto, "" = leer, "~auszug" = Auszugnummer
    no_prefix: bool = False   # True: kein ZA-/ZE-Präfix im Final-Sheet
    split_re: bool = False    # True: RE NNN/YYYY-Nummern als separate Final-Zeilen
    invoice_dir: Path | None = None  # Verzeichnis für Ausgangsrechnungs-PDFs
    fixed_split: list[FixedSplitRow] = field(default_factory=list)


@dataclass
class DogTenantConfig:
    tenant_id: str
    display_name: str
    konto_nr: str                        # Kontonummer (Spalte 'Konto')
    source_dir: Path
    output_path: Path
    extra_source_dirs: list[Path] = field(default_factory=list)
    rules: list[BuchungstextRule] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Config laden
# ---------------------------------------------------------------------------

_RE_TEUR = re.compile(r"(\d+)\s*TEUR", re.IGNORECASE)


def _parse_fixed_split_entry(fs: dict) -> FixedSplitRow:
    """Parst einen fixed_split-Eintrag aus buchungstext.yaml."""
    amount_regex_raw = fs.get("amount_regex")
    if amount_regex_raw:
        amount_regex = (
            [str(amount_regex_raw)]
            if isinstance(amount_regex_raw, str)
            else [str(p) for p in amount_regex_raw]
        )
        return FixedSplitRow(
            gegenkonto=str(fs.get("gegenkonto", "")),
            kuerzel=str(fs.get("kuerzel", "")),
            use_tx_betrag=False,
            betrag=None,
            amount_regex=amount_regex,
            beleg1=str(fs.get("beleg1", "")),
            no_prefix=bool(fs.get("no_prefix", False)),
        )
    betrag_raw = fs.get("betrag", "~tx")
    if betrag_raw == "~tx" or (betrag_raw is None and "betrag" not in fs):
        use_tx, betrag_val = True, None
    elif betrag_raw is None or str(betrag_raw).strip() == "":
        use_tx, betrag_val = False, None
    else:
        use_tx, betrag_val = False, Decimal(str(betrag_raw))
    return FixedSplitRow(
        gegenkonto=str(fs.get("gegenkonto", "")),
        kuerzel=str(fs.get("kuerzel", "")),
        use_tx_betrag=use_tx,
        betrag=betrag_val,
        beleg1=str(fs.get("beleg1", "")),
        no_prefix=bool(fs.get("no_prefix", False)),
    )


def _load_rules(buchungstext_yaml: Path) -> list[BuchungstextRule]:
    if not buchungstext_yaml.exists():
        return []
    raw = yaml.safe_load(buchungstext_yaml.read_text(encoding="utf-8")) or {}
    rules: list[BuchungstextRule] = []
    for entry in raw.get("rules", []):
        pattern_str = entry.get("pattern", "")
        if not pattern_str:
            continue
        beleg1_val = entry.get("beleg1", None)
        invoice_dir_raw = entry.get("invoice_dir")
        fixed_split = [_parse_fixed_split_entry(fs) for fs in entry.get("fixed_split", [])]
        rules.append(BuchungstextRule(
            pattern=re.compile(pattern_str, re.IGNORECASE | re.DOTALL),
            gegenkonto=str(entry.get("gegenkonto", "")),
            kuerzel=str(entry.get("kuerzel", "")),
            beleg1=str(beleg1_val) if beleg1_val is not None else None,
            no_prefix=bool(entry.get("no_prefix", False)),
            split_re=bool(entry.get("split_re", False)),
            invoice_dir=Path(invoice_dir_raw) if invoice_dir_raw else None,
            fixed_split=fixed_split,
        ))
    return rules


def load_tenant_config(tenant_dir: str | Path) -> DogTenantConfig:
    """Lädt tenant_config.yaml (+ optionale tenant_local.yaml) aus tenant_dir."""
    tenant_dir = Path(tenant_dir)
    cfg_file = tenant_dir / "tenant_config.yaml"
    local_file = tenant_dir / "tenant_local.yaml"

    cfg = yaml.safe_load(cfg_file.read_text(encoding="utf-8"))
    if local_file.exists():
        local = yaml.safe_load(local_file.read_text(encoding="utf-8")) or {}
        cfg.update({k: v for k, v in local.items() if v is not None})

    rules = _load_rules(tenant_dir / "buchungstext.yaml")

    extra_dirs = [
        Path(d) for d in cfg.get("extra_source_dirs", [])
    ]

    return DogTenantConfig(
        tenant_id=tenant_dir.name,
        display_name=cfg.get("display_name", tenant_dir.name),
        konto_nr=str(cfg.get("konto_nr", "1200")),
        source_dir=Path(cfg["source_dir"]),
        output_path=Path(cfg["output_path"]),
        extra_source_dirs=extra_dirs,
        rules=rules,
    )


# ---------------------------------------------------------------------------
# Gegenkonto-Lookup und Buchungstext-Aufbereitung
# ---------------------------------------------------------------------------

def _extract_amount_from_text(text: str, patterns: list[str]) -> Decimal | None:
    """Summiert Beträge aus Buchungstext (Regex-Gruppe 1 je Pattern, oder TEUR-Muster)."""
    total = Decimal("0")
    found = False
    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if not m:
            continue
        teur_m = _RE_TEUR.search(m.group(0))
        if teur_m:
            total += Decimal(teur_m.group(1)) * 1000
        elif m.lastindex:
            total += _parse_german_decimal(m.group(1))
        found = True
    return total if found else None


def _fixed_split_umsatz(fs: FixedSplitRow, tx: KskTransaction) -> Decimal | None:
    """Ermittelt Umsatz für eine fixed_split-Zeile."""
    if fs.amount_regex:
        amt = _extract_amount_from_text(tx.buchungstext, fs.amount_regex)
        if amt is None:
            return None
        sign = Decimal(-1) if tx.betrag < 0 else Decimal(1)
        return sign * amt
    if fs.use_tx_betrag:
        return tx.betrag
    return fs.betrag


def _row_kurz(tx: KskTransaction, kuerzel: str, no_prefix: bool) -> str:
    prefix = "" if no_prefix else ("ZA-" if tx.betrag < 0 else ("ZE-" if tx.betrag > 0 else ""))
    return (prefix + _resolve_placeholders(kuerzel, tx.buchungstext, fallback_date=tx.datum)).strip()


def _final_row(
    tx: KskTransaction,
    cfg: DogTenantConfig,
    *,
    umsatz: Decimal | None,
    bu_gkto: str,
    beleg1_auto: str,
    beleg1_final: str,
    bt_full: str,
    bt_kurz: str,
) -> ExportRow:
    return ExportRow(
        umsatz=umsatz,
        bu_gkto=bu_gkto,
        beleg1=beleg1_auto,
        beleg1_final=beleg1_final,
        beleg2=tx.auszug_nr,
        datum=tx.datum,
        konto=cfg.konto_nr,
        buchungstext=bt_full,
        buchungstext_kurz=bt_kurz,
        skonto_euro=Decimal("0"),
    )


def _apply_fixed_split(
    rule: BuchungstextRule,
    tx: KskTransaction,
    cfg: DogTenantConfig,
    beleg1_auto: str,
    beleg1_final: str,
    bt_full: str,
) -> list[ExportRow] | None:
    """Gibt Final-Zeilen zurück, oder None wenn Split fehlschlägt."""
    split_rows: list[tuple[FixedSplitRow, Decimal | None]] = []
    for fs in rule.fixed_split:
        row_umsatz = _fixed_split_umsatz(fs, tx)
        if fs.amount_regex and row_umsatz is None:
            logger.warning(
                "[%s] Split übersprungen – Betrag nicht im Text: %s",
                cfg.display_name, fs.amount_regex,
            )
            return None
        split_rows.append((fs, row_umsatz))
    return [
        _final_row(
            tx, cfg,
            umsatz=row_umsatz,
            bu_gkto=fs.gegenkonto,
            beleg1_auto=beleg1_auto,
            beleg1_final=fs.beleg1 if fs.beleg1 else beleg1_final,
            bt_full=bt_full,
            bt_kurz=_row_kurz(tx, fs.kuerzel, fs.no_prefix),
        )
        for fs, row_umsatz in split_rows
    ]


def _apply_split_re(
    rule: BuchungstextRule,
    tx: KskTransaction,
    cfg: DogTenantConfig,
    beleg1_auto: str,
    bt_full: str,
    bt_kurz: str,
) -> list[ExportRow] | None:
    """RE/JJJJ-NNN-Split via Rechnungs-PDFs. None = nicht splitten."""
    split_refs = _extract_split_refs(tx.buchungstext)
    if not split_refs or not rule.invoice_dir:
        return None
    sign = Decimal(1) if tx.betrag >= 0 else Decimal(-1)
    resolved = [(ref, *lookup_invoice(ref, rule.invoice_dir)) for ref in split_refs]
    missing = [ref for ref, amt, _ in resolved if not amt]
    if missing:
        logger.warning(
            "[%s] Split übersprungen – Rechnungen nicht gefunden: %s",
            cfg.display_name, ", ".join(missing),
        )
        return None
    return [
        _final_row(
            tx, cfg,
            umsatz=sign * inv_betrag,
            bu_gkto=rule.gegenkonto,
            beleg1_auto=beleg1_auto,
            beleg1_final=ref,
            bt_full=bt_full,
            bt_kurz=bt_kurz,
        )
        for ref, inv_betrag, _ in resolved
    ]


def _lookup_rule(tx: KskTransaction, rules: list[BuchungstextRule]) -> BuchungstextRule | None:
    for rule in rules:
        if rule.pattern.search(tx.buchungstext):
            return rule
    return None


# Datum-Extraktion aus Buchungstext für Platzhalter {MM.YYYY}
_RE_DATE_IN_TEXT = re.compile(r"\b(\d{2})\.(\d{2})\.(\d{4})\b")


_RE_PDF_DATE_SPLIT = re.compile(r"(\d{2}\.\d)\s+(\d\.20\d{2})")


def _normalize_dates(text: str) -> str:
    """Repariert PDF-Artefakte wie '01.0 4.2026' → '01.04.2026'."""
    return _RE_PDF_DATE_SPLIT.sub(r"\1\2", text)


_DATE_PLACEHOLDERS = ("{MM.YYYY}", "{MM YYYY}", "{YYYY MM}", "{MM}", "{YYYY}")

_RE_BEITRAG_MMYY = re.compile(r"BEITRAG\s+(\d{2})(\d{2})-\d{4}", re.IGNORECASE)
_RE_MON_ABBR = re.compile(
    r"\b(JAN|FEB|MÄR|MAR|APR|MAI|JUN|JUL|AUG|SEP|OKT|NOV|DEZ)\.(\d{2})\b",
    re.IGNORECASE,
)
_MON_ABBR_TO_MM = {
    "JAN": "01", "FEB": "02", "MÄR": "03", "MAR": "03", "APR": "04",
    "MAI": "05", "JUN": "06", "JUL": "07", "AUG": "08", "SEP": "09",
    "OKT": "10", "NOV": "11", "DEZ": "12",
}


def _extract_period_mm_yyyy(buchungstext: str) -> tuple[str, str] | None:
    """Beitrags-/Steuerzeitraum aus Text (z. B. BEITRAG 0326-0326, FEB.26)."""
    m = _RE_BEITRAG_MMYY.search(buchungstext)
    if m:
        return m.group(1), f"20{m.group(2)}"
    m = _RE_MON_ABBR.search(buchungstext)
    if m:
        mm = _MON_ABBR_TO_MM.get(m.group(1).upper().replace("Ä", "A"))
        if mm:
            return mm, f"20{m.group(2)}"
    return None


def _resolve_placeholders(
    kuerzel: str, buchungstext: str, fallback_date: date | None = None
) -> str:
    """Ersetzt Datum-Platzhalter im Kürzel:
    {MM.YYYY} → "04.2026"  |  {MM YYYY} → "04 2026"
    {MM}      → "04"       |  {YYYY}    → "2026"
    Datum-Quelle: Beitrags-/Steuerzeitraum, dann DD.MM.YYYY, Fallback: fallback_date.
    """
    if not any(ph in kuerzel for ph in _DATE_PLACEHOLDERS):
        return kuerzel
    period = _extract_period_mm_yyyy(buchungstext)
    if period:
        mm, yyyy = period
    else:
        normalized = _normalize_dates(buchungstext)
        m = _RE_DATE_IN_TEXT.search(normalized)
        if m:
            mm = m.group(2)
            yyyy = m.group(3)
        elif fallback_date:
            mm = f"{fallback_date.month:02d}"
            yyyy = str(fallback_date.year)
        else:
            mm = yyyy = ""
    return (
        kuerzel
        .replace("{MM.YYYY}", f"{mm}.{yyyy}")
        .replace("{MM YYYY}", f"{mm} {yyyy}")
        .replace("{YYYY MM}", f"{yyyy} {mm}")
        .replace("{MM}", mm)
        .replace("{YYYY}", yyyy)
    ).strip()


# Split-Referenz-Extraktion: RE NNN/YYYY  oder  JJJJ-NNN[+NNN…]
_RE_SPLIT_AFTER_RE  = re.compile(r"\bRE\b(.*)", re.DOTALL | re.IGNORECASE)
_RE_SPLIT_NNN_YYYY  = re.compile(r"\b(\d{3}/\d{4})\b")    # 006/2026
# Erkennt "2026-008" allein oder "2026-008+011" (mehrere mit gemeinsamem Jahres-Prefix)
_RE_SPLIT_JJJJ_NNN  = re.compile(r"\b(20\d{2})-(\d{3})((?:\+\d{3})*)\b")


def _extract_split_refs(buchungstext: str) -> list[str]:
    """Gibt alle Split-Rechnungsnummern zurück.
    Erkennt NNN/YYYY (nach 'RE') und JJJJ-NNN (z.B. 2026-008 oder 2026-008+011)."""
    # RE NNN/YYYY: nur nach dem Schlüsselwort "RE" suchen
    m = _RE_SPLIT_AFTER_RE.search(buchungstext)
    if m:
        refs = _RE_SPLIT_NNN_YYYY.findall(m.group(1))
        if refs:
            return refs
    # JJJJ-NNN[+NNN…]: Jahres-Prefix + erste Nummer + optionale Folgennummern
    refs: list[str] = []
    for m in _RE_SPLIT_JJJJ_NNN.finditer(buchungstext):
        year, first, rest = m.group(1), m.group(2), m.group(3)
        refs.append(f"{year}-{first}")
        for extra in re.findall(r"\d{3}", rest):
            refs.append(f"{year}-{extra}")
    return refs


# Beleg1-Extraktion – Prioritätsreihenfolge:
# 1. RE NNN/YYYY        → "006/2026"
# 2. JJJJ-NNN           → "2026-008"  (Ping Zhou, Jahresformat)
# 3. ReNr/RNR/Re-Nr     → alphanumerische Rechnungsnummern ("AR26-391", "2026-008")
# 4. RGN (Vodafone)     → Rechnungsnummer aus "RGN 00229874854 1"
# 5. RG                 → "RG20260005566710"
# 6. DRP                → sechsstellige KSK-Referenz
# 7. Kd.-Nr./KdNr.      → Kundennummer
# 8. erste lange Zahl   → Fallback (6–15 Stellen)
_RE_BELEG_RE       = re.compile(r"\bRE\s+(\d+/\d+)", re.IGNORECASE)
_RE_BELEG_YEAR_NUM = re.compile(r"\b(20\d{2}-\d{3})\b")
_RE_BELEG_RENR     = re.compile(
    r"\b(?:ReNr\.?|Re-Nr\.?|RNR|Rechnungsnummer)\s+(?:RE-|AR-)?([^\s+,;]+\d)",
    re.IGNORECASE,
)
_RE_BELEG_RGN      = re.compile(r"\bRGN\s+0*(\d+)\s+(\d)\b", re.IGNORECASE)
_RE_BELEG_RG       = re.compile(r"\bRG(20\d{10})\b", re.IGNORECASE)
_RE_BELEG_DRP      = re.compile(r"\bDRP\s+(\d{6,12})")
_RE_BELEG_KDNR     = re.compile(r"\bKd\.?-?Nr\.?\s*(\d{5,})", re.IGNORECASE)
_RE_BELEG_REF      = re.compile(r"\b(\d{6,15})\b")


def _extract_beleg1(buchungstext: str) -> str:
    """Extrahiert die Belegnummer aus dem Buchungstext (Prioritätsreihenfolge s. o.)."""
    for pat in (_RE_BELEG_RE, _RE_BELEG_YEAR_NUM, _RE_BELEG_RENR, _RE_BELEG_DRP, _RE_BELEG_KDNR):
        if m := pat.search(buchungstext):
            return m.group(1)
    if m := _RE_BELEG_RGN.search(buchungstext):
        return str(int(m.group(1))) + m.group(2)
    if m := _RE_BELEG_RG.search(buchungstext):
        return m.group(1)
    if m := _RE_BELEG_REF.search(buchungstext):
        return str(int(m.group(1)))
    return ""


_RE_VORGANG_PREFIX = re.compile(
    r"^(GutschriftÜberweisung|Gutschrift\s+Überweisung|Gutschrift|"
    r"Überweisung\s+online|Überweisung|Lastschrift|Dauerauftrag\s+online|"
    r"Dauerauftrag|Entgeltabrechnung(?:\s*/\s*Wert:\s*\d{2}\.\d{2}\.\d{4})?|Rechnung|"
    r"Darlehensrate|Kartenzahlung|Einzahlung|Auszahlung)\s*",
    re.IGNORECASE,
)


def _build_buchungstext_full(tx: KskTransaction) -> str:
    """Kontoauszug-Sheet: Vorgangstyp-Präfix entfernen, restlichen Text mehrzeilig."""
    return _RE_VORGANG_PREFIX.sub("", tx.buchungstext).strip()


def _build_buchungstext_kurz(tx: KskTransaction, rule: BuchungstextRule | None) -> str:
    """Final-Sheet: (ZA/ZE-)Präfix + Kürzel aus Regel (einzeilig)."""
    if rule and rule.kuerzel:
        return _row_kurz(tx, rule.kuerzel, rule.no_prefix)
    prefix = "ZA-" if tx.betrag < 0 else ("ZE-" if tx.betrag > 0 else "")
    first_line = _build_buchungstext_full(tx).split("\n")[0].strip()[:40]
    return (prefix + first_line).strip()


# ---------------------------------------------------------------------------
# Hauptfunktion
# ---------------------------------------------------------------------------

def run(tenant_dir: str | Path) -> Path:
    """
    Vollständiger Lauf für einen DOG-Tenant:
    1. Config + Regeln laden
    2. Alle PDFs aus source_dir parsen
    3. Gegenkonto per Regel zuordnen
    4. Excel schreiben
    Gibt den Pfad zum erzeugten Excel zurück.
    """
    cfg = load_tenant_config(tenant_dir)

    logger.info("[%s] PDFs lesen aus: %s", cfg.display_name, cfg.source_dir)
    transactions: list[KskTransaction] = parse_directory(cfg.source_dir)
    for extra_dir in cfg.extra_source_dirs:
        if extra_dir.exists():
            extra = parse_directory(extra_dir)
            logger.info("[%s] %d zusätzliche Buchungen aus: %s", cfg.display_name, len(extra), extra_dir)
            transactions.extend(extra)
        else:
            logger.warning("[%s] extra_source_dir nicht gefunden: %s", cfg.display_name, extra_dir)
    transactions.sort(key=lambda t: t.datum)
    logger.info("[%s] %d Buchungen eingelesen", cfg.display_name, len(transactions))

    konto_rows: list[ExportRow] = []
    final_rows: list[ExportRow] = []
    unmatched: set[str] = set()

    for tx in transactions:
        rule = _lookup_rule(tx, cfg.rules)
        if rule is None:
            unmatched.add(tx.buchungstext[:60])

        beleg1_auto = _extract_beleg1(tx.buchungstext)
        if rule is not None and rule.beleg1 is not None:
            if rule.beleg1 == "~auszug":
                beleg1_final = tx.auszug_nr   # Auszugnummer als Beleg1
            else:
                beleg1_final = rule.beleg1    # explizit aus Config (auch "" möglich)
        else:
            beleg1_final = beleg1_auto
        bt_full = _build_buchungstext_full(tx)
        bt_kurz = _build_buchungstext_kurz(tx, rule)

        # ---- Kontoauszug-Sheet: immer 1:1, unveraendert ----
        konto_rows.append(ExportRow(
            umsatz=tx.betrag,
            bu_gkto=rule.gegenkonto if rule else "",
            beleg1=beleg1_auto,
            beleg1_final=beleg1_final,
            beleg2=tx.auszug_nr,
            datum=tx.datum,
            konto=cfg.konto_nr,
            buchungstext=bt_full,
            buchungstext_kurz=bt_kurz,
            skonto_euro=Decimal("0"),
        ))

        # ---- Final-Sheet: ggf. aufsplitten ----
        if rule and rule.fixed_split:
            split_rows = _apply_fixed_split(
                rule, tx, cfg, beleg1_auto, beleg1_final, bt_full,
            )
            if split_rows:
                final_rows.extend(split_rows)
                continue

        if rule and rule.split_re:
            split_rows = _apply_split_re(
                rule, tx, cfg, beleg1_auto, bt_full, bt_kurz,
            )
            if split_rows:
                final_rows.extend(split_rows)
                continue

        # kein Split → Final-Row identisch mit Kontoauszug-Row
        final_rows.append(konto_rows[-1])

    if unmatched:
        logger.warning(
            "[%s] %d Buchungen ohne Gegenkonto-Zuordnung:\n  %s",
            cfg.display_name,
            len(unmatched),
            "\n  ".join(sorted(unmatched)),
        )

    out = write_excel(konto_rows, cfg.output_path, final_rows=final_rows)
    logger.info("[%s] Excel geschrieben: %s", cfg.display_name, out)
    return out
