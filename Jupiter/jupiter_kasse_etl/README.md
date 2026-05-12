## jupiter_kasse_etl

Kassen-ETL (Jupiter): Kassenbuch + Allopay PDFs -> Excel mit `Umsatz`, `Allopay` und `Final`.

### Start

```bash
python -m jupiter_kasse_etl --help
```

### Typischer Lauf

```bash
python -m jupiter_kasse_etl --input "<cashbook.pdf|cashbook.xlsx>" --out "<result.xlsx>" --pdf-base "<basisordner>"
```

### Hinweis

- Ohne Parameter werden die aktuell hinterlegten Jupiter-Standardpfade verwendet.
- Das Kassenbuch kann als PDF oder Excel geliefert werden.
- Wenn die Ziel-Excel geoeffnet ist, wird automatisch auf einen neuen Dateinamen wie `_new.xlsx` ausgewichen.
