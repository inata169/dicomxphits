"""CSV cell serialization guards for externally derived strings."""

from __future__ import annotations

import unicodedata
from typing import Any


SPREADSHEET_FORMULA_PREFIXES = frozenset("=+-@")


def neutralize_external_csv_value(value: Any) -> Any:
    """Prefix spreadsheet-active strings while preserving non-string types."""

    if not isinstance(value, str) or not value:
        return value
    first = value[0]
    if first in SPREADSHEET_FORMULA_PREFIXES or unicodedata.category(first) == "Cc":
        return "'" + value
    return value
