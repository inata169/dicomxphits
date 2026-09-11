from __future__ import annotations

import hashlib
import json
import os
import subprocess
from copy import deepcopy
from pathlib import Path

import pytest

from dicomxphits.run_segments import run_segments, summary_path
from dicomxphits.segment_preflight import (
    CANCEL, RELATIVE_PATH, PreparationCancelled, Session, read_receipt,
    require_current_result, validate_receipt,
)
from dicomxphits.segment_stop import StopControl
from dicomxphits.sumtally_inputs import file_sha256
from dicomxphits.workspace_execution import WorkspaceExecutionLease
from dicomxphits.workspace_recovery import validate_segment_execution_for_downstream
from test_segment_retry import workspace_fixture, runner_for, partial


@pytest.mark.skipif(os.name != "nt", reason="Windows receipt replacement policy")
@pytest.mark.parametrize("denials,code", [(1, 5), (2, 32), (3, 5), (1, 112)])
def test_receipt_replace_retry_bound(tmp_path, monkeypatch, denials, code):
    from dicomxphits import safe_output
    session = Session(tmp_path, "nonce", "run", None)
    session.publish(force=True)
    path = tmp_path / RELATIVE_PATH
    old = path.read_bytes()
    replace = os.replace
    calls, waits = [], []

    def replace_with_denial(source, target):
        calls.append((source, target, Path(source).read_bytes()))
        if len(calls) <= denials:
            error = OSError("synthetic replacement denial")
            error.winerror = code
            raise error
        replace(source, target)

    monkeypatch.setattr(safe_output.os, "replace", replace_with_denial)
    monkeypatch.setattr(safe_output.time, "sleep", waits.append)
    if denials == 3 or code == 112:
        with pytest.raises(OSError):
            session.publish(force=True)
        assert path.read_bytes() == old
    else:
        session.publish(force=True)
        assert read_receipt(tmp_path)["sequence"] == 2
    expected = 1 if code == 112 else min(denials + 1, 3)
    assert len(calls) == expected
    assert waits == [0.05] * (expected - 1)
    assert len({(str(a), str(b), data) for a, b, data in calls}) == 1
    assert not list(path.parent.glob("*.tmp"))


@pytest.mark.skipif(os.name != "nt", reason="Windows native file sharing")
@pytest.mark.parametrize("release_on_wait", [True, False])
def test_receipt_native_reader_contention(tmp_path, monkeypatch, release_on_wait):
    from dicomxphits import safe_output
    session = Session(tmp_path, "nonce", "run", None)
    session.publish(force=True)
    path = tmp_path / RELATIVE_PATH
    old = path.read_bytes()
    stream = path.open("rb")
    waits = []

    def wait(delay):
        waits.append(delay)
        if release_on_wait:
            stream.close()

    monkeypatch.setattr(safe_output.time, "sleep", wait)
    try:
        if release_on_wait:
            session.publish(force=True)
            assert read_receipt(tmp_path)["sequence"] == 2
            assert waits == [0.05]
        else:
            with pytest.raises(PermissionError) as caught:
                session.publish(force=True)
            assert caught.value.winerror == 5
            assert path.read_bytes() == old
            assert waits == [0.05, 0.05]
    finally:
        stream.close()
    assert not list(path.parent.glob("*.tmp"))


def test_other_output_does_not_retry_replace(tmp_path, monkeypatch):
    from dicomxphits import safe_output
    calls, waits = [], []

    def deny(*args):
        calls.append(args)
        error = OSError("synthetic replacement denial")
        error.winerror = 5
        raise error

    monkeypatch.setattr(safe_output.os, "replace", deny)
    monkeypatch.setattr(safe_output.time, "sleep", waits.append)
    with safe_output.WorkspaceOutputGuard(tmp_path) as guard:
        with pytest.raises(OSError):
            guard.write_json(tmp_path / "analysis/segment_execution_summary.json", {})
    assert len(calls) == 1
    assert waits == []


@pytest.mark.skipif(os.name != "nt", reason="Windows receipt replacement policy")
def test_receipt_retry_rechecks_guard(tmp_path, monkeypatch):
    from dicomxphits import safe_output
    session = Session(tmp_path, "nonce", "run", None)
    session.publish(force=True)
    path = tmp_path / RELATIVE_PATH
    old = path.read_bytes()
    prepare = safe_output.WorkspaceOutputGuard.prepare_file_target
    calls, waits = [], []

    def deny(*args):
        calls.append(args)
        error = OSError("synthetic sharing denial")
        error.winerror = 5
        raise error

    def recheck(guard, target, **kwargs):
        if calls:
            raise safe_output.UnsafeWorkspacePathError("synthetic changed boundary")
        return prepare(guard, target, **kwargs)

    monkeypatch.setattr(safe_output.os, "replace", deny)
    monkeypatch.setattr(safe_output.time, "sleep", waits.append)
    monkeypatch.setattr(safe_output.WorkspaceOutputGuard, "prepare_file_target", recheck)
    with pytest.raises(safe_output.UnsafeWorkspacePathError):
        session.publish(force=True)
    assert len(calls) == 1
    assert waits == [0.05]
    assert path.read_bytes() == old
    assert not list(path.parent.glob("*.tmp"))


@pytest.mark.skipif(os.name != "nt", reason="Windows receipt replacement policy")
def test_denied_cancellation_receipt_is_not_acknowledged(tmp_path, monkeypatch):
    from dicomxphits import safe_output
    session = Session(tmp_path, "nonce", "run", None)
    session.publish(force=True)
    calls, waits = [], []

    def deny(*args):
        calls.append(args)
        error = OSError("synthetic persistent sharing denial")
        error.winerror = 5
        raise error

    monkeypatch.setattr(safe_output.os, "replace", deny)
    monkeypatch.setattr(safe_output.time, "sleep", waits.append)
    with pytest.raises(OSError):
        session.handle_cancel(dict(operation=CANCEL, workspace_root=str(tmp_path.resolve()),
            run_id="run", request_id="cancel", gui_nonce="nonce"))
    assert len(calls) == 3
    assert waits == [0.05, 0.05]
    receipt = read_receipt(tmp_path)
    assert receipt["phase"] == "preparing"
    assert receipt["request_id"] is None
    with pytest.raises(ValueError):
        require_current_result(tmp_path, {})


def cancel(control, root, **changes):
    request = dict(operation=CANCEL, workspace_root=str(root.resolve()),
        run_id="preflight-run", gui_nonce="nonce", request_id="cancel-1")
    request.update(changes)
    control.feed(json.dumps(request).encode())


def test_cancel_before_scan_never_launches_or_fabricates_binding(tmp_path):
    root, manifest, paths = workspace_fixture(tmp_path)
    control = StopControl()
    cancel(control, root)
    result = run_segments(workspace_root=root, paths=paths, preflight_nonce="nonce",
        run_id_factory=lambda: "preflight-run", stop_control=control,
        runner=lambda *a, **k: pytest.fail("PHITS launched"))
    assert result["phase"] == "cancelled_before_launch"
    assert result["scanned_bytes"] == 0
    assert result["child_committed"] is False
    assert not summary_path(root).exists()
    assert read_receipt(root, nonce="nonce") == result
    with pytest.raises(ValueError):
        validate_segment_execution_for_downstream(root, manifest, {})
    with WorkspaceExecutionLease(root, create=False):
        pass


def test_cancel_during_large_hash_is_bounded_and_preserves_source(tmp_path, monkeypatch):
    root, _, paths, original = partial(tmp_path)
    source_bytes = summary_path(root).read_bytes()
    source_mtime = summary_path(root).stat().st_mtime_ns
    runtime = tmp_path / "large.bin"
    runtime.write_bytes(b"x" * (5 * 1024 * 1024))
    control = StopControl()
    original_checkpoint = Session.checkpoint

    def checkpoint(session, *, files=0, size=0):
        if size:
            assert size <= 1024 * 1024
            cancel(control, root)
        return original_checkpoint(session, files=files, size=size)

    monkeypatch.setattr(Session, "checkpoint", checkpoint)
    with WorkspaceExecutionLease(root):
        with Session(root, "nonce", "preflight-run", control) as session:
            with pytest.raises(PreparationCancelled):
                file_sha256(runtime)
            assert session.receipt["scanned_bytes"] <= 1024 * 1024
    assert summary_path(root).read_bytes() == source_bytes
    assert summary_path(root).stat().st_mtime_ns == source_mtime
    with pytest.raises(ValueError):
        require_current_result(root, original)


@pytest.mark.parametrize("changes", [{"gui_nonce": "stale"}, {"run_id": "old"},
    {"workspace_root": "elsewhere"}, {"request_id": ""}, {"extra": 1}])
def test_invalid_cancel_does_not_interrupt_scan(tmp_path, changes):
    root, _, _ = workspace_fixture(tmp_path)
    control = StopControl(report=lambda _: None)
    cancel(control, root, **changes)
    with WorkspaceExecutionLease(root):
        with Session(root, "nonce", "preflight-run", control) as session:
            session.checkpoint()
            assert session.receipt["request_id"] is None


def test_commitment_wins_cancel_race(tmp_path):
    root, _, _ = workspace_fixture(tmp_path)
    rejected = []
    control = StopControl(report=rejected.append)
    with WorkspaceExecutionLease(root):
        with Session(root, "nonce", "preflight-run", control) as session:
            session.commit()
            cancel(control, root)
            session.checkpoint()
            assert session.receipt["child_committed"]
            assert session.receipt["request_id"] is None
    assert rejected


def test_success_binds_terminal_receipt_and_downstream(tmp_path):
    root, manifest, paths = workspace_fixture(tmp_path)
    result = run_segments(workspace_root=root, paths=paths, preflight_nonce="nonce",
        runner=runner_for(root), run_id_factory=lambda: "preflight-run")
    assert result["status"] == "success"
    receipt = read_receipt(root)
    assert receipt["phase"] == "finished" and receipt["child_committed"]
    assert receipt["summary_sha256"] == hashlib.sha256(summary_path(root).read_bytes()).hexdigest()
    require_current_result(root, result)
    validate_segment_execution_for_downstream(root, manifest, result)


def test_embedded_secondary_tally_error_does_not_require_companion_file(tmp_path):
    root, manifest, paths = workspace_fixture(tmp_path, segment_count=1)
    segment = manifest["segments"][0]
    source = root / segment["phits_input_path"]
    secondary = Path(segment["expected_output_path"]).with_name("deposit-pdd.out")
    source.write_text(
        source.read_text(encoding="utf-8").replace(
            "[ E N D ]",
            f"[ T-Deposit ]\n  file = {secondary.as_posix()}\n[ E N D ]",
        ),
        encoding="utf-8",
    )

    def runner(command, **kwargs):
        staging = Path(kwargs["cwd"])
        expected = staging / segment["expected_output_path"]
        expected.parent.mkdir(parents=True, exist_ok=True)
        expected.write_text("dose\n", encoding="utf-8")
        expected.with_name("deposit-target-3D_err.out").write_text(
            "error\n", encoding="utf-8"
        )
        (staging / secondary).write_text(
            "# z-lower z-upper all r.err\n0.0 0.3 1.0 0.1\n",
            encoding="utf-8",
        )
        (staging / "phits.out").write_text(
            "Number of lost particles     =     0 / nlost =    10000\n"
            "Number of geometry recovering = 0\n"
            "Number of unrecovered errors = 0\n",
            encoding="utf-8",
        )
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    result = run_segments(workspace_root=root, paths=paths, runner=runner)

    required = result["execution_binding"]["segments"][0]["required_outputs"]
    assert secondary.as_posix() in required
    assert secondary.with_name("deposit-pdd_err.out").as_posix() not in required
    assert Path(segment["expected_output_path"]).with_name(
        "deposit-target-3D_err.out"
    ).as_posix() in required
    assert result["status"] == "success"
    assert "r.err" in (root / secondary).read_text(encoding="utf-8")
    validate_segment_execution_for_downstream(root, manifest, result)


@pytest.mark.parametrize("field,value", [("schema_version", "future"), ("scanned_bytes", -1),
    ("sequence", True), ("elapsed_seconds", float("nan")), ("child_committed", 0),
    ("request_id", "bad\nrequest"), ("phase", "success")])
def test_strict_receipt_validation(tmp_path, field, value):
    root, _, _ = workspace_fixture(tmp_path)
    with WorkspaceExecutionLease(root):
        with Session(root, "nonce", "preflight-run", None) as session:
            receipt = deepcopy(session.receipt)
    receipt[field] = value
    with pytest.raises((ValueError, TypeError)):
        validate_receipt(receipt)


def test_incomplete_or_changed_receipt_blocks_historical_success(tmp_path):
    root, _, paths = workspace_fixture(tmp_path)
    success = run_segments(workspace_root=root, paths=paths, runner=runner_for(root))
    with WorkspaceExecutionLease(root):
        with Session(root, "nonce", "preflight-run", None):
            pass
    with pytest.raises(ValueError):
        require_current_result(root, success)
    (root / RELATIVE_PATH).write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError):
        require_current_result(root, success)


def test_cancellation_write_failure_is_not_success(tmp_path, monkeypatch):
    root, _, _ = workspace_fixture(tmp_path)
    control = StopControl()
    import dicomxphits.prepare_3dcrt_workspace as preparation
    write = preparation.write_json

    def fail(path, value, **kwargs):
        if value.get("phase") == "cancelled_before_launch":
            raise OSError("synthetic receipt write failure")
        write(path, value, **kwargs)

    monkeypatch.setattr(preparation, "write_json", fail)
    with WorkspaceExecutionLease(root):
        with pytest.raises(OSError):
            with Session(root, "nonce", "preflight-run", control) as session:
                cancel(control, root)
                session.checkpoint()
    assert read_receipt(root)["phase"] == "failed"


def test_selective_preflight_cancel_preserves_original_attempt(tmp_path, monkeypatch):
    root, _, paths, _ = partial(tmp_path)
    before = summary_path(root).read_bytes()
    mtime = summary_path(root).stat().st_mtime_ns
    control = StopControl()
    original_checkpoint = Session.checkpoint

    def checkpoint(session, *, files=0, size=0):
        if size:
            cancel(control, root)
        return original_checkpoint(session, files=files, size=size)

    monkeypatch.setattr(Session, "checkpoint", checkpoint)
    receipt = run_segments(workspace_root=root, paths=paths, preflight_nonce="nonce",
        run_incomplete=True, run_id_factory=lambda: "preflight-run", stop_control=control,
        runner=lambda *a, **k: pytest.fail("launched"))
    assert receipt["phase"] == "cancelled_before_launch"
    assert summary_path(root).read_bytes() == before
    assert summary_path(root).stat().st_mtime_ns == mtime


def test_stop_is_acknowledged_inside_post_child_verification(tmp_path, monkeypatch):
    root, manifest, paths = workspace_fixture(tmp_path)
    control = StopControl()
    original_checkpoint = Session.checkpoint
    queued = False
    witnessed = []

    def checkpoint(session, *, files=0, size=0):
        nonlocal queued
        if size and session.receipt["child_committed"] and session.receipt["phase"] == "verifying" and not queued:
            queued = True
            control.feed(json.dumps(dict(operation="stop-after-current", workspace_root=str(root.resolve()),
                run_id="preflight-run", request_id="stop-1")).encode())
            original_checkpoint(session, files=files, size=size)
            witnessed.append(json.loads(summary_path(root).read_text(encoding="utf-8"))["stop_requested"])
            return
        original_checkpoint(session, files=files, size=size)

    monkeypatch.setattr(Session, "checkpoint", checkpoint)
    calls = []
    result = run_segments(workspace_root=root, paths=paths, preflight_nonce="nonce",
        run_id_factory=lambda: "preflight-run", stop_control=control, runner=runner_for(root, calls=calls))
    assert witnessed and witnessed[0]["request_id"] == "stop-1"
    assert len(calls) == 1
    assert result["status"] == "stopped"
    assert result["segments"][0]["status"] == "success"
    assert result["segments"][1]["status"] == "pending"
    assert read_receipt(root)["phase"] == "finished"
    with pytest.raises(ValueError):
        validate_segment_execution_for_downstream(root, manifest, result)


def test_same_size_same_mtime_runtime_mutation_is_detected(tmp_path):
    from dicomxphits.segment_retry import capture_binding, validate_binding
    import os
    root, manifest, paths = workspace_fixture(tmp_path)
    library = Path(paths.phits_root_folder) / "extra-library"
    library.write_bytes(b"abcd")
    binding = capture_binding(root, manifest, paths)
    stamp = library.stat()
    library.write_bytes(b"abce")
    os.utime(library, ns=(stamp.st_atime_ns, stamp.st_mtime_ns))
    with pytest.raises(ValueError, match="changed"):
        validate_binding(root, manifest, binding, paths)


def test_many_files_enumeration_has_per_entry_checkpoints(tmp_path, monkeypatch):
    from dicomxphits.segment_retry import _runtime_files
    import dicomxphits.segment_preflight as module
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    for index in range(30):
        (runtime / str(index)).write_bytes(b"x")
    checkpoints = []
    monkeypatch.setattr(module, "checkpoint", lambda **kwargs: checkpoints.append(kwargs))
    assert len(list(_runtime_files(runtime, tmp_path / "workspace"))) == 30
    assert len(checkpoints) >= 31


@pytest.mark.parametrize("scan_kind", ["enumerate", "hash"])
def test_cancel_at_every_scanner_checkpoint_prevents_commit(tmp_path, monkeypatch, scan_kind):
    from contextlib import closing
    from dicomxphits.segment_retry import _runtime_files

    root, _, paths = workspace_fixture(tmp_path)
    runtime = Path(paths.phits_root_folder)
    large = runtime / "large.bin"
    large.write_bytes(b"x" * (2 * 1024 * 1024 + 17))
    before = {path: (path.read_bytes(), path.stat().st_mtime_ns)
        for path in runtime.iterdir()}
    original = Session.checkpoint
    checkpoints = 0
    cancel_at = None
    control = StopControl()

    def checkpoint(session, **kwargs):
        nonlocal checkpoints
        checkpoints += 1
        if checkpoints == cancel_at:
            cancel(control, root)
        return original(session, **kwargs)

    def scan():
        if scan_kind == "hash":
            file_sha256(large)
        else:
            with closing(_runtime_files(runtime, root)) as entries:
                list(entries)

    monkeypatch.setattr(Session, "checkpoint", checkpoint)
    with WorkspaceExecutionLease(root):
        with Session(root, "nonce", "preflight-run", control) as session:
            scan()
            session.commit()
    checkpoint_count = checkpoints
    assert checkpoint_count > 1
    for cancel_at in range(1, checkpoint_count + 1):
        checkpoints = 0
        with WorkspaceExecutionLease(root):
            with pytest.raises(PreparationCancelled):
                with Session(root, "nonce", "preflight-run", control) as session:
                    scan()
                    session.commit()
                    pytest.fail("Cancellation allowed first commitment")
        receipt = read_receipt(root, nonce="nonce")
        assert receipt["phase"] == "cancelled_before_launch"
        assert receipt["request_id"] == "cancel-1"
        assert not receipt["child_committed"]
        assert checkpoints == cancel_at
        assert not summary_path(root).exists()
        with pytest.raises(ValueError):
            require_current_result(root, {})
        with WorkspaceExecutionLease(root, create=False):
            pass
    assert all((path.read_bytes(), path.stat().st_mtime_ns) == evidence
        for path, evidence in before.items())


def test_hash_progress_is_published_before_scan_finishes(tmp_path, monkeypatch):
    import dicomxphits.segment_preflight as module

    root, _, _ = workspace_fixture(tmp_path)
    data = b"x" * (3 * 1024 * 1024 + 17)
    source = tmp_path / "large.bin"
    source.write_bytes(data)
    original = Session.checkpoint
    clock = [0.0]
    snapshots = []
    monkeypatch.setattr(module.time, "monotonic", lambda: clock[0])

    def checkpoint(session, **kwargs):
        clock[0] += 0.25
        original(session, **kwargs)
        snapshots.append(read_receipt(root, nonce="nonce"))

    monkeypatch.setattr(Session, "checkpoint", checkpoint)
    with WorkspaceExecutionLease(root):
        with Session(root, "nonce", "preflight-run", None):
            assert file_sha256(source) == hashlib.sha256(data).hexdigest()
    assert any(0 < r["scanned_bytes"] < len(data) and r["scanned_files"] == 0
        for r in snapshots)
    assert snapshots[-1]["scanned_bytes"] == len(data)
    assert snapshots[-1]["scanned_files"] == 1
    assert all(r["phase"] == "preparing" and not r["child_committed"] for r in snapshots)


@pytest.mark.parametrize("mutation", ["add", "remove", "rename"])
def test_runtime_membership_mutations_fail_closed(tmp_path, mutation):
    from dicomxphits.segment_retry import capture_binding, validate_binding

    root, manifest, paths = workspace_fixture(tmp_path)
    runtime = Path(paths.phits_root_folder)
    binding = capture_binding(root, manifest, paths)
    library = runtime / "synthetic-library"
    if mutation == "add":
        (runtime / "added-library").write_bytes(b"synthetic extra dependency")
    elif mutation == "remove":
        library.unlink()
    else:
        library.rename(runtime / "renamed-library")
    with pytest.raises(ValueError, match="changed"):
        validate_binding(root, manifest, binding, paths)


def test_gui_tracker_remembers_high_water_mark_after_invalid_read(tmp_path):
    from dicomxphits.segment_preflight import ReceiptTracker
    tracker = ReceiptTracker()
    receipt = Session(tmp_path, "nonce", "run-1", None).receipt
    receipt.update(sequence=10, scanned_bytes=100, elapsed_seconds=2.0)
    tracker.accept(receipt, root=tmp_path, nonce="nonce")
    for invalid in (None, {}, dict(receipt, gui_nonce="old"),
        dict(receipt, sequence=9), dict(receipt, sequence=11, run_id="other"),
        dict(receipt, sequence=11, scanned_bytes=99),
        dict(receipt, scanned_files=1)):
        with pytest.raises((TypeError, ValueError)):
            tracker.accept(invalid, root=tmp_path, nonce="nonce")
        assert tracker.last == receipt
    assert tracker.accept(dict(receipt, sequence=11), root=tmp_path, nonce="nonce")["sequence"] == 11


@pytest.mark.parametrize("changes", [{}, {"gui_nonce": "old"}, {"run_id": "old"},
    {"request_id": "other"}, {"phase": "preparing"}, {"child_committed": True},
    {"schema_version": "future"}, {"workspace_root": "elsewhere"}])
def test_gui_cancellation_requires_matching_terminal_evidence(tmp_path, changes):
    from dicomxphits.segment_preflight import validate_gui_cancellation
    receipt = dict(Session(tmp_path, "nonce", "run-1", None).receipt,
        phase="cancelled_before_launch", request_id="request-1")
    receipt.update(changes)
    kwargs = dict(root=tmp_path, nonce="nonce", run_id="run-1", request_id="request-1")
    if changes:
        with pytest.raises(ValueError):
            validate_gui_cancellation(receipt, **kwargs)
    else:
        assert validate_gui_cancellation(receipt, **kwargs) == receipt
        with pytest.raises(ValueError):
            validate_gui_cancellation(receipt, **dict(kwargs, request_id=None))
        with pytest.raises(ValueError):
            validate_gui_cancellation(receipt, **dict(kwargs, run_id=None))


def test_duplicate_cancel_is_terminal_and_never_commits(tmp_path):
    root, _, paths = workspace_fixture(tmp_path)
    control = StopControl()
    cancel(control, root)
    cancel(control, root)
    receipt = run_segments(workspace_root=root, paths=paths,
        preflight_nonce="nonce", run_id_factory=lambda: "preflight-run",
        stop_control=control, runner=lambda *a, **k: pytest.fail("launched"))
    assert receipt["phase"] == "cancelled_before_launch"
    assert receipt["request_id"] == "cancel-1"
    assert not receipt["child_committed"]


def test_controller_failure_does_not_fabricate_cancellation(tmp_path):
    root, _, paths = workspace_fixture(tmp_path)
    class BrokenControl:
        def take(self):
            raise OSError("synthetic controller failure")
        def close(self):
            pass
    with pytest.raises(OSError, match="controller failure"):
        run_segments(workspace_root=root, paths=paths, preflight_nonce="nonce",
            stop_control=BrokenControl(), runner=lambda *a, **k: pytest.fail("launched"))
    receipt = read_receipt(root)
    assert receipt["phase"] == "failed"
    assert receipt["request_id"] is None
    assert not summary_path(root).exists()
    with WorkspaceExecutionLease(root, create=False):
        pass


def test_cli_cancel_exit_five_without_external_execution(tmp_path, monkeypatch, capsys):
    import importlib
    module = importlib.import_module("dicomxphits.run_segments")
    root, _, paths = workspace_fixture(tmp_path)
    original = module.run_segments
    def controlled(**kwargs):
        # The wrapper recurses without the nonce to perform actual preparation.
        if kwargs.get("preflight_nonce"):
            control = StopControl()
            cancel(control, root)
            kwargs.update(stop_control=control, run_id_factory=lambda: "preflight-run",
                runner=lambda *a, **k: pytest.fail("launched"))
        return original(**kwargs)
    monkeypatch.setattr(module, "run_segments", controlled)
    monkeypatch.setattr(module, "paths_from_args", lambda _: paths)
    assert module.main(["--workspace-root", str(root), "--preflight-nonce", "nonce"]) == 5
    assert str(root / RELATIVE_PATH) in capsys.readouterr().out
    assert read_receipt(root)["phase"] == "cancelled_before_launch"


def test_relocated_cancelled_receipt_cannot_authorize_historical_success(tmp_path):
    root, _, paths = workspace_fixture(tmp_path)
    result = run_segments(workspace_root=root, paths=paths, runner=runner_for(root))
    control = StopControl()
    cancel(control, root)
    run_segments(workspace_root=root, paths=paths, preflight_nonce="nonce",
        run_id_factory=lambda: "preflight-run", stop_control=control,
        runner=lambda *a, **k: pytest.fail("launched"))
    relocated = root.with_name("relocated")
    root.rename(relocated)
    with pytest.raises(ValueError, match="workspace changed"):
        require_current_result(relocated, result)


@pytest.mark.parametrize("selective", [False, True])
def test_cancel_then_explicit_fresh_preflight_can_complete(tmp_path, selective):
    from dicomxphits.segment_retry import plan_incomplete
    if selective:
        root, manifest, paths, _ = partial(tmp_path)
    else:
        root, manifest, paths = workspace_fixture(tmp_path)
    existing = {path: (path.read_bytes(), path.stat().st_mtime_ns)
        for path in root.rglob("*") if path.is_file() and path.name != ".dicomxphits-execution.lock"}
    control = StopControl()
    cancel(control, root)
    receipt = run_segments(workspace_root=root, paths=paths, preflight_nonce="nonce",
        run_id_factory=lambda: "preflight-run", stop_control=control,
        run_incomplete=selective, runner=lambda *a, **k: pytest.fail("launched during cancellation"))
    assert receipt["phase"] == "cancelled_before_launch"
    assert all((path.read_bytes(), path.stat().st_mtime_ns) == evidence
        for path, evidence in existing.items())
    expected = None
    if selective:
        plan = plan_incomplete(root, paths)
        expected = plan["source_sha256"]
        assert plan["scheduled"] == ["seg_002"]
    calls = []
    result = run_segments(workspace_root=root, paths=paths, preflight_nonce="fresh-nonce",
        run_id_factory=lambda: "fresh-run", run_incomplete=selective,
        expected_summary_sha256=expected, runner=runner_for(root, calls=calls))
    assert calls == (["seg_002"] if selective else ["seg_001", "seg_002"])
    assert read_receipt(root)["gui_nonce"] == "fresh-nonce"
    validate_segment_execution_for_downstream(root, manifest, result)
    from dicomxphits.gui import rtdose_stage_state, RTDOSE_PHITS_INCOMPLETE
    assert rtdose_stage_state(root) != RTDOSE_PHITS_INCOMPLETE
    if selective:
        retained_paths = [path for path in existing if "seg_001" in path.parts]
        assert retained_paths
        assert all((path.read_bytes(), path.stat().st_mtime_ns) == existing[path]
            for path in retained_paths)
