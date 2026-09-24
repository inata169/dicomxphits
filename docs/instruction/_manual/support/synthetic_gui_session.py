"""Isolated documentation session; never launches a PHITS or other external tool.

Run with the repository's development environment. Session artifacts belong in
an explicitly supplied new directory outside the repository, never in Git.
The GUI and its validation gates are unchanged. Only external execution/control
transport and initial fixture selection are replaced in this process.
"""
from __future__ import annotations

import argparse
import inspect
import json
import os
from pathlib import Path
import sys
import threading
import time
import uuid


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--session-root", type=Path, required=True)
    parser.add_argument("--mode", choices=("layout", "stop", "cancel", "resume", "recovery"), required=True)
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[4]
    session = args.session_root.resolve()
    if session == repo or repo in session.parents:
        raise ValueError("Synthetic calculation artifacts must stay outside the repository")
    if args.mode == "resume":
        if not (session / "session.json").is_file():
            raise ValueError("Resume requires this harness's existing session")
    else:
        session.mkdir(parents=True, exist_ok=False)
    os.environ["DICOMXPHITS_GUI_DEFAULTS_JSON"] = str(session / "isolated-settings.json")
    sys.path[:0] = [str(repo / "src"), str(repo / "tests")]

    # Fail closed if an unhandled action tries to create any external process.
    def prohibit_process(event, values):
        if event in {"subprocess.Popen", "os.system", "os.startfile", "os.startfile/2"}:
            raise RuntimeError("Documentation session forbids external process execution")
    sys.addaudithook(prohibit_process)

    import tkinter as tk
    from dicomxphits import gui
    from dicomxphits.prepare_3dcrt_workspace import ExternalToolPaths
    from dicomxphits.run_segments import run_segments, summary_path
    from dicomxphits.segment_preflight import CANCEL, RELATIVE_PATH
    from dicomxphits.segment_stop import StopControl
    import dicomxphits.segment_stop as stop_module
    from test_segment_retry import workspace_fixture, runner_for

    defaults = gui._base_default_values()
    defaults["rtdose_template_dicom"] = ""
    workspace = None
    paths = None
    if args.mode != "layout":
        if args.mode == "resume":
            saved = json.loads((session / "session.json").read_text(encoding="utf-8"))
            workspace = session / saved["workspace"]
            paths = ExternalToolPaths(str(session / "synthetic-tools"),
                                      str(session / "synthetic-tools/synthetic-executable"), None)
        elif args.mode == "recovery":
            from test_manual_smoke_workflow import (
                create_successful_sumtally_workspace, write_synthetic_dicom,
                SMOKE_FRAME_UID,
            )
            from dicomxphits.prepare_rtdose import prepare_rtdose
            workspace, _, files = create_successful_sumtally_workspace(session)
            tools = session / "synthetic-tools"
            tools.mkdir()
            (tools / "synthetic-executable").write_text("never launched", encoding="utf-8")
            converter = tools / "synthetic-converter"
            converter.write_text("never launched", encoding="utf-8")
            paths = ExternalToolPaths(str(tools), str(tools / "synthetic-executable"), str(converter))
            template = session / "synthetic-template.dcm"
            ct = session / "synthetic-ct.dcm"
            write_synthetic_dicom(template, modality="RTDOSE")
            write_synthetic_dicom(ct, modality="CT", frame_uid=SMOKE_FRAME_UID)
            prepare_rtdose(workspace_root=workspace, paths=paths, paths_config={},
                           template_dicom=template, ct_reference_dicom=ct,
                           phits_out=files["phits_out"])
            defaults.update(rtdose_template_dicom=str(template), ct_reference_dicom=str(ct),
                            rtplan_path=str(workspace / "RTPLAN.dcm"),
                            phits2dicom_executable_path=str(converter))
        else:
            workspace, _, paths = workspace_fixture(session)
        defaults.update(workspace_root=str(workspace), tool_profile_mode="custom",
                        phits_root_folder=paths.phits_root_folder,
                        phits_executable_path=paths.phits_executable_path)
        for effective, saved_name in gui.CUSTOM_TOOL_SETTING_FIELDS.items():
            defaults[saved_name] = defaults.get(effective, "")
    if args.mode != "resume":
        (session / "session.json").write_text(json.dumps({
            "synthetic_only": True,
            "workspace": str(workspace.relative_to(session)) if workspace else None,
        }), encoding="utf-8")
    gui._default_values = lambda *a, **kw: defaults.copy()
    gui._browse_directories = lambda *a, **kw: {"workspace_root": str(session)}

    class SyntheticPipe:
        def __init__(self):
            self.nonce = uuid.uuid4().hex
            self.cancel_request_id = None
            self.process = object()
            self.control = StopControl()

        def send(self, root, run_id, *, cancel_preparation=False):
            if workspace is None or Path(root).resolve() != workspace.resolve():
                raise ValueError("Control request outside this synthetic session")
            request_id = uuid.uuid4().hex
            record = dict(operation="stop-after-current", workspace_root=root,
                          run_id=run_id, request_id=request_id)
            if cancel_preparation:
                self.cancel_request_id = request_id
                record.update(operation=CANCEL, gui_nonce=self.nonce)
            self.control.feed(json.dumps(record).encode() + b"\n")
            return request_id

    stop_module.ControllerPipe = SyntheticPipe
    calls = []

    def synthetic_stage(config, stage_key, *, control_client=None, **kwargs):
        if args.mode == "recovery" and stage_key == "run_rtdose":
            from dicomxphits.prepare_rtdose import run_rtdose
            from test_manual_smoke_workflow import write_coordinate_rtdose
            if Path(config.workspace_root).resolve() != workspace.resolve():
                raise ValueError("Recovery outside this synthetic session")
            class FakeConverter:
                returncode = 0
                def communicate(self, input):
                    staged_dose = Path(input.splitlines()[3])
                    write_coordinate_rtdose(staged_dose.with_suffix(".dcm"))
                    return "synthetic conversion", None
            result = run_rtdose(workspace_root=workspace, paths=paths,
                                runner=lambda *a, **kw: FakeConverter())
            calls.append(stage_key)
            (session / "runner-calls.json").write_text(json.dumps(calls), encoding="utf-8")
            return gui.StageResult(stage_key, ["synthetic-converter"], 0,
                workspace / "analysis/rtdose_conversion_execution_summary.json", result, "", "")
        if stage_key != "run_segments" or args.mode not in {"stop", "cancel", "resume"}:
            raise RuntimeError("This documentation scenario does not execute this stage")
        if Path(config.workspace_root).resolve() != workspace.resolve():
            raise ValueError("Selected workspace is outside the synthetic scenario")
        base = runner_for(workspace, calls=calls)

        def child(command, **options):
            if args.mode == "cancel":
                raise RuntimeError("Cancellation scenario must not launch a child")
            if args.mode == "stop":
                deadline = time.monotonic() + 600
                while not (session / "finish-synthetic-segment").exists():
                    if time.monotonic() > deadline:
                        raise TimeoutError("Synthetic segment wait exceeded ten minutes")
                    time.sleep(0.1)
            return base(command, **options)

        result = run_segments(
            workspace_root=workspace, paths=paths, runner=child,
            stop_control=control_client.control, preflight_nonce=control_client.nonce,
            run_incomplete=bool(config.retry_source_sha256),
            expected_summary_sha256=config.retry_source_sha256 or None,
        )
        cancelled = result.get("phase") == "cancelled_before_launch"
        code = 5 if cancelled else {"success": 0, "stopped": 4}.get(result.get("stage_status"), 3)
        target = workspace / RELATIVE_PATH if cancelled else summary_path(workspace)
        (session / "runner-calls.json").write_text(json.dumps(calls), encoding="utf-8")
        return gui.StageResult(stage_key, ["synthetic-in-process-runner"], code, target, result, "", "")

    gui.run_stage = synthetic_stage
    original_recovery = gui.run_workspace_recovery
    def synthetic_recovery(config, inspection, *, progress=None):
        return original_recovery(config, inspection, stage_runner=synthetic_stage,
                                 progress=progress)
    gui.run_workspace_recovery = synthetic_recovery
    if args.mode == "cancel":
        original_open = Path.open
        class DelayedRead:
            def __init__(self, stream):
                self.stream = stream
            def __enter__(self):
                return self
            def __exit__(self, *exc):
                self.stream.close()
            def read(self, count):
                deadline = time.monotonic() + 600
                while not (session / "finish-synthetic-read").exists():
                    if time.monotonic() > deadline:
                        raise TimeoutError("Synthetic preflight wait exceeded ten minutes")
                    time.sleep(0.1)
                return self.stream.read(count)
        def opened(path, *a, **kw):
            stream = original_open(path, *a, **kw)
            if path == Path(paths.phits_executable_path) and threading.current_thread() is not threading.main_thread():
                return DelayedRead(stream)
            return stream
        Path.open = opened

    original_tk = tk.Tk
    class DocumentationTk(original_tk):
        def title(self, text=None):
            return super().title(f"SYNTHETIC MANUAL CHECK [{args.mode}] - {text}" if text else None)
        def state(self, value=None):
            if value == "zoomed":
                return super().state()
            return super().state(value)
        def mainloop(self, *a):
            ui = inspect.currentframe().f_back.f_locals
            previous = None
            def observe():
                nonlocal previous
                snapshot = {
                    "mode": args.mode,
                    "active_stage": ui["execution_guard"].active_stage,
                    "navigation": {k: v.get() for k, v in ui["nav_status"].items()},
                    "buttons": {k: not v.instate(["disabled"]) for k, v in ui["action_buttons"].items()},
                    "progress": ui["phits_progress_status"].get(),
                    "stop": ui["phits_stop_status"].get(),
                    "recovery": ui["recovery_status"].get(),
                }
                if snapshot != previous:
                    with (session / f"ui-{args.mode}.jsonl").open("a", encoding="utf-8") as stream:
                        stream.write(json.dumps(snapshot, ensure_ascii=False) + "\n")
                    previous = snapshot
                self.after(500, observe)
            self.after(500, observe)
            super().mainloop(*a)
    tk.Tk = DocumentationTk
    gui._build_gui()


if __name__ == "__main__":
    main()
