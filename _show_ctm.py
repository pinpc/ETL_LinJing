import sys
sys.path.insert(0, r'C:\temp_cursor\LinJing\03_Coding\ETL_LinJing\Restaurant')

from etl_platform.bank.dog_bank_etl.kspark_parser import parse_pdf
from etl_platform.bank.dog_bank_etl.runner import (
    _lookup_rule, _extract_beleg1, load_tenant_config,
    _build_buchungstext_kurz, _build_buchungstext_full,
)

cfg = load_tenant_config(
    r'C:\temp_cursor\LinJing\03_Coding\ETL_LinJing\Restaurant\tenants\ctm'
)
txs = parse_pdf(
    r'C:\temp_cursor\DOG\2026\CTM\Fibu 04 2026\Kontoauszüge\Konto_0015171704-Auszug_2026_0004.PDF'
)

print(f"Buchungen: {len(txs)}\n")
print(f"{'Datum':<12} {'BU Gkto':<8}  {'Final (kurz)':<45}  Kontoauszug (1. Zeile)")
print("-" * 120)
for tx in txs:
    rule = _lookup_rule(tx, cfg.rules)
    kurz = _build_buchungstext_kurz(tx, rule)
    full_first = _build_buchungstext_full(tx).split("\n")[0][:55]
    gkto = rule.gegenkonto if rule else "???"
    d = tx.datum.strftime("%d.%m.%Y")
    print(f"{d:<12} {gkto:<8}  {kurz:<45}  {full_first}")
