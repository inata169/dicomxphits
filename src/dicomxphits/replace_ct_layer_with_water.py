"""Create a water-replaced derived CT series for a non-patient phantom."""

from __future__ import annotations

import argparse
from collections import deque
import copy
from dataclasses import dataclass
from datetime import datetime
import hashlib
import io
import inspect
import math
import os
from pathlib import Path
import struct
import sys
from typing import Any, Sequence
import zlib

import numpy as np
import pydicom
from pydicom.dataset import Dataset
from pydicom.misc import is_dicom
from pydicom.uid import UID, generate_uid

from dicomxphits.safe_output import WorkspaceOutputGuard


SCHEMA_VERSION = "dicomxphits_phantom_ct_water_replacement_v1"
PLANE_TOLERANCE_MM = 0.1
ORIENTATION_TOLERANCE = 1.0e-6
SLICE_SPACING_TOLERANCE_MM = 1.0e-3
MIN_REFERENCE_VOXELS = 1_000
WATER_HU_MIN = -200.0
WATER_HU_MAX = 200.0
MAX_REFERENCE_STD_HU = 100.0
AIR_HU_THRESHOLD = -500.0
TARGET_THICKNESS_MIN_MM = 15.0
TARGET_THICKNESS_MAX_MM = 25.0
PNG_WINDOW_CENTER_HU = 0.0
PNG_WINDOW_WIDTH_HU = 500.0
DICOMWRITE_SUPPORTS_ENFORCE_FILE_FORMAT = (
    "enforce_file_format" in inspect.signature(pydicom.dcmwrite).parameters
)


class PhantomCtDerivationError(ValueError):
    """A derived phantom CT cannot be created safely."""


@dataclass(frozen=True)
class PixelFormat:
    bits_allocated: int
    bits_stored: int
    high_bit: int
    pixel_representation: int
    little_endian: bool
    samples: int

    @property
    def bytes_per_sample(self) -> int:
        return self.bits_allocated // 8

    @property
    def low_bit(self) -> int:
        return self.high_bit - self.bits_stored + 1

    @property
    def stored_mask(self) -> int:
        return (1 << self.bits_stored) - 1

    @property
    def allocated_mask(self) -> int:
        return self.stored_mask << self.low_bit

    @property
    def minimum(self) -> int:
        if self.pixel_representation:
            return -(1 << (self.bits_stored - 1))
        return 0

    @property
    def maximum(self) -> int:
        if self.pixel_representation:
            return (1 << (self.bits_stored - 1)) - 1
        return self.stored_mask


@dataclass(frozen=True)
class CtSlice:
    path: Path
    dataset: Dataset
    source_sha256: str
    source_sop_uid: str
    position: np.ndarray
    distance_mm: float
    slope: float
    intercept: float
    pixel_format: PixelFormat
    raw_pixel_data: bytes
    containers: np.ndarray
    stored_values: np.ndarray


@dataclass(frozen=True)
class CtSeries:
    source_root: Path
    series_uid: str
    study_uid: str
    frame_uid: str
    rows: int
    columns: int
    row_spacing_mm: float
    column_spacing_mm: float
    row_direction: np.ndarray
    column_direction: np.ndarray
    normal_direction: np.ndarray
    slice_spacing_mm: float
    slices: tuple[CtSlice, ...]


@dataclass(frozen=True)
class DerivationResult:
    output_dir: Path
    series_instance_uid: str
    dicom_files: tuple[Path, ...]
    json_report: Path
    text_report: Path
    png_report: Path
    warnings: tuple[str, ...]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _finite_vector(value: Any, *, length: int, label: str) -> np.ndarray:
    try:
        result = np.asarray([float(item) for item in value], dtype=np.float64)
    except (TypeError, ValueError) as exc:
        raise PhantomCtDerivationError(f"{label} must contain {length} finite numbers") from exc
    if result.shape != (length,) or not np.all(np.isfinite(result)):
        raise PhantomCtDerivationError(f"{label} must contain {length} finite numbers")
    return result


def _is_link_or_junction(path: Path) -> bool:
    if path.is_symlink():
        return True
    is_junction = getattr(path, "is_junction", None)
    return bool(is_junction is not None and is_junction())


def _is_ct_candidate(path: Path) -> bool:
    name = path.name.upper()
    return (
        path.suffix.lower() == ".dcm"
        or name == "CT"
        or name.startswith(("CT.", "CT_", "CT-"))
        or is_dicom(str(path))
    )


def _raw_containers(raw: bytes, pixel_format: PixelFormat) -> np.ndarray:
    data_length = pixel_format.samples * pixel_format.bytes_per_sample
    if len(raw) not in {data_length, data_length + (data_length % 2)}:
        raise PhantomCtDerivationError(
            "PixelData length does not match Rows, Columns, and BitsAllocated"
        )
    byte_order = "<" if pixel_format.little_endian else ">"
    dtype = np.dtype("u1" if pixel_format.bits_allocated == 8 else f"{byte_order}u2")
    return np.frombuffer(raw[:data_length], dtype=dtype).copy()


def _decode_stored(containers: np.ndarray, pixel_format: PixelFormat) -> np.ndarray:
    values = (
        (containers.astype(np.uint32) >> pixel_format.low_bit)
        & pixel_format.stored_mask
    ).astype(np.int32)
    if pixel_format.pixel_representation:
        sign_bit = 1 << (pixel_format.bits_stored - 1)
        values = np.where(values & sign_bit, values - (1 << pixel_format.bits_stored), values)
    return values


def _validate_pixel_format(dataset: Dataset, *, rows: int, columns: int, path: Path) -> tuple[PixelFormat, bytes]:
    transfer_syntax = UID(str(getattr(dataset.file_meta, "TransferSyntaxUID", "") or ""))
    if not transfer_syntax or transfer_syntax.is_compressed:
        raise PhantomCtDerivationError(
            f"CT PixelData must use a native uncompressed transfer syntax: {path.name}"
        )
    if int(getattr(dataset, "NumberOfFrames", 1) or 1) != 1:
        raise PhantomCtDerivationError(f"multi-frame CT is not supported: {path.name}")
    if int(getattr(dataset, "SamplesPerPixel", 0) or 0) != 1:
        raise PhantomCtDerivationError(f"CT SamplesPerPixel must be 1: {path.name}")
    if str(getattr(dataset, "PhotometricInterpretation", "") or "") not in {
        "MONOCHROME1",
        "MONOCHROME2",
    }:
        raise PhantomCtDerivationError(
            f"CT PhotometricInterpretation must be MONOCHROME1 or MONOCHROME2: {path.name}"
        )
    try:
        bits_allocated = int(dataset.BitsAllocated)
        bits_stored = int(dataset.BitsStored)
        high_bit = int(dataset.HighBit)
        pixel_representation = int(dataset.PixelRepresentation)
    except (AttributeError, TypeError, ValueError) as exc:
        raise PhantomCtDerivationError(
            f"CT pixel representation attributes are missing or invalid: {path.name}"
        ) from exc
    if bits_allocated not in {8, 16}:
        raise PhantomCtDerivationError(
            f"CT BitsAllocated must be 8 or 16: {path.name}"
        )
    if not 1 <= bits_stored <= bits_allocated:
        raise PhantomCtDerivationError(f"CT BitsStored is invalid: {path.name}")
    if not bits_stored - 1 <= high_bit < bits_allocated:
        raise PhantomCtDerivationError(f"CT HighBit is invalid: {path.name}")
    if pixel_representation not in {0, 1}:
        raise PhantomCtDerivationError(f"CT PixelRepresentation is invalid: {path.name}")
    if "PixelData" not in dataset:
        raise PhantomCtDerivationError(f"CT PixelData is missing: {path.name}")
    raw = bytes(dataset.PixelData)
    pixel_format = PixelFormat(
        bits_allocated=bits_allocated,
        bits_stored=bits_stored,
        high_bit=high_bit,
        pixel_representation=pixel_representation,
        little_endian=bool(transfer_syntax.is_little_endian),
        samples=rows * columns,
    )
    _raw_containers(raw, pixel_format)
    return pixel_format, raw


def _read_ct_datasets(root: Path) -> dict[str, list[tuple[Path, Dataset, str]]]:
    series: dict[str, list[tuple[Path, Dataset, str]]] = {}
    for path in sorted(root.iterdir()):
        if not path.is_file():
            continue
        if _is_link_or_junction(path):
            raise PhantomCtDerivationError(f"CT input files must not be links: {path.name}")
        source_sha256 = _sha256(path)
        try:
            dataset = pydicom.dcmread(str(path), force=False)
        except Exception as exc:
            if _is_ct_candidate(path):
                raise PhantomCtDerivationError(
                    f"unreadable CT DICOM candidate: {path.name}"
                ) from exc
            continue
        if _sha256(path) != source_sha256:
            raise PhantomCtDerivationError(
                f"CT input changed while it was being read: {path.name}"
            )
        if str(getattr(dataset, "Modality", "") or "") != "CT":
            continue
        uid = str(getattr(dataset, "SeriesInstanceUID", "") or "")
        if not uid:
            raise PhantomCtDerivationError(
                f"CT DICOM is missing SeriesInstanceUID: {path.name}"
            )
        series.setdefault(uid, []).append((path, dataset, source_sha256))
    return series


def load_ct_series(
    ct_dir: Path, *, series_instance_uid: str | None = None
) -> CtSeries:
    supplied_root = Path(os.path.abspath(os.fspath(ct_dir)))
    if not supplied_root.is_dir() or _is_link_or_junction(supplied_root):
        raise PhantomCtDerivationError(
            f"CT input directory must be an existing non-link directory: {ct_dir}"
        )
    root = supplied_root.resolve()
    available = _read_ct_datasets(root)
    if not available:
        raise PhantomCtDerivationError("no readable CT DICOM series was found")
    if series_instance_uid is None:
        if len(available) != 1:
            raise PhantomCtDerivationError(
                "multiple CT series were found; specify --ct-series-instance-uid"
            )
        selected_uid = next(iter(available))
    else:
        selected_uid = series_instance_uid.strip()
        if not selected_uid or selected_uid not in available:
            raise PhantomCtDerivationError("the requested CT SeriesInstanceUID was not found")

    selected = available[selected_uid]
    rows_values: set[int] = set()
    columns_values: set[int] = set()
    study_uids: set[str] = set()
    frame_uids: set[str] = set()
    spacings: list[np.ndarray] = []
    orientations: list[np.ndarray] = []
    prepared: list[dict[str, Any]] = []
    sop_uids: set[str] = set()
    for path, dataset, source_sha256 in selected:
        try:
            rows = int(dataset.Rows)
            columns = int(dataset.Columns)
        except (AttributeError, TypeError, ValueError) as exc:
            raise PhantomCtDerivationError(
                f"CT Rows and Columns must be positive integers: {path.name}"
            ) from exc
        if rows <= 0 or columns <= 0:
            raise PhantomCtDerivationError(
                f"CT Rows and Columns must be positive integers: {path.name}"
            )
        rows_values.add(rows)
        columns_values.add(columns)
        study_uid = str(getattr(dataset, "StudyInstanceUID", "") or "")
        frame_uid = str(getattr(dataset, "FrameOfReferenceUID", "") or "")
        sop_uid = str(getattr(dataset, "SOPInstanceUID", "") or "")
        sop_class_uid = str(getattr(dataset, "SOPClassUID", "") or "")
        if sop_class_uid != str(pydicom.uid.CTImageStorage):
            raise PhantomCtDerivationError(
                f"only conventional CT Image Storage is supported: {path.name}"
            )
        if not study_uid or not frame_uid or not sop_uid:
            raise PhantomCtDerivationError(
                f"CT Study, FrameOfReference, and SOP Instance UIDs are required: {path.name}"
            )
        if sop_uid in sop_uids:
            raise PhantomCtDerivationError("selected CT contains duplicate SOPInstanceUID values")
        sop_uids.add(sop_uid)
        study_uids.add(study_uid)
        frame_uids.add(frame_uid)
        spacing = _finite_vector(dataset.PixelSpacing, length=2, label="CT PixelSpacing")
        if np.any(spacing <= 0.0):
            raise PhantomCtDerivationError(f"CT PixelSpacing must be positive: {path.name}")
        orientation = _finite_vector(
            dataset.ImageOrientationPatient,
            length=6,
            label="CT ImageOrientationPatient",
        )
        position = _finite_vector(
            dataset.ImagePositionPatient,
            length=3,
            label="CT ImagePositionPatient",
        )
        try:
            slope = float(dataset.RescaleSlope)
            intercept = float(dataset.RescaleIntercept)
        except (AttributeError, TypeError, ValueError) as exc:
            raise PhantomCtDerivationError(
                f"CT RescaleSlope and RescaleIntercept are required: {path.name}"
            ) from exc
        if not math.isfinite(slope) or slope == 0.0 or not math.isfinite(intercept):
            raise PhantomCtDerivationError(
                f"CT rescale values must be finite and slope must be nonzero: {path.name}"
            )
        pixel_format, raw = _validate_pixel_format(
            dataset, rows=rows, columns=columns, path=path
        )
        containers = _raw_containers(raw, pixel_format).reshape(rows, columns)
        prepared.append(
            {
                "path": path,
                "dataset": dataset,
                "source_sha256": source_sha256,
                "source_sop_uid": sop_uid,
                "position": position,
                "slope": slope,
                "intercept": intercept,
                "pixel_format": pixel_format,
                "raw": raw,
                "containers": containers,
                "stored": _decode_stored(containers, pixel_format),
            }
        )
        spacings.append(spacing)
        orientations.append(orientation)

    if len(rows_values) != 1 or len(columns_values) != 1:
        raise PhantomCtDerivationError("selected CT has inconsistent matrix dimensions")
    if len(study_uids) != 1 or len(frame_uids) != 1:
        raise PhantomCtDerivationError("selected CT has inconsistent study or frame UIDs")
    first_spacing = spacings[0]
    if any(not np.allclose(item, first_spacing, atol=1.0e-6, rtol=0.0) for item in spacings[1:]):
        raise PhantomCtDerivationError("selected CT has inconsistent PixelSpacing")
    first_orientation = orientations[0]
    if any(
        not np.allclose(item, first_orientation, atol=ORIENTATION_TOLERANCE, rtol=0.0)
        for item in orientations[1:]
    ):
        raise PhantomCtDerivationError("selected CT has inconsistent ImageOrientationPatient")
    row_direction = first_orientation[:3]
    column_direction = first_orientation[3:]
    if not math.isclose(float(np.linalg.norm(row_direction)), 1.0, abs_tol=ORIENTATION_TOLERANCE, rel_tol=0.0):
        raise PhantomCtDerivationError("CT row direction cosine is not unit length")
    if not math.isclose(float(np.linalg.norm(column_direction)), 1.0, abs_tol=ORIENTATION_TOLERANCE, rel_tol=0.0):
        raise PhantomCtDerivationError("CT column direction cosine is not unit length")
    if not math.isclose(float(np.dot(row_direction, column_direction)), 0.0, abs_tol=ORIENTATION_TOLERANCE, rel_tol=0.0):
        raise PhantomCtDerivationError("CT orientation direction cosines are not orthogonal")
    normal_direction = np.cross(row_direction, column_direction)
    normal_direction /= np.linalg.norm(normal_direction)
    first_position = prepared[0]["position"]
    for item in prepared[1:]:
        position_delta = item["position"] - first_position
        if (
            abs(float(np.dot(position_delta, row_direction)))
            > SLICE_SPACING_TOLERANCE_MM
            or abs(float(np.dot(position_delta, column_direction)))
            > SLICE_SPACING_TOLERANCE_MM
        ):
            raise PhantomCtDerivationError(
                "selected CT has inconsistent in-plane image origins"
            )
    for item in prepared:
        item["distance"] = float(np.dot(item["position"], normal_direction))
    prepared.sort(key=lambda item: item["distance"])
    distances = np.asarray([item["distance"] for item in prepared], dtype=np.float64)
    if len(np.unique(np.round(distances, decimals=6))) != len(distances):
        raise PhantomCtDerivationError("selected CT contains duplicate image planes")
    if len(distances) >= 2:
        adjacent = np.diff(distances)
        slice_spacing = float(np.median(adjacent))
        if slice_spacing <= 0.0 or not np.allclose(
            adjacent, slice_spacing, atol=SLICE_SPACING_TOLERANCE_MM, rtol=0.0
        ):
            raise PhantomCtDerivationError("selected CT has non-uniform slice spacing")
    else:
        try:
            slice_spacing = float(prepared[0]["dataset"].SliceThickness)
        except (AttributeError, TypeError, ValueError) as exc:
            raise PhantomCtDerivationError(
                "a single-slice CT requires positive SliceThickness"
            ) from exc
        if not math.isfinite(slice_spacing) or slice_spacing <= 0.0:
            raise PhantomCtDerivationError(
                "a single-slice CT requires positive SliceThickness"
            )
    slices = tuple(
        CtSlice(
            path=item["path"],
            dataset=item["dataset"],
            source_sha256=item["source_sha256"],
            source_sop_uid=item["source_sop_uid"],
            position=item["position"],
            distance_mm=item["distance"],
            slope=item["slope"],
            intercept=item["intercept"],
            pixel_format=item["pixel_format"],
            raw_pixel_data=item["raw"],
            containers=item["containers"],
            stored_values=item["stored"],
        )
        for item in prepared
    )
    return CtSeries(
        source_root=root,
        series_uid=selected_uid,
        study_uid=next(iter(study_uids)),
        frame_uid=next(iter(frame_uids)),
        rows=next(iter(rows_values)),
        columns=next(iter(columns_values)),
        row_spacing_mm=float(first_spacing[0]),
        column_spacing_mm=float(first_spacing[1]),
        row_direction=row_direction.copy(),
        column_direction=column_direction.copy(),
        normal_direction=normal_direction.copy(),
        slice_spacing_mm=slice_spacing,
        slices=slices,
    )


def _referenced_series_uids(rtstruct: Dataset) -> set[str]:
    result: set[str] = set()
    for frame in getattr(rtstruct, "ReferencedFrameOfReferenceSequence", ()):
        for study in getattr(frame, "RTReferencedStudySequence", ()):
            for series in getattr(study, "RTReferencedSeriesSequence", ()):
                uid = str(getattr(series, "SeriesInstanceUID", "") or "")
                if uid:
                    result.add(uid)
    return result


def _roi_number(rtstruct: Dataset, *, name: str, frame_uid: str) -> int:
    matches = [
        item
        for item in getattr(rtstruct, "StructureSetROISequence", ())
        if str(getattr(item, "ROIName", "") or "") == name
    ]
    if len(matches) != 1:
        raise PhantomCtDerivationError(
            f"RTSTRUCT ROI name must occur exactly once: {name!r}"
        )
    item = matches[0]
    if str(getattr(item, "ReferencedFrameOfReferenceUID", "") or "") != frame_uid:
        raise PhantomCtDerivationError(f"RTSTRUCT ROI frame does not match CT: {name!r}")
    try:
        return int(item.ROINumber)
    except (AttributeError, TypeError, ValueError) as exc:
        raise PhantomCtDerivationError(f"RTSTRUCT ROI number is invalid: {name!r}") from exc


def _roi_contours(rtstruct: Dataset, *, roi_number: int, name: str) -> Sequence[Dataset]:
    matches: list[Dataset] = []
    for item in getattr(rtstruct, "ROIContourSequence", ()):
        try:
            referenced_number = int(item.ReferencedROINumber)
        except (AttributeError, TypeError, ValueError):
            continue
        if referenced_number == roi_number:
            matches.append(item)
    if len(matches) != 1:
        raise PhantomCtDerivationError(
            f"RTSTRUCT ROIContour must occur exactly once for ROI: {name!r}"
        )
    contours = getattr(matches[0], "ContourSequence", ())
    if not contours:
        raise PhantomCtDerivationError(f"RTSTRUCT ROI has no contours: {name!r}")
    return contours


def _polygon_mask(rows: int, columns: int, row_values: np.ndarray, column_values: np.ndarray) -> np.ndarray:
    row_min = max(0, int(math.floor(float(np.min(row_values)))) - 1)
    row_max = min(rows - 1, int(math.ceil(float(np.max(row_values)))) + 1)
    column_min = max(0, int(math.floor(float(np.min(column_values)))) - 1)
    column_max = min(columns - 1, int(math.ceil(float(np.max(column_values)))) + 1)
    result = np.zeros((rows, columns), dtype=bool)
    if row_min > row_max or column_min > column_max:
        return result
    yy, xx = np.mgrid[row_min : row_max + 1, column_min : column_max + 1]
    inside = np.zeros(xx.shape, dtype=bool)
    boundary = np.zeros(xx.shape, dtype=bool)
    count = len(row_values)
    for index in range(count):
        next_index = (index + 1) % count
        x1 = float(column_values[index])
        y1 = float(row_values[index])
        x2 = float(column_values[next_index])
        y2 = float(row_values[next_index])
        dx = x2 - x1
        dy = y2 - y1
        cross = (xx - x1) * dy - (yy - y1) * dx
        scale = max(1.0, abs(dx), abs(dy))
        on_line = np.abs(cross) <= 1.0e-9 * scale
        within = (
            (xx >= min(x1, x2) - 1.0e-9)
            & (xx <= max(x1, x2) + 1.0e-9)
            & (yy >= min(y1, y2) - 1.0e-9)
            & (yy <= max(y1, y2) + 1.0e-9)
        )
        boundary |= on_line & within
        crosses = (y1 > yy) != (y2 > yy)
        x_intersection = (dx * (yy - y1) / ((y2 - y1) + 1.0e-300)) + x1
        inside ^= crosses & (xx < x_intersection)
    result[row_min : row_max + 1, column_min : column_max + 1] = inside | boundary
    return result


def _rasterize_roi(
    rtstruct: Dataset,
    *,
    series: CtSeries,
    roi_number: int,
    roi_name: str,
) -> np.ndarray:
    masks = np.zeros((len(series.slices), series.rows, series.columns), dtype=bool)
    sop_to_index = {item.source_sop_uid: index for index, item in enumerate(series.slices)}
    for contour in _roi_contours(rtstruct, roi_number=roi_number, name=roi_name):
        if str(getattr(contour, "ContourGeometricType", "") or "") != "CLOSED_PLANAR":
            raise PhantomCtDerivationError(
                f"RTSTRUCT contour must be CLOSED_PLANAR for ROI: {roi_name!r}"
            )
        references = getattr(contour, "ContourImageSequence", ())
        if len(references) != 1:
            raise PhantomCtDerivationError(
                f"each RTSTRUCT contour must reference exactly one CT image: {roi_name!r}"
            )
        referenced_class_uid = str(
            getattr(references[0], "ReferencedSOPClassUID", "") or ""
        )
        if referenced_class_uid != str(pydicom.uid.CTImageStorage):
            raise PhantomCtDerivationError(
                f"RTSTRUCT contour must reference conventional CT Image Storage: {roi_name!r}"
            )
        sop_uid = str(getattr(references[0], "ReferencedSOPInstanceUID", "") or "")
        if sop_uid not in sop_to_index:
            raise PhantomCtDerivationError(
                f"RTSTRUCT contour references a CT image outside the selected series: {roi_name!r}"
            )
        try:
            points = np.asarray(
                [float(value) for value in contour.ContourData], dtype=np.float64
            ).reshape(-1, 3)
            declared_points = int(contour.NumberOfContourPoints)
        except (AttributeError, TypeError, ValueError) as exc:
            raise PhantomCtDerivationError(
                f"RTSTRUCT contour data is invalid: {roi_name!r}"
            ) from exc
        if declared_points != len(points) or len(points) < 3 or not np.all(np.isfinite(points)):
            raise PhantomCtDerivationError(
                f"RTSTRUCT contour must contain at least three finite declared points: {roi_name!r}"
            )
        slice_index = sop_to_index[sop_uid]
        ct_slice = series.slices[slice_index]
        relative = points - ct_slice.position
        residual = np.abs(relative @ series.normal_direction)
        if float(np.max(residual)) > PLANE_TOLERANCE_MM:
            raise PhantomCtDerivationError(
                f"RTSTRUCT contour is more than {PLANE_TOLERANCE_MM:g} mm off its referenced CT plane: {roi_name!r}"
            )
        column_values = (relative @ series.row_direction) / series.column_spacing_mm
        row_values = (relative @ series.column_direction) / series.row_spacing_mm
        polygon = _polygon_mask(
            series.rows, series.columns, row_values, column_values
        )
        if not np.any(polygon):
            raise PhantomCtDerivationError(
                f"RTSTRUCT contour selects no CT pixel centres: {roi_name!r}"
            )
        masks[slice_index] ^= polygon
    if not np.any(masks):
        raise PhantomCtDerivationError(f"RTSTRUCT ROI selects no CT voxels: {roi_name!r}")
    return masks


def load_rtstruct_masks(
    rtstruct_path: Path,
    *,
    series: CtSeries,
    target_roi: str,
    reference_roi: str,
) -> tuple[np.ndarray, np.ndarray]:
    supplied_path = Path(os.path.abspath(os.fspath(rtstruct_path)))
    if not supplied_path.is_file() or _is_link_or_junction(supplied_path):
        raise PhantomCtDerivationError(
            f"RTSTRUCT must be an existing non-link file: {rtstruct_path}"
        )
    path = supplied_path.resolve()
    try:
        rtstruct = pydicom.dcmread(str(path), force=False, stop_before_pixels=True)
    except Exception as exc:
        raise PhantomCtDerivationError(f"RTSTRUCT is not readable: {rtstruct_path}") from exc
    if str(getattr(rtstruct, "Modality", "") or "") != "RTSTRUCT":
        raise PhantomCtDerivationError("the supplied structure file is not an RTSTRUCT")
    frame_uids = {
        str(getattr(item, "FrameOfReferenceUID", "") or "")
        for item in getattr(rtstruct, "ReferencedFrameOfReferenceSequence", ())
    }
    if series.frame_uid not in frame_uids:
        raise PhantomCtDerivationError("RTSTRUCT does not reference the selected CT frame")
    if series.series_uid not in _referenced_series_uids(rtstruct):
        raise PhantomCtDerivationError("RTSTRUCT does not reference the selected CT series")
    if not target_roi or not reference_roi or target_roi == reference_roi:
        raise PhantomCtDerivationError("target and reference ROI names must be nonempty and distinct")
    target_number = _roi_number(rtstruct, name=target_roi, frame_uid=series.frame_uid)
    reference_number = _roi_number(rtstruct, name=reference_roi, frame_uid=series.frame_uid)
    if target_number == reference_number:
        raise PhantomCtDerivationError("target and reference ROIs must have distinct ROI numbers")
    target_mask = _rasterize_roi(
        rtstruct,
        series=series,
        roi_number=target_number,
        roi_name=target_roi,
    )
    reference_mask = _rasterize_roi(
        rtstruct,
        series=series,
        roi_number=reference_number,
        roi_name=reference_roi,
    )
    if np.any(target_mask & reference_mask):
        raise PhantomCtDerivationError("target and reference ROI masks overlap")
    occupied_target_slices = np.flatnonzero(np.any(target_mask, axis=(1, 2)))
    expected_target_slices = np.arange(
        int(occupied_target_slices[0]), int(occupied_target_slices[-1]) + 1
    )
    if not np.array_equal(occupied_target_slices, expected_target_slices):
        raise PhantomCtDerivationError(
            "target ROI has unrepresented CT slices inside its occupied layer; explicit contours are required on every replaced slice"
        )
    return target_mask, reference_mask


def _slice_hu(ct_slice: CtSlice) -> np.ndarray:
    return ct_slice.stored_values.astype(np.float64) * ct_slice.slope + ct_slice.intercept


def _stats(values: np.ndarray) -> dict[str, float | int]:
    if values.size == 0:
        raise PhantomCtDerivationError("cannot calculate statistics for an empty ROI")
    return {
        "count": int(values.size),
        "minimum_hu": float(np.min(values)),
        "p05_hu": float(np.percentile(values, 5.0)),
        "median_hu": float(np.median(values)),
        "mean_hu": float(np.mean(values)),
        "standard_deviation_hu": float(np.std(values)),
        "p95_hu": float(np.percentile(values, 95.0)),
        "maximum_hu": float(np.max(values)),
    }


def _boundary_connected(mask: np.ndarray) -> np.ndarray:
    rows, columns = mask.shape
    connected = np.zeros_like(mask, dtype=bool)
    queue: deque[tuple[int, int]] = deque()
    for row in range(rows):
        for column in (0, columns - 1):
            if mask[row, column] and not connected[row, column]:
                connected[row, column] = True
                queue.append((row, column))
    for column in range(columns):
        for row in (0, rows - 1):
            if mask[row, column] and not connected[row, column]:
                connected[row, column] = True
                queue.append((row, column))
    while queue:
        row, column = queue.popleft()
        for next_row, next_column in (
            (row - 1, column),
            (row + 1, column),
            (row, column - 1),
            (row, column + 1),
        ):
            if (
                0 <= next_row < rows
                and 0 <= next_column < columns
                and mask[next_row, next_column]
                and not connected[next_row, next_column]
            ):
                connected[next_row, next_column] = True
                queue.append((next_row, next_column))
    return connected


def _replacement_analysis(
    series: CtSeries,
    target_mask: np.ndarray,
    reference_mask: np.ndarray,
) -> tuple[dict[str, Any], tuple[str, ...], tuple[float | None, ...]]:
    reference_parts: list[np.ndarray] = []
    target_parts: list[np.ndarray] = []
    per_slice_reference: list[float | None] = []
    outside_air_count = 0
    boundary_contact = False
    for index, ct_slice in enumerate(series.slices):
        hu = _slice_hu(ct_slice)
        reference_values = hu[reference_mask[index]]
        target_values = hu[target_mask[index]]
        if reference_values.size:
            reference_parts.append(reference_values)
            per_slice_reference.append(float(np.median(reference_values)))
        else:
            per_slice_reference.append(None)
        if target_values.size:
            target_parts.append(target_values)
            slice_target = target_mask[index]
            boundary_contact = boundary_contact or bool(
                np.any(slice_target[0, :])
                or np.any(slice_target[-1, :])
                or np.any(slice_target[:, 0])
                or np.any(slice_target[:, -1])
            )
            boundary_air = _boundary_connected(hu < AIR_HU_THRESHOLD)
            outside_air_count += int(np.count_nonzero(slice_target & boundary_air))
    if not reference_parts or not target_parts:
        raise PhantomCtDerivationError("target and reference masks must both contain voxels")
    reference_values = np.concatenate(reference_parts)
    target_values = np.concatenate(target_parts)
    reference_stats = _stats(reference_values)
    target_before_stats = _stats(target_values)
    global_median = float(reference_stats["median_hu"])
    replacement_hu: list[float | None] = []
    fallback_indices: list[int] = []
    for index, target in enumerate(target_mask):
        if not np.any(target):
            replacement_hu.append(None)
        elif per_slice_reference[index] is None:
            replacement_hu.append(global_median)
            fallback_indices.append(index)
        else:
            replacement_hu.append(per_slice_reference[index])
    occupied = np.flatnonzero(np.any(target_mask, axis=(1, 2)))
    target_thickness_mm = (
        float(series.slices[int(occupied[-1])].distance_mm - series.slices[int(occupied[0])].distance_mm)
        + series.slice_spacing_mm
    )
    voxel_volume_mm3 = (
        series.row_spacing_mm * series.column_spacing_mm * series.slice_spacing_mm
    )
    target_count = int(np.count_nonzero(target_mask))
    reference_count = int(np.count_nonzero(reference_mask))
    warnings: list[str] = []
    if reference_count < MIN_REFERENCE_VOXELS:
        warnings.append(
            f"reference ROI contains {reference_count} voxels; expected at least {MIN_REFERENCE_VOXELS}"
        )
    if not WATER_HU_MIN <= global_median <= WATER_HU_MAX:
        warnings.append(
            f"reference median {global_median:.3f} HU is outside {WATER_HU_MIN:g} to {WATER_HU_MAX:g} HU"
        )
    if float(reference_stats["standard_deviation_hu"]) > MAX_REFERENCE_STD_HU:
        warnings.append(
            "reference standard deviation "
            f"{float(reference_stats['standard_deviation_hu']):.3f} HU exceeds {MAX_REFERENCE_STD_HU:g} HU"
        )
    if (
        float(reference_stats["p05_hu"]) < WATER_HU_MIN
        or float(reference_stats["p95_hu"]) > WATER_HU_MAX
    ):
        warnings.append(
            "reference 5th/95th percentile range "
            f"{float(reference_stats['p05_hu']):.3f} to {float(reference_stats['p95_hu']):.3f} HU "
            f"extends outside {WATER_HU_MIN:g} to {WATER_HU_MAX:g} HU"
        )
    if boundary_contact:
        warnings.append("target ROI touches the CT image matrix boundary")
    if outside_air_count:
        warnings.append(
            f"target ROI overlaps {outside_air_count} boundary-connected pixels below {AIR_HU_THRESHOLD:g} HU"
        )
    if not TARGET_THICKNESS_MIN_MM <= target_thickness_mm <= TARGET_THICKNESS_MAX_MM:
        warnings.append(
            f"target occupied thickness {target_thickness_mm:.3f} mm is outside "
            f"{TARGET_THICKNESS_MIN_MM:g} to {TARGET_THICKNESS_MAX_MM:g} mm"
        )
    analysis = {
        "reference_statistics": reference_stats,
        "target_before_statistics": target_before_stats,
        "global_reference_median_hu": global_median,
        "target_voxel_count": target_count,
        "target_volume_cm3": target_count * voxel_volume_mm3 / 1000.0,
        "reference_voxel_count": reference_count,
        "reference_volume_cm3": reference_count * voxel_volume_mm3 / 1000.0,
        "voxel_volume_mm3": voxel_volume_mm3,
        "target_thickness_mm": target_thickness_mm,
        "target_boundary_contact": boundary_contact,
        "target_boundary_connected_air_voxel_count": outside_air_count,
        "fallback_slice_indices": fallback_indices,
    }
    return analysis, tuple(warnings), tuple(replacement_hu)


def _encode_replacement(
    ct_slice: CtSlice, mask: np.ndarray, replacement_hu: float
) -> tuple[bytes, np.ndarray, int]:
    desired = (replacement_hu - ct_slice.intercept) / ct_slice.slope
    if not math.isfinite(desired):
        raise PhantomCtDerivationError(
            f"inverse rescale is not finite for source SOP {ct_slice.source_sop_uid}"
        )
    stored = int(np.rint(desired))
    pixel_format = ct_slice.pixel_format
    if not pixel_format.minimum <= stored <= pixel_format.maximum:
        raise PhantomCtDerivationError(
            "inverse-rescaled water value is outside the declared stored-pixel range "
            f"for source SOP {ct_slice.source_sop_uid}"
        )
    containers = ct_slice.containers.copy()
    code = stored & pixel_format.stored_mask
    replacement_bits = code << pixel_format.low_bit
    allocated_full_mask = (1 << pixel_format.bits_allocated) - 1
    keep_mask = allocated_full_mask ^ pixel_format.allocated_mask
    updated = (
        (containers[mask].astype(np.uint32) & keep_mask) | replacement_bits
    ).astype(containers.dtype)
    containers[mask] = updated
    data_length = pixel_format.samples * pixel_format.bytes_per_sample
    raw = containers.reshape(-1).tobytes(order="C") + ct_slice.raw_pixel_data[data_length:]
    decoded = _decode_stored(containers, pixel_format).reshape(mask.shape)
    return raw, decoded, stored


def _dicom_bytes(dataset: Dataset) -> bytes:
    buffer = io.BytesIO()
    if DICOMWRITE_SUPPORTS_ENFORCE_FILE_FORMAT:
        pydicom.dcmwrite(buffer, dataset, enforce_file_format=True)
    else:  # pydicom 2.x compatibility
        pydicom.dcmwrite(buffer, dataset, write_like_original=False)
    return buffer.getvalue()


def _now_dicom() -> tuple[str, str, str]:
    now = datetime.now().astimezone()
    date = now.strftime("%Y%m%d")
    time = now.strftime("%H%M%S.%f").rstrip("0").rstrip(".")
    offset = now.strftime("%z")
    return date, time, offset


def _derived_dataset(
    ct_slice: CtSlice,
    *,
    pixel_data: bytes,
    new_series_uid: str,
    new_sop_uid: str,
    date: str,
    time: str,
    offset: str,
) -> Dataset:
    dataset = copy.deepcopy(ct_slice.dataset)
    source_class_uid = str(dataset.SOPClassUID)
    source_sop_uid = ct_slice.source_sop_uid
    dataset.PixelData = pixel_data
    dataset.SeriesInstanceUID = new_series_uid
    dataset.SOPInstanceUID = new_sop_uid
    dataset.file_meta.MediaStorageSOPClassUID = source_class_uid
    dataset.file_meta.MediaStorageSOPInstanceUID = new_sop_uid
    dataset.ImageType = ["DERIVED", "SECONDARY", "WATER_REPLACED"]
    source_description = str(getattr(dataset, "SeriesDescription", "") or "CT")
    suffix = " [WATER DERIVED]"
    dataset.SeriesDescription = source_description[: 64 - len(suffix)] + suffix
    dataset.DerivationDescription = (
        "Non-patient phantom target ROI replaced with median HU from an explicit clean-water reference ROI."
    )
    source_item = Dataset()
    source_item.ReferencedSOPClassUID = source_class_uid
    source_item.ReferencedSOPInstanceUID = source_sop_uid
    dataset.SourceImageSequence = [source_item]
    dataset.InstanceCreationDate = date
    dataset.InstanceCreationTime = time
    dataset.SeriesDate = date
    dataset.SeriesTime = time
    dataset.ContentDate = date
    dataset.ContentTime = time
    if offset:
        dataset.TimezoneOffsetFromUTC = offset
    return dataset


def _mask_boundary(mask: np.ndarray) -> np.ndarray:
    interior = mask.copy()
    interior[1:, :] &= mask[:-1, :]
    interior[:-1, :] &= mask[1:, :]
    interior[:, 1:] &= mask[:, :-1]
    interior[:, :-1] &= mask[:, 1:]
    return mask & ~interior


def _window_rgb(values: np.ndarray) -> np.ndarray:
    low = PNG_WINDOW_CENTER_HU - PNG_WINDOW_WIDTH_HU / 2.0
    scaled = np.clip((values - low) / PNG_WINDOW_WIDTH_HU, 0.0, 1.0)
    gray = np.rint(scaled * 255.0).astype(np.uint8)
    return np.repeat(gray[:, :, None], 3, axis=2)


def _overlay_boundaries(image: np.ndarray, target: np.ndarray, reference: np.ndarray) -> np.ndarray:
    result = image.copy()
    result[_mask_boundary(target)] = np.array([255, 32, 32], dtype=np.uint8)
    result[_mask_boundary(reference)] = np.array([32, 255, 32], dtype=np.uint8)
    return result


def _png_chunk(chunk_type: bytes, data: bytes) -> bytes:
    payload = chunk_type + data
    return struct.pack(">I", len(data)) + payload + struct.pack(">I", zlib.crc32(payload) & 0xFFFFFFFF)


def _encode_png_rgb(image: np.ndarray) -> bytes:
    if image.ndim != 3 or image.shape[2] != 3 or image.dtype != np.uint8:
        raise AssertionError("PNG input must be an RGB uint8 array")
    height, width, _channels = image.shape
    scanlines = b"".join(b"\x00" + image[row].tobytes() for row in range(height))
    return (
        b"\x89PNG\r\n\x1a\n"
        + _png_chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + _png_chunk(b"IDAT", zlib.compress(scanlines, level=9))
        + _png_chunk(b"IEND", b"")
    )


def _qc_png(
    before_hu: np.ndarray,
    after_hu: np.ndarray,
    target_mask: np.ndarray,
    reference_mask: np.ndarray,
) -> bytes:
    before = _overlay_boundaries(_window_rgb(before_hu), target_mask, reference_mask)
    after = _overlay_boundaries(_window_rgb(after_hu), target_mask, reference_mask)
    difference = np.abs(after_hu - before_hu)
    maximum = max(1.0, float(np.max(difference)))
    intensity = np.rint(np.clip(difference / maximum, 0.0, 1.0) * 255.0).astype(np.uint8)
    diff_rgb = np.zeros((*intensity.shape, 3), dtype=np.uint8)
    diff_rgb[:, :, 0] = intensity
    masks = np.zeros((*target_mask.shape, 3), dtype=np.uint8)
    masks[target_mask] = np.array([255, 32, 32], dtype=np.uint8)
    masks[reference_mask] = np.array([32, 255, 32], dtype=np.uint8)
    separator_v = np.full((before.shape[0], 2, 3), 255, dtype=np.uint8)
    top = np.concatenate((before, separator_v, after), axis=1)
    bottom = np.concatenate((diff_rgb, separator_v, masks), axis=1)
    separator_h = np.full((2, top.shape[1], 3), 255, dtype=np.uint8)
    return _encode_png_rgb(np.concatenate((top, separator_h, bottom), axis=0))


def _report_text(report: dict[str, Any]) -> str:
    lines = [
        "dicomxphits non-patient phantom CT water replacement",
        f"Status: {report['status']}",
        f"Source CT: {report['input']['ct_directory']}",
        f"RTSTRUCT: {report['input']['rtstruct']}",
        f"Output: {report['output']['directory']}",
        f"Target ROI: {report['roi']['target_name']}",
        f"Reference ROI: {report['roi']['reference_name']}",
        f"Target voxels: {report['qc']['target_voxel_count']}",
        f"Target volume [cm3]: {report['qc']['target_volume_cm3']:.6f}",
        f"Target thickness [mm]: {report['qc']['target_thickness_mm']:.6f}",
        f"Reference voxels: {report['qc']['reference_voxel_count']}",
        f"Global reference median [HU]: {report['qc']['global_reference_median_hu']:.6f}",
        f"Fallback slice indices: {report['qc']['fallback_slice_indices']}",
        f"Warnings: {len(report['warnings'])}",
    ]
    lines.extend(f"  - {warning}" for warning in report["warnings"])
    lines.extend(
        [
            "",
            "The original RTSTRUCT still references the source CT SOP instances.",
            "Import the derived CT as a new series and independently verify TPS reassociation, geometry, structures, and plans.",
            "This output is for education and research with a non-patient phantom only.",
            "",
        ]
    )
    return "\n".join(lines)


def _paths_overlap(first: Path, second: Path) -> bool:
    try:
        os.path.commonpath((first, second))
    except ValueError:
        return False
    first_norm = os.path.normcase(os.fspath(first))
    second_norm = os.path.normcase(os.fspath(second))
    common = os.path.normcase(os.path.commonpath((first, second)))
    return common in {first_norm, second_norm}


def derive_phantom_ct(
    *,
    ct_dir: Path,
    rtstruct: Path,
    target_roi: str,
    reference_roi: str,
    output_dir: Path,
    confirmed_non_patient_phantom: bool,
    accept_qc_warnings: bool = False,
    series_instance_uid: str | None = None,
) -> DerivationResult:
    if not confirmed_non_patient_phantom:
        raise PhantomCtDerivationError(
            "explicit --confirm-non-patient-phantom acknowledgement is required"
        )
    output = Path(os.path.abspath(os.fspath(output_dir)))
    source = Path(os.path.abspath(os.fspath(ct_dir)))
    if os.path.lexists(output):
        raise PhantomCtDerivationError(f"output directory already exists: {output_dir}")
    if _paths_overlap(source, output):
        raise PhantomCtDerivationError(
            "output directory must not equal, contain, or be inside the CT input directory"
        )
    series = load_ct_series(ct_dir, series_instance_uid=series_instance_uid)
    rtstruct_resolved = Path(rtstruct).resolve()
    rtstruct_sha256 = _sha256(rtstruct_resolved)
    target_mask, reference_mask = load_rtstruct_masks(
        rtstruct,
        series=series,
        target_roi=target_roi,
        reference_roi=reference_roi,
    )
    if _sha256(rtstruct_resolved) != rtstruct_sha256:
        raise PhantomCtDerivationError("source RTSTRUCT changed while it was being read")
    analysis, warnings, replacement_hu = _replacement_analysis(
        series, target_mask, reference_mask
    )
    if warnings and not accept_qc_warnings:
        detail = "\n".join(f"- {warning}" for warning in warnings)
        raise PhantomCtDerivationError(
            "QC warnings require explicit --accept-qc-warnings acknowledgement:\n" + detail
        )

    new_series_uid = generate_uid()
    new_sop_uids = [generate_uid() for _item in series.slices]
    date, time, offset = _now_dicom()
    derived_datasets: list[Dataset] = []
    derived_stored: list[np.ndarray] = []
    per_slice: list[dict[str, Any]] = []
    for index, ct_slice in enumerate(series.slices):
        if replacement_hu[index] is None:
            pixel_data = ct_slice.raw_pixel_data
            stored_values = ct_slice.stored_values.copy()
            replacement_stored: int | None = None
        else:
            pixel_data, stored_values, replacement_stored = _encode_replacement(
                ct_slice, target_mask[index], float(replacement_hu[index])
            )
        dataset = _derived_dataset(
            ct_slice,
            pixel_data=pixel_data,
            new_series_uid=new_series_uid,
            new_sop_uid=new_sop_uids[index],
            date=date,
            time=time,
            offset=offset,
        )
        derived_datasets.append(dataset)
        derived_stored.append(stored_values)
        per_slice.append(
            {
                "index": index,
                "source_sop_instance_uid": ct_slice.source_sop_uid,
                "derived_sop_instance_uid": new_sop_uids[index],
                "distance_along_stack_mm": ct_slice.distance_mm,
                "target_voxel_count": int(np.count_nonzero(target_mask[index])),
                "reference_voxel_count": int(np.count_nonzero(reference_mask[index])),
                "replacement_hu": replacement_hu[index],
                "replacement_stored_value": replacement_stored,
                "used_global_fallback": bool(
                    index in analysis["fallback_slice_indices"]
                ),
            }
        )

    representative_index = int(
        np.argmax(np.count_nonzero(target_mask, axis=(1, 2)))
    )
    before_hu = _slice_hu(series.slices[representative_index])
    after_hu = (
        derived_stored[representative_index].astype(np.float64)
        * series.slices[representative_index].slope
        + series.slices[representative_index].intercept
    )
    target_after_values = np.concatenate(
        [
            derived_stored[index][target_mask[index]].astype(np.float64)
            * ct_slice.slope
            + ct_slice.intercept
            for index, ct_slice in enumerate(series.slices)
            if np.any(target_mask[index])
        ]
    )
    analysis["target_after_statistics"] = _stats(target_after_values)
    source_hashes = {item.path.name: item.source_sha256 for item in series.slices}
    output_files = tuple(output / f"CT.{index + 1:04d}.dcm" for index in range(len(series.slices)))
    json_path = output / "qc-report.json"
    text_path = output / "qc-report.txt"
    png_path = output / "qc-comparison.png"
    marker = output / "INCOMPLETE.txt"

    with WorkspaceOutputGuard(output, create_root=True) as guard:
        guard.write_text(
            marker,
            "This derived CT output is incomplete and must not be used.\n",
            overwrite=False,
        )
        for path, dataset in zip(output_files, derived_datasets, strict=True):
            guard.write_bytes(path, _dicom_bytes(dataset), overwrite=False)
        for index, (path, source_slice) in enumerate(
            zip(output_files, series.slices, strict=True)
        ):
            reread = pydicom.dcmread(str(path), force=False)
            if str(reread.SeriesInstanceUID) != new_series_uid:
                raise PhantomCtDerivationError("derived CT SeriesInstanceUID verification failed")
            if str(reread.SOPInstanceUID) != new_sop_uids[index]:
                raise PhantomCtDerivationError("derived CT SOPInstanceUID verification failed")
            if str(reread.file_meta.MediaStorageSOPInstanceUID) != new_sop_uids[index]:
                raise PhantomCtDerivationError("derived CT file-meta SOP UID verification failed")
            if str(reread.StudyInstanceUID) != series.study_uid or str(reread.FrameOfReferenceUID) != series.frame_uid:
                raise PhantomCtDerivationError("derived CT study or frame UID verification failed")
            reread_raw = bytes(reread.PixelData)
            reread_containers = _raw_containers(reread_raw, source_slice.pixel_format).reshape(
                series.rows, series.columns
            )
            outside = ~target_mask[index]
            source_bytes = source_slice.containers.view(np.uint8).reshape(
                series.rows, series.columns, source_slice.pixel_format.bytes_per_sample
            )
            derived_bytes = reread_containers.view(np.uint8).reshape(
                series.rows, series.columns, source_slice.pixel_format.bytes_per_sample
            )
            if not np.array_equal(source_bytes[outside], derived_bytes[outside]):
                raise PhantomCtDerivationError("outside-target stored pixel bytes changed")
            reread_stored = _decode_stored(
                reread_containers, source_slice.pixel_format
            ).reshape(series.rows, series.columns)
            if not np.array_equal(reread_stored, derived_stored[index]):
                raise PhantomCtDerivationError("derived CT stored-pixel reread verification failed")
        refreshed_hashes = {item.path.name: _sha256(item.path) for item in series.slices}
        if refreshed_hashes != source_hashes:
            raise PhantomCtDerivationError("source CT files changed during derivation")
        if _sha256(rtstruct_resolved) != rtstruct_sha256:
            raise PhantomCtDerivationError("source RTSTRUCT changed during derivation")
        report: dict[str, Any] = {
            "schema_version": SCHEMA_VERSION,
            "status": "complete",
            "purpose": "education and research with a non-patient phantom only",
            "input": {
                "ct_directory": str(series.source_root),
                "rtstruct": str(rtstruct_resolved),
                "rtstruct_sha256": rtstruct_sha256,
                "series_instance_uid": series.series_uid,
                "study_instance_uid": series.study_uid,
                "frame_of_reference_uid": series.frame_uid,
                "source_sha256": source_hashes,
            },
            "output": {
                "directory": str(output),
                "series_instance_uid": new_series_uid,
                "dicom_files": [path.name for path in output_files],
                "source_integrity_verified": True,
                "rtstruct_integrity_verified": True,
                "outside_target_pixel_bytes_verified": True,
                "post_write_reread_verified": True,
            },
            "geometry": {
                "slice_count": len(series.slices),
                "rows": series.rows,
                "columns": series.columns,
                "pixel_spacing_mm": [
                    series.row_spacing_mm,
                    series.column_spacing_mm,
                ],
                "slice_spacing_mm": series.slice_spacing_mm,
                "row_direction": series.row_direction.tolist(),
                "column_direction": series.column_direction.tolist(),
                "normal_direction": series.normal_direction.tolist(),
            },
            "roi": {
                "target_name": target_roi,
                "reference_name": reference_roi,
            },
            "qc": analysis,
            "per_slice": per_slice,
            "warnings": list(warnings),
            "warning_acknowledged": bool(accept_qc_warnings),
            "representative_slice_index": representative_index,
            "png_window_center_hu": PNG_WINDOW_CENTER_HU,
            "png_window_width_hu": PNG_WINDOW_WIDTH_HU,
            "reference_notice": (
                "The original RTSTRUCT still references the source CT. Import the derived CT as a new series and independently verify TPS reassociation."
            ),
        }
        guard.write_json(json_path, report, overwrite=False)
        guard.write_text(text_path, _report_text(report), overwrite=False)
        guard.write_bytes(
            png_path,
            _qc_png(
                before_hu,
                after_hu,
                target_mask[representative_index],
                reference_mask[representative_index],
            ),
            overwrite=False,
        )
        guard.unlink(marker)
    return DerivationResult(
        output_dir=output,
        series_instance_uid=new_series_uid,
        dicom_files=output_files,
        json_report=json_path,
        text_report=text_path,
        png_report=png_path,
        warnings=warnings,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Create a water-replaced derived CT series for an explicitly confirmed non-patient phantom."
        )
    )
    parser.add_argument("--ct-dir", type=Path, required=True)
    parser.add_argument("--rtstruct", type=Path, required=True)
    parser.add_argument("--target-roi", required=True)
    parser.add_argument("--reference-roi", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--ct-series-instance-uid")
    parser.add_argument("--confirm-non-patient-phantom", action="store_true")
    parser.add_argument("--accept-qc-warnings", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = derive_phantom_ct(
            ct_dir=args.ct_dir,
            rtstruct=args.rtstruct,
            target_roi=args.target_roi,
            reference_roi=args.reference_roi,
            output_dir=args.output_dir,
            confirmed_non_patient_phantom=args.confirm_non_patient_phantom,
            accept_qc_warnings=args.accept_qc_warnings,
            series_instance_uid=args.ct_series_instance_uid,
        )
    except (OSError, PhantomCtDerivationError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(f"Derived CT series: {result.output_dir}")
    print(f"SeriesInstanceUID: {result.series_instance_uid}")
    print(f"QC JSON: {result.json_report}")
    print(f"QC text: {result.text_report}")
    print(f"QC PNG: {result.png_report}")
    if result.warnings:
        print("QC warnings were explicitly acknowledged:")
        for warning in result.warnings:
            print(f"- {warning}")
    print("The original RTSTRUCT still references the source CT; independently reassociate and verify downstream TPS objects.")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
