$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$input = "C:\temp_cursor\LinJing\01_Asia\Asia Kasse 03.2026\01 allO现金簿导出2026.03\cashbook_china_restaurant_asia__01_03_2026_31_03_2026.xlsx"
$pdfBase = "C:\temp_cursor\LinJing\01_Asia"
$outDir = Join-Path $root "result"
$outFile = Join-Path $outDir "asia_kasse_etl_03_2026.xlsx"

New-Item -ItemType Directory -Force -Path $outDir | Out-Null

python -m asia_kasse_etl --input $input --out $outFile --pdf-base $pdfBase --sheet cashbook
Write-Host "Input:  $input"
Write-Host "PDFs:   $pdfBase"
Write-Host "Output: $outFile"

