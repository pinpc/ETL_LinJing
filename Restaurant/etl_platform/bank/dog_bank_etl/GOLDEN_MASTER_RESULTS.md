# DOG Bank ETL — Golden Master (Fibu 04/2026)

Ausführung:

```powershell
python -m etl_platform.bank.dog_bank_etl.golden_master
```

Baseline-Abweichungen: `golden_master_baselines.py`

| Tenant | Status | Bekannte Abw. | Hinweis |
|--------|--------|---------------|---------|
| **CTM** | OK (Baseline) | 8 | Summe stimmt; Telekom-Split, VL, Massion offen |
| **Ramtel12** | OK (Baseline) | 20 | Display-Split Miete/NK; Telekom/KSK Monat |
| **DOG Holding** | OK (Baseline) | 1 | 17/17 SOLL-Zeilen; Ping Zhou Datum Agenda vs. Bank |

## CTM (8 bekannte Abweichungen)

- Telekom: Umsatz/Datum/Split (SOLL −1219,95 vs. IST −191,11)
- VL 04 2026 / F. Massion 01–04 vs. F. Massion 04 (Beleg1)
- P. Massion Umsatz-Split

## Ramtel12 (20 bekannte Abweichungen)

- Stadtwerke Wasser/Abwasser Display-Split
- Miete D.O.G./Hirotec/systemgruppe/Köhler/Bruchmann: Umsatz nur Zeile 1, NK-Zeile fehlt
- Haftpflichtkasse: Datum ±1 Tag
- Telekom Alarm Pumpe: Monat 03 vs. 04 in Kürzel
- KSK Tilgung: Tippfehler „202 Merklingen“ in SOLL vs. „2026“ in IST

## DOG Holding (1 bekannte Abweichung)

- Ping Zhou: Datum SOLL 27.04. vs. Bank/PDF 28.04.
- 6 EXTRA-Zeilen (29.–30.04.) in `_KNOWN_EXTRA`: Ramtel12, Chen, Massion, Software, EBICS

## Änderungshistorie

| Datum | Änderung |
|-------|----------|
| 2026-06-25 | Baseline nach Code-Optimierung: Entgelt-Fix, Perioden BEK/USt, semantic match DOG Holding, Summe Final=Kontoauszug |
