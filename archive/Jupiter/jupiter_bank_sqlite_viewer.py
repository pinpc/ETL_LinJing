#!/usr/bin/env python3
"""
Liest die SQLite-Datei des Jupiter-Bank-ETL im Browser (nur Standardbibliothek).

Start (eine der Varianten):

  python jupiter_bank_sqlite_viewer.py <pfad_zur.sqlite>

  set JUPITER_BANK_SQLITE=C:\\pfad\\export.sqlite
  python jupiter_bank_sqlite_viewer.py

Browser: http://127.0.0.1:8765/  ·  JSON: /api/konto_jupiter

Nur lokal oder hinter Auth/HTTPS nutzen.
"""

from __future__ import annotations

import json
import os
import sqlite3
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765
TABLE = "konto_jupiter"


def row_to_dict(cur: sqlite3.Cursor, row: sqlite3.Row) -> dict:
    return {k: row[k] for k in row.keys()}


def fetch_all(db_path: str) -> list[dict]:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        cur = conn.execute(
            f"SELECT umsatz_euro, bu_gkto, beleg_1, datum, bank, kost_1, buchungstext "
            f"FROM {TABLE} ORDER BY rowid"
        )
        return [row_to_dict(cur, r) for r in cur.fetchall()]
    finally:
        conn.close()


def html_page(rows: list[dict]) -> bytes:
    th = (
        "<tr><th>Umsatz Euro</th><th>BU Gkto</th><th>Beleg 1</th><th>Datum</th>"
        "<th>Bank</th><th>Kost 1</th><th>Buchungstext</th></tr>"
    )
    body_rows = []
    for r in rows:
        cells = [
            r.get("umsatz_euro"),
            r.get("bu_gkto") or "",
            r.get("beleg_1") or "",
            r.get("datum") or "",
            r.get("bank") or "",
            r.get("kost_1") or "",
            (r.get("buchungstext") or "")
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;"),
        ]
        tds = "".join(f"<td>{c}</td>" for c in cells)
        body_rows.append(f"<tr>{tds}</tr>")
    table = f"<table border='1' cellpadding='6' cellspacing='0'>{th}{''.join(body_rows)}</table>"
    doc = f"""<!DOCTYPE html>
<html lang="de"><head><meta charset="utf-8"><title>{TABLE}</title></head>
<body>
<h1>{TABLE}</h1>
<p>{len(rows)} Zeilen · <a href="/api/konto_jupiter">JSON</a></p>
{table}
</body></html>"""
    return doc.encode("utf-8")


def make_handler(db_path: str):
    class H(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            path = urlparse(self.path).path
            if path == "/api/konto_jupiter":
                try:
                    data = fetch_all(db_path)
                    payload = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
                except Exception as e:
                    self.send_response(500)
                    self.send_header("Content-Type", "text/plain; charset=utf-8")
                    self.end_headers()
                    self.wfile.write(str(e).encode("utf-8"))
                    return
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(payload)
                return
            if path in ("/", "/index.html"):
                try:
                    rows = fetch_all(db_path)
                    body = html_page(rows)
                except Exception as e:
                    self.send_response(500)
                    self.send_header("Content-Type", "text/plain; charset=utf-8")
                    self.end_headers()
                    self.wfile.write(str(e).encode("utf-8"))
                    return
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(body)
                return
            self.send_response(404)
            self.end_headers()

        def log_message(self, format: str, *args) -> None:
            sys.stderr.write("%s - %s\n" % (self.address_string(), format % args))

    return H


def _resolve_db_path() -> str | None:
    if len(sys.argv) > 1:
        return os.path.normpath(sys.argv[1].strip().strip('"'))
    env = os.environ.get("JUPITER_BANK_SQLITE", "").strip().strip('"')
    return os.path.normpath(env) if env else None


def main() -> None:
    db_path = _resolve_db_path()
    if not db_path or not os.path.isfile(db_path):
        print("Keine gültige SQLite-Datei angegeben (Datei fehlt oder Pfad leer).")
        print()
        print("  A) Argument:")
        print("     python jupiter_bank_sqlite_viewer.py C:\\pfad\\export.sqlite")
        print()
        print("  B) Umgebungsvariable (z. B. vor F5 im Terminal oder in launch.json):")
        print("     set JUPITER_BANK_SQLITE=C:\\pfad\\export.sqlite")
        print("     python jupiter_bank_sqlite_viewer.py")
        print()
        print("  C) Cursor/VS Code: Run and Debug → launch.json → \"args\": [\"C:\\\\pfad\\\\export.sqlite\"]")
        sys.exit(1)
    host = os.environ.get("SQLITE_WEB_HOST", DEFAULT_HOST)
    port = int(os.environ.get("SQLITE_WEB_PORT", str(DEFAULT_PORT)))
    server = HTTPServer((host, port), make_handler(db_path))
    print(f"Öffnen: http://{host}:{port}/")
    print(f"JSON:   http://{host}:{port}/api/konto_jupiter")
    print("Beenden: Ctrl+C")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nBeendet.")


if __name__ == "__main__":
    main()
