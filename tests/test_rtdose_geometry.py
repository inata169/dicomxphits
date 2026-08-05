from __future__ import annotations

from pathlib import Path

import pydicom
import pytest
from pydicom.dataset import Dataset, FileDataset

from dicomxphits.rtdose_geometry import (
    derive_rtdose_placement,
    parse_tally_mesh_geometry,
    segment_tally_geometry_binding,
    validate_rtdose_placement,
)


def tally_text(
    *,
    xmin: float = -0.7,
    xmax: float = 0.5,
    nx: int = 4,
    ymin: float = -0.3,
    ymax: float = 0.1,
    ny: int = 2,
    zmin: float = -0.9,
    zmax: float = 0.3,
    nz: int = 3,
) -> str:
    return (
        "[ T-Deposit ]\n"
        f" xmin = {xmin}\n"
        f" xmax = {xmax}\n"
        f" nx = {nx}\n"
        f" ymin = {ymin}\n"
        f" ymax = {ymax}\n"
        f" ny = {ny}\n"
        f" zmin = {zmin}\n"
        f" zmax = {zmax}\n"
        f" nz = {nz}\n"
    )


def write_tally(path: Path, **kwargs) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(tally_text(**kwargs), encoding="utf-8")
    return path


def write_positioned_rtdose(path: Path, placement: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    file_meta = Dataset()
    file_meta.MediaStorageSOPClassUID = pydicom.uid.RTDoseStorage
    file_meta.MediaStorageSOPInstanceUID = "1.2.826.0.1.3680043.10.543.101"
    file_meta.TransferSyntaxUID = pydicom.uid.ExplicitVRLittleEndian
    dataset = FileDataset(str(path), {}, file_meta=file_meta, preamble=b"\0" * 128)
    dataset.SOPClassUID = file_meta.MediaStorageSOPClassUID
    dataset.SOPInstanceUID = file_meta.MediaStorageSOPInstanceUID
    dataset.Modality = "RTDOSE"
    (
        dataset.NumberOfFrames,
        dataset.Rows,
        dataset.Columns,
    ) = placement["output_shape_frames_rows_columns"]
    dataset.PixelSpacing = placement["pixel_spacing_mm"]
    dataset.GridFrameOffsetVector = placement["grid_frame_offset_vector_mm"]
    dataset.ImageOrientationPatient = placement["image_orientation_patient"]
    dataset.ImagePositionPatient = placement["image_position_patient_mm"]
    dataset.save_as(str(path))


def test_asymmetric_tally_edges_derive_exact_plan_anchored_affine(
    tmp_path: Path,
) -> None:
    geometry = parse_tally_mesh_geometry(write_tally(tmp_path / "dose.out"))
    placement = derive_rtdose_placement(
        geometry,
        rtplan_isocenter_dicom_mm=[10.0, -20.0, 30.0],
    )

    assert geometry["bounds_semantics"] == "bin_edges"
    assert geometry["axes"]["x"]["spacing_cm"] == pytest.approx(0.3)
    assert geometry["axes"]["y"]["spacing_cm"] == pytest.approx(0.2)
    assert geometry["axes"]["z"]["spacing_cm"] == pytest.approx(0.4)
    assert placement["output_shape_frames_rows_columns"] == [2, 3, 4]
    assert placement["pixel_spacing_mm"] == pytest.approx([4.0, 3.0])
    assert placement["grid_frame_offset_vector_mm"] == pytest.approx([0.0, 2.0])
    assert placement["image_position_patient_mm"] == pytest.approx(
        [6.5, -27.0, 28.0]
    )
    assert placement["rule_derived_volume_center_dicom_mm"] == pytest.approx(
        [11.0, -23.0, 29.0]
    )


def test_segment_tallies_must_share_one_mesh(tmp_path: Path) -> None:
    first = write_tally(tmp_path / "first.out")
    second = write_tally(tmp_path / "second.out", zmax=0.6)

    with pytest.raises(ValueError, match="do not share one mesh"):
        segment_tally_geometry_binding([first, second])


def test_missing_or_ambiguous_mesh_evidence_fails(tmp_path: Path) -> None:
    missing = tmp_path / "missing.out"
    missing.write_text("xmin = -1\n", encoding="utf-8")
    with pytest.raises(ValueError, match="missing xmax"):
        parse_tally_mesh_geometry(missing)

    ambiguous = write_tally(tmp_path / "ambiguous.out")
    ambiguous.write_text(
        ambiguous.read_text(encoding="utf-8") + "xmin = -2\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="ambiguous xmin"):
        parse_tally_mesh_geometry(ambiguous)


def test_explicit_target_requires_reason_and_records_translation(
    tmp_path: Path,
) -> None:
    geometry = parse_tally_mesh_geometry(write_tally(tmp_path / "dose.out"))
    with pytest.raises(ValueError, match="non-empty reason"):
        derive_rtdose_placement(
            geometry,
            rtplan_isocenter_dicom_mm=[10.0, -20.0, 30.0],
            target_center_dicom_mm=[1.0, 2.0, 3.0],
        )

    placement = derive_rtdose_placement(
        geometry,
        rtplan_isocenter_dicom_mm=[10.0, -20.0, 30.0],
        target_center_dicom_mm=[1.0, 2.0, 3.0],
        target_reason="bounded synthetic reproduction",
    )
    assert placement["mode"] == "explicit_reasoned_target_override"
    assert placement["requested_target_center_dicom_mm"] == [1.0, 2.0, 3.0]
    assert placement["applied_translation_dicom_mm"] == pytest.approx(
        [-10.0, 25.0, -26.0]
    )
    assert placement["output_volume_center_dicom_mm"] == pytest.approx(
        [1.0, 2.0, 3.0]
    )


def test_final_rtdose_affine_is_reopened_and_checked_componentwise(
    tmp_path: Path,
) -> None:
    geometry = parse_tally_mesh_geometry(write_tally(tmp_path / "dose.out"))
    placement = derive_rtdose_placement(
        geometry,
        rtplan_isocenter_dicom_mm=[10.0, -20.0, 30.0],
    )
    output = tmp_path / "fixed.dcm"
    write_positioned_rtdose(output, placement)

    validation = validate_rtdose_placement(
        output,
        expected_placement=placement,
    )

    assert validation["validated"] is True
    assert validation["maximum_absolute_component_residual_mm"] < 1e-12
    assert set(validation["points"]) == {"first", "centre", "edge", "final"}

    dataset = pydicom.dcmread(str(output))
    dataset.ImagePositionPatient = [
        float(dataset.ImagePositionPatient[0]) + 0.01,
        *dataset.ImagePositionPatient[1:],
    ]
    dataset.save_as(str(output))

    with pytest.raises(ValueError, match="residual exceeds"):
        validate_rtdose_placement(output, expected_placement=placement)
