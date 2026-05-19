@echo off
setlocal

REM Start ETL API + open GUI in browser.
set "ROOT_DIR=%~dp0"
cd /d "%ROOT_DIR%"

start "" "http://127.0.0.1:8000/"
echo Starting Restaurant ETL API...
python -m Restaurant.apps.etl_api.main

endlocal
