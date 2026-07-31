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
from dicomxphits.run_segments import build_parser, main, run_segments


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
        path.write_text(
            "$OMP=8\n[ Parameters ]\n  icntl = 0\n[ E N D ]\n",
            encoding="utf-8",
        )
    return workspace, manifest


def paths():
    return ExternalToolPaths(
        phits_root_folder="/unused/phits-root",
        phits_executable_path="/opt/phits/bin/phits",
        phits2dicom_executable_path=None,
    )


def fake_runner_for(workspace: Path, outputs: list[Path], *, returncode: int = 0):
    pending = list(outputs)

    def fake_runner(command, *, input, cwd, capture_output, text, shell, env):
        assert command == ["/opt/phits/bin/phits"]
        assert Path(cwd) == workspace
        assert capture_output is True
        assert text is True
        assert shell is False
        assert input.startswith("file = segments/")
        assert input.endswith("/phits.inp\n")
        assert env["OMP_NUM_THREADS"] == "8"
        if pending and returncode == 0:
            output = pending.pop(0)
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text("dose\n", encoding="utf-8")
        (Path(cwd) / "batch.out").write_text("batch\n", encoding="utf-8")
        (Path(cwd) / "phits.out").write_text("phits\n", encoding="utf-8")
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


def test_run_segments_collects_root_outputs_on_phits_failure(tmp_path):
    workspace, _manifest = write_workspace(tmp_path)

    summary = run_segments(
        workspace_root=workspace,
        paths=paths(),
        command_argv=["run"],
        runner=fake_runner_for(workspace, [], returncode=9),
    )

    assert summary["status"] == "failed"
    assert summary["segments"][0]["status"] == "failed"
    assert summary["segments"][0]["return_code"] == 9
    assert Path(summary["segments"][0]["batch_out_path"]).is_file()
    assert Path(summary["segments"][0]["phits_out_path"]).is_file()


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
        module.write_json(module.summary_path(kwargs["workspace_root"]), summary)
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
