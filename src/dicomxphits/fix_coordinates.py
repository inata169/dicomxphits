from __future__ import annotations

import argparse
import json
import math
import io
from pathlib import Path
from typing import Any, Sequence

import numpy as np
import pydicom

from dicomxphits.safe_output import WorkspaceOutputGuard
from pydicom.dataset import Dataset

from dicomxphits.rtdose_geometry import validate_rtdose_placement
from dicomxphits.sumtally_inputs import file_sha256


SCHEMA_VERSION = "dicomxphits_public_rtdose_coordinate_correction_v1"
AXIS_MAPPING = "phits2dicom_frames_rows_columns_to_dicom_rows_frames_columns_v1"
EXPECTED_AXIAL_IOP = np.asarray([1.0, 0.0, 0.0, 0.0, 1.0, 0.0])
GEOMETRY_TOLERANCE = 1.0e-6


def coordinate_summary_path(output_path: Path) -> Path:
    return output_path.with_name(f"{output_path.stem}.coordinate.json")


def corrected_rtdose_path(raw_path: Path) -> Path:
    return raw_path.with_name(f"{raw_path.stem}.fixed.dcm")


def _numeric_vector(dataset: Dataset, name: str, length: int) -> np.ndarray:
    value = getattr(dataset, name, None)
    if value is None:
        raise ValueError(f"RTDOSE is missing required {name}")
    try:
        result = np.asarray([float(item) for item in value], dtype=float)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"RTDOSE {name} must contain numeric values") from exc
    if result.shape != (length,) or not np.all(np.isfinite(result)):
        raise ValueError(f"RTDOSE {name} must contain {length} finite values")
    return result


def _validate_orientation(dataset: Dataset) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    orientation = _numeric_vector(dataset, "ImageOrientationPatient", 6)
    column_direction = orientation[:3]
    row_direction = orientation[3:]
    if not math.isclose(
        float(np.linalg.norm(column_direction)),
        1.0,
        abs_tol=GEOMETRY_TOLERANCE,
    ):
        raise ValueError("RTDOSE ImageOrientationPatient first direction must be unit length")
    if not math.isclose(
        float(np.linalg.norm(row_direction)),
        1.0,
        abs_tol=GEOMETRY_TOLERANCE,
    ):
        raise ValueError("RTDOSE ImageOrientationPatient second direction must be unit length")
    if not math.isclose(
        float(np.dot(column_direction, row_direction)),
        0.0,
        abs_tol=GEOMETRY_TOLERANCE,
    ):
        raise ValueError("RTDOSE ImageOrientationPatient directions must be orthogonal")
    if not np.allclose(
        orientation,
        EXPECTED_AXIAL_IOP,
        rtol=0.0,
        atol=GEOMETRY_TOLERANCE,
    ):
        raise ValueError(
            "RTDOSE ImageOrientationPatient is outside the supported axial "
            "PHITS2DICOM contract"
        )
    return column_direction, row_direction, np.cross(column_direction, row_direction)


def _relative_frame_offsets(
    dataset: Dataset,
    *,
    number_of_frames: int,
    image_position: np.ndarray,
) -> tuple[np.ndarray, float, str]:
    offsets = _numeric_vector(dataset, "GridFrameOffsetVector", number_of_frames)
    if number_of_frames < 2:
        raise ValueError("RTDOSE coordinate correction requires at least two source frames")
    if math.isclose(float(offsets[0]), 0.0, abs_tol=GEOMETRY_TOLERANCE):
        relative = offsets
        interpretation = "relative_to_image_position_patient"
    elif math.isclose(
        float(offsets[0]),
        float(image_position[2]),
        abs_tol=GEOMETRY_TOLERANCE,
    ):
        relative = offsets - offsets[0]
        interpretation = "absolute_patient_z"
    else:
        raise ValueError("RTDOSE GridFrameOffsetVector interpretation is ambiguous")
    steps = np.diff(relative)
    if np.any(steps <= 0.0) or not np.all(np.isfinite(steps)):
        raise ValueError("RTDOSE GridFrameOffsetVector must be strictly increasing")
    spacing = float(steps[0])
    if not np.allclose(steps, spacing, rtol=0.0, atol=GEOMETRY_TOLERANCE):
        raise ValueError("RTDOSE GridFrameOffsetVector spacing must be uniform")
    return relative, spacing, interpretation


def _geometry_record(
    *,
    array: np.ndarray,
    pixel_spacing: Sequence[float],
    frame_offsets: Sequence[float],
    image_position: Sequence[float],
    image_orientation: Sequence[float],
    volume_center: Sequence[float],
    frame_offset_interpretation: str,
) -> dict[str, Any]:
    return {
        "array_shape_frames_rows_columns": [int(value) for value in array.shape],
        "PixelSpacing": [float(value) for value in pixel_spacing],
        "GridFrameOffsetVector": [float(value) for value in frame_offsets],
        "ImagePositionPatient": [float(value) for value in image_position],
        "ImageOrientationPatient": [float(value) for value in image_orientation],
        "volume_center": [float(value) for value in volume_center],
        "frame_offset_interpretation": frame_offset_interpretation,
    }


def _placement_vector(
    placement: dict[str, Any],
    key: str,
    length: int,
) -> np.ndarray:
    value = placement.get(key)
    try:
        result = np.asarray([float(item) for item in value], dtype=float)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"expected placement {key} must be numeric") from exc
    if result.shape != (length,) or not np.all(np.isfinite(result)):
        raise ValueError(
            f"expected placement {key} must contain {length} finite values"
        )
    return result


def _placement_shape(placement: dict[str, Any]) -> tuple[int, int, int]:
    value = placement.get("output_shape_frames_rows_columns")
    if not isinstance(value, (list, tuple)) or len(value) != 3:
        raise ValueError("expected placement is missing output dimensions")
    try:
        shape = tuple(int(item) for item in value)
    except (TypeError, ValueError) as exc:
        raise ValueError("expected placement dimensions must be integers") from exc
    if any(item <= 0 for item in shape):
        raise ValueError("expected placement dimensions must be positive")
    return shape  # type: ignore[return-value]


def fix_coordinates(
    input_path: Path,
    output_path: Path,
    *,
    summary_path: Path | None = None,
    expected_placement: dict[str, Any] | None = None,
    guard: WorkspaceOutputGuard | None = None,
) -> dict[str, Any]:
    """Place PHITS2DICOM dose voxels on the supported DICOM LPS grid."""

    dataset = pydicom.dcmread(str(input_path))
    input_sha256 = file_sha256(input_path)
    if str(getattr(dataset, "Modality", "")).upper() != "RTDOSE":
        raise ValueError("Coordinate correction requires Modality RTDOSE")
    try:
        frames = int(dataset.NumberOfFrames)
        rows = int(dataset.Rows)
        columns = int(dataset.Columns)
    except (AttributeError, TypeError, ValueError) as exc:
        raise ValueError("RTDOSE dimensions must be present and numeric") from exc
    if min(frames, rows, columns) <= 0:
        raise ValueError("RTDOSE dimensions must be positive")

    source = np.asarray(dataset.pixel_array)
    if source.shape != (frames, rows, columns):
        raise ValueError(
            "RTDOSE decoded pixel array does not match NumberOfFrames, Rows, and Columns"
        )
    spacing = _numeric_vector(dataset, "PixelSpacing", 2)
    if np.any(spacing <= 0.0):
        raise ValueError("RTDOSE PixelSpacing values must be positive")
    source_row_spacing, source_column_spacing = map(float, spacing)
    source_position = _numeric_vector(dataset, "ImagePositionPatient", 3)
    source_orientation = _numeric_vector(dataset, "ImageOrientationPatient", 6)
    column_direction, row_direction, normal_direction = _validate_orientation(dataset)
    source_offsets, source_frame_spacing, offset_interpretation = _relative_frame_offsets(
        dataset,
        number_of_frames=frames,
        image_position=source_position,
    )

    source_center = (
        source_position
        + column_direction * ((columns - 1) * source_column_spacing / 2.0)
        + row_direction * ((rows - 1) * source_row_spacing / 2.0)
        + normal_direction * ((source_offsets[0] + source_offsets[-1]) / 2.0)
    )
    corrected = np.ascontiguousarray(source.transpose(1, 0, 2))
    corrected_frames, corrected_rows, corrected_columns = corrected.shape
    corrected_pixel_spacing = np.asarray(
        (source_frame_spacing, source_column_spacing),
        dtype=float,
    )
    corrected_offsets = np.arange(corrected_frames, dtype=float) * source_row_spacing
    corrected_position = (
        source_center
        - EXPECTED_AXIAL_IOP[:3]
        * ((corrected_columns - 1) * source_column_spacing / 2.0)
        - EXPECTED_AXIAL_IOP[3:]
        * ((corrected_rows - 1) * source_frame_spacing / 2.0)
        - np.cross(EXPECTED_AXIAL_IOP[:3], EXPECTED_AXIAL_IOP[3:])
        * ((corrected_offsets[0] + corrected_offsets[-1]) / 2.0)
    )
    output_center = source_center
    center_mode = "preserve_source_physical_volume_center"

    if expected_placement is not None:
        expected_shape = _placement_shape(expected_placement)
        if corrected.shape != expected_shape:
            raise ValueError(
                "PHITS2DICOM voxel dimensions do not match bound tally geometry: "
                f"{corrected.shape} != {expected_shape}"
            )
        expected_orientation = _placement_vector(
            expected_placement,
            "image_orientation_patient",
            6,
        )
        expected_pixel_spacing = _placement_vector(
            expected_placement,
            "pixel_spacing_mm",
            2,
        )
        expected_offsets = _placement_vector(
            expected_placement,
            "grid_frame_offset_vector_mm",
            corrected_frames,
        )
        expected_position = _placement_vector(
            expected_placement,
            "image_position_patient_mm",
            3,
        )
        output_center = _placement_vector(
            expected_placement,
            "output_volume_center_dicom_mm",
            3,
        )
        for label, actual, expected in (
            ("ImageOrientationPatient", EXPECTED_AXIAL_IOP, expected_orientation),
            ("PixelSpacing", corrected_pixel_spacing, expected_pixel_spacing),
            ("GridFrameOffsetVector", corrected_offsets, expected_offsets),
        ):
            if not np.allclose(
                actual,
                expected,
                rtol=0.0,
                atol=GEOMETRY_TOLERANCE,
            ):
                raise ValueError(
                    f"PHITS2DICOM {label} does not match bound tally geometry"
                )
        corrected_pixel_spacing = expected_pixel_spacing
        corrected_offsets = expected_offsets
        corrected_position = expected_position
        center_mode = str(expected_placement.get("mode") or "plan_and_tally_affine")

    dataset.PixelData = corrected.tobytes()
    dataset.NumberOfFrames = corrected_frames
    dataset.Rows = corrected_rows
    dataset.Columns = corrected_columns
    dataset.PixelSpacing = [f"{value:.10f}" for value in corrected_pixel_spacing]
    dataset.GridFrameOffsetVector = [
        f"{value:.10f}" for value in corrected_offsets
    ]
    dataset.ImagePositionPatient = [
        f"{value:.10f}" for value in corrected_position
    ]
    dataset.ImageOrientationPatient = [
        f"{value:.10f}" for value in EXPECTED_AXIAL_IOP
    ]
    if hasattr(dataset, "SliceThickness"):
        dataset.SliceThickness = f"{source_row_spacing:.10f}"
    if hasattr(dataset, "SpacingBetweenSlices"):
        dataset.SpacingBetweenSlices = f"{source_row_spacing:.10f}"

    summary = {
        "schema_version": SCHEMA_VERSION,
        "axis_mapping": AXIS_MAPPING,
        "input_path": str(input_path),
        "input_sha256": input_sha256,
        "output_path": str(output_path),
        "center_mode": center_mode,
        "expected_placement": expected_placement,
        "applied_translation_dicom_mm": (
            np.asarray(output_center, dtype=float)
            - np.asarray(source_center, dtype=float)
        ).tolist(),
        "target_override_translation_dicom_mm": (
            expected_placement.get("applied_translation_dicom_mm")
            if expected_placement is not None
            else [0.0, 0.0, 0.0]
        ),
        "source_geometry": _geometry_record(
            array=source,
            pixel_spacing=spacing,
            frame_offsets=source_offsets,
            image_position=source_position,
            image_orientation=source_orientation,
            volume_center=source_center,
            frame_offset_interpretation=offset_interpretation,
        ),
        "output_geometry": _geometry_record(
            array=corrected,
            pixel_spacing=corrected_pixel_spacing,
            frame_offsets=corrected_offsets,
            image_position=corrected_position,
            image_orientation=EXPECTED_AXIAL_IOP,
            volume_center=output_center,
            frame_offset_interpretation="relative_to_image_position_patient",
        ),
        "invariants": {
            "stored_value_multiset_preserved": bool(
                np.array_equal(np.sort(source, axis=None), np.sort(corrected, axis=None))
            ),
            "DoseGridScaling_preserved": True,
            "physical_dose_values_preserved": True,
        },
    }

    if guard is None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        dataset.save_as(str(output_path))
    else:
        stream = io.BytesIO()
        dataset.save_as(stream)
        guard.write_bytes(output_path, stream.getvalue())
    placement_validation = (
        validate_rtdose_placement(
            output_path,
            expected_placement=expected_placement,
        )
        if expected_placement is not None
        else None
    )
    summary["placement_validation"] = placement_validation
    summary["output_sha256"] = file_sha256(output_path)
    if summary_path is not None and guard is None:
        summary_path.parent.mkdir(parents=True, exist_ok=True)
        summary_path.write_text(
            json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    elif summary_path is not None:
        guard.write_json(summary_path, summary)
    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Correct the supported PHITS2DICOM RTDOSE axis layout while "
            "preserving voxel dose values and the physical volume center."
        )
    )
    parser.add_argument("input_rtdose")
    parser.add_argument("output_rtdose")
    parser.add_argument("--summary-json")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(list(argv) if argv is not None else None)
    output = Path(args.output_rtdose)
    summary = (
        Path(args.summary_json)
        if args.summary_json
        else coordinate_summary_path(output)
    )
    fix_coordinates(Path(args.input_rtdose), output, summary_path=summary)
    print(summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
