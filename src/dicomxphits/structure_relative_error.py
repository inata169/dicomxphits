"""Evidence-bound post-completion RT Structure relative-error evaluation."""

from __future__ import annotations

import hashlib
import json
import math
import os
from decimal import Decimal, localcontext
from pathlib import Path
import secrets
import time
from typing import Any

import numpy as np
import pydicom

from dicomxphits.ct2phits_datfiles import RAW_CT2PHITS_NAMES
from dicomxphits.phits_observation_format import (
    MAX_TALLY_BYTES,
    Mesh,
    paired_sumtally_values,
    prepared_sumtally_contract,
)
from dicomxphits.replace_ct_layer_with_water import (
    CtSeries,
    load_ct_series,
    load_rtstruct_roi_mask_by_number,
)
from dicomxphits.rtdose_geometry import (
    derive_rtdose_placement,
    normalize_tally_mesh_geometry,
    tally_mesh_geometry_sha256,
)
from dicomxphits.rtdose_plan_references import validate_full_plan_context
from dicomxphits.safe_output import WorkspaceOutputGuard
from dicomxphits.sumtally_inputs import file_sha256


SCHEMA_VERSION = "dicomxphits_structure_relative_error_v1"
PAIR_SCHEMA_VERSION = "dicomxphits_sumtally_relative_error_pair_v1"
CONTRACT_VERSION = "post_completion_structure_relative_error_v1"
PAIR_SEMANTICS = "phits_3_35_sumtally_isumtally_2_relative_error_v1"
THRESHOLD_FRACTION = 0.5
THRESHOLD_RULE = "dose_greater_than_0_5_global_combined_dmax_v1"
STATISTICS_RULE = "unweighted_rerr_percent_mean_median_linear_p95_v1"
RESULT_RELATIVE_ROOT = Path("analysis") / "structure_relative_error"
NON_CLINICAL_LABEL = (
    "Monte Carlo statistical relative error within the selected Structure; "
    "not clinical dose error, convergence, patient QA, or an acceptance "
    "criterion."
)
MAX_JSON_BYTES = 16 * 1024**2
PAIR_PARSE_SECONDS = 120.0
MAPPING_CHUNK_CELLS = 100_000
RETAINED_VALIDATION_SCHEMA_VERSION = (
    "dicomxphits_structure_relative_error_retained_validation_v1"
)
_WINDOWS_FILE_BASIC_INFO: Any = None
_WINDOWS_GET_FILE_INFORMATION: Any = None


class StructureRelativeErrorUnavailable(ValueError):
    """The requested derived presentation is unavailable and non-authoritative."""


def _canonical_sha256(value: Any) -> str:
    try:
        payload = json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("ascii")
    except (TypeError, ValueError) as exc:
        raise StructureRelativeErrorUnavailable(
            "evaluation evidence is not canonically serializable"
        ) from exc
    return hashlib.sha256(payload).hexdigest()


def _is_link_or_junction(path: Path) -> bool:
    if path.is_symlink():
        return True
    is_junction = getattr(path, "is_junction", None)
    return bool(is_junction is not None and is_junction())


def _stable_regular_bytes(
    path: Path,
    *,
    label: str,
    maximum_bytes: int | None = None,
) -> tuple[bytes, str]:
    supplied = Path(os.path.abspath(os.fspath(path)))
    if not supplied.is_file() or _is_link_or_junction(supplied):
        raise StructureRelativeErrorUnavailable(
            f"{label} must be an existing non-link regular file"
        )
    if maximum_bytes is not None and supplied.stat().st_size > maximum_bytes:
        raise StructureRelativeErrorUnavailable(f"{label} exceeds its size limit")
    before = file_sha256(supplied)
    try:
        content = supplied.read_bytes()
    except OSError as exc:
        raise StructureRelativeErrorUnavailable(f"{label} is not readable") from exc
    after = hashlib.sha256(content).hexdigest()
    if after != before or file_sha256(supplied) != before:
        raise StructureRelativeErrorUnavailable(f"{label} changed while being read")
    return content, before


def _stable_json(path: Path, *, label: str) -> tuple[dict[str, Any], str]:
    raw, digest = _stable_regular_bytes(
        path,
        label=label,
        maximum_bytes=MAX_JSON_BYTES,
    )
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise StructureRelativeErrorUnavailable(f"{label} is not valid JSON") from exc
    if not isinstance(value, dict):
        raise StructureRelativeErrorUnavailable(f"{label} JSON root must be an object")
    return value, digest


def _mesh_matches_geometry(mesh: Mesh, expected_geometry: Any) -> bool:
    normalized = normalize_tally_mesh_geometry(expected_geometry)
    axes = normalized["axes"]
    expected_counts = tuple(int(axes[axis]["bin_count"]) for axis in "xyz")
    expected_bounds = tuple(
        (
            float(axes[axis]["minimum_cm"]),
            float(axes[axis]["maximum_cm"]),
        )
        for axis in "xyz"
    )
    return mesh.counts == expected_counts and mesh.bounds == expected_bounds


def _read_combined_tally_pair(
    *,
    dose_path: Path,
    error_path: Path,
    sum_input_path: Path,
    expected_geometry: Any,
) -> tuple[np.ndarray, np.ndarray, Mesh, dict[str, Any], dict[str, Any]]:
    dose_raw, dose_sha256 = _stable_regular_bytes(
        dose_path,
        label="combined Sumtally dose output",
        maximum_bytes=MAX_TALLY_BYTES,
    )
    error_raw, error_sha256 = _stable_regular_bytes(
        error_path,
        label="combined Sumtally statistical-error output",
        maximum_bytes=MAX_TALLY_BYTES,
    )
    input_raw, input_sha256 = _stable_regular_bytes(
        sum_input_path,
        label="generated Sumtally wrapper input",
        maximum_bytes=4 * 1024**2,
    )
    try:
        input_text = input_raw.decode("utf-8")
        prepared_mesh, _runtime = prepared_sumtally_contract(input_text)
        if not _mesh_matches_geometry(prepared_mesh, expected_geometry):
            raise StructureRelativeErrorUnavailable(
                "combined dose/error mesh does not match validated Sumtally geometry"
            )
        mesh = Mesh(
            prepared_mesh.title,
            dose_path.name,
            prepared_mesh.counts,
            prepared_mesh.bounds,
        )
        dose, error, metadata = paired_sumtally_values(
            dose_raw,
            error_raw,
            mesh,
            time.monotonic() + PAIR_PARSE_SECONDS,
        )
    except StructureRelativeErrorUnavailable:
        raise
    except Exception as exc:
        raise StructureRelativeErrorUnavailable(
            "combined Sumtally dose/error pair has unsupported or mismatched semantics"
        ) from exc
    evidence = {
        "schema_version": PAIR_SCHEMA_VERSION,
        "semantics": PAIR_SEMANTICS,
        "dose_path": str(dose_path.resolve()),
        "dose_sha256": dose_sha256,
        "error_path": str(error_path.resolve()),
        "error_sha256": error_sha256,
        "sum_input_sha256": input_sha256,
        "mesh_geometry_sha256": tally_mesh_geometry_sha256(expected_geometry),
        "cell_count": mesh.cells,
        "pair_metadata_sha256": _canonical_sha256(metadata),
        "validated": True,
    }
    return dose, error, mesh, metadata, evidence


def validate_combined_tally_pair(
    *,
    dose_path: Path,
    error_path: Path,
    sum_input_path: Path,
    expected_geometry: Any,
) -> dict[str, Any]:
    """Validate PHITS 3.35 combined dose/error semantics for Sumtally evidence."""

    _dose, _error, _mesh, _metadata, evidence = _read_combined_tally_pair(
        dose_path=dose_path,
        error_path=error_path,
        sum_input_path=sum_input_path,
        expected_geometry=expected_geometry,
    )
    return evidence


def _supplemental_receipt_path(workspace_root: Path) -> Path:
    from dicomxphits.sumtally_relative_error_recovery import RECEIPT_RELATIVE_PATH

    return workspace_root / RECEIPT_RELATIVE_PATH


def reject_supplemental_receipt_with_direct_evidence(workspace_root: Path) -> None:
    """Reject contradictory direct and fixed supplemental pair authority."""

    if os.path.lexists(_supplemental_receipt_path(workspace_root)):
        raise StructureRelativeErrorUnavailable(
            "supplemental recovery receipt conflicts with direct evidence"
        )


def _current_combined_source(
    workspace_root: Path,
) -> tuple[
    np.ndarray,
    np.ndarray,
    Mesh,
    dict[str, Any],
    dict[str, Any],
    dict[str, Any],
]:
    from dicomxphits.prepare_rtdose import (
        validate_sumtally_manifest_binding,
    )
    from dicomxphits.run_segments import phits_error_output_path
    from dicomxphits.workspace_recovery import (
        normalize_relocated_sumtally_summaries,
    )

    control_paths = {
        "Sumtally generation summary": workspace_root
        / "analysis"
        / "sumtally_generation_summary.json",
        "Sumtally execution summary": workspace_root
        / "analysis"
        / "sumtally_execution_summary.json",
        "segment preflight receipt": workspace_root
        / "analysis"
        / "segment_preflight.json",
        "segment manifest": workspace_root / "segments" / "segment_manifest.json",
    }
    generation, generation_sha256 = _stable_json(
        control_paths["Sumtally generation summary"],
        label="Sumtally generation summary",
    )
    execution, execution_sha256 = _stable_json(
        control_paths["Sumtally execution summary"],
        label="Sumtally execution summary",
    )
    if generation.get("stage_status") != "success":
        raise StructureRelativeErrorUnavailable(
            "Sumtally generation summary is not successful"
        )
    if execution.get("stage_status") != "success":
        raise StructureRelativeErrorUnavailable(
            "Sumtally execution summary is not successful"
        )
    control_sha256 = {
        "Sumtally generation summary": generation_sha256,
        "Sumtally execution summary": execution_sha256,
    }
    for label in ("segment preflight receipt", "segment manifest"):
        _raw, digest = _stable_regular_bytes(
            control_paths[label],
            label=label,
            maximum_bytes=MAX_JSON_BYTES,
        )
        control_sha256[label] = digest
    generation, execution = normalize_relocated_sumtally_summaries(
        workspace_root,
        generation=generation,
        execution=execution,
    )
    binding = validate_sumtally_manifest_binding(
        workspace_root=workspace_root,
        generation=generation,
        execution=execution,
    )
    recorded = execution.get("combined_relative_error_evidence")
    direct_evidence = isinstance(recorded, dict)
    if direct_evidence:
        reject_supplemental_receipt_with_direct_evidence(workspace_root)
    else:
        from dicomxphits.sumtally_relative_error_recovery import (
            RECEIPT_RELATIVE_PATH,
            resolved_combined_relative_error_evidence,
        )

        try:
            recorded, receipt_sha256 = resolved_combined_relative_error_evidence(
                workspace_root
            )
        except Exception as exc:
            raise StructureRelativeErrorUnavailable(
                "verified combined Sumtally statistical-error evidence is unavailable"
            ) from exc
        control_paths["Sumtally relative-error recovery receipt"] = (
            workspace_root / RECEIPT_RELATIVE_PATH
        )
        control_sha256["Sumtally relative-error recovery receipt"] = receipt_sha256
    dose_path = Path(str(binding["sumtally_output_path"])).resolve()
    error_path = phits_error_output_path(dose_path)
    if str(recorded.get("dose_path") or "") != str(dose_path):
        raise StructureRelativeErrorUnavailable(
            "combined relative-error dose path does not match current Sumtally evidence"
        )
    if str(recorded.get("error_path") or "") != str(error_path):
        raise StructureRelativeErrorUnavailable(
            "combined relative-error path does not match the paired Sumtally output"
        )
    generation_outputs = generation.get("outputs")
    if not isinstance(generation_outputs, dict):
        raise StructureRelativeErrorUnavailable(
            "Sumtally generation output evidence is unavailable"
        )
    sum_input_path = Path(str(generation_outputs.get("sum_input") or "")).resolve()
    dose, error, mesh, metadata, current = _read_combined_tally_pair(
        dose_path=dose_path,
        error_path=error_path,
        sum_input_path=sum_input_path,
        expected_geometry=binding["tally_geometry_binding"]["mesh_geometry"],
    )
    if current != recorded:
        raise StructureRelativeErrorUnavailable(
            "combined relative-error evidence is stale or mismatched"
        )
    if current["dose_sha256"] != binding["sumtally_output_sha256"]:
        raise StructureRelativeErrorUnavailable(
            "combined dose digest does not match terminal Sumtally evidence"
        )
    for label, path in control_paths.items():
        if file_sha256(path) != control_sha256[label]:
            raise StructureRelativeErrorUnavailable(
                f"{label} changed during Structure relative-error evaluation"
            )
    if direct_evidence:
        reject_supplemental_receipt_with_direct_evidence(workspace_root)
    control_evidence = {
        "files": [
            {
                "label": label,
                "path": str(path.resolve()),
                "sha256": control_sha256[label],
            }
            for label, path in control_paths.items()
        ],
        "sum_input_path": str(sum_input_path),
    }
    return dose, error, mesh, binding, current, control_evidence


def _frozen_ct_series(
    ct_reference_path: Path,
    *,
    workspace_root: Path,
) -> tuple[CtSeries, dict[str, Any], dict[str, Any]]:
    reference = Path(os.path.abspath(os.fspath(ct_reference_path)))
    reference_raw, reference_sha256 = _stable_regular_bytes(
        reference,
        label="frozen CT reference",
    )
    try:
        reference_dataset = pydicom.dcmread(
            reference,
            stop_before_pixels=True,
            force=False,
        )
    except Exception as exc:
        raise StructureRelativeErrorUnavailable(
            "frozen CT reference is not readable"
        ) from exc
    series_uid = str(getattr(reference_dataset, "SeriesInstanceUID", "") or "")
    if not series_uid:
        raise StructureRelativeErrorUnavailable(
            "frozen CT reference is missing SeriesInstanceUID"
        )
    ct_root = reference.parent
    validated_directory_entries = sorted(item.name for item in ct_root.iterdir())
    snapshot_root = ct_root.parent
    manifest_path = snapshot_root / "ct2phits_workspace_manifest.json"
    summary_path = snapshot_root / "ct2phits_execution_summary.json"
    manifest, manifest_sha256 = _stable_json(
        manifest_path,
        label="CT2PHITS workspace manifest",
    )
    summary, summary_sha256 = _stable_json(
        summary_path,
        label="CT2PHITS execution summary",
    )
    if manifest.get("status") != "completed" or summary.get("status") != "completed":
        raise StructureRelativeErrorUnavailable(
            "frozen CT series lacks completed CT2PHITS evidence"
        )
    preparation, preparation_sha256 = _stable_json(
        workspace_root
        / "analysis"
        / "public_preparation_workspace_summary.json",
        label="3D-CRT workspace preparation summary",
    )
    if (
        preparation.get("schema_version")
        != "dicomxphits_public_prepare_3dcrt_workspace_v1"
        or preparation.get("returncode") != 0
    ):
        raise StructureRelativeErrorUnavailable(
            "current workspace lacks successful preparation evidence"
        )
    phits_generation = preparation.get("phits_generation")
    if not isinstance(phits_generation, dict):
        raise StructureRelativeErrorUnavailable(
            "workspace preparation is missing PHITS generation evidence"
        )
    ct_assets = phits_generation.get("ct_voxel_assets")
    if (
        not isinstance(ct_assets, dict)
        or ct_assets.get("status") != "validated_and_copied"
        or ct_assets.get("source_contract")
        != "raw_ct2phits_datfiles_plus_ct_reference"
        or ct_assets.get("frame_of_reference_match") is not True
    ):
        raise StructureRelativeErrorUnavailable(
            "workspace preparation lacks validated frozen-CT asset evidence"
        )
    recorded_raw_hashes = ct_assets.get("raw_datfiles_sha256")
    summary_raw_hashes = summary.get("raw_datfiles_sha256")
    if (
        not isinstance(recorded_raw_hashes, dict)
        or summary_raw_hashes != recorded_raw_hashes
        or set(recorded_raw_hashes) != set(RAW_CT2PHITS_NAMES)
    ):
        raise StructureRelativeErrorUnavailable(
            "CT2PHITS DATfiles evidence does not match workspace preparation"
        )
    for name in RAW_CT2PHITS_NAMES:
        path = snapshot_root / "DATfiles" / name
        expected_sha256 = str(recorded_raw_hashes.get(name) or "")
        if (
            not path.is_file()
            or _is_link_or_junction(path)
            or not expected_sha256
            or file_sha256(path) != expected_sha256
        ):
            raise StructureRelativeErrorUnavailable(
                "current CT2PHITS DATfiles do not match workspace preparation"
            )
    recorded_series = manifest.get("ct_series")
    if not isinstance(recorded_series, dict):
        raise StructureRelativeErrorUnavailable(
            "CT2PHITS manifest is missing frozen CT-series evidence"
        )
    try:
        series = load_ct_series(ct_root, series_instance_uid=series_uid)
    except Exception as exc:
        raise StructureRelativeErrorUnavailable(
            "frozen CT series is invalid"
        ) from exc
    if (
        str(recorded_series.get("series_instance_uid") or "") != series.series_uid
        or str(recorded_series.get("frame_of_reference_uid") or "")
        != series.frame_uid
        or recorded_series.get("slice_count") != len(series.slices)
        or recorded_series.get("rows") != series.rows
        or recorded_series.get("columns") != series.columns
    ):
        raise StructureRelativeErrorUnavailable(
            "frozen CT geometry does not match CT2PHITS evidence"
        )
    if (
        ct_assets.get("ct_slice_count") != len(series.slices)
        or ct_assets.get("ct_origin_dicom_cm")
        != recorded_series.get("ct_origin_dicom_cm")
    ):
        raise StructureRelativeErrorUnavailable(
            "frozen CT/plan geometry does not match workspace preparation"
        )
    recorded_rtplan = manifest.get("rtplan")
    if (
        not isinstance(recorded_rtplan, dict)
        or ct_assets.get("rtplan_isocenter_dicom_cm")
        != recorded_rtplan.get("isocenter_dicom_cm")
    ):
        raise StructureRelativeErrorUnavailable(
            "frozen CT/plan geometry does not match workspace preparation"
        )
    copied_files = recorded_series.get("copied_files")
    recorded_hashes = recorded_series.get("sha256")
    if not isinstance(copied_files, list) or not isinstance(recorded_hashes, dict):
        raise StructureRelativeErrorUnavailable(
            "CT2PHITS manifest has incomplete CT digest evidence"
        )
    expected_paths: list[Path] = []
    slice_hashes: list[str] = []
    for value in copied_files:
        if not isinstance(value, str) or not value:
            raise StructureRelativeErrorUnavailable(
                "CT2PHITS manifest has an invalid CT file entry"
            )
        candidate = (snapshot_root / value).resolve()
        try:
            candidate.relative_to(ct_root.resolve())
        except ValueError as exc:
            raise StructureRelativeErrorUnavailable(
                "CT2PHITS CT evidence escapes the frozen CT directory"
            ) from exc
        if not candidate.is_file() or _is_link_or_junction(candidate):
            raise StructureRelativeErrorUnavailable(
                "frozen CT evidence contains a missing or linked file"
            )
        recorded_sha256 = str(recorded_hashes.get(value) or "")
        if not recorded_sha256 or file_sha256(candidate) != recorded_sha256:
            raise StructureRelativeErrorUnavailable(
                "frozen CT content does not match CT2PHITS digest evidence"
            )
        expected_paths.append(candidate)
        slice_hashes.append(recorded_sha256)
    actual_paths = {item.path.resolve() for item in series.slices}
    if set(expected_paths) != actual_paths or reference.resolve() not in actual_paths:
        raise StructureRelativeErrorUnavailable(
            "frozen CT series membership does not match CT2PHITS evidence"
        )
    if hashlib.sha256(reference_raw).hexdigest() != reference_sha256:
        raise StructureRelativeErrorUnavailable("frozen CT reference changed")
    for path, expected_sha256 in zip(expected_paths, slice_hashes, strict=True):
        if file_sha256(path) != expected_sha256:
            raise StructureRelativeErrorUnavailable(
                "frozen CT series changed while being validated"
            )
    evidence_payload = {
        "manifest_sha256": manifest_sha256,
        "execution_summary_sha256": summary_sha256,
        "workspace_preparation_sha256": preparation_sha256,
        "raw_datfiles_sha256": recorded_raw_hashes,
        "series_instance_uid": series.series_uid,
        "frame_of_reference_uid": series.frame_uid,
        "study_instance_uid": series.study_uid,
        "slice_sha256": slice_hashes,
        "rows": series.rows,
        "columns": series.columns,
        "row_spacing_mm": series.row_spacing_mm,
        "column_spacing_mm": series.column_spacing_mm,
        "slice_spacing_mm": series.slice_spacing_mm,
        "row_direction": series.row_direction.tolist(),
        "column_direction": series.column_direction.tolist(),
        "slice_positions": [item.position.tolist() for item in series.slices],
        "reference_sha256": reference_sha256,
    }
    if sorted(item.name for item in ct_root.iterdir()) != validated_directory_entries:
        raise StructureRelativeErrorUnavailable(
            "frozen CT directory membership changed while being validated"
        )
    return (
        series,
        {
            "ct_series_evidence_sha256": _canonical_sha256(evidence_payload),
            "ct2phits_manifest_sha256": manifest_sha256,
            "ct2phits_execution_summary_sha256": summary_sha256,
            "workspace_preparation_sha256": preparation_sha256,
            "ct_reference_sha256": reference_sha256,
        },
        {
            "path": str(ct_root.resolve()),
            "entries": validated_directory_entries,
        },
    )


def _values_in_rtdose_order(values: np.ndarray, mesh: Mesh) -> np.ndarray:
    nx, ny, nz = mesh.counts
    if values.shape != (nx * ny * nz,):
        raise StructureRelativeErrorUnavailable(
            "combined tally cell count does not match its mesh"
        )
    phits = values.reshape(nz, ny, nx)
    return np.transpose(phits[:, ::-1, ::-1], (1, 0, 2)).copy()


def _decimal_vector(values: Any) -> tuple[Decimal, ...]:
    return tuple(Decimal(str(float(value))) for value in values)


def _decimal_dot(
    left: tuple[Decimal, ...],
    right: tuple[Decimal, ...],
) -> Decimal:
    return sum((a * b for a, b in zip(left, right, strict=True)), Decimal(0))


def _decimal_cross(
    left: tuple[Decimal, ...],
    right: tuple[Decimal, ...],
) -> tuple[Decimal, Decimal, Decimal]:
    return (
        left[1] * right[2] - left[2] * right[1],
        left[2] * right[0] - left[0] * right[2],
        left[0] * right[1] - left[1] * right[0],
    )


def _decimal_mapping_geometry(
    placement: dict[str, Any],
    series: CtSeries,
) -> dict[str, Any]:
    dose_iop = _decimal_vector(placement["image_orientation_patient"])
    dose_column = dose_iop[:3]
    dose_row = dose_iop[3:]
    return {
        "dose_ipp": _decimal_vector(placement["image_position_patient_mm"]),
        "dose_column": dose_column,
        "dose_row": dose_row,
        "dose_normal": _decimal_cross(dose_column, dose_row),
        "dose_spacing": _decimal_vector(placement["pixel_spacing_mm"]),
        "dose_offsets": _decimal_vector(
            placement["grid_frame_offset_vector_mm"]
        ),
        "ct_origin": _decimal_vector(series.slices[0].position),
        "ct_normal": _decimal_vector(series.normal_direction),
        "ct_spacing": _decimal_vector(
            (
                series.slice_spacing_mm,
                series.row_spacing_mm,
                series.column_spacing_mm,
            )
        ),
        "ct_column": _decimal_vector(series.column_direction),
        "ct_row": _decimal_vector(series.row_direction),
    }


def _lies_on_decimal_ct_boundary(
    geometry: dict[str, Any],
    *,
    frame: int,
    row: int,
    column: int,
) -> bool:
    with localcontext() as context:
        context.prec = 50
        dose_ipp = geometry["dose_ipp"]
        dose_column = geometry["dose_column"]
        dose_row = geometry["dose_row"]
        dose_normal = geometry["dose_normal"]
        dose_spacing = geometry["dose_spacing"]
        offset = geometry["dose_offsets"][frame]
        row_index = Decimal(row)
        column_index = Decimal(column)
        point = tuple(
            dose_ipp[index]
            + column_index * dose_spacing[1] * dose_column[index]
            + row_index * dose_spacing[0] * dose_row[index]
            + offset * dose_normal[index]
            for index in range(3)
        )
        relative = tuple(
            point[index] - geometry["ct_origin"][index]
            for index in range(3)
        )
        coordinates = (
            _decimal_dot(relative, geometry["ct_normal"])
            / geometry["ct_spacing"][0],
            _decimal_dot(relative, geometry["ct_column"])
            / geometry["ct_spacing"][1],
            _decimal_dot(relative, geometry["ct_row"])
            / geometry["ct_spacing"][2],
        )
        return any(
            (value + Decimal("0.5"))
            == (value + Decimal("0.5")).to_integral_value()
            for value in coordinates
        )


def _structure_membership_on_dose_grid(
    *,
    placement: dict[str, Any],
    series: CtSeries,
    ct_mask: np.ndarray,
) -> np.ndarray:
    shape = tuple(int(value) for value in placement["output_shape_frames_rows_columns"])
    if len(shape) != 3 or any(value <= 0 for value in shape):
        raise StructureRelativeErrorUnavailable("RTDOSE affine shape is invalid")
    if ct_mask.shape != (len(series.slices), series.rows, series.columns):
        raise StructureRelativeErrorUnavailable("Structure mask shape is invalid")
    ipp = np.asarray(placement["image_position_patient_mm"], dtype=np.float64)
    iop = np.asarray(placement["image_orientation_patient"], dtype=np.float64)
    spacing = np.asarray(placement["pixel_spacing_mm"], dtype=np.float64)
    offsets = np.asarray(
        placement["grid_frame_offset_vector_mm"],
        dtype=np.float64,
    )
    if (
        ipp.shape != (3,)
        or iop.shape != (6,)
        or spacing.shape != (2,)
        or offsets.shape != (shape[0],)
        or not np.all(np.isfinite(np.concatenate((ipp, iop, spacing, offsets))))
    ):
        raise StructureRelativeErrorUnavailable("RTDOSE affine is invalid")
    column_direction = iop[:3]
    row_direction = iop[3:]
    normal_direction = np.cross(column_direction, row_direction)
    total = math.prod(shape)
    membership = np.zeros(total, dtype=bool)
    dose_rows, dose_columns = shape[1], shape[2]
    plane = dose_rows * dose_columns
    ct_origin = series.slices[0].position
    ct_counts = np.asarray(
        [len(series.slices), series.rows, series.columns],
        dtype=np.int64,
    )
    decimal_geometry = _decimal_mapping_geometry(placement, series)
    ct_spacing = np.asarray(
        [
            series.slice_spacing_mm,
            series.row_spacing_mm,
            series.column_spacing_mm,
        ],
        dtype=np.float64,
    )
    for start in range(0, total, MAPPING_CHUNK_CELLS):
        stop = min(total, start + MAPPING_CHUNK_CELLS)
        flat = np.arange(start, stop, dtype=np.int64)
        frames = flat // plane
        within = flat % plane
        rows = within // dose_columns
        columns = within % dose_columns
        points = (
            ipp
            + columns[:, None] * spacing[1] * column_direction
            + rows[:, None] * spacing[0] * row_direction
            + offsets[frames, None] * normal_direction
        )
        relative = points - ct_origin
        coordinates = np.column_stack(
            (
                (points @ series.normal_direction - series.slices[0].distance_mm)
                / series.slice_spacing_mm,
                (relative @ series.column_direction) / series.row_spacing_mm,
                (relative @ series.row_direction) / series.column_spacing_mm,
            )
        )
        scaled = coordinates + 0.5
        nearest = np.rint(scaled)
        patient_magnitude = np.max(np.abs(points), axis=1)[:, None]
        # This bound only selects values for exact Decimal evaluation; it is
        # never used to classify a point as on or off a boundary.
        decimal_prefilter = (
            256.0
            * np.finfo(np.float64).eps
            * (
                np.abs(scaled)
                + patient_magnitude / ct_spacing[None, :]
                + 1.0
            )
        )
        near_closed = np.all(
            (scaled >= -decimal_prefilter)
            & (scaled <= ct_counts + decimal_prefilter),
            axis=1,
        )
        boundary_candidates = near_closed & np.any(
            np.abs(scaled - nearest) <= decimal_prefilter,
            axis=1,
        )
        for index in np.flatnonzero(boundary_candidates):
            if _lies_on_decimal_ct_boundary(
                decimal_geometry,
                frame=int(frames[index]),
                row=int(rows[index]),
                column=int(columns[index]),
            ):
                raise StructureRelativeErrorUnavailable(
                    "a dose-voxel centre lies on a frozen CT voxel-cell boundary"
                )
        valid = np.all((scaled > 0.0) & (scaled < ct_counts), axis=1)
        indices = np.floor(scaled[valid]).astype(np.int64)
        if len(indices):
            membership_chunk = membership[start:stop]
            membership_chunk[valid] = ct_mask[
                indices[:, 0],
                indices[:, 1],
                indices[:, 2],
            ]
    if not np.any(membership):
        raise StructureRelativeErrorUnavailable(
            "no dose voxel maps uniquely to the selected Structure"
        )
    return membership.reshape(shape)


def _statistics_percent(values: np.ndarray) -> dict[str, float]:
    sorted_values = np.sort(values.astype(np.float64, copy=False) * 100.0)
    count = len(sorted_values)
    if count < 2:
        raise StructureRelativeErrorUnavailable(
            "fewer than two eligible positive-error voxels remain"
        )
    mean = math.fsum(float(value) for value in sorted_values) / count
    middle = count // 2
    median = (
        float(sorted_values[middle])
        if count % 2
        else (float(sorted_values[middle - 1]) + float(sorted_values[middle])) / 2.0
    )
    position = 0.95 * (count - 1)
    lower = math.floor(position)
    upper = math.ceil(position)
    fraction = position - lower
    p95 = float(sorted_values[lower]) + fraction * (
        float(sorted_values[upper]) - float(sorted_values[lower])
    )
    result = {"mean": mean, "median": median, "p95": p95}
    if not all(math.isfinite(value) for value in result.values()):
        raise StructureRelativeErrorUnavailable("derived statistics are not finite")
    return result


def _read_exact_record(path: Path, expected: dict[str, Any]) -> dict[str, Any]:
    value, _digest = _stable_json(path, label="Structure relative-error result")
    if value != expected:
        raise StructureRelativeErrorUnavailable(
            "the exact persisted Structure relative-error result is stale or mismatched"
        )
    return value


_ATOMIC_NO_REPLACE_RENAME = os.name == "nt"


def _publish_temporary_without_replacement(temporary: Path, path: Path) -> None:
    """Atomically publish *temporary* without replacing an existing path."""

    if _ATOMIC_NO_REPLACE_RENAME:
        # On Windows os.rename() is an atomic same-directory move and raises
        # FileExistsError when the destination already exists.  Unlike a hard
        # link, this is supported by FAT/exFAT and compatible network shares.
        os.rename(temporary, path)
        return
    # POSIX rename replaces its destination, so retain hard-link publication
    # there to preserve the required no-replace race boundary.
    os.link(temporary, path)


def _publish_new_record(
    workspace_root: Path,
    path: Path,
    record: dict[str, Any],
) -> dict[str, Any]:
    with WorkspaceOutputGuard(workspace_root) as guard:
        guard.mkdir(path.parent)
        guard.prepare_file_target(path)
        if os.path.lexists(path):
            return _read_exact_record(path, record)
        temporary = path.with_name(
            f".{path.name}.dicomxphits-{secrets.token_hex(8)}.tmp"
        )
        try:
            guard.write_json(temporary, record, overwrite=False)
            guard.prepare_file_target(path)
            try:
                _publish_temporary_without_replacement(temporary, path)
            except FileExistsError:
                return _read_exact_record(path, record)
        finally:
            if os.path.lexists(temporary):
                guard.unlink(temporary)
    return _read_exact_record(path, record)


def _identity_evidence(
    *,
    sumtally_binding: dict[str, Any],
    pair_evidence: dict[str, Any],
    rtstruct_sha256: str,
    roi_number: int,
    ct_evidence: dict[str, Any],
    placement: dict[str, Any],
) -> dict[str, Any]:
    return {
        "contract_version": CONTRACT_VERSION,
        "threshold_rule": THRESHOLD_RULE,
        "statistics_rule": STATISTICS_RULE,
        "manifest_sha256": sumtally_binding["manifest_sha256"],
        "sumtally_binding_sha256": _canonical_sha256(sumtally_binding),
        "combined_pair_evidence_sha256": _canonical_sha256(pair_evidence),
        "combined_dose_sha256": pair_evidence["dose_sha256"],
        "combined_error_sha256": pair_evidence["error_sha256"],
        "rtstruct_sha256": rtstruct_sha256,
        "roi_number": roi_number,
        **ct_evidence,
        "rtdose_placement_sha256": _canonical_sha256(placement),
    }


def _file_change_token(path: Path) -> int:
    if os.name != "nt":
        return int(path.stat().st_ctime_ns)

    import ctypes
    from ctypes import wintypes
    import msvcrt

    global _WINDOWS_FILE_BASIC_INFO, _WINDOWS_GET_FILE_INFORMATION
    if _WINDOWS_FILE_BASIC_INFO is None:
        class FileBasicInfo(ctypes.Structure):
            _fields_ = (
                ("CreationTime", ctypes.c_longlong),
                ("LastAccessTime", ctypes.c_longlong),
                ("LastWriteTime", ctypes.c_longlong),
                ("ChangeTime", ctypes.c_longlong),
                ("FileAttributes", wintypes.DWORD),
            )

        api = ctypes.WinDLL("kernel32", use_last_error=True)
        function = api.GetFileInformationByHandleEx
        function.argtypes = (
            wintypes.HANDLE,
            ctypes.c_int,
            ctypes.c_void_p,
            wintypes.DWORD,
        )
        function.restype = wintypes.BOOL
        _WINDOWS_FILE_BASIC_INFO = FileBasicInfo
        _WINDOWS_GET_FILE_INFORMATION = function

    descriptor = os.open(
        os.fspath(path),
        os.O_RDONLY | getattr(os, "O_BINARY", 0),
    )
    try:
        information = _WINDOWS_FILE_BASIC_INFO()
        handle = msvcrt.get_osfhandle(descriptor)
        if not _WINDOWS_GET_FILE_INFORMATION(
            handle,
            0,
            ctypes.byref(information),
            ctypes.sizeof(information),
        ):
            raise ctypes.WinError(ctypes.get_last_error())
        return int(information.ChangeTime)
    finally:
        os.close(descriptor)


def _retained_file_snapshot(
    path: Path,
    *,
    label: str,
    expected_sha256: str | None,
    poll_sha256: bool,
) -> dict[str, Any]:
    supplied = Path(os.path.abspath(os.fspath(path)))
    if not supplied.is_file() or _is_link_or_junction(supplied):
        raise StructureRelativeErrorUnavailable(
            f"{label} must be an existing non-link regular file"
        )
    attributes = (
        "st_dev",
        "st_ino",
        "st_mode",
        "st_size",
        "st_mtime_ns",
        "st_ctime_ns",
    )
    before = supplied.stat()
    before_change_token = _file_change_token(supplied)
    if expected_sha256 is not None and not expected_sha256:
        raise StructureRelativeErrorUnavailable(
            f"{label} has missing validated digest evidence"
        )
    digest = file_sha256(supplied)
    after = supplied.stat()
    after_change_token = _file_change_token(supplied)
    if (
        before_change_token != after_change_token
        or any(getattr(before, name) != getattr(after, name) for name in attributes)
    ):
        raise StructureRelativeErrorUnavailable(f"{label} changed while being recorded")
    if expected_sha256 is not None and digest != expected_sha256:
        raise StructureRelativeErrorUnavailable(
            f"{label} does not match its validated digest evidence"
        )
    return {
        "path": str(supplied.resolve()),
        "sha256": digest,
        "poll_sha256": poll_sha256,
        "change_token": after_change_token,
        "stat": {name: int(getattr(after, name)) for name in attributes},
    }


def _verify_retained_file_snapshot(record: dict[str, Any]) -> None:
    path = Path(str(record.get("path") or ""))
    expected_stat = record.get("stat")
    if not isinstance(expected_stat, dict):
        raise StructureRelativeErrorUnavailable(
            "retained Structure relative-error source evidence is invalid"
        )
    if not path.is_file() or _is_link_or_junction(path):
        raise StructureRelativeErrorUnavailable(
            "a retained Structure relative-error source is missing or linked"
        )
    current = path.stat()
    if (
        _file_change_token(path) != record.get("change_token")
        or any(
            int(getattr(current, name)) != value
            for name, value in expected_stat.items()
        )
    ):
        raise StructureRelativeErrorUnavailable(
            "a retained Structure relative-error source changed"
        )
    # Same-size rewrites can preserve every metadata field, including Windows
    # ChangeTime. The legacy poll_sha256 hint must never bypass content checks.
    # GUI revalidation already runs in one background worker; stream the hash
    # without reparsing tallies, CT pixels or Structure membership.
    if file_sha256(path) != record.get("sha256"):
        raise StructureRelativeErrorUnavailable(
            "a retained Structure relative-error source changed"
        )
    after = path.stat()
    if (
        _file_change_token(path) != record.get("change_token")
        or any(
            int(getattr(after, name)) != value
            for name, value in expected_stat.items()
        )
    ):
        raise StructureRelativeErrorUnavailable(
            "a retained Structure relative-error source changed during validation"
        )


def _retained_directory_snapshot(
    path: Path,
    *,
    label: str,
    expected_entries: list[str],
) -> dict[str, Any]:
    supplied = Path(os.path.abspath(os.fspath(path)))
    if not supplied.is_dir() or _is_link_or_junction(supplied):
        raise StructureRelativeErrorUnavailable(
            f"{label} must be an existing non-link directory"
        )
    entries = sorted(item.name for item in supplied.iterdir())
    if entries != expected_entries:
        raise StructureRelativeErrorUnavailable(
            f"{label} membership does not match validated evidence"
        )
    return {
        "path": str(supplied.resolve()),
        "entries": entries,
    }


def _verify_retained_directory_snapshot(record: dict[str, Any]) -> None:
    path = Path(str(record.get("path") or ""))
    entries = record.get("entries")
    if (
        not isinstance(entries, list)
        or not path.is_dir()
        or _is_link_or_junction(path)
        or sorted(item.name for item in path.iterdir()) != entries
    ):
        raise StructureRelativeErrorUnavailable(
            "retained Structure relative-error source membership changed"
        )


def _capture_retained_validation(
    *,
    workspace_root: Path,
    rtstruct_path: Path,
    rtplan_path: Path,
    ct_reference_path: Path,
    roi_number: int,
    sumtally_binding: dict[str, Any],
    pair_evidence: dict[str, Any],
    control_evidence: dict[str, Any],
    ct_evidence: dict[str, Any],
    ct_directory_evidence: dict[str, Any],
    placement: dict[str, Any],
    rtstruct_sha256: str,
) -> dict[str, Any]:
    """Capture proven source identities for low-cost retained-display checks."""

    root = workspace_root.resolve()
    entries: dict[str, tuple[str, str | None, bool]] = {}

    def add(
        path: Path,
        *,
        label: str,
        expected_sha256: str | None = None,
        poll_sha256: bool = False,
    ) -> None:
        resolved = str(Path(os.path.abspath(os.fspath(path))).resolve())
        previous = entries.get(resolved)
        if previous is None:
            entries[resolved] = (label, expected_sha256, poll_sha256)
            return
        previous_label, previous_sha256, previous_poll = previous
        if (
            previous_sha256 is not None
            and expected_sha256 is not None
            and previous_sha256 != expected_sha256
        ):
            raise StructureRelativeErrorUnavailable(
                f"conflicting retained digest evidence for {label}"
            )
        entries[resolved] = (
            previous_label,
            previous_sha256 or expected_sha256,
            previous_poll or poll_sha256,
        )

    control_files = control_evidence.get("files")
    if not isinstance(control_files, list):
        raise StructureRelativeErrorUnavailable(
            "retained control-file evidence is unavailable"
        )
    receipt_path = Path(
        os.path.abspath(os.fspath(_supplemental_receipt_path(root)))
    )
    supplemental_receipt_captured = False
    for record in control_files:
        if not isinstance(record, dict):
            raise StructureRelativeErrorUnavailable(
                "retained control-file evidence is invalid"
            )
        control_path = Path(
            os.path.abspath(os.fspath(Path(str(record.get("path") or ""))))
        )
        if os.path.normcase(os.fspath(control_path)) == os.path.normcase(
            os.fspath(receipt_path)
        ):
            supplemental_receipt_captured = True
        add(
            control_path,
            label=str(record.get("label") or "control file"),
            expected_sha256=str(record.get("sha256") or ""),
            poll_sha256=True,
        )
    if not supplemental_receipt_captured:
        reject_supplemental_receipt_with_direct_evidence(root)
    add(
        Path(str(sumtally_binding["sumtally_input_path"])),
        label="Sumtally normalization input",
        expected_sha256=str(sumtally_binding["sumtally_input_sha256"]),
        poll_sha256=True,
    )
    add(
        Path(str(pair_evidence["dose_path"])),
        label="combined Sumtally dose output",
        expected_sha256=str(pair_evidence["dose_sha256"]),
    )
    add(
        Path(str(pair_evidence["error_path"])),
        label="combined Sumtally statistical-error output",
        expected_sha256=str(pair_evidence["error_sha256"]),
    )
    add(
        Path(str(control_evidence.get("sum_input_path") or "")),
        label="generated Sumtally wrapper input",
        expected_sha256=str(pair_evidence["sum_input_sha256"]),
        poll_sha256=True,
    )
    for field, label in (
        ("segment_output_evidence", "Sumtally-bound segment PHITS output"),
        ("wrapper_include_evidence", "Sumtally wrapper include"),
    ):
        records = sumtally_binding.get(field)
        if not isinstance(records, list):
            raise StructureRelativeErrorUnavailable(
                f"retained {field} evidence is unavailable"
            )
        for record in records:
            if not isinstance(record, dict):
                raise StructureRelativeErrorUnavailable(
                    f"retained {field} evidence is invalid"
                )
            add(
                Path(str(record.get("path") or "")),
                label=label,
                expected_sha256=str(record.get("sha256") or ""),
                poll_sha256=field == "wrapper_include_evidence",
            )

    reference = Path(os.path.abspath(os.fspath(ct_reference_path))).resolve()
    snapshot_root = reference.parent.parent
    ct_manifest_path = snapshot_root / "ct2phits_workspace_manifest.json"
    ct_summary_path = snapshot_root / "ct2phits_execution_summary.json"
    preparation_path = root / "analysis" / "public_preparation_workspace_summary.json"
    ct_manifest, _ = _stable_json(
        ct_manifest_path,
        label="CT2PHITS workspace manifest",
    )
    ct_summary, _ = _stable_json(
        ct_summary_path,
        label="CT2PHITS execution summary",
    )
    preparation, _ = _stable_json(
        preparation_path,
        label="3D-CRT workspace preparation summary",
    )
    for path, label, field in (
        (
            ct_manifest_path,
            "CT2PHITS workspace manifest",
            "ct2phits_manifest_sha256",
        ),
        (
            ct_summary_path,
            "CT2PHITS execution summary",
            "ct2phits_execution_summary_sha256",
        ),
        (
            preparation_path,
            "3D-CRT workspace preparation summary",
            "workspace_preparation_sha256",
        ),
    ):
        add(
            path,
            label=label,
            expected_sha256=str(ct_evidence[field]),
            poll_sha256=True,
        )
    recorded_series = ct_manifest.get("ct_series")
    if not isinstance(recorded_series, dict):
        raise StructureRelativeErrorUnavailable(
            "CT2PHITS manifest is missing frozen CT-series evidence"
        )
    copied_files = recorded_series.get("copied_files")
    copied_hashes = recorded_series.get("sha256")
    if not isinstance(copied_files, list) or not isinstance(copied_hashes, dict):
        raise StructureRelativeErrorUnavailable(
            "CT2PHITS manifest has incomplete CT digest evidence"
        )
    for value in copied_files:
        if not isinstance(value, str) or not value:
            raise StructureRelativeErrorUnavailable(
                "CT2PHITS manifest has an invalid CT file entry"
            )
        add(
            snapshot_root / value,
            label="frozen CT slice",
            expected_sha256=str(copied_hashes.get(value) or ""),
        )
    phits_generation = preparation.get("phits_generation")
    ct_assets = (
        phits_generation.get("ct_voxel_assets")
        if isinstance(phits_generation, dict)
        else None
    )
    raw_hashes = (
        ct_assets.get("raw_datfiles_sha256")
        if isinstance(ct_assets, dict)
        else None
    )
    if (
        not isinstance(raw_hashes, dict)
        or ct_summary.get("raw_datfiles_sha256") != raw_hashes
    ):
        raise StructureRelativeErrorUnavailable(
            "CT2PHITS DATfiles evidence does not match workspace preparation"
        )
    for name in RAW_CT2PHITS_NAMES:
        add(
            snapshot_root / "DATfiles" / name,
            label="CT2PHITS DATfile",
            expected_sha256=str(raw_hashes.get(name) or ""),
        )
    rtplan_record = ct_manifest.get("rtplan")
    if not isinstance(rtplan_record, dict):
        raise StructureRelativeErrorUnavailable(
            "CT2PHITS manifest is missing frozen RT Plan evidence"
        )
    add(
        rtplan_path,
        label="frozen RT Plan",
        expected_sha256=str(rtplan_record.get("sha256") or ""),
    )
    add(
        reference,
        label="frozen CT reference",
        expected_sha256=str(ct_evidence["ct_reference_sha256"]),
    )
    add(
        rtstruct_path,
        label="selected RT Structure Set",
        expected_sha256=rtstruct_sha256,
    )

    files = [
        _retained_file_snapshot(
            Path(path),
            label=label,
            expected_sha256=expected_sha256,
            poll_sha256=poll_sha256,
        )
        for path, (label, expected_sha256, poll_sha256) in sorted(entries.items())
    ]
    return {
        "schema_version": RETAINED_VALIDATION_SCHEMA_VERSION,
        "workspace_root": str(root),
        "request": {
            "rtstruct_path": str(Path(rtstruct_path).resolve()),
            "rtplan_path": str(Path(rtplan_path).resolve()),
            "ct_reference_path": str(reference),
            "roi_number": roi_number,
        },
        "sumtally_binding": json.loads(json.dumps(sumtally_binding)),
        "pair_evidence": json.loads(json.dumps(pair_evidence)),
        "pair_authority": (
            "supplemental_receipt"
            if supplemental_receipt_captured
            else "direct_execution"
        ),
        "ct_evidence": json.loads(json.dumps(ct_evidence)),
        "placement": json.loads(json.dumps(placement)),
        "files": files,
        "directories": [
            _retained_directory_snapshot(
                Path(str(ct_directory_evidence.get("path") or "")),
                label="frozen CT directory",
                expected_entries=ct_directory_evidence.get("entries", []),
            )
        ],
    }


def _verify_retained_validation(
    retained: dict[str, Any],
    *,
    workspace_root: Path,
    rtstruct_path: Path,
    rtplan_path: Path,
    ct_reference_path: Path,
    roi_number: int,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    if retained.get("schema_version") != RETAINED_VALIDATION_SCHEMA_VERSION:
        raise StructureRelativeErrorUnavailable(
            "retained Structure relative-error validation evidence is unavailable"
        )
    expected_request = {
        "rtstruct_path": str(Path(rtstruct_path).resolve()),
        "rtplan_path": str(Path(rtplan_path).resolve()),
        "ct_reference_path": str(Path(ct_reference_path).resolve()),
        "roi_number": roi_number,
    }
    if (
        retained.get("workspace_root") != str(workspace_root.resolve())
        or retained.get("request") != expected_request
    ):
        raise StructureRelativeErrorUnavailable(
            "the displayed Structure relative-error request is stale or mismatched"
        )
    files = retained.get("files")
    if not isinstance(files, list) or not files:
        raise StructureRelativeErrorUnavailable(
            "retained Structure relative-error source evidence is unavailable"
        )
    receipt_path = Path(
        os.path.abspath(os.fspath(_supplemental_receipt_path(workspace_root)))
    )
    supplemental_receipt_captured = False
    for record in files:
        if not isinstance(record, dict):
            raise StructureRelativeErrorUnavailable(
                "retained Structure relative-error source evidence is invalid"
            )
        retained_path = Path(str(record.get("path") or ""))
        if os.path.normcase(os.fspath(retained_path)) == os.path.normcase(
            os.fspath(receipt_path)
        ):
            supplemental_receipt_captured = True
        _verify_retained_file_snapshot(record)
    pair_authority = retained.get("pair_authority")
    if pair_authority == "direct_execution":
        if supplemental_receipt_captured:
            raise StructureRelativeErrorUnavailable(
                "retained direct evidence includes a supplemental recovery receipt"
            )
        reject_supplemental_receipt_with_direct_evidence(workspace_root)
    elif pair_authority == "supplemental_receipt":
        if not supplemental_receipt_captured:
            raise StructureRelativeErrorUnavailable(
                "retained supplemental recovery receipt evidence is unavailable"
            )
    else:
        raise StructureRelativeErrorUnavailable(
            "retained Structure relative-error pair authority is invalid"
        )
    directories = retained.get("directories")
    if not isinstance(directories, list):
        raise StructureRelativeErrorUnavailable(
            "retained Structure relative-error directory evidence is invalid"
        )
    for record in directories:
        if not isinstance(record, dict):
            raise StructureRelativeErrorUnavailable(
                "retained Structure relative-error directory evidence is invalid"
            )
        _verify_retained_directory_snapshot(record)
    values = tuple(
        retained.get(field)
        for field in (
            "sumtally_binding",
            "pair_evidence",
            "ct_evidence",
            "placement",
        )
    )
    if not all(isinstance(value, dict) for value in values):
        raise StructureRelativeErrorUnavailable(
            "retained Structure relative-error identity evidence is invalid"
        )
    return values  # type: ignore[return-value]


def evaluate_structure_relative_error(
    *,
    workspace_root: Path,
    rtstruct_path: Path,
    roi_number: int,
    rtplan_path: Path,
    ct_reference_path: Path,
) -> dict[str, Any]:
    """Evaluate and new-only publish one approved post-completion ROI summary."""

    if isinstance(roi_number, bool) or not isinstance(roi_number, int):
        raise StructureRelativeErrorUnavailable("ROI number must be an integer")
    root = Path(os.path.abspath(os.fspath(workspace_root)))
    if not root.is_dir() or _is_link_or_junction(root):
        raise StructureRelativeErrorUnavailable(
            "workspace root must be an existing non-link directory"
        )
    from dicomxphits.workspace_execution import WorkspaceExecutionLease

    try:
        with WorkspaceOutputGuard(root):
            with WorkspaceExecutionLease(root):
                (
                    dose,
                    error,
                    mesh,
                    sumtally_binding,
                    pair_evidence,
                    control_evidence,
                ) = _current_combined_source(root)
                (
                    series,
                    ct_evidence,
                    ct_directory_evidence,
                ) = _frozen_ct_series(
                    ct_reference_path,
                    workspace_root=root,
                )
                plan_evidence = validate_full_plan_context(
                    rtplan_path=rtplan_path,
                    workspace_root=root,
                    ct_reference_path=ct_reference_path,
                )
                placement = derive_rtdose_placement(
                    sumtally_binding["tally_geometry_binding"]["mesh_geometry"],
                    rtplan_isocenter_dicom_mm=plan_evidence[
                        "rtplan_isocenter_dicom_mm"
                    ],
                )
                try:
                    ct_mask, roi_name, rtstruct_sha256 = (
                        load_rtstruct_roi_mask_by_number(
                            rtstruct_path,
                            series=series,
                            roi_number=roi_number,
                        )
                    )
                except Exception as exc:
                    raise StructureRelativeErrorUnavailable(
                        f"selected RT Structure ROI is unavailable: {exc}"
                    ) from exc
                dose_grid = _values_in_rtdose_order(dose, mesh)
                error_grid = _values_in_rtdose_order(error, mesh)
                expected_shape = tuple(
                    int(value)
                    for value in placement["output_shape_frames_rows_columns"]
                )
                if dose_grid.shape != expected_shape or error_grid.shape != expected_shape:
                    raise StructureRelativeErrorUnavailable(
                        "combined grids do not match accepted RTDOSE affine shape"
                    )
                dmax = float(np.max(dose_grid))
                if not math.isfinite(dmax) or dmax <= 0.0:
                    raise StructureRelativeErrorUnavailable(
                        "global combined Dmax is not finite and positive"
                    )
                mapped = _structure_membership_on_dose_grid(
                    placement=placement,
                    series=series,
                    ct_mask=ct_mask,
                )
                mapped_count = int(np.count_nonzero(mapped))
                threshold = THRESHOLD_FRACTION * dmax
                above = mapped & (dose_grid > threshold)
                above_count = int(np.count_nonzero(above))
                if above_count == 0:
                    raise StructureRelativeErrorUnavailable(
                        "the selected Structure has no voxel above the fixed threshold"
                    )
                zero_error_count = int(np.count_nonzero(above & (error_grid == 0.0)))
                eligible = above & (error_grid > 0.0)
                eligible_count = int(np.count_nonzero(eligible))
                statistics = _statistics_percent(error_grid[eligible])

                identity_evidence = _identity_evidence(
                    sumtally_binding=sumtally_binding,
                    pair_evidence=pair_evidence,
                    rtstruct_sha256=rtstruct_sha256,
                    roi_number=roi_number,
                    ct_evidence=ct_evidence,
                    placement=placement,
                )
                evaluation_sha256 = _canonical_sha256(identity_evidence)
                record = {
                    "schema_version": SCHEMA_VERSION,
                    "evaluation_sha256": evaluation_sha256,
                    "contract_version": CONTRACT_VERSION,
                    "identity_evidence": identity_evidence,
                    "population": {
                        "mapped_structure_voxel_count": mapped_count,
                        "above_threshold_voxel_count": above_count,
                        "eligible_voxel_count": eligible_count,
                        "zero_relative_error_exclusion_count": zero_error_count,
                    },
                    "statistics_percent": statistics,
                    "presentation": {
                        "threshold": "D > 0.5 * global combined Dmax",
                        "voxel_weighting": "unweighted eligible voxels",
                        "statement": NON_CLINICAL_LABEL,
                    },
                    "authority": {
                        "live_observation": False,
                        "completion_evidence": False,
                        "convergence_evidence": False,
                        "downstream_eligibility": False,
                        "clinical_acceptance": False,
                    },
                }
                result_path = root / RESULT_RELATIVE_ROOT / f"{evaluation_sha256}.json"
                published = _publish_new_record(root, result_path, record)
                retained_validation = _capture_retained_validation(
                    workspace_root=root,
                    rtstruct_path=rtstruct_path,
                    rtplan_path=rtplan_path,
                    ct_reference_path=ct_reference_path,
                    roi_number=roi_number,
                    sumtally_binding=sumtally_binding,
                    pair_evidence=pair_evidence,
                    control_evidence=control_evidence,
                    ct_evidence=ct_evidence,
                    ct_directory_evidence=ct_directory_evidence,
                    placement=placement,
                    rtstruct_sha256=rtstruct_sha256,
                )
    except StructureRelativeErrorUnavailable:
        raise
    except Exception as exc:
        raise StructureRelativeErrorUnavailable(str(exc)) from exc
    return {
        **published,
        "display_roi_name": roi_name,
        "result_path": str(result_path),
        "_retained_validation": retained_validation,
    }


def revalidate_structure_relative_error_result(
    *,
    workspace_root: Path,
    rtstruct_path: Path,
    roi_number: int,
    rtplan_path: Path,
    ct_reference_path: Path,
    expected_result: dict[str, Any],
) -> dict[str, Any]:
    """Revalidate one exact persisted result without publishing another result."""

    root = Path(os.path.abspath(os.fspath(workspace_root)))
    if not root.is_dir() or _is_link_or_junction(root):
        raise StructureRelativeErrorUnavailable(
            "workspace root must be an existing non-link directory"
        )

    try:
        with WorkspaceOutputGuard(root, read_only=True):
            retained = expected_result.get("_retained_validation")
            if not isinstance(retained, dict):
                raise StructureRelativeErrorUnavailable(
                    "retained Structure relative-error validation evidence is unavailable"
                )
            sumtally_binding, pair_evidence, ct_evidence, placement = (
                _verify_retained_validation(
                    retained,
                    workspace_root=root,
                    rtstruct_path=rtstruct_path,
                    rtplan_path=rtplan_path,
                    ct_reference_path=ct_reference_path,
                    roi_number=roi_number,
                )
            )
            expected_identity = expected_result.get("identity_evidence")
            if not isinstance(expected_identity, dict):
                raise StructureRelativeErrorUnavailable(
                    "the displayed Structure relative-error identity is invalid"
                )
            identity_evidence = _identity_evidence(
                sumtally_binding=sumtally_binding,
                pair_evidence=pair_evidence,
                rtstruct_sha256=str(expected_identity.get("rtstruct_sha256") or ""),
                roi_number=roi_number,
                ct_evidence=ct_evidence,
                placement=placement,
            )
            evaluation_sha256 = _canonical_sha256(identity_evidence)
            if (
                expected_identity != identity_evidence
                or expected_result.get("evaluation_sha256") != evaluation_sha256
            ):
                raise StructureRelativeErrorUnavailable(
                    "the displayed Structure relative-error result identity "
                    "is stale or mismatched"
                )
            result_path = root / RESULT_RELATIVE_ROOT / f"{evaluation_sha256}.json"
            if expected_result.get("result_path") != str(result_path):
                raise StructureRelativeErrorUnavailable(
                    "the displayed Structure relative-error result path is mismatched"
                )
            expected_record = {
                key: value
                for key, value in expected_result.items()
                if key
                not in {"display_roi_name", "result_path", "_retained_validation"}
            }
            persisted = _read_exact_record(result_path, expected_record)
    except StructureRelativeErrorUnavailable:
        raise
    except Exception as exc:
        raise StructureRelativeErrorUnavailable(str(exc)) from exc
    return {
        **persisted,
        "display_roi_name": expected_result.get("display_roi_name", ""),
        "result_path": str(result_path),
        "_retained_validation": retained,
    }


def format_structure_relative_error(result: dict[str, Any]) -> str:
    """Render only the approved post-completion scalar presentation."""

    statistics = result["statistics_percent"]
    population = result["population"]
    roi_number = result["identity_evidence"]["roi_number"]
    roi_name = str(result.get("display_roi_name") or "").strip()
    roi_label = f"ROI {roi_number}" + (f" — {roi_name}" if roi_name else "")
    return "\n".join(
        (
            roi_label,
            "D > 0.5 * global combined Dmax; unweighted eligible voxels",
            (
                f"Mean {statistics['mean']:.6g}%   "
                f"Median {statistics['median']:.6g}%   "
                f"P95 {statistics['p95']:.6g}%"
            ),
            (
                "Counts: mapped "
                f"{population['mapped_structure_voxel_count']}, above threshold "
                f"{population['above_threshold_voxel_count']}, eligible "
                f"{population['eligible_voxel_count']}, zero r.err excluded "
                f"{population['zero_relative_error_exclusion_count']}"
            ),
            NON_CLINICAL_LABEL,
        )
    )
