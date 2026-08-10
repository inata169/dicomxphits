from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path
from typing import Any


TARGET_TALLY_PATTERNS = ["deposit-target-3D", "deposit_target"]
DEFAULT_SUMTALLY_MAXCAS = 1_000_000
DEFAULT_SUMTALLY_MAXBCH = 10
DEFAULT_SUMTALLY_OMP_THREADS = 8
MU_TOLERANCE = 1.0e-6
PLAN_MU_NORMALIZATION_SCHEMA = "dicomxphits_active_treatment_mu_sum_v1"
ACTIVE_TREATMENT_SUMTALLY_NORMALIZATION = (
    "active_treatment_segments_totalfield_segment_mu_sum"
)
ACTIVE_TREATMENT_INPUT_DOSE_STATE = "sumtally_active_treatment_mu_sum"
ACTIVE_TREATMENT_SUMMATION_RULE = (
    "sum(active_segment_mu * segment_dose_per_mu)"
)


def file_sha256(path: Path) -> str:
    """Return the SHA-256 digest of one generated Sumtally input file."""

    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def manifest_sha256(manifest: dict[str, Any]) -> str:
    """Return a stable digest that binds Sumtally evidence to one manifest."""

    try:
        canonical = json.dumps(
            manifest,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ValueError(
            "Segment manifest must be canonical JSON without non-finite numbers"
        ) from exc
    return hashlib.sha256(canonical).hexdigest()


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\n")


def normalize_path_for_phits(path: str | Path) -> str:
    return str(path).replace("\\", "/")


def is_portable_absolute_path(path: str | Path) -> bool:
    text = str(path)
    return text.startswith("/") or re.match(r"^[A-Za-z]:[\\/]", text) is not None


def write_libpath_file(output_path: Path, phits_root: str | None = None) -> Path:
    if not phits_root:
        raise ValueError("phits_root is required to write libpath.inp")
    root = normalize_path_for_phits(phits_root)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(f"file(1)  = {root} # PHITS install folder name\n", encoding="utf-8", newline="\r\n")
    return output_path


def resolve_manifest_path(case_root: Path, path_value: str) -> Path:
    if not path_value:
        raise ValueError("expected_output_path is empty")
    path = Path(path_value)
    if path.is_absolute():
        return path
    return case_root / path


def active_segments(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    segments = manifest.get("segments")
    if not isinstance(segments, list):
        raise ValueError("Manifest must contain a segments list")
    return [segment for segment in segments if isinstance(segment, dict) and not segment.get("skip_reason")]


def _finite_number(
    value: Any,
    *,
    label: str,
    positive: bool = False,
) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{label} must be a finite {'positive' if positive else 'nonnegative'} number")
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"{label} must be a finite {'positive' if positive else 'nonnegative'} number"
        ) from exc
    invalid = not math.isfinite(result) or result < 0.0 or (positive and result <= 0.0)
    if invalid:
        raise ValueError(
            f"{label} must be a finite {'positive' if positive else 'nonnegative'} number"
        )
    return result


def _positive_beam_number(value: Any, *, label: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{label} must be a positive integer")
    try:
        number = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} must be a positive integer") from exc
    if number <= 0 or str(value).strip() not in {str(number), f"{number}.0"}:
        raise ValueError(f"{label} must be a positive integer")
    return number


def _close_mu(actual: float, expected: float) -> bool:
    return math.isclose(actual, expected, rel_tol=0.0, abs_tol=MU_TOLERANCE)


def plan_mu_normalization_evidence(manifest: dict[str, Any]) -> dict[str, Any]:
    if manifest.get("workflow_mode") != "full_plan":
        raise ValueError(
            "Active-treatment-MU Sumtally normalization requires workflow_mode full_plan"
        )
    segments = manifest.get("segments")
    if not isinstance(segments, list) or not segments:
        raise ValueError("Manifest must contain a non-empty segments list")

    active_mu_by_beam: dict[int, float] = {}
    active_beam_metersets: dict[int, float] = {}
    skipped_beam_metersets: dict[int, float] = {}
    active_segment_mu_sum = 0.0

    for index, segment in enumerate(segments, start=1):
        if not isinstance(segment, dict):
            raise ValueError(f"Manifest segment {index} must be an object")
        label = str(segment.get("segment_id") or f"manifest segment {index}")
        beam_number = _positive_beam_number(
            segment.get("beam_number"),
            label=f"{label} beam_number",
        )
        skipped = bool(segment.get("skip_reason"))
        if skipped:
            if str(segment.get("delivery_type") or "").lower() != "unsupported":
                raise ValueError(
                    f"{label}: only unsupported non-treatment beams may be skipped"
                )
            segment_mu = _finite_number(
                segment.get("segment_mu"),
                label=f"{label} skipped segment_mu",
            )
            mu_weight = _finite_number(
                segment.get("mu_weight"),
                label=f"{label} skipped mu_weight",
            )
            if not _close_mu(segment_mu, 0.0):
                raise ValueError(f"{label}: skipped segment_mu must be zero")
            if not _close_mu(mu_weight, 0.0):
                raise ValueError(f"{label}: skipped mu_weight must be zero")
            beam_meterset = _finite_number(
                segment.get("beam_meterset_mu"),
                label=f"{label} skipped beam_meterset_mu",
            )
            if beam_number in active_mu_by_beam:
                raise ValueError(
                    f"BeamNumber {beam_number} cannot be both active and skipped"
                )
            previous = skipped_beam_metersets.get(beam_number)
            if previous is not None and not _close_mu(previous, beam_meterset):
                raise ValueError(
                    f"Skipped BeamNumber {beam_number} has inconsistent beam_meterset_mu"
                )
            skipped_beam_metersets[beam_number] = beam_meterset
            continue

        if beam_number in skipped_beam_metersets:
            raise ValueError(f"BeamNumber {beam_number} cannot be both active and skipped")
        if str(segment.get("delivery_type") or "").lower() not in {
            "3dcrt",
            "3dcrt_static",
        }:
            raise ValueError(
                f"Active segment references non-treatment BeamNumber {beam_number}"
            )
        segment_mu = _finite_number(
            segment.get("segment_mu"),
            label=f"{label} active segment_mu",
            positive=True,
        )
        mu_weight = _finite_number(
            segment.get("mu_weight"),
            label=f"{label} active mu_weight",
            positive=True,
        )
        if not _close_mu(mu_weight, segment_mu):
            raise ValueError(f"{label}: active mu_weight does not match segment_mu")
        beam_meterset = _finite_number(
            segment.get("beam_meterset_mu"),
            label=f"{label} active beam_meterset_mu",
            positive=True,
        )
        previous = active_beam_metersets.get(beam_number)
        if previous is not None and not _close_mu(previous, beam_meterset):
            raise ValueError(
                f"Active BeamNumber {beam_number} has inconsistent beam_meterset_mu"
            )
        active_beam_metersets[beam_number] = beam_meterset
        active_mu_by_beam[beam_number] = (
            active_mu_by_beam.get(beam_number, 0.0) + segment_mu
        )
        active_segment_mu_sum += segment_mu

    if not active_mu_by_beam:
        raise ValueError("At least one active treatment segment is required")
    for beam_number, beam_meterset in active_beam_metersets.items():
        if not _close_mu(active_mu_by_beam[beam_number], beam_meterset):
            raise ValueError(
                f"BeamNumber {beam_number} active segment MU does not match beam_meterset_mu"
            )

    active_treatment_beam_meterset_sum = sum(active_beam_metersets.values())
    if not _close_mu(active_segment_mu_sum, active_treatment_beam_meterset_sum):
        raise ValueError(
            "Active segment MU sum does not match active treatment beam meterset sum"
        )
    skipped_non_treatment_beam_meterset_sum = sum(
        skipped_beam_metersets.values()
    )
    reconciled_complete_mu = (
        active_segment_mu_sum + skipped_non_treatment_beam_meterset_sum
    )
    complete_totals: dict[str, float] = {}
    for key in ("plan_total_mu", "included_total_mu", "dose_normalization_mu"):
        value = _finite_number(
            manifest.get(key),
            label=f"Manifest {key}",
            positive=True,
        )
        if not _close_mu(value, reconciled_complete_mu):
            raise ValueError(
                f"Manifest {key} does not reconcile active treatment and skipped non-treatment MU"
            )
        complete_totals[key] = value

    return {
        "schema_version": PLAN_MU_NORMALIZATION_SCHEMA,
        "isumtally": 2,
        "weight_field": "segment_mu",
        "sumfactor": active_segment_mu_sum,
        "sumfactor_unit": "MU",
        "active_segment_mu_sum": active_segment_mu_sum,
        "active_treatment_beam_meterset_sum": active_treatment_beam_meterset_sum,
        "active_treatment_beams": [
            {
                "beam_number": number,
                "beam_meterset_mu": active_beam_metersets[number],
                "segment_mu_sum": active_mu_by_beam[number],
            }
            for number in sorted(active_mu_by_beam)
        ],
        "skipped_non_treatment_beam_meterset_sum": (
            skipped_non_treatment_beam_meterset_sum
        ),
        "skipped_non_treatment_beams": [
            {
                "beam_number": number,
                "beam_meterset_mu": skipped_beam_metersets[number],
                "segment_mu": 0.0,
            }
            for number in sorted(skipped_beam_metersets)
        ],
        **complete_totals,
        "reconciled_complete_mu": reconciled_complete_mu,
        "summation_rule": ACTIVE_TREATMENT_SUMMATION_RULE,
        "input_segment_dose_unit": "GY/MU",
        "output_dose_state": ACTIVE_TREATMENT_INPUT_DOSE_STATE,
        "output_dose_unit": "GY",
        "reconciled": True,
    }


def segment_weight(segment: dict[str, Any], *, weight_field: str) -> float:
    value = segment.get(weight_field)
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"beam={segment.get('beam_number')} segment={segment.get('segment_index')} has invalid {weight_field}"
        ) from exc


def dose_normalization_mu(manifest: dict[str, Any]) -> float:
    value = manifest.get("dose_normalization_mu")
    try:
        normalized = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("Manifest dose_normalization_mu must be numeric") from exc
    if normalized == 0.0:
        raise ValueError("Manifest dose_normalization_mu must be non-zero")
    return normalized


def sumfactor_for(
    manifest: dict[str, Any],
    *,
    mode: str,
    weight_field: str,
    raw_total_weight: float,
) -> tuple[float, str, dict[str, Any] | None]:
    if mode == "totalfield" and weight_field == "segment_mu":
        evidence = plan_mu_normalization_evidence(manifest)
        expected = float(evidence["active_segment_mu_sum"])
        if not _close_mu(raw_total_weight, expected):
            raise ValueError(
                "Sumtally active segment weights do not match validated active treatment MU"
            )
        return (
            expected,
            "isumtally=2 normalizes segment_mu weights; sumfactor restores the active treatment MU sum",
            evidence,
        )
    return (
        1.0,
        "no additional Sumtally normalization for this mode and weight field",
        None,
    )


def build_sumtally(
    manifest: dict[str, Any],
    *,
    case_root: Path,
    output_name: str,
    weight_field: str,
    mode: str,
    weight_normalization_mu: float | None = None,
) -> tuple[str, dict[str, Any]]:
    if mode not in {"distributed", "totalfield"}:
        raise ValueError(f"Unsupported Sumtally mode: {mode}")
    if weight_normalization_mu is not None and weight_normalization_mu <= 0:
        raise ValueError("weight_normalization_mu must be positive")
    isumtally = 1 if mode == "distributed" else 2
    rows: list[dict[str, Any]] = []
    total_weight = 0.0
    raw_total_weight = 0.0
    for segment in active_segments(manifest):
        expected_output_path = str(segment.get("expected_output_path") or "")
        resolved_path = resolve_manifest_path(case_root, expected_output_path)
        raw_weight = segment_weight(segment, weight_field=weight_field)
        weight = raw_weight / weight_normalization_mu if weight_normalization_mu is not None else raw_weight
        raw_total_weight += raw_weight
        total_weight += weight
        rows.append(
            {
                "beam_number": segment.get("beam_number"),
                "segment_index": segment.get("segment_index"),
                "expected_output_path": expected_output_path,
                "resolved_output_path": str(resolved_path),
                "raw_weight": raw_weight,
                "weight": weight,
            }
        )

    sumfactor, sumfactor_reason, normalization_evidence = sumfactor_for(
        manifest,
        mode=mode,
        weight_field=weight_field,
        raw_total_weight=raw_total_weight,
    )

    lines = [
        "sumtally start",
        f"  isumtally = {isumtally}",
        f"  sfile = {output_name}",
        f"  sumfactor = {sumfactor:.12g}",
        f"  nfile = {len(rows)}",
    ]
    for row in rows:
        lines.append(f"  {normalize_path_for_phits(row['resolved_output_path'])}  {row['weight']:.12g}")
    lines.append("sumtally end")
    lines.append("")

    summary = {
        "case_id": manifest.get("case_id"),
        "plan_uid": manifest.get("plan_uid"),
        "workflow_mode": manifest.get("workflow_mode"),
        "sumtally_mode": mode,
        "weight_field": weight_field,
        "weight_normalization_mu": weight_normalization_mu,
        "output_name": output_name,
        "segment_count": len(rows),
        "raw_total_weight": raw_total_weight,
        "total_weight": total_weight,
        "dose_normalization_mu": manifest.get("dose_normalization_mu"),
        "sumfactor": sumfactor,
        "sumfactor_reason": sumfactor_reason,
        "sumtally_normalization_evidence": normalization_evidence,
        "phits_execution_performed": False,
        "segments": rows,
    }
    return "\n".join(lines), summary


def _single_sumtally_assignment(text: str, name: str) -> str:
    matches = re.findall(
        rf"(?im)^\s*{re.escape(name)}\s*=\s*([^\s$]+)",
        text,
    )
    if len(matches) != 1:
        raise ValueError(f"Generated sumtally.inp must contain exactly one {name} assignment")
    return matches[0]


def validate_sumtally_normalization_input(
    path: Path,
    *,
    manifest: dict[str, Any],
    recorded_evidence: Any,
) -> dict[str, Any]:
    expected = plan_mu_normalization_evidence(manifest)
    if recorded_evidence != expected:
        raise ValueError(
            "Sumtally normalization evidence is missing or does not match the current manifest; "
            "rerun Sumtally Generate"
        )
    text = path.read_text(encoding="utf-8", errors="strict")
    try:
        isumtally = int(_single_sumtally_assignment(text, "isumtally"))
        nfile = int(_single_sumtally_assignment(text, "nfile"))
        sumfactor = float(_single_sumtally_assignment(text, "sumfactor"))
    except ValueError as exc:
        raise ValueError(
            "Generated sumtally.inp has invalid normalization controls; rerun Sumtally Generate"
        ) from exc
    if isumtally != 2:
        raise ValueError(
            "Generated sumtally.inp isumtally does not match the active treatment MU contract"
        )
    if not _close_mu(sumfactor, float(expected["sumfactor"])):
        raise ValueError(
            "Generated sumtally.inp sumfactor does not match validated active treatment MU"
        )

    block_match = re.search(
        r"(?ims)^\s*sumtally\s+start\s*$([\s\S]*?)^\s*sumtally\s+end\s*$",
        text,
    )
    if block_match is None:
        raise ValueError("Generated sumtally.inp is missing its Sumtally block")
    assignment_names = {"isumtally", "sfile", "sumfactor", "nfile"}
    weights: list[float] = []
    for raw_line in block_match.group(1).splitlines():
        line = raw_line.strip()
        if not line or line.startswith("$"):
            continue
        assignment = re.match(r"^([A-Za-z0-9_]+)\s*=", line)
        if assignment is not None and assignment.group(1).lower() in assignment_names:
            continue
        parts = line.rsplit(None, 1)
        if len(parts) != 2:
            raise ValueError(
                "Generated sumtally.inp has an invalid weighted-file row; rerun Sumtally Generate"
            )
        try:
            weight = float(parts[1])
        except ValueError as exc:
            raise ValueError(
                "Generated sumtally.inp has an invalid segment weight; rerun Sumtally Generate"
            ) from exc
        if not math.isfinite(weight):
            raise ValueError(
                "Generated sumtally.inp has a non-finite segment weight; rerun Sumtally Generate"
            )
        weights.append(weight)

    expected_weights = [
        _finite_number(
            segment.get("segment_mu"),
            label="Active segment_mu",
            positive=True,
        )
        for segment in active_segments(manifest)
    ]
    if nfile != len(expected_weights) or len(weights) != len(expected_weights):
        raise ValueError(
            "Generated sumtally.inp nfile does not match active treatment segments"
        )
    if any(
        not _close_mu(actual, expected_weight)
        for actual, expected_weight in zip(weights, expected_weights)
    ):
        raise ValueError(
            "Generated sumtally.inp weights do not match active segment MU"
        )
    return expected


def resolve_relative_path_for_phits(path: str | Path, base_dir: Path) -> str:
    text = str(path).strip()
    if is_portable_absolute_path(text):
        return normalize_path_for_phits(text)
    return normalize_path_for_phits((Path(base_dir) / text).resolve())


def resolve_include_path_for_sumtally(include_path: str, base_dir: Path) -> str:
    resolved = resolve_relative_path_for_phits(include_path, base_dir)
    return resolved.replace("/phits_inputs/production_assets/", "/production_assets/").replace(
        "\\phits_inputs\\production_assets\\", "\\production_assets\\"
    )


def localize_phits_output_file_reference(line: str, output_dir: Path, base_dir: Path) -> str | None:
    if Path(output_dir).resolve() == Path(base_dir).resolve():
        return None
    stripped = line.rstrip("\r\n")
    match = re.match(r"^(\s*file\(\s*6\s*\)\s*=\s*)(\S+)(.*)$", stripped, re.IGNORECASE)
    if not match:
        return None
    path_text = match.group(2).strip()
    if not path_text or is_portable_absolute_path(path_text):
        return None
    eol = "\r\n" if "\r\n" in line else "\n"
    local_name = Path(path_text.replace("\\", "/")).name or "phits.out"
    return f"{match.group(1)}{local_name}{match.group(3)}{eol}"


def get_section_pattern(name: str) -> str:
    chars = [re.escape(char) for char in name]
    return r"\[\s*" + r"\s*".join(chars) + r"\s*\]"


def is_target_tally_line(file_line: str, patterns: list[str]) -> bool:
    return any(pattern in file_line for pattern in patterns)


def is_tally_section_header(line: str) -> bool:
    match = re.match(r"^\s*\[([^\]]+)\]", line)
    if not match:
        return False
    compact_name = re.sub(r"\s+", "", match.group(1)).lower()
    return compact_name.startswith("t-")


def section_header_has_off(line: str) -> bool:
    match = re.match(r"^\s*\[[^\]]+\]\s*(\S+)?", line)
    return bool(match and match.group(1) and match.group(1).lower() == "off")


def add_off_to_section_header(line: str) -> str:
    if section_header_has_off(line):
        return line
    eol = "\r\n" if line.endswith("\r\n") else "\n" if line.endswith("\n") else ""
    body = line[: -len(eol)] if eol else line
    return re.sub(r"(\])", r"\1 off", body, count=1) + eol


def disable_non_target_tally_sections(
    lines: list[str],
    patterns: list[str],
    sumtally_filename: str,
) -> list[str]:
    result: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if not is_tally_section_header(line):
            result.append(line)
            i += 1
            continue

        j = i + 1
        while j < len(lines) and not re.match(r"^\s*\[", lines[j]):
            j += 1
        section = lines[i:j]
        section_text = "".join(section)
        is_target = (
            any(is_target_tally_line(section_line, patterns) for section_line in section)
            and re.search(rf"infl:\s*\{{\s*{re.escape(sumtally_filename)}\s*\}}", section_text, re.IGNORECASE)
        )
        if is_target:
            result.extend(section)
        else:
            result.append(add_off_to_section_header(section[0]))
            result.extend(section[1:])
        i = j
    return result


def inject_sumtally_include_into_target_tallies(
    lines: list[str],
    patterns: list[str],
    sumtally_filename: str,
) -> list[str]:
    result: list[str] = []
    i = 0
    include_pattern = re.compile(rf"infl:\s*\{{\s*{re.escape(sumtally_filename)}\s*\}}", re.IGNORECASE)
    while i < len(lines):
        line = lines[i]
        if not is_tally_section_header(line):
            result.append(line)
            i += 1
            continue

        j = i + 1
        while j < len(lines) and not re.match(r"^\s*\[", lines[j]):
            j += 1
        section = lines[i:j]
        section_text = "".join(section)
        is_target = any(is_target_tally_line(section_line, patterns) for section_line in section)
        has_include = include_pattern.search(section_text) is not None
        if not is_target or has_include:
            result.extend(section)
            i = j
            continue

        inserted = False
        for section_line in section:
            result.append(section_line)
            if not inserted and is_target_tally_line(section_line, patterns):
                eol = "\r\n" if "\r\n" in section_line else "\n"
                result.append(f" infl:{{{sumtally_filename}}}{eol}")
                inserted = True
        i = j
    return result


def generate_sum_inp(
    base_inp_path: Path,
    out_files: list[tuple[str, float]],
    sfile: str,
    sumfactor: float,
    mode: str,
    tally_patterns: list[str],
    output_path: Path,
    sumtally_filename: str = "sumtally.inp",
    include_base_dir: Path | None = None,
    output_dir_basis: Path | None = None,
) -> Path:
    del out_files, sfile, sumfactor, mode
    content = base_inp_path.read_text(encoding="utf-8", errors="replace")

    base_dir = Path(base_inp_path).resolve().parent
    include_dir = (
        Path(include_base_dir).resolve()
        if include_base_dir is not None
        else base_dir
    )
    output_dir = (
        Path(output_dir_basis).resolve()
        if output_dir_basis is not None
        else Path(output_path).resolve().parent
    )
    lines = content.splitlines(keepends=True)
    preferred_eol = "\r\n" if "\r\n" in content else "\n"
    new_lines: list[str] = [
        f"$OMP = {DEFAULT_SUMTALLY_OMP_THREADS}{preferred_eol}"
    ]

    params_active = False
    params_pattern = get_section_pattern("Parameters")
    icntl_done = False
    maxcas_done = False
    maxbch_done = False

    def append_missing_sumtally_parameters() -> None:
        nonlocal maxcas_done, maxbch_done
        if not maxcas_done:
            new_lines.append(
                f"  maxcas = {DEFAULT_SUMTALLY_MAXCAS}{preferred_eol}"
            )
            maxcas_done = True
        if not maxbch_done:
            new_lines.append(
                f"  maxbch = {DEFAULT_SUMTALLY_MAXBCH}{preferred_eol}"
            )
            maxbch_done = True

    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.rstrip("\r\n")

        if re.match(r"^\s*\$OMP\s*=", stripped, re.IGNORECASE):
            i += 1
            continue

        if re.search(params_pattern, stripped, re.IGNORECASE):
            params_active = True
            new_lines.append(line)
            i += 1
            continue

        if params_active:
            if re.match(r"^\s*\[", stripped) and not re.search(params_pattern, stripped, re.IGNORECASE):
                append_missing_sumtally_parameters()
                params_active = False
            elif re.match(r"^\s*maxcas\s*=", stripped, re.IGNORECASE):
                eol = "\r\n" if "\r\n" in line else "\n"
                new_lines.append(f"  maxcas = {DEFAULT_SUMTALLY_MAXCAS}{eol}")
                maxcas_done = True
                i += 1
                continue
            elif re.match(r"^\s*maxbch\s*=", stripped, re.IGNORECASE):
                eol = "\r\n" if "\r\n" in line else "\n"
                new_lines.append(f"  maxbch = {DEFAULT_SUMTALLY_MAXBCH}{eol}")
                maxbch_done = True
                i += 1
                continue
            elif re.match(r"^\s*icntl\s*=", stripped, re.IGNORECASE):
                eol = "\r\n" if "\r\n" in line else "\n"
                new_lines.append(f"  icntl = 13{eol}")
                icntl_done = True
                i += 1
                continue

        if re.match(r"^\s*epsout\s*=", stripped, re.IGNORECASE):
            eol = "\r\n" if "\r\n" in line else "\n"
            indent = re.match(r"^(\s*)", line).group(1)
            new_lines.append(f"{indent}epsout = 0{eol}")
            i += 1
            continue

        localized_file_ref = localize_phits_output_file_reference(line, output_dir, base_dir)
        if localized_file_ref is not None:
            new_lines.append(localized_file_ref)
            i += 1
            continue

        if re.match(r"^\s*\$\s*infl:\s*\{sumtally\.inp\}", stripped, re.IGNORECASE):
            eol = "\r\n" if "\r\n" in line else "\n"
            new_lines.append(f" infl:{{{sumtally_filename}}}{eol}")
            i += 1
            continue

        if output_dir != base_dir:
            infl_match = re.match(r"^(\s*infl:\s*\{)([^}]+)(\})(.*)$", stripped, re.IGNORECASE)
            if infl_match:
                include_path = infl_match.group(2).strip()
                if Path(include_path.replace("\\", "/")).name.lower() == "libpath.inp":
                    eol = "\r\n" if "\r\n" in line else "\n"
                    new_lines.append(f"{infl_match.group(1)}libpath.inp{infl_match.group(3)}{infl_match.group(4)}{eol}")
                    i += 1
                    continue
                if include_path.lower() not in {sumtally_filename.lower(), "sumtally.inp"}:
                    eol = "\r\n" if "\r\n" in line else "\n"
                    resolved_include = resolve_include_path_for_sumtally(
                        include_path,
                        include_dir,
                    )
                    new_lines.append(
                        f"{infl_match.group(1)}{resolved_include}{infl_match.group(3)}{infl_match.group(4)}{eol}"
                    )
                    i += 1
                    continue

        new_lines.append(line)
        i += 1

    if params_active:
        append_missing_sumtally_parameters()

    if not icntl_done:
        result: list[str] = []
        for line in new_lines:
            result.append(line)
            if re.search(params_pattern, line.rstrip("\r\n"), re.IGNORECASE):
                eol = "\r\n" if "\r\n" in line else "\n"
                result.append(f"  icntl = 13{eol}")
        new_lines = result

    new_lines = inject_sumtally_include_into_target_tallies(new_lines, tally_patterns, sumtally_filename)
    new_lines = disable_non_target_tally_sections(new_lines, tally_patterns, sumtally_filename)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("".join(new_lines), encoding="utf-8", newline="")
    return output_path


def loads_json_object(text: str) -> dict[str, Any]:
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError("JSON root must be an object")
    return data
