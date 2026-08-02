from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path
from typing import Any


TARGET_TALLY_PATTERNS = ["deposit-target-3D", "deposit_target"]


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
    total_weight: float,
) -> tuple[float, str]:
    if mode == "totalfield" and weight_field == "segment_mu":
        normalization_mu = dose_normalization_mu(manifest)
        return (
            total_weight / normalization_mu,
            "totalfield segment_mu weights normalized by total_segment_mu / dose_normalization_mu",
        )
    return 1.0, "no additional Sumtally normalization for this mode and weight field"


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

    if weight_normalization_mu is not None:
        sumfactor = 1.0
        sumfactor_reason = (
            f"{weight_field} values divided by weight_normalization_mu={weight_normalization_mu:g}; "
            "Sumtally weights are coefficients and PHITS2DICOM applies the Beam MU factor later."
        )
    else:
        sumfactor, sumfactor_reason = sumfactor_for(
            manifest,
            mode=mode,
            weight_field=weight_field,
            total_weight=total_weight,
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
        "phits_execution_performed": False,
        "segments": rows,
    }
    return "\n".join(lines), summary


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
) -> Path:
    del out_files, sfile, sumfactor, mode
    content = base_inp_path.read_text(encoding="utf-8", errors="replace")

    base_dir = Path(base_inp_path).resolve().parent
    include_dir = (
        Path(include_base_dir).resolve()
        if include_base_dir is not None
        else base_dir
    )
    output_dir = Path(output_path).resolve().parent
    lines = content.splitlines(keepends=True)
    new_lines: list[str] = []

    params_active = False
    params_pattern = get_section_pattern("Parameters")
    icntl_done = False

    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.rstrip("\r\n")

        if re.search(params_pattern, stripped, re.IGNORECASE):
            params_active = True
            new_lines.append(line)
            i += 1
            continue

        if params_active:
            if re.match(r"^\s*\[", stripped) and not re.search(params_pattern, stripped, re.IGNORECASE):
                params_active = False
            elif re.match(r"^\s*icntl\s*=", stripped, re.IGNORECASE):
                eol = "\r\n" if "\r\n" in line else "\n"
                new_lines.append(f"  icntl = 13{eol}")
                icntl_done = True
                i += 1
                continue
            elif re.match(r"^\s*\$OMP\s*=", stripped, re.IGNORECASE):
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
