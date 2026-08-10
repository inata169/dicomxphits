from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

PUBLIC_SRC = Path(__file__).resolve().parents[1] / "src"
if str(PUBLIC_SRC) not in sys.path:
    sys.path.insert(0, str(PUBLIC_SRC))

from dicomxphits.prepare_3dcrt_workspace import ExternalToolPaths
from dicomxphits.run_segments import (
    build_parser,
    main,
    phits_environment,
    run_segments,
)


def active_segment(index=0, **overrides):
    segment = {
        "segment_id": f"seg_{index + 1:03d}",
        "beam_number": 1,
        "segment_index": index,
        "delivery_type": "3dcrt",
        "beam_meterset_mu": 100.0,
        "segment_mu": 50.0,
        "mu_weight": 50.0,
        "mu_weight_unit": "MU",
        "phits_input_path": f"segments/seg_{index + 1:03d}/phits.inp",
        "expected_output_path": f"segments/seg_{index + 1:03d}/deposit-target-3D.out",
    }
    segment.update(overrides)
    return segment


def write_workspace(tmp_path, *segments):
    workspace = tmp_path / "workspace"
    manifest = {
        "schema_version": "segment_manifest_v2",
        "case_id": "synthetic",
        "segments": list(segments) or [active_segment(0)],
    }
    manifest_path = workspace / "segments" / "segment_manifest.json"
    manifest_path.parent.mkdir(parents=True)
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    for segment in manifest["segments"]:
        phits_input = segment.get("phits_input_path")
        if not phits_input or Path(str(phits_input)).is_absolute():
            continue
        path = workspace / str(phits_input)
        path.parent.mkdir(parents=True, exist_ok=True)
        expected_output = str(segment.get("expected_output_path") or "")
        path.write_text(
            "$OMP=8\n[ Parameters ]\n  icntl = 0\n"
            "[ T-Deposit ]\n"
            f"  file = {expected_output}\n"
            "[ E N D ]\n",
            encoding="utf-8",
        )
    return workspace, manifest


def paths():
    return ExternalToolPaths(
        phits_root_folder="/unused/phits-root",
        phits_executable_path="/opt/phits/bin/phits",
        phits2dicom_executable_path=None,
    )


def test_phits_environment_reads_documented_omp_directive(tmp_path):
    phits_input = tmp_path / "phits.inp"
    phits_input.write_text(
        "$OMP = 12\n[ Parameters ]\n maxcas = 1\n",
        encoding="utf-8",
    )

    environment = phits_environment(phits_input)

    assert environment["OMP_NUM_THREADS"] == "12"


@pytest.mark.parametrize(
    "first_line",
    ["OMP = 12", "$OMP = 0", "$OMP = -1", "$OMP = eight", ""],
)
def test_phits_environment_rejects_missing_or_invalid_omp_directive(
    tmp_path,
    first_line,
):
    phits_input = tmp_path / "phits.inp"
    phits_input.write_text(
        f"{first_line}\n[ Parameters ]\n maxcas = 1\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match=r"\$OMP"):
        phits_environment(phits_input)


def fake_runner_for(
    workspace: Path,
    outputs: list[Path],
    *,
    returncode: int = 0,
    produce_output_on_failure: bool = False,
):
    pending = list(outputs)

    def fake_runner(command, *, input, cwd, capture_output, text, shell, env):
        assert command == ["/opt/phits/bin/phits"]
        execution_root = Path(cwd)
        assert execution_root != workspace
        execution_root.resolve().relative_to(workspace.resolve())
        assert capture_output is True
        assert text is True
        assert shell is False
        assert input.startswith("file = segments/")
        assert input.endswith("/phits.inp\n")
        assert env["OMP_NUM_THREADS"] == "8"
        if pending and (returncode == 0 or produce_output_on_failure):
            output = execution_root / pending.pop(0).relative_to(workspace)
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text("dose\n", encoding="utf-8")
        (execution_root / "batch.out").write_text("batch\n", encoding="utf-8")
        (execution_root / "phits.out").write_text("phits\n", encoding="utf-8")
        return subprocess.CompletedProcess(command, returncode, stdout="stdout\n", stderr="stderr\n")

    return fake_runner


def read_summary(workspace: Path):
    return json.loads((workspace / "analysis" / "segment_execution_summary.json").read_text(encoding="utf-8"))


def assert_minimum_summary_shape(summary):
    assert {"status", "segment_count", "succeeded", "failed", "skipped", "segments"} <= set(summary)
    for segment in summary["segments"]:
        assert {
            "segment_id",
            "phits_input_path",
            "expected_output_path",
            "return_code",
            "stdout_log_path",
            "stderr_log_path",
            "status",
        } <= set(segment)


def test_run_segments_records_success_summary_and_collects_root_outputs(tmp_path):
    workspace, manifest = write_workspace(tmp_path, active_segment(0), active_segment(1, segment_mu=0.0))
    expected = [workspace / manifest["segments"][0]["expected_output_path"]]

    summary = run_segments(
        workspace_root=workspace,
        paths=paths(),
        command_argv=["run"],
        runner=fake_runner_for(workspace, expected),
    )

    assert_minimum_summary_shape(summary)
    assert summary["status"] == "success"
    assert summary["segment_count"] == 2
    assert summary["succeeded"] == 1
    assert summary["failed"] == 0
    assert summary["skipped"] == 1
    assert summary["segments"][0]["segment_id"] == "seg_001"
    assert summary["segments"][0]["status"] == "success"
    assert summary["segments"][0]["return_code"] == 0
    assert Path(summary["segments"][0]["stdout_log_path"]).is_file()
    assert Path(summary["segments"][0]["stderr_log_path"]).is_file()
    assert Path(summary["segments"][0]["batch_out_path"]).is_file()
    assert Path(summary["segments"][0]["phits_out_path"]).is_file()
    assert summary["segments"][1]["status"] == "skipped"
    assert read_summary(workspace)["status"] == "success"


def test_run_segments_honors_active_and_skip_flags(tmp_path):
    workspace, manifest = write_workspace(
        tmp_path,
        active_segment(0, active=False, segment_mu=50.0),
        active_segment(1, skip=True, segment_mu=50.0),
        active_segment(2, active=True, segment_mu=0.0),
    )
    expected = [workspace / manifest["segments"][2]["expected_output_path"]]

    summary = run_segments(
        workspace_root=workspace,
        paths=paths(),
        command_argv=["run"],
        runner=fake_runner_for(workspace, expected),
    )

    statuses = {segment["segment_id"]: segment["status"] for segment in summary["segments"]}
    assert statuses == {"seg_001": "skipped", "seg_002": "skipped", "seg_003": "success"}
    assert summary["succeeded"] == 1
    assert summary["skipped"] == 2


@pytest.mark.parametrize("field", ["phits_input_path", "expected_output_path"])
def test_run_segments_rejects_active_paths_outside_workspace_before_execution(tmp_path, field):
    outside = tmp_path / "outside" / "file.out"
    workspace, _manifest = write_workspace(tmp_path, active_segment(0, **{field: str(outside)}))
    calls = []

    def fake_runner(*args, **kwargs):
        calls.append((args, kwargs))
        return subprocess.CompletedProcess(args[0], 0, stdout="", stderr="")

    with pytest.raises(ValueError, match="must resolve inside workspace root"):
        run_segments(workspace_root=workspace, paths=paths(), command_argv=["run"], runner=fake_runner)

    summary = read_summary(workspace)
    assert calls == []
    assert summary["status"] == "gate_failed"
    assert summary["segment_count"] == 1
    assert summary["failed"] == 1
    assert summary["segments"][0]["status"] == "gate_failed"


def test_run_segments_missing_phits_executable_path_does_not_execute(tmp_path):
    workspace, _manifest = write_workspace(tmp_path)
    calls = []

    def fake_runner(*args, **kwargs):
        calls.append((args, kwargs))
        return subprocess.CompletedProcess(args[0], 0, stdout="", stderr="")

    with pytest.raises(ValueError, match="phits_executable_path"):
        run_segments(
            workspace_root=workspace,
            paths=ExternalToolPaths(phits_root_folder="/unused", phits_executable_path=""),
            command_argv=["run"],
            runner=fake_runner,
        )

    assert calls == []
    assert read_summary(workspace)["status"] == "gate_failed"


def test_run_segments_marks_failed_when_expected_output_is_missing(tmp_path):
    workspace, _manifest = write_workspace(tmp_path)

    summary = run_segments(
        workspace_root=workspace,
        paths=paths(),
        command_argv=["run"],
        runner=fake_runner_for(workspace, [], returncode=0),
    )

    assert summary["status"] == "failed"
    assert summary["failed"] == 1
    assert summary["segments"][0]["status"] == "failed"
    assert summary["segments"][0]["return_code"] == 0


def test_run_segments_removes_stale_expected_output_before_success_check(tmp_path):
    workspace, manifest = write_workspace(tmp_path)
    expected = workspace / manifest["segments"][0]["expected_output_path"]
    expected.parent.mkdir(parents=True, exist_ok=True)
    expected.write_text("stale dose\n", encoding="utf-8")

    summary = run_segments(
        workspace_root=workspace,
        paths=paths(),
        command_argv=["run"],
        runner=fake_runner_for(workspace, [], returncode=0),
    )

    assert summary["status"] == "failed"
    assert summary["failed"] == 1
    assert summary["segments"][0]["status"] == "failed"
    assert not expected.exists()


def test_run_segments_validates_all_omp_directives_before_removing_outputs(tmp_path):
    workspace, manifest = write_workspace(tmp_path, active_segment(0), active_segment(1))
    expected_outputs = [
        workspace / segment["expected_output_path"]
        for segment in manifest["segments"]
    ]
    for output in expected_outputs:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text("prior dose\n", encoding="utf-8")
    root_outputs = [workspace / "batch.out", workspace / "phits.out"]
    for output in root_outputs:
        output.write_text("prior root output\n", encoding="utf-8")
    second_input = workspace / manifest["segments"][1]["phits_input_path"]
    second_input.write_text(
        "[ Parameters ]\n  icntl = 0\n[ E N D ]\n",
        encoding="utf-8",
    )
    calls = []

    def fake_runner(*args, **kwargs):
        calls.append((args, kwargs))
        return subprocess.CompletedProcess(args[0], 0, stdout="", stderr="")

    with pytest.raises(ValueError, match=r"\$OMP"):
        run_segments(
            workspace_root=workspace,
            paths=paths(),
            command_argv=["run"],
            runner=fake_runner,
        )

    assert calls == []
    assert all(output.read_text(encoding="utf-8") == "prior dose\n" for output in expected_outputs)
    assert all(output.read_text(encoding="utf-8") == "prior root output\n" for output in root_outputs)
    assert read_summary(workspace)["status"] == "gate_failed"


def test_run_segments_keeps_failure_outputs_diagnostic_only(tmp_path):
    workspace, manifest = write_workspace(tmp_path)
    expected = workspace / manifest["segments"][0]["expected_output_path"]

    summary = run_segments(
        workspace_root=workspace,
        paths=paths(),
        command_argv=["run"],
        runner=fake_runner_for(
            workspace,
            [expected],
            returncode=9,
            produce_output_on_failure=True,
        ),
    )

    assert summary["status"] == "failed"
    segment_summary = summary["segments"][0]
    assert segment_summary["status"] == "failed"
    assert segment_summary["return_code"] == 9
    assert not expected.exists()
    assert Path(segment_summary["stdout_log_path"]).read_text(encoding="utf-8") == "stdout\n"
    assert Path(segment_summary["stderr_log_path"]).read_text(encoding="utf-8") == "stderr\n"
    assert Path(segment_summary["batch_out_path"]).is_file()
    assert Path(segment_summary["phits_out_path"]).is_file()


def test_run_segments_cli_returns_success_and_prints_summary_path(tmp_path, capsys, monkeypatch):
    workspace, _manifest = write_workspace(tmp_path)

    import dicomxphits.run_segments as module

    def fake_run_segments(**kwargs):
        summary = {
            "status": "success",
            "segment_count": 1,
            "succeeded": 1,
            "failed": 0,
            "skipped": 0,
            "segments": [],
        }
        module.write_json(
            module.summary_path(kwargs["workspace_root"]),
            summary,
            case_root=kwargs["workspace_root"],
        )
        return summary

    monkeypatch.setattr(module, "run_segments", fake_run_segments)

    code = main(["--workspace-root", str(workspace), "--phits-executable-path", "/opt/phits/bin/phits"])

    captured = capsys.readouterr()
    assert code == 0
    assert "segment_execution_summary.json" in captured.out
    assert read_summary(workspace)["status"] == "success"


def test_run_segments_parser_has_public_cli_options():
    parser_actions = {action.dest for action in build_parser()._actions}

    assert {"workspace_root", "paths_json", "phits_executable_path"} <= parser_actions
