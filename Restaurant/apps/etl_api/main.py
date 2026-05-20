"""Minimal ETL API with async run jobs."""

from __future__ import annotations

import json
import sqlite3
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs
from uuid import uuid4
from wsgiref.simple_server import make_server

_INDEX_HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Restaurant ETL Runner</title>
  <style>
    body { font-family: Arial, sans-serif; margin: 24px; max-width: 980px; }
    h1 { margin-bottom: 8px; }
    .muted { color: #555; margin-bottom: 20px; }
    .grid { display: grid; grid-template-columns: 180px 1fr; gap: 10px 12px; align-items: center; }
    .input-row { display: flex; gap: 8px; align-items: center; }
    .input-row input { flex: 1; }
    input, select, button, textarea { font: inherit; padding: 6px 8px; }
    textarea { min-height: 180px; width: 100%; }
    .actions { margin-top: 16px; display: flex; gap: 10px; }
    .row { margin-top: 18px; }
    .status { font-weight: 700; }
    .history { margin-top: 18px; border: 1px solid #ccc; border-radius: 6px; padding: 10px; }
    .history-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
    .history-list { max-height: 220px; overflow: auto; border: 1px solid #eee; padding: 6px; }
    .history-item { display: flex; justify-content: space-between; gap: 8px; padding: 6px; border-bottom: 1px solid #f2f2f2; cursor: pointer; }
    .history-item:last-child { border-bottom: none; }
    .status-succeeded { color: #0a7d00; }
    .status-failed { color: #c00000; }
    .status-running { color: #0058c0; }
    .status-queued { color: #8a6d00; }
  </style>
</head>
<body>
  <h1>Restaurant ETL Runner</h1>
  <div class="muted">Run bank or cashbook jobs and poll status.</div>
  <div class="grid">
    <label for="module">Module</label>
    <select id="module">
      <option value="bank">bank</option>
      <option value="cashbook">cashbook</option>
    </select>

    <label for="tenant">Tenant</label>
    <select id="tenant"></select>

    <label for="source">Source</label>
    <div class="input-row">
      <input id="source" placeholder="C:\\path\\to\\source" />
      <button id="browseSourceFileBtn" type="button">Browse File</button>
      <button id="browseSourceDirBtn" type="button">Browse Folder</button>
    </div>

    <label for="output">Output</label>
    <div class="input-row">
      <input id="output" placeholder="C:\\path\\to\\output.xlsx" />
      <button id="browseOutputBtn" type="button">Browse Save</button>
    </div>

    <label for="statementPdf">Statement PDF (bank)</label>
    <input id="statementPdf" placeholder="Optional" />

    <label for="agendaFile">Agenda File (bank)</label>
    <input id="agendaFile" placeholder="Optional" />

    <label for="pdfBaseDir">PDF Base Dir (cashbook)</label>
    <input id="pdfBaseDir" placeholder="Optional" />

    <label for="sheetName">Sheet Name (cashbook)</label>
    <input id="sheetName" placeholder="Optional" />

    <label for="sqliteOutput">SQLite Output</label>
    <input id="sqliteOutput" placeholder="Optional" />

    <label for="excelTitle">Excel Title (bank)</label>
    <input id="excelTitle" placeholder="Optional" />
  </div>

  <div class="actions">
    <button id="startBtn">Start Job</button>
    <button id="pollBtn" type="button">Poll Current Job</button>
  </div>

  <div class="row">Current Job ID: <span id="jobId" class="status">-</span></div>
  <div class="row">Status: <span id="status" class="status">idle</span></div>

  <div class="row">
    <label for="resultBox"><strong>Result / Error</strong></label><br />
    <textarea id="resultBox" readonly></textarea>
  </div>

  <div class="history">
    <div class="history-header">
      <strong>Recent Runs</strong>
      <button id="refreshHistoryBtn" type="button">Refresh History</button>
    </div>
    <div id="historyList" class="history-list"></div>
  </div>

  <script>
    const jobIdEl = document.getElementById("jobId");
    const statusEl = document.getElementById("status");
    const resultBox = document.getElementById("resultBox");
    const historyList = document.getElementById("historyList");
    let currentJobId = "";
    let pollTimer = null;

    function setStatus(text) {
      statusEl.textContent = text;
    }

    function setResult(data) {
      resultBox.value = JSON.stringify(data, null, 2);
    }

    async function loadTenants() {
      try {
        const res = await fetch("/etl/tenants");
        const data = await res.json();
        if (!res.ok) {
          setStatus("tenant_load_failed");
          setResult(data);
          return;
        }
        const tenantSelect = document.getElementById("tenant");
        tenantSelect.innerHTML = "";
        const tenants = Array.isArray(data.tenants) ? data.tenants : [];
        const selectedModule = document.getElementById("module").value;
        for (const tenant of tenants) {
          const supported = Array.isArray(tenant.supported_modules)
            ? tenant.supported_modules
            : ["bank", "cashbook"];
          if (!supported.includes(selectedModule)) {
            continue;
          }
          const option = document.createElement("option");
          option.value = tenant.tenant_id;
          option.textContent = tenant.display_name
            ? `${tenant.tenant_id} (${tenant.display_name})`
            : tenant.tenant_id;
          tenantSelect.appendChild(option);
        }
        if (!tenants.length) {
          const option = document.createElement("option");
          option.value = "";
          option.textContent = "no tenants found";
          tenantSelect.appendChild(option);
        }
      } catch (err) {
        setStatus("tenant_load_error");
        setResult({ error: String(err) });
      }
    }

    function buildPayload() {
      const payload = {
        module: document.getElementById("module").value,
        tenant_id: document.getElementById("tenant").value.trim(),
        source: document.getElementById("source").value.trim(),
        output: document.getElementById("output").value.trim(),
      };
      const optionalFields = [
        ["statement_pdf", "statementPdf"],
        ["agenda_file", "agendaFile"],
        ["pdf_base_dir", "pdfBaseDir"],
        ["sheet_name", "sheetName"],
        ["sqlite_output", "sqliteOutput"],
        ["excel_title", "excelTitle"],
      ];
      for (const [apiKey, domId] of optionalFields) {
        const value = document.getElementById(domId).value.trim();
        if (value) payload[apiKey] = value;
      }
      return payload;
    }

    async function pickPath(endpoint, payload, targetInputId) {
      try {
        const res = await fetch(endpoint, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload || {}),
        });
        const data = await res.json();
        if (!res.ok) {
          setStatus("browse_failed");
          setResult(data);
          return;
        }
        if (data.path) {
          document.getElementById(targetInputId).value = data.path;
        }
      } catch (err) {
        setStatus("browse_error");
        setResult({ error: String(err) });
      }
    }

    async function startJob() {
      const payload = buildPayload();
      setStatus("submitting...");
      setResult({ payload });
      try {
        const res = await fetch("/etl/run", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        const data = await res.json();
        if (!res.ok) {
          setStatus("submit_failed");
          setResult(data);
          return;
        }
        currentJobId = data.job_id;
        jobIdEl.textContent = currentJobId;
        setStatus(data.status || "queued");
        setResult(data);
        startPolling();
      } catch (err) {
        setStatus("submit_error");
        setResult({ error: String(err) });
      }
    }

    async function pollJob() {
      if (!currentJobId) {
        setStatus("no_job");
        return;
      }
      try {
        const res = await fetch(`/etl/run/${currentJobId}`);
        const data = await res.json();
        if (!res.ok) {
          setStatus("poll_failed");
          setResult(data);
          return;
        }
        setStatus(data.status || "unknown");
        setResult(data);
        if (data.status === "succeeded" || data.status === "failed") {
          stopPolling();
        }
      } catch (err) {
        setStatus("poll_error");
        setResult({ error: String(err) });
      }
    }

    function statusClass(status) {
      switch (status) {
        case "succeeded": return "status-succeeded";
        case "failed": return "status-failed";
        case "running": return "status-running";
        case "queued": return "status-queued";
        default: return "";
      }
    }

    async function loadHistory() {
      try {
        const res = await fetch("/etl/runs?limit=30");
        const data = await res.json();
        if (!res.ok) {
          setResult(data);
          return;
        }
        const runs = Array.isArray(data.runs) ? data.runs : [];
        historyList.innerHTML = "";
        if (!runs.length) {
          historyList.innerHTML = "<div class='history-item'>No runs yet.</div>";
          return;
        }
        for (const run of runs) {
          const item = document.createElement("div");
          item.className = "history-item";
          item.innerHTML = `
            <span>${run.module}/${run.tenant_id} - <span class="${statusClass(run.status)}">${run.status}</span></span>
            <span>${(run.created_at_utc || "").replace("T", " ").slice(0, 19)}</span>
          `;
          item.addEventListener("click", async () => {
            currentJobId = run.job_id;
            jobIdEl.textContent = currentJobId;
            await pollJob();
          });
          historyList.appendChild(item);
        }
      } catch (err) {
        setResult({ error: String(err) });
      }
    }

    function startPolling() {
      stopPolling();
      pollTimer = setInterval(pollJob, 1000);
      pollJob();
      loadHistory();
    }

    function stopPolling() {
      if (pollTimer) {
        clearInterval(pollTimer);
        pollTimer = null;
      }
    }

    document.getElementById("startBtn").addEventListener("click", startJob);
    document.getElementById("pollBtn").addEventListener("click", pollJob);
    document.getElementById("refreshHistoryBtn").addEventListener("click", loadHistory);
    document.getElementById("module").addEventListener("change", loadTenants);
    document.getElementById("browseSourceFileBtn").addEventListener("click", () =>
      pickPath("/fs/pick-file", { title: "Select source file" }, "source")
    );
    document.getElementById("browseSourceDirBtn").addEventListener("click", () =>
      pickPath("/fs/pick-dir", { title: "Select source folder" }, "source")
    );
    document.getElementById("browseOutputBtn").addEventListener("click", () => {
      const tenant = document.getElementById("tenant").value;
      const module = document.getElementById("module").value;
      const suggested = `${tenant}_${module}_output.xlsx`;
      pickPath(
        "/fs/save-file",
        { title: "Select output workbook", suggested_name: suggested, default_extension: ".xlsx" },
        "output"
      );
    });
    loadHistory();
    loadTenants();
  </script>
</body>
</html>
"""

_JOB_DB_LOCK = threading.Lock()
_JOB_DB_PATH = Path(__file__).resolve().parents[2] / "data" / "etl_jobs.sqlite"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(slots=True)
class JobRecord:
    """In-memory ETL job record."""

    job_id: str
    status: str
    module: str
    tenant_id: str
    created_at_utc: str
    started_at_utc: str | None = None
    finished_at_utc: str | None = None
    request: dict[str, Any] = field(default_factory=dict)
    result: dict[str, Any] | None = None
    error: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "status": self.status,
            "module": self.module,
            "tenant_id": self.tenant_id,
            "created_at_utc": self.created_at_utc,
            "started_at_utc": self.started_at_utc,
            "finished_at_utc": self.finished_at_utc,
            "request": self.request,
            "result": self.result,
            "error": self.error,
        }

    @staticmethod
    def from_db_row(row) -> "JobRecord":
        return JobRecord(
            job_id=row["job_id"],
            status=row["status"],
            module=row["module"],
            tenant_id=row["tenant_id"],
            created_at_utc=row["created_at_utc"],
            started_at_utc=row["started_at_utc"],
            finished_at_utc=row["finished_at_utc"],
            request=json.loads(row["request_json"]) if row["request_json"] else {},
            result=json.loads(row["result_json"]) if row["result_json"] else None,
            error=json.loads(row["error_json"]) if row["error_json"] else None,
        )


def create_app():
    """Return a WSGI app exposing ETL run endpoints."""

    def app(environ, start_response):
        method = environ.get("REQUEST_METHOD", "GET").upper()
        path = environ.get("PATH_INFO", "")

        if method == "GET" and path == "/":
            return _html_response(start_response, 200, _INDEX_HTML)

        if method == "GET" and path == "/health":
            return _json_response(start_response, 200, {"status": "ok"})

        if method == "POST" and path == "/fs/pick-file":
            return _handle_pick_file(environ, start_response)

        if method == "POST" and path == "/fs/pick-dir":
            return _handle_pick_dir(environ, start_response)

        if method == "POST" and path == "/fs/save-file":
            return _handle_save_file(environ, start_response)

        if method == "POST" and path == "/etl/run":
            return _handle_run_request(environ, start_response)

        if method == "GET" and path == "/etl/runs":
            return _handle_list_runs(environ, start_response)

        if method == "GET" and path == "/etl/tenants":
            return _handle_list_tenants(start_response)

        if method == "GET" and path.startswith("/etl/run/"):
            job_id = path.removeprefix("/etl/run/").strip()
            return _handle_get_job(job_id, start_response)

        return _json_response(start_response, 404, {"error": {"code": "NOT_FOUND", "message": "Route not found"}})

    return app


def run_dev_server(host: str = "127.0.0.1", port: int = 8000) -> None:
    """Run local WSGI dev server for ETL API."""
    _init_job_store()
    app = create_app()
    with make_server(host, port, app) as server:
        print(f"ETL API listening on http://{host}:{port}")
        server.serve_forever()


def _handle_run_request(environ, start_response):
    try:
        payload = _read_json_body(environ)
    except ValueError as exc:
        return _json_response(start_response, 400, {"error": {"code": "BAD_REQUEST", "message": str(exc)}})

    module = str(payload.get("module", "")).strip().lower()
    tenant_id = str(payload.get("tenant_id", "")).strip().lower()
    source = str(payload.get("source", "")).strip()
    output = str(payload.get("output", "")).strip()

    if module not in {"bank", "cashbook"}:
        return _json_response(
            start_response,
            400,
            {"error": {"code": "BAD_REQUEST", "message": "Field 'module' must be one of: bank, cashbook."}},
        )
    if not tenant_id:
        return _json_response(
            start_response,
            400,
            {"error": {"code": "BAD_REQUEST", "message": "Field 'tenant_id' is required."}},
        )
    if not source:
        return _json_response(start_response, 400, {"error": {"code": "BAD_REQUEST", "message": "Field 'source' is required."}})
    if not output:
        return _json_response(start_response, 400, {"error": {"code": "BAD_REQUEST", "message": "Field 'output' is required."}})

    job_id = str(uuid4())
    created = _utc_now_iso()
    record = JobRecord(
        job_id=job_id,
        status="queued",
        module=module,
        tenant_id=tenant_id,
        created_at_utc=created,
        request={
            "module": module,
            "tenant_id": tenant_id,
            "source": source,
            "output": output,
        },
    )
    _job_store_insert(record)

    worker = threading.Thread(target=_run_job, args=(job_id, payload), daemon=True)
    worker.start()

    return _json_response(start_response, 202, {"job_id": job_id, "status": "queued"})


def _handle_get_job(job_id: str, start_response):
    record = _job_store_get(job_id)
    if record is None:
        return _json_response(
            start_response,
            404,
            {"error": {"code": "JOB_NOT_FOUND", "message": f"Job '{job_id}' was not found."}},
        )
    return _json_response(start_response, 200, record.to_dict())


def _handle_list_runs(environ, start_response):
    query = parse_qs(environ.get("QUERY_STRING", ""), keep_blank_values=False)
    raw_limit = query.get("limit", ["50"])[0]
    try:
        limit = max(1, min(500, int(raw_limit)))
    except ValueError:
        return _json_response(
            start_response,
            400,
            {"error": {"code": "BAD_REQUEST", "message": "Query parameter 'limit' must be an integer."}},
        )
    records = _job_store_list(limit=limit)
    return _json_response(start_response, 200, {"runs": [record.to_dict() for record in records]})


def _handle_list_tenants(start_response):
    from Restaurant.etl_platform.tenant.registry import list_tenants

    tenants = list_tenants()
    return _json_response(start_response, 200, {"tenants": tenants})


def _handle_pick_file(environ, start_response):
    try:
        payload = _read_json_body(environ)
        selected = _show_open_file_dialog(title=str(payload.get("title", "Select file")))
        return _json_response(start_response, 200, {"path": selected})
    except Exception as exc:
        return _json_response(
            start_response,
            500,
            {"error": {"code": "FILE_DIALOG_ERROR", "message": str(exc)}},
        )


def _handle_pick_dir(environ, start_response):
    try:
        payload = _read_json_body(environ)
        selected = _show_open_dir_dialog(title=str(payload.get("title", "Select folder")))
        return _json_response(start_response, 200, {"path": selected})
    except Exception as exc:
        return _json_response(
            start_response,
            500,
            {"error": {"code": "FILE_DIALOG_ERROR", "message": str(exc)}},
        )


def _handle_save_file(environ, start_response):
    try:
        payload = _read_json_body(environ)
        selected = _show_save_file_dialog(
            title=str(payload.get("title", "Select output file")),
            suggested_name=str(payload.get("suggested_name", "output.xlsx")),
            default_extension=str(payload.get("default_extension", ".xlsx")),
        )
        return _json_response(start_response, 200, {"path": selected})
    except Exception as exc:
        return _json_response(
            start_response,
            500,
            {"error": {"code": "FILE_DIALOG_ERROR", "message": str(exc)}},
        )


def _run_job(job_id: str, payload: dict[str, Any]) -> None:
    module = str(payload["module"]).strip().lower()
    tenant_id = str(payload["tenant_id"]).strip().lower()
    source = Path(str(payload["source"]))
    output = Path(str(payload["output"]))

    _job_store_mark_running(job_id)

    try:
        if module == "bank":
            result = _run_bank_job(tenant_id=tenant_id, source=source, output=output, payload=payload)
        else:
            result = _run_cashbook_job(tenant_id=tenant_id, source=source, output=output, payload=payload)

        _job_store_mark_succeeded(job_id, result)
    except Exception as exc:  # safety net for worker thread
        error_code, public_message = _map_job_error(exc)
        print(f"[JOB FAILED] {job_id} {type(exc).__name__}: {exc}")
        _job_store_mark_failed(
            job_id=job_id,
            error={
                "code": error_code,
                "message": public_message,
                "exception_type": type(exc).__name__,
            },
        )


def _run_bank_job(tenant_id: str, source: Path, output: Path, payload: dict[str, Any]) -> dict[str, Any]:
    from Restaurant.etl_platform.bank.errors import BankServiceError
    from Restaurant.etl_platform.bank.interfaces import BankRunRequest
    from Restaurant.etl_platform.bank.service import BankService

    request = BankRunRequest(
        tenant_id=tenant_id,
        source_dir=source,
        output_path=output,
        statement_pdf=Path(payload["statement_pdf"]) if payload.get("statement_pdf") else None,
        agenda_file=Path(payload["agenda_file"]) if payload.get("agenda_file") else None,
        sqlite_output_path=Path(payload["sqlite_output"]) if payload.get("sqlite_output") else None,
        excel_title=str(payload.get("excel_title")) if payload.get("excel_title") else None,
    )
    try:
        result = BankService().run_with_result(request)
    except BankServiceError as exc:
        raise RuntimeError(f"bank:{exc.code}:{exc.message}") from exc

    return {
        "module": result.module_name,
        "tenant_id": result.tenant_id,
        "row_count": len(result.rows),
        "artifacts": {
            "workbook": str(result.output_path),
            "canonical_json": str(result.canonical_json_path),
            "run_meta": str(result.run_meta_path) if result.run_meta_path else None,
            "diagnostics": str(result.diagnostics_path) if result.diagnostics_path else None,
        },
        "warnings": result.warnings,
    }


def _run_cashbook_job(tenant_id: str, source: Path, output: Path, payload: dict[str, Any]) -> dict[str, Any]:
    from Restaurant.etl_platform.cashbook.errors import CashbookServiceError
    from Restaurant.etl_platform.cashbook.interfaces import CashbookRunRequest
    from Restaurant.etl_platform.cashbook.service import CashbookService

    request = CashbookRunRequest(
        tenant_id=tenant_id,
        input_path=source,
        output_path=output,
        pdf_base_dir=Path(payload["pdf_base_dir"]) if payload.get("pdf_base_dir") else None,
        sheet_name=str(payload.get("sheet_name")) if payload.get("sheet_name") else None,
        sqlite_output_path=Path(payload["sqlite_output"]) if payload.get("sqlite_output") else None,
    )
    try:
        result = CashbookService().run_with_result(request)
    except CashbookServiceError as exc:
        raise RuntimeError(f"cashbook:{exc.code}:{exc.message}") from exc

    return {
        "module": result.module_name,
        "tenant_id": result.tenant_id,
        "row_count": len(result.rows),
        "artifacts": {
            "workbook": str(result.output_path),
            "canonical_json": str(result.canonical_json_path),
            "sqlite": str(result.sqlite_path),
            "run_meta": str(result.run_meta_path) if result.run_meta_path else None,
        },
        "warnings": result.warnings,
    }


def _read_json_body(environ) -> dict[str, Any]:
    raw_length = environ.get("CONTENT_LENGTH", "")
    try:
        length = int(raw_length) if raw_length else 0
    except ValueError as exc:
        raise ValueError("Invalid Content-Length header.") from exc

    body = environ["wsgi.input"].read(length if length > 0 else 0)
    if not body:
        return {}
    try:
        parsed = json.loads(body.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON body: {exc.msg}") from exc
    if not isinstance(parsed, dict):
        raise ValueError("JSON request body must be an object.")
    return parsed


def _json_response(start_response, status_code: int, payload: dict[str, Any]):
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    reason = {
        200: "OK",
        202: "Accepted",
        400: "Bad Request",
        404: "Not Found",
        500: "Internal Server Error",
    }.get(status_code, "OK")
    start_response(
        f"{status_code} {reason}",
        [
            ("Content-Type", "application/json; charset=utf-8"),
            ("Content-Length", str(len(body))),
        ],
    )
    return [body]


def _html_response(start_response, status_code: int, html: str):
    body = html.encode("utf-8")
    reason = {
        200: "OK",
        404: "Not Found",
    }.get(status_code, "OK")
    start_response(
        f"{status_code} {reason}",
        [
            ("Content-Type", "text/html; charset=utf-8"),
            ("Content-Length", str(len(body))),
        ],
    )
    return [body]


def _show_open_file_dialog(title: str = "Select file") -> str:
    import tkinter as tk
    from tkinter import filedialog

    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    try:
        return str(filedialog.askopenfilename(title=title) or "")
    finally:
        root.destroy()


def _show_open_dir_dialog(title: str = "Select folder") -> str:
    import tkinter as tk
    from tkinter import filedialog

    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    try:
        return str(filedialog.askdirectory(title=title) or "")
    finally:
        root.destroy()


def _show_save_file_dialog(
    title: str = "Select output file",
    suggested_name: str = "output.xlsx",
    default_extension: str = ".xlsx",
) -> str:
    import tkinter as tk
    from tkinter import filedialog

    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    try:
        return str(
            filedialog.asksaveasfilename(
                title=title,
                initialfile=suggested_name,
                defaultextension=default_extension,
                filetypes=[("Excel Workbook", "*.xlsx"), ("All Files", "*.*")],
            )
            or ""
        )
    finally:
        root.destroy()


def _map_job_error(exc: Exception) -> tuple[str, str]:
    raw = str(exc)
    parts = raw.split(":", 2)
    if len(parts) == 3 and parts[0] in {"bank", "cashbook"}:
        _module, code, message = parts
        return code, message
    return "UNKNOWN", "Job failed. See server logs for details."


def _init_job_store() -> None:
    _JOB_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _job_store_connection() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS etl_jobs (
                job_id TEXT PRIMARY KEY,
                status TEXT NOT NULL,
                module TEXT NOT NULL,
                tenant_id TEXT NOT NULL,
                created_at_utc TEXT NOT NULL,
                started_at_utc TEXT,
                finished_at_utc TEXT,
                request_json TEXT,
                result_json TEXT,
                error_json TEXT
            )
            """
        )
        connection.execute("CREATE INDEX IF NOT EXISTS idx_etl_jobs_created ON etl_jobs(created_at_utc DESC)")
        connection.commit()


def _job_store_connection():
    connection = sqlite3.connect(_JOB_DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def _job_store_insert(record: JobRecord) -> None:
    with _JOB_DB_LOCK, _job_store_connection() as connection:
        connection.execute(
            """
            INSERT INTO etl_jobs (
                job_id, status, module, tenant_id, created_at_utc, started_at_utc, finished_at_utc,
                request_json, result_json, error_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record.job_id,
                record.status,
                record.module,
                record.tenant_id,
                record.created_at_utc,
                record.started_at_utc,
                record.finished_at_utc,
                json.dumps(record.request, ensure_ascii=False),
                json.dumps(record.result, ensure_ascii=False) if record.result is not None else None,
                json.dumps(record.error, ensure_ascii=False) if record.error is not None else None,
            ),
        )
        connection.commit()


def _job_store_get(job_id: str) -> JobRecord | None:
    with _JOB_DB_LOCK, _job_store_connection() as connection:
        row = connection.execute(
            "SELECT * FROM etl_jobs WHERE job_id = ?",
            (job_id,),
        ).fetchone()
    return JobRecord.from_db_row(row) if row is not None else None


def _job_store_list(limit: int) -> list[JobRecord]:
    with _JOB_DB_LOCK, _job_store_connection() as connection:
        rows = connection.execute(
            "SELECT * FROM etl_jobs ORDER BY created_at_utc DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [JobRecord.from_db_row(row) for row in rows]


def _job_store_mark_running(job_id: str) -> None:
    with _JOB_DB_LOCK, _job_store_connection() as connection:
        connection.execute(
            """
            UPDATE etl_jobs
            SET status = ?, started_at_utc = ?
            WHERE job_id = ?
            """,
            ("running", _utc_now_iso(), job_id),
        )
        connection.commit()


def _job_store_mark_succeeded(job_id: str, result: dict[str, Any]) -> None:
    with _JOB_DB_LOCK, _job_store_connection() as connection:
        connection.execute(
            """
            UPDATE etl_jobs
            SET status = ?, finished_at_utc = ?, result_json = ?, error_json = NULL
            WHERE job_id = ?
            """,
            ("succeeded", _utc_now_iso(), json.dumps(result, ensure_ascii=False), job_id),
        )
        connection.commit()


def _job_store_mark_failed(job_id: str, error: dict[str, Any]) -> None:
    with _JOB_DB_LOCK, _job_store_connection() as connection:
        connection.execute(
            """
            UPDATE etl_jobs
            SET status = ?, finished_at_utc = ?, error_json = ?
            WHERE job_id = ?
            """,
            ("failed", _utc_now_iso(), json.dumps(error, ensure_ascii=False), job_id),
        )
        connection.commit()


if __name__ == "__main__":
    run_dev_server()

