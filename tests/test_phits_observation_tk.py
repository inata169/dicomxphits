"""Opt-in real Tk smoke test using authored data; never launches PHITS."""
import json
import os
import sys
import time
from copy import deepcopy

import pytest

from dicomxphits import gui
from dicomxphits.phits_observation import RELATIVE_PATH
from dicomxphits.segment_stop import ControllerPipe
from test_phits_live_observation import observer_fixture


@pytest.mark.skipif(os.environ.get("DICOMXPHITS_TEST_TK") != "1", reason="requires an interactive Tk desktop")
def test_real_tk_observation_updates_stale_resets_and_layout(tmp_path, monkeypatch):
    import tkinter as tk

    observer, summary = observer_fixture(tmp_path)
    observer.sample()
    record = {**observer.sample(), "sequence": 1}
    target = tmp_path / RELATIVE_PATH
    target.parent.mkdir()
    target.write_text(json.dumps(record))
    defaults = gui._base_default_values()
    defaults["workspace_root"] = str(tmp_path)
    defaults["rtdose_template_dicom"] = ""
    monkeypatch.setattr(gui, "_default_values", lambda: defaults)
    monkeypatch.setattr(gui, "_browse_directories", lambda: {})

    def forbidden(*args, **kwargs):
        raise AssertionError("external execution/settings write forbidden in Tk smoke test")

    monkeypatch.setattr(gui.subprocess, "Popen", forbidden)
    monkeypatch.setattr(gui, "run_stage", forbidden)
    monkeypatch.setattr(gui, "_save_gui_settings", forbidden)
    monkeypatch.setattr(gui, "read_summary", lambda path: summary)
    # Ownership validation has independent tests; inject its accepted result here.
    monkeypatch.setattr(gui, "select_cached_workspace_segment_progress_summary",
        lambda *args, **kwargs: (summary, summary, True))
    monkeypatch.setattr(gui, "segment_progress_run_id", lambda value: value["run_id"])
    monkeypatch.setattr(gui, "format_segment_progress", lambda *args, **kwargs: "Synthetic segment running")
    monkeypatch.setattr(gui, "format_terminal_segment_progress", lambda *args, **kwargs: "Synthetic segment ended")
    monkeypatch.setattr(gui, "select_workspace_segment_progress_summary", lambda *args, **kwargs: summary)

    def exercise(root):
        state = sys._getframe(1).f_locals
        root.title("dicomxphits synthetic observation test - NO PHITS")
        root.state("normal")
        root.geometry("1120x720")
        refresh = state["refresh_phits_progress"]
        cells = dict(zip(refresh.__code__.co_freevars, refresh.__closure__))
        cells["phits_progress_summary_path"].cell_contents = tmp_path / "analysis/segment_execution_summary.json"
        # Match the owned controller initialized by run_selected before refresh.
        # Construction does not launch a process; Popen remains forbidden above.
        cells["phits_control"].cell_contents = ControllerPipe()
        status = state["phits_observation_status"]
        presentation = state["observation_presentation"]
        guard = state["execution_guard"]
        state["show_page"]("phits")
        failures = []
        root.report_callback_exception = lambda *args: failures.append(args)

        def paint():
            refresh()
            root.update_idletasks()
            # Exercise Tk events, rather than merely checking Python strings.
            fired = []
            root.after(0, lambda: fired.append(True))
            root.update()
            assert fired and not failures

        def review_pause():
            if os.environ.get("DICOMXPHITS_GUI_REVIEW") == "1":
                done = tk.BooleanVar(root, False)
                root.after(30000, lambda: done.set(True))
                root.wait_variable(done)

        try:
            paint()
            assert "no owned active" in status.get()
            guard.begin("run_segments")
            paint()
            assert "remaining batches 9" in status.get()
            assert "median 10%" in status.get() and "provisional" in status.get()
            labels = [w for w in state["phits_frame"].winfo_children()
                if "textvariable" in w.keys() and str(w.cget("textvariable")) == str(status)]
            assert len(labels) == 1 and labels[0].winfo_ismapped()
            label = labels[0]
            for button in (state["phits_button"], state["retry_button"], state["stop_button"]):
                overlap_x = min(label.winfo_x()+label.winfo_width(), button.winfo_x()+button.winfo_width()) - max(label.winfo_x(), button.winfo_x())
                overlap_y = min(label.winfo_y()+label.winfo_height(), button.winfo_y()+button.winfo_height()) - max(label.winfo_y(), button.winfo_y())
                assert overlap_x <= 0 or overlap_y <= 0, "observation label overlaps an execution control"
            print("TK provisional and layout passed", flush=True)
            review_pause()
            updated = deepcopy(record)
            updated["sequence"] = 2
            updated["published_monotonic"] = time.monotonic()
            updated["batch"]["value"]["remaining"] = 8
            for kind in ("batch", "error"):
                updated[kind]["sample_age_seconds"] = 6
            target.write_text(json.dumps(updated))
            presentation.last_read = float("-inf")
            paint()
            assert "remaining batches 8" in status.get() and "stale" in status.get()
            print("TK stale update passed", flush=True)
            review_pause()
            summary["run_id"] = "different-invocation"
            paint()
            assert "unavailable" in status.get() and "median" not in status.get()
            state["values"]["workspace_root"].set(str(tmp_path / "different"))
            paint()
            assert "workspace selection changed" in status.get()
            state["values"]["workspace_root"].set(str(tmp_path))
            for terminal in ("success", "stopped", "failed"):
                summary["stage_status"] = terminal
                state["finish_phits_progress"](summary)
                root.update_idletasks()
                assert "no owned active" in status.get() and presentation.record is None
            guard.finish()
            paint()
            assert "no owned active" in status.get()
            print("TK invocation/workspace/terminal resets and event loop passed", flush=True)
        finally:
            root.destroy()

    monkeypatch.setattr(tk.Tk, "mainloop", exercise)
    assert gui._build_gui() == 0
