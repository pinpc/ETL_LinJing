"""Platform package for shared ETL modules (legacy namespace)."""

from __future__ import annotations

import warnings

warnings.warn(
    "Restaurant.platform is deprecated; prefer Restaurant.etl_platform.",
    DeprecationWarning,
    stacklevel=2,
)

