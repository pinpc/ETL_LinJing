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

### Manifest-based alias registration (new)

You can onboard a new tenant with **zero new runner code** by reusing an existing tenant runner via tenant manifest:

- Create `tenants/<new_tenant>/tenant_manifest.yaml`
- Set:
  - `runner_aliases.cashbook: "<existing_tenant_id>"`
- Optional defaults in manifest (`display_name`, `bank_account`, `default_kost`, `options`) are merged with `tenant_config.yaml`
  - `tenant_config.yaml` values override manifest defaults

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
- Canonical JSON at `<output>.processed.json`
- Run metadata at `<output>.run_meta.json`
- SQLite at resolved sqlite path

## 5) Smoke Test

Preferred unified smoke entrypoint:

- `python -m Restaurant.apps.etl_cli.etl_smoke --module cashbook --tenant-id <tenant> --source <file> --output <xlsx>`

Quality gate:

- CI-friendly checks:
  - `python -m Restaurant.apps.etl_cli.quality_gate`
- Include local-data golden-master checks:
  - `python -m Restaurant.apps.etl_cli.quality_gate --include-golden`
