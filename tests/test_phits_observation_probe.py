from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import sys
import threading
import time

import pytest

from dicomxphits.safe_output import WorkspaceOutputGuard
from dicomxphits.workspace_execution import WorkspaceExecutionLease, WorkspaceBusyError

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("probe_collect", ROOT / "tools/phits_observation_probe/collect.py")
probe = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(probe)


def plan_fixture(tmp_path):
    installation = tmp_path / "synthetic-installation"
    (installation / "bin").mkdir(parents=True)
    exe = installation / "bin/phits335_win_openmp.exe"
    exe.write_bytes(b"synthetic identity only; never executable")
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    plan = {"schema": probe.SCHEMA, "executable": str(exe), "installation_root": str(installation),
        "scratch_parent": str(scratch), "run_dir": str(scratch / "run-one"),
        "evidence_dir": str(scratch / "evidence-one"),
        "executable_sha256": probe.digest(exe.read_bytes()),
        "deck_sha256": probe.digest(probe.DECK.read_bytes()),
        "collector_sha256": probe.digest(Path(probe.__file__).read_bytes()),
        "lease_sha256": probe.digest(probe.LEASE.read_bytes()),
        "libpath_sha256": probe.digest(probe.libpath_bytes(installation))}
    path = tmp_path / "private-plan.json"
    path.write_text(json.dumps(plan))
    return path, plan


def test_check_only_never_launches_or_creates_destinations(tmp_path, monkeypatch, capsys):
    path, plan = plan_fixture(tmp_path)
    monkeypatch.setattr(probe.subprocess, "Popen", lambda *a, **k: pytest.fail("launched"))
    assert probe.main(["--plan", str(path)]) == 0
    assert json.loads(capsys.readouterr().out)["execution_authorized"] is False
    assert not Path(plan["run_dir"]).exists()
    assert not Path(plan["evidence_dir"]).exists()


@pytest.mark.parametrize("damage", ["digest", "plan_digest", "existing", "same_destination", "unknown", "layout"])
def test_preflight_rejects_changes_without_launch(tmp_path, damage, monkeypatch):
    path, plan = plan_fixture(tmp_path)
    if damage == "digest":
        plan["deck_sha256"] = "0" * 64
    elif damage == "existing":
        Path(plan["run_dir"]).mkdir()
    elif damage == "same_destination":
        plan["evidence_dir"] = plan["run_dir"]
    elif damage == "unknown":
        plan["allow_override"] = True
    elif damage == "layout":
        plan["executable"] = str(Path(plan["installation_root"]) / "other.exe")
    path.write_text(json.dumps(plan))
    monkeypatch.setattr(probe.subprocess, "Popen", lambda *a, **k: pytest.fail("launched"))
    with pytest.raises(ValueError):
        probe.check_plan(path, "0" * 64 if damage == "plan_digest" else None)


def test_execute_requires_explicit_plan_digest_before_preflight(tmp_path, monkeypatch):
    monkeypatch.setattr(probe, "check_plan", lambda *a: pytest.fail("preflight unexpectedly invoked"))
    with pytest.raises(ValueError):
        probe.execute_plan(tmp_path / "missing.json", None)


def test_deck_is_fixed_probe_not_a_production_plan():
    text = probe.DECK.read_text()
    for entry in ("$OMP = 2", "maxcas = 10000", "maxbch = 10", "e0 = 1.0",
        "nx = 3", "ny = 3", "nz = 3", "output = dose", "axis = xy", "epsout = 1"):
        assert entry in text
    assert text.count("[ T-Deposit ]") == 1
    for absent in ("istdev", "itall", "timeout", "totfact", "stdcut", "resfile", "$MPI"):
        assert absent not in text


def test_bounded_read_and_unchanged_confirmation(tmp_path):
    source = tmp_path / "run"
    source.mkdir()
    target = source / "batch.out"
    target.write_bytes(b"synthetic batch bytes\n")
    with pytest.raises(ValueError, match="limit"):
        probe.read_sample(target, 1)
    out = tmp_path / "evidence"
    with WorkspaceOutputGuard(out, create_root=True) as guard:
        store = probe.Evidence(guard)
        previous = {}
        first = probe.capture_files(source, store, previous, time.monotonic())
        second = probe.capture_files(source, store, previous, time.monotonic())
        assert first["batch.out"]["stable_metadata"]
        assert second["batch.out"]["unchanged_confirmation"]
        assert target.read_bytes() == b"synthetic batch bytes\n"


def test_unsafe_link_is_not_read(tmp_path):
    outside = tmp_path / "outside"
    outside.write_bytes(b"not for capture")
    link = tmp_path / "link"
    try:
        link.symlink_to(outside)
    except OSError:
        pytest.skip("symlink privilege unavailable")
    with pytest.raises(ValueError, match="Link"):
        probe.read_sample(link, 100)


def test_hardlink_is_not_read(tmp_path):
    source = tmp_path / "original"
    source.write_bytes(b"not for capture")
    linked = tmp_path / "linked"
    os.link(source, linked)
    with pytest.raises(ValueError, match="regular"):
        probe.read_sample(linked, 100)


@pytest.mark.parametrize("cap", [probe.CAP, probe.RESERVE + 100])
def test_fake_child_capture_drains_both_streams_and_keeps_lease(tmp_path, cap):
    run, out = tmp_path / "run", tmp_path / "evidence"
    run.mkdir()
    code = "\n".join([
        "import sys,os,time,pathlib",
        "assert sys.stdin.readline() == 'file = observation-probe.inp\\n'",
        "assert os.environ['OMP_NUM_THREADS'] == '2'",
        "pathlib.Path('batch.out').write_text('synthetic first')",
        "sys.stdout.buffer.write(b'o'*200000); sys.stdout.flush()",
        "sys.stderr.buffer.write(b'e'*200000); sys.stderr.flush()",
        "time.sleep(0.5)",
        "pathlib.Path('batch.out').write_text('synthetic final')",
    ])
    busy = []
    def contend():
        time.sleep(0.2)
        try:
            with WorkspaceExecutionLease(run, create=False):
                busy.append(False)
        except WorkspaceBusyError:
            busy.append(True)
    with WorkspaceOutputGuard(out, create_root=True) as guard, WorkspaceExecutionLease(run) as lease:
        store = probe.Evidence(guard, cap=cap)
        contender = threading.Thread(target=contend)
        contender.start()
        result = probe.collect_child([sys.executable, "-c", code], run, store, lease, warning_seconds=0.1)
        contender.join()
    assert busy == [True]
    assert result["return_code"] == 0
    assert (run / "batch.out").read_text() == "synthetic final"
    assert store.used <= cap - probe.RESERVE
    assert sum(p.stat().st_size for p in out.iterdir()) <= cap
    assert result["capture_disabled"] == (cap < probe.CAP)
    if cap == probe.CAP:
        assert result["files"]["batch.out"]["sha256"] == probe.digest(b"synthetic final")
        assert sum(len(p.read_bytes()) for p in out.glob("*-stdout.bin")) == 200000
        assert sum(len(p.read_bytes()) for p in out.glob("*-stderr.bin")) == 200000


def test_evidence_write_failure_does_not_escape_into_child_control(tmp_path, monkeypatch):
    with WorkspaceOutputGuard(tmp_path / "evidence", create_root=True) as guard:
        store = probe.Evidence(guard)
        def fail(*a, **k):
            raise OSError("synthetic storage failure")
        monkeypatch.setattr(guard, "write_bytes", fail)
        assert not store.put("stdout", b"data", {})
        assert store.disabled and store.reason == "evidence-write-failed"


def test_oversized_capture_disables_storage(tmp_path):
    run = tmp_path / "run"
    run.mkdir()
    (run / "batch.out").write_bytes(b"x" * 65537)
    with WorkspaceOutputGuard(tmp_path / "evidence", create_root=True) as guard:
        store = probe.Evidence(guard)
        result = probe.capture_files(run, store, {}, time.monotonic())
        assert result["batch.out"]["status"] == "unavailable"
        assert store.disabled and store.used == 0


@pytest.mark.skipif(os.name != "nt", reason="real entry point intentionally Windows-only")
def test_frozen_execution_entry_with_fake_collector_is_single_use(tmp_path, monkeypatch):
    path, plan = plan_fixture(tmp_path)
    calls = []
    def fake(command, run_dir, evidence, lease):
        calls.append(command)
        assert (run_dir / "observation-probe.inp").read_bytes() == probe.DECK.read_bytes()
        return {"return_code": 0, "capture_disabled": False, "files": {}, "collector_interrupted": False}
    monkeypatch.setattr(probe, "collect_child", fake)
    monkeypatch.setattr(probe.subprocess, "Popen", lambda *a, **k: pytest.fail("real launch"))
    sha = probe.digest(path.read_bytes())
    result = probe.execute_plan(path, sha)
    assert result["input_digests_unchanged"]
    assert (Path(plan["evidence_dir"]) / "report.json").is_file()
    with pytest.raises(ValueError, match="absent"):
        probe.execute_plan(path, sha)
    assert calls == [[plan["executable"]]]
