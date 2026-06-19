"""DOG-Bank ETL Runner: Konfiguration laden → PDFs parsen → Excel schreiben."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from .excel_export import ExportRow, write_excel
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
    kuerzel: str        # Anzeigename / Kürzel im Buchungstext (optional)


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
        rules.append(BuchungstextRule(
            pattern=re.compile(pattern_str, re.IGNORECASE),
            gegenkonto=str(entry.get("gegenkonto", "")),
            kuerzel=str(entry.get("kuerzel", "")),
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
# Gegenkonto-Lookup
# ---------------------------------------------------------------------------

def _lookup_gegenkonto(tx: KskTransaction, rules: list[BuchungstextRule]) -> str:
    for rule in rules:
        if rule.pattern.search(tx.buchungstext):
            return rule.gegenkonto
    return ""


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

    rows: list[ExportRow] = []
    unmatched: set[str] = set()
    for tx in transactions:
        gegenkonto = _lookup_gegenkonto(tx, cfg.rules)
        if not gegenkonto:
            unmatched.add(tx.buchungstext[:60])
        rows.append(ExportRow(
            datum=tx.datum,
            betrag=tx.betrag,
            gegenkonto=gegenkonto,
            konto=cfg.konto_nr,
            buchungstext=tx.buchungstext,
        ))

    if unmatched:
        logger.warning(
            "[%s] %d Buchungen ohne Gegenkonto-Zuordnung:\n  %s",
            cfg.display_name,
            len(unmatched),
            "\n  ".join(sorted(unmatched)),
        )

    out = write_excel(rows, cfg.output_path)
    logger.info("[%s] Excel geschrieben: %s", cfg.display_name, out)
    return out
