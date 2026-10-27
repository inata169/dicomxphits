"""Own hidden Tk interpreter, synthetic evidence, and no external tools."""
from __future__ import annotations

import inspect
import os
from pathlib import Path
import subprocess
import sys

import pytest


@pytest.mark.parametrize("decision", ["yes", "no", "closed", "empty"])
def test_hidden_gui_research_review_is_responsive_and_cancel_safe(tmp_path, decision):
    result = subprocess.run(
        [sys.executable, str(Path(__file__).resolve()), str(tmp_path), decision],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
    if result.returncode == 77:
        pytest.skip(result.stdout.strip())
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Research GUI assertions passed" in result.stdout
    assert not result.stderr, result.stderr


def exercise():
    import threading
    import time
    from types import SimpleNamespace

    session, decision = Path(sys.argv[1]), sys.argv[2]
    repo = Path(__file__).resolve().parents[1]
    sys.path[:0] = [str(repo / "src"), str(repo / "tests")]
    os.environ["DICOMXPHITS_GUI_DEFAULTS_JSON"] = str(session / "settings.json")

    def prohibit(event, _arguments):
        if event in {"subprocess.Popen", "os.system", "os.startfile"}:
            raise RuntimeError("External execution forbidden in research acceptance GUI test")
    sys.addaudithook(prohibit)

    import tkinter as tk
    from tkinter import filedialog, simpledialog
    from dicomxphits import gui
    from dicomxphits.gui_dialogs import GuiMessages
    import dicomxphits.research_geometry_gui as review_module
    from dicomxphits.research_geometry_recovery import RECEIPT_PATH, validate
    from test_research_geometry_recovery import eligible, snapshot
    from dicomxphits.workspace_execution import LOCK_NAME

    workspace, _, paths, summary = eligible(session)
    def saved_evidence():
        return {p.relative_to(workspace).as_posix(): p.read_bytes()
                for p in workspace.rglob("*") if p.is_file() and p.name != LOCK_NAME}

    before = saved_evidence()
    staging = workspace / summary["segments"][0]["retained_staging"]["staging_directory"]
    defaults = gui._base_default_values()
    defaults.update(workspace_root=str(workspace), tool_profile_mode="custom",
                    phits_root_folder=paths.phits_root_folder,
                    phits_executable_path=paths.phits_executable_path)
    gui._default_values = lambda *a, **k: defaults.copy()
    gui._browse_directories = lambda *a, **k: {}
    profile = SimpleNamespace(mode="custom", ready=True, layout_id=None,
        issues=(), ready_for_stage=lambda _: True, issues_for_stage=lambda _: ())
    gui.resolve_tool_profile = lambda _: profile
    filedialog.askdirectory = lambda **kwargs: str(staging)
    simpledialog.askstring = lambda *a, **k: (None if decision == "closed" else
                                            "" if decision == "empty" else "Reviewed synthetic recoveries")
    messages, errors = [], []
    GuiMessages.showinfo = lambda *a, **k: messages.append(str(a))
    GuiMessages.showerror = lambda *a, **k: errors.append(str(a))
    GuiMessages.askyesno = lambda *a, **k: decision == "yes"
    entered, release = threading.Event(), threading.Event()
    preview = review_module.preview

    def blocked_preview(*args, **kwargs):
        entered.set()
        assert release.wait(15), "Tk event loop did not release blocked evidence read"
        return preview(*args, **kwargs)
    review_module.preview = blocked_preview
    original = tk.Tk
    checks = []
    workers = []
    original_thread = threading.Thread

    class TrackedThread(original_thread):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            workers.append(self)
    threading.Thread = TrackedThread

    class HiddenTk(original):
        def __init__(self):
            super().__init__()
            self.withdraw()

        def mainloop(self, *args, **kwargs):
            frame = inspect.currentframe().f_back
            deadline = time.monotonic() + 20
            frame.f_locals["start_research_geometry_preview"]()

            def poll():
                try:
                    assert not errors, errors
                    if entered.is_set() and not release.is_set():
                        # The event thread is running while the worker is blocked.
                        checks.append("responsive")
                        release.set()
                    state = frame.f_locals
                    idle = state["execution_guard"].active_stage is None
                    finished = (state["research_verified_workspace"] == workspace and not state["sumtally_readiness_active"]
                                if decision == "yes" else bool(messages) and idle)
                    if finished:
                        assert checks == ["responsive"]
                        assert all((workspace / path).read_bytes() == data for path, data in before.items())
                        assert "failed" in state["nav_status"]["phits"].get().lower() if decision == "yes" else True
                        if decision == "yes":
                            assert "RESEARCH ONLY" in state["research_status"].get()
                        else:
                            assert not (workspace / RECEIPT_PATH).exists()
                            assert saved_evidence() == before
                        checks.append("complete")
                        state["close_gui"]()
                        return
                    assert time.monotonic() < deadline, "GUI review did not finish"
                    self.after(10, poll)
                except BaseException as exc:
                    errors.append(repr(exc))
                    release.set()
                    self.destroy()
            self.after(5, poll)
            return super().mainloop(*args, **kwargs)

    tk.Tk = HiddenTk
    try:
        gui._build_gui()
    except tk.TclError as exc:
        print(f"Tk unavailable: {exc}")
        return 77
    assert not errors, errors
    assert checks == ["responsive", "complete"], checks
    for worker in workers:
        worker.join(5)
    assert not any(worker.is_alive() for worker in workers)
    if decision == "yes":
        validate(workspace)
    print("Research GUI assertions passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(exercise())
