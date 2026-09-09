from __future__ import annotations

import io
import json
import threading
import subprocess
import sys
import time
from pathlib import Path
from copy import deepcopy
from dataclasses import replace

import pytest

from dicomxphits.gui import StageResult, format_segment_progress, stop_available, verified_user_stop
from dicomxphits.run_segments import (
    SEGMENT_EXECUTION_SCHEMA_V4, SEGMENT_EXECUTION_SCHEMA_V5,
    run_segments, summary_path, validate_segment_execution_summary,
)
from dicomxphits.segment_retry import plan_incomplete
from dicomxphits.segment_stop import ControllerPipe, StopControl, run_while_polling
from dicomxphits.workspace_execution import WorkspaceBusyError, WorkspaceExecutionLease
from dicomxphits.workspace_recovery import validate_segment_execution_for_downstream
from test_segment_retry import workspace_fixture, runner_for, partial


def request(root, *, run_id="stop-run", request_id="request-1"):
    return {"operation": "stop-after-current", "workspace_root": str(root.resolve()),
        "run_id": run_id, "request_id": request_id}


def submit(control, root, **kwargs):
    control.feed(json.dumps(request(root, **kwargs)).encode() + b"\n")


def writer(root, snapshots, callback=lambda s: None):
    def write(path, summary):
        snapshots.append(deepcopy(summary))
        path.parent.mkdir(exist_ok=True)
        path.write_text(json.dumps(summary), encoding="utf-8")
        callback(summary)
    return write


def test_stop_before_first_launch_then_explicit_retry(tmp_path):
    root, manifest, paths = workspace_fixture(tmp_path)
    control = StopControl()
    submit(control, root)
    result = run_segments(workspace_root=root, paths=paths, stop_control=control,
        run_id_factory=lambda: "stop-run", runner=lambda *a, **k: pytest.fail("launched"))
    assert result["stage_status"] == "stopped"
    assert result["stop_requested"]["boundary_segment"] is None
    assert result["remaining_active_segment_count"] == 2
    validate_segment_execution_summary(result, require_success=False)
    with pytest.raises(ValueError):
        validate_segment_execution_for_downstream(root, manifest, result)
    assert plan_incomplete(root, paths)["scheduled"] == ["seg_001", "seg_002"]
    resumed = run_segments(workspace_root=root, paths=paths, run_incomplete=True, runner=runner_for(root))
    assert resumed["stage_status"] == "success" and resumed["stop_requested"] is None


@pytest.mark.parametrize("target,fail,expected", [
    ("seg_001", (), "stopped"), ("seg_001", ("seg_001",), "failed"),
    ("seg_002", (), "success"), ("seg_002", ("seg_002",), "failed"),
    ("seg_002", ("seg_001",), "failed"),
])
def test_in_segment_acknowledgement_and_terminal_precedence(tmp_path, target, fail, expected):
    root, _, paths = workspace_fixture(tmp_path)
    control = StopControl()
    acknowledged = threading.Event()
    calls, snapshots = [], []
    base = runner_for(root, fail=fail, calls=calls)

    def child(command, **kwargs):
        if target in kwargs["input"]:
            submit(control, root)
            assert acknowledged.wait(10), "controller did not acknowledge while child was running"
        return base(command, **kwargs)

    def boundary(summary):
        if summary.get("stop_requested"):
            acknowledged.set()

    result = run_segments(workspace_root=root, paths=paths, stop_control=control,
        runner=child, run_id_factory=lambda: "stop-run",
        summary_writer=writer(root, snapshots, boundary))
    assert result["stage_status"] == expected
    assert calls == (["seg_001"] if target == "seg_001" else ["seg_001", "seg_002"])
    assert result["stop_requested"]["boundary_segment"]["segment_id"] == target
    pending = next(s for s in snapshots if s["stop_requested"])
    assert pending["stage_status"] == "running" and pending["current_segment"] is not None
    assert "Stop pending" in format_segment_progress(pending, process_active=True)
    assert "Interrupted" in format_segment_progress(pending, process_active=False)
    if expected == "stopped":
        kept = root / "segments/seg_001/deposit-target-3D.out"
        original = (kept.read_bytes(), kept.stat().st_mtime_ns)
        resumed = run_segments(workspace_root=root, paths=paths, run_incomplete=True, runner=runner_for(root))
        assert resumed["stage_status"] == "success" and resumed["stop_requested"] is None
        assert (kept.read_bytes(), kept.stat().st_mtime_ns) == original


def test_request_between_segments_has_no_current_boundary(tmp_path):
    root, _, paths = workspace_fixture(tmp_path)
    control = StopControl()
    snapshots = []
    def boundary(s):
        if s["completed_active_segment_count"] == 1 and s["current_segment"] is None and not s["stop_requested"]:
            submit(control, root)
            submit(control, root)  # duplicate acknowledgement is idempotent
    result = run_segments(workspace_root=root, paths=paths, stop_control=control,
        runner=runner_for(root), run_id_factory=lambda: "stop-run",
        summary_writer=writer(root, snapshots, boundary))
    assert result["stage_status"] == "stopped"
    assert result["stop_requested"]["boundary_segment"] is None
    assert len([s for s in snapshots if s["stop_requested"] and s["stage_status"] == "running"]) == 1


@pytest.mark.parametrize("damage", ["run", "workspace", "operation", "identity", "extra"])
def test_invalid_request_does_not_change_execution(tmp_path, damage):
    root, _, paths = workspace_fixture(tmp_path)
    messages = []
    control = StopControl(messages.append)
    value = request(root)
    value[{"run": "run_id", "workspace": "workspace_root", "operation": "operation",
        "identity": "request_id", "extra": "extra"}[damage]] = ""
    control.feed(json.dumps(value).encode())
    result = run_segments(workspace_root=root, paths=paths, stop_control=control,
        runner=runner_for(root), run_id_factory=lambda: "stop-run")
    assert result["stage_status"] == "success" and result["stop_requested"] is None
    assert messages


def test_control_reader_is_bounded_and_eof_does_not_stop(tmp_path):
    control = StopControl(lambda message: None)
    data = (b"x" * 5000 + b"\nnot json\n\xff\n" + b"[" * 1500 + b"0" + b"]" * 1500
        + b"\n" + json.dumps(request(tmp_path)).encode() + b"\n")
    control.read(io.BytesIO(data))
    assert list(control.take()) == [request(tmp_path)]
    control.read(io.BytesIO(b""))
    assert list(control.take()) == []
    for _ in range(100):
        control.feed(json.dumps(request(tmp_path)).encode())
    assert len(list(control.take())) == 16
    control.close()
    submit(control, tmp_path)
    assert list(control.take()) == []


def test_acknowledgement_persistence_failure_waits_for_child(tmp_path):
    root, _, paths = workspace_fixture(tmp_path)
    control = StopControl()
    failed_write, child_finished = threading.Event(), threading.Event()
    calls = []
    base = runner_for(root, calls=calls)
    def child(command, **kwargs):
        submit(control, root)
        assert failed_write.wait(10)
        result = base(command, **kwargs)
        child_finished.set()
        return result
    def persist(path, summary):
        if summary["stop_requested"] and summary["stage_status"] == "running":
            failed_write.set()
            raise OSError("synthetic acknowledgement persistence failure")
        path.write_text(json.dumps(summary))
    with pytest.raises(OSError, match="acknowledgement"):
        run_segments(workspace_root=root, paths=paths, stop_control=control,
            runner=child, run_id_factory=lambda: "stop-run", summary_writer=persist)
    assert child_finished.is_set() and calls == ["seg_001"]
    assert json.loads(summary_path(root).read_text())["stage_status"] == "gate_failed"


def stopped_fixture(tmp_path):
    root, manifest, paths = workspace_fixture(tmp_path)
    control = StopControl()
    submit(control, root)
    result = run_segments(workspace_root=root, paths=paths, stop_control=control,
        run_id_factory=lambda: "stop-run", runner=runner_for(root))
    return root, manifest, paths, result


@pytest.mark.parametrize("damage", ["ack", "time", "run", "boundary", "enabled", "count", "version"])
def test_stopped_evidence_is_strict(tmp_path, damage):
    root, _, paths, result = stopped_fixture(tmp_path)
    if damage == "ack": result["stop_requested"] = None
    if damage == "time": result["stop_requested"]["acknowledged_elapsed_seconds"] = float("nan")
    if damage == "run": result["stop_requested"]["run_id"] = "old"
    if damage == "boundary": result["stop_requested"]["boundary_segment"] = {"segment_id": "missing"}
    if damage == "enabled": result["stop_control_enabled"] = False
    if damage == "count": result["remaining_active_segment_count"] = 0
    if damage == "version": result["schema_version"] = SEGMENT_EXECUTION_SCHEMA_V4
    with pytest.raises(ValueError): validate_segment_execution_summary(result, require_success=False)


def test_v4_parent_can_be_retained_by_stopped_v5_then_retried(tmp_path):
    root, _, paths, source = partial(tmp_path)
    source["schema_version"] = SEGMENT_EXECUTION_SCHEMA_V4
    source.pop("stop_requested")
    source.pop("stop_control_enabled")
    summary_path(root).write_text(json.dumps(source))
    old_bytes = summary_path(root).read_bytes()
    control = StopControl()
    submit(control, root)
    stopped = run_segments(workspace_root=root, paths=paths, run_incomplete=True,
        run_id_factory=lambda: "stop-run", stop_control=control, runner=runner_for(root))
    assert stopped["schema_version"] == SEGMENT_EXECUTION_SCHEMA_V5
    assert (root / stopped["parent_attempt"]["path"]).read_bytes() == old_bytes
    assert stopped["retained_active_segment_count"] == 1
    assert run_segments(workspace_root=root, paths=paths, run_incomplete=True,
        runner=runner_for(root))["stage_status"] == "success"


def test_gui_stop_requires_owned_matching_exit_and_evidence(tmp_path):
    root, _, _, summary = stopped_fixture(tmp_path)
    result = StageResult(stage_key="run_segments", command=[], return_code=4,
        summary_path=summary_path(root), summary=summary, stdout="", stderr="")
    assert verified_user_stop(result, expected_run_id="stop-run", prior_run_id=None)
    assert not verified_user_stop(replace(result, return_code=0), expected_run_id="stop-run", prior_run_id=None)
    assert not verified_user_stop(result, expected_run_id="another-run", prior_run_id=None)
    assert not stop_available(summary)
    assert "User stopped" in format_segment_progress(summary, process_active=False)


def test_gui_controller_pipe_drains_output_and_sends_only_to_controller(tmp_path):
    client = ControllerPipe()
    ready = tmp_path / "ready"
    code = (
        "import sys,json,pathlib; "
        "sys.stdout.write('x'*100000); sys.stdout.flush(); "
        "sys.stderr.write('y'*100000); sys.stderr.flush(); "
        "pathlib.Path(sys.argv[1]).write_text('ready'); "
        "request=json.loads(sys.stdin.readline()); "
        "assert request['operation']=='stop-after-current'; "
        "print(request['run_id']); sys.exit(4)"
    )
    results = []
    worker = threading.Thread(target=lambda: results.append(client.run(
        [sys.executable, "-c", code, str(ready)], cwd=tmp_path)))
    worker.start()
    try:
        deadline = time.monotonic() + 10
        while not ready.exists() and time.monotonic() < deadline:
            time.sleep(0.02)
        assert ready.exists(), "controller output pipes stalled"
        assert client.send(str(tmp_path), "test-owned-run")
    finally:
        # Test-only EOF releases the synthetic readline if an assertion failed.
        if client.process is not None:
            try: client.process.stdin.close()
            except OSError: pass
        worker.join(10)
    assert not worker.is_alive()
    assert results[0].returncode == 4
    assert results[0].stdout.endswith("test-owned-run\n")
    assert len(results[0].stderr) == 100000 and client.process is None
    with pytest.raises(ValueError): client.send(str(tmp_path), "late")


def test_stop_wait_loop_retains_ownership_after_controller_death(tmp_path):
    root = tmp_path / "workspace"
    root.mkdir()
    ready, done = tmp_path / "ready", tmp_path / "done"
    child = (
        "import pathlib,sys,time; p=pathlib.Path(sys.argv[1]); "
        "pathlib.Path(sys.argv[2]).write_text('ready'); "
        "exec('while not p.exists(): time.sleep(0.02)')"
    )
    controller = "\n".join([
        "import os,sys,pathlib",
        "from dicomxphits.segment_stop import run_while_polling",
        "from dicomxphits.workspace_execution import WorkspaceExecutionLease",
        "def poll():",
        "    if pathlib.Path(sys.argv[3]).exists(): os._exit(0)",
        "with WorkspaceExecutionLease(pathlib.Path(sys.argv[1])) as lease:",
        "    run_while_polling(lease.run, poll, [sys.executable,'-c',sys.argv[4],sys.argv[2],sys.argv[3]])",
    ])
    process = subprocess.Popen([sys.executable, "-c", controller, str(root), str(done), str(ready), child])
    try:
        process.wait(10)
        assert ready.exists()
        with pytest.raises(WorkspaceBusyError):
            with WorkspaceExecutionLease(root, create=False): pass
    finally:
        done.write_text("release")
        process.wait(10)


def test_stop_unavailable_without_retry_identity_does_not_change_ordinary_run(tmp_path):
    root, _, paths = workspace_fixture(tmp_path)
    control = StopControl(lambda message: None)
    submit(control, root)
    snapshots = []
    result = run_segments(workspace_root=root, paths=replace(paths, phits_root_folder=None),
        stop_control=control, runner=runner_for(root), run_id_factory=lambda: "stop-run",
        summary_writer=writer(root, snapshots))
    assert result["stage_status"] == "success" and result["stop_requested"] is None
    assert not any(stop_available(s) for s in snapshots)


def test_stop_capability_is_available_only_before_acknowledgement(tmp_path):
    root, _, paths = workspace_fixture(tmp_path)
    control = StopControl()
    snapshots = []
    submit(control, root)
    run_segments(workspace_root=root, paths=paths, stop_control=control,
        run_id_factory=lambda: "stop-run", runner=runner_for(root),
        summary_writer=writer(root, snapshots))
    assert stop_available(snapshots[0])
    assert not any(stop_available(s) for s in snapshots[1:])


def test_stopped_gui_rejects_input_changes_even_when_outputs_are_intact(tmp_path):
    root, manifest, _, summary = stopped_fixture(tmp_path)
    source = root / manifest["segments"][0]["phits_input_path"]
    source.write_text(source.read_text() + "# changed\n")
    result = StageResult(stage_key="run_segments", command=[], return_code=4,
        summary_path=summary_path(root), summary=summary, stdout="", stderr="")
    assert not verified_user_stop(result, expected_run_id="stop-run", prior_run_id=None)
    from dicomxphits.gui import format_existing_segment_progress
    assert "User stopped" not in format_existing_segment_progress(root, summary)


def test_cli_has_distinct_stopped_exit_without_changing_other_exit_contracts(tmp_path, monkeypatch):
    import dicomxphits.run_segments as module
    root, _, _, stopped = stopped_fixture(tmp_path)
    monkeypatch.setattr(module, "run_segments", lambda **kwargs: stopped)
    assert module.main(["--workspace-root", str(root)]) == 4
    for status, code in [("success", 0), ("failed", 3)]:
        monkeypatch.setattr(module, "run_segments", lambda **kwargs: {"status": status})
        assert module.main(["--workspace-root", str(root)]) == code


@pytest.mark.parametrize("source", ["retained", "earlier_completed"])
def test_corrupted_stop_boundary_cannot_name_a_noncurrent_result(tmp_path, source):
    if source == "retained":
        root, _, paths, _ = partial(tmp_path)
    else:
        root, _, paths = workspace_fixture(tmp_path)
    control = StopControl()
    if source == "retained":
        submit(control, root)
    def on_boundary(summary):
        if (source == "earlier_completed" and summary["completed_active_segment_count"] == 1
            and summary["current_segment"] is None and summary["stop_requested"] is None):
            submit(control, root)
    summary = run_segments(workspace_root=root, paths=paths, stop_control=control,
        run_incomplete=source == "retained", runner=runner_for(root),
        run_id_factory=lambda: "stop-run", summary_writer=writer(root, [], on_boundary))
    assert summary["stage_status"] == "stopped"
    first = summary["segments"][0]
    summary["stop_requested"]["boundary_segment"] = {
        key: first[key] for key in ("segment_id", "manifest_ordinal", "active_ordinal")}
    # Retained identity must fail even inside its old interval; an earlier
    # current-run success must fail when it ended before acknowledgement.
    summary["stop_requested"]["acknowledged_elapsed_seconds"] = first["started_elapsed_seconds"] + (
        first["duration_seconds"] / 2 if source == "retained" else first["duration_seconds"] + 1)
    summary["elapsed_seconds"] = max(summary["elapsed_seconds"], summary["stop_requested"]["acknowledged_elapsed_seconds"])
    summary_path(root).write_text(json.dumps(summary))
    with pytest.raises(ValueError, match="not active in this invocation"):
        plan_incomplete(root, paths)
    result = StageResult(stage_key="run_segments", command=[], return_code=4,
        summary_path=summary_path(root), summary=summary, stdout="", stderr="")
    assert not verified_user_stop(result, expected_run_id="stop-run", prior_run_id=None)


@pytest.mark.parametrize("damage", ["later_launch", "null_active"])
def test_stop_rejects_execution_after_acknowledged_boundary(tmp_path, damage):
    root, _, paths = workspace_fixture(tmp_path, segment_count=3)
    control = StopControl()
    def boundary(summary):
        if (summary["completed_active_segment_count"] == 2
            and summary["current_segment"] is None and summary["stop_requested"] is None):
            submit(control, root)
    summary = run_segments(workspace_root=root, paths=paths, stop_control=control,
        runner=runner_for(root), run_id_factory=lambda: "stop-run",
        summary_writer=writer(root, [], boundary))
    assert summary["stage_status"] == "stopped"
    assert plan_incomplete(root, paths)["scheduled"] == ["seg_003"]
    first = summary["segments"][0]
    summary["stop_requested"]["acknowledged_elapsed_seconds"] = (
        first["started_elapsed_seconds"] + first["duration_seconds"] / 2)
    summary["stop_requested"]["boundary_segment"] = (
        {key: first[key] for key in ("segment_id", "manifest_ordinal", "active_ordinal")}
        if damage == "later_launch" else None)
    summary_path(root).write_text(json.dumps(summary))
    with pytest.raises(ValueError, match="acknowledgement"):
        plan_incomplete(root, paths)
    result = StageResult(stage_key="run_segments", command=[], return_code=4,
        summary_path=summary_path(root), summary=summary, stdout="", stderr="")
    assert not verified_user_stop(result, expected_run_id="stop-run", prior_run_id=None)
