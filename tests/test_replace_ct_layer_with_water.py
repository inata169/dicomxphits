from __future__ import annotations

import hashlib
import inspect
import json
import os
from pathlib import Path
import subprocess
import sys

import numpy as np
import pydicom
import pytest
from pydicom.dataset import Dataset, FileDataset, FileMetaDataset

from dicomxphits.replace_ct_layer_with_water import (
    PhantomCtDerivationError,
    _boundary_connected,
    _replacement_analysis,
    derive_phantom_ct,
    load_ct_series,
    load_rtstruct_masks,
)


def _uid() -> str:
    return pydicom.uid.generate_uid(prefix=None)


def _file_dataset(path: Path, sop_class_uid: str, sop_instance_uid: str) -> FileDataset:
    file_meta = FileMetaDataset()
    file_meta.MediaStorageSOPClassUID = sop_class_uid
    file_meta.MediaStorageSOPInstanceUID = sop_instance_uid
    file_meta.TransferSyntaxUID = pydicom.uid.ExplicitVRLittleEndian
    dataset = FileDataset(str(path), {}, file_meta=file_meta, preamble=b"\0" * 128)
    dataset.SOPClassUID = sop_class_uid
    dataset.SOPInstanceUID = sop_instance_uid
    return dataset


def _save_dataset(dataset: FileDataset, path: Path) -> None:
    if "enforce_file_format" in inspect.signature(dataset.save_as).parameters:
        dataset.save_as(path, enforce_file_format=True)
    else:
        dataset.save_as(path, write_like_original=False)


def _encode_stored(
    values: np.ndarray,
    *,
    bits_allocated: int,
    bits_stored: int,
    high_bit: int,
    pixel_representation: int,
    unused_pattern: int = 0,
) -> bytes:
    low_bit = high_bit - bits_stored + 1
    stored_mask = (1 << bits_stored) - 1
    allocated_mask = stored_mask << low_bit
    allocated_full = (1 << bits_allocated) - 1
    codes = values.astype(np.int64) & stored_mask
    containers = ((codes << low_bit) | (unused_pattern & (allocated_full ^ allocated_mask))).astype(
        np.uint8 if bits_allocated == 8 else np.dtype("<u2")
    )
    raw = containers.tobytes()
    if len(raw) % 2:
        raw += b"\0"
    return raw


def _orientation(oblique: bool) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    if not oblique:
        row = np.array([1.0, 0.0, 0.0])
        column = np.array([0.0, 1.0, 0.0])
    else:
        root = np.sqrt(0.5)
        row = np.array([root, root, 0.0])
        column = np.array([0.0, 0.0, 1.0])
    normal = np.cross(row, column)
    return row, column, normal


def _write_ct_series(
    root: Path,
    *,
    slice_count: int = 4,
    rows: int = 64,
    columns: int = 64,
    spacing_mm: float = 5.0,
    oblique: bool = False,
    bits_allocated: int = 16,
    bits_stored: int = 16,
    high_bit: int = 15,
    pixel_representation: int = 1,
    slopes: tuple[float, ...] | None = None,
    intercepts: tuple[float, ...] | None = None,
    water_hu: tuple[float, ...] | None = None,
    unused_pattern: int = 0,
    transfer_syntax_uid: str | None = None,
) -> dict[str, object]:
    root.mkdir()
    study_uid = _uid()
    series_uid = _uid()
    frame_uid = _uid()
    row_direction, column_direction, normal = _orientation(oblique)
    slopes = slopes or tuple(1.0 for _ in range(slice_count))
    intercepts = intercepts or tuple(0.0 for _ in range(slice_count))
    water_hu = water_hu or tuple(10.0 + index for index in range(slice_count))
    paths: list[Path] = []
    sop_uids: list[str] = []
    source_stored: list[np.ndarray] = []
    for index in range(slice_count):
        path = root / f"CT.{index + 1:04d}.dcm"
        sop_uid = _uid()
        dataset = _file_dataset(path, pydicom.uid.CTImageStorage, sop_uid)
        if transfer_syntax_uid is not None:
            dataset.file_meta.TransferSyntaxUID = transfer_syntax_uid
        dataset.Modality = "CT"
        dataset.PatientName = "SYNTHETIC^PHANTOM"
        dataset.PatientID = "SYNTHETIC-ID"
        dataset.StudyInstanceUID = study_uid
        dataset.SeriesInstanceUID = series_uid
        dataset.FrameOfReferenceUID = frame_uid
        dataset.SeriesDescription = "Synthetic Phantom"
        dataset.InstanceNumber = index + 1
        dataset.Rows = rows
        dataset.Columns = columns
        dataset.PixelSpacing = [1.0, 1.0]
        dataset.SliceThickness = spacing_mm
        dataset.SpacingBetweenSlices = spacing_mm
        dataset.ImageOrientationPatient = [
            *row_direction.tolist(),
            *column_direction.tolist(),
        ]
        position = normal * (index * spacing_mm)
        dataset.ImagePositionPatient = position.tolist()
        dataset.SamplesPerPixel = 1
        dataset.PhotometricInterpretation = "MONOCHROME2"
        dataset.BitsAllocated = bits_allocated
        dataset.BitsStored = bits_stored
        dataset.HighBit = high_bit
        dataset.PixelRepresentation = pixel_representation
        dataset.RescaleSlope = slopes[index]
        dataset.RescaleIntercept = intercepts[index]
        stored = np.full(
            (rows, columns),
            int(round((water_hu[index] - intercepts[index]) / slopes[index])),
            dtype=np.int32,
        )
        stored[10:31, 10:31] += 50 + index
        dataset.PixelData = _encode_stored(
            stored,
            bits_allocated=bits_allocated,
            bits_stored=bits_stored,
            high_bit=high_bit,
            pixel_representation=pixel_representation,
            unused_pattern=unused_pattern,
        )
        _save_dataset(dataset, path)
        paths.append(path)
        sop_uids.append(sop_uid)
        source_stored.append(stored)
    return {
        "root": root,
        "paths": tuple(paths),
        "sop_uids": tuple(sop_uids),
        "study_uid": study_uid,
        "series_uid": series_uid,
        "frame_uid": frame_uid,
        "row_direction": row_direction,
        "column_direction": column_direction,
        "normal": normal,
        "spacing_mm": spacing_mm,
        "source_stored": tuple(source_stored),
        "water_hu": water_hu,
    }


def _rectangle_points(
    *,
    origin: np.ndarray,
    row_direction: np.ndarray,
    column_direction: np.ndarray,
    row_min: float,
    row_max: float,
    column_min: float,
    column_max: float,
) -> list[float]:
    points = []
    for row, column in (
        (row_min, column_min),
        (row_min, column_max),
        (row_max, column_max),
        (row_max, column_min),
    ):
        point = origin + row_direction * column + column_direction * row
        points.extend(float(value) for value in point)
    return points


def _write_rtstruct(
    path: Path,
    ct: dict[str, object],
    *,
    target_slices: tuple[int, ...] | None = None,
    reference_slices: tuple[int, ...] | None = None,
    target_bounds: tuple[float, float, float, float] = (10.0, 40.0, 10.0, 50.0),
    reference_bounds: tuple[float, float, float, float] = (5.0, 50.0, 52.0, 60.0),
    referenced_series_uid: str | None = None,
    frame_uid: str | None = None,
) -> Path:
    sop_uid = _uid()
    dataset = _file_dataset(path, pydicom.uid.RTStructureSetStorage, sop_uid)
    dataset.Modality = "RTSTRUCT"
    dataset.StudyInstanceUID = ct["study_uid"]
    dataset.SeriesInstanceUID = _uid()
    selected_frame_uid = frame_uid or str(ct["frame_uid"])
    target_slices = target_slices if target_slices is not None else tuple(
        range(len(ct["paths"]))
    )
    reference_slices = reference_slices if reference_slices is not None else tuple(
        range(len(ct["paths"]))
    )

    referenced_frame = Dataset()
    referenced_frame.FrameOfReferenceUID = selected_frame_uid
    referenced_study = Dataset()
    referenced_study.ReferencedSOPClassUID = "1.2.840.10008.3.1.2.3.1"
    referenced_study.ReferencedSOPInstanceUID = ct["study_uid"]
    referenced_series = Dataset()
    referenced_series.SeriesInstanceUID = referenced_series_uid or ct["series_uid"]
    referenced_images = []
    for sop_instance_uid in ct["sop_uids"]:
        image = Dataset()
        image.ReferencedSOPClassUID = pydicom.uid.CTImageStorage
        image.ReferencedSOPInstanceUID = sop_instance_uid
        referenced_images.append(image)
    referenced_series.ContourImageSequence = referenced_images
    referenced_study.RTReferencedSeriesSequence = [referenced_series]
    referenced_frame.RTReferencedStudySequence = [referenced_study]
    dataset.ReferencedFrameOfReferenceSequence = [referenced_frame]

    roi_items = []
    for number, name in ((1, "Water_CC13_2cm"), (2, "Water_reference")):
        roi = Dataset()
        roi.ROINumber = number
        roi.ReferencedFrameOfReferenceUID = selected_frame_uid
        roi.ROIName = name
        roi.ROIGenerationAlgorithm = "MANUAL"
        roi_items.append(roi)
    dataset.StructureSetROISequence = roi_items

    row_direction = np.asarray(ct["row_direction"])
    column_direction = np.asarray(ct["column_direction"])
    normal = np.asarray(ct["normal"])
    spacing = float(ct["spacing_mm"])
    roi_contours = []
    for roi_number, slice_indices, bounds in (
        (1, target_slices, target_bounds),
        (2, reference_slices, reference_bounds),
    ):
        roi_contour = Dataset()
        roi_contour.ReferencedROINumber = roi_number
        contours = []
        for index in slice_indices:
            origin = normal * (index * spacing)
            contour = Dataset()
            contour.ContourGeometricType = "CLOSED_PLANAR"
            contour.NumberOfContourPoints = 4
            contour.ContourData = _rectangle_points(
                origin=origin,
                row_direction=row_direction,
                column_direction=column_direction,
                row_min=bounds[0],
                row_max=bounds[1],
                column_min=bounds[2],
                column_max=bounds[3],
            )
            reference = Dataset()
            reference.ReferencedSOPClassUID = pydicom.uid.CTImageStorage
            reference.ReferencedSOPInstanceUID = ct["sop_uids"][index]
            contour.ContourImageSequence = [reference]
            contours.append(contour)
        roi_contour.ContourSequence = contours
        roi_contours.append(roi_contour)
    dataset.ROIContourSequence = roi_contours
    _save_dataset(dataset, path)
    return path


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _case(tmp_path: Path, **ct_options: object) -> dict[str, object]:
    ct = _write_ct_series(tmp_path / "ct", **ct_options)
    rtstruct = _write_rtstruct(tmp_path / "RTSTRUCT.dcm", ct)
    return {"ct": ct, "rtstruct": rtstruct, "output": tmp_path / "derived"}


def _derive(case: dict[str, object], **overrides: object):
    options = {
        "ct_dir": case["ct"]["root"],
        "rtstruct": case["rtstruct"],
        "target_roi": "Water_CC13_2cm",
        "reference_roi": "Water_reference",
        "output_dir": case["output"],
        "confirmed_non_patient_phantom": True,
    }
    options.update(overrides)
    return derive_phantom_ct(**options)


def test_confirmation_is_required_before_inputs_are_read(tmp_path: Path) -> None:
    with pytest.raises(PhantomCtDerivationError, match="confirmation|acknowledgement"):
        derive_phantom_ct(
            ct_dir=tmp_path / "missing",
            rtstruct=tmp_path / "missing-rtstruct.dcm",
            target_roi="target",
            reference_roi="reference",
            output_dir=tmp_path / "output",
            confirmed_non_patient_phantom=False,
        )
    assert not (tmp_path / "output").exists()


def test_boundary_connected_uses_four_connected_run_components() -> None:
    mask = np.zeros((7, 7), dtype=bool)
    mask[0, 0:3] = True
    mask[1, 2:5] = True
    mask[2, 4] = True
    mask[4:6, 1:3] = True
    mask[6, 6] = True
    expected = np.zeros_like(mask)
    expected[0, 0:3] = True
    expected[1, 2:5] = True
    expected[2, 4] = True
    expected[6, 6] = True
    np.testing.assert_array_equal(_boundary_connected(mask), expected)


def test_target_thickness_uses_shortest_patient_coordinate_principal_extent(
    tmp_path: Path,
) -> None:
    ct = _write_ct_series(tmp_path / "ct", slice_count=32)
    rtstruct = _write_rtstruct(
        tmp_path / "RTSTRUCT.dcm",
        ct,
        target_bounds=(10.0, 30.0, 10.0, 50.0),
        reference_bounds=(5.0, 50.0, 52.0, 60.0),
    )
    series = load_ct_series(ct["root"])
    target, reference = load_rtstruct_masks(
        rtstruct,
        series=series,
        target_roi="Water_CC13_2cm",
        reference_roi="Water_reference",
    )
    analysis, warnings, _replacement_hu = _replacement_analysis(
        series, target, reference
    )
    assert analysis["target_stack_extent_mm"] == pytest.approx(160.0)
    assert analysis["target_thickness_mm"] == pytest.approx(21.0)
    assert not any("target occupied thickness" in warning for warning in warnings)


def test_two_by_two_centimeter_rod_is_not_accepted_as_a_whole_layer(
    tmp_path: Path,
) -> None:
    ct = _write_ct_series(tmp_path / "ct", slice_count=32)
    rtstruct = _write_rtstruct(
        tmp_path / "RTSTRUCT.dcm",
        ct,
        target_bounds=(10.0, 30.0, 10.0, 30.0),
        reference_bounds=(5.0, 50.0, 52.0, 60.0),
    )
    series = load_ct_series(ct["root"])
    target, reference = load_rtstruct_masks(
        rtstruct,
        series=series,
        target_roi="Water_CC13_2cm",
        reference_roi="Water_reference",
    )
    analysis, warnings, _replacement_hu = _replacement_analysis(
        series, target, reference
    )
    assert analysis["target_thickness_range_dimension_count"] == 2
    assert any("whole layer" in warning for warning in warnings)


def test_success_replaces_target_only_and_updates_uids(tmp_path: Path) -> None:
    case = _case(tmp_path)
    source_hashes = {
        path.name: _sha256(path) for path in case["ct"]["paths"]
    }
    result = _derive(case)
    assert len(result.dicom_files) == 4
    assert result.png_report.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
    assert not (result.output_dir / "INCOMPLETE.txt").exists()
    report = json.loads(result.json_report.read_text(encoding="utf-8"))
    assert report["status"] == "complete"
    assert report["output"]["outside_target_pixel_bytes_verified"] is True
    assert report["output"]["rtstruct_integrity_verified"] is True
    assert report["qc"]["fallback_slice_indices"] == []
    report_text = result.json_report.read_text(encoding="utf-8")
    assert "PatientName" not in report_text
    assert "SYNTHETIC^PHANTOM" not in report_text
    assert "SYNTHETIC-ID" not in report_text
    new_series_uids = set()
    for index, (source_path, output_path) in enumerate(
        zip(case["ct"]["paths"], result.dicom_files, strict=True)
    ):
        source = pydicom.dcmread(source_path)
        derived = pydicom.dcmread(output_path)
        new_series_uids.add(str(derived.SeriesInstanceUID))
        assert str(derived.SeriesInstanceUID) != str(source.SeriesInstanceUID)
        assert str(derived.SOPInstanceUID) != str(source.SOPInstanceUID)
        assert str(derived.file_meta.MediaStorageSOPInstanceUID) == str(
            derived.SOPInstanceUID
        )
        assert str(derived.StudyInstanceUID) == str(source.StudyInstanceUID)
        assert str(derived.FrameOfReferenceUID) == str(source.FrameOfReferenceUID)
        assert list(derived.ImageType)[:2] == ["DERIVED", "SECONDARY"]
        source_array = source.pixel_array
        derived_array = derived.pixel_array
        target = np.zeros(source_array.shape, dtype=bool)
        target[10:41, 10:51] = True
        np.testing.assert_array_equal(derived_array[~target], source_array[~target])
        assert np.all(derived_array[target] == int(case["ct"]["water_hu"][index]))
    assert len(new_series_uids) == 1
    assert {
        path.name: _sha256(path) for path in case["ct"]["paths"]
    } == source_hashes


def test_per_slice_rescale_and_global_fallback_are_reported(tmp_path: Path) -> None:
    ct = _write_ct_series(
        tmp_path / "ct",
        slopes=(1.0, 2.0, 1.0, 2.0),
        intercepts=(-1000.0, -1000.0, -1000.0, -1000.0),
        water_hu=(10.0, 12.0, 14.0, 16.0),
    )
    rtstruct = _write_rtstruct(
        tmp_path / "RTSTRUCT.dcm",
        ct,
        reference_slices=(0, 1, 2),
    )
    case = {"ct": ct, "rtstruct": rtstruct, "output": tmp_path / "derived"}
    result = _derive(case)
    report = json.loads(result.json_report.read_text(encoding="utf-8"))
    assert report["qc"]["fallback_slice_indices"] == [3]
    assert report["per_slice"][3]["replacement_hu"] == pytest.approx(12.0)
    assert report["per_slice"][3]["replacement_stored_value"] == 506
    for index, path in enumerate(result.dicom_files):
        dataset = pydicom.dcmread(path)
        desired_hu = report["per_slice"][index]["replacement_hu"]
        actual_hu = (
            dataset.pixel_array[15, 15] * float(dataset.RescaleSlope)
            + float(dataset.RescaleIntercept)
        )
        assert actual_hu == pytest.approx(desired_hu)


@pytest.mark.parametrize("pixel_representation", [0, 1])
def test_signed_and_unsigned_pixel_representations(
    tmp_path: Path, pixel_representation: int
) -> None:
    case = _case(
        tmp_path,
        bits_allocated=16,
        bits_stored=12,
        high_bit=11,
        pixel_representation=pixel_representation,
        water_hu=(20.0, 20.0, 20.0, 20.0),
    )
    result = _derive(case)
    for path in result.dicom_files:
        assert int(pydicom.dcmread(path).pixel_array[15, 15]) == 20


def test_bits_stored_high_bit_and_unused_bits_are_preserved(tmp_path: Path) -> None:
    case = _case(
        tmp_path,
        bits_allocated=16,
        bits_stored=12,
        high_bit=14,
        pixel_representation=0,
        water_hu=(20.0, 20.0, 20.0, 20.0),
        unused_pattern=0x8005,
    )
    source = pydicom.dcmread(case["ct"]["paths"][0])
    result = _derive(case)
    derived = pydicom.dcmread(result.dicom_files[0])
    source_raw = np.frombuffer(source.PixelData, dtype="<u2").reshape(64, 64)
    derived_raw = np.frombuffer(derived.PixelData, dtype="<u2").reshape(64, 64)
    target = np.zeros((64, 64), dtype=bool)
    target[10:41, 10:51] = True
    np.testing.assert_array_equal(derived_raw[~target], source_raw[~target])
    assert np.all((derived_raw[target] & 0x8007) == (source_raw[target] & 0x8007))


def test_oblique_patient_coordinate_contours_are_supported(tmp_path: Path) -> None:
    case = _case(tmp_path, oblique=True)
    result = _derive(case)
    assert len(result.dicom_files) == 4
    report = json.loads(result.json_report.read_text(encoding="utf-8"))
    assert report["geometry"]["normal_direction"] != [0.0, 0.0, 1.0]


def test_qc_warning_requires_separate_acknowledgement(tmp_path: Path) -> None:
    ct = _write_ct_series(tmp_path / "ct")
    rtstruct = _write_rtstruct(
        tmp_path / "RTSTRUCT.dcm",
        ct,
        target_slices=(0,),
        reference_bounds=(5.0, 10.0, 52.0, 56.0),
    )
    case = {"ct": ct, "rtstruct": rtstruct, "output": tmp_path / "derived"}
    with pytest.raises(PhantomCtDerivationError, match="QC warnings"):
        _derive(case)
    assert not case["output"].exists()
    result = _derive(case, accept_qc_warnings=True)
    assert result.warnings
    report = json.loads(result.json_report.read_text(encoding="utf-8"))
    assert report["warning_acknowledged"] is True


def test_boundary_connected_air_in_target_is_a_recorded_qc_warning(
    tmp_path: Path,
) -> None:
    case = _case(
        tmp_path,
        water_hu=(-1000.0, -1000.0, -1000.0, -1000.0),
    )
    result = _derive(case, accept_qc_warnings=True)
    assert any("boundary-connected" in warning for warning in result.warnings)
    report = json.loads(result.json_report.read_text(encoding="utf-8"))
    assert report["qc"]["target_boundary_connected_air_voxel_count"] > 0


@pytest.mark.parametrize(
    (
        "roi_name",
        "coordinate",
        "padding_sample",
        "padding_value",
        "padding_limit",
    ),
    (
        pytest.param("target", (15, 15), 60, 60, None, id="target-value"),
        pytest.param("reference", (10, 55), 45, 40, 50, id="reference-range"),
    ),
)
def test_pixel_padding_values_in_rois_are_rejected(
    tmp_path: Path,
    roi_name: str,
    coordinate: tuple[int, int],
    padding_sample: int,
    padding_value: int,
    padding_limit: int | None,
) -> None:
    case = _case(tmp_path)
    first_path = case["ct"]["paths"][0]
    dataset = pydicom.dcmread(first_path)
    stored = dataset.pixel_array.astype(np.int32)
    stored[coordinate] = padding_sample
    padding_vr = "SS" if int(dataset.PixelRepresentation) else "US"
    dataset.add_new(0x00280120, padding_vr, padding_value)
    if padding_limit is not None:
        dataset.add_new(0x00280121, padding_vr, padding_limit)
    dataset.PixelData = _encode_stored(
        stored,
        bits_allocated=int(dataset.BitsAllocated),
        bits_stored=int(dataset.BitsStored),
        high_bit=int(dataset.HighBit),
        pixel_representation=int(dataset.PixelRepresentation),
    )
    _save_dataset(dataset, first_path)

    with pytest.raises(
        PhantomCtDerivationError,
        match=rf"{roi_name} ROI contains CT pixel padding values",
    ):
        _derive(case, accept_qc_warnings=True)
    assert not case["output"].exists()


def test_existing_and_overlapping_output_paths_are_rejected(tmp_path: Path) -> None:
    case = _case(tmp_path)
    case["output"].mkdir()
    with pytest.raises(PhantomCtDerivationError, match="already exists"):
        _derive(case)
    nested_output = case["ct"]["root"] / "derived"
    with pytest.raises(PhantomCtDerivationError, match="must not equal"):
        _derive(case, output_dir=nested_output)


def test_output_created_during_preflight_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    case = _case(tmp_path)
    sentinel = case["output"] / "sentinel.txt"

    def create_competing_output(*args: object, **kwargs: object):
        result = _replacement_analysis(*args, **kwargs)
        case["output"].mkdir()
        sentinel.write_text("preserve", encoding="utf-8")
        return result

    monkeypatch.setattr(
        "dicomxphits.replace_ct_layer_with_water._replacement_analysis",
        create_competing_output,
    )
    with pytest.raises(PhantomCtDerivationError, match="already exists"):
        _derive(case)

    assert sentinel.read_text(encoding="utf-8") == "preserve"
    assert set(case["output"].iterdir()) == {sentinel}


def test_output_below_resolved_ct_root_is_rejected(tmp_path: Path) -> None:
    actual_parent = tmp_path / "actual"
    actual_parent.mkdir()
    case = _case(actual_parent)
    linked_parent = tmp_path / "linked"
    try:
        linked_parent.symlink_to(actual_parent, target_is_directory=True)
    except OSError as symlink_error:
        if sys.platform != "win32":
            pytest.skip(f"directory symlink creation is unavailable: {symlink_error}")
        trusted_cmd = Path(os.environ["SystemRoot"]) / "System32" / "cmd.exe"
        result = subprocess.run(
            [
                str(trusted_cmd),
                "/d",
                "/c",
                "mklink",
                "/J",
                str(linked_parent),
                str(actual_parent),
            ],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if result.returncode != 0:
            pytest.skip(
                "directory link creation is unavailable: "
                f"{symlink_error}; {result.stdout}{result.stderr}"
            )

    nested_output = case["ct"]["root"] / "derived"
    with pytest.raises(PhantomCtDerivationError, match="must not equal"):
        _derive(
            case,
            ct_dir=linked_parent / "ct",
            output_dir=nested_output,
        )
    assert not nested_output.exists()


def test_rtstruct_series_reference_mismatch_is_rejected(tmp_path: Path) -> None:
    ct = _write_ct_series(tmp_path / "ct")
    rtstruct = _write_rtstruct(
        tmp_path / "RTSTRUCT.dcm", ct, referenced_series_uid=_uid()
    )
    case = {"ct": ct, "rtstruct": rtstruct, "output": tmp_path / "derived"}
    with pytest.raises(PhantomCtDerivationError, match="does not reference"):
        _derive(case)
    assert not case["output"].exists()


def test_rtstruct_series_must_be_nested_in_selected_frame(tmp_path: Path) -> None:
    case = _case(tmp_path)
    rtstruct = pydicom.dcmread(case["rtstruct"])
    selected_frame = rtstruct.ReferencedFrameOfReferenceSequence[0]
    mismatched_frame = Dataset()
    mismatched_frame.FrameOfReferenceUID = _uid()
    mismatched_frame.RTReferencedStudySequence = selected_frame.RTReferencedStudySequence
    del selected_frame.RTReferencedStudySequence
    rtstruct.ReferencedFrameOfReferenceSequence.append(mismatched_frame)
    _save_dataset(rtstruct, case["rtstruct"])

    with pytest.raises(PhantomCtDerivationError, match="frame hierarchy"):
        _derive(case)
    assert not case["output"].exists()


def test_contour_image_must_be_listed_in_selected_frame_series(
    tmp_path: Path,
) -> None:
    case = _case(tmp_path)
    rtstruct = pydicom.dcmread(case["rtstruct"])
    referenced_series = (
        rtstruct.ReferencedFrameOfReferenceSequence[0]
        .RTReferencedStudySequence[0]
        .RTReferencedSeriesSequence[0]
    )
    referenced_series.ContourImageSequence = list(
        referenced_series.ContourImageSequence[1:]
    )
    _save_dataset(rtstruct, case["rtstruct"])

    with pytest.raises(PhantomCtDerivationError, match="frame/series hierarchy"):
        _derive(case)
    assert not case["output"].exists()


@pytest.mark.parametrize(
    "referenced_sop_class_uid",
    (None, pydicom.uid.MRImageStorage),
)
def test_hierarchy_image_reference_requires_ct_sop_class(
    tmp_path: Path,
    referenced_sop_class_uid: str | None,
) -> None:
    case = _case(tmp_path)
    rtstruct = pydicom.dcmread(case["rtstruct"])
    reference = (
        rtstruct.ReferencedFrameOfReferenceSequence[0]
        .RTReferencedStudySequence[0]
        .RTReferencedSeriesSequence[0]
        .ContourImageSequence[0]
    )
    if referenced_sop_class_uid is None:
        del reference.ReferencedSOPClassUID
    else:
        reference.ReferencedSOPClassUID = referenced_sop_class_uid
    _save_dataset(rtstruct, case["rtstruct"])

    with pytest.raises(PhantomCtDerivationError, match="CT Image Storage"):
        _derive(case)
    assert not case["output"].exists()


def test_rtstruct_requires_structure_set_storage_sop_class(tmp_path: Path) -> None:
    case = _case(tmp_path)
    rtstruct = pydicom.dcmread(case["rtstruct"])
    rtstruct.SOPClassUID = pydicom.uid.MRImageStorage
    rtstruct.file_meta.MediaStorageSOPClassUID = pydicom.uid.MRImageStorage
    _save_dataset(rtstruct, case["rtstruct"])

    with pytest.raises(PhantomCtDerivationError, match="RT Structure Set Storage"):
        _derive(case)
    assert not case["output"].exists()


@pytest.mark.parametrize(
    "file_meta_attribute",
    (
        "MediaStorageSOPClassUID",
        "MediaStorageSOPInstanceUID",
    ),
)
def test_rtstruct_file_meta_sop_identity_mismatch_is_rejected(
    tmp_path: Path,
    file_meta_attribute: str,
) -> None:
    case = _case(tmp_path)
    rtstruct_path = case["rtstruct"]
    rtstruct = pydicom.dcmread(rtstruct_path)
    original = str(getattr(rtstruct.file_meta, file_meta_attribute)).encode("ascii")
    replacement = bytearray(original)
    replacement[-1] = ord("0") if replacement[-1] != ord("0") else ord("1")
    raw = rtstruct_path.read_bytes()
    assert raw.count(original) >= 2
    rtstruct_path.write_bytes(raw.replace(original, bytes(replacement), 1))

    with pytest.raises(PhantomCtDerivationError, match="file-meta SOP identity"):
        _derive(case)
    assert not case["output"].exists()


def test_selected_roi_number_must_be_unique(tmp_path: Path) -> None:
    case = _case(tmp_path)
    rtstruct = pydicom.dcmread(case["rtstruct"])
    duplicate = Dataset()
    duplicate.ROINumber = rtstruct.StructureSetROISequence[0].ROINumber
    duplicate.ReferencedFrameOfReferenceUID = rtstruct.StructureSetROISequence[
        0
    ].ReferencedFrameOfReferenceUID
    duplicate.ROIName = "Different_name_same_number"
    duplicate.ROIGenerationAlgorithm = "MANUAL"
    rtstruct.StructureSetROISequence.append(duplicate)
    _save_dataset(rtstruct, case["rtstruct"])

    with pytest.raises(
        PhantomCtDerivationError, match="ROI number must occur exactly once"
    ):
        _derive(case)
    assert not case["output"].exists()


def test_target_reference_overlap_is_rejected(tmp_path: Path) -> None:
    ct = _write_ct_series(tmp_path / "ct")
    rtstruct = _write_rtstruct(
        tmp_path / "RTSTRUCT.dcm",
        ct,
        target_bounds=(10.0, 40.0, 10.0, 50.0),
        reference_bounds=(10.0, 30.0, 10.0, 30.0),
    )
    case = {"ct": ct, "rtstruct": rtstruct, "output": tmp_path / "derived"}
    with pytest.raises(PhantomCtDerivationError, match="overlap"):
        _derive(case)


def test_zero_area_closed_planar_contour_is_rejected(tmp_path: Path) -> None:
    case = _case(tmp_path)
    rtstruct = pydicom.dcmread(case["rtstruct"])
    contour = rtstruct.ROIContourSequence[0].ContourSequence[0]
    points = np.asarray(contour.ContourData, dtype=np.float64).reshape(-1, 3)
    contour.NumberOfContourPoints = 3
    contour.ContourData = np.concatenate(
        (points[0], (points[0] + points[2]) / 2.0, points[2])
    ).tolist()
    _save_dataset(rtstruct, case["rtstruct"])

    with pytest.raises(PhantomCtDerivationError, match="nonzero area"):
        _derive(case, accept_qc_warnings=True)
    assert not case["output"].exists()


def test_target_layer_with_missing_internal_contour_slice_is_rejected(
    tmp_path: Path,
) -> None:
    ct = _write_ct_series(tmp_path / "ct")
    rtstruct = _write_rtstruct(
        tmp_path / "RTSTRUCT.dcm",
        ct,
        target_slices=(0, 2, 3),
    )
    case = {"ct": ct, "rtstruct": rtstruct, "output": tmp_path / "derived"}
    with pytest.raises(PhantomCtDerivationError, match="unrepresented CT slices"):
        _derive(case)


def test_compressed_pixel_data_is_rejected_without_output(tmp_path: Path) -> None:
    case = _case(tmp_path)
    first_path = case["ct"]["paths"][0]
    raw = first_path.read_bytes()
    explicit_little_endian = b"1.2.840.10008.1.2.1\0"
    rle_lossless = b"1.2.840.10008.1.2.5\0"
    assert explicit_little_endian in raw
    first_path.write_bytes(raw.replace(explicit_little_endian, rle_lossless, 1))
    with pytest.raises(PhantomCtDerivationError, match="uncompressed"):
        _derive(case)
    assert not case["output"].exists()


@pytest.mark.parametrize(
    "file_meta_attribute",
    (
        "MediaStorageSOPClassUID",
        "MediaStorageSOPInstanceUID",
    ),
)
def test_source_file_meta_sop_identity_mismatch_is_rejected(
    tmp_path: Path,
    file_meta_attribute: str,
) -> None:
    case = _case(tmp_path)
    first_path = case["ct"]["paths"][0]
    dataset = pydicom.dcmread(first_path)
    original = str(getattr(dataset.file_meta, file_meta_attribute)).encode("ascii")
    replacement = bytearray(original)
    replacement[-1] = ord("0") if replacement[-1] != ord("0") else ord("1")
    raw = first_path.read_bytes()
    assert raw.count(original) >= 2
    first_path.write_bytes(raw.replace(original, bytes(replacement), 1))

    with pytest.raises(PhantomCtDerivationError, match="file-meta SOP identity"):
        _derive(case)
    assert not case["output"].exists()


def test_explicit_non_hu_rescale_type_is_rejected(tmp_path: Path) -> None:
    case = _case(tmp_path)
    first_path = case["ct"]["paths"][0]
    dataset = pydicom.dcmread(first_path)
    dataset.RescaleType = "US"
    _save_dataset(dataset, first_path)

    with pytest.raises(PhantomCtDerivationError, match="RescaleType must be HU"):
        _derive(case)
    assert not case["output"].exists()


def test_derived_instance_uses_writer_implementation_identity(tmp_path: Path) -> None:
    case = _case(tmp_path)
    source_implementation_uid = "1.2.826.0.1.3680043.10.999"
    source_instance_creator_uid = "1.2.826.0.1.3680043.10.998"
    source_version_name = "SOURCE_WRITER"
    for path in case["ct"]["paths"]:
        dataset = pydicom.dcmread(path)
        dataset.InstanceCreatorUID = source_instance_creator_uid
        dataset.file_meta.ImplementationClassUID = source_implementation_uid
        dataset.file_meta.ImplementationVersionName = source_version_name
        _save_dataset(dataset, path)

    result = _derive(case)
    for path in result.dicom_files:
        derived = pydicom.dcmread(path)
        assert "InstanceCreatorUID" not in derived
        assert str(derived.file_meta.ImplementationClassUID) != source_implementation_uid
        assert str(derived.file_meta.ImplementationVersionName) != source_version_name


def test_derived_instance_removes_source_sop_authorization(tmp_path: Path) -> None:
    case = _case(tmp_path)
    source_authorization = {
        "SOPInstanceStatus": "ORIGINAL",
        "SOPAuthorizationDateTime": "20260831120000+0900",
        "SOPAuthorizationComment": "Authorized source instance",
        "AuthorizationEquipmentCertificationNumber": "SOURCE-EQUIPMENT",
    }
    for path in case["ct"]["paths"]:
        dataset = pydicom.dcmread(path)
        for keyword, value in source_authorization.items():
            setattr(dataset, keyword, value)
        _save_dataset(dataset, path)

    result = _derive(case)
    for path in result.dicom_files:
        derived = pydicom.dcmread(path)
        for keyword in source_authorization:
            assert keyword not in derived


def test_derived_dataset_removes_stale_pixel_extrema(tmp_path: Path) -> None:
    case = _case(tmp_path)
    for path in case["ct"]["paths"]:
        dataset = pydicom.dcmread(path)
        dataset.add_new(
            0x00280106, "SS", int(np.min(dataset.pixel_array))
        )
        dataset.add_new(
            0x00280107, "SS", int(np.max(dataset.pixel_array))
        )
        _save_dataset(dataset, path)

    result = _derive(case)
    for path in result.dicom_files:
        derived = pydicom.dcmread(path)
        assert "SmallestImagePixelValue" not in derived
        assert "LargestImagePixelValue" not in derived


def test_inverse_rescale_overflow_is_rejected(tmp_path: Path) -> None:
    ct = _write_ct_series(
        tmp_path / "ct",
        bits_allocated=8,
        bits_stored=8,
        high_bit=7,
        pixel_representation=0,
        slopes=(1.0, 1.0, 1.0, 1.0),
        intercepts=(1000.0, 0.0, 0.0, 0.0),
        water_hu=(1000.0, 10.0, 10.0, 10.0),
    )
    rtstruct = _write_rtstruct(
        tmp_path / "RTSTRUCT.dcm",
        ct,
        target_slices=(1,),
        reference_slices=(0,),
        reference_bounds=(5.0, 50.0, 52.0, 60.0),
    )
    case = {"ct": ct, "rtstruct": rtstruct, "output": tmp_path / "derived"}
    with pytest.raises(PhantomCtDerivationError, match="stored-pixel range"):
        _derive(case, accept_qc_warnings=True)
    assert not case["output"].exists()


def test_cli_script_creates_a_verified_series(tmp_path: Path) -> None:
    case = _case(tmp_path)
    script = Path(__file__).resolve().parents[1] / "tools" / "replace_ct_layer_with_water.py"
    result = subprocess.run(
        [
            sys.executable,
            str(script),
            "--ct-dir",
            str(case["ct"]["root"]),
            "--rtstruct",
            str(case["rtstruct"]),
            "--target-roi",
            "Water_CC13_2cm",
            "--reference-roi",
            "Water_reference",
            "--output-dir",
            str(case["output"]),
            "--confirm-non-patient-phantom",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert "original RTSTRUCT still references" in result.stdout
    assert (case["output"] / "qc-report.json").is_file()
