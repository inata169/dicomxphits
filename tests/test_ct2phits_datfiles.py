from __future__ import annotations

import hashlib
import sys
from pathlib import Path

import pydicom
import pytest
from pydicom.dataset import Dataset, FileDataset

PUBLIC_SRC = Path(__file__).resolve().parents[1] / "src"
if str(PUBLIC_SRC) not in sys.path:
    sys.path.insert(0, str(PUBLIC_SRC))

import dicomxphits.ct2phits_datfiles as ct2phits_datfiles_module
from dicomxphits.ct2phits_datfiles import (
    Ct2PhitsDatfilesError,
    RAW_CT2PHITS_NAMES,
    prepare_ct2phits_assets,
)


def _uid() -> str:
    return pydicom.uid.generate_uid(prefix=None)


def _dataset(path: Path, *, modality: str, sop_class_uid: str) -> FileDataset:
    file_meta = Dataset()
    file_meta.MediaStorageSOPClassUID = sop_class_uid
    file_meta.MediaStorageSOPInstanceUID = _uid()
    file_meta.TransferSyntaxUID = pydicom.uid.ExplicitVRLittleEndian
    dataset = FileDataset(
        str(path),
        {},
        file_meta=file_meta,
        preamble=b"\0" * 128,
    )
    dataset.SOPClassUID = sop_class_uid
    dataset.SOPInstanceUID = file_meta.MediaStorageSOPInstanceUID
    dataset.Modality = modality
    return dataset


def _write_ct_series(
    root: Path,
    *,
    frame_uid: str,
    series_uid: str,
    orientation=(1, 0, 0, 0, 1, 0),
    patient_position: str = "HFS",
) -> Path:
    root.mkdir()
    paths: list[Path] = []
    for index, position in enumerate(
        ((-255.5, -255.5, -100.0), (-255.5, -255.5, -175.0)),
        start=1,
    ):
        path = root / f"CT.{index}.dcm"
        dataset = _dataset(
            path,
            modality="CT",
            sop_class_uid=pydicom.uid.CTImageStorage,
        )
        dataset.FrameOfReferenceUID = frame_uid
        dataset.SeriesInstanceUID = series_uid
        dataset.StudyInstanceUID = _uid()
        dataset.PatientPosition = patient_position
        dataset.ImageOrientationPatient = list(orientation)
        dataset.ImagePositionPatient = list(position)
        dataset.save_as(str(path))
        paths.append(path)
    return paths[0]


def _write_rtplan(
    path: Path,
    *,
    frame_uid: str,
    isocenters=((10.0, 20.0, 30.0),),
) -> Path:
    dataset = _dataset(
        path,
        modality="RTPLAN",
        sop_class_uid=pydicom.uid.RTPlanStorage,
    )
    referenced_frame = Dataset()
    referenced_frame.FrameOfReferenceUID = frame_uid
    dataset.ReferencedFrameOfReferenceSequence = [referenced_frame]
    beams = []
    referenced_beams = []
    for number, isocenter in enumerate(isocenters, start=1):
        beam = Dataset()
        beam.BeamNumber = number
        control_point = Dataset()
        control_point.ControlPointIndex = 0
        control_point.IsocenterPosition = list(isocenter)
        beam.ControlPointSequence = [control_point]
        beams.append(beam)
        referenced_beam = Dataset()
        referenced_beam.ReferencedBeamNumber = number
        referenced_beams.append(referenced_beam)
    dataset.BeamSequence = beams
    fraction_group = Dataset()
    fraction_group.ReferencedBeamSequence = referenced_beams
    dataset.FractionGroupSequence = [fraction_group]
    dataset.save_as(str(path))
    return path


def _write_raw_datfiles(root: Path) -> Path:
    root.mkdir()
    for name in RAW_CT2PHITS_NAMES:
        text = f"$ synthetic {name}\n"
        if name == "CTusrparam.dat":
            text = (
                "set: c81[512]\n"
                "set: c82[512]\n"
                "set: c83[71]\n"
                "set: c84[0.1]\n"
                "set: c85[0.1]\n"
                "set: c86[0.5]\n"
                "set: c91[-25.55] $ raw x\n"
                "set: c92[-25.55] $ raw y\n"
                "set: c93[-17.50] $ raw z\n"
            )
        (root / name).write_text(text, encoding="utf-8")
    return root


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.mark.parametrize(
    ("value", "expected"),
    [(1, 1), ("1", 1), (1.0, 1), ("-2", -2)],
)
def test_integral_beam_number_values_are_preserved(value, expected: int) -> None:
    assert (
        ct2phits_datfiles_module._require_integral_beam_number(
            value,
            label="RTPLAN BeamNumber",
        )
        == expected
    )


@pytest.mark.parametrize(
    "value",
    [1.5, "1.5", float("nan"), float("inf"), float("-inf"), True, None, ""],
)
def test_non_integral_beam_number_values_are_rejected(value) -> None:
    with pytest.raises(
        Ct2PhitsDatfilesError,
        match="RTPLAN BeamNumber must be an integer",
    ):
        ct2phits_datfiles_module._require_integral_beam_number(
            value,
            label="RTPLAN BeamNumber",
        )


def test_raw_datfiles_are_prepared_from_ct_and_rtplan_without_mutating_source(
    tmp_path: Path,
) -> None:
    frame_uid = _uid()
    raw = _write_raw_datfiles(tmp_path / "DATfiles")
    reference = _write_ct_series(
        tmp_path / "CT",
        frame_uid=frame_uid,
        series_uid=_uid(),
    )
    rtplan = _write_rtplan(
        tmp_path / "RTPLAN.dcm",
        frame_uid=frame_uid,
    )
    before = {name: _sha256(raw / name) for name in RAW_CT2PHITS_NAMES}

    prepared = prepare_ct2phits_assets(
        raw_datfiles_root=raw,
        ct_reference_dicom=reference,
        rtplan_path=rtplan,
        output_root=tmp_path / "prepared",
        confirmed_non_patient_phantom=True,
    )

    assert prepared.ct_origin_dicom_cm == (-25.55, -25.55, -17.5)
    assert prepared.rtplan_isocenter_dicom_cm == (1.0, 2.0, 3.0)
    assert prepared.ct_shift_iec_cm == (26.55, -20.5, -27.55)
    assert prepared.ct_slice_count == 2
    assert prepared.assets.voxel_counts == (512, 512, 71)
    assert set(prepared.assets.files) == {
        "CTusrparam.dat",
        "CTtrans.inp",
        "CTsurf.dat",
        "CTmaterial.dat",
        "CTuniverse.inp",
        "CTvoxel.inp",
    }
    parameters = prepared.assets.files["CTusrparam.dat"].read_text(encoding="utf-8")
    assert "set: c91[26.55000]" in parameters
    assert "set: c92[-20.50000]" in parameters
    assert "set: c93[-27.55000]" in parameters
    transform = prepared.assets.files["CTtrans.inp"].read_text(encoding="utf-8")
    assert "tr500 c91 c92 c93" in transform
    assert "-1.00000   0.00000   0.00000" in transform
    assert (tmp_path / "prepared" / "CTuniverse.inp").read_bytes() == (
        raw / "CTuniverse.dat"
    ).read_bytes()
    assert (tmp_path / "prepared" / "CTvoxel.inp").read_bytes() == (
        raw / "CTvoxel.dat"
    ).read_bytes()
    assert {name: _sha256(raw / name) for name in RAW_CT2PHITS_NAMES} == before


def test_missing_raw_asset_fails_before_output_creation(tmp_path: Path) -> None:
    raw = _write_raw_datfiles(tmp_path / "DATfiles")
    (raw / "CTuniverse.dat").unlink()
    output = tmp_path / "prepared"

    with pytest.raises(
        Ct2PhitsDatfilesError,
        match="missing: CTuniverse.dat",
    ):
        prepare_ct2phits_assets(
            raw_datfiles_root=raw,
            ct_reference_dicom=tmp_path / "missing-ct.dcm",
            rtplan_path=tmp_path / "missing-plan.dcm",
            output_root=output,
            confirmed_non_patient_phantom=True,
        )

    assert not output.exists()


def test_frame_of_reference_mismatch_fails_before_output_creation(
    tmp_path: Path,
) -> None:
    raw = _write_raw_datfiles(tmp_path / "DATfiles")
    reference = _write_ct_series(
        tmp_path / "CT",
        frame_uid=_uid(),
        series_uid=_uid(),
    )
    rtplan = _write_rtplan(
        tmp_path / "RTPLAN.dcm",
        frame_uid=_uid(),
    )
    output = tmp_path / "prepared"

    with pytest.raises(Ct2PhitsDatfilesError, match="do not match"):
        prepare_ct2phits_assets(
            raw_datfiles_root=raw,
            ct_reference_dicom=reference,
            rtplan_path=rtplan,
            output_root=output,
            confirmed_non_patient_phantom=True,
        )

    assert not output.exists()


@pytest.mark.parametrize(
    ("orientation", "patient_position", "message"),
    [
        ((0, 1, 0, 1, 0, 0), "HFS", "axial HFS orientation"),
        ((1, 0, 0, 0, 1, 0), "FFS", "PatientPosition must be HFS"),
    ],
)
def test_unsupported_ct_orientation_fails_closed(
    tmp_path: Path,
    orientation,
    patient_position,
    message,
) -> None:
    frame_uid = _uid()
    raw = _write_raw_datfiles(tmp_path / "DATfiles")
    reference = _write_ct_series(
        tmp_path / "CT",
        frame_uid=frame_uid,
        series_uid=_uid(),
        orientation=orientation,
        patient_position=patient_position,
    )
    rtplan = _write_rtplan(
        tmp_path / "RTPLAN.dcm",
        frame_uid=frame_uid,
    )

    with pytest.raises(Ct2PhitsDatfilesError, match=message):
        prepare_ct2phits_assets(
            raw_datfiles_root=raw,
            ct_reference_dicom=reference,
            rtplan_path=rtplan,
            output_root=tmp_path / "prepared",
            confirmed_non_patient_phantom=True,
        )


def test_referenced_beams_must_share_one_isocenter(tmp_path: Path) -> None:
    frame_uid = _uid()
    raw = _write_raw_datfiles(tmp_path / "DATfiles")
    reference = _write_ct_series(
        tmp_path / "CT",
        frame_uid=frame_uid,
        series_uid=_uid(),
    )
    rtplan = _write_rtplan(
        tmp_path / "RTPLAN.dcm",
        frame_uid=frame_uid,
        isocenters=((10.0, 20.0, 30.0), (10.0, 20.0, 31.0)),
    )

    with pytest.raises(Ct2PhitsDatfilesError, match="do not share one"):
        prepare_ct2phits_assets(
            raw_datfiles_root=raw,
            ct_reference_dicom=reference,
            rtplan_path=rtplan,
            output_root=tmp_path / "prepared",
            confirmed_non_patient_phantom=True,
        )
