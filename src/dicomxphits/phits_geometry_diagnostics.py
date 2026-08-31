from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Iterable, Mapping


GEOMETRY_DIAGNOSTICS_SCHEMA_VERSION = (
    "dicomxphits_phits_geometry_diagnostics_v1"
)
GEOMETRY_DIAGNOSTIC_LABELS = {
    "lost_particles": "Number of lost particles",
    "geometry_recovering": "Number of geometry recovering",
    "unrecovered_errors": "Number of unrecovered errors",
}
_COUNT_PATTERNS = {
    key: re.compile(
        rf"^\s*{re.escape(label)}\s*(?:=|:)?\s*"
        r"([0-9]{1,20})"
        + (
            r"(?:\s+/\s+nlost\s+=\s+[0-9]{1,20})?"
            if key == "lost_particles"
            else ""
        )
        + r"\s*$",
        re.IGNORECASE,
    )
    for key, label in GEOMETRY_DIAGNOSTIC_LABELS.items()
}
_MAX_DIAGNOSTIC_LINE_LENGTH = 4096


class PhitsGeometryDiagnosticsError(ValueError):
    """Raised when PHITS geometry-clean completion cannot be established."""


def parse_phits_geometry_diagnostics(
    lines: Iterable[str],
) -> dict[str, Any]:
    """Parse the three PHITS Category-I geometry counters fail-closed."""

    counts: dict[str, int] = {}
    for line_number, line in enumerate(lines, start=1):
        candidate = line.rstrip("\r\n")
        folded = candidate.lstrip().casefold()
        for key, label in GEOMETRY_DIAGNOSTIC_LABELS.items():
            if not folded.startswith(label.casefold()):
                continue
            if len(candidate) > _MAX_DIAGNOSTIC_LINE_LENGTH:
                raise PhitsGeometryDiagnosticsError(
                    f"PHITS geometry diagnostic line {line_number} is too long"
                )
            if key in counts:
                raise PhitsGeometryDiagnosticsError(
                    f"duplicate PHITS geometry diagnostic: {label}"
                )
            match = _COUNT_PATTERNS[key].fullmatch(candidate)
            if match is None:
                raise PhitsGeometryDiagnosticsError(
                    f"malformed PHITS geometry diagnostic: {label}"
                )
            counts[key] = int(match.group(1))
            break

    missing = [
        label
        for key, label in GEOMETRY_DIAGNOSTIC_LABELS.items()
        if key not in counts
    ]
    if missing:
        raise PhitsGeometryDiagnosticsError(
            "missing PHITS geometry diagnostics: " + ", ".join(missing)
        )
    status = "clean" if all(value == 0 for value in counts.values()) else "error"
    return {
        "schema_version": GEOMETRY_DIAGNOSTICS_SCHEMA_VERSION,
        "status": status,
        "counts": counts,
    }


def parse_phits_geometry_diagnostics_file(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise PhitsGeometryDiagnosticsError(
            f"PHITS geometry diagnostic output is missing: {path.name}"
        )
    with path.open("r", encoding="utf-8", errors="replace") as stream:
        return parse_phits_geometry_diagnostics(stream)


def invalid_phits_geometry_diagnostics(reason: str) -> dict[str, Any]:
    return {
        "schema_version": GEOMETRY_DIAGNOSTICS_SCHEMA_VERSION,
        "status": "invalid",
        "counts": None,
        "reason": reason,
    }


def require_clean_phits_geometry_diagnostics(
    evidence: Mapping[str, Any] | None,
) -> dict[str, int]:
    if not isinstance(evidence, Mapping):
        raise PhitsGeometryDiagnosticsError(
            "PHITS geometry diagnostic evidence is missing"
        )
    if evidence.get("schema_version") != GEOMETRY_DIAGNOSTICS_SCHEMA_VERSION:
        raise PhitsGeometryDiagnosticsError(
            "PHITS geometry diagnostic evidence has an unsupported schema"
        )
    counts = evidence.get("counts")
    if evidence.get("status") != "clean" or not isinstance(counts, Mapping):
        raise PhitsGeometryDiagnosticsError(
            "PHITS geometry diagnostic evidence is not clean"
        )
    normalized: dict[str, int] = {}
    if set(counts) != set(GEOMETRY_DIAGNOSTIC_LABELS):
        raise PhitsGeometryDiagnosticsError(
            "PHITS geometry diagnostic evidence is incomplete"
        )
    for key in GEOMETRY_DIAGNOSTIC_LABELS:
        value = counts.get(key)
        if isinstance(value, bool) or not isinstance(value, int) or value != 0:
            raise PhitsGeometryDiagnosticsError(
                "PHITS geometry diagnostic evidence contains a nonzero or invalid count"
            )
        normalized[key] = value
    return normalized
