from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

CONFIG_JSON_PATH = Path(__file__).resolve().parents[1] / "config.json"


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
