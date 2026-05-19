# Cashbook Tenant Onboarding Contract

This document defines the minimum contract for adding a new cashbook tenant flow.

## 1) Service Contract

`CashbookService` supports two entry points:

- `run(request) -> list[ProcessedTransaction]` (backward-compatible)
- `run_with_result(request) -> CashbookPipelineResult` (preferred for GUI/API)

## 2) New Tenant Requirements

When adding a tenant implementation:

- Parse tenant-specific source into normalized rows
- Produce workbook at `request.output_path`
- Ensure rows can be converted into `ProcessedTransaction`
- Raise explicit exceptions for invalid/missing input

## 3) Standard Errors

Use `CashbookServiceError` codes from `etl_platform/cashbook/errors.py`:

- `INPUT_MISSING`
- `PARSER_FAILED`
- `LEGACY_RUN_FAILED`
- `OUTPUT_NOT_CREATED`
- `TENANT_UNSUPPORTED`
- `UNKNOWN`

## 4) Output Artifacts

`CashbookService` writes:

- Workbook at `request.output_path`
- SQLite at resolved sqlite path
- Run metadata at `<output>.run_meta.json`

## 5) Smoke Test

Preferred unified smoke entrypoint:

- `python -m Restaurant.apps.etl_cli.etl_smoke --module cashbook --tenant-id <tenant> --source <file> --output <xlsx>`
