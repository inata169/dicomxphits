from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path
from typing import Any, Sequence

import numpy as np
import pydicom

from dicomxphits.sumtally_inputs import file_sha256


TALLY_GEOMETRY_SCHEMA_VERSION = "dicomxphits_public_tally_geometry_v1"
TALLY_BINDING_SCHEMA_VERSION = "dicomxphits_public_tally_geometry_binding_v1"
RTDOSE_PLACEMENT_SCHEMA_VERSION = "dicomxphits_public_rtdose_placement_v1"
COORDINATE_TRANSFORM_VERSION = "phits_iec_fixed_to_dicom_lps_v1"
OUTPUT_AXIS_MAPPING = "phits_y_z_reversed_x_to_dicom_frames_rows_columns_v1"
GEOMETRY_TOLERANCE_MM = 1.0e-6
_NUMBER = r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[EeDd][-+]?\d+)?"
_ASSIGNMENT_PATTERN = re.compile(
    rf"^\s*(xmin|xmax|nx|ymin|ymax|ny|zmin|zmax|nz)\s*=\s*({_NUMBER})(?:\s|$)",
    re.IGNORECASE,
)
_FIELDS = ("xmin", "xmax", "nx", "ymin", "ymax", "ny", "zmin", "zmax", "nz")


def _canonical_sha256(value: Any) -> str:
    payload = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _finite_float(value: Any, *, label: str) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} must be finite and numeric") from exc
    if not math.isfinite(result):
        raise ValueError(f"{label} must be finite and numeric")
    return 0.0 if result == 0.0 else result


def _positive_int(value: Any, *, label: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{label} must be a positive integer")
    try:
        numeric = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} must be a positive integer") from exc
    if not math.isfinite(numeric) or not numeric.is_integer() or numeric <= 0:
        raise ValueError(f"{label} must be a positive integer")
    return int(numeric)


def _axis_record(minimum: Any, maximum: Any, count: Any, *, axis: str) -> dict[str, Any]:
    minimum_cm = _finite_float(minimum, label=f"tally {axis} minimum")
    maximum_cm = _finite_float(maximum, label=f"tally {axis} maximum")
    bin_count = _positive_int(count, label=f"tally {axis} bin count")
    if maximum_cm <= minimum_cm:
        raise ValueError(f"tally {axis} maximum must be greater than its minimum")
    return {
        "minimum_cm": minimum_cm,
        "maximum_cm": maximum_cm,
        "bin_count": bin_count,
        "spacing_cm": (maximum_cm - minimum_cm) / bin_count,
    }


def normalize_tally_mesh_geometry(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError("tally mesh geometry must be an object")
    axes_value = value.get("axes")
    if not isinstance(axes_value, dict):
        raise ValueError("tally mesh geometry is missing axes")
    axes: dict[str, dict[str, Any]] = {}
    for axis in ("x", "y", "z"):
        record = axes_value.get(axis)
        if not isinstance(record, dict):
            raise ValueError(f"tally mesh geometry is missing axis {axis}")
        axes[axis] = _axis_record(
            record.get("minimum_cm"),
            record.get("maximum_cm"),
            record.get("bin_count"),
            axis=axis,
        )
    return {
        "schema_version": TALLY_GEOMETRY_SCHEMA_VERSION,
        "coordinate_system": "phits_iec_fixed_cm_isocenter_anchored",
        "bounds_semantics": "bin_edges",
        "axes": axes,
    }


def tally_mesh_geometry_sha256(geometry: Any) -> str:
    return _canonical_sha256(normalize_tally_mesh_geometry(geometry))


def parse_tally_mesh_geometry(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"PHITS tally output not found: {path}")
    values: dict[str, list[float]] = {field: [] for field in _FIELDS}
    with path.open("r", encoding="utf-8", errors="replace") as stream:
        for line in stream:
            match = _ASSIGNMENT_PATTERN.match(line)
            if match is None:
                continue
            field = match.group(1).lower()
            number = _finite_float(
                match.group(2).replace("D", "E").replace("d", "e"),
                label=f"{path.name} {field}",
            )
            values[field].append(number)

    selected: dict[str, float] = {}
    for field, candidates in values.items():
        unique = set(candidates)
        if not unique:
            raise ValueError(
                f"PHITS tally output is missing {field} mesh evidence: {path}"
            )
        if len(unique) != 1:
            raise ValueError(
                f"PHITS tally output has ambiguous {field} mesh evidence: {path}"
            )
        selected[field] = next(iter(unique))

    return normalize_tally_mesh_geometry(
        {
            "axes": {
                "x": {
                    "minimum_cm": selected["xmin"],
                    "maximum_cm": selected["xmax"],
                    "bin_count": selected["nx"],
                },
                "y": {
                    "minimum_cm": selected["ymin"],
                    "maximum_cm": selected["ymax"],
                    "bin_count": selected["ny"],
                },
                "z": {
                    "minimum_cm": selected["zmin"],
                    "maximum_cm": selected["zmax"],
                    "bin_count": selected["nz"],
                },
            }
        }
    )


def segment_tally_geometry_binding(paths: Sequence[Path]) -> dict[str, Any]:
    resolved_paths = sorted(
        {path.resolve() for path in paths},
        key=lambda item: str(item).casefold(),
    )
    if not resolved_paths:
        raise ValueError("at least one active segment tally output is required")
    records: list[dict[str, Any]] = []
    common_geometry: dict[str, Any] | None = None
    common_sha256: str | None = None
    for path in resolved_paths:
        geometry = parse_tally_mesh_geometry(path)
        geometry_sha256 = tally_mesh_geometry_sha256(geometry)
        if common_geometry is None:
            common_geometry = geometry
            common_sha256 = geometry_sha256
        elif geometry_sha256 != common_sha256:
            raise ValueError(
                "active segment tally outputs do not share one mesh geometry"
            )
        records.append(
            {
                "path": str(path),
                "sha256": file_sha256(path),
                "mesh_geometry_sha256": geometry_sha256,
            }
        )
    assert common_geometry is not None and common_sha256 is not None
    return {
        "schema_version": TALLY_BINDING_SCHEMA_VERSION,
        "mesh_geometry": common_geometry,
        "mesh_geometry_sha256": common_sha256,
        "segment_tallies": records,
    }


def sumtally_output_geometry_evidence(
    path: Path,
    *,
    expected_geometry: Any,
) -> dict[str, Any]:
    geometry = parse_tally_mesh_geometry(path)
    geometry_sha256 = tally_mesh_geometry_sha256(geometry)
    expected_sha256 = tally_mesh_geometry_sha256(expected_geometry)
    if geometry_sha256 != expected_sha256:
        raise ValueError(
            "Sumtally output mesh geometry does not match active segment tallies"
        )
    return {
        "path": str(path.resolve()),
        "sha256": file_sha256(path),
        "mesh_geometry": geometry,
        "mesh_geometry_sha256": geometry_sha256,
        "matches_segment_tallies": True,
    }


def _axis_centres(axis: dict[str, Any]) -> list[float]:
    minimum = float(axis["minimum_cm"])
    spacing = float(axis["spacing_cm"])
    count = int(axis["bin_count"])
    return [minimum + (index + 0.5) * spacing for index in range(count)]


def _finite_vector(
    value: Sequence[float] | None,
    *,
    label: str,
) -> tuple[float, float, float]:
    if value is None:
        raise ValueError(f"{label} is required")
    try:
        result = tuple(_finite_float(item, label=label) for item in value)
    except TypeError as exc:
        raise ValueError(f"{label} must contain three finite values") from exc
    if len(result) != 3:
        raise ValueError(f"{label} must contain three finite values")
    return result  # type: ignore[return-value]


def _map_iec_cm_to_dicom_mm(
    isocenter_mm: Sequence[float],
    point_cm: Sequence[float],
) -> tuple[float, float, float]:
    return (
        float(isocenter_mm[0]) - 10.0 * float(point_cm[0]),
        float(isocenter_mm[1]) + 10.0 * float(point_cm[2]),
        float(isocenter_mm[2]) + 10.0 * float(point_cm[1]),
    )


def derive_rtdose_placement(
    mesh_geometry: Any,
    *,
    rtplan_isocenter_dicom_mm: Sequence[float],
    target_center_dicom_mm: Sequence[float] | None = None,
    target_reason: str | None = None,
) -> dict[str, Any]:
    mesh = normalize_tally_mesh_geometry(mesh_geometry)
    isocenter = _finite_vector(
        rtplan_isocenter_dicom_mm,
        label="RT Plan isocenter DICOM mm",
    )
    axes = mesh["axes"]
    xs = _axis_centres(axes["x"])
    ys = _axis_centres(axes["y"])
    zs = _axis_centres(axes["z"])
    rule_center = _map_iec_cm_to_dicom_mm(
        isocenter,
        (
            (xs[0] + xs[-1]) / 2.0,
            (ys[0] + ys[-1]) / 2.0,
            (zs[0] + zs[-1]) / 2.0,
        ),
    )

    if target_center_dicom_mm is None:
        if target_reason is not None and target_reason.strip():
            raise ValueError("target reason requires a target center")
        requested_target = None
        reason = None
        translation = (0.0, 0.0, 0.0)
        mode = "plan_and_tally_affine"
    else:
        requested_target = _finite_vector(
            target_center_dicom_mm,
            label="target center DICOM mm",
        )
        reason = str(target_reason or "").strip()
        if not reason:
            raise ValueError("target center override requires a non-empty reason")
        translation = tuple(
            requested - derived
            for requested, derived in zip(requested_target, rule_center)
        )
        mode = "explicit_reasoned_target_override"

    mapped_first = _map_iec_cm_to_dicom_mm(
        isocenter,
        (xs[-1], ys[0], zs[0]),
    )
    image_position = tuple(
        value + shift for value, shift in zip(mapped_first, translation)
    )
    pixel_spacing = (
        10.0 * float(axes["z"]["spacing_cm"]),
        10.0 * float(axes["x"]["spacing_cm"]),
    )
    frame_spacing = 10.0 * float(axes["y"]["spacing_cm"])
    frame_offsets = [frame_spacing * index for index in range(len(ys))]
    output_center = tuple(
        value + shift for value, shift in zip(rule_center, translation)
    )
    return {
        "schema_version": RTDOSE_PLACEMENT_SCHEMA_VERSION,
        "coordinate_transform_version": COORDINATE_TRANSFORM_VERSION,
        "axis_mapping": OUTPUT_AXIS_MAPPING,
        "mode": mode,
        "rtplan_isocenter_dicom_mm": list(isocenter),
        "mesh_geometry": mesh,
        "mesh_geometry_sha256": tally_mesh_geometry_sha256(mesh),
        "output_shape_frames_rows_columns": [len(ys), len(zs), len(xs)],
        "image_orientation_patient": [1.0, 0.0, 0.0, 0.0, 1.0, 0.0],
        "pixel_spacing_mm": list(pixel_spacing),
        "grid_frame_offset_vector_mm": frame_offsets,
        "image_position_patient_mm": list(image_position),
        "rule_derived_volume_center_dicom_mm": list(rule_center),
        "requested_target_center_dicom_mm": (
            list(requested_target) if requested_target is not None else None
        ),
        "target_reason": reason,
        "applied_translation_dicom_mm": list(translation),
        "output_volume_center_dicom_mm": list(output_center),
        "absolute_tolerance_mm": GEOMETRY_TOLERANCE_MM,
        "relative_tolerance": 0.0,
    }


def expected_voxel_position(
    placement: dict[str, Any],
    *,
    frame: int,
    row: int,
    column: int,
) -> tuple[float, float, float]:
    mesh = normalize_tally_mesh_geometry(placement.get("mesh_geometry"))
    isocenter = _finite_vector(
        placement.get("rtplan_isocenter_dicom_mm"),
        label="placement RT Plan isocenter DICOM mm",
    )
    translation = _finite_vector(
        placement.get("applied_translation_dicom_mm"),
        label="placement applied translation DICOM mm",
    )
    axes = mesh["axes"]
    xs = _axis_centres(axes["x"])
    ys = _axis_centres(axes["y"])
    zs = _axis_centres(axes["z"])
    if not (0 <= frame < len(ys) and 0 <= row < len(zs) and 0 <= column < len(xs)):
        raise ValueError("voxel index is outside expected placement geometry")
    mapped = _map_iec_cm_to_dicom_mm(
        isocenter,
        (xs[len(xs) - 1 - column], ys[frame], zs[row]),
    )
    return tuple(value + shift for value, shift in zip(mapped, translation))


def validate_rtdose_placement(
    path: Path,
    *,
    expected_placement: dict[str, Any],
) -> dict[str, Any]:
    dataset = pydicom.dcmread(str(path), stop_before_pixels=True)
    if str(getattr(dataset, "Modality", "") or "").upper() != "RTDOSE":
        raise ValueError("final coordinate placement requires Modality RTDOSE")

    expected_shape = tuple(
        _positive_int(value, label="expected RTDOSE dimension")
        for value in expected_placement.get("output_shape_frames_rows_columns", [])
    )
    if len(expected_shape) != 3:
        raise ValueError("expected RTDOSE placement is missing output dimensions")
    actual_shape = (
        _positive_int(getattr(dataset, "NumberOfFrames", None), label="RTDOSE NumberOfFrames"),
        _positive_int(getattr(dataset, "Rows", None), label="RTDOSE Rows"),
        _positive_int(getattr(dataset, "Columns", None), label="RTDOSE Columns"),
    )
    if actual_shape != expected_shape:
        raise ValueError(
            f"final RTDOSE dimensions do not match tally geometry: {actual_shape} != {expected_shape}"
        )

    def vector(name: str, count: int) -> np.ndarray:
        raw = getattr(dataset, name, None)
        if raw is None:
            raise ValueError(f"final RTDOSE is missing {name}")
        try:
            result = np.asarray([float(item) for item in raw], dtype=float)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"final RTDOSE {name} must be numeric") from exc
        if result.shape != (count,) or not np.all(np.isfinite(result)):
            raise ValueError(f"final RTDOSE {name} has invalid geometry")
        return result

    ipp = vector("ImagePositionPatient", 3)
    iop = vector("ImageOrientationPatient", 6)
    spacing = vector("PixelSpacing", 2)
    offsets = vector("GridFrameOffsetVector", actual_shape[0])
    expected_iop = np.asarray(expected_placement["image_orientation_patient"], dtype=float)
    expected_spacing = np.asarray(expected_placement["pixel_spacing_mm"], dtype=float)
    expected_offsets = np.asarray(
        expected_placement["grid_frame_offset_vector_mm"],
        dtype=float,
    )
    tolerance = float(expected_placement.get("absolute_tolerance_mm", GEOMETRY_TOLERANCE_MM))
    if tolerance != GEOMETRY_TOLERANCE_MM:
        raise ValueError("expected RTDOSE placement uses an unsupported tolerance")
    for label, actual, expected in (
        ("ImageOrientationPatient", iop, expected_iop),
        ("PixelSpacing", spacing, expected_spacing),
        ("GridFrameOffsetVector", offsets, expected_offsets),
    ):
        if actual.shape != expected.shape or not np.allclose(
            actual,
            expected,
            rtol=0.0,
            atol=tolerance,
        ):
            raise ValueError(f"final RTDOSE {label} does not match tally geometry")

    column_direction = iop[:3]
    row_direction = iop[3:]
    normal_direction = np.cross(column_direction, row_direction)
    point_indices = {
        "first": (0, 0, 0),
        "centre": tuple(value // 2 for value in actual_shape),
        "edge": (0, actual_shape[1] - 1, actual_shape[2] - 1),
        "final": tuple(value - 1 for value in actual_shape),
    }
    point_records: dict[str, Any] = {}
    maximum_residual = 0.0
    for label, (frame, row, column) in point_indices.items():
        actual = (
            ipp
            + column_direction * (column * spacing[1])
            + row_direction * (row * spacing[0])
            + normal_direction * offsets[frame]
        )
        expected = np.asarray(
            expected_voxel_position(
                expected_placement,
                frame=frame,
                row=row,
                column=column,
            ),
            dtype=float,
        )
        residual = np.abs(actual - expected)
        maximum_residual = max(maximum_residual, float(np.max(residual)))
        point_records[label] = {
            "index_frames_rows_columns": [frame, row, column],
            "actual_dicom_mm": actual.tolist(),
            "expected_dicom_mm": expected.tolist(),
            "absolute_component_residual_mm": residual.tolist(),
        }
    if maximum_residual > tolerance:
        raise ValueError(
            "final RTDOSE patient-coordinate residual exceeds 1e-6 mm"
        )
    return {
        "path": str(path),
        "placement_schema_version": expected_placement.get("schema_version"),
        "coordinate_transform_version": expected_placement.get(
            "coordinate_transform_version"
        ),
        "axis_mapping": expected_placement.get("axis_mapping"),
        "points": point_records,
        "maximum_absolute_component_residual_mm": maximum_residual,
        "absolute_tolerance_mm": tolerance,
        "relative_tolerance": 0.0,
        "validated": True,
    }
