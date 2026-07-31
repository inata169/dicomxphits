from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pydicom
from pydicom.dataset import Dataset, FileDataset

from dicomxphits.run_gpr_compare import run_adapter


def write_rtdose(path: Path, *, frame_uid: str = "1.2.3") -> None:
    file_meta = Dataset()
    file_meta.MediaStorageSOPClassUID = "1.2.840.10008.5.1.4.1.1.481.2"
    file_meta.MediaStorageSOPInstanceUID = pydicom.uid.generate_uid(prefix=None)
    file_meta.TransferSyntaxUID = pydicom.uid.ExplicitVRLittleEndian
    dataset = FileDataset(str(path), {}, file_meta=file_meta, preamble=b"\0" * 128)
    dataset.SOPClassUID = file_meta.MediaStorageSOPClassUID
    dataset.SOPInstanceUID = file_meta.MediaStorageSOPInstanceUID
    dataset.Modality = "RTDOSE"
    dataset.DoseUnits = "GY"
    dataset.FrameOfReferenceUID = frame_uid
    dataset.save_as(str(path))


def write_gpr_root(path: Path) -> None:
    entrypoint = path / "rtgamma" / "main.py"
    entrypoint.parent.mkdir(parents=True)
    entrypoint.write_text("# synthetic external entrypoint\n", encoding="utf-8")


def test_missing_external_tool_records_explicit_skip(tmp_path: Path) -> None:
    summary = run_adapter(
        reference_rtdose=tmp_path / "reference.dcm",
        evaluation_rtdose=tmp_path / "evaluation.fixed.dcm",
        output_dir=tmp_path / "gpr",
        gpr_root=None,
    )

    assert summary["status"] == "skipped"
    assert summary["gpr_comparing_available"] is False
    assert summary["gpr_comparing_executed"] is False
    assert "not configured" in summary["skip_reason"]


def test_configured_boundary_builds_external_command_without_execution(
    tmp_path: Path,
) -> None:
    gpr_root = tmp_path / "GPR-comparing"
    write_gpr_root(gpr_root)

    summary = run_adapter(
        reference_rtdose=tmp_path / "reference.dcm",
        evaluation_rtdose=tmp_path / "evaluation.fixed.dcm",
        output_dir=tmp_path / "gpr",
        gpr_root=gpr_root,
        python_executable=sys.executable,
    )

    assert summary["status"] == "configured_only"
    assert summary["gpr_comparing_available"] is True
    assert summary["gpr_comparing_executed"] is False
    assert summary["command"][1:3] == ["-m", "rtgamma.main"]
    assert summary["gamma_criteria"]["dd_percent"] == 3.0
    assert summary["gamma_criteria"]["dta_mm"] == 2.0


def test_execute_requires_matching_frame_and_fresh_report(tmp_path: Path) -> None:
    reference = tmp_path / "reference.dcm"
    evaluation = tmp_path / "evaluation.fixed.dcm"
    output_dir = tmp_path / "gpr"
    gpr_root = tmp_path / "GPR-comparing"
    write_rtdose(reference)
    write_rtdose(evaluation)
    write_gpr_root(gpr_root)

    def fake_runner(command, **kwargs):
        assert kwargs["cwd"] == str(gpr_root.resolve())
        assert command[1:3] == ["-m", "rtgamma.main"]
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "run3d.json").write_text(
            json.dumps({"pass_rate_percent": 98.25}) + "\n",
            encoding="utf-8",
        )
        return subprocess.CompletedProcess(command, 0, stdout="ok", stderr="")

    summary = run_adapter(
        reference_rtdose=reference,
        evaluation_rtdose=evaluation,
        output_dir=output_dir,
        gpr_root=gpr_root,
        execute=True,
        python_executable=sys.executable,
        runner=fake_runner,
    )

    assert summary["status"] == "completed", summary["failure_reason"]
    assert summary["gpr_comparing_executed"] is True
    assert summary["pass_rate_percent"] == 98.25
    assert summary["report_artifact"]["exists"] is True


def test_frame_mismatch_fails_before_external_execution(tmp_path: Path) -> None:
    reference = tmp_path / "reference.dcm"
    evaluation = tmp_path / "evaluation.fixed.dcm"
    gpr_root = tmp_path / "GPR-comparing"
    write_rtdose(reference, frame_uid="1.2.3")
    write_rtdose(evaluation, frame_uid="1.2.4")
    write_gpr_root(gpr_root)
    called = False

    def unexpected_runner(*args, **kwargs):
        nonlocal called
        called = True
        raise AssertionError("external GPR runner must not start")

    summary = run_adapter(
        reference_rtdose=reference,
        evaluation_rtdose=evaluation,
        output_dir=tmp_path / "gpr",
        gpr_root=gpr_root,
        execute=True,
        python_executable=sys.executable,
        runner=unexpected_runner,
    )

    assert summary["status"] == "failed"
    assert "FrameOfReferenceUID mismatch" in summary["failure_reason"]
    assert called is False
