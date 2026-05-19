"""Minimal ETL API with async run jobs."""

from __future__ import annotations

import json
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
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
    <select id="tenant">
      <option value="asia">asia</option>
      <option value="jupiter">jupiter</option>
    </select>

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

  <script>
    const jobIdEl = document.getElementById("jobId");
    const statusEl = document.getElementById("status");
    const resultBox = document.getElementById("resultBox");
    let currentJobId = "";
    let pollTimer = null;

    function setStatus(text) {
      statusEl.textContent = text;
    }

    function setResult(data) {
      resultBox.value = JSON.stringify(data, null, 2);
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

    function startPolling() {
      stopPolling();
      pollTimer = setInterval(pollJob, 1000);
      pollJob();
    }

    function stopPolling() {
      if (pollTimer) {
        clearInterval(pollTimer);
        pollTimer = null;
      }
    }

    document.getElementById("startBtn").addEventListener("click", startJob);
    document.getElementById("pollBtn").addEventListener("click", pollJob);
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
  </script>
</body>
</html>
"""


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


_JOBS: dict[str, JobRecord] = {}
_JOBS_LOCK = threading.Lock()


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

        if method == "GET" and path.startswith("/etl/run/"):
            job_id = path.removeprefix("/etl/run/").strip()
            return _handle_get_job(job_id, start_response)

        return _json_response(start_response, 404, {"error": {"code": "NOT_FOUND", "message": "Route not found"}})

    return app


def run_dev_server(host: str = "127.0.0.1", port: int = 8000) -> None:
    """Run local WSGI dev server for ETL API."""
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
    with _JOBS_LOCK:
        _JOBS[job_id] = record

    worker = threading.Thread(target=_run_job, args=(job_id, payload), daemon=True)
    worker.start()

    return _json_response(start_response, 202, {"job_id": job_id, "status": "queued"})


def _handle_get_job(job_id: str, start_response):
    with _JOBS_LOCK:
        record = _JOBS.get(job_id)
    if record is None:
        return _json_response(
            start_response,
            404,
            {"error": {"code": "JOB_NOT_FOUND", "message": f"Job '{job_id}' was not found."}},
        )
    return _json_response(start_response, 200, record.to_dict())


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

    with _JOBS_LOCK:
        record = _JOBS[job_id]
        record.status = "running"
        record.started_at_utc = _utc_now_iso()

    try:
        if module == "bank":
            result = _run_bank_job(tenant_id=tenant_id, source=source, output=output, payload=payload)
        else:
            result = _run_cashbook_job(tenant_id=tenant_id, source=source, output=output, payload=payload)

        with _JOBS_LOCK:
            record = _JOBS[job_id]
            record.status = "succeeded"
            record.finished_at_utc = _utc_now_iso()
            record.result = result
    except Exception as exc:  # safety net for worker thread
        with _JOBS_LOCK:
            record = _JOBS[job_id]
            record.status = "failed"
            record.finished_at_utc = _utc_now_iso()
            error_code, public_message = _map_job_error(exc)
            print(f"[JOB FAILED] {job_id} {type(exc).__name__}: {exc}")
            record.error = {
                "code": error_code,
                "message": public_message,
                "exception_type": type(exc).__name__,
            }


def _run_bank_job(tenant_id: str, source: Path, output: Path, payload: dict[str, Any]) -> dict[str, Any]:
    from Restaurant.platform.bank.errors import BankServiceError
    from Restaurant.platform.bank.interfaces import BankRunRequest
    from Restaurant.platform.bank.service import BankService

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
    from Restaurant.platform.cashbook.errors import CashbookServiceError
    from Restaurant.platform.cashbook.interfaces import CashbookRunRequest
    from Restaurant.platform.cashbook.service import CashbookService

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


if __name__ == "__main__":
    run_dev_server()

