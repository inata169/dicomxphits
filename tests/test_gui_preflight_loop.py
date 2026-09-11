"""Hidden Tk integration with synthetic inputs and no external executables."""
from __future__ import annotations

import inspect
import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

from dicomxphits import gui
from dicomxphits.run_segments import run_segments, summary_path
from dicomxphits.segment_preflight import CANCEL, RELATIVE_PATH, read_receipt
from dicomxphits.segment_stop import StopControl
from dicomxphits.workspace_execution import WorkspaceBusyError, WorkspaceExecutionLease
from test_segment_retry import workspace_fixture


@pytest.mark.parametrize("read_fails", [False, True])
def test_hidden_tk_stays_responsive_during_blocked_preflight_read(tmp_path, read_fails):
    # Each case owns a fresh Tcl interpreter and cannot leave Tk objects or
    # worker callbacks in the parent pytest process.
    completed = subprocess.run(
        [sys.executable, str(Path(__file__).resolve()), str(tmp_path), str(int(read_fails))],
        cwd=Path(__file__).resolve().parents[1], capture_output=True,
        text=True, encoding="utf-8", errors="replace", timeout=25,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
    )
    if completed.returncode == 77:
        pytest.skip(completed.stdout.strip())
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "Tk preflight assertions passed" in completed.stdout
    assert not completed.stderr, completed.stderr


def _exercise_hidden_tk(tmp_path, monkeypatch, read_fails):
    tk = pytest.importorskip("tkinter")
    from tkinter import messagebox
    import dicomxphits.segment_stop as stop_module

    workspace, _, paths = workspace_fixture(tmp_path)
    library = Path(paths.phits_root_folder) / "synthetic-blocked-library"
    library.write_bytes(b"synthetic runtime")
    blocked = threading.Event()
    release = threading.Event()
    sent = threading.Event()
    closed = threading.Event()
    finished = threading.Event()
    control = StopControl()
    errors = []
    results = []
    heartbeats = []
    timings = {}
    original_open = Path.open
    workers = []
    original_thread = threading.Thread

    class TrackedThread(original_thread):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            workers.append(self)

    monkeypatch.setattr(threading, "Thread", TrackedThread)

    class BlockedRead:
        def __init__(self, stream):
            self.stream = stream
        def __enter__(self):
            return self
        def __exit__(self, *args):
            self.stream.close()
            closed.set()
        def read(self, size):
            assert size <= 1024 * 1024
            blocked.set()
            if not release.wait(10):
                raise TimeoutError("synthetic read was not released")
            if read_fails:
                raise OSError("synthetic read failure")
            return self.stream.read(size)

    def opened(path, *args, **kwargs):
        stream = original_open(path, *args, **kwargs)
        return BlockedRead(stream) if path == library else stream

    class FakePipe:
        nonce = "gui-nonce"
        cancel_request_id = None
        process = object()
        def send(self, root, run_id, *, cancel_preparation=False):
            assert cancel_preparation
            self.cancel_request_id = "gui-request"
            control.feed(json.dumps(dict(operation=CANCEL, workspace_root=root,
                run_id=run_id, gui_nonce=self.nonce, request_id=self.cancel_request_id)).encode())
            sent.set()

    def fake_stage(config, stage_key, *, control_client):
        assert stage_key == "run_segments"
        try:
            result = run_segments(workspace_root=workspace, paths=paths,
                preflight_nonce=control_client.nonce, run_id_factory=lambda: "gui-run",
                stop_control=control, runner=lambda *a, **k: pytest.fail("external child launched"))
        finally:
            finished.set()
        results.append(result)
        code = 3 if read_fails else 5
        result_path = summary_path(workspace) if read_fails else workspace / RELATIVE_PATH
        return gui.StageResult(stage_key, [], code, result_path, result, "", "")

    defaults = gui._base_default_values()
    defaults.update(workspace_root=str(workspace), tool_profile_mode="custom")
    profile = SimpleNamespace(mode="custom", ready=True, layout_id=None,
        issues=(), ready_for_stage=lambda _: True, issues_for_stage=lambda _: ())
    monkeypatch.setattr(gui, "_default_values", lambda: defaults)
    monkeypatch.setattr(gui, "_browse_directories", lambda: {})
    monkeypatch.setattr(gui, "resolve_tool_profile", lambda _: profile)
    monkeypatch.setattr(gui, "validate_stage", lambda *_: workspace)
    monkeypatch.setattr(gui, "run_stage", fake_stage)
    monkeypatch.setattr(stop_module, "ControllerPipe", FakePipe)
    monkeypatch.setattr(Path, "open", opened)
    monkeypatch.setattr(messagebox, "showerror", lambda *args: errors.append(args))

    original_tk = tk.Tk
    class HiddenTk(original_tk):
        def __init__(self):
            try:
                super().__init__()
            except tk.TclError as exc:
                if os.name != "nt" and not os.environ.get("DISPLAY"):
                    pytest.skip(f"Tk display unavailable: {exc}")
                raise
            self.withdraw()
        def state(self, value=None):
            if value == "zoomed":
                return "withdrawn"
            return super().state(value)
        def report_callback_exception(self, kind, value, traceback):
            errors.append(value)
            release.set()
            self.quit()
        def mainloop(self, *args):
            # Capture the actual builder's callbacks, not copied test callbacks.
            ui = inspect.currentframe().f_back.f_locals
            requested = False
            waiting_ticks = 0
            def tick():
                nonlocal requested, waiting_ticks
                heartbeats.append(time.monotonic())
                if blocked.is_set() and not requested:
                    ui["refresh_phits_progress"]()
                    assert "PHITS not started" in ui["phits_progress_status"].get()
                    assert not ui["action_buttons"]["cancel_preparation"].instate(["disabled"])
                    assert ui["action_buttons"]["stop_segments"].instate(["disabled"])
                    ui["request_preparation_cancel"]()
                    requested = True
                if sent.is_set() and not release.is_set():
                    waiting_ticks += 1
                    receipt = read_receipt(workspace)
                    assert receipt["phase"] != "cancelled_before_launch"
                    assert receipt["request_id"] is None
                    assert not closed.is_set()
                    assert ui["execution_guard"].active_stage == "run_segments"
                    assert ui["action_buttons"]["generate_sumtally"].instate(["disabled"])
                    with pytest.raises(WorkspaceBusyError):
                        with WorkspaceExecutionLease(workspace, create=False):
                            pass
                    if waiting_ticks == 5:
                        timings["released"] = time.monotonic()
                        release.set()
                if finished.is_set() and ui["execution_guard"].active_stage is None:
                    timings.setdefault("displayed", time.monotonic())
                    expected = "Failed" if read_fails else "Preparation cancelled"
                    assert ui["nav_status"]["phits"].get() == expected
                    assert ui["nav_status"]["rtdose"].get() == "PHITS incomplete"
                    for stage in ("generate_sumtally", "run_sumtally", "prepare_rtdose", "run_rtdose", "recover_rtdose"):
                        assert ui["action_buttons"][stage].instate(["disabled"])
                    if not read_fails:
                        assert "no PHITS launched" in ui["phits_progress_status"].get()
                    assert ui["action_buttons"]["generate_sumtally"].instate(["disabled"])
                    if not any(worker.is_alive() for worker in workers):
                        self.quit()
                        return
                self.after(10, tick)
            def timeout():
                errors.append("hidden GUI test deadline exceeded")
                release.set()
                self.quit()
            self.after(0, lambda: ui["start_stage"]("run_segments"))
            self.after(10, tick)
            self.after(8000, timeout)
            try:
                super().mainloop(*args)
            finally:
                release.set()
                for identifier in self.tk.call("after", "info"):
                    self.after_cancel(identifier)
                self.destroy()

    monkeypatch.setattr(tk, "Tk", HiddenTk)
    assert gui._build_gui() == 0
    assert not any(worker.is_alive() for worker in workers)
    if read_fails:
        assert len(errors) == 1 and isinstance(errors[0], tuple)
        assert "synthetic read failure" in str(errors[0])
    else:
        assert not errors
    assert len(heartbeats) >= 5
    assert timings["displayed"] - timings["released"] < 1.0
    assert closed.is_set()
    if read_fails:
        assert not results
        assert read_receipt(workspace)["phase"] == "failed"
        assert read_receipt(workspace)["request_id"] is None
    else:
        assert results[0]["phase"] == "cancelled_before_launch"
        assert not summary_path(workspace).exists()
    assert not read_receipt(workspace)["child_committed"]
    with WorkspaceExecutionLease(workspace, create=False):
        pass


if __name__ == "__main__":
    try:
        with pytest.MonkeyPatch.context() as patches:
            _exercise_hidden_tk(Path(sys.argv[1]), patches, bool(int(sys.argv[2])))
    except pytest.skip.Exception as exc:
        print(str(exc))
        raise SystemExit(77)
    print("Tk preflight assertions passed")
