from __future__ import annotations

import argparse
import json
import math
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pydicom

from dicomxphits.dose_semantics import (
    mark_rtdose_absolute,
    public_absolute_dose_semantics,
    require_absolute_units,
)
from dicomxphits.fix_coordinates import (
    coordinate_summary_path,
    corrected_rtdose_path,
    fix_coordinates,
)
from dicomxphits.prepare_3dcrt_workspace import (
    ExternalToolPaths,
    load_paths_config,
    merged_tool_paths,
    write_json,
)
from dicomxphits.prepare_sumtally import load_json_object, resolve_workspace_path
from dicomxphits.rtdose_plan_references import (
    synchronize_plan_rtdose,
    validate_full_plan_context,
    validate_plan_rtdose,
)
from dicomxphits.sumtally_inputs import file_sha256, manifest_sha256


INPUT_DOSE_STATE = "sumtally_mu_weighted"
SUMTALLY_NORMALIZATION = "all_segments_totalfield_segment_mu"
IS_BEAM_MU_OUTPUT = False
DEFAULT_INPUT_DOSE_UNIT = "gy_per_mu"
DEFAULT_OUTPUT_DICOM_DOSE_UNIT = "GY"
NORM_MODE_FACTOR = "2"
IPP_PATTERN = re.compile(
    r"ImagePositionPatient\s+([-+]?\d*\.?\d+(?:[Ee][-+]?\d+)?)\s+"
    r"([-+]?\d*\.?\d+(?:[Ee][-+]?\d+)?)\s+"
    r"([-+]?\d*\.?\d+(?:[Ee][-+]?\d+)?)"
)
PHITS2DICOM_REQUIRED_TEMPLATE_TAGS = [
    # Tags that phits2dicom must be able to overwrite for this public adapter.
    # The set is intentionally compatible with the official RTphits sample.dcm;
    # other phits2dicom dictionary tags may be absent there yet still convert.
    (0x0008, 0x0012),
    (0x0008, 0x0013),
    (0x0008, 0x0020),
    (0x0008, 0x0023),
    (0x0008, 0x0030),
    (0x0008, 0x0033),
    (0x0008, 0x0060),
    (0x0008, 0x0070),
    (0x0008, 0x0080),
    (0x0008, 0x1010),
    (0x0008, 0x1040),
    (0x0008, 0x1090),
    (0x0010, 0x0010),
    (0x0010, 0x0020),
    (0x0010, 0x0030),
    (0x0010, 0x0040),
    (0x0018, 0x1000),
    (0x0018, 0x1020),
    (0x0020, 0x0010),
    (0x0020, 0x0011),
    (0x0020, 0x0013),
    (0x0020, 0x0032),
    (0x0020, 0x0037),
    (0x0020, 0x0052),
    (0x0020, 0x1040),
    (0x0028, 0x0008),
    (0x0028, 0x0009),
    (0x0028, 0x0010),
    (0x0028, 0x0011),
    (0x0028, 0x0030),
    (0x0028, 0x0100),
    (0x0028, 0x0101),
    (0x0028, 0x0102),
    (0x3004, 0x0004),
    (0x3004, 0x0008),
    (0x3004, 0x000C),
    (0x3004, 0x000E),
    (0x7FE0, 0x0010),
    (0x0028, 0x0103),
]


@dataclass(frozen=True)
class CTReferenceSelection:
    source_path: Path
    workspace_path: Path
    source: str


def normalize_slash_path(path: str | Path, *, is_dir: bool = False) -> str:
    text = str(path).replace("\\", "/")
    normalized = Path(text).absolute().as_posix() if ":" not in text else text
    if is_dir and not normalized.endswith("/"):
        normalized += "/"
    return normalized


def read_paths_config(path: Path | None) -> dict[str, Any]:
    if path is None:
        return {}
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError(f"Path config must be a JSON object: {path}")
    return data


def path_config_ct_reference(path_config: dict[str, Any]) -> Path | None:
    value = str(path_config.get("ct_reference_dicom_path") or "").strip()
    return Path(value) if value else None


def require_existing_file(path: Path, *, label: str, non_empty: bool = False) -> None:
    if not path.is_file():
        raise FileNotFoundError(f"{label} not found: {path}")
    if non_empty and path.stat().st_size <= 0:
        raise ValueError(f"{label} is empty: {path}")


def require_workspace_file(path: Path, *, workspace_root: Path, label: str) -> Path:
    resolved = path.resolve()
    workspace_resolved = workspace_root.resolve()
    try:
        resolved.relative_to(workspace_resolved)
    except ValueError as exc:
        raise ValueError(f"{label} must be inside workspace root for public RTDOSE prepare: {path}") from exc
    return resolved


def prepare_summary_path(workspace_root: Path) -> Path:
    return workspace_root / "analysis" / "rtdose_conversion_prepare_summary.json"


def execution_summary_path(workspace_root: Path) -> Path:
    return workspace_root / "analysis" / "rtdose_conversion_execution_summary.json"


def write_failure_summary(
    *,
    path: Path,
    stage: str,
    workspace_root: Path,
    reason: str,
    command_argv: list[str] | None = None,
    extra: dict[str, Any] | None = None,
    stage_status: str = "gate_failed",
) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "schema_version": "dicomxphits_public_rtdose_stage_v1",
        "stage": stage,
        "stage_status": stage_status,
        "workspace_root": str(workspace_root),
        "failure_reason": reason,
        "command": {"argv": command_argv or sys.argv},
        "returncode": None,
        "phits2dicom_execution_started": False,
    }
    if extra:
        summary.update(extra)
    write_json(path, summary)
    return summary


def load_sumtally_summaries(workspace_root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    generation_path = workspace_root / "analysis" / "sumtally_generation_summary.json"
    execution_path = workspace_root / "analysis" / "sumtally_execution_summary.json"
    generation = load_json_object(generation_path)
    execution = load_json_object(execution_path)
    if generation.get("stage_status") != "success":
        raise ValueError("Sumtally generation summary is not successful")
    if execution.get("stage_status") != "success":
        raise ValueError("Sumtally execution summary is not successful")
    return generation, execution


def validate_sumtally_manifest_binding(
    *,
    workspace_root: Path,
    generation: dict[str, Any],
    execution: dict[str, Any],
    verify_sumtally_output: bool = True,
) -> dict[str, Any]:
    manifest_path = workspace_root / "segments" / "segment_manifest.json"
    manifest = load_json_object(manifest_path)
    current_sha256 = manifest_sha256(manifest)
    generation_sha256 = str(generation.get("manifest_sha256") or "")
    execution_sha256 = str(execution.get("manifest_sha256") or "")
    if not generation_sha256 or not execution_sha256:
        raise ValueError(
            "Sumtally manifest digest evidence is missing; rerun Sumtally "
            "Generate and Sumtally Run"
        )
    if generation_sha256 != current_sha256:
        raise ValueError(
            "Segment manifest does not match Sumtally Generate evidence; "
            "rerun Sumtally Generate and Sumtally Run"
        )
    if execution_sha256 != generation_sha256:
        raise ValueError(
            "Sumtally Run evidence does not match Sumtally Generate; "
            "rerun Sumtally Run"
        )
    input_digests: dict[str, str] = {}
    for field in ("sum_input_sha256", "sumtally_input_sha256"):
        generation_input_sha256 = str(generation.get(field) or "")
        execution_input_sha256 = str(execution.get(field) or "")
        if not generation_input_sha256 or not execution_input_sha256:
            raise ValueError(
                "Sumtally input digest evidence is missing; rerun Sumtally "
                "Generate and Sumtally Run"
            )
        if execution_input_sha256 != generation_input_sha256:
            raise ValueError(
                "Sumtally Run input evidence does not match Sumtally Generate; "
                "rerun Sumtally Run"
            )
        input_digests[field] = generation_input_sha256
    generation_outputs = generation.get("outputs")
    if not isinstance(generation_outputs, dict):
        raise ValueError("Sumtally Generate evidence is missing outputs")
    generation_output_value = str(generation_outputs.get("sumtally_output") or "")
    execution_output_value = str(execution.get("expected_sumtally_output") or "")
    if not generation_output_value or not execution_output_value:
        raise ValueError(
            "Sumtally output path evidence is missing; rerun Sumtally Generate "
            "and Sumtally Run"
        )
    generation_output = resolve_workspace_path(
        workspace_root,
        generation_output_value,
    ).resolve()
    execution_output = resolve_workspace_path(
        workspace_root,
        execution_output_value,
    ).resolve()
    if execution_output != generation_output:
        raise ValueError(
            "Sumtally Run output path does not match Sumtally Generate; "
            "rerun Sumtally Run"
        )
    if execution.get("expected_sumtally_output_updated_by_run") is not True:
        raise ValueError(
            "Sumtally Run did not prove that it updated the expected output; "
            "rerun Sumtally Run"
        )
    execution_output_sha256 = str(
        execution.get("expected_sumtally_output_sha256") or ""
    )
    if not execution_output_sha256:
        raise ValueError(
            "Sumtally output digest evidence is missing; rerun Sumtally Run"
        )
    if verify_sumtally_output:
        require_existing_file(
            generation_output,
            label="Sumtally PHITS dose output",
            non_empty=True,
        )
        if file_sha256(generation_output) != execution_output_sha256:
            raise ValueError(
                "Sumtally output content does not match Sumtally Run evidence; "
                "rerun Sumtally Run"
            )
    return {
        "manifest_path": str(manifest_path),
        "manifest_sha256": current_sha256,
        "generation_manifest_sha256": generation_sha256,
        "execution_manifest_sha256": execution_sha256,
        **input_digests,
        "sumtally_output_path": str(generation_output),
        "sumtally_output_sha256": execution_output_sha256,
        "validated": True,
    }


def validate_sumtally_contract(
    generation: dict[str, Any],
    *,
    input_dose_unit: str,
    output_dicom_dose_unit: str,
) -> tuple[float, str]:
    hint = generation.get("rt_dose_conversion_hint")
    if not isinstance(hint, dict):
        raise ValueError("Sumtally generation summary is missing rt_dose_conversion_hint")
    if hint.get("input_dose_state") != INPUT_DOSE_STATE:
        raise ValueError("Unsupported input_dose_state for PR E")
    if bool(hint.get("is_beam_mu_output")) is not IS_BEAM_MU_OUTPUT:
        raise ValueError("PR E does not accept per-beam beamMU Sumtally output")
    if hint.get("sumtally_normalization") != SUMTALLY_NORMALIZATION:
        raise ValueError("Unsupported sumtally_normalization for PR E")
    require_absolute_units(
        input_dose_unit=input_dose_unit,
        output_dicom_dose_unit=output_dicom_dose_unit,
    )
    return (
        1.0,
        "Factor 1.0 selected because the approved public-model "
        "totfact_per_MU was already applied in each PHITS input before "
        "all-active-segments totalfield Sumtally.",
    )


def select_phits_dose(generation: dict[str, Any]) -> Path:
    outputs = generation.get("outputs")
    if not isinstance(outputs, dict):
        raise ValueError("Sumtally generation summary is missing outputs")
    value = outputs.get("sumtally_output")
    if not value:
        raise ValueError("Sumtally generation summary is missing outputs.sumtally_output")
    return Path(str(value))


def metadata_phits_out_candidates(workspace_root: Path, generation: dict[str, Any], execution: dict[str, Any]) -> list[Path]:
    candidates: list[Path] = []
    for data in (generation, execution):
        for key in ("phits_out", "phits_out_path", "companion_phits_out"):
            value = data.get(key)
            if value:
                candidates.append(resolve_workspace_path(workspace_root, str(value)))
        outputs = data.get("outputs")
        if isinstance(outputs, dict):
            for key in ("phits_out", "phits_out_path", "companion_phits_out"):
                value = outputs.get(key)
                if value:
                    candidates.append(resolve_workspace_path(workspace_root, str(value)))
    return candidates


def select_phits_out(
    *,
    workspace_root: Path,
    generation: dict[str, Any],
    execution: dict[str, Any],
    explicit_phits_out: Path | None,
) -> tuple[Path, str]:
    if explicit_phits_out is not None:
        return resolve_workspace_path(workspace_root, explicit_phits_out), "explicit_phits_out"
    for candidate in metadata_phits_out_candidates(workspace_root, generation, execution):
        if candidate.is_file():
            return candidate, "workspace_metadata"
    raise FileNotFoundError("phits_out companion file not found; provide --phits-out")


def copy_template(template_dicom: Path, workspace_root: Path) -> Path:
    require_existing_file(template_dicom, label="template DICOM")
    dest = workspace_root / "rtdose" / "template.dcm"
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(template_dicom, dest)
    return dest


def dicom_tag_label(tag: tuple[int, int]) -> str:
    keyword = pydicom.datadict.keyword_for_tag(tag)
    hex_tag = f"({tag[0]:04x},{tag[1]:04x})"
    return f"{hex_tag} {keyword}" if keyword else hex_tag


def phits2dicom_template_preflight(template_dicom: Path) -> dict[str, Any]:
    ds = pydicom.dcmread(str(template_dicom), force=True)
    missing = [tag for tag in PHITS2DICOM_REQUIRED_TEMPLATE_TAGS if tag not in ds]
    missing_labels = [dicom_tag_label(tag) for tag in missing]
    summary = {
        "template_dicom_path": str(template_dicom),
        "required_tag_count": len(PHITS2DICOM_REQUIRED_TEMPLATE_TAGS),
        "missing_tag_count": len(missing),
        "missing_tags": missing_labels,
    }
    if missing:
        preview = ", ".join(missing_labels[:8])
        suffix = "" if len(missing_labels) <= 8 else f", ... (+{len(missing_labels) - 8} more)"
        raise ValueError(
            "phits2dicom template preflight failed: missing required overwrite tag(s): "
            f"{preview}{suffix}"
        )
    return summary


def metadata_generated_ct_candidates(workspace_root: Path) -> list[Path]:
    candidates: list[Path] = []
    for path in (
        workspace_root / "analysis" / "public_preparation_workspace_summary.json",
        workspace_root / "analysis" / "rtdose_conversion_prepare_summary.json",
    ):
        if not path.is_file():
            continue
        data = load_json_object(path)
        for key in ("generated_ct_reference_dicom", "generated_ct_reference_dicom_path", "ct_reference_dicom"):
            value = data.get(key)
            if value:
                candidates.append(resolve_workspace_path(workspace_root, str(value)))
        outputs = data.get("outputs")
        if isinstance(outputs, dict):
            for key in ("generated_ct_reference_dicom", "ct_reference_dicom"):
                value = outputs.get(key)
                if value:
                    candidates.append(resolve_workspace_path(workspace_root, str(value)))
    return candidates


def select_ct_reference(
    *,
    workspace_root: Path,
    paths_config: dict[str, Any],
    explicit_ct_reference: Path | None,
    generated_ct_reference: Path | None,
    smoke_dummy_ct_reference: Path | None,
) -> tuple[Path, str]:
    choices = [
        (explicit_ct_reference, "explicit_ct_reference"),
        (path_config_ct_reference(paths_config), "paths_config_ct_reference"),
        (generated_ct_reference, "generated_ct_reference"),
    ]
    for path, source in choices:
        if path is not None:
            return resolve_workspace_path(workspace_root, path), source
    for candidate in metadata_generated_ct_candidates(workspace_root):
        if candidate.is_file():
            return candidate, "workspace_generated_ct_reference"
    if smoke_dummy_ct_reference is not None:
        return resolve_workspace_path(workspace_root, smoke_dummy_ct_reference), "explicit_smoke_dummy_ct_reference"
    raise FileNotFoundError("CT reference DICOM not found")


def copy_and_optionally_sync_ct(
    *,
    source_ct: Path,
    workspace_root: Path,
    selection_source: str,
    reference_dicom_for_identity: Path | None,
) -> tuple[CTReferenceSelection, dict[str, Any] | None]:
    require_existing_file(source_ct, label="CT reference DICOM")
    dest = workspace_root / "rtdose" / "ct_reference.dcm"
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source_ct, dest)
    sync_summary = None
    if reference_dicom_for_identity is not None:
        require_existing_file(reference_dicom_for_identity, label="reference DICOM for identity")
        ct = pydicom.dcmread(str(dest))
        reference = pydicom.dcmread(str(reference_dicom_for_identity), stop_before_pixels=True)
        copied: dict[str, str] = {}
        for attr in ("FrameOfReferenceUID", "StudyInstanceUID", "PatientID", "PatientName"):
            value = getattr(reference, attr, None)
            if value not in (None, ""):
                setattr(ct, attr, value)
                copied[attr] = str(value)
        ct.Modality = "CT"
        copied["Modality"] = "CT"
        ct.save_as(str(dest))
        sync_summary = {
            "source_ct_reference_path": str(source_ct),
            "workspace_ct_reference_path": str(dest),
            "reference_dicom_for_identity": str(reference_dicom_for_identity),
            "copied": copied,
        }
    return CTReferenceSelection(source_path=source_ct, workspace_path=dest, source=selection_source), sync_summary


def numeric_image_position_patient(dicom_path: Path) -> list[float]:
    ds = pydicom.dcmread(str(dicom_path), stop_before_pixels=True)
    ipp = getattr(ds, "ImagePositionPatient", None)
    if ipp is None:
        raise ValueError(f"CT reference ImagePositionPatient is missing: {dicom_path}")
    try:
        values = [float(value) for value in ipp]
    except (TypeError, ValueError) as exc:
        raise ValueError(f"CT reference ImagePositionPatient is malformed: {dicom_path}") from exc
    if len(values) != 3 or not all(math.isfinite(value) for value in values):
        raise ValueError(f"CT reference ImagePositionPatient must contain three finite numeric values: {dicom_path}")
    return values


def ipp_title(ipp: list[float]) -> str:
    return f"(ImagePositionPatient  {ipp[0]:.5f}  {ipp[1]:.5f}  {ipp[2]:.5f} mm)"


def parse_title_ipp(title_line: str) -> list[float] | None:
    match = IPP_PATTERN.search(title_line)
    if not match:
        return None
    return [float(match.group(index)) for index in range(1, 4)]


def close_ipp(actual: list[float], expected: list[float]) -> bool:
    rounded_expected = [float(f"{value:.5f}") for value in expected]
    return all(math.isclose(a, b, rel_tol=0.0, abs_tol=5.0e-6) for a, b in zip(actual, rounded_expected))


def is_t_deposit_header(line: str) -> bool:
    match = re.match(r"^\s*\[([^\]]+)\]", line)
    if not match:
        return False
    compact = re.sub(r"\s+", "", match.group(1)).lower()
    return compact == "t-deposit"


def is_section_header(line: str) -> bool:
    return re.match(r"^\s*\[[^\]]+\]", line) is not None


def patch_deposit_title_ipp(path: Path, *, ipp: list[float], write_changes: bool = True) -> dict[str, Any]:
    size_before = path.stat().st_size
    original = path.read_text(encoding="utf-8", errors="replace")
    lines = original.splitlines(keepends=True)
    patched_count = 0
    skipped_existing = 0
    warnings: list[str] = []
    gate_failures: list[str] = []
    in_t_deposit = False
    new_lines: list[str] = []
    replacement_title = ipp_title(ipp)

    for line in lines:
        if is_section_header(line):
            in_t_deposit = is_t_deposit_header(line)
        if in_t_deposit and re.match(r"^\s*title\s*=", line, re.IGNORECASE):
            if "ImagePositionPatient" in line:
                skipped_existing += 1
                existing = parse_title_ipp(line)
                if existing is None:
                    gate_failures.append(f"{path}: existing ImagePositionPatient title is malformed")
                elif not close_ipp(existing, ipp):
                    gate_failures.append(f"{path}: existing ImagePositionPatient differs from CT reference")
                new_lines.append(line)
                continue
            eol = "\r\n" if line.endswith("\r\n") else "\n" if line.endswith("\n") else ""
            prefix_match = re.match(r"^(\s*title\s*=\s*)", line, re.IGNORECASE)
            prefix = prefix_match.group(1) if prefix_match else "  title = "
            new_lines.append(f"{prefix}{replacement_title}{eol}")
            patched_count += 1
            continue
        new_lines.append(line)

    updated = "".join(new_lines)
    if gate_failures:
        updated = original
        patched_count = 0
        warnings.extend(gate_failures)
    content_changed = updated != original
    if content_changed and write_changes:
        path.write_text(updated, encoding="utf-8", newline="")
    size_after = path.stat().st_size
    return {
        "path": str(path),
        "file_size_before": size_before,
        "file_size_after": size_after,
        "content_changed": content_changed,
        "write_changes": write_changes,
        "patched_title_count": patched_count,
        "skipped_existing_ipp": skipped_existing,
        "warnings": warnings,
        "gate_failures": gate_failures,
    }


def patch_rtdose_inputs_for_ipp(
    *,
    workspace_root: Path,
    phits_dose: Path,
    phits_out: Path,
    ct_reference_workspace_copy: Path,
) -> dict[str, Any]:
    workspace_phits_dose = require_workspace_file(phits_dose, workspace_root=workspace_root, label="phits_dose")
    workspace_phits_out = require_workspace_file(phits_out, workspace_root=workspace_root, label="phits_out")
    ipp = numeric_image_position_patient(ct_reference_workspace_copy)
    preflight_files = [
        patch_deposit_title_ipp(workspace_phits_dose, ipp=ipp, write_changes=False),
        patch_deposit_title_ipp(workspace_phits_out, ipp=ipp, write_changes=False),
    ]
    gate_failures = [failure for item in preflight_files for failure in item["gate_failures"]]
    if gate_failures:
        raise ValueError("ImagePositionPatient title gate failure: " + "; ".join(gate_failures))
    files = [
        patch_deposit_title_ipp(workspace_phits_dose, ipp=ipp),
        patch_deposit_title_ipp(workspace_phits_out, ipp=ipp),
    ]
    return {
        "image_position_patient": ipp,
        "files": files,
        "warnings": [warning for item in files for warning in item["warnings"]],
        "gate_failures": gate_failures,
    }


def phits2dicom_input_content(
    *,
    template_dicom: Path,
    ct_reference: Path,
    phits_dose: Path,
    phits_out: Path,
    dat_dir: Path,
    factor: float,
) -> str:
    lines = [
        "PHITS2DICOM",
        normalize_slash_path(template_dicom),
        normalize_slash_path(ct_reference),
        normalize_slash_path(phits_dose),
        normalize_slash_path(phits_out),
        normalize_slash_path(dat_dir, is_dir=True),
        NORM_MODE_FACTOR,
        f"{factor:.12g}",
        "",
    ]
    return "\n".join(lines)


def write_text_lf(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\n")


def prepare_rtdose(
    *,
    workspace_root: Path,
    paths: ExternalToolPaths,
    paths_config: dict[str, Any],
    template_dicom: Path,
    rtplan_path: Path | None = None,
    ct_reference_dicom: Path | None = None,
    generated_ct_reference_dicom: Path | None = None,
    smoke_dummy_ct_reference: Path | None = None,
    reference_dicom_for_identity: Path | None = None,
    phits_out: Path | None = None,
    input_dose_unit: str = DEFAULT_INPUT_DOSE_UNIT,
    output_dicom_dose_unit: str = DEFAULT_OUTPUT_DICOM_DOSE_UNIT,
    command_argv: list[str] | None = None,
) -> dict[str, Any]:
    summary_path = prepare_summary_path(workspace_root)
    try:
        generation, execution = load_sumtally_summaries(workspace_root)
        sumtally_manifest_binding = validate_sumtally_manifest_binding(
            workspace_root=workspace_root,
            generation=generation,
            execution=execution,
        )
        factor, factor_reason = validate_sumtally_contract(
            generation,
            input_dose_unit=input_dose_unit,
            output_dicom_dose_unit=output_dicom_dose_unit,
        )
        phits_dose = select_phits_dose(generation)
        require_existing_file(phits_dose, label="Sumtally PHITS dose output", non_empty=True)
        selected_phits_out, phits_out_source = select_phits_out(
            workspace_root=workspace_root,
            generation=generation,
            execution=execution,
            explicit_phits_out=phits_out,
        )
        require_existing_file(selected_phits_out, label="phits_out companion file")
        template_copy = copy_template(template_dicom, workspace_root)
        template_preflight = phits2dicom_template_preflight(template_copy)
        ct_source, ct_selection_source = select_ct_reference(
            workspace_root=workspace_root,
            paths_config=paths_config,
            explicit_ct_reference=ct_reference_dicom,
            generated_ct_reference=generated_ct_reference_dicom,
            smoke_dummy_ct_reference=smoke_dummy_ct_reference,
        )
        ct_selection, sync_summary = copy_and_optionally_sync_ct(
            source_ct=ct_source,
            workspace_root=workspace_root,
            selection_source=ct_selection_source,
            reference_dicom_for_identity=reference_dicom_for_identity,
        )
        full_plan_evidence = validate_full_plan_context(
            rtplan_path=rtplan_path or (workspace_root / "RTPLAN.dcm"),
            workspace_root=workspace_root,
            ct_reference_path=ct_selection.workspace_path,
        )
        ipp_patch_summary = patch_rtdose_inputs_for_ipp(
            workspace_root=workspace_root,
            phits_dose=phits_dose,
            phits_out=selected_phits_out,
            ct_reference_workspace_copy=ct_selection.workspace_path,
        )
        phits_dose_sha256_after_prepare = file_sha256(phits_dose)
        dat_dir = workspace_root / "rtdose" / "DATfiles"
        phits2dicom_inp = dat_dir / "phits2dicom.inp"
        stdin_content = phits2dicom_input_content(
            template_dicom=template_copy,
            ct_reference=ct_selection.workspace_path,
            phits_dose=phits_dose,
            phits_out=selected_phits_out,
            dat_dir=dat_dir,
            factor=factor,
        )
        write_text_lf(phits2dicom_inp, stdin_content)
        summary = {
            "schema_version": "dicomxphits_public_rtdose_prepare_v1",
            "stage": "prepare_rtdose",
            "stage_status": "success",
            "workspace_root": str(workspace_root),
            "command": {"argv": command_argv or sys.argv},
            "returncode": 0,
            "phits2dicom_execution_started": False,
            "input_dose_state": INPUT_DOSE_STATE,
            "input_dose_unit": input_dose_unit,
            "output_dicom_dose_unit": output_dicom_dose_unit,
            "sumtally_normalization": SUMTALLY_NORMALIZATION,
            "is_beam_mu_output": IS_BEAM_MU_OUTPUT,
            "factor": factor,
            "factor_selection_reason": factor_reason,
            "dose_semantics": public_absolute_dose_semantics(),
            "sumtally_manifest_binding": sumtally_manifest_binding,
            "full_plan_evidence": full_plan_evidence,
            "phits_dose": str(phits_dose),
            "phits_dose_sha256_after_prepare": phits_dose_sha256_after_prepare,
            "phits_out": str(selected_phits_out),
            "phits_out_selection_source": phits_out_source,
            "template_dicom_original_path": str(template_dicom),
            "template_dicom_workspace_copy_path": str(template_copy),
            "template_dicom_preflight": template_preflight,
            "ct_reference_original_path": str(ct_selection.source_path),
            "ct_reference_workspace_copy_path": str(ct_selection.workspace_path),
            "ct_reference_selection_source": ct_selection.source,
            "ct_reference_identity_sync": sync_summary,
            "image_position_patient_patch": ipp_patch_summary,
            "dat_dir": str(dat_dir),
            "phits2dicom_input_path": str(phits2dicom_inp),
            "phits2dicom_stdin_content": stdin_content,
            "path_config": {
                "phits_root_folder": paths.phits_root_folder,
                "phits_executable_path": paths.phits_executable_path,
                "phits2dicom_executable_path": paths.phits2dicom_executable_path,
            },
        }
        write_json(summary_path, summary)
        return summary
    except Exception as exc:
        write_failure_summary(
            path=summary_path,
            stage="prepare_rtdose",
            workspace_root=workspace_root,
            reason=str(exc),
            command_argv=command_argv,
        )
        raise


def unique_output_dirs(*paths: Path) -> list[Path]:
    output_dirs: list[Path] = []
    seen: set[str] = set()
    for path in paths:
        resolved = str(path.resolve())
        if resolved in seen:
            continue
        seen.add(resolved)
        output_dirs.append(path)
    return output_dirs


def dicom_snapshot(output_dirs: list[Path]) -> dict[str, dict[str, Any]]:
    snapshot: dict[str, dict[str, Any]] = {}
    for output_dir in output_dirs:
        if not output_dir.is_dir():
            continue
        for path in output_dir.iterdir():
            if path.is_file() and path.suffix.lower() == ".dcm":
                snapshot[str(path.resolve())] = {
                    "path": str(path),
                    "directory": str(output_dir),
                    "name": path.name,
                    "size": path.stat().st_size,
                    "mtime_ns": path.stat().st_mtime_ns,
                }
    return snapshot


def run_phits2dicom(
    *,
    executable_path: str,
    dat_dir: Path,
    stdin_content: str,
    stdout_path: Path,
    stderr_path: Path,
    runner=subprocess.Popen,
) -> tuple[int, str]:
    proc = runner(
        [executable_path],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        cwd=str(dat_dir.absolute()),
    )
    stdout, _ = proc.communicate(input=stdin_content + "\n\n\n")
    stdout_path.parent.mkdir(parents=True, exist_ok=True)
    stdout_path.write_text(stdout or "", encoding="utf-8")
    stderr_path.write_text("", encoding="utf-8")
    return int(proc.returncode), stdout or ""


def run_rtdose(
    *,
    workspace_root: Path,
    paths: ExternalToolPaths,
    command_argv: list[str] | None = None,
    runner=subprocess.Popen,
) -> dict[str, Any]:
    summary_path = execution_summary_path(workspace_root)
    execution_started = False
    try:
        if not paths.phits2dicom_executable_path:
            raise ValueError("Missing required external tool path setting: phits2dicom_executable_path")
        exe = Path(paths.phits2dicom_executable_path)
        require_existing_file(exe, label="phits2dicom executable")
        resolved_exe = exe.resolve()
        prepare_summary = load_json_object(prepare_summary_path(workspace_root))
        if prepare_summary.get("stage_status") != "success":
            raise ValueError("RTDOSE prepare summary is not successful")
        generation, execution = load_sumtally_summaries(workspace_root)
        current_sumtally_binding = validate_sumtally_manifest_binding(
            workspace_root=workspace_root,
            generation=generation,
            execution=execution,
            verify_sumtally_output=False,
        )
        if current_sumtally_binding != prepare_summary.get(
            "sumtally_manifest_binding"
        ):
            raise ValueError(
                "Sumtally manifest binding changed after RTDOSE Prepare; "
                "rerun RTDOSE Prepare"
            )
        recorded_plan_evidence = prepare_summary.get("full_plan_evidence")
        if not isinstance(recorded_plan_evidence, dict):
            raise ValueError(
                "RTDOSE prepare summary is missing full_plan_evidence; rerun RTDOSE Prepare"
            )
        recorded_rtplan_path = str(recorded_plan_evidence.get("rtplan_path") or "")
        recorded_ct_path = str(
            prepare_summary.get("ct_reference_workspace_copy_path") or ""
        )
        if not recorded_rtplan_path or not recorded_ct_path:
            raise ValueError(
                "RTDOSE prepare summary is missing frozen plan or CT reference evidence"
            )
        plan_evidence = validate_full_plan_context(
            rtplan_path=Path(recorded_rtplan_path),
            workspace_root=workspace_root,
            ct_reference_path=Path(recorded_ct_path),
        )
        if plan_evidence != recorded_plan_evidence:
            raise ValueError(
                "Frozen RT Plan or full-plan workspace evidence changed after RTDOSE Prepare"
            )
        phits2dicom_inp = Path(str(prepare_summary.get("phits2dicom_input_path") or ""))
        require_existing_file(phits2dicom_inp, label="phits2dicom input")
        dat_dir = Path(str(prepare_summary.get("dat_dir") or phits2dicom_inp.parent))
        phits_dose_value = str(prepare_summary.get("phits_dose") or "")
        if not phits_dose_value:
            raise ValueError("RTDOSE prepare summary is missing phits_dose")
        phits_dose = Path(phits_dose_value)
        require_existing_file(
            phits_dose,
            label="Prepared Sumtally PHITS dose output",
            non_empty=True,
        )
        prepared_phits_dose_sha256 = str(
            prepare_summary.get("phits_dose_sha256_after_prepare") or ""
        )
        if not prepared_phits_dose_sha256:
            raise ValueError(
                "RTDOSE prepare summary is missing the prepared PHITS dose digest; "
                "rerun RTDOSE Prepare"
            )
        if file_sha256(phits_dose) != prepared_phits_dose_sha256:
            raise ValueError(
                "Prepared Sumtally PHITS dose changed after RTDOSE Prepare; "
                "rerun RTDOSE Prepare"
            )
        expected_rtdose_output = phits_dose.with_suffix(".dcm")
        output_dirs = unique_output_dirs(dat_dir, phits_dose.parent)
        stdin_content = phits2dicom_inp.read_text(encoding="utf-8")
        before = dicom_snapshot(output_dirs)
        stdout_path = workspace_root / "rtdose" / "phits2dicom_stdout.txt"
        stderr_path = workspace_root / "rtdose" / "phits2dicom_stderr.txt"
        execution_started = True
        returncode, _stdout = run_phits2dicom(
            executable_path=str(resolved_exe),
            dat_dir=dat_dir,
            stdin_content=stdin_content,
            stdout_path=stdout_path,
            stderr_path=stderr_path,
            runner=runner,
        )
        after_conversion = dicom_snapshot(output_dirs)
        expected_key = str(expected_rtdose_output.resolve())
        expected_before = before.get(expected_key)
        expected_after_conversion = after_conversion.get(expected_key)
        expected_updated = (
            expected_after_conversion is not None
            and expected_after_conversion != expected_before
        )
        absolute_labeling = None
        plan_reference_synchronization = None
        coordinate_correction = None
        final_semantic_validation = None
        coordinate_corrected_output = corrected_rtdose_path(expected_rtdose_output)
        if returncode == 0 and expected_updated:
            absolute_labeling = mark_rtdose_absolute(expected_rtdose_output)
            plan_reference_synchronization = synchronize_plan_rtdose(
                expected_rtdose_output,
                plan_evidence=plan_evidence,
            )
            coordinate_correction = fix_coordinates(
                expected_rtdose_output,
                coordinate_corrected_output,
                summary_path=coordinate_summary_path(coordinate_corrected_output),
            )
            final_semantic_validation = validate_plan_rtdose(
                coordinate_corrected_output,
                plan_evidence=plan_evidence,
            )
        after = dicom_snapshot(output_dirs)
        new_paths = sorted(set(after) - set(before))
        new_dicoms = [after[path] for path in new_paths]
        expected_after = after.get(expected_key)
        expected_exists = expected_rtdose_output.is_file()
        expected_size = expected_rtdose_output.stat().st_size if expected_exists else None
        coordinate_corrected_exists = coordinate_corrected_output.is_file()
        coordinate_corrected_size = (
            coordinate_corrected_output.stat().st_size
            if coordinate_corrected_exists
            else None
        )
        stage_status = (
            "success"
            if returncode == 0
            and expected_updated
            and coordinate_corrected_exists
            and bool(final_semantic_validation and final_semantic_validation["validated"])
            and bool(
                coordinate_correction
                and coordinate_correction["invariants"][
                    "stored_value_multiset_preserved"
                ]
            )
            else "failed"
        )
        summary = {
            "schema_version": "dicomxphits_public_rtdose_execution_v1",
            "stage": "run_rtdose",
            "stage_status": stage_status,
            "workspace_root": str(workspace_root),
            "command": {
                "argv": command_argv or sys.argv,
                "phits2dicom_command": [str(resolved_exe)],
                "stdin": str(phits2dicom_inp),
                "cwd": str(dat_dir),
                "shell": False,
            },
            "returncode": returncode,
            "stdout_path": str(stdout_path),
            "stderr_path": str(stderr_path),
            "phits2dicom_execution_started": execution_started,
            "dat_dir": str(dat_dir),
            "output_snapshot_dirs": [str(path) for path in output_dirs],
            "output_snapshot_before": before,
            "output_snapshot_after": after,
            "new_dicom_outputs": new_dicoms,
            "expected_rtdose_output": str(expected_rtdose_output),
            "expected_rtdose_output_exists": expected_exists,
            "expected_rtdose_output_size": expected_size,
            "expected_rtdose_output_preexisting": expected_before is not None,
            "expected_rtdose_output_updated_by_run": expected_updated,
            "coordinate_corrected_rtdose_output": str(coordinate_corrected_output),
            "coordinate_corrected_rtdose_output_exists": coordinate_corrected_exists,
            "coordinate_corrected_rtdose_output_size": coordinate_corrected_size,
            "coordinate_correction_summary_path": str(
                coordinate_summary_path(coordinate_corrected_output)
            ),
            "coordinate_correction": coordinate_correction,
            "input_dose_state": prepare_summary.get("input_dose_state"),
            "sumtally_normalization": prepare_summary.get("sumtally_normalization"),
            "is_beam_mu_output": prepare_summary.get("is_beam_mu_output"),
            "factor": prepare_summary.get("factor"),
            "dose_semantics": prepare_summary.get("dose_semantics"),
            "absolute_dose_labeling": absolute_labeling,
            "plan_reference_synchronization": plan_reference_synchronization,
            "final_semantic_validation": final_semantic_validation,
        }
        write_json(summary_path, summary)
        return summary
    except Exception as exc:
        write_failure_summary(
            path=summary_path,
            stage="run_rtdose",
            workspace_root=workspace_root,
            reason=str(exc),
            command_argv=command_argv,
            extra={"phits2dicom_execution_started": execution_started},
            stage_status="failed" if execution_started else "gate_failed",
        )
        raise


def paths_from_args(args: argparse.Namespace) -> tuple[ExternalToolPaths, dict[str, Any]]:
    config_path = Path(args.paths_json) if args.paths_json else None
    raw_config = read_paths_config(config_path)
    paths_config = load_paths_config(config_path) if config_path else None
    paths = merged_tool_paths(
        paths_config=paths_config,
        phits_root_folder=args.phits_root_folder,
        phits_executable_path=args.phits_executable_path,
        phits2dicom_executable_path=args.phits2dicom_executable_path,
    )
    return paths, raw_config


def build_prepare_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Prepare public dicomxphits RTDOSE conversion inputs.")
    parser.add_argument("--workspace-root", required=True)
    parser.add_argument("--paths-json", default=None)
    parser.add_argument("--phits-root-folder", default=None)
    parser.add_argument("--phits-executable-path", default=None)
    parser.add_argument("--phits2dicom-executable-path", default=None)
    parser.add_argument("--rtplan", required=True)
    parser.add_argument("--template-dicom", required=True)
    parser.add_argument("--ct-reference-dicom", default=None)
    parser.add_argument("--generated-ct-reference-dicom", default=None)
    parser.add_argument("--smoke-dummy-ct-reference", default=None)
    parser.add_argument("--reference-dicom-for-identity", default=None)
    parser.add_argument("--phits-out", default=None)
    parser.add_argument("--input-dose-unit", default=DEFAULT_INPUT_DOSE_UNIT)
    parser.add_argument("--output-dicom-dose-unit", default=DEFAULT_OUTPUT_DICOM_DOSE_UNIT)
    return parser


def build_run_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run public dicomxphits RTDOSE conversion.")
    parser.add_argument("--workspace-root", required=True)
    parser.add_argument("--paths-json", default=None)
    parser.add_argument("--phits-root-folder", default=None)
    parser.add_argument("--phits-executable-path", default=None)
    parser.add_argument("--phits2dicom-executable-path", default=None)
    return parser


def prepare_main(argv: list[str] | None = None) -> int:
    args = build_prepare_parser().parse_args(argv)
    try:
        paths, raw_config = paths_from_args(args)
        summary = prepare_rtdose(
            workspace_root=Path(args.workspace_root),
            paths=paths,
            paths_config=raw_config,
            rtplan_path=Path(args.rtplan),
            template_dicom=Path(args.template_dicom),
            ct_reference_dicom=Path(args.ct_reference_dicom) if args.ct_reference_dicom else None,
            generated_ct_reference_dicom=Path(args.generated_ct_reference_dicom)
            if args.generated_ct_reference_dicom
            else None,
            smoke_dummy_ct_reference=Path(args.smoke_dummy_ct_reference) if args.smoke_dummy_ct_reference else None,
            reference_dicom_for_identity=Path(args.reference_dicom_for_identity)
            if args.reference_dicom_for_identity
            else None,
            phits_out=Path(args.phits_out) if args.phits_out else None,
            input_dose_unit=args.input_dose_unit,
            output_dicom_dose_unit=args.output_dicom_dose_unit,
            command_argv=sys.argv if argv is None else ["dicomxphits-prepare-rtdose", *argv],
        )
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(
        "Dose semantics: GY for the approved public research model "
        "(not a commissioned or universal clinical beam)"
    )
    print(prepare_summary_path(Path(args.workspace_root)))
    return 0


def run_main(argv: list[str] | None = None) -> int:
    args = build_run_parser().parse_args(argv)
    try:
        paths, _raw_config = paths_from_args(args)
        summary = run_rtdose(
            workspace_root=Path(args.workspace_root),
            paths=paths,
            command_argv=sys.argv if argv is None else ["dicomxphits-run-rtdose", *argv],
        )
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(
        "Dose semantics: GY for the approved public research model "
        "(not a commissioned or universal clinical beam)"
    )
    print(execution_summary_path(Path(args.workspace_root)))
    return 0 if summary["stage_status"] == "success" else 3


if __name__ == "__main__":
    raise SystemExit(prepare_main())
