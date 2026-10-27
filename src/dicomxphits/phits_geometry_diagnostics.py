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
        rf"^\s*{re.escape(label[:-1]) + 's?' if key == 'unrecovered_errors' else re.escape(label)}\s*(?:=|:)?\s*"
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
            prefix = label[:-1] if key == "unrecovered_errors" else label
            if not folded.startswith(prefix.casefold()):
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


def parse_research_geometry_completion(lines: Iterable[str]) -> dict[str, Any]:
    """Parse the operator-supplied table format; unknown layouts fail closed.

    Numeric width and line bounds match the existing counter parser. This is
    a format contract, not evidence of transport accuracy or dose validity.
    """
    counters = []
    pairs = []
    seen = set()
    in_summary = False
    table = False
    table_done = False
    summaries = 0
    headers = 0
    last_batch = None
    for line in lines:
        candidate = line.strip()
        if len(line.rstrip("\r\n")) > _MAX_DIAGNOSTIC_LINE_LENGTH:
            raise PhitsGeometryDiagnosticsError("PHITS completion line is too long")
        if candidate.casefold() == "geometry error summary":
            summaries += 1
            in_summary = True
        elif re.fullmatch(r"region1\s+region2\s+count", candidate, re.I):
            if not in_summary or table_done:
                raise PhitsGeometryDiagnosticsError("Misplaced geometry region-pair table")
            headers += 1
            table = True
        elif table:
            if not candidate or re.fullmatch(r"-+", candidate):
                if pairs:
                    table = False
                    table_done = True
            else:
                match = re.fullmatch(r"([0-9]{1,20})\s+([0-9]{1,20})\s+([0-9]{1,20})", candidate)
                if match is None:
                    raise PhitsGeometryDiagnosticsError("Unsupported geometry region-pair row")
                first, second, count = map(int, match.groups())
                if count <= 0 or (first, second) in seen:
                    raise PhitsGeometryDiagnosticsError("Ambiguous geometry region-pair counts")
                seen.add((first, second))
                pairs.append({"region1": first, "region2": second, "count": count})
        if candidate.casefold().startswith("number of "):
            counters.append(line)
        if candidate.casefold().startswith("bat["):
            match = re.fullmatch(r"bat\[\s*([0-9]{1,20})\s*\]\s+ncas\s*=\s*[0-9]{1,20}\.?", candidate, re.I)
            if match is None:
                raise PhitsGeometryDiagnosticsError("Unsupported PHITS batch completion record")
            batch = int(match.group(1))
            if last_batch is not None and batch <= last_batch:
                raise PhitsGeometryDiagnosticsError("Ambiguous PHITS batch sequence")
            last_batch = batch
    diagnostics = parse_phits_geometry_diagnostics(counters)
    counts = diagnostics["counts"]
    if (summaries != 1 or headers != 1 or not pairs
            or counts["lost_particles"] != 0 or counts["unrecovered_errors"] != 0
            or counts["geometry_recovering"] <= 0
            or sum(pair["count"] for pair in pairs) != counts["geometry_recovering"]
            or last_batch is None):
        raise PhitsGeometryDiagnosticsError("Incomplete or inconsistent research geometry evidence")
    return {"diagnostics": diagnostics, "region_pair_counts": pairs,
            "completed_batches": last_batch}


def parse_phits_geometry_diagnostics_file(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise PhitsGeometryDiagnosticsError(
            f"PHITS geometry diagnostic output is missing: {path.name}"
        )
    from dicomxphits.sumtally_inputs import checked_text_lines

    with checked_text_lines(path, errors="replace") as stream:
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
