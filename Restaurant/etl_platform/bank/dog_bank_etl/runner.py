"""DOG-Bank ETL Runner: Konfiguration laden → PDFs parsen → Excel schreiben."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path

import yaml

from .excel_export import ExportRow, write_excel
from .invoice_lookup import lookup_invoice
from .kspark_parser import KskTransaction, parse_directory

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Konfigurationsmodell
# ---------------------------------------------------------------------------

@dataclass
class BuchungstextRule:
    """Eine Zeile aus buchungstext.yaml."""
    pattern: re.Pattern[str]
    gegenkonto: str
    kuerzel: str              # Anzeigename / Kürzel im Buchungstext (optional)
    beleg1: str | None = None # None = auto-extrahieren, "" = leer erzwingen
    split_re: bool = False    # True: RE NNN/YYYY-Nummern als separate Final-Zeilen
    invoice_dir: Path | None = None  # Verzeichnis für Ausgangsrechnungs-PDFs


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
        rules.append(BuchungstextRule(
            pattern=re.compile(pattern_str, re.IGNORECASE),
            gegenkonto=str(entry.get("gegenkonto", "")),
            kuerzel=str(entry.get("kuerzel", "")),
            beleg1=str(beleg1_val) if beleg1_val is not None else None,
            split_re=bool(entry.get("split_re", False)),
            invoice_dir=Path(invoice_dir_raw) if invoice_dir_raw else None,
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


def _resolve_placeholders(kuerzel: str, buchungstext: str) -> str:
    """Ersetzt {MM.YYYY} im Kürzel durch das erste Datum aus dem Buchungstext."""
    if "{MM.YYYY}" not in kuerzel:
        return kuerzel
    normalized = _normalize_dates(buchungstext)
    m = _RE_DATE_IN_TEXT.search(normalized)
    if m:
        mm_yyyy = f"{m.group(2)}.{m.group(3)}"   # MM.YYYY
    else:
        mm_yyyy = ""
    return kuerzel.replace("{MM.YYYY}", mm_yyyy).strip()


# RE-Split: alle NNN/YYYY nach "RE" extrahieren (auch über Zeilenumbruch hinweg)
_RE_SPLIT_AFTER_RE = re.compile(r"\bRE\b(.*)", re.DOTALL | re.IGNORECASE)
_RE_SPLIT_INV_NUM = re.compile(r"\b(\d{3}/\d{4})\b")


def _extract_re_invoice_refs(buchungstext: str) -> list[str]:
    """Gibt alle Rechnungsnummern (NNN/YYYY) nach 'RE' zurück (z. B. ['006/2026', '007/2026'])."""
    m = _RE_SPLIT_AFTER_RE.search(buchungstext)
    if not m:
        return []
    return _RE_SPLIT_INV_NUM.findall(m.group(1))


# Beleg1-Extraktion: bevorzugt RE-Nummer, dann DRP-Referenz, dann erste sinnvolle Zahl
_RE_BELEG_RE = re.compile(r"\bRE\s+(\d+/\d+)", re.IGNORECASE)
_RE_BELEG_DRP = re.compile(r"\bDRP\s+(\d{6,12})")
_RE_BELEG_REF = re.compile(r"\b(\d{6,15})\b")   # erste lange Zahl


def _extract_beleg1(buchungstext: str) -> str:
    """Extrahiert Belegnummer aus dem Buchungstext."""
    m = _RE_BELEG_RE.search(buchungstext)
    if m:
        return m.group(1)
    m = _RE_BELEG_DRP.search(buchungstext)
    if m:
        return m.group(1)
    m = _RE_BELEG_REF.search(buchungstext)
    if m:
        return str(int(m.group(1)))   # führende Nullen entfernen
    return ""


_RE_VORGANG_PREFIX = re.compile(
    r"^(GutschriftÜberweisung|Gutschrift\s+Überweisung|Gutschrift|"
    r"Überweisung\s+online|Überweisung|Lastschrift|Dauerauftrag\s+online|"
    r"Dauerauftrag|Entgeltabrechnung(?:\s*/\s*Wert:[^)]+)?|Rechnung|"
    r"Darlehensrate|Kartenzahlung|Einzahlung|Auszahlung)\s*",
    re.IGNORECASE,
)


def _build_buchungstext_full(tx: KskTransaction) -> str:
    """Kontoauszug-Sheet: Vorgangstyp-Präfix entfernen, restlichen Text mehrzeilig."""
    return _RE_VORGANG_PREFIX.sub("", tx.buchungstext).strip()


def _build_buchungstext_kurz(tx: KskTransaction, rule: BuchungstextRule | None) -> str:
    """Final-Sheet: ZA/ZE-Präfix + Kürzel aus Regel (einzeilig).
    Unterstützt Platzhalter {MM.YYYY} → Datum aus Buchungstext."""
    prefix = "ZA-" if tx.betrag < 0 else ("ZE-" if tx.betrag > 0 else "")
    if rule and rule.kuerzel:
        kuerzel = _resolve_placeholders(rule.kuerzel, tx.buchungstext)
        return prefix + kuerzel
    # Fallback: erste Zeile des bereinigten Textes, max. 40 Zeichen
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
        beleg1_final = rule.beleg1 if (rule is not None and rule.beleg1 is not None) else beleg1_auto
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
        if rule and rule.split_re and rule.invoice_dir:
            split_refs = _extract_re_invoice_refs(tx.buchungstext)
            if split_refs:
                sign = Decimal(1) if tx.betrag >= 0 else Decimal(-1)
                for ref in split_refs:
                    inv_betrag, _ = lookup_invoice(ref, rule.invoice_dir)
                    if not inv_betrag:
                        logger.warning(
                            "[%s] RE-Betrag nicht gefunden für %s in %s",
                            cfg.display_name, ref, rule.invoice_dir,
                        )
                    final_rows.append(ExportRow(
                        umsatz=sign * inv_betrag,
                        bu_gkto=rule.gegenkonto,
                        beleg1=beleg1_auto,
                        beleg1_final=ref,     # Beleg1 = einzelne RE-Nr.
                        beleg2=tx.auszug_nr,
                        datum=tx.datum,       # Buchungsdatum aus Kontoauszug
                        konto=cfg.konto_nr,
                        buchungstext=bt_full,
                        buchungstext_kurz=bt_kurz,
                        skonto_euro=Decimal("0"),
                    ))
                continue  # nicht nochmal als Normal-Zeile eintragen

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
