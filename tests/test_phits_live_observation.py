"""Authored fixtures, not copied PHITS outputs or distribution artifacts."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time
from copy import deepcopy
from pathlib import Path

import pytest

from dicomxphits.phits_observation_format import (
    Mesh, ObservationError, parse_batch, parse_identity, parse_tally,
    paired_statistics, prepared_contract,
)
from dicomxphits.phits_observation import (
    Candidate, Observer, Presentation, SCHEMA, RELATIVE_PATH, read_snapshot,
    observation_binding,
)
from dicomxphits.safe_output import WorkspaceOutputGuard
from dicomxphits.workspace_execution import WorkspaceExecutionLease, WorkspaceBusyError

MESH = Mesh("Authored observation fixture", "dose.out", (2, 2, 2), ((-1., 1.),)*3)


def deck():
    return "$OMP = 2\n[ Parameters ]\n maxcas = 10\n maxbch = 10\n[ T-Deposit ]\n" + header(False)


def header(output=True):
    rows = ["title = Authored observation fixture", "mesh = xyz"]
    for axis in "xyz":
        rows += [f"{axis}-type = 2", f"{axis}min = -1.000000", f"{axis}max = 1.000000", f"n{axis} = 2"]
    rows += ["unit = 0", "material = all", "output = dose", "axis = xy", "file = dose.out", "part = all", "epsout = 1"]
    if output:
        rows += ["letmat = 0", "dedxfnc = 0", "deposit = 0", "2D-type = 3", "mother = all"]
    return "\n".join(rows)+"\n"


def tally(role="dose", values=None, histories=10, seed="0"*64):
    values = list(values) if values is not None else ([1.0]*8 if role == "dose" else [.1]*8)
    rows = ["[ T-Deposit ]", header(), "#newpage:"]
    for index in (1, 2):
        if index > 1:
            rows.append(" newpage:")
        rows += [f"#   no. = {index:2d}   iz  = {index:2d}   part. = all",
            f"#   z = ( {index-2:.4E} - {index-1:.4E} )",
            f"'no. = {index:2d},  iz = {index:2d}'",
            "msuc: {Authored observation fixture}",
            r"msdl: {\it calculated by \PHITS  3.35}",
            "#  ny =   2   nx =   2",
            "# ( ( data(x,y), x = 1, nx ), y = ny, 1, -1 )", "",
            "hc:  y = 0.5000000 to -0.5000000 by 1.000000 ; x = -0.5000000 to 0.5000000 by 1.000000 ;",
            " ".join(str(v) for v in values[(index-1)*4:index*4]), "",
            "#"+"-"*78,
            "hc: y= 0.005 to 0.995 by 0.01 ; x= 0.5 to 0.5 by 1 ;",
            " ".join(str(i) for i in range(1,101)),
            "z: xorg(0.0)",
            "y: " + ("Dose [Gy/source]" if role == "dose" else "Relative Error"),
            "e:", "z: xorg[-1.03/0.05]", "p: ymin(-1) ymax(1)", ""]
    rows += ["# Information for Restart Calculation", "# This calculation was newly started",
        "# istdev = 2 # 1:Batch variance, 2:History variance",
        f"# resc2 = {histories:.17E} # Total source weight or Total source weight / maxcas",
        f"# resc3 = {histories:.17E} # Total history number or Total batch number",
        "# maxcas = 10 # History / Batch, only used for istdev=1",
        f"# bitrseed = {seed} # bit data of rseed"]
    return ("\n".join(rows)+"\n").encode()


def batch(remaining=9):
    return (f"{remaining} <--- number of remaining batches \n\n" + "-"*79 +
        "\nbat[       1] ncas =             10.\n bitrseed = " + "0"*64 +
        "\n          cpu time = 0.123 s.\n\n date = 2000-01-01\n time = 00h 00m 00s\n\n" + "-"*79 +
        "\nnext initial random seed:\n bitrseed = " + "1"*64 + "\n").encode()


def stats(dose=None, errors=None):
    return paired_statistics(tally(values=dose), tally("error", errors), MESH, 10, time.monotonic()+2)


def test_prepared_mesh_and_complete_fixture_statistics():
    mesh, runtime = prepared_contract(deck(), "dose.out")
    assert mesh == MESH and runtime == {"maxcas": 10, "maxbch": 10, "threads": 2}
    result = stats([0, 1, 1, 1, 1, 1, 1, 1], [0, 0, .1, .2, .3, .4, .5, 2.0])
    assert result == {"total_cells": 8, "valid_cells": 6, "excluded_cells": 2,
        "coverage": .75, "median_percent": 35.0, "maximum_percent": 200.0}


@pytest.mark.parametrize("value", [-1, float("nan"), float("inf"), "1"*65])
@pytest.mark.parametrize("role", ["dose", "error"])
def test_invalid_numeric_sample_is_rejected(value, role):
    values = [value]+[.1]*7
    with pytest.raises(ObservationError):
        stats(values if role == "dose" else None, values if role == "error" else None)


def test_zero_cells_are_unavailable_not_zero_error():
    with pytest.raises(ObservationError, match="no-evaluable-cells"):
        stats(errors=[0]*8)


@pytest.mark.parametrize("damage", ["slice", "extra_cells", "history", "seed", "ending", "role", "mesh", "version", "legend"])
def test_structural_and_pair_damage_rejected(damage):
    error = tally("error")
    if damage == "slice":
        error = error.replace(b"iz  =  2", b"iz  =  1")
    elif damage == "extra_cells":
        error = error.replace(b"0.1 0.1 0.1 0.1", b"0.1 0.1 0.1 0.1 0.1", 1)
    elif damage == "history":
        error = tally("error", histories=20)
    elif damage == "seed":
        error = tally("error", seed="1"*64)
    elif damage == "ending":
        error = error[:-2]
    elif damage == "role":
        error = tally("dose")
    elif damage == "mesh":
        error = error.replace(b"nx = 2", b"nx = 3")
    elif damage == "version":
        error = error.replace(b"3.35", b"3.37")
    elif damage == "legend":
        error = error.replace(b"98 99 100", b"98 99")
    with pytest.raises(ObservationError):
        paired_statistics(tally(), error, MESH, 10, time.monotonic()+2)


def test_limits_apply_before_numeric_allocation():
    with pytest.raises(ObservationError, match="resource-limit"):
        prepared_contract(deck().replace("nx = 2", "nx = 10000001"), "dose.out")
    with pytest.raises(ObservationError, match="resource-limit"):
        parse_tally(tally(), MESH, "dose", time.monotonic()-1)


def test_full_batch_and_identity_contract():
    assert parse_batch(batch(), 10) == 9
    initial = ("10 <--- remaining batch number\n\n" + "-"*79 + "\n start calculation\n" + "-"*79 +
        "\n\n date = 2000-01-01\n time = 00h 00m 00\n\n").replace("\n", "\r\n").encode()
    assert parse_batch(initial, 10) == 10
    for invalid in (b"0\n", b"10 <--- remaining batch number\r\n", batch(11), batch()[:-1], batch()+b"extra"):
        with pytest.raises(ObservationError):
            parse_batch(invalid, 10)
    output = b"OpenMP PARALLEL PROCESS 1/ 2 @ IP(MPI)=0\nOpenMP PARALLEL PROCESS 2/ 2 @ IP(MPI)=0\n"
    assert parse_identity(b" Version =  3.350 ", output, 2)
    for version, stdout in ((b"Version = 3.370", output), (b"Version = 3.350", b""),
                            (b"Version = 3.350", output.replace(b"MPI)=0", b"MPI)=1"))):
        with pytest.raises(ObservationError):
            parse_identity(version, stdout, 2)


def test_confirmation_reset_and_unchanged_age():
    candidate = Candidate()
    candidate.offer("a", 2, 10)
    assert candidate.record(10)["value"] is None
    candidate.offer("a", 2, 11)
    candidate.offer("a", 2, 14)
    assert candidate.record(16)["sample_age_seconds"] == 5
    assert candidate.record(16)["state"] == "stale"
    candidate.reject("pair-mismatch")
    candidate.offer("b", 3, 17)
    assert candidate.record(17)["value"] == 2
    assert candidate.record(17)["state"] == "stale"
    candidate.offer("b", 3, 18)
    assert candidate.record(18)["value"] == 3


def observer_fixture(tmp_path):
    root = tmp_path.resolve()
    staging = root / "staging"
    staging.mkdir()
    source = staging / "input.inp"
    source.write_text(deck())
    (staging / "phits.out").write_text("Version = 3.350\n")
    (staging / "batch.out").write_bytes(batch())
    (staging / "dose.out").write_bytes(tally())
    (staging / "dose_err.out").write_bytes(tally("error"))
    summary = {"workspace_root": str(root), "run_id": "owned-run", "stage_status": "running",
        "current_segment": {"segment_id": "one", "manifest_ordinal": 1, "active_ordinal": 1},
        "execution_binding": {"manifest_sha256": "0"*64,
            "segments": [{"segment_id": "one", "inputs": [], "environment_sha256": "1"*64}],
            "tool": {"executable_sha256": "2"*64}}}
    observer = Observer(root, staging, source, staging/"dose.out", observation_binding(summary, summary["current_segment"]))
    observer.feed_stdout(b"OpenMP PARALLEL PROCESS 1/2 @ IP(MPI)=0\nOpenMP PARALLEL PROCESS 2/2 @ IP(MPI)=0\n")
    return observer, summary


def test_observer_rejects_torn_mismatch_and_counter_regression(tmp_path):
    observer, _ = observer_fixture(tmp_path)
    assert observer.sample()["error"]["value"] is None
    assert observer.sample()["error"]["value"]["valid_cells"] == 8
    observer.error_path.write_bytes(tally("error", histories=20))
    assert observer.sample()["error"]["state"] == "stale"
    observer.error_path.write_bytes(tally("error")[:300])
    assert observer.sample()["error"]["state"] == "stale"
    (observer.staging/"batch.out").write_bytes(batch(10))
    assert observer.sample()["batch"]["reason"] == "counter-regression"


def test_reader_rejects_limits_hardlinks_and_outside_paths(tmp_path):
    source = tmp_path/"source"
    source.write_bytes(b"hello")
    with pytest.raises(ObservationError, match="resource-limit"):
        read_snapshot(tmp_path, source, 4, time.monotonic()+2)
    with pytest.raises(ObservationError, match="unsafe-path"):
        read_snapshot(tmp_path/"inside", source, 10, time.monotonic()+2)
    alias = tmp_path/"alias"
    os.link(source, alias)
    with pytest.raises(ObservationError, match="unsafe-path"):
        read_snapshot(tmp_path, alias, 10, time.monotonic()+2)


def test_publication_failure_close_and_no_output_mutations(tmp_path):
    observer, _ = observer_fixture(tmp_path)
    before = {p.name:p.read_bytes() for p in observer.staging.iterdir()}
    observer.sample()
    observer.latest = {**observer.sample(), "sequence": 1}
    class Broken:
        def write_bytes(self, *args):
            raise OSError("simulated sidecar failure")
    observer.publish(Broken())
    assert observer.closed.is_set()
    assert before == {p.name:p.read_bytes() for p in observer.staging.iterdir()}


def test_presentation_generation_corruption_stale_and_terminal(tmp_path):
    observer, summary = observer_fixture(tmp_path)
    observer.sample()
    record = {**observer.sample(), "sequence": 1}
    target = tmp_path/RELATIVE_PATH
    target.parent.mkdir()
    target.write_text(json.dumps(record))
    display = Presentation()
    now = time.monotonic()
    assert "median 10%" in display.refresh(tmp_path, summary, active=True, now=now)
    assert "stale" in display.refresh(tmp_path, summary, active=True, now=now+6)
    changed = deepcopy(summary)
    changed["run_id"] = "next"
    assert "unavailable" in display.refresh(tmp_path, changed, active=True, now=now+7)
    assert "no owned active" in display.refresh(tmp_path, summary, active=False)
    for invalid in ([], {"schema_version": SCHEMA}, {**record, "error": []}, {**record, "sequence": True}):
        target.write_text(json.dumps(invalid))
        display.reset()
        assert "unavailable" in display.refresh(tmp_path, summary, active=True)


def test_live_stdout_callback_drain_result_and_inherited_lease(tmp_path):
    seen = threading.Event()
    prefix = []
    def observe(chunk):
        prefix.append(chunk)
        seen.set()
        raise ValueError("optional observer failure must not change child")
    script = "import sys,time; print('identity',flush=True); time.sleep(.1); sys.stderr.write('diagnostic\\n'); print('done')"
    with WorkspaceExecutionLease(tmp_path) as lease:
        result = lease.run([sys.executable, "-c", script], input="", capture_output=True,
            text=True, shell=False, stdout_observer=observe)
        assert seen.is_set()
    assert result.returncode == 0 and result.stdout == "identity\ndone\n" and result.stderr == "diagnostic\n"
    assert b"identity" in b"".join(prefix)


def test_observation_stays_on_owner_thread_through_stop_and_retry(tmp_path, monkeypatch):
    from dicomxphits import phits_observation as observation
    from dicomxphits.run_segments import run_segments, summary_path
    from dicomxphits.segment_stop import StopControl
    from dicomxphits.workspace_recovery import validate_segment_execution_for_downstream
    from test_segment_retry import workspace_fixture, runner_for

    root, manifest, paths = workspace_fixture(tmp_path)
    for segment in manifest["segments"]:
        source = root / segment["phits_input_path"]
        source.write_text("infl:{libpath.inp}\n" + deck().replace("file = dose.out", "file = " + segment["expected_output_path"]))
    inputs = {s["phits_input_path"]: (root/s["phits_input_path"]).read_bytes() for s in manifest["segments"]}
    owner = threading.get_ident()
    published = []
    control = StopControl()
    base = runner_for(root)

    class CheckedObserver(Observer):
        def publish(self, guard):
            assert threading.get_ident() == owner
            super().publish(guard)
            path = root / RELATIVE_PATH
            if path.is_file():
                published.append(json.loads(path.read_bytes()))

    def make(root, staging, source, dose, context):
        return CheckedObserver(root, staging, source, dose, observation_binding(context, context["current_segment"]))
    monkeypatch.setattr(observation, "make_observer", make)

    def fake_owned_child(self, command, **kwargs):
        callback = kwargs.pop("stdout_observer")
        callback(b"OpenMP PARALLEL PROCESS 1/2 @ IP(MPI)=0\nOpenMP PARALLEL PROCESS 2/2 @ IP(MPI)=0\n")
        staging = Path(kwargs["cwd"])
        source = Path(kwargs["input"].strip().removeprefix("file = "))
        output = source.parent / "deposit-target-3D.out"
        (staging/"phits.out").write_text("Version = 3.350\n")
        (staging/"batch.out").write_bytes(batch(0))
        (staging/output).write_bytes(tally().replace(b"file = dose.out", ("file = " + output.as_posix()).encode()))
        (staging/output.with_name("deposit-target-3D_err.out")).write_bytes(tally("error").replace(b"file = dose.out", ("file = " + output.as_posix()).encode()))
        if source.parent.name == "seg_001":
            summary = json.loads(summary_path(root).read_bytes())
            control.feed(json.dumps({"operation": "stop-after-current", "workspace_root": str(root),
                "run_id": summary["run_id"], "request_id": "test-stop"}).encode()+b"\n")
        time.sleep(2.2)
        current = json.loads(summary_path(root).read_bytes())
        assert current["stage_status"] == "running"
        with pytest.raises(ValueError):
            validate_segment_execution_for_downstream(root, manifest, current)
        return base(command, **kwargs)
    monkeypatch.setattr(WorkspaceExecutionLease, "run", fake_owned_child)
    result = run_segments(workspace_root=root, paths=paths, stop_control=control)
    assert result["stage_status"] == "stopped"
    assert any(r["error"]["value"] is not None for r in published)
    assert not (root/RELATIVE_PATH).exists()
    first_dose = (root/manifest["segments"][0]["expected_output_path"]).read_bytes()
    resumed = run_segments(workspace_root=root, paths=paths, run_incomplete=True)
    assert resumed["stage_status"] == "success"
    assert (root/manifest["segments"][0]["expected_output_path"]).read_bytes() == first_dose
    assert inputs == {s["phits_input_path"]: (root/s["phits_input_path"]).read_bytes() for s in manifest["segments"]}
    assert not (root/RELATIVE_PATH).exists()


def test_retired_worker_cannot_publish_and_stdout_prefix_is_bounded(tmp_path):
    observer, _ = observer_fixture(tmp_path)
    observer.feed_stdout(b"a"*100000)
    assert len(observer.stdout) == 65536
    started, release = threading.Event(), threading.Event()
    def slow_sample():
        started.set()
        release.wait(5)
        return {"late": True}
    observer.sample = slow_sample
    observer.start()
    assert started.wait(2)
    with WorkspaceOutputGuard(tmp_path) as guard:
        observer.close(guard)
        release.set()
        observer.thread.join(2)
        observer.publish(guard)
    assert observer.latest is None and not (tmp_path/RELATIVE_PATH).exists()
