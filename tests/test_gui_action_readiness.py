"""Synthetic readiness checks without opening a GUI or launching external tools."""

import ast
import inspect
import json
import queue
import threading
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest

from dicomxphits import gui
from test_gui import base_config
from test_prepare_sumtally import generate_sumtally, paths, write_workspace


@pytest.mark.parametrize("overwrite", [False, True])
def test_ordinary_phits_button_protects_existing_record(tmp_path, overwrite):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    config = base_config(tmp_path, workspace=workspace, allow_overwrite=overwrite)
    assert gui.run_action_ready(config, "run_segments")
    record = workspace / "analysis/segment_execution_summary.json"
    record.parent.mkdir()
    record.write_text('{"stage_status":"success"}', encoding="utf-8")
    assert not gui.run_action_ready(config, "run_segments")
    assert not gui.run_action_ready(replace(config, retry_source_sha256="a" * 64), "run_segments")


@pytest.mark.parametrize("damage", [
    "none", "missing", "malformed", "failed", "wrapper", "input",
    "manifest", "output", "phits_incomplete", "execution_record",
])
def test_sumtally_button_requires_current_generation_without_writing(tmp_path, damage):
    workspace, manifest = write_workspace(tmp_path)
    config = base_config(tmp_path, workspace=workspace)
    assert not gui.run_action_ready(config, "run_sumtally")
    generation = generate_sumtally(workspace_root=workspace, paths=paths())
    record = workspace / "analysis/sumtally_generation_summary.json"
    if damage == "missing":
        record.unlink()
    elif damage == "malformed":
        record.write_text("{", encoding="utf-8")
    elif damage == "failed":
        generation["stage_status"] = "failed"
        record.write_text(json.dumps(generation), encoding="utf-8")
    elif damage in {"wrapper", "input"}:
        field = "sum_input" if damage == "wrapper" else "sumtally_input"
        target = Path(generation["outputs"][field])
        target.write_text(target.read_text(encoding="utf-8") + "\n$ changed\n", encoding="utf-8")
    elif damage == "manifest":
        manifest["case_id"] = "changed"
        (workspace / "segments/segment_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    elif damage == "output":
        (workspace / manifest["segments"][0]["expected_output_path"]).write_text("changed", encoding="utf-8")
    elif damage == "phits_incomplete":
        (workspace / "analysis/segment_execution_summary.json").write_text('{"stage_status":"running"}', encoding="utf-8")
    elif damage == "execution_record":
        (workspace / "analysis/sumtally_execution_summary.json").write_text("{}", encoding="utf-8")

    def snapshot():
        return {p.relative_to(workspace): (p.read_bytes(), p.stat().st_mtime_ns)
                for p in workspace.rglob("*") if p.is_file()}

    before = snapshot()
    assert gui.run_action_ready(config, "run_sumtally") is (damage == "none")
    if damage == "execution_record":
        assert gui.run_action_ready(replace(config, allow_overwrite=True), "run_sumtally")
    assert snapshot() == before


class Value:
    def __init__(self, value):
        self.value = value

    def get(self):
        return self.value

    def set(self, value):
        self.value = value


def callbacks(names, state):
    """Execute a real nested callback with synthetic closure variables, without Tk."""
    tree = ast.parse(inspect.getsource(gui._build_gui))
    nodes = [next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == name)
             for name in names]

    class SyntheticClosure(ast.NodeTransformer):
        def visit_Nonlocal(self, node):
            return ast.Global(names=node.names)

    nodes = [SyntheticClosure().visit(node) for node in nodes]
    namespace = {**vars(gui), **state}
    code = compile(ast.fix_missing_locations(ast.Module(body=nodes, type_ignores=[])), "<gui-callback>", "exec")
    exec(code, namespace)
    return namespace


def callback(name, state):
    namespace = callbacks([name], state)
    return namespace[name]


@pytest.mark.parametrize("status", ["success", "failed", "gate_failed", "running", None])
@pytest.mark.parametrize("matches", [False, True])
def test_terminal_callback_clears_previous_stop_available_hint(status, matches):
    hint = Value("Stop after current segment is available.")
    selected = {"stage_status": status, "run_id": "synthetic"} if status else None
    finish = callback("finish_phits_progress", {
        "observation_presentation": SimpleNamespace(reset=lambda: None),
        "phits_observation_status": Value(""), "phits_stop_status": hint,
        "values": {"workspace_root": Value("synthetic")},
        "phits_progress_summary_path": Path("synthetic/analysis/segment_execution_summary.json"),
        "progress_workspace_matches": lambda *args: matches,
        "phits_progress_run_id": "synthetic", "phits_progress_prior_run_id": None,
        "select_workspace_segment_progress_summary": lambda *args, **kwargs: selected,
        "format_terminal_segment_progress": lambda *args, **kwargs: "Terminal",
        "phits_progress_status": Value("Running"),
    })
    finish({"stage_status": status})
    assert hint.get() == gui.terminal_stop_hint(selected if matches else None)
    assert "is available" not in hint.get()


@pytest.mark.parametrize("ready", [False, True])
@pytest.mark.parametrize("busy", [False, True])
def test_run_buttons_use_readiness_and_busy_gates(ready, busy):
    states = {}
    actions = {key: SimpleNamespace(state=lambda value, key=key: states.update({key: value}))
               for key in ("run_segments", "run_sumtally")}
    refresh = callback("refresh_action_button_states", {
        "execution_guard": SimpleNamespace(active_stage="run_segments" if busy else None),
        "current_rtdose_state": lambda: gui.RTDOSE_NOT_PREPARED,
        "current_structure_binding_ready": lambda: False,
        "structure_frame": None, "nav_status": {"rtdose": Value("Not run")},
        "tool_profile_resolution": SimpleNamespace(ready_for_stage=lambda key: True),
        "overwrite": Value(False), "existing_case_mode": Value(False),
        "action_buttons": actions, "config_from_entries": lambda: None,
        "run_action_ready": lambda *args: ready,
        "sumtally_readiness_generation": 0, "sumtally_readiness_pending": None,
        "start_sumtally_readiness": lambda: None,
    })
    refresh()
    assert states["run_segments"] == (["!disabled"] if ready and not busy else ["disabled"])
    assert states["run_sumtally"] == ["disabled"]  # Pending background validation.


def readiness_callbacks(check, thread_module=threading):
    states, scheduled = {}, queue.Queue()
    selection = Value("workspace-a")
    state = {
        "execution_guard": SimpleNamespace(active_stage=None),
        "current_rtdose_state": lambda: gui.RTDOSE_NOT_PREPARED,
        "current_structure_binding_ready": lambda: False,
        "structure_frame": None, "nav_status": {"rtdose": Value("Not run")},
        "tool_profile_resolution": SimpleNamespace(ready_for_stage=lambda key: True),
        "overwrite": Value(False), "existing_case_mode": Value(False),
        "action_buttons": {"run_sumtally": SimpleNamespace(state=lambda value: states.update(button=value))},
        "config_from_entries": selection.get, "run_action_ready": check,
        "sumtally_readiness_generation": 0, "sumtally_readiness_pending": None,
        "sumtally_readiness_active": False, "sumtally_readiness_closed": False,
        "root": SimpleNamespace(after=lambda delay, fn: scheduled.put(fn)),
        "threading": thread_module,
    }
    namespace = callbacks(["refresh_action_button_states", "start_sumtally_readiness"], state)
    return namespace, states, scheduled, selection


def test_sumtally_scan_runs_off_event_thread_and_returns_before_read_completes():
    started, release = threading.Event(), threading.Event()
    event_thread = threading.get_ident()

    def blocked_scan(*args):
        assert threading.get_ident() != event_thread
        started.set()
        assert release.wait(5)
        return True

    ns, states, scheduled, _ = readiness_callbacks(blocked_scan)
    try:
        ns["refresh_action_button_states"]()
        assert started.wait(2)
        assert states["button"] == ["disabled"]
        assert scheduled.empty()
    finally:
        release.set()
    scheduled.get(timeout=5)()
    assert states["button"] == ["!disabled"]


@pytest.mark.parametrize("change", ["workspace", "busy", "existing_case", "closed", "failure", "settings"])
def test_background_readiness_rejects_stale_results_and_coalesces_requests(change):
    workers, calls = [], []
    fake_threads = SimpleNamespace(Thread=lambda *, target, daemon: SimpleNamespace(start=lambda: workers.append(target)))

    def scan(config, stage):
        calls.append(config)
        if change == "failure":
            raise OSError("synthetic unavailable evidence")
        return True

    ns, states, scheduled, selection = readiness_callbacks(scan, fake_threads)
    refresh = ns["refresh_action_button_states"]
    refresh()
    if change == "workspace":
        selection.set("workspace-b")
        refresh()
        selection.set("workspace-c")
        refresh()
    elif change == "busy":
        ns["execution_guard"].active_stage = "run_segments"
        refresh()
    elif change == "existing_case":
        ns["existing_case_mode"].set(True)
        refresh()
    elif change == "closed":
        ns["sumtally_readiness_closed"] = True
    elif change == "settings":
        selection.set("changed-without-refresh")
    assert len(workers) == 1
    workers.pop(0)()
    if change == "closed":
        assert scheduled.empty()
    else:
        scheduled.get_nowait()()
    assert states["button"] == ["disabled"]
    if change == "workspace":
        assert len(workers) == 1
        workers.pop(0)()
        scheduled.get_nowait()()
        assert calls == ["workspace-a", "workspace-c"]
        assert states["button"] == ["!disabled"]
    else:
        assert not workers
