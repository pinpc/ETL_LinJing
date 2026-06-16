## asia_kasse_etl

Kassen-ETL (Asia): Cashbook + Allopay PDFs -> Excel mit `Buchung`, `Allopay` und `Final`.

### Start

```bash
python -m asia_kasse_etl --help
```

### Typischer Lauf

```bash
python -m asia_kasse_etl --input "<cashbook.xlsx>" --out "<result.xlsx>" --pdf-base "<basisordner>" --sheet cashbook
```

### Beispiel

```powershell
.\scripts\run_sample.ps1
```

### Hinweis

- `--pdf-base` ist optional. Wenn nicht angegeben, wird der Basisordner aus dem Input-Pfad abgeleitet.
- Beim Schreiben in eine geoeffnete Excel-Datei wird automatisch auf einen neuen Dateinamen wie `_new.xlsx` ausgewichen.

