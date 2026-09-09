from __future__ import annotations

import json
import subprocess
import sys
import threading
from copy import deepcopy
from dataclasses import replace
from pathlib import Path

import pytest

from dicomxphits.prepare_3dcrt_workspace import ExternalToolPaths, write_libpath
from dicomxphits.run_segments import run_segments, summary_path, main
from dicomxphits.segment_retry import plan_incomplete, validate_results
from dicomxphits.safe_output import WorkspaceOutputGuard
from dicomxphits.workspace_execution import WorkspaceBusyError, WorkspaceExecutionLease
from dicomxphits.workspace_recovery import validate_segment_execution_for_downstream
from test_run_segments import write_workspace, active_segment, CLEAN_PHITS_GEOMETRY_SUMMARY


def workspace_fixture(tmp_path, segment_count=2):
    root, manifest = write_workspace(tmp_path, *(active_segment(i) for i in range(segment_count)))
    (root / "analysis").mkdir()
    for name in ("phits_generation_summary.json", "public_preparation_workspace_summary.json"):
        (root / "analysis" / name).write_text(json.dumps({"synthetic": True}), encoding="utf-8")
    tools = tmp_path / "synthetic-tools"
    tools.mkdir()
    executable = tools / "synthetic-executable"
    executable.write_bytes(b"synthetic executable identity, never launched")
    (tools / "synthetic-library").write_bytes(b"synthetic runtime data")
    write_libpath(root, phits_root_folder=str(tools))
    for segment in manifest["segments"]:
        source = root / segment["phits_input_path"]
        source.write_text("infl:{libpath.inp}\n" + source.read_text(), encoding="utf-8")
    return root, manifest, ExternalToolPaths(str(tools), str(executable), None)


def runner_for(root, *, fail=(), calls=None):
    def runner(command, **kwargs):
        source = kwargs["input"].strip().removeprefix("file = ")
        segment_id = Path(source).parent.name
        if calls is not None:
            calls.append(segment_id)
        if segment_id in fail:
            return subprocess.CompletedProcess(command, 1, stdout="failed", stderr="synthetic failure")
        staging = Path(kwargs["cwd"])
        output = staging / Path(source).parent / "deposit-target-3D.out"
        output.write_text("dose\n", encoding="utf-8")
        output.with_name("deposit-target-3D_err.out").write_text("error\n", encoding="utf-8")
        (staging / "phits.out").write_text(CLEAN_PHITS_GEOMETRY_SUMMARY, encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, stdout="ok", stderr="")
    return runner


def partial(tmp_path):
    root, manifest, paths = workspace_fixture(tmp_path)
    result = run_segments(workspace_root=root, paths=paths,
        runner=runner_for(root, fail={"seg_002"}))
    assert result["stage_status"] == "failed"
    return root, manifest, paths, result


@pytest.mark.parametrize("damage", ["different_root", "extra_directive", "other_file"])
def test_noncanonical_runtime_directive_cannot_authorize_retry(tmp_path, damage):
    root, manifest, paths = workspace_fixture(tmp_path)
    if damage == "different_root":
        write_libpath(root, phits_root_folder=str(tmp_path / "different-installation"))
    elif damage == "extra_directive":
        libpath = root / "libpath.inp"
        libpath.write_text(libpath.read_text() + "file(2) = unknown\n")
    else:
        source = root / manifest["segments"][0]["phits_input_path"]
        source.write_text(source.read_text() + (root / "libpath.inp").read_text())
    result = run_segments(workspace_root=root, paths=paths,
        runner=runner_for(root, fail={"seg_002"}))
    assert result["execution_binding"]["retry_unavailable"]
    with pytest.raises(ValueError, match="Retry evidence unavailable"):
        plan_incomplete(root, paths)


def test_retry_preserves_completed_artifacts_and_creates_unique_terminal_evidence(tmp_path):
    root, manifest, paths, original = partial(tmp_path)
    first_files = list((root / "segments" / "seg_001").iterdir())
    before = {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in first_files}
    original_bytes = summary_path(root).read_bytes()
    plan = plan_incomplete(root, paths)
    assert plan["retained"] == ["seg_001"]
    assert plan["scheduled"] == ["seg_002"]
    assert summary_path(root).read_bytes() == original_bytes
    calls = []
    result = run_segments(workspace_root=root, paths=paths, run_incomplete=True,
        expected_summary_sha256=plan["source_sha256"], runner=runner_for(root, calls=calls))
    assert calls == ["seg_002"]
    assert result["stage_status"] == "success"
    assert result["retained_active_segment_count"] == 1
    assert result["segments"][0]["producer_run_id"] == original["run_id"]
    assert result["segments"][1]["producer_run_id"] == result["run_id"]
    assert {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in first_files} == before
    assert (root / result["parent_attempt"]["path"]).read_bytes() == original_bytes
    validate_segment_execution_for_downstream(root, manifest, result)
    assert plan_incomplete(root, paths)["scheduled"] == []
    again = run_segments(workspace_root=root, paths=paths, run_incomplete=True,
        runner=lambda *a, **kw: pytest.fail("completed retry launched"))
    assert again == result


@pytest.mark.parametrize("damage", ["input", "include", "tool", "library", "prep",
    "manifest", "output", "missing", "geometry", "missing_record", "malformed", "legacy", "history"])
def test_retry_rejects_changed_or_missing_evidence_before_launch(tmp_path, damage):
    root, manifest, paths, original = partial(tmp_path)
    source = root / manifest["segments"][0]["phits_input_path"]
    output = root / manifest["segments"][0]["expected_output_path"]
    if damage == "input":
        source.write_text(source.read_text() + "# changed\n")
    elif damage == "include":
        (root / "new.inp").write_text("synthetic")
        source.write_text(source.read_text() + "infl:{new.inp}\n")
    elif damage == "tool":
        Path(paths.phits_executable_path).write_bytes(b"changed")
    elif damage == "library":
        (Path(paths.phits_root_folder) / "synthetic-library").write_bytes(b"changed")
    elif damage == "prep":
        (root / "analysis/phits_generation_summary.json").write_text("{}")
    elif damage == "manifest":
        manifest["segments"][0]["segment_mu"] = 49
        (root / "segments/segment_manifest.json").write_text(json.dumps(manifest))
    elif damage == "output":
        output.write_bytes(b"changed")
    elif damage == "missing":
        output.unlink()
    elif damage == "geometry":
        original["segments"][0]["geometry_diagnostics"]["counts"]["lost_particles"] = 1
        summary_path(root).write_text(json.dumps(original))
    elif damage == "missing_record":
        summary_path(root).unlink()
    elif damage == "malformed":
        summary_path(root).write_text("{")
    elif damage == "legacy":
        original["schema_version"] = "dicomxphits_public_segment_execution_v3"
        summary_path(root).write_text(json.dumps(original))
    else:
        run_segments(workspace_root=root, paths=paths, run_incomplete=True,
            runner=runner_for(root, fail={"seg_002"}))
        current = json.loads(summary_path(root).read_text())
        (root / current["parent_attempt"]["path"]).write_text("{}")
    before = summary_path(root).read_bytes() if summary_path(root).exists() else None
    with pytest.raises((ValueError, OSError)):
        run_segments(workspace_root=root, paths=paths, run_incomplete=True,
            runner=lambda *a, **kw: pytest.fail("invalid retry launched"))
    assert (summary_path(root).read_bytes() if summary_path(root).exists() else None) == before


def test_repeated_failure_retains_verified_segment_and_blocks_downstream(tmp_path):
    root, manifest, paths, _ = partial(tmp_path)
    for _ in range(2):
        result = run_segments(workspace_root=root, paths=paths, run_incomplete=True,
            runner=runner_for(root, fail={"seg_002"}))
        assert result["stage_status"] == "failed"
        assert result["retained_active_segment_count"] == 1
        with pytest.raises(ValueError):
            validate_segment_execution_for_downstream(root, manifest, result)


def test_stale_preview_does_not_replace_summary(tmp_path):
    root, _, paths, original = partial(tmp_path)
    plan = plan_incomplete(root, paths)
    original["failure_reason"] = "changed preview"
    summary_path(root).write_text(json.dumps(original))
    before = summary_path(root).read_bytes()
    with pytest.raises(ValueError, match="preview changed"):
        run_segments(workspace_root=root, paths=paths, run_incomplete=True,
            expected_summary_sha256=plan["source_sha256"])
    assert summary_path(root).read_bytes() == before


def test_staged_input_change_rejects_before_runner(tmp_path, monkeypatch):
    import dicomxphits.run_segments as module
    root, _, paths = workspace_fixture(tmp_path)
    stage = module.stage_phits_segment_run
    def changed(**kwargs):
        staging, source, outputs = stage(**kwargs)
        source.write_text("changed")
        return staging, source, outputs
    monkeypatch.setattr(module, "stage_phits_segment_run", changed)
    with pytest.raises(ValueError, match="Staged input changed"):
        run_segments(workspace_root=root, paths=paths,
            runner=lambda *a, **kw: pytest.fail("stale staged input launched"))


def test_concurrent_owner_blocks_another_thread_without_changing_evidence(tmp_path):
    root, _, paths, _ = partial(tmp_path)
    before = summary_path(root).read_bytes()
    errors = []
    def another():
        try:
            plan_incomplete(root, paths)
        except Exception as exc:
            errors.append(exc)
    with WorkspaceExecutionLease(root, create=False):
        thread = threading.Thread(target=another)
        thread.start()
        thread.join(timeout=10)
        assert not thread.is_alive()
    assert len(errors) == 1 and isinstance(errors[0], WorkspaceBusyError)
    assert summary_path(root).read_bytes() == before


def test_lock_is_retained_by_child_after_controller_exits(tmp_path):
    root = tmp_path / "workspace"
    root.mkdir()
    child_done = tmp_path / "done"
    ready = tmp_path / "ready"
    # A synthetic child waits for a file, without loading any external tool.
    child = "import pathlib,sys,time; p=pathlib.Path(sys.argv[1]); pathlib.Path(sys.argv[2]).write_text('ready'); " + \
        "exec('while not p.exists(): time.sleep(0.02)')"
    controller = "\n".join([
        "import os,sys,threading,time,pathlib",
        "from dicomxphits.workspace_execution import WorkspaceExecutionLease",
        "lease=WorkspaceExecutionLease(pathlib.Path(sys.argv[1])); lease.__enter__()",
        "threading.Thread(target=lambda: lease.run([sys.executable,'-c',sys.argv[4],sys.argv[2],sys.argv[3]])).start()",
        "while not pathlib.Path(sys.argv[3]).exists(): time.sleep(0.02)",
        "os._exit(0)",
    ])
    process = subprocess.Popen([sys.executable, "-c", controller, str(root), str(child_done), str(ready), child])
    try:
        process.wait(timeout=10)
        assert ready.exists()
        with pytest.raises(WorkspaceBusyError):
            with WorkspaceExecutionLease(root, create=False):
                pass
    finally:
        child_done.write_text("release")
        process.wait(timeout=10)


def test_gui_retry_command_uses_preview_and_does_not_require_overwrite(tmp_path):
    from test_gui import base_config
    from dicomxphits.gui import build_stage_command, stage_by_key, validate_stage
    root, _, paths, _ = partial(tmp_path)
    plan = plan_incomplete(root, paths)
    config = replace(base_config(tmp_path, workspace=root),
        phits_root_folder=paths.phits_root_folder,
        phits_executable_path=paths.phits_executable_path,
        retry_source_sha256=plan["source_sha256"], allow_overwrite=False)
    spec = stage_by_key("run_segments")
    assert validate_stage(config, spec) == root
    command = build_stage_command(config, spec)
    assert "--run-incomplete" in command
    assert command[command.index("--expected-summary-sha256") + 1] == plan["source_sha256"]


def test_gui_retry_progress_distinguishes_retained_results_and_waits_for_new_eta(tmp_path):
    from dicomxphits.gui import format_segment_progress, estimate_segment_remaining_seconds
    root, _, paths, _ = partial(tmp_path)
    snapshots = []
    run_segments(workspace_root=root, paths=paths, run_incomplete=True,
        runner=runner_for(root), summary_writer=lambda p, s: snapshots.append(deepcopy(s)))
    initial = snapshots[0]
    assert "retained 1, newly completed 0" in format_segment_progress(initial, process_active=True)
    assert estimate_segment_remaining_seconds(initial, live_elapsed_seconds=0) is None
    assert "retained 1, newly completed 1" in format_segment_progress(snapshots[-1], process_active=False)


def test_gui_progress_does_not_match_another_selected_workspace(tmp_path):
    from dicomxphits.gui import progress_workspace_matches
    root = tmp_path / "first"
    source = root / "analysis/segment_execution_summary.json"
    assert progress_workspace_matches(str(root), source)
    assert not progress_workspace_matches(str(tmp_path / "second"), source)
    assert not progress_workspace_matches("", source)


def test_retry_after_orphaned_running_snapshot_starts_only_pending_segment(tmp_path):
    root, _, paths = workspace_fixture(tmp_path)
    base_runner = runner_for(root)
    def interrupted(command, **kwargs):
        if "seg_002" in kwargs["input"]:
            raise KeyboardInterrupt()
        return base_runner(command, **kwargs)
    with pytest.raises(KeyboardInterrupt):
        run_segments(workspace_root=root, paths=paths, runner=interrupted)
    assert json.loads(summary_path(root).read_text())["stage_status"] == "running"
    calls = []
    result = run_segments(workspace_root=root, paths=paths, run_incomplete=True,
        runner=runner_for(root, calls=calls))
    assert result["stage_status"] == "success" and calls == ["seg_002"]


@pytest.mark.parametrize("field", ["phits_input_path", "expected_output_path"])
def test_retry_rejects_escaping_paths_before_execution(tmp_path, field):
    root, manifest, paths, _ = partial(tmp_path)
    manifest["segments"][1][field] = "../outside"
    (root / "segments/segment_manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError):
        run_segments(workspace_root=root, paths=paths, run_incomplete=True,
            runner=lambda *a, **k: pytest.fail("escaping path executed"))


def test_colliding_target_cannot_replace_successful_segment_files(tmp_path):
    root, manifest, paths = workspace_fixture(tmp_path)
    second = root / manifest["segments"][1]["phits_input_path"]
    second.write_text(second.read_text() + "\nfile = segments/seg_001/phits_stdout.txt\n")
    with pytest.raises(ValueError, match="collision"):
        run_segments(workspace_root=root, paths=paths,
            runner=lambda *a, **k: pytest.fail("collision executed"))


def test_retained_source_missing_during_preservation_starts_no_retry(tmp_path, monkeypatch):
    root, _, paths, _ = partial(tmp_path)
    before = summary_path(root).read_bytes()
    copy_file = WorkspaceOutputGuard.copy_file
    def reject_history(self, source, destination, **kwargs):
        if "segment_attempt_history" in destination.parts:
            raise OSError("synthetic preservation failure")
        return copy_file(self, source, destination, **kwargs)
    monkeypatch.setattr(WorkspaceOutputGuard, "copy_file", reject_history)
    with pytest.raises(OSError, match="preservation failure"):
        run_segments(workspace_root=root, paths=paths, run_incomplete=True,
            runner=lambda *a, **k: pytest.fail("preservation failure executed"))
    assert summary_path(root).read_bytes() == before
