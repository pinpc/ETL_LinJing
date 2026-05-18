"""Cashbook service placeholders."""

from __future__ import annotations

from pathlib import Path

from .asia_legacy import AsiaKasseETL
from .interfaces import CashbookRunRequest, ICashbookService
from .jupiter_legacy import JupiterKasseETL
from ..shared.models import ProcessedTransaction


class CashbookService(ICashbookService):
    """Adapter service wrapping legacy tenant-specific cashbook ETLs."""

    def run(self, request: CashbookRunRequest) -> list[ProcessedTransaction]:
        tenant_id = request.tenant_id.strip().lower()
        if tenant_id == "asia":
            engine = AsiaKasseETL()
            engine.run(
                input_path=request.input_path,
                output_path=request.output_path,
                pdf_base_dir=request.input_path.parents[2] if request.input_path.exists() else Path("."),
                sheet_name="cashbook",
            )
            return _result_to_processed_transactions(engine.final_rows, tenant_id, "cashbook")

        if tenant_id == "jupiter":
            engine = JupiterKasseETL()
            engine.run(
                input_path=request.input_path,
                output_path=request.output_path,
                pdf_base_dir=request.input_path.parent if request.input_path.exists() else Path("."),
                sheet_name=None,
            )
            return _result_to_processed_transactions(engine.final_rows, tenant_id, "cashbook")

        raise ValueError(f"Unsupported cashbook tenant '{request.tenant_id}'. Expected: asia, jupiter.")


def _result_to_processed_transactions(rows: list, tenant_id: str, module_name: str) -> list[ProcessedTransaction]:
    processed: list[ProcessedTransaction] = []
    for row in rows:
        processed.append(
            ProcessedTransaction(
                tenant_id=tenant_id,
                module_name=module_name,
                amount=float(row.umsatz_euro),
                booking_date=str(row.datum),
                booking_text=str(row.buchungstext),
                bu_gkto=str(row.bu_gkto),
                beleg_1=str(row.beleg_1),
            )
        )
    return processed

