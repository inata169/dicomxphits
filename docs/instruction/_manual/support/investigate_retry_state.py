"""Hidden Tk diagnostic; synthetic fixtures only, no external programs.

Supply a NEW --session-root outside the repository. This records existing
behavior, including the blocked downstream path; it does not repair it.
"""
from __future__ import annotations

import argparse
import inspect
import json
import os
from pathlib import Path
import sys
import time
from types import SimpleNamespace


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--session-root", type=Path, required=True)
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[4]
    session = args.session_root.resolve()
    if session == repo or repo in session.parents:
        raise ValueError("Use an isolated directory outside the repository")
    session.mkdir(parents=True, exist_ok=False)
    os.environ["DICOMXPHITS_GUI_DEFAULTS_JSON"] = str(session / "settings.json")
    sys.path[:0] = [str(repo / "src"), str(repo / "tests")]

    def audit(event, arguments):
        if event in {"subprocess.Popen", "os.system", "os.startfile"}:
            raise RuntimeError("External execution prohibited in this diagnostic")
    sys.addaudithook(audit)

    import tkinter as tk
    from tkinter import messagebox
    from dicomxphits import gui
    import dicomxphits.segment_stop as stop_module
    from dicomxphits.run_segments import run_segments, summary_path
    from dicomxphits.segment_retry import plan_incomplete
    from dicomxphits.segment_stop import StopControl
    from dicomxphits.workspace_recovery import inspect_existing_workspace
    from test_segment_retry import workspace_fixture, runner_for

    workspace, manifest, paths = workspace_fixture(session)
    control = StopControl()
    initial_calls = []
    base = runner_for(workspace, calls=initial_calls)
    def stopped_runner(command, **kwargs):
        current = json.loads(summary_path(workspace).read_text())
        control.feed(json.dumps(dict(operation="stop-after-current",
            workspace_root=str(workspace), run_id=current["run_id"],
            request_id="diagnostic-stop")).encode() + b"\n")
        return base(command, **kwargs)
    stopped = run_segments(workspace_root=workspace, paths=paths,
        stop_control=control, runner=stopped_runner)
    assert stopped["stage_status"] == "stopped"
    assert initial_calls == ["seg_001"]
    plan = plan_incomplete(workspace, paths)
    assert plan["retained"] == ["seg_001"] and plan["scheduled"] == ["seg_002"]

    defaults = gui._base_default_values()
    defaults.update(workspace_root=str(workspace), tool_profile_mode="custom",
        phits_root_folder=paths.phits_root_folder,
        phits_executable_path=paths.phits_executable_path)
    gui._default_values = lambda *a, **k: defaults.copy()
    gui._browse_directories = lambda *a, **k: {}
    # Tool presence is unrelated to the state transition under examination.
    profile = SimpleNamespace(mode="custom", ready=True, layout_id=None,
        issues=(), ready_for_stage=lambda _: True, issues_for_stage=lambda _: ())
    gui.resolve_tool_profile = lambda _: profile
    calls, errors, records = [], [], {}
    class FakePipe:
        nonce = "diagnostic-retry"
        cancel_request_id = None
        process = object()
    stop_module.ControllerPipe = FakePipe
    def fake_stage(config, key, *, control_client):
        assert key == "run_segments"
        assert Path(config.workspace_root).resolve() == workspace.resolve()
        result = run_segments(workspace_root=workspace, paths=paths,
            run_incomplete=True, expected_summary_sha256=config.retry_source_sha256,
            preflight_nonce=control_client.nonce, runner=runner_for(workspace, calls=calls))
        return gui.StageResult(key, [], 0, summary_path(workspace), result, "", "")
    gui.run_stage = fake_stage
    messagebox.showerror = lambda *a, **k: errors.append(str(a))
    original = tk.Tk
    class HiddenTk(original):
        def __init__(self):
            super().__init__()
            self.withdraw()
        def state(self, value=None):
            return "withdrawn" if value == "zoomed" else super().state(value)
        def report_callback_exception(self, kind, value, traceback):
            errors.append(repr(value))
            self.quit()
        def mainloop(self, *args):
            ui = inspect.currentframe().f_back.f_locals
            def snapshot():
                return dict(nav={k: v.get() for k, v in ui["nav_status"].items()},
                    recovery=ui["recovery_status"].get(),
                    buttons={k: not v.instate(["disabled"])
                        for k, v in ui["action_buttons"].items()})
            ui["inspect_selected_existing_workspace"]()
            records["stopped_reopened"] = snapshot()
            assert records["stopped_reopened"]["buttons"]["retry_segments"]
            ui["start_stage"]("run_segments", retry_plan=plan)
            deadline = time.monotonic() + 30
            def poll():
                if errors or time.monotonic() > deadline:
                    errors.append("Diagnostic did not finish successfully")
                    self.quit()
                elif ui["execution_guard"].active_stage is None:
                    records["after_retry"] = snapshot()
                    assert calls == ["seg_002"]
                    assert records["after_retry"]["nav"]["phits"] == "Completed"
                    assert gui.segment_execution_authorizes_sumtally(workspace)
                    records["sumtally_evidence_valid"] = True
                    assert not records["after_retry"]["buttons"]["generate_sumtally"]
                    assert not records["after_retry"]["buttons"]["recover_rtdose"]
                    inspection = inspect_existing_workspace(workspace)
                    records["fresh_inspection"] = dict(state=inspection.state, message=inspection.message)
                    assert "Matching SHA-256" in inspection.message
                    ui["inspect_selected_existing_workspace"]()
                    records["after_reinspection"] = snapshot()
                    self.quit()
                else:
                    self.after(50, poll)
            self.after(50, poll)
            super().mainloop(*args)
            self.destroy()
    tk.Tk = HiddenTk
    gui.main([])
    records.update(errors=errors, initial_calls=initial_calls, retry_calls=calls)
    (session / "result.json").write_text(json.dumps(records, indent=2), encoding="utf-8")
    assert not errors, errors
    assert records["sumtally_evidence_valid"]
    print(json.dumps(records, indent=2))


if __name__ == "__main__":
    main()
