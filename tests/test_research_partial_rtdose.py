"""Synthetic retained tallies and fake external runners only."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import numpy as np
import pydicom
import pytest

from dicomxphits.gantry_geometry import (
    CURRENT_GANTRY_GEOMETRY_CONTRACT,
    GANTRY_GEOMETRY_CONTRACT_FIELD,
)
from dicomxphits.phits_terminal_evidence import OPENMP_335, PHASE, STACK_OVERFLOW
from dicomxphits.prepare_3dcrt_workspace import ExternalToolPaths, write_libpath
from dicomxphits.research_partial_rtdose import (
    LEGACY_SCHEMA, SCHEMA, ExportInputs, OUTPUT_DIRECTORY, RECEIPT, export, preview, verify,
)
from dicomxphits.research_partial_tally import has_partial_tally_candidate
from dicomxphits.run_segments import run_segments
from dicomxphits.safe_output import WorkspaceOutputGuard
from dicomxphits.segment_retry import digest_object
from dicomxphits.workspace_recovery import validate_segment_execution_for_downstream
from test_phits_live_observation import header, tally
from test_prepare_rtdose import write_coordinate_rtdose, write_dicom, write_workspace
from test_research_geometry_recovery_evidence import snapshot


_FINAL_BATCH = "bat[ 4] ncas = 40. : date = 2000-01-01 : time = 10h 30m 11s\n"
_FINAL_WORKERS = [f"OpenMP FINALIZE {worker}/ 10 @ IP(MPI)= 0\n" for worker in range(10, 0, -1)]
_FINAL_STDOUT = _FINAL_BATCH + "".join(_FINAL_WORKERS)
_SUMMARY = Path("analysis/segment_execution_summary.json")


def case(tmp_path, *, damage=None, exit_code=STACK_OVERFLOW, stdout="", stderr=""):
    root, _ = write_workspace(tmp_path, number_of_fractions=3)
    manifest_path = root / "segments/segment_manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest[GANTRY_GEOMETRY_CONTRACT_FIELD] = CURRENT_GANTRY_GEOMETRY_CONTRACT
    segment = manifest["segments"][0]
    segment["phits_input_path"] = "segments/seg_b0001_s0000/phits.inp"
    manifest_path.write_text(json.dumps(manifest))
    primary = segment["expected_output_path"]
    pdd = str(Path(primary).with_name("deposit-pdd.out").as_posix())
    dose_header = header(False).replace("dose.out", primary)
    pdd_header = dose_header.replace(primary, pdd).replace("axis = xy", "axis = z")
    pdd_header = pdd_header.replace("nx = 2", "nx = 1").replace("ny = 2", "ny = 1")
    (root / segment["phits_input_path"]).write_text(
        "$OMP = 10\n[ Parameters ]\n infl:{libpath.inp}\n icntl = 0\n maxcas = 10\n maxbch = 4\n"
        f"[ T-Deposit ]\n{dose_header}[ T-Deposit ]\n{pdd_header}[ E N D ]\n"
    )
    for name in ("phits_generation_summary.json", "public_preparation_workspace_summary.json"):
        (root / "analysis" / name).write_text('{"synthetic": true}')
    for name in ("sumtally_generation_summary.json", "sumtally_execution_summary.json"):
        (root / "analysis" / name).unlink()
    shutil.rmtree(root / "sumtally")
    (root / primary).unlink()

    tools = tmp_path / "fake-tools"
    tools.mkdir()
    exe = tools / OPENMP_335
    converter = tools / "synthetic-converter.exe"
    for file in (exe, converter):
        file.write_text("synthetic identity, never executed")
    paths = ExternalToolPaths(str(tools), str(exe), str(converter))
    write_libpath(root, phits_root_folder=str(tools))
    ct, template = tmp_path / "ct.dcm", tmp_path / "template.dcm"
    write_dicom(ct)
    write_dicom(template, modality="RTDOSE")
    inputs = ExportInputs(paths, root / "RTPLAN.dcm", ct, template)
    dose_raw = tally(histories=3).replace(b"file = dose.out", f"file = {primary}".encode())
    error_raw = tally("error", histories=3).replace(b"file = dose.out", f"file = {primary}".encode())
    dose_raw = dose_raw.replace(b"# istdev = 2", b"# istdev = 1")
    error_raw = error_raw.replace(b"# istdev = 2", b"# istdev = 1")
    if damage == "different_weight":
        error_raw = error_raw.replace(b"# resc2 = 3", b"# resc2 = 4")

    def fake_segment(command, **kwargs):
        staged = Path(kwargs["cwd"])
        (staged / primary).write_bytes(dose_raw)
        (staged / primary).with_name("deposit-target-3D_err.out").write_bytes(error_raw)
        restart = dose_raw.split(b"# Information for Restart Calculation\n", 1)[1].decode()
        rows = "-1.5000E+00 -5.0000E-01 1.0 0.1\n-5.0000E-01 5.0000E-01 2.0 0.2\n"
        if damage == "truncated_pdd":
            rows = rows.splitlines()[0] + "\n"
        (staged / pdd).write_text(
            f"[ T-Deposit ]\n{pdd_header}#newpage:\n{rows}# Information for Restart Calculation\n{restart}"
        )
        batch_count = 3 if damage == "short_run" else 4
        seed = "1" * 64 if damage == "wrong_seed" else "0" * 64
        log = "".join(f"bat[ {index} ] ncas = {index * 10}.\n bitrseed = {seed}\n"
                      for index in range(1, batch_count + 1))
        if damage == "known_lost":
            log += "Number of lost particles = 1 / nlost = 1000\n"
        if damage == "input_error":
            log = "*** Error! Invalid PHITS input\n" + log
        if damage == "extra_tally":
            (staged / primary).with_name("extra.out").write_text("synthetic extra tally")
        (staged / "phits.out").write_text(log)
        if damage == "timeout":
            raise subprocess.TimeoutExpired(command, 1, output=stdout, stderr=stderr)
        if damage == "launcher_failure":
            raise OSError("synthetic launcher or controller failure")
        return subprocess.CompletedProcess(command, exit_code, stdout, stderr)

    if damage in ("timeout", "launcher_failure"):
        with pytest.raises(subprocess.TimeoutExpired if damage == "timeout" else OSError):
            run_segments(workspace_root=root, paths=paths, runner=fake_segment)
        return root, inputs, None, manifest, json.loads((root / _SUMMARY).read_text())
    result = run_segments(workspace_root=root, paths=paths, runner=fake_segment)
    staging = result["segments"][0]["retained_staging"]["staging_directory"]
    return root, inputs, staging, manifest, result


def runners(calls, *, stop=False):
    def fake_sumtally(command, **kwargs):
        calls.append("sumtally")
        assert "icntl = 13" in kwargs["stdin"].read()
        directory = Path(kwargs["cwd"])
        weights = (directory / "sumtally.inp").read_text()
        assert "isumtally = 2" in weights and "sumfactor = 100" in weights
        (directory / "deposit-target-3D_sum.out").write_text("[ T-Deposit ]\n" + header())
        (directory / "phits.out").write_text("synthetic aggregation companion\n")
        return subprocess.CompletedProcess(command, 0, "", "")

    class FakeConverter:
        returncode = 12 if stop else 0

        def communicate(self, input):
            lines = input.splitlines()
            assert lines[6:8] == ["2", "3"]
            dose = Path(lines[3]).with_suffix(".dcm")
            write_coordinate_rtdose(dose)
            dataset = pydicom.dcmread(dose)
            dataset.NumberOfFrames = dataset.Rows = dataset.Columns = 2
            dataset.PixelSpacing = [10, 10]
            dataset.GridFrameOffsetVector = [0, 10]
            dataset.PixelData = np.arange(8, dtype=np.uint16).tobytes()
            dataset.save_as(dose)
            return "synthetic", None

    def fake_converter(*args, **kwargs):
        calls.append("converter")
        return FakeConverter()

    return {"sumtally_runner": fake_sumtally, "converter_runner": fake_converter}


def test_confirmed_export_uses_only_saved_statistics_and_reopens(tmp_path):
    root, inputs, staging, manifest, failed = case(tmp_path)
    before = snapshot(root)
    frozen = preview(root, staging, inputs)
    assert snapshot(root) == before
    assert frozen["plan"]["snapshot"]["saved_batches"] == 3
    calls = []
    receipt = export(root, staging, inputs, expected_digest=frozen["plan_digest"],
                     acknowledge_research_only=True, **runners(calls))
    assert calls == ["sumtally", "converter"]
    assert all((root / path).read_bytes() == data for path, data in before.items())
    assert verify(root, rtplan=inputs.rtplan, ct_reference=inputs.ct_reference) == receipt
    dose_path = root / receipt["rtdose"]["path"]
    dose = pydicom.dcmread(dose_path)
    assert dose.DoseComment == "RESEARCH ONLY - PARTIAL PHITS 3/4"
    assert dose.DoseUnits == "GY" and dose.DoseSummationType == "PLAN"
    assert float(dose.DoseGridScaling) == 0.125
    assert np.array_equal(dose.pixel_array, np.arange(8).reshape(2, 2, 2).transpose(1, 0, 2)[:, :, ::-1])
    assert dose.ReferencedRTPlanSequence[0].ReferencedSOPInstanceUID == manifest["plan_uid"]
    assert str(root) not in json.dumps(receipt)
    with pytest.raises(ValueError):
        validate_segment_execution_for_downstream(root, manifest, failed)

    dose.DoseComment = "altered"
    dose.save_as(dose_path)
    with pytest.raises(ValueError, match="missing or changed"):
        verify(root, rtplan=inputs.rtplan, ct_reference=inputs.ct_reference)


@pytest.mark.parametrize("damage", ["short_run", "wrong_seed", "known_lost",
                                   "different_weight", "truncated_pdd", "extra_tally"])
def test_ineligible_snapshot_is_read_only(tmp_path, damage):
    root, inputs, staging, _, _ = case(tmp_path, damage=damage)
    before = snapshot(root)
    with pytest.raises(ValueError):
        preview(root, staging, inputs)
    assert snapshot(root) == before


@pytest.mark.parametrize("code", [7, 0xC0000005])
def test_bound_finalization_allows_different_nonzero_exits(tmp_path, code):
    root, inputs, staging, manifest, failed = case(tmp_path, exit_code=code, stdout=_FINAL_STDOUT)
    assert has_partial_tally_candidate(failed)
    frozen = preview(root, staging, inputs)
    saved = frozen["plan"]["snapshot"]
    assert (saved["saved_batches"], saved["planned_batches"], saved["exit_code"]) == (3, 4, code)
    assert saved["failure_evidence"] == {
        "route": "bound_post_batch", "phase": PHASE,
        "terminal_evidence": failed["segments"][0]["terminal_evidence"],
    }
    assert all(log["sha256"] for log in saved["failure_evidence"]["terminal_evidence"]["logs"].values())
    calls = []
    receipt = export(root, staging, inputs, expected_digest=frozen["plan_digest"],
                     acknowledge_research_only=True, **runners(calls))
    assert receipt["schema_version"] == SCHEMA
    assert calls == ["sumtally", "converter"]
    assert verify(root, rtplan=inputs.rtplan, ct_reference=inputs.ct_reference) == receipt
    with pytest.raises(ValueError):
        validate_segment_execution_for_downstream(root, manifest, failed)
    stdout = root / failed["segments"][0]["terminal_evidence"]["logs"]["stdout"]["path"]
    stdout.write_bytes(stdout.read_bytes() + b"\n")
    with pytest.raises(ValueError, match="changed while being read"):
        verify(root, rtplan=inputs.rtplan, ct_reference=inputs.ct_reference)


@pytest.mark.parametrize("stdout,stderr,code", [
    ("", "", 7),
    (_FINAL_BATCH + "".join(_FINAL_WORKERS[:-1]), "", 7),
    ("".join(_FINAL_WORKERS) + _FINAL_BATCH, "", 7),
    (_FINAL_STDOUT + _FINAL_WORKERS[0], "", 7),
    (_FINAL_STDOUT.replace("40.", "30."), "", 7),
    (_FINAL_STDOUT, "Fatal transport error\n", 7),
    (_FINAL_STDOUT, "unrecognized diagnostic\n", 7),
    (_FINAL_STDOUT, "", 0xC000013A),
])
def test_unproven_terminal_sequence_cannot_offer_export(tmp_path, stdout, stderr, code):
    root, inputs, staging, _, failed = case(tmp_path, exit_code=code, stdout=stdout, stderr=stderr)
    assert not has_partial_tally_candidate(failed)
    assert "terminal_evidence" not in failed["segments"][0]
    with pytest.raises(ValueError, match="lacks an eligible exit"):
        preview(root, staging, inputs)
    assert not (root / OUTPUT_DIRECTORY).exists()


@pytest.mark.parametrize("damage", ["known_lost", "input_error", "wrong_seed", "short_run"])
def test_console_sequence_cannot_override_inconsistent_staging(tmp_path, damage):
    root, inputs, staging, _, _ = case(tmp_path, damage=damage, exit_code=7, stdout=_FINAL_STDOUT)
    with pytest.raises(ValueError):
        preview(root, staging, inputs)
    assert not (root / OUTPUT_DIRECTORY).exists()


@pytest.mark.parametrize("damage", ["timeout", "launcher_failure"])
def test_controller_failures_do_not_record_a_native_exit(tmp_path, damage):
    root, inputs, _, _, failed = case(tmp_path, damage=damage, exit_code=7, stdout=_FINAL_STDOUT)
    assert failed["stage_status"] == "gate_failed"
    assert not has_partial_tally_candidate(failed)
    assert "terminal_evidence" not in failed["segments"][0]
    with pytest.raises(ValueError, match="one failed active segment"):
        preview(root, "analysis/.phits-segment-run-missing", inputs)


@pytest.mark.parametrize("change", ["remove_binding", "run_id", "stop", "stderr"])
def test_bound_logs_are_rechecked_before_launch(tmp_path, change):
    root, inputs, staging, _, failed = case(tmp_path, exit_code=7, stdout=_FINAL_STDOUT)
    frozen = preview(root, staging, inputs)
    record = failed["segments"][0]["terminal_evidence"]
    if change == "stderr":
        (root / record["logs"]["stderr"]["path"]).write_text("changed")
    else:
        if change == "remove_binding":
            del failed["segments"][0]["terminal_evidence"]
        elif change == "run_id":
            record["run_id"] = "another-run"
        else:
            segment = failed["segments"][0]
            failed["stop_control_enabled"] = True
            failed["stop_requested"] = {
                "request_id": "stop", "workspace_root": str(root), "run_id": failed["run_id"],
                "acknowledged_at": segment["started_at"],
                "acknowledged_elapsed_seconds": segment["started_elapsed_seconds"],
                "boundary_segment": {key: segment[key] for key in
                                     ("segment_id", "manifest_ordinal", "active_ordinal")},
            }
        (root / _SUMMARY).write_text(json.dumps(failed))
    calls = []
    error = "lacks an eligible exit|does not match the failed invocation|changed while being read"
    with pytest.raises(ValueError, match=error):
        export(root, staging, inputs, expected_digest=frozen["plan_digest"],
               acknowledge_research_only=True, **runners(calls))
    assert not calls and not (root / RECEIPT).exists()


def test_legacy_stack_overflow_receipt_can_be_verified_without_rewriting(tmp_path):
    root, inputs, staging, _, _ = case(tmp_path)
    frozen = preview(root, staging, inputs)
    receipt = export(root, staging, inputs, expected_digest=frozen["plan_digest"],
                     acknowledge_research_only=True, **runners([]))
    assert receipt["plan"]["snapshot"].pop("failure_evidence") == {
        "route": "recorded_stack_overflow", "phase": "unavailable",
    }
    receipt["schema_version"] = LEGACY_SCHEMA
    receipt["plan_digest"] = digest_object(receipt["plan"])
    del receipt["receipt_content_sha256"]
    receipt["receipt_content_sha256"] = digest_object(receipt)
    old_bytes = (json.dumps(receipt, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    (root / RECEIPT).write_bytes(old_bytes)
    assert verify(root, rtplan=inputs.rtplan, ct_reference=inputs.ct_reference) == receipt
    assert (root / RECEIPT).read_bytes() == old_bytes


def test_confirmation_and_current_evidence_required_before_launch(tmp_path):
    root, inputs, staging, _, _ = case(tmp_path)
    frozen = preview(root, staging, inputs)
    calls = []
    with pytest.raises(ValueError, match="acknowledgement"):
        export(root, staging, inputs, expected_digest=frozen["plan_digest"],
               acknowledge_research_only=False, **runners(calls))
    inputs.template.write_bytes(inputs.template.read_bytes() + b" ")
    with pytest.raises(ValueError, match="evidence changed"):
        export(root, staging, inputs, expected_digest=frozen["plan_digest"],
               acknowledge_research_only=True, **runners(calls))
    assert not calls and not (root / OUTPUT_DIRECTORY).exists()


def test_interrupted_conversion_has_no_accepted_export_and_can_retry(tmp_path):
    root, inputs, staging, _, _ = case(tmp_path)
    frozen = preview(root, staging, inputs)
    with pytest.raises(ValueError, match="conversion"):
        export(root, staging, inputs, expected_digest=frozen["plan_digest"],
               acknowledge_research_only=True, **runners([], stop=True))
    assert not (root / RECEIPT).exists()
    assert preview(root, staging, inputs) == frozen
    export(root, staging, inputs, expected_digest=frozen["plan_digest"],
           acknowledge_research_only=True, **runners([]))
    (root / RECEIPT).write_bytes((root / RECEIPT).read_bytes() + b" ")
    with pytest.raises(ValueError, match="receipt is malformed or changed"):
        verify(root, rtplan=inputs.rtplan, ct_reference=inputs.ct_reference)


@pytest.mark.parametrize("prefix,name,allowed", [
    (".sumtally-run-", "sumtally.inp", []),
    (".p2d-", "ct.dcm", ["sumtally"]),
])
def test_changed_tool_staging_copy_blocks_launch(tmp_path, monkeypatch, prefix, name, allowed):
    root, inputs, staging, _, _ = case(tmp_path)
    frozen = preview(root, staging, inputs)
    original = WorkspaceOutputGuard.copy_file

    def corrupt_copy(guard, source, destination, **kwargs):
        path = original(guard, source, destination, **kwargs)
        if path.name == name and any(part.startswith(prefix) for part in path.parts):
            path.write_bytes(path.read_bytes() + b"unexpected change")
        return path

    monkeypatch.setattr(WorkspaceOutputGuard, "copy_file", corrupt_copy)
    calls = []
    with pytest.raises(ValueError, match="private research export input changed"):
        export(root, staging, inputs, expected_digest=frozen["plan_digest"],
               acknowledge_research_only=True, **runners(calls))
    assert calls == allowed and not (root / RECEIPT).exists()


@pytest.mark.skipif(os.environ.get("DICOMXPHITS_TEST_TK") != "1", reason="requires a Tk desktop")
@pytest.mark.parametrize("inside,bound", [(True, False), (False, False), (True, True)])
def test_partial_export_button_displays_the_review_or_selection_error(tmp_path, monkeypatch, inside, bound):
    import sys
    import tkinter as tk
    from tkinter import filedialog

    from dicomxphits import gui, research_partial_rtdose
    from dicomxphits.gui_dialogs import GuiMessages
    from dicomxphits.gui_tool_profile import ToolProfileResolution

    workspace, inputs, staging, _, _ = case(
        tmp_path, exit_code=7 if bound else STACK_OVERFLOW, stdout=_FINAL_STDOUT if bound else "",
    )
    tool = inputs.tools
    profile = ToolProfileResolution(
        "custom", None, tool.phits_root_folder, tool.phits_root_folder,
        tool.phits_root_folder, tool.phits_executable_path, tool.phits2dicom_executable_path, (),
    )
    defaults = gui._base_default_values()
    defaults.update(profile.values(), workspace_root=str(workspace), rtplan_path=str(inputs.rtplan),
                    ct_reference_dicom=str(inputs.ct_reference), rtdose_template_dicom=str(inputs.template))
    monkeypatch.setattr(gui, "_default_values", lambda: defaults)
    monkeypatch.setattr(gui, "_browse_directories", lambda: {})
    monkeypatch.setattr(gui, "resolve_tool_profile", lambda _: profile)
    monkeypatch.setattr(filedialog, "askdirectory", lambda **_: str(workspace / staging if inside else tmp_path))
    monkeypatch.setattr(research_partial_rtdose, "export", lambda *a, **k: pytest.fail("unexpected export"))
    messages, failures = [], []

    def show(self, title, message, *, kind, confirm=False, accept="Yes", cancel="No"):
        messages.append((title, message, kind, confirm))
        self.parent.after_idle(self.parent.quit)
        return False

    monkeypatch.setattr(GuiMessages, "_show", show)
    original_mainloop = tk.Tk.mainloop

    def exercise(window):
        button = sys._getframe(1).f_locals["action_buttons"]["research_partial_export"]
        window.withdraw()
        window.report_callback_exception = lambda *error: (failures.append(error), window.quit())
        window.after(0, button.invoke)
        window.after(8000, window.quit)
        try:
            original_mainloop(window)
        finally:
            window.destroy()

    monkeypatch.setattr(tk.Tk, "mainloop", exercise)
    assert gui._build_gui() == 0
    assert not failures
    assert len(messages) == 1
    title, message, kind, confirm = messages[0]
    assert title == "Research partial tally RT Dose"
    assert confirm is inside
    if inside:
        assert kind == "warning" and "3/4 batches" in message
        assert ("OpenMP finalization was observed" if bound else "Recorded stack overflow") in message
    else:
        assert kind == "error" and "within the current workspace" in message
