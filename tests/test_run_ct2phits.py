from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pydicom
import pytest
from pydicom.dataset import Dataset, FileDataset

PUBLIC_SRC = Path(__file__).resolve().parents[1] / "src"
if str(PUBLIC_SRC) not in sys.path:
    sys.path.insert(0, str(PUBLIC_SRC))

import dicomxphits.run_ct2phits as run_ct2phits_module
from dicomxphits.run_ct2phits import (
    CT2PHITS_GENERATED_NAMES,
    Ct2PhitsFrontendError,
    run_ct2phits_frontend,
    select_ct_series,
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
    rows: int = 64,
    columns: int = 96,
    name_prefix: str = "CT",
    z_positions_mm: tuple[float, ...] = (-100.0, -50.0),
    pixel_spacing_mm: tuple[float, float] = (0.8, 0.8),
) -> tuple[Path, ...]:
    root.mkdir(exist_ok=True)
    paths: list[Path] = []
    for index, z_mm in enumerate(z_positions_mm, start=1):
        path = root / f"{name_prefix}.{index}.dcm"
        dataset = _dataset(
            path,
            modality="CT",
            sop_class_uid=pydicom.uid.CTImageStorage,
        )
        dataset.FrameOfReferenceUID = frame_uid
        dataset.SeriesInstanceUID = series_uid
        dataset.StudyInstanceUID = _uid()
        dataset.PatientPosition = "HFS"
        dataset.ImageOrientationPatient = [1, 0, 0, 0, 1, 0]
        dataset.ImagePositionPatient = [-120.0, -80.0, z_mm]
        dataset.PixelSpacing = list(pixel_spacing_mm)
        dataset.Rows = rows
        dataset.Columns = columns
        dataset.save_as(str(path))
        paths.append(path)
    return tuple(paths)


def _write_rtplan(path: Path, *, frame_uid: str) -> Path:
    dataset = _dataset(
        path,
        modality="RTPLAN",
        sop_class_uid=pydicom.uid.RTPlanStorage,
    )
    referenced_frame = Dataset()
    referenced_frame.FrameOfReferenceUID = frame_uid
    dataset.ReferencedFrameOfReferenceSequence = [referenced_frame]
    beam = Dataset()
    beam.BeamNumber = 1
    control_point = Dataset()
    control_point.ControlPointIndex = 0
    control_point.IsocenterPosition = [10.0, 20.0, 30.0]
    beam.ControlPointSequence = [control_point]
    dataset.BeamSequence = [beam]
    referenced_beam = Dataset()
    referenced_beam.ReferencedBeamNumber = 1
    fraction_group = Dataset()
    fraction_group.ReferencedBeamSequence = [referenced_beam]
    dataset.FractionGroupSequence = [fraction_group]
    dataset.save_as(str(path))
    return path


def _fake_rtphits_root(root: Path) -> Path:
    (root / "data").mkdir(parents=True)
    (root / "RTphits_win.bat").write_text(
        "synthetic fake runner marker\n",
        encoding="utf-8",
    )
    (root / "data" / "HumanVoxelTable.data").write_text(
        "synthetic fake table marker\n",
        encoding="utf-8",
    )
    return root


def _write_generated_datfiles(
    root: Path,
    *,
    missing: str | None = None,
    empty: str | None = None,
    old_mtime: bool = False,
) -> None:
    root.mkdir(exist_ok=True)
    for name in CT2PHITS_GENERATED_NAMES:
        if name == missing:
            continue
        content = f"$ synthetic {name}\n"
        if name == "CTusrparam.dat":
            content = (
                "set: c81[12]\n"
                "set: c82[8]\n"
                "set: c83[1]\n"
                "set: c84[0.8]\n"
                "set: c85[0.8]\n"
                "set: c86[1.0]\n"
                "set: c91[-12.0]\n"
                "set: c92[-8.0]\n"
                "set: c93[-10.0]\n"
            )
        path = root / name
        path.write_text("" if name == empty else content, encoding="utf-8")
        if old_mtime:
            old_ns = time.time_ns() - 10_000_000_000
            os.utime(path, ns=(old_ns, old_ns))


def _case(tmp_path: Path) -> dict[str, Path]:
    frame_uid = _uid()
    ct_root = tmp_path / "source_ct"
    _write_ct_series(
        ct_root,
        frame_uid=frame_uid,
        series_uid=_uid(),
    )
    return {
        "ct_root": ct_root,
        "rtplan": _write_rtplan(tmp_path / "RTPLAN.dcm", frame_uid=frame_uid),
        "rtphits": _fake_rtphits_root(tmp_path / "licensed_rtphits"),
        "workspace": tmp_path / "licensed_rtphits" / "work" / "case",
    }


def _success_runner(workspace: Path):
    def runner(command, cwd, timeout_seconds):
        assert Path(cwd).name == "licensed_rtphits"
        assert timeout_seconds == 12.0
        assert Path(command[4]).name == "RTphits_win.bat"
        assert Path(command[5]).name == "ct2phits.inp"
        _write_generated_datfiles(workspace / "DATfiles")
        return subprocess.CompletedProcess(command, 0, "synthetic stdout\n", "")

    return runner


def test_windows_frontend_generates_input_inventory_summary_and_handoff(
    tmp_path: Path,
) -> None:
    case = _case(tmp_path)

    result = run_ct2phits_frontend(
        ct_dicom_root=case["ct_root"],
        rtplan_path=case["rtplan"],
        rtphits_root=case["rtphits"],
        workspace_root=case["workspace"],
        confirmed_non_patient_phantom=True,
        timeout_seconds=12.0,
        runner=_success_runner(case["workspace"]),
        platform_system="Windows",
    )

    input_bytes = (case["workspace"] / "ct2phits.inp").read_bytes()
    assert b"\r" not in input_bytes
    assert input_bytes.decode("utf-8") == (
        "CT2PHITS input\n"
        '"data/HumanVoxelTable.data"\n'
        '"work/case/CT/"\n'
        '"work/case/DATfiles/"\n'
        "1 2\n"
        "1 96 1 64\n"
        "8 8 2\n"
        "1\n"
    )
    assert len(tuple((case["workspace"] / "CT").iterdir())) == 2
    assert result.ct_reference_dicom.name == "CT000001.dcm"
    assert (result.prepared_assets_root / "CTtrans.inp").is_file()
    assert not (result.prepared_assets_root / "CTtrans.dat").exists()
    transform = (result.prepared_assets_root / "CTtrans.inp").read_text(
        encoding="utf-8"
    )
    assert "-1.00000   0.00000   0.00000" in transform
    assert "0.00000   1.00000   0.00000" in transform

    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    assert manifest["status"] == "completed"
    assert manifest["ct_series"]["rows"] == 64
    assert manifest["ct_series"]["columns"] == 96
    assert len(manifest["generated_output_contract"]) == 9
    assert len(manifest["downstream_raw_datfiles_contract"]) == 8
    assert manifest["cttrans_contract"]["downstream_role"].startswith(
        "inventory_only"
    )

    summary = json.loads(result.summary_path.read_text(encoding="utf-8"))
    assert summary["status"] == "completed"
    assert summary["returncode"] == 0
    assert summary["pre_run_outputs_absent"] is True
    assert len(summary["generated_inventory"]) == 9
    assert len(summary["raw_datfiles_sha256"]) == 8
    assert len(summary["prepared_assets_sha256"]) == 6
    assert summary["workspace_preparation_handoff"]["validated_with"] == [
        "validate_raw_ct2phits_datfiles",
        "prepare_ct2phits_assets",
    ]
    assert (case["workspace"] / "logs" / "ct2phits.stdout.log").read_text(
        encoding="utf-8"
    ) == "synthetic stdout\n"


def test_non_windows_execution_is_rejected_before_workspace_creation(
    tmp_path: Path,
) -> None:
    case = _case(tmp_path)

    with pytest.raises(Ct2PhitsFrontendError, match="Windows only"):
        run_ct2phits_frontend(
            ct_dicom_root=case["ct_root"],
            rtplan_path=case["rtplan"],
            rtphits_root=case["rtphits"],
            workspace_root=case["workspace"],
            confirmed_non_patient_phantom=True,
            platform_system="Linux",
        )

    assert not case["workspace"].exists()


def test_missing_batch_is_rejected_before_workspace_creation(tmp_path: Path) -> None:
    case = _case(tmp_path)
    (case["rtphits"] / "RTphits_win.bat").unlink()

    with pytest.raises(Ct2PhitsFrontendError, match="batch file is missing"):
        run_ct2phits_frontend(
            ct_dicom_root=case["ct_root"],
            rtplan_path=case["rtplan"],
            rtphits_root=case["rtphits"],
            workspace_root=case["workspace"],
            confirmed_non_patient_phantom=True,
            platform_system="Windows",
        )

    assert not case["workspace"].exists()


def test_nonzero_return_code_is_recorded(tmp_path: Path) -> None:
    case = _case(tmp_path)

    def runner(command, cwd, timeout_seconds):
        return subprocess.CompletedProcess(command, 7, "partial\n", "failed\n")

    with pytest.raises(Ct2PhitsFrontendError, match="non-zero exit code 7"):
        run_ct2phits_frontend(
            ct_dicom_root=case["ct_root"],
            rtplan_path=case["rtplan"],
            rtphits_root=case["rtphits"],
            workspace_root=case["workspace"],
            confirmed_non_patient_phantom=True,
            runner=runner,
            platform_system="Windows",
        )

    summary = json.loads(
        (case["workspace"] / "ct2phits_execution_summary.json").read_text(
            encoding="utf-8"
        )
    )
    assert summary["status"] == "failed"
    assert summary["returncode"] == 7
    assert summary["timed_out"] is False


def test_timeout_is_recorded(tmp_path: Path) -> None:
    case = _case(tmp_path)

    def runner(command, cwd, timeout_seconds):
        raise subprocess.TimeoutExpired(command, timeout_seconds, output="partial")

    with pytest.raises(Ct2PhitsFrontendError, match="timed out"):
        run_ct2phits_frontend(
            ct_dicom_root=case["ct_root"],
            rtplan_path=case["rtplan"],
            rtphits_root=case["rtphits"],
            workspace_root=case["workspace"],
            confirmed_non_patient_phantom=True,
            timeout_seconds=0.5,
            runner=runner,
            platform_system="Windows",
        )

    summary = json.loads(
        (case["workspace"] / "ct2phits_execution_summary.json").read_text(
            encoding="utf-8"
        )
    )
    assert summary["timed_out"] is True
    assert summary["process_tree_termination_error"] is None
    assert summary["returncode"] is None


def test_timeout_termination_failure_preserves_logs_and_summary(
    tmp_path: Path,
) -> None:
    case = _case(tmp_path)

    def runner(command, cwd, timeout_seconds):
        raise run_ct2phits_module.Ct2PhitsProcessTimeout(
            command,
            timeout_seconds,
            output="partial output\n",
            stderr="partial error\n",
            termination_error="taskkill could not start: unavailable",
        )

    with pytest.raises(
        Ct2PhitsFrontendError,
        match="process-tree termination failed",
    ):
        run_ct2phits_frontend(
            ct_dicom_root=case["ct_root"],
            rtplan_path=case["rtplan"],
            rtphits_root=case["rtphits"],
            workspace_root=case["workspace"],
            confirmed_non_patient_phantom=True,
            timeout_seconds=0.5,
            runner=runner,
            platform_system="Windows",
        )

    summary = json.loads(
        (case["workspace"] / "ct2phits_execution_summary.json").read_text(
            encoding="utf-8"
        )
    )
    assert summary["timed_out"] is True
    assert summary["process_tree_termination_error"] == (
        "taskkill could not start: unavailable"
    )
    assert (case["workspace"] / "logs" / "ct2phits.stdout.log").read_text(
        encoding="utf-8"
    ) == "partial output\n"
    assert (case["workspace"] / "logs" / "ct2phits.stderr.log").read_text(
        encoding="utf-8"
    ) == "partial error\n"


@pytest.mark.skipif(os.name != "nt", reason="Windows process-tree behavior")
def test_default_runner_terminates_child_process_tree_on_timeout(
    tmp_path: Path,
) -> None:
    orphan_marker = tmp_path / "orphan.txt"
    child_code = (
        "import pathlib, sys, time; "
        "time.sleep(1.5); "
        "pathlib.Path(sys.argv[1]).write_text('orphan', encoding='utf-8')"
    )
    parent_code = (
        "import subprocess, sys, time; "
        "subprocess.Popen([sys.executable, '-c', sys.argv[1], sys.argv[2]]); "
        "print('parent started', flush=True); "
        "time.sleep(4)"
    )

    with pytest.raises(subprocess.TimeoutExpired) as timeout:
        run_ct2phits_module._default_runner(
            [sys.executable, "-c", parent_code, child_code, str(orphan_marker)],
            tmp_path,
            0.5,
        )

    assert "parent started" in str(timeout.value.stdout)
    time.sleep(1.5)
    assert not orphan_marker.exists()


@pytest.mark.parametrize(
    ("taskkill_failure", "expected_error"),
    [
        ("unavailable", "taskkill could not start"),
        ("timeout", "taskkill exceeded the process-tree termination timeout"),
        ("nonzero", "taskkill returned 5"),
    ],
)
def test_default_runner_preserves_output_when_taskkill_cleanup_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    taskkill_failure: str,
    expected_error: str,
) -> None:
    original_run = subprocess.run

    def failing_taskkill(command, *args, **kwargs):
        if Path(command[0]).name.lower() == "taskkill.exe":
            if taskkill_failure == "unavailable":
                raise FileNotFoundError("taskkill unavailable")
            if taskkill_failure == "timeout":
                raise subprocess.TimeoutExpired(command, kwargs["timeout"])
            return subprocess.CompletedProcess(command, 5, "", "access denied")
        return original_run(command, *args, **kwargs)

    monkeypatch.setattr(run_ct2phits_module.subprocess, "run", failing_taskkill)
    command = [
        sys.executable,
        "-c",
        "import os, time; os.write(1, b'partial output'); time.sleep(4)",
    ]

    with pytest.raises(run_ct2phits_module.Ct2PhitsProcessTimeout) as timeout:
        run_ct2phits_module._default_runner(command, tmp_path, 0.5)

    assert timeout.value.stdout == "partial output"
    assert expected_error in str(timeout.value.termination_error)


def test_default_runner_decodes_process_output_with_replacement(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(run_ct2phits_module.locale, "getencoding", lambda: "ascii")
    command = [
        sys.executable,
        "-c",
        "import os; os.write(1, b'out\\xff'); os.write(2, b'err\\xfe')",
    ]

    completed = run_ct2phits_module._default_runner(command, tmp_path, 5.0)

    assert completed.returncode == 0
    assert completed.stdout == "out\ufffd"
    assert completed.stderr == "err\ufffd"


@pytest.mark.parametrize(
    ("mode", "expected"),
    [
        ("missing", "generated files are missing"),
        ("empty", "generated files are empty"),
    ],
)
def test_invalid_generated_output_is_rejected_and_recorded(
    tmp_path: Path,
    mode: str,
    expected: str,
) -> None:
    case = _case(tmp_path)

    def runner(command, cwd, timeout_seconds):
        _write_generated_datfiles(
            case["workspace"] / "DATfiles",
            missing="CTtrans.dat" if mode == "missing" else None,
            empty="CTvoxel.dat" if mode == "empty" else None,
        )
        return subprocess.CompletedProcess(command, 0, "", "")

    with pytest.raises(Ct2PhitsFrontendError, match=expected):
        run_ct2phits_frontend(
            ct_dicom_root=case["ct_root"],
            rtplan_path=case["rtplan"],
            rtphits_root=case["rtphits"],
            workspace_root=case["workspace"],
            confirmed_non_patient_phantom=True,
            runner=runner,
            platform_system="Windows",
        )

    summary = json.loads(
        (case["workspace"] / "ct2phits_execution_summary.json").read_text(
            encoding="utf-8"
        )
    )
    assert summary["status"] == "failed"
    assert expected in summary["failure_reason"]


def test_generated_outputs_with_coarse_old_mtime_are_accepted(tmp_path: Path) -> None:
    case = _case(tmp_path)

    def runner(command, cwd, timeout_seconds):
        _write_generated_datfiles(
            case["workspace"] / "DATfiles",
            old_mtime=True,
        )
        return subprocess.CompletedProcess(command, 0, "", "")

    result = run_ct2phits_frontend(
        ct_dicom_root=case["ct_root"],
        rtplan_path=case["rtplan"],
        rtphits_root=case["rtphits"],
        workspace_root=case["workspace"],
        confirmed_non_patient_phantom=True,
        runner=runner,
        platform_system="Windows",
    )

    summary = json.loads(result.summary_path.read_text(encoding="utf-8"))
    assert summary["status"] == "completed"
    assert summary["pre_run_outputs_absent"] is True
    assert len(summary["generated_inventory"]) == 9


def test_preexisting_generated_output_is_rejected(tmp_path: Path) -> None:
    datfiles_root = tmp_path / "DATfiles"
    datfiles_root.mkdir()
    (datfiles_root / "CTtrans.dat").write_text("old\n", encoding="utf-8")

    with pytest.raises(Ct2PhitsFrontendError, match="absent before execution"):
        run_ct2phits_module._require_generated_outputs_absent(datfiles_root)


def test_existing_workspace_is_never_overwritten(tmp_path: Path) -> None:
    case = _case(tmp_path)
    case["workspace"].mkdir(parents=True)
    marker = case["workspace"] / "keep.txt"
    marker.write_text("user data\n", encoding="utf-8")

    with pytest.raises(Ct2PhitsFrontendError, match="already exists"):
        run_ct2phits_frontend(
            ct_dicom_root=case["ct_root"],
            rtplan_path=case["rtplan"],
            rtphits_root=case["rtphits"],
            workspace_root=case["workspace"],
            confirmed_non_patient_phantom=True,
            platform_system="Windows",
        )

    assert marker.read_text(encoding="utf-8") == "user data\n"


def test_workspace_with_cmd_metacharacter_is_rejected_before_creation(
    tmp_path: Path,
) -> None:
    case = _case(tmp_path)
    workspace = case["rtphits"] / "work" / "R&D" / "case"

    def runner(command, cwd, timeout_seconds):
        raise AssertionError("unsafe workspace path must reject before execution")

    with pytest.raises(Ct2PhitsFrontendError, match="cmd.exe metacharacters"):
        run_ct2phits_frontend(
            ct_dicom_root=case["ct_root"],
            rtplan_path=case["rtplan"],
            rtphits_root=case["rtphits"],
            workspace_root=workspace,
            confirmed_non_patient_phantom=True,
            runner=runner,
            platform_system="Windows",
        )

    assert not workspace.exists()


def test_repository_workspace_is_rejected_independently_of_installation_path(
    tmp_path: Path,
) -> None:
    case = _case(tmp_path)
    repository = tmp_path / "synthetic_checkout"
    repository.mkdir()
    (repository / "pyproject.toml").write_text(
        '[project]\nname = "dicomxphits"\n',
        encoding="utf-8",
    )
    (repository / "src" / "dicomxphits").mkdir(parents=True)
    rtphits = _fake_rtphits_root(repository / "licensed_rtphits")
    workspace = rtphits / "work" / "case"

    def runner(command, cwd, timeout_seconds):
        raise AssertionError("repository boundary must reject before execution")

    with pytest.raises(
        Ct2PhitsFrontendError,
        match="outside the dicomxphits repository",
    ):
        run_ct2phits_frontend(
            ct_dicom_root=case["ct_root"],
            rtplan_path=case["rtplan"],
            rtphits_root=rtphits,
            workspace_root=workspace,
            confirmed_non_patient_phantom=True,
            runner=runner,
            platform_system="Windows",
        )

    assert not workspace.exists()


def test_rtplan_snapshot_is_stable_during_external_execution(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    case = _case(tmp_path)
    original_prepare = run_ct2phits_module.prepare_ct2phits_assets
    prepared_rtplan_paths: list[Path] = []

    def recording_prepare(**kwargs):
        prepared_rtplan_paths.append(Path(kwargs["rtplan_path"]))
        return original_prepare(**kwargs)

    monkeypatch.setattr(
        run_ct2phits_module,
        "prepare_ct2phits_assets",
        recording_prepare,
    )

    def runner(command, cwd, timeout_seconds):
        changed = pydicom.dcmread(str(case["rtplan"]))
        changed.BeamSequence[0].ControlPointSequence[0].IsocenterPosition = [
            40.0,
            50.0,
            60.0,
        ]
        changed.save_as(str(case["rtplan"]))
        _write_generated_datfiles(case["workspace"] / "DATfiles")
        return subprocess.CompletedProcess(command, 0, "", "")

    result = run_ct2phits_frontend(
        ct_dicom_root=case["ct_root"],
        rtplan_path=case["rtplan"],
        rtphits_root=case["rtphits"],
        workspace_root=case["workspace"],
        confirmed_non_patient_phantom=True,
        runner=runner,
        platform_system="Windows",
    )

    snapshot = case["workspace"] / "RTPLAN.dcm"
    frozen = pydicom.dcmread(str(snapshot))
    assert list(
        frozen.BeamSequence[0].ControlPointSequence[0].IsocenterPosition
    ) == [10.0, 20.0, 30.0]
    assert prepared_rtplan_paths == [snapshot]
    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    assert manifest["rtplan"]["snapshot_path"] == "RTPLAN.dcm"
    assert manifest["rtplan"]["sha256"] == run_ct2phits_module._sha256(snapshot)
    assert manifest["rtplan"]["isocenter_dicom_cm"] == [1.0, 2.0, 3.0]


def test_rtplan_change_during_snapshot_is_rejected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    case = _case(tmp_path)
    original_copyfile = run_ct2phits_module.shutil.copyfile

    def mutating_copyfile(source, destination):
        if Path(source) == case["rtplan"].resolve():
            changed = pydicom.dcmread(str(source))
            changed.BeamSequence[0].ControlPointSequence[0].IsocenterPosition = [
                40.0,
                50.0,
                60.0,
            ]
            changed.save_as(str(source))
        return original_copyfile(source, destination)

    monkeypatch.setattr(
        run_ct2phits_module.shutil,
        "copyfile",
        mutating_copyfile,
    )

    def runner(command, cwd, timeout_seconds):
        raise AssertionError("unstable RT Plan must be rejected before execution")

    with pytest.raises(
        Ct2PhitsFrontendError,
        match="changed while creating the workspace snapshot",
    ):
        run_ct2phits_frontend(
            ct_dicom_root=case["ct_root"],
            rtplan_path=case["rtplan"],
            rtphits_root=case["rtphits"],
            workspace_root=case["workspace"],
            confirmed_non_patient_phantom=True,
            runner=runner,
            platform_system="Windows",
        )

    assert not case["workspace"].exists()


def test_rtplan_snapshot_copy_failure_is_controlled_and_workspace_is_removed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    case = _case(tmp_path)
    original_copyfile = run_ct2phits_module.shutil.copyfile

    def failing_copyfile(source, destination):
        if Path(source) == case["rtplan"].resolve():
            Path(destination).write_bytes(b"partial snapshot")
            raise PermissionError("synthetic copy failure")
        return original_copyfile(source, destination)

    monkeypatch.setattr(
        run_ct2phits_module.shutil,
        "copyfile",
        failing_copyfile,
    )

    def runner(command, cwd, timeout_seconds):
        raise AssertionError("failed snapshot copy must reject before execution")

    with pytest.raises(
        Ct2PhitsFrontendError,
        match="could not create RT Plan workspace snapshot",
    ):
        run_ct2phits_frontend(
            ct_dicom_root=case["ct_root"],
            rtplan_path=case["rtplan"],
            rtphits_root=case["rtphits"],
            workspace_root=case["workspace"],
            confirmed_non_patient_phantom=True,
            runner=runner,
            platform_system="Windows",
        )

    assert not case["workspace"].exists()


@pytest.mark.parametrize("snapshot_kind", ["rtplan", "ct"])
def test_workspace_input_snapshot_change_during_runner_is_rejected(
    tmp_path: Path,
    snapshot_kind: str,
) -> None:
    case = _case(tmp_path)

    def runner(command, cwd, timeout_seconds):
        if snapshot_kind == "rtplan":
            snapshot = case["workspace"] / "RTPLAN.dcm"
            dataset = pydicom.dcmread(str(snapshot))
            dataset.BeamSequence[0].ControlPointSequence[0].IsocenterPosition = [
                40.0,
                50.0,
                60.0,
            ]
        else:
            snapshot = case["workspace"] / "CT" / "CT000001.dcm"
            dataset = pydicom.dcmread(str(snapshot))
            dataset.ImagePositionPatient = [-119.0, -80.0, -50.0]
        dataset.save_as(str(snapshot))
        _write_generated_datfiles(case["workspace"] / "DATfiles")
        return subprocess.CompletedProcess(command, 0, "", "")

    with pytest.raises(
        Ct2PhitsFrontendError,
        match="workspace input snapshots changed after preparation",
    ):
        run_ct2phits_frontend(
            ct_dicom_root=case["ct_root"],
            rtplan_path=case["rtplan"],
            rtphits_root=case["rtphits"],
            workspace_root=case["workspace"],
            confirmed_non_patient_phantom=True,
            runner=runner,
            platform_system="Windows",
        )

    summary = json.loads(
        (case["workspace"] / "ct2phits_execution_summary.json").read_text(
            encoding="utf-8"
        )
    )
    manifest = json.loads(
        (case["workspace"] / "ct2phits_workspace_manifest.json").read_text(
            encoding="utf-8"
        )
    )
    assert summary["status"] == "failed"
    assert manifest["status"] == "failed"
    assert not (case["workspace"] / "prepared_ct_assets").exists()


@pytest.mark.parametrize("snapshot_kind", ["rtplan", "ct"])
def test_workspace_input_snapshot_change_during_handoff_is_rejected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    snapshot_kind: str,
) -> None:
    case = _case(tmp_path)
    original_prepare = run_ct2phits_module.prepare_ct2phits_assets

    def mutating_prepare(**kwargs):
        prepared = original_prepare(**kwargs)
        if snapshot_kind == "rtplan":
            snapshot = case["workspace"] / "RTPLAN.dcm"
            dataset = pydicom.dcmread(str(snapshot))
            dataset.BeamSequence[0].ControlPointSequence[0].IsocenterPosition = [
                40.0,
                50.0,
                60.0,
            ]
        else:
            snapshot = case["workspace"] / "CT" / "CT000001.dcm"
            dataset = pydicom.dcmread(str(snapshot))
            dataset.ImagePositionPatient = [-119.0, -80.0, -50.0]
        dataset.save_as(str(snapshot))
        return prepared

    monkeypatch.setattr(
        run_ct2phits_module,
        "prepare_ct2phits_assets",
        mutating_prepare,
    )

    with pytest.raises(
        Ct2PhitsFrontendError,
        match="workspace input snapshots changed after preparation",
    ):
        run_ct2phits_frontend(
            ct_dicom_root=case["ct_root"],
            rtplan_path=case["rtplan"],
            rtphits_root=case["rtphits"],
            workspace_root=case["workspace"],
            confirmed_non_patient_phantom=True,
            runner=_success_runner(case["workspace"]),
            platform_system="Windows",
            timeout_seconds=12.0,
        )

    summary = json.loads(
        (case["workspace"] / "ct2phits_execution_summary.json").read_text(
            encoding="utf-8"
        )
    )
    assert summary["status"] == "failed"
    assert summary["prepared_assets_sha256"] is None


def test_ct_change_during_snapshot_copy_is_rejected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    case = _case(tmp_path)
    ct_sources = sorted(case["ct_root"].glob("*.dcm"))
    changing_source = ct_sources[1].resolve()
    original_copyfile = run_ct2phits_module.shutil.copyfile

    def mutating_copyfile(source, destination):
        if Path(source) == changing_source:
            changed = pydicom.dcmread(str(source))
            changed.ImagePositionPatient = [-119.0, -80.0, -50.0]
            changed.save_as(str(source))
        return original_copyfile(source, destination)

    monkeypatch.setattr(
        run_ct2phits_module.shutil,
        "copyfile",
        mutating_copyfile,
    )

    def runner(command, cwd, timeout_seconds):
        raise AssertionError("unstable CT snapshot must be rejected before execution")

    with pytest.raises(
        Ct2PhitsFrontendError,
        match="changed while creating the workspace snapshot",
    ):
        run_ct2phits_frontend(
            ct_dicom_root=case["ct_root"],
            rtplan_path=case["rtplan"],
            rtphits_root=case["rtphits"],
            workspace_root=case["workspace"],
            confirmed_non_patient_phantom=True,
            runner=runner,
            platform_system="Windows",
        )


def test_copied_ct_series_is_revalidated_before_execution(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    case = _case(tmp_path)
    ct_sources = sorted(case["ct_root"].glob("*.dcm"))
    changing_source = ct_sources[1].resolve()
    original_sha256 = run_ct2phits_module._sha256
    changed_source = False

    def mutating_sha256(path: Path) -> str:
        nonlocal changed_source
        if Path(path) == changing_source and not changed_source:
            changed = pydicom.dcmread(str(path))
            changed.ImagePositionPatient = [-119.0, -80.0, -50.0]
            changed.save_as(str(path))
            changed_source = True
        return original_sha256(path)

    monkeypatch.setattr(run_ct2phits_module, "_sha256", mutating_sha256)

    def runner(command, cwd, timeout_seconds):
        raise AssertionError("changed CT geometry must be rejected before execution")

    with pytest.raises(
        Ct2PhitsFrontendError,
        match="inconsistent ImagePositionPatient X or Y values",
    ):
        run_ct2phits_frontend(
            ct_dicom_root=case["ct_root"],
            rtplan_path=case["rtplan"],
            rtphits_root=case["rtphits"],
            workspace_root=case["workspace"],
            confirmed_non_patient_phantom=True,
            runner=runner,
            platform_system="Windows",
        )


def test_multiple_ct_series_require_explicit_selection(tmp_path: Path) -> None:
    root = tmp_path / "ct"
    frame_uid = _uid()
    first_uid = _uid()
    second_uid = _uid()
    _write_ct_series(
        root,
        frame_uid=frame_uid,
        series_uid=first_uid,
        name_prefix="A",
    )
    _write_ct_series(
        root,
        frame_uid=frame_uid,
        series_uid=second_uid,
        name_prefix="B",
    )

    with pytest.raises(Ct2PhitsFrontendError, match="multiple CT DICOM series"):
        select_ct_series(root)

    selected = select_ct_series(root, series_instance_uid=second_uid)
    assert selected.series_instance_uid == second_uid
    assert len(selected.files) == 2


def test_unreadable_ct_dicom_candidate_is_rejected(tmp_path: Path) -> None:
    root = tmp_path / "ct"
    _write_ct_series(
        root,
        frame_uid=_uid(),
        series_uid=_uid(),
    )
    (root / "CT.corrupt.dcm").write_bytes(b"not a readable DICOM file")

    with pytest.raises(Ct2PhitsFrontendError, match="unreadable CT DICOM candidate"):
        select_ct_series(root)


def test_unrelated_non_dicom_file_is_ignored(tmp_path: Path) -> None:
    root = tmp_path / "ct"
    series_uid = _uid()
    _write_ct_series(
        root,
        frame_uid=_uid(),
        series_uid=series_uid,
    )
    (root / "notes.txt").write_text("not DICOM\n", encoding="utf-8")

    selected = select_ct_series(root)

    assert selected.series_instance_uid == series_uid
    assert len(selected.files) == 2


def test_in_plane_ct_slice_shift_is_rejected(tmp_path: Path) -> None:
    root = tmp_path / "ct"
    paths = _write_ct_series(
        root,
        frame_uid=_uid(),
        series_uid=_uid(),
    )
    shifted = pydicom.dcmread(str(paths[1]))
    shifted.ImagePositionPatient = [-119.0, -80.0, -50.0]
    shifted.save_as(str(paths[1]))

    with pytest.raises(
        Ct2PhitsFrontendError,
        match="inconsistent ImagePositionPatient X or Y values",
    ):
        select_ct_series(root)


def test_missing_ct_pixel_spacing_is_rejected(tmp_path: Path) -> None:
    root = tmp_path / "ct"
    paths = _write_ct_series(
        root,
        frame_uid=_uid(),
        series_uid=_uid(),
    )
    missing = pydicom.dcmread(str(paths[1]))
    del missing.PixelSpacing
    missing.save_as(str(paths[1]))

    with pytest.raises(Ct2PhitsFrontendError, match="CT PixelSpacing"):
        select_ct_series(root)


def test_non_positive_ct_pixel_spacing_is_rejected(tmp_path: Path) -> None:
    root = tmp_path / "ct"
    paths = _write_ct_series(
        root,
        frame_uid=_uid(),
        series_uid=_uid(),
    )
    invalid = pydicom.dcmread(str(paths[1]))
    invalid.PixelSpacing = [0.0, 0.8]
    invalid.save_as(str(paths[1]))

    with pytest.raises(Ct2PhitsFrontendError, match="must be positive"):
        select_ct_series(root)


def test_inconsistent_ct_pixel_spacing_is_rejected(tmp_path: Path) -> None:
    root = tmp_path / "ct"
    paths = _write_ct_series(
        root,
        frame_uid=_uid(),
        series_uid=_uid(),
    )
    inconsistent = pydicom.dcmread(str(paths[1]))
    inconsistent.PixelSpacing = [0.8, 0.9]
    inconsistent.save_as(str(paths[1]))

    with pytest.raises(Ct2PhitsFrontendError, match="inconsistent PixelSpacing"):
        select_ct_series(root)


def test_non_uniform_ct_slice_spacing_is_rejected(tmp_path: Path) -> None:
    root = tmp_path / "ct"
    _write_ct_series(
        root,
        frame_uid=_uid(),
        series_uid=_uid(),
        z_positions_mm=(0.0, 1.0, 3.0),
    )

    with pytest.raises(
        Ct2PhitsFrontendError,
        match="non-uniform ImagePositionPatient Z spacing",
    ):
        select_ct_series(root)


def test_ct_slice_spacing_uses_reviewed_absolute_tolerance(tmp_path: Path) -> None:
    root = tmp_path / "ct"
    _write_ct_series(
        root,
        frame_uid=_uid(),
        series_uid=_uid(),
        z_positions_mm=(0.0, 1.0, 2.0000005),
    )

    selected = select_ct_series(root)

    assert len(selected.files) == 3


def test_ct_slice_spacing_beyond_reviewed_absolute_tolerance_is_rejected(
    tmp_path: Path,
) -> None:
    root = tmp_path / "ct"
    _write_ct_series(
        root,
        frame_uid=_uid(),
        series_uid=_uid(),
        z_positions_mm=(0.0, 1.0, 2.000002),
    )

    with pytest.raises(
        Ct2PhitsFrontendError,
        match="non-uniform ImagePositionPatient Z spacing",
    ):
        select_ct_series(root)


def test_raw_datfile_change_during_handoff_is_rejected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    case = _case(tmp_path)
    original_prepare = run_ct2phits_module.prepare_ct2phits_assets

    def mutating_prepare(**kwargs):
        prepared = original_prepare(**kwargs)
        raw_root = Path(kwargs["raw_datfiles_root"])
        (raw_root / "CTsurf.dat").write_text(
            "$ synthetic changed during handoff\n",
            encoding="utf-8",
        )
        return prepared

    monkeypatch.setattr(
        run_ct2phits_module,
        "prepare_ct2phits_assets",
        mutating_prepare,
    )

    with pytest.raises(
        Ct2PhitsFrontendError,
        match="raw CT2PHITS DATfiles changed during downstream handoff",
    ):
        run_ct2phits_frontend(
            ct_dicom_root=case["ct_root"],
            rtplan_path=case["rtplan"],
            rtphits_root=case["rtphits"],
            workspace_root=case["workspace"],
            confirmed_non_patient_phantom=True,
            timeout_seconds=12.0,
            runner=_success_runner(case["workspace"]),
            platform_system="Windows",
        )

    summary = json.loads(
        (case["workspace"] / "ct2phits_execution_summary.json").read_text(
            encoding="utf-8"
        )
    )
    assert summary["status"] == "failed"
    assert "changed during downstream handoff" in summary["failure_reason"]


def test_cttrans_change_during_handoff_is_rejected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    case = _case(tmp_path)
    original_prepare = run_ct2phits_module.prepare_ct2phits_assets

    def mutating_prepare(**kwargs):
        prepared = original_prepare(**kwargs)
        raw_root = Path(kwargs["raw_datfiles_root"])
        (raw_root / "CTtrans.dat").write_text(
            "$ synthetic changed during handoff\n",
            encoding="utf-8",
        )
        return prepared

    monkeypatch.setattr(
        run_ct2phits_module,
        "prepare_ct2phits_assets",
        mutating_prepare,
    )

    with pytest.raises(
        Ct2PhitsFrontendError,
        match="CT2PHITS generated files changed during downstream handoff",
    ):
        run_ct2phits_frontend(
            ct_dicom_root=case["ct_root"],
            rtplan_path=case["rtplan"],
            rtphits_root=case["rtphits"],
            workspace_root=case["workspace"],
            confirmed_non_patient_phantom=True,
            timeout_seconds=12.0,
            runner=_success_runner(case["workspace"]),
            platform_system="Windows",
        )

    summary = json.loads(
        (case["workspace"] / "ct2phits_execution_summary.json").read_text(
            encoding="utf-8"
        )
    )
    assert summary["status"] == "failed"
    assert "generated files changed" in summary["failure_reason"]


def test_raw_change_after_initial_inventory_is_rejected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    case = _case(tmp_path)
    original_inventory = run_ct2phits_module._generated_inventory
    inventory_calls = 0

    def mutating_inventory(datfiles_root: Path):
        nonlocal inventory_calls
        result = original_inventory(datfiles_root)
        inventory_calls += 1
        if inventory_calls == 1:
            (datfiles_root / "CTsurf.dat").write_text(
                "$ synthetic changed after initial inventory\n",
                encoding="utf-8",
            )
        return result

    monkeypatch.setattr(
        run_ct2phits_module,
        "_generated_inventory",
        mutating_inventory,
    )

    with pytest.raises(
        Ct2PhitsFrontendError,
        match="CT2PHITS generated files changed during downstream handoff",
    ):
        run_ct2phits_frontend(
            ct_dicom_root=case["ct_root"],
            rtplan_path=case["rtplan"],
            rtphits_root=case["rtphits"],
            workspace_root=case["workspace"],
            confirmed_non_patient_phantom=True,
            timeout_seconds=12.0,
            runner=_success_runner(case["workspace"]),
            platform_system="Windows",
        )

    assert inventory_calls == 2
    summary = json.loads(
        (case["workspace"] / "ct2phits_execution_summary.json").read_text(
            encoding="utf-8"
        )
    )
    assert summary["status"] == "failed"
    assert "generated files changed" in summary["failure_reason"]
