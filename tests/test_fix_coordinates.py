from __future__ import annotations

from pathlib import Path

import numpy as np
import pydicom
import pytest
from pydicom.dataset import Dataset, FileDataset

from dicomxphits.fix_coordinates import fix_coordinates
from dicomxphits.rtdose_geometry import (
    derive_rtdose_placement,
    parse_tally_mesh_geometry,
)


def write_rtdose(
    path: Path,
    *,
    shape: tuple[int, int, int] = (3, 2, 4),
    pixel_spacing: tuple[float, float] = (2.0, 3.0),
    frame_offsets: tuple[float, ...] = (0.0, 4.0, 8.0),
    orientation: tuple[float, ...] = (1.0, 0.0, 0.0, 0.0, 1.0, 0.0),
) -> np.ndarray:
    file_meta = Dataset()
    file_meta.MediaStorageSOPClassUID = "1.2.840.10008.5.1.4.1.1.481.2"
    file_meta.MediaStorageSOPInstanceUID = "1.2.826.0.1.3680043.10.543.1"
    file_meta.TransferSyntaxUID = pydicom.uid.ExplicitVRLittleEndian
    dataset = FileDataset(str(path), {}, file_meta=file_meta, preamble=b"\0" * 128)
    dataset.SOPClassUID = file_meta.MediaStorageSOPClassUID
    dataset.SOPInstanceUID = file_meta.MediaStorageSOPInstanceUID
    dataset.Modality = "RTDOSE"
    dataset.NumberOfFrames, dataset.Rows, dataset.Columns = shape
    dataset.PixelSpacing = list(pixel_spacing)
    dataset.GridFrameOffsetVector = list(frame_offsets)
    dataset.ImageOrientationPatient = list(orientation)
    dataset.ImagePositionPatient = [-4.0, -5.0, -6.0]
    dataset.SliceThickness = 4.0
    dataset.SpacingBetweenSlices = 4.0
    dataset.SamplesPerPixel = 1
    dataset.PhotometricInterpretation = "MONOCHROME2"
    dataset.BitsAllocated = 16
    dataset.BitsStored = 16
    dataset.HighBit = 15
    dataset.PixelRepresentation = 0
    dataset.DoseGridScaling = 0.125
    dataset.DoseUnits = "GY"
    dataset.DoseType = "PHYSICAL"
    dataset.DoseSummationType = "PLAN"
    dataset.FrameOfReferenceUID = "1.2.826.0.1.3680043.10.543.2"
    array = np.arange(int(np.prod(shape)), dtype=np.uint16).reshape(shape)
    dataset.PixelData = array.tobytes()
    dataset.save_as(str(path))
    return array


def test_anisotropic_axis_mapping_reverses_iec_x_and_preserves_volume_center(
    tmp_path: Path,
) -> None:
    source_path = tmp_path / "raw.dcm"
    output_path = tmp_path / "fixed.dcm"
    source = write_rtdose(source_path)

    summary = fix_coordinates(source_path, output_path)

    fixed = pydicom.dcmread(str(output_path))
    expected = source.transpose(1, 0, 2)[:, :, ::-1]
    np.testing.assert_array_equal(fixed.pixel_array, expected)
    np.testing.assert_array_equal(fixed.pixel_array[:, :, 0], source[:, :, -1].T)
    np.testing.assert_array_equal(fixed.pixel_array[:, :, -1], source[:, :, 0].T)
    assert fixed.pixel_array.shape == (2, 3, 4)
    assert [float(value) for value in fixed.PixelSpacing] == [4.0, 3.0]
    assert [float(value) for value in fixed.GridFrameOffsetVector] == [0.0, 2.0]
    assert [float(value) for value in fixed.ImagePositionPatient] == [-4.0, -8.0, -3.0]
    assert summary["source_geometry"]["volume_center"] == [0.5, -4.0, -2.0]
    assert summary["output_geometry"]["volume_center"] == [0.5, -4.0, -2.0]
    assert summary["invariants"]["stored_value_multiset_preserved"] is True
    assert float(fixed.DoseGridScaling) == 0.125
    assert fixed.DoseUnits == "GY"


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"pixel_spacing": (0.0, 3.0)}, "PixelSpacing values must be positive"),
        ({"frame_offsets": (0.0, 4.0, 9.0)}, "spacing must be uniform"),
        (
            {"orientation": (0.0, 1.0, 0.0, 1.0, 0.0, 0.0)},
            "outside the supported axial",
        ),
    ],
)
def test_unsupported_geometry_fails_without_output(
    tmp_path: Path,
    overrides: dict[str, tuple[float, ...]],
    message: str,
) -> None:
    source_path = tmp_path / "raw.dcm"
    output_path = tmp_path / "fixed.dcm"
    write_rtdose(source_path, **overrides)

    with pytest.raises(ValueError, match=message):
        fix_coordinates(source_path, output_path)

    assert not output_path.exists()


def write_tally_geometry(path: Path) -> None:
    path.write_text(
        "[ T-Deposit ]\n"
        " xmin = -0.7\n"
        " xmax = 0.5\n"
        " nx = 4\n"
        " ymin = -0.3\n"
        " ymax = 0.1\n"
        " ny = 2\n"
        " zmin = -0.9\n"
        " zmax = 0.3\n"
        " nz = 3\n",
        encoding="utf-8",
    )


def test_plan_and_tally_affine_replaces_converter_inherited_translation(
    tmp_path: Path,
) -> None:
    source_path = tmp_path / "raw.dcm"
    output_path = tmp_path / "fixed.dcm"
    tally_path = tmp_path / "dose.out"
    source = write_rtdose(source_path)
    write_tally_geometry(tally_path)
    placement = derive_rtdose_placement(
        parse_tally_mesh_geometry(tally_path),
        rtplan_isocenter_dicom_mm=[10.0, -20.0, 30.0],
    )

    summary = fix_coordinates(
        source_path,
        output_path,
        expected_placement=placement,
    )

    fixed = pydicom.dcmread(str(output_path))
    expected = source.transpose(1, 0, 2)[:, :, ::-1]
    np.testing.assert_array_equal(fixed.pixel_array, expected)
    assert [float(value) for value in fixed.ImagePositionPatient] == pytest.approx(
        [6.5, -27.0, 28.0]
    )
    assert summary["source_geometry"]["volume_center"] == [0.5, -4.0, -2.0]
    assert summary["output_geometry"]["volume_center"] == pytest.approx(
        [11.0, -23.0, 29.0]
    )
    assert summary["center_mode"] == "plan_and_tally_affine"
    assert summary["applied_translation_dicom_mm"] == pytest.approx(
        [10.5, -19.0, 31.0]
    )
    assert summary["target_override_translation_dicom_mm"] == [0.0, 0.0, 0.0]
    assert len(summary["input_sha256"]) == 64
    assert len(summary["output_sha256"]) == 64
    assert summary["placement_validation"]["validated"] is True
    assert summary["invariants"]["physical_dose_values_preserved"] is True


def test_bound_tally_geometry_mismatch_fails_before_output(tmp_path: Path) -> None:
    source_path = tmp_path / "raw.dcm"
    output_path = tmp_path / "fixed.dcm"
    tally_path = tmp_path / "dose.out"
    write_rtdose(source_path)
    write_tally_geometry(tally_path)
    placement = derive_rtdose_placement(
        parse_tally_mesh_geometry(tally_path),
        rtplan_isocenter_dicom_mm=[10.0, -20.0, 30.0],
    )
    placement["output_shape_frames_rows_columns"] = [2, 3, 5]

    with pytest.raises(ValueError, match="dimensions do not match"):
        fix_coordinates(
            source_path,
            output_path,
            expected_placement=placement,
        )

    assert not output_path.exists()
