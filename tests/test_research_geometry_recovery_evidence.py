from __future__ import annotations

import json
from pathlib import Path

import pytest

from dicomxphits.run_segments import run_segments, summary_path
from dicomxphits.safe_output import WorkspaceOutputGuard
from dicomxphits.segment_retry import (
    FAILED_STAGING_SCHEMA, RESEARCH_RECEIPT_PATH, plan_incomplete,
)
from dicomxphits.sumtally_inputs import file_sha256
from test_segment_retry import runner_for, workspace_fixture


def snapshot(root):
    return {p.relative_to(root).as_posix(): p.read_bytes()
            for p in root.rglob("*") if p.is_file()}


def recovering_runner(root, *, observed=None, damage=None):
    ordinary = runner_for(root)

    def run(command, **kwargs):
        result = ordinary(command, **kwargs)
        staging = Path(kwargs["cwd"])
        if observed is not None:
            observed.append(staging)
        output = staging / "phits.out"
        output.write_text(output.read_text().replace(
            "Number of geometry recovering = 0",
            "Number of geometry recovering = 12"), encoding="utf-8")
        source = kwargs["input"].strip().removeprefix("file = ")
        if damage == "input":
            staged_input = staging / source
            staged_input.write_text(staged_input.read_text() + "# changed by fake child\n")
        elif damage == "missing_error":
            (staging / Path(source).parent / "deposit-target-3D_err.out").unlink()
        return result

    return run


def test_geometry_failure_retains_invocation_bound_tree_without_publication(tmp_path, monkeypatch):
    root, manifest, paths = workspace_fixture(tmp_path, segment_count=1)
    before = snapshot(root)
    cleanups = []
    original_cleanup = WorkspaceOutputGuard.rmtree

    def cleanup(self, path, **kwargs):
        cleanups.append(path)
        return original_cleanup(self, path, **kwargs)

    monkeypatch.setattr(WorkspaceOutputGuard, "rmtree", cleanup)
    seen = []
    summary = run_segments(workspace_root=root, paths=paths,
                           runner=recovering_runner(root, observed=seen))
    assert summary["stage_status"] == "failed"
    segment = summary["segments"][0]
    assert segment["status"] == "failed"
    assert segment["geometry_diagnostics"]["counts"]["geometry_recovering"] == 12
    assert cleanups == []  # Same retention decision on Windows and non-Windows.
    evidence = segment["retained_staging"]
    assert evidence["schema_version"] == FAILED_STAGING_SCHEMA
    assert evidence["run_id"] == summary["run_id"] == segment["producer_run_id"]
    assert evidence["segment_id"] == segment["segment_id"]
    assert root / evidence["staging_directory"] == seen[0]
    assert evidence["missing_required_outputs"] == []
    for item in evidence["files"]:
        path = root / item["path"]
        assert path.is_relative_to(seen[0])
        assert item["sha256"] == file_sha256(path)
        assert item["size"] == path.stat().st_size
    bound_inputs = summary["execution_binding"]["segments"][0]["inputs"]
    assert {item["input_path"]: item["sha256"] for item in evidence["inputs"]} == {
        item["path"]: item["sha256"] for item in bound_inputs}
    assert any(item["output_path"] == "phits.out" for item in evidence["outputs"])
    assert not (root / manifest["segments"][0]["expected_output_path"]).exists()
    assert not (root / RESEARCH_RECEIPT_PATH).exists()
    assert all((root / path).read_bytes() == content for path, content in before.items())
    assert json.loads(summary_path(root).read_text())["segments"][0]["retained_staging"] == evidence


def test_missing_retained_output_is_recorded_without_fabricated_digest(tmp_path):
    root, _manifest, paths = workspace_fixture(tmp_path, segment_count=1)
    summary = run_segments(workspace_root=root, paths=paths,
                          runner=recovering_runner(root, damage="missing_error"))
    evidence = summary["segments"][0]["retained_staging"]
    assert evidence["missing_required_outputs"] == ["segments/seg_001/deposit-target-3D_err.out"]
    assert all(item["output_path"] not in evidence["missing_required_outputs"]
               for item in evidence["outputs"])
    assert summary["stage_status"] == "failed"


def test_changed_staged_input_preserves_tree_but_cannot_create_valid_binding(tmp_path):
    root, _manifest, paths = workspace_fixture(tmp_path, segment_count=1)
    before = snapshot(root)
    seen = []
    with pytest.raises(ValueError, match="Retained staged input differs"):
        run_segments(workspace_root=root, paths=paths,
                     runner=recovering_runner(root, observed=seen, damage="input"))
    assert seen[0].is_dir()
    summary = json.loads(summary_path(root).read_text())
    assert summary["stage_status"] == "gate_failed"
    assert "retained_staging" not in summary["segments"][0]
    assert all((root / path).read_bytes() == content for path, content in before.items())


@pytest.mark.parametrize("mode", ["ordinary", "retry", "preflight", "preview"])
@pytest.mark.parametrize("content", ["{}", "not valid JSON"])
def test_any_receipt_refuses_phits_before_mutation(tmp_path, mode, content):
    root, _manifest, paths = workspace_fixture(tmp_path, segment_count=1)
    (root / RESEARCH_RECEIPT_PATH).write_text(content, encoding="utf-8")
    before = snapshot(root)
    directories = {p.relative_to(root) for p in root.rglob("*") if p.is_dir()}

    def forbidden(*args, **kwargs):
        pytest.fail("Receipt refusal must precede all external process launches")

    with pytest.raises(ValueError, match="research geometry-recovery receipt exists"):
        if mode == "preview":
            plan_incomplete(root, paths)
        else:
            run_segments(workspace_root=root, paths=paths, runner=forbidden,
                         run_incomplete=mode == "retry",
                         preflight_nonce="synthetic-nonce" if mode == "preflight" else None)
    assert snapshot(root) == before
    assert {p.relative_to(root) for p in root.rglob("*") if p.is_dir()} == directories


@pytest.mark.parametrize("context", ["receipt", "generation_marker", "execution_marker"])
def test_legacy_rtdose_context_cannot_hide_research_authority(tmp_path, context):
    from dicomxphits.prepare_rtdose import validate_sumtally_manifest_binding
    from test_prepare_rtdose import write_workspace

    root, _files = write_workspace(tmp_path)
    generation = json.loads((root / "analysis/sumtally_generation_summary.json").read_text())
    execution = json.loads((root / "analysis/sumtally_execution_summary.json").read_text())
    if context == "receipt":
        (root / RESEARCH_RECEIPT_PATH).write_text("{}", encoding="utf-8")
    else:
        selected = generation if context == "generation_marker" else execution
        selected["research_exception"] = {"receipt_sha256": "0" * 64,
                                           "accepted_segment_id": "synthetic"}
    before = snapshot(root)
    # This legitimate ordinary legacy fixture has no separate segment record.
    # A receipt or marker must never send it through the ordinary fallback.
    with pytest.raises((ValueError, FileNotFoundError)):
        validate_sumtally_manifest_binding(workspace_root=root,
                                          generation=generation, execution=execution)
    assert snapshot(root) == before


@pytest.mark.parametrize("content", ["", "{}", "[]", '{"schema_version":"unsupported"}'])
def test_receipt_existence_cannot_bypass_sumtally_preflight(tmp_path, content):
    from dicomxphits.prepare_sumtally import validate_segment_outputs_exist
    from test_prepare_sumtally import write_workspace

    root, manifest = write_workspace(tmp_path)
    source = summary_path(root)
    summary = json.loads(source.read_text())
    summary["stage_status"] = "failed"
    summary["segments"][0]["status"] = "failed"
    source.write_text(json.dumps(summary))
    (root / RESEARCH_RECEIPT_PATH).write_text(content, encoding="utf-8")
    before = snapshot(root)
    with pytest.raises(ValueError):
        validate_segment_outputs_exist(root, manifest)
    assert snapshot(root) == before
