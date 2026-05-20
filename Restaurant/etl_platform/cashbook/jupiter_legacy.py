from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass, replace
from datetime import datetime
from decimal import Decimal, InvalidOperation
import os
from pathlib import Path
from typing import Any, Iterable

import pdfplumber
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side

CONFIG_JSON_PATH = Path(__file__).resolve().with_name("jupiter_legacy_config.json")


def _load_config() -> dict:
    return json.loads(CONFIG_JSON_PATH.read_text(encoding="utf-8"))


_CONFIG = _load_config()
_DEFAULTS = _CONFIG["defaults"]
_ACCOUNTS = _CONFIG["accounts"]
_PATHS = _CONFIG["paths"]

TARGET_COLUMNS = list(_CONFIG["target_columns"])
COLUMN_WIDTHS = {key: int(value) for key, value in _CONFIG["column_widths"].items()}

STANDARD_KOST = int(_DEFAULTS["standard_kost"])
STANDARD_BANK = int(_DEFAULTS["standard_bank"])

BU_GKTO_ALLOPAY_EXPENSE = int(_ACCOUNTS["allopay_expense"])
BU_GKTO_BAUMARKT_EXPENSE = int(_ACCOUNTS["baumarkt_expense"])
BU_GKTO_FISCH_FOOD = int(_ACCOUNTS["fisch_food"])
BU_GKTO_INCOME = int(_ACCOUNTS["income"])
BU_GKTO_ALLOPAY_19 = int(_ACCOUNTS["allopay_19"])
BU_GKTO_ALLOPAY_7 = int(_ACCOUNTS["allopay_7"])

MERGE_TOLERANCE = Decimal(str(_DEFAULTS["merge_tolerance"]))
XL_EURO_NUM_FMT = str(_DEFAULTS["xl_euro_num_fmt"])

DEFAULT_BASE_PATH = Path(_PATHS["base_path"])
DEFAULT_CASHBOOK_CANDIDATES = [Path(path) for path in _PATHS["cashbook_candidates"]]
DEFAULT_OUTPUT_PATH = Path(_PATHS["output_path"])


@dataclass(frozen=True)
class CashbookTransaction:
    datum: str
    einnahmen: Decimal
    ausgaben: Decimal
    buchungstext: str


@dataclass(frozen=True)
class BuchungRow:
    umsatz_euro: Decimal
    bu_gkto: int
    beleg_1: str
    datum: str
    kost_1: int
    bank: int
    buchungstext: str


@dataclass(frozen=True)
class AllopayPdfData:
    datum: str
    z_nummer: str
    umsatz_7: Decimal
    umsatz_19: Decimal
    allopay_payment_sum: Decimal
    dateiname: str


@dataclass(frozen=True)
class PipelineResult:
    saved_path: Path
    umsatz_count: int
    allopay_count: int
    final_count: int
    pdf_base_dir: Path


def as_text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def convert_german_number(value: Any) -> Decimal:
    if value is None:
        return Decimal("0")
    if isinstance(value, Decimal):
        return value
    if isinstance(value, (int, float)):
        return Decimal(str(value))

    text = str(value).strip().replace("EUR", "").replace("€", "").strip()
    if text == "":
        return Decimal("0")

    text = text.replace(" ", "")
    if "." in text and "," in text:
        text = text.replace(".", "").replace(",", ".")
    elif "," in text:
        parts = text.split(",")
        if len(parts) == 2 and len(parts[1]) == 2:
            text = text.replace(",", ".")
        else:
            text = text.replace(",", ".")
    elif "." in text:
        if text.count(".") > 1:
            text = text.replace(".", "")
        else:
            parts = text.split(".")
            if len(parts) == 2 and len(parts[1]) != 2:
                text = text.replace(".", "")

    try:
        return Decimal(text)
    except InvalidOperation:
        return Decimal("0")


def parse_money_amount(value: Any) -> Decimal:
    if value is None:
        return Decimal("0")
    if isinstance(value, Decimal):
        return value
    if isinstance(value, (int, float)):
        return Decimal(str(value))

    text = str(value).strip()
    if text in {"", "-"}:
        return Decimal("0")

    text = text.replace("\ufeff", "").replace("\ufffd", "")
    text = text.replace("EUR", "").replace("€", "")
    text = re.sub(r"\s+", "", text)
    if text == "":
        return Decimal("0")

    neg = False
    if text.startswith("(") and text.endswith(")"):
        neg = True
        text = text[1:-1]
    if text.startswith("-"):
        neg = True
        text = text[1:]

    m = re.search(r"([\d.,]+)", text)
    if not m:
        return Decimal("0")
    core = m.group(1)

    if "," in core and "." in core:
        if core.rfind(".") > core.rfind(","):
            core = core.replace(",", "")
        else:
            core = core.replace(".", "").replace(",", ".")
    elif "," in core:
        parts = core.split(",")
        if len(parts) == 2 and len(parts[1]) <= 2:
            core = parts[0].replace(".", "") + "." + parts[1]
        else:
            core = core.replace(".", "").replace(",", ".")
    elif "." in core:
        if core.count(".") > 1:
            core = core.replace(".", "")
        else:
            parts = core.split(".")
            if len(parts) == 2 and len(parts[1]) != 2:
                core = parts[0] + parts[1]

    try:
        d = Decimal(core)
    except InvalidOperation:
        return Decimal("0")
    return -d if neg else d


def parse_date(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.strftime("%d.%m.%Y")

    text = str(value).strip()
    if text == "":
        return ""

    for fmt in ("%d.%m.%Y", "%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(text, fmt).strftime("%d.%m.%Y")
        except ValueError:
            pass

    return text


def date_sort_key(value: str) -> tuple[int, int, int, str]:
    text = as_text(value)
    if text == "":
        return (9999, 12, 31, text)

    for fmt in ("%d.%m.%Y", "%Y-%m-%d", "%Y/%m/%d", "%d/%m/%Y"):
        try:
            dt = datetime.strptime(text, fmt)
            return (dt.year, dt.month, dt.day, text)
        except ValueError:
            pass

    return (9999, 12, 31, text)


def sort_rows_by_date(rows: Iterable[BuchungRow]) -> list[BuchungRow]:
    return sorted(rows, key=lambda row: (date_sort_key(row.datum), row.beleg_1, row.buchungstext))


def _contains_any(text: str, tokens: tuple[str, ...]) -> bool:
    lowered = text.lower()
    return any(token in lowered for token in tokens)


def _find_header_row(ws, scan_rows: int = 30) -> int:
    best_row = 1
    best_score = -1

    for row_idx in range(1, min(ws.max_row, scan_rows) + 1):
        values = [str(cell.value).strip() if cell.value is not None else "" for cell in ws[row_idx]]
        row_text = " ".join(values).lower()
        nonempty = sum(1 for value in values if value)
        score = nonempty

        if _contains_any(row_text, ("datum", "beleg datum", "einnahmen", "ausgaben", "geschäft", "收入", "支出")):
            score += 8

        if score > best_score and nonempty >= 3:
            best_score = score
            best_row = row_idx

    return best_row


def _map_excel_columns(headers: list[str]) -> dict[str, int]:
    mapping: dict[str, int] = {}

    for idx, header in enumerate(headers):
        value = header.lower()
        if "datum" in value or "日期" in value:
            mapping.setdefault("datum", idx)
        elif "einnahmen" in value or "rechts" in value or "收入" in value:
            mapping.setdefault("einnahmen", idx)
        elif "ausgaben" in value or "links" in value or "支出" in value:
            mapping.setdefault("ausgaben", idx)
        elif "geschäft" in value or "用途" in value:
            mapping.setdefault("text", idx)

    return mapping


def _should_stop_row(values: list[Any]) -> bool:
    row_text = " ".join(str(value) for value in values if value is not None).lower()
    return _contains_any(row_text, ("summe", "unterschrift", "bestand", "收入总额"))


def _read_excel_transactions(input_path: Path, sheet_name: str | None = None) -> list[CashbookTransaction]:
    workbook = load_workbook(input_path, data_only=True)

    if sheet_name:
        name_map = {name.lower(): name for name in workbook.sheetnames}
        resolved = name_map.get(sheet_name.lower(), sheet_name)
        if resolved not in workbook.sheetnames:
            raise ValueError(f"Sheet '{sheet_name}' not found. Available: {workbook.sheetnames}")
        worksheet = workbook[resolved]
    else:
        worksheet = next(workbook[name] for name in workbook.sheetnames if not name.startswith("__"))

    header_row = _find_header_row(worksheet)
    headers = [str(cell.value).strip() if cell.value is not None else "" for cell in worksheet[header_row]]
    col_map = _map_excel_columns(headers)

    transactions: list[CashbookTransaction] = []
    for row_idx in range(header_row + 1, worksheet.max_row + 1):
        values = [cell.value for cell in worksheet[row_idx]]
        if all(value is None or str(value).strip() == "" for value in values):
            continue
        if _should_stop_row(values):
            break

        def get(column_name: str) -> Any:
            idx = col_map.get(column_name)
            return values[idx] if idx is not None and idx < len(values) else None

        datum = parse_date(get("datum"))
        einnahmen = convert_german_number(get("einnahmen"))
        ausgaben = convert_german_number(get("ausgaben"))
        text = str(get("text")).strip() if get("text") is not None else ""

        if datum == "":
            continue
        if einnahmen <= 0 and ausgaben <= 0:
            continue

        transactions.append(
            CashbookTransaction(
                datum=datum,
                einnahmen=einnahmen,
                ausgaben=ausgaben,
                buchungstext=text,
            )
        )

    return transactions


def _read_pdf_transactions(pdf_path: Path) -> list[CashbookTransaction]:
    transactions: list[CashbookTransaction] = []

    with pdfplumber.open(str(pdf_path)) as pdf:
        page = pdf.pages[0]
        tables = page.extract_tables()
        if not tables:
            return []

        table = tables[0]
        header_row_idx = -1
        col_datum_idx = -1
        col_einnahmen_idx = -1
        col_ausgaben_idx = -1
        col_text_idx = -1

        for row_idx, row in enumerate(table):
            row_text = str(row).lower()
            if "beleg" in row_text or "datum" in row_text or "einnahmen" in row_text:
                header_row_idx = row_idx
                for col_idx, cell in enumerate(row):
                    if cell is None:
                        continue
                    cell_text = str(cell).lower()
                    if "datum" in cell_text:
                        col_datum_idx = col_idx
                    elif "einnahmen" in cell_text or "rechts" in cell_text or "收入" in cell_text:
                        col_einnahmen_idx = col_idx
                    elif "ausgaben" in cell_text or "links" in cell_text or "支出" in cell_text:
                        col_ausgaben_idx = col_idx
                    elif "geschäfts" in cell_text or "用途" in cell_text:
                        col_text_idx = col_idx
                break

        if header_row_idx == -1:
            return []

        if col_datum_idx == -1:
            col_datum_idx = 1
        if col_einnahmen_idx == -1:
            col_einnahmen_idx = 2
        if col_ausgaben_idx == -1:
            col_ausgaben_idx = 3
        if col_text_idx == -1:
            col_text_idx = 5

        for row in table[header_row_idx + 1 :]:
            if not row or all(cell is None or str(cell).strip() == "" for cell in row):
                continue
            row_text = str(row).lower()
            if _contains_any(row_text, ("summe", "unterschrift", "bestand", "收入总额")):
                break

            datum = ""
            if col_datum_idx < len(row) and row[col_datum_idx]:
                datum = parse_date(str(row[col_datum_idx]).strip())

            if not re.match(r"\d{2}\.\d{2}\.\d{4}", datum):
                continue

            einnahmen = (
                convert_german_number(row[col_einnahmen_idx])
                if col_einnahmen_idx < len(row)
                else Decimal("0")
            )
            ausgaben = (
                convert_german_number(row[col_ausgaben_idx])
                if col_ausgaben_idx < len(row)
                else Decimal("0")
            )
            text = str(row[col_text_idx]).strip() if col_text_idx < len(row) and row[col_text_idx] else ""

            if einnahmen > 0 or ausgaben > 0:
                transactions.append(
                    CashbookTransaction(
                        datum=datum,
                        einnahmen=einnahmen,
                        ausgaben=ausgaben,
                        buchungstext=text,
                    )
                )

    return transactions


def get_bu_gkto(umsatz: Decimal, text: str) -> int:
    text_lower = text.lower()

    if umsatz < 0:
        if "allo" in text_lower or "bankeinzahlung" in text_lower:
            return BU_GKTO_ALLOPAY_EXPENSE
        if "baumarkt" in text_lower or "v-baumarkt" in text_lower:
            return BU_GKTO_BAUMARKT_EXPENSE
        return BU_GKTO_BAUMARKT_EXPENSE
    return BU_GKTO_INCOME


def _build_buchung_rows(transactions: list[CashbookTransaction]) -> list[BuchungRow]:
    rows: list[BuchungRow] = []

    for transaction in transactions:
        if transaction.einnahmen > 0:
            rows.append(
                BuchungRow(
                    umsatz_euro=transaction.einnahmen.quantize(Decimal("0.01")),
                    bu_gkto=get_bu_gkto(transaction.einnahmen, transaction.buchungstext),
                    beleg_1="",
                    datum=transaction.datum,
                    kost_1=STANDARD_KOST,
                    bank=STANDARD_BANK,
                    buchungstext=transaction.buchungstext,
                )
            )
        if transaction.ausgaben > 0:
            negative_amount = (-transaction.ausgaben).quantize(Decimal("0.01"))
            rows.append(
                BuchungRow(
                    umsatz_euro=negative_amount,
                    bu_gkto=get_bu_gkto(negative_amount, transaction.buchungstext),
                    beleg_1="",
                    datum=transaction.datum,
                    kost_1=STANDARD_KOST,
                    bank=STANDARD_BANK,
                    buchungstext=transaction.buchungstext,
                )
            )

    sorted_rows = sort_rows_by_date(rows)
    return [
        BuchungRow(
            umsatz_euro=row.umsatz_euro,
            bu_gkto=row.bu_gkto,
            beleg_1=f"Z{idx:03d}",
            datum=row.datum,
            kost_1=row.kost_1,
            bank=row.bank,
            buchungstext=row.buchungstext,
        )
        for idx, row in enumerate(sorted_rows, start=1)
    ]


def read_cashbook_rows(input_path: Path, sheet_name: str | None = None) -> list[BuchungRow]:
    suffix = input_path.suffix.lower()
    if suffix == ".pdf":
        transactions = _read_pdf_transactions(input_path)
    elif suffix in {".xlsx", ".xlsm", ".xltx", ".xltm"}:
        transactions = _read_excel_transactions(input_path, sheet_name=sheet_name)
    else:
        raise ValueError(f"Unsupported cashbook format: {input_path.suffix}")

    return _build_buchung_rows(transactions)


def _table_gross_amount(row: list) -> Decimal:
    if not row:
        return Decimal("0")
    if len(row) >= 4 and row[3] is not None and str(row[3]).strip():
        value = parse_money_amount(row[3])
        if value != 0:
            return value
    for cell in reversed(row[1:]):
        if cell is None:
            continue
        value = parse_money_amount(cell)
        if value != 0:
            return value
    return Decimal("0")


def _find_allopay_pdfs(base_path: Path) -> list[Path]:
    pattern = re.compile(r"jupiter \d{2}-\d{2}-\d{4}\.pdf$", re.IGNORECASE)
    matched: list[Path] = []

    for root, _dirs, files in os.walk(base_path):
        for filename in files:
            if pattern.match(filename):
                matched.append(Path(root) / filename)

    return sorted(matched)


def _extract_allopay_from_pdf(pdf_path: Path) -> AllopayPdfData:
    umsatz_7 = convert_german_number(0)
    umsatz_19 = convert_german_number(0)
    allopay_payment_sum = convert_german_number(0)
    datum = ""
    z_nummer = ""

    with pdfplumber.open(str(pdf_path)) as pdf:
        full_text = ""
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                full_text += text + "\n"

        z_match = re.search(r"Z-Nummer\s*\(Berichtnummer\):\s*(\d+)", full_text, re.IGNORECASE)
        if z_match:
            z_nummer = z_match.group(1)

        generiert_match = re.search(r"Generiert um:\s*(\d{2})-(\d{2})-(\d{4})", full_text)
        if generiert_match:
            datum = f"{generiert_match.group(1)}.{generiert_match.group(2)}.{generiert_match.group(3)}"
        else:
            date_match = re.search(r"jupiter (\d{2})-(\d{2})-(\d{4})\.pdf", pdf_path.name, re.IGNORECASE)
            if date_match:
                datum = f"{date_match.group(1)}.{date_match.group(2)}.{date_match.group(3)}"

        for page in pdf.pages:
            for table in page.extract_tables() or []:
                for row in table or []:
                    if not row or len(row) < 4:
                        continue

                    row_text = " ".join(str(cell) if cell else "" for cell in row)
                    first_cell = str(row[0]).strip().lower() if row[0] else ""
                    gross = _table_gross_amount(row)

                    if "Umsatz 7%" in row_text or "Umsatz 7 %" in row_text:
                        if gross > 0:
                            umsatz_7 = gross
                    if "Umsatz 19%" in row_text or "Umsatz 19 %" in row_text:
                        if gross > 0:
                            umsatz_19 = gross
                    if "allo" in first_cell and "pay" in first_cell:
                        if gross > 0:
                            allopay_payment_sum = max(allopay_payment_sum, gross)

        if umsatz_7 == 0 and umsatz_19 == 0:
            match_7 = re.search(
                r"Umsatz\s*7\s*%\D*([\d.,]+)\D+([\d.,]+)\D+([\d.,]+)",
                full_text,
                re.IGNORECASE,
            )
            if match_7:
                umsatz_7 = parse_money_amount(match_7.group(3))

            match_19 = re.search(
                r"Umsatz\s*19\s*%\D*([\d.,]+)\D+([\d.,]+)\D+([\d.,]+)",
                full_text,
                re.IGNORECASE,
            )
            if match_19:
                umsatz_19 = parse_money_amount(match_19.group(3))

        if allopay_payment_sum == 0:
            payment_match = re.search(
                r"allO\s*Pay\D*([\d.,]+)\D+([\d.,]+)\D+([\d.,]+)",
                full_text,
                re.IGNORECASE,
            )
            if payment_match:
                allopay_payment_sum = parse_money_amount(payment_match.group(3))

    return AllopayPdfData(
        datum=datum,
        z_nummer=z_nummer,
        umsatz_7=umsatz_7,
        umsatz_19=umsatz_19,
        allopay_payment_sum=allopay_payment_sum,
        dateiname=pdf_path.name,
    )


def read_allopay_pdf_data(pdf_base_dir: Path) -> list[AllopayPdfData]:
    data_items: list[AllopayPdfData] = []

    for pdf_path in _find_allopay_pdfs(pdf_base_dir):
        data = _extract_allopay_from_pdf(pdf_path)
        if data.datum != "":
            data_items.append(data)

    return sorted(data_items, key=lambda item: item.datum)


def build_allopay_rows(allopay_pdf_data: list[AllopayPdfData]) -> list[BuchungRow]:
    rows: list[BuchungRow] = []

    for data in allopay_pdf_data:
        beleg = f"Z{str(data.z_nummer).zfill(3)}" if data.z_nummer else "Z000"

        if data.umsatz_19 > 0:
            rows.append(
                BuchungRow(
                    umsatz_euro=data.umsatz_19,
                    bu_gkto=BU_GKTO_ALLOPAY_19,
                    beleg_1=beleg,
                    datum=data.datum,
                    kost_1=STANDARD_KOST,
                    bank=STANDARD_BANK,
                    buchungstext="Umsatz 19 %",
                )
            )

        if data.umsatz_7 > 0:
            rows.append(
                BuchungRow(
                    umsatz_euro=data.umsatz_7,
                    bu_gkto=BU_GKTO_ALLOPAY_7,
                    beleg_1=beleg,
                    datum=data.datum,
                    kost_1=STANDARD_KOST,
                    bank=STANDARD_BANK,
                    buchungstext="Umsatz 7 %",
                )
            )

    return sort_rows_by_date(rows)


def _append_sheet(workbook: Workbook, rows: list[BuchungRow], sheet_name: str) -> int:
    worksheet = workbook.create_sheet(sheet_name)
    worksheet.append(TARGET_COLUMNS)

    for row in rows:
        worksheet.append(
            [
                float(row.umsatz_euro),
                row.bu_gkto,
                row.beleg_1,
                row.datum,
                row.kost_1,
                row.bank,
                row.buchungstext,
            ]
        )

    if rows:
        worksheet.append(
            [
                float(sum((row.umsatz_euro for row in rows), Decimal("0"))),
                "",
                "",
                "",
                "",
                "",
                "Gesamtbetrag",
            ]
        )

    _apply_excel_formatting(worksheet)
    return len(rows)


def _apply_excel_formatting(worksheet) -> None:
    max_row = worksheet.max_row
    max_col = len(TARGET_COLUMNS)
    thin_border = Border(
        left=Side(style="thin"),
        right=Side(style="thin"),
        top=Side(style="thin"),
        bottom=Side(style="thin"),
    )

    for row in worksheet.iter_rows(min_row=1, max_row=max_row, min_col=1, max_col=max_col):
        for cell in row:
            cell.border = thin_border
            cell.alignment = Alignment(horizontal="left", vertical="center")

    for cell in worksheet[1]:
        cell.font = Font(bold=True)
        cell.fill = PatternFill(start_color="DDDDDD", end_color="DDDDDD", fill_type="solid")
        cell.alignment = Alignment(horizontal="center", vertical="center")

    for row_idx in range(2, max_row + 1):
        amount_cell = worksheet.cell(row=row_idx, column=1)
        if amount_cell.value not in (None, ""):
            amount_cell.number_format = XL_EURO_NUM_FMT

        if worksheet.cell(row=row_idx, column=7).value == "Gesamtbetrag":
            for col_idx in range(1, max_col + 1):
                worksheet.cell(row=row_idx, column=col_idx).font = Font(bold=True)

    for col_letter, width in COLUMN_WIDTHS.items():
        worksheet.column_dimensions[col_letter].width = width


def _save_workbook(workbook: Workbook, output_xlsx: Path) -> Path:
    output_xlsx.parent.mkdir(parents=True, exist_ok=True)

    try:
        workbook.save(output_xlsx)
        return output_xlsx
    except PermissionError:
        candidates = [output_xlsx.with_name(output_xlsx.stem + "_new" + output_xlsx.suffix)]
        candidates.extend(
            output_xlsx.with_name(output_xlsx.stem + f"_new_{idx}" + output_xlsx.suffix)
            for idx in range(2, 11)
        )

        for alt_path in candidates:
            try:
                workbook.save(alt_path)
                print(f"WARNING: Could not overwrite (file open?). Saved to: {alt_path}")
                return alt_path
            except PermissionError:
                continue

        raise


def build_workbook(
    umsatz_rows: list[BuchungRow],
    allopay_rows: list[BuchungRow],
    final_rows: list[BuchungRow],
    output_xlsx: Path,
) -> tuple[Path, int, int, int]:
    workbook = Workbook()
    if workbook.sheetnames == ["Sheet"]:
        workbook.remove(workbook["Sheet"])

    umsatz_count = _append_sheet(workbook, umsatz_rows, "Umsatz")
    allopay_count = _append_sheet(workbook, allopay_rows, "Allopay")
    final_count = _append_sheet(workbook, final_rows, "Final")

    saved_path = _save_workbook(workbook, output_xlsx)
    return saved_path, umsatz_count, allopay_count, final_count


class JupiterKasseETL:
    def __init__(self) -> None:
        self.umsatz_rows: list[BuchungRow] = []
        self.allopay_rows: list[BuchungRow] = []
        self.final_rows: list[BuchungRow] = []

    def merge_final_rows(
        self,
        umsatz_rows: list[BuchungRow],
        allopay_rows: list[BuchungRow],
        allopay_payment_sum_by_date: dict[str, Decimal] | None = None,
    ) -> list[BuchungRow]:
        if allopay_payment_sum_by_date is None:
            allopay_payment_sum_by_date = {}

        if not umsatz_rows:
            return []

        if not allopay_rows:
            for row in umsatz_rows:
                if row.umsatz_euro > 0 and "allo" in row.buchungstext.lower():
                    print(
                        "WARNUNG [Blatt Final]: Allopay-Auflösung nicht mergebar "
                        f"({row.datum}): keine Allopay-PDF-Zeilen geladen; Kasse bleibt {row.umsatz_euro} EUR.",
                        file=sys.stderr,
                    )
            return sort_rows_by_date([replace(row, beleg_1="") for row in umsatz_rows])

        allopay_by_date: dict[str, list[BuchungRow]] = {}
        allopay_sum_by_date = {}
        safe_allopay_beleg_by_date = self._build_safe_allopay_beleg_by_date(allopay_rows)

        for row in allopay_rows:
            allopay_by_date.setdefault(row.datum, []).append(row)
            allopay_sum_by_date[row.datum] = allopay_sum_by_date.get(row.datum, 0) + row.umsatz_euro

        final_rows: list[BuchungRow] = []
        for row in umsatz_rows:
            is_allopay_income = row.umsatz_euro > 0 and "allo" in row.buchungstext.lower()
            if is_allopay_income:
                pdf_umsatz_sum = allopay_sum_by_date.get(row.datum)
                if pdf_umsatz_sum is not None:
                    diff = abs(pdf_umsatz_sum - row.umsatz_euro)
                    if diff < MERGE_TOLERANCE:
                        final_rows.extend(
                            replace(allopay_row, beleg_1=safe_allopay_beleg_by_date.get(row.datum, ""))
                            for allopay_row in allopay_by_date[row.datum]
                        )
                        continue
                    print(
                        "WARNUNG [Blatt Final]: Allopay-Auflösung nicht mergebar "
                        f"({row.datum}): Kasse {row.umsatz_euro} EUR vs. Summe PDF "
                        f"(Umsatz 19 % + Umsatz 7 %) {pdf_umsatz_sum} EUR "
                        f"(|Diff|={diff}, Toleranz {MERGE_TOLERANCE}).",
                        file=sys.stderr,
                    )
                else:
                    print(
                        "WARNUNG [Blatt Final]: Allopay-Auflösung nicht mergebar "
                        f"({row.datum}): keine PDF-Umsatzzeilen (19 %/7 %) für dieses Datum; "
                        f"Kasse bleibt {row.umsatz_euro} EUR.",
                        file=sys.stderr,
                    )

            split_rows = self._split_compound_final_row(
                row,
                allopay_payment_sum_by_date,
                safe_allopay_beleg_by_date,
            )
            if split_rows is not None:
                final_rows.extend(split_rows)
                continue

            final_rows.append(self._assign_final_beleg(row, safe_allopay_beleg_by_date))

        return sort_rows_by_date(final_rows)

    def _build_safe_allopay_beleg_by_date(self, allopay_rows: list[BuchungRow]) -> dict[str, str]:
        belege_by_date: dict[str, set[str]] = {}
        for row in allopay_rows:
            beleg = row.beleg_1.strip()
            if beleg == "" or beleg == "Z000":
                continue
            belege_by_date.setdefault(row.datum, set()).add(beleg)

        return {
            datum: next(iter(belege)) if len(belege) == 1 else ""
            for datum, belege in belege_by_date.items()
        }

    def _split_compound_final_row(
        self,
        row: BuchungRow,
        allopay_payment_sum_by_date: dict[str, Decimal],
        safe_allopay_beleg_by_date: dict[str, str],
    ) -> list[BuchungRow] | None:
        text_lower = row.buchungstext.lower()
        is_compound_row = row.umsatz_euro < 0 and "+" in row.buchungstext and "allo" in text_lower
        if not is_compound_row:
            return None

        allopay_total = allopay_payment_sum_by_date.get(row.datum)
        if allopay_total is None or allopay_total <= 0:
            return None

        expense_total = abs(row.umsatz_euro)
        allopay_expense = min(expense_total, allopay_total).quantize(Decimal("0.01"))
        remainder_expense = (expense_total - allopay_expense).quantize(Decimal("0.01"))
        safe_allopay_beleg = safe_allopay_beleg_by_date.get(row.datum, "")

        split_rows = [
            replace(
                row,
                umsatz_euro=-allopay_expense,
                bu_gkto=BU_GKTO_ALLOPAY_EXPENSE,
                beleg_1=safe_allopay_beleg,
                buchungstext=f"alloPay {row.datum}",
            )
        ]

        if remainder_expense <= 0:
            return split_rows

        if "fisch" in text_lower:
            split_rows.append(
                replace(
                    row,
                    umsatz_euro=-remainder_expense,
                    bu_gkto=BU_GKTO_FISCH_FOOD,
                    beleg_1="",
                    buchungstext="Fisch Food",
                )
            )
            return split_rows

        if "bank" in text_lower:
            split_rows.append(
                replace(
                    row,
                    umsatz_euro=-remainder_expense,
                    bu_gkto=BU_GKTO_ALLOPAY_EXPENSE,
                    beleg_1="",
                    buchungstext="An Bank",
                )
            )
            return split_rows

        return None

    def _assign_final_beleg(
        self,
        row: BuchungRow,
        safe_allopay_beleg_by_date: dict[str, str],
    ) -> BuchungRow:
        text_lower = row.buchungstext.lower()
        if text_lower == "allo pay":
            return replace(
                row,
                beleg_1=safe_allopay_beleg_by_date.get(row.datum, ""),
                buchungstext=f"alloPay {row.datum}",
            )
        if "allo" in text_lower:
            return replace(row, beleg_1=safe_allopay_beleg_by_date.get(row.datum, ""))
        return replace(row, beleg_1="")

    def run(
        self,
        input_path: Path,
        output_path: Path,
        pdf_base_dir: Path | None = None,
        sheet_name: str | None = None,
    ) -> PipelineResult:
        if pdf_base_dir is None:
            pdf_base_dir = input_path.parent

        self.umsatz_rows = read_cashbook_rows(input_path, sheet_name=sheet_name)
        allopay_pdf_data = read_allopay_pdf_data(pdf_base_dir)
        self.allopay_rows = build_allopay_rows(allopay_pdf_data)
        self.final_rows = self.merge_final_rows(
            self.umsatz_rows,
            self.allopay_rows,
            {
                item.datum: item.allopay_payment_sum
                for item in allopay_pdf_data
                if item.datum != "" and item.allopay_payment_sum > 0
            },
        )

        saved_path, umsatz_count, allopay_count, final_count = build_workbook(
            self.umsatz_rows,
            self.allopay_rows,
            self.final_rows,
            output_path,
        )

        return PipelineResult(
            saved_path=saved_path,
            umsatz_count=umsatz_count,
            allopay_count=allopay_count,
            final_count=final_count,
            pdf_base_dir=pdf_base_dir,
        )


def run_cli(
    input_path: Path,
    output_path: Path,
    pdf_base_dir: Path | None = None,
    sheet_name: str | None = None,
) -> PipelineResult:
    return JupiterKasseETL().run(
        input_path=input_path,
        output_path=output_path,
        pdf_base_dir=pdf_base_dir,
        sheet_name=sheet_name,
    )
