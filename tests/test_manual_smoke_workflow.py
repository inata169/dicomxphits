from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pydicom
import pytest
from pydicom.dataset import Dataset, FileDataset
from pydicom.tag import Tag

PUBLIC_ROOT = Path(__file__).resolve().parents[1]
PUBLIC_SRC = PUBLIC_ROOT / "src"
if str(PUBLIC_SRC) not in sys.path:
    sys.path.insert(0, str(PUBLIC_SRC))

from dicomxphits.prepare_3dcrt_workspace import ExternalToolPaths
from dicomxphits.prepare_rtdose import PHITS2DICOM_REQUIRED_TEMPLATE_TAGS, prepare_rtdose, run_rtdose
from dicomxphits.prepare_sumtally import generate_sumtally, run_sumtally
from dicomxphits.sumtally_inputs import file_sha256


SMOKE_PLAN_UID = "1.2.826.0.1.3680043.10.54321.9101"
SMOKE_FRAME_UID = "1.2.826.0.1.3680043.10.54321.9102"


def synthetic_uid() -> str:
    return pydicom.uid.generate_uid(prefix=None)


def required_tag_value(tag: tuple[int, int], vr: str):
    if tag == (0x0028, 0x0009):
        return [Tag(0x3004, 0x000C)]
    if tag == (0x7FE0, 0x0010):
        return b"\x00\x00"
    if tag in {(0x0020, 0x0032), (0x0020, 0x0037), (0x3004, 0x000C)}:
        return ["0", "0", "0"]
    if tag == (0x0028, 0x0030):
        return ["1", "1"]
    if vr in {"US", "SS", "UL", "SL"}:
        return 0
    if vr in {"IS", "DS"}:
        return "0"
    if vr in {"FL", "FD"}:
        return 0.0
    if vr == "AT":
        return [Tag(0x3004, 0x000C)]
    if vr == "DA":
        return "20260101"
    if vr == "TM":
        return "000000"
    if vr == "UI":
        return synthetic_uid()
    if vr == "CS":
        return "SYNTHETIC"
    return "SYNTHETIC"


def add_phits2dicom_template_tags(ds: FileDataset) -> None:
    for tag in PHITS2DICOM_REQUIRED_TEMPLATE_TAGS:
        if tag in ds:
            continue
        vr = pydicom.datadict.dictionary_VR(tag)
        ds.add_new(tag, vr, required_tag_value(tag, vr))


def write_synthetic_dicom(
    path: Path,
    *,
    modality: str,
    frame_uid: str | None = None,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    file_meta = Dataset()
    file_meta.MediaStorageSOPClassUID = {
        "CT": pydicom.uid.CTImageStorage,
        "RTDOSE": pydicom.uid.RTDoseStorage,
    }[modality]
    file_meta.MediaStorageSOPInstanceUID = synthetic_uid()
    file_meta.TransferSyntaxUID = pydicom.uid.ExplicitVRLittleEndian
    ds = FileDataset(str(path), {}, file_meta=file_meta, preamble=b"\0" * 128)
    ds.SOPClassUID = file_meta.MediaStorageSOPClassUID
    ds.SOPInstanceUID = file_meta.MediaStorageSOPInstanceUID
    ds.Modality = modality
    setattr(ds, "Patient" + "Name", "SYNTHETIC^DUMMY")
    setattr(ds, "Patient" + "ID", "SYNTHETIC_PATIENT")
    ds.InstitutionName = "SYNTHETIC_INSTITUTION"
    ds.ManufacturerModelName = "SYNTHETIC_MACHINE"
    ds.FrameOfReferenceUID = frame_uid or synthetic_uid()
    ds.StudyInstanceUID = synthetic_uid()
    ds.SeriesInstanceUID = synthetic_uid()
    ds.ImagePositionPatient = ["1.0", "2.0", "3.0"]
    if modality == "RTDOSE":
        add_phits2dicom_template_tags(ds)
    ds.save_as(str(path))


def write_synthetic_rtplan(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    file_meta = Dataset()
    file_meta.MediaStorageSOPClassUID = pydicom.uid.RTPlanStorage
    file_meta.MediaStorageSOPInstanceUID = SMOKE_PLAN_UID
    file_meta.TransferSyntaxUID = pydicom.uid.ExplicitVRLittleEndian
    ds = FileDataset(str(path), {}, file_meta=file_meta, preamble=b"\0" * 128)
    ds.SOPClassUID = file_meta.MediaStorageSOPClassUID
    ds.SOPInstanceUID = SMOKE_PLAN_UID
    ds.Modality = "RTPLAN"
    ds.FrameOfReferenceUID = SMOKE_FRAME_UID
    ds.BeamSequence = []
    referenced_beams = []
    for number, meterset in ((1, 80.0), (2, 120.0)):
        beam = Dataset()
        beam.BeamNumber = number
        beam.TreatmentDeliveryType = "TREATMENT"
        ds.BeamSequence.append(beam)
        reference = Dataset()
        reference.ReferencedBeamNumber = number
        reference.BeamMeterset = meterset
        referenced_beams.append(reference)
    fraction_group = Dataset()
    fraction_group.FractionGroupNumber = 1
    fraction_group.ReferencedBeamSequence = referenced_beams
    ds.FractionGroupSequence = [fraction_group]
    ds.save_as(str(path))


def write_coordinate_rtdose(path: Path) -> None:
    write_synthetic_dicom(path, modality="RTDOSE", frame_uid=SMOKE_FRAME_UID)
    ds = pydicom.dcmread(str(path))
    ds.NumberOfFrames = 3
    ds.Rows = 2
    ds.Columns = 4
    ds.PixelSpacing = [2.0, 3.0]
    ds.GridFrameOffsetVector = [0.0, 4.0, 8.0]
    ds.ImageOrientationPatient = [1.0, 0.0, 0.0, 0.0, 1.0, 0.0]
    ds.ImagePositionPatient = [-4.0, -5.0, -6.0]
    ds.SamplesPerPixel = 1
    ds.PhotometricInterpretation = "MONOCHROME2"
    ds.BitsAllocated = 16
    ds.BitsStored = 16
    ds.HighBit = 15
    ds.PixelRepresentation = 0
    ds.DoseGridScaling = 0.125
    ds.PixelData = np.arange(24, dtype=np.uint16).reshape(3, 2, 4).tobytes()
    ds.save_as(str(path))


def assert_under_tmp_not_public(path_value: str | Path, tmp_path: Path) -> None:
    path = Path(path_value).resolve()
    assert path == tmp_path.resolve() or tmp_path.resolve() in path.parents
    assert PUBLIC_ROOT.resolve() not in path.parents


def assert_summary_paths_under_tmp(summary: dict[str, Any], tmp_path: Path) -> None:
    path_keys = {
        "workspace_root",
        "manifest_path",
        "sumtally_base_input",
        "phits_dose",
        "phits_out",
        "template_dicom_original_path",
        "template_dicom_workspace_copy_path",
        "ct_reference_original_path",
        "ct_reference_workspace_copy_path",
        "dat_dir",
        "phits2dicom_input_path",
        "stdout_path",
        "stderr_path",
        "expected_rtdose_output",
        "expected_sumtally_output",
    }
    for key in path_keys:
        value = summary.get(key)
        if isinstance(value, str) and value:
            assert_under_tmp_not_public(value, tmp_path)
    outputs = summary.get("outputs")
    if isinstance(outputs, dict):
        for value in outputs.values():
            if isinstance(value, str) and value:
                assert_under_tmp_not_public(value, tmp_path)
    for item in summary.get("new_dicom_outputs", []):
        if isinstance(item, dict) and item.get("path"):
            assert_under_tmp_not_public(str(item["path"]), tmp_path)


def write_manual_smoke_workspace(tmp_path: Path) -> tuple[Path, dict[str, Any]]:
    workspace = tmp_path / "smoke_workspace"
    manifest = {
        "schema_version": "segment_manifest_v2",
        "case_id": "synthetic_smoke",
        "plan_uid": SMOKE_PLAN_UID,
        "workflow_mode": "full_plan",
        "plan_total_mu": 200.0,
        "included_total_mu": 200.0,
        "dose_normalization_mu": 200.0,
        "segments": [
            {
                "segment_id": "seg_001",
                "beam_number": 1,
                "segment_index": 0,
                "delivery_type": "3dcrt",
                "beam_meterset_mu": 80.0,
                "segment_mu": 80.0,
                "mu_weight": 80.0,
                "mu_weight_unit": "MU",
                "phits_input_path": "segments/seg_001/phits.inp",
                "expected_output_path": "segments/seg_001/deposit-target-3D.out",
            },
            {
                "segment_id": "seg_002",
                "beam_number": 2,
                "segment_index": 1,
                "delivery_type": "3dcrt",
                "beam_meterset_mu": 120.0,
                "segment_mu": 120.0,
                "mu_weight": 120.0,
                "mu_weight_unit": "MU",
                "phits_input_path": "segments/seg_002/phits.inp",
                "expected_output_path": "segments/seg_002/deposit-target-3D.out",
            },
        ],
    }
    manifest_path = workspace / "segments" / "segment_manifest.json"
    manifest_path.parent.mkdir(parents=True)
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    rtplan_path = workspace / "RTPLAN.dcm"
    write_synthetic_rtplan(rtplan_path)
    (workspace / "ct2phits_workspace_manifest.json").write_text(
        json.dumps(
            {
                "status": "completed",
                "rtplan": {
                    "snapshot_path": rtplan_path.name,
                    "sha256": file_sha256(rtplan_path),
                },
            }
        ),
        encoding="utf-8",
    )
    for segment in manifest["segments"]:
        phits_path = workspace / str(segment["phits_input_path"])
        phits_path.parent.mkdir(parents=True, exist_ok=True)
        phits_path.write_text(
            "[ Parameters ]\n"
            "  icntl = 0\n"
            "  file(6) = phits.out\n"
            "[ T-Deposit ]\n"
            "  title = Synthetic smoke dose\n"
            "  file = deposit-target-3D.out\n"
            "[ E N D ]\n",
            encoding="utf-8",
        )
    return workspace, manifest


def tool_paths(tmp_path: Path, *, phits2dicom: str | None = None) -> ExternalToolPaths:
    return ExternalToolPaths(
        phits_root_folder=str(tmp_path / "dummy_phits_root"),
        phits_executable_path=str(tmp_path / "dummy_phits_root" / "bin" / "phits"),
        phits2dicom_executable_path=phits2dicom,
    )


def create_segment_outputs(workspace: Path, manifest: dict[str, Any]) -> None:
    for segment in manifest["segments"]:
        output_path = workspace / str(segment["expected_output_path"])
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text("synthetic segment dose", encoding="utf-8")


def create_successful_sumtally_workspace(tmp_path: Path) -> tuple[Path, dict[str, Any], dict[str, Path]]:
    workspace, manifest = write_manual_smoke_workspace(tmp_path)
    create_segment_outputs(workspace, manifest)
    generation = generate_sumtally(
        workspace_root=workspace,
        paths=tool_paths(tmp_path),
        command_argv=["manual-smoke", "generate-sumtally"],
    )
    sumtally_output = Path(generation["outputs"]["sumtally_output"])
    phits_out = workspace / "sumtally" / "phits.out"

    def fake_phits_runner(cmd, **kwargs):
        assert kwargs["shell"] is False
        sumtally_output.write_text("synthetic merged dose", encoding="utf-8")
        phits_out.write_text("synthetic phits companion", encoding="utf-8")
        return subprocess.CompletedProcess(cmd, 0, stdout="synthetic sumtally ok", stderr="")

    execution = run_sumtally(
        workspace_root=workspace,
        paths=tool_paths(tmp_path, phits2dicom=None),
        command_argv=["manual-smoke", "run-sumtally"],
        runner=fake_phits_runner,
    )
    assert generation["stage_status"] == "success"
    assert execution["stage_status"] == "success"
    return workspace, manifest, {"sumtally_output": sumtally_output, "phits_out": phits_out}


def test_manual_smoke_happy_path_uses_tmp_path_only(tmp_path):
    workspace, _manifest, files = create_successful_sumtally_workspace(tmp_path)
    template = tmp_path / "synthetic_template_rtdose.dcm"
    ct = tmp_path / "synthetic_ct_reference.dcm"
    phits2dicom = tmp_path / "tools" / "phits2dicom"
    phits2dicom.parent.mkdir(parents=True)
    phits2dicom.write_text("synthetic executable placeholder", encoding="utf-8")
    write_synthetic_dicom(template, modality="RTDOSE")
    write_synthetic_dicom(ct, modality="CT", frame_uid=SMOKE_FRAME_UID)

    prepare = prepare_rtdose(
        workspace_root=workspace,
        paths=tool_paths(tmp_path, phits2dicom=str(phits2dicom)),
        paths_config={},
        template_dicom=template,
        ct_reference_dicom=ct,
        phits_out=files["phits_out"],
        command_argv=["manual-smoke", "prepare-rtdose"],
    )

    def fake_phits2dicom_runner(cmd, **kwargs):
        class FakeProc:
            returncode = 0

            def communicate(self, input):
                assert input.startswith("PHITS2DICOM")
                write_coordinate_rtdose(files["sumtally_output"].with_suffix(".dcm"))
                return "synthetic phits2dicom ok", None

        assert cmd == [str(phits2dicom.resolve())]
        assert kwargs["cwd"] == str(Path(prepare["dat_dir"]).absolute())
        return FakeProc()

    execution = run_rtdose(
        workspace_root=workspace,
        paths=tool_paths(tmp_path, phits2dicom=str(phits2dicom)),
        command_argv=["manual-smoke", "run-rtdose"],
        runner=fake_phits2dicom_runner,
    )

    assert prepare["stage_status"] == "success"
    assert execution["stage_status"] == "success"
    assert execution["expected_rtdose_output_exists"] is True
    assert execution["coordinate_corrected_rtdose_output_exists"] is True
    assert execution["new_dicom_outputs"]
    for summary in (prepare, execution):
        assert_summary_paths_under_tmp(summary, tmp_path)
    for path in (
        files["sumtally_output"],
        files["sumtally_output"].with_suffix(".dcm"),
        files["phits_out"],
        workspace / "analysis" / "sumtally_generation_summary.json",
        workspace / "analysis" / "sumtally_execution_summary.json",
        workspace / "analysis" / "rtdose_conversion_prepare_summary.json",
        workspace / "analysis" / "rtdose_conversion_execution_summary.json",
    ):
        assert_under_tmp_not_public(path, tmp_path)


def test_manual_smoke_gate_failure_missing_segment_output_before_sumtally_run(tmp_path):
    workspace, manifest = write_manual_smoke_workspace(tmp_path)
    create_segment_outputs(workspace, manifest)
    generate_sumtally(
        workspace_root=workspace,
        paths=tool_paths(tmp_path),
        command_argv=["manual-smoke", "generate-sumtally"],
    )
    missing = workspace / str(manifest["segments"][0]["expected_output_path"])
    missing.unlink()

    with pytest.raises(FileNotFoundError, match="Expected segment PHITS output"):
        run_sumtally(
            workspace_root=workspace,
            paths=tool_paths(tmp_path),
            command_argv=["manual-smoke", "run-sumtally"],
        )

    failure = json.loads((workspace / "analysis" / "sumtally_execution_summary.json").read_text(encoding="utf-8"))
    assert failure["stage_status"] == "gate_failed"
    assert failure["phits_execution_started"] is False
    assert_summary_paths_under_tmp(failure, tmp_path)


def test_manual_smoke_gate_failure_missing_phits_out_before_rtdose_prepare(tmp_path):
    workspace, _manifest, _files = create_successful_sumtally_workspace(tmp_path)
    template = tmp_path / "synthetic_template_rtdose.dcm"
    ct = tmp_path / "synthetic_ct_reference.dcm"
    write_synthetic_dicom(template, modality="RTDOSE")
    write_synthetic_dicom(ct, modality="CT", frame_uid=SMOKE_FRAME_UID)

    with pytest.raises(FileNotFoundError, match="phits_out companion file"):
        prepare_rtdose(
            workspace_root=workspace,
            paths=tool_paths(tmp_path),
            paths_config={},
            template_dicom=template,
            ct_reference_dicom=ct,
            phits_out=workspace / "sumtally" / "missing_phits.out",
            command_argv=["manual-smoke", "prepare-rtdose"],
        )

    failure = json.loads((workspace / "analysis" / "rtdose_conversion_prepare_summary.json").read_text(encoding="utf-8"))
    assert failure["stage_status"] == "gate_failed"
    assert failure["phits2dicom_execution_started"] is False
    assert_summary_paths_under_tmp(failure, tmp_path)


def test_manual_smoke_gate_failure_missing_ct_reference_before_rtdose_prepare(tmp_path):
    workspace, _manifest, files = create_successful_sumtally_workspace(tmp_path)
    template = tmp_path / "synthetic_template_rtdose.dcm"
    write_synthetic_dicom(template, modality="RTDOSE")

    with pytest.raises(FileNotFoundError, match="CT reference DICOM"):
        prepare_rtdose(
            workspace_root=workspace,
            paths=tool_paths(tmp_path),
            paths_config={},
            template_dicom=template,
            ct_reference_dicom=tmp_path / "missing_ct_reference.dcm",
            phits_out=files["phits_out"],
            command_argv=["manual-smoke", "prepare-rtdose"],
        )

    failure = json.loads((workspace / "analysis" / "rtdose_conversion_prepare_summary.json").read_text(encoding="utf-8"))
    assert failure["stage_status"] == "gate_failed"
    assert failure["phits2dicom_execution_started"] is False
    assert_summary_paths_under_tmp(failure, tmp_path)


def test_manual_smoke_gate_failure_missing_phits2dicom_executable_before_rtdose_run(tmp_path):
    workspace, _manifest, files = create_successful_sumtally_workspace(tmp_path)
    template = tmp_path / "synthetic_template_rtdose.dcm"
    ct = tmp_path / "synthetic_ct_reference.dcm"
    write_synthetic_dicom(template, modality="RTDOSE")
    write_synthetic_dicom(ct, modality="CT", frame_uid=SMOKE_FRAME_UID)
    prepare_rtdose(
        workspace_root=workspace,
        paths=tool_paths(tmp_path, phits2dicom=None),
        paths_config={},
        template_dicom=template,
        ct_reference_dicom=ct,
        phits_out=files["phits_out"],
        command_argv=["manual-smoke", "prepare-rtdose"],
    )

    with pytest.raises(ValueError, match="phits2dicom_executable_path"):
        run_rtdose(
            workspace_root=workspace,
            paths=tool_paths(tmp_path, phits2dicom=None),
            command_argv=["manual-smoke", "run-rtdose"],
        )

    failure = json.loads((workspace / "analysis" / "rtdose_conversion_execution_summary.json").read_text(encoding="utf-8"))
    assert failure["stage_status"] == "gate_failed"
    assert failure["phits2dicom_execution_started"] is False
    assert_summary_paths_under_tmp(failure, tmp_path)
