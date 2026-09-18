"""Synthetic readiness checks without opening a GUI or launching external tools."""

import ast
import inspect
import json
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


def callback(name, state):
    """Execute a real nested callback with synthetic closure variables, without Tk."""
    tree = ast.parse(inspect.getsource(gui._build_gui))
    node = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == name)
    node.body = [ast.Global(names=n.names) if isinstance(n, ast.Nonlocal) else n for n in node.body]
    namespace = {**vars(gui), **state}
    code = compile(ast.fix_missing_locations(ast.Module(body=[node], type_ignores=[])), "<gui-callback>", "exec")
    exec(code, namespace)
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
    })
    refresh()
    assert all(state == (["!disabled"] if ready and not busy else ["disabled"])
               for state in states.values())
