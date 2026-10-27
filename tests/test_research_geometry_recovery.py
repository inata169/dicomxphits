"""Synthetic only: the table grammar was supplied by the operator as an example."""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from dicomxphits.phits_geometry_diagnostics import parse_research_geometry_completion
from dicomxphits.research_geometry_recovery import (
    RECEIPT_PATH, apply, main, preview, validate,
)
from dicomxphits.run_segments import run_segments, summary_path
from dicomxphits.workspace_recovery import validate_segment_execution_for_downstream
from test_research_geometry_recovery_evidence import snapshot
from test_segment_retry import runner_for, workspace_fixture

FORMAT = (Path(__file__).parent / "fixtures/phits_geometry_recovery_summary.synthetic.txt").read_text()


def eligible(tmp_path, *, text=FORMAT, damage=None, count=1, preflight=False, secondary=False, fail_all=False):
    root, manifest, paths = workspace_fixture(tmp_path, segment_count=count)
    for segment in manifest["segments"]:
        path = root / segment["phits_input_path"]
        path.write_text(path.read_text().replace("icntl = 0", "icntl = 0\n maxbch = 3"))
        if secondary:
            path.write_text(path.read_text().replace("[ E N D ]", "[ T-Deposit ]\n file = "
                + str(Path(segment["expected_output_path"]).with_name("deposit-pdd.out")).replace("\\", "/")
                + "\n[ E N D ]"))
    ordinary = runner_for(root)

    def runner(command, **kwargs):
        result = ordinary(command, **kwargs)
        staging = Path(kwargs["cwd"])
        source = kwargs["input"].strip().removeprefix("file = ")
        if secondary:
            (staging / Path(source).parent / "deposit-pdd.out").write_text("synthetic PDD")
        if fail_all or Path(source).parent.name == "seg_001":
            (staging / "phits.out").write_text(text)
            if damage == "extra":
                (staging / Path(source).parent / "deposit-unexpected.out").write_text("extra")
        return result

    summary = run_segments(workspace_root=root, paths=paths, runner=runner,
                           preflight_nonce="synthetic_nonce" if preflight else None)
    return root, manifest, paths, summary


def accept(root, summary):
    staging = summary["segments"][0]["retained_staging"]["staging_directory"]
    plan = preview(root, staging_directory=staging)
    receipt = apply(root, staging_directory=staging, expected_plan_digest=plan["plan_digest"],
                    acknowledge_research_only=True, reason="Reviewed saved synthetic recovery distribution for research.")
    return plan, receipt


def test_preview_apply_and_independent_verification_are_immutable(tmp_path):
    root, manifest, paths, summary = eligible(tmp_path, count=2)
    before = snapshot(root)
    staging = summary["segments"][0]["retained_staging"]["staging_directory"]
    plan = preview(root, staging_directory=staging)
    assert snapshot(root) == before
    assert plan["plan"]["diagnostics"]["counts"]["geometry_recovering"] == 12
    assert [p["count"] for p in plan["plan"]["region_pair_counts"]] == [5, 7]
    _, receipt = accept(root, summary)
    assert all((root / path).read_bytes() == data for path, data in before.items())
    assert validate(root, summary, manifest) == receipt
    assert str(root) not in json.dumps(receipt)
    marker = validate_segment_execution_for_downstream(root, manifest, summary)
    assert marker["accepted_segment_id"] == "seg_001"
    after = snapshot(root)
    assert main(["--workspace-root", str(root), "--verify-only"]) == 0
    assert snapshot(root) == after
    with pytest.raises(ValueError, match="already exists"):
        accept(root, summary)


@pytest.mark.parametrize("old,new", [
    ("=            0 / nlost", "=            1 / nlost"),
    ("error      =            0", "error      =            1"),
    ("=           12", "=           13"),
    ("4103        4103           7", "4101        4102           7"),
    ("4103        4103           7", "4103        4103          -7"),
    ("bat[       3]", "bat[       2]"),
    ("region1     region2       count", "unknown layout"),
])
def test_ineligible_completion_never_publishes(tmp_path, old, new):
    root, _, _, summary = eligible(tmp_path, text=FORMAT.replace(old, new))
    before = snapshot(root)
    with pytest.raises(ValueError):
        preview(root, staging_directory=summary["segments"][0]["retained_staging"]["staging_directory"])
    assert snapshot(root) == before


@pytest.mark.parametrize("damage", ["extra", "invocation", "historical", "reason", "returncode", "summary_counts", "staging", "conflict"])
def test_ineligible_binding_never_publishes(tmp_path, damage):
    root, manifest, _, summary = eligible(tmp_path, damage=damage)
    segment = summary["segments"][0]
    staging = segment["retained_staging"]["staging_directory"]
    if damage == "invocation":
        segment["retained_staging"]["run_id"] = "other"
    elif damage == "historical":
        segment.pop("retained_staging")
    elif damage == "reason":
        segment["reason"] = "stopped"
    elif damage == "returncode":
        segment["return_code"] = 1
    elif damage == "summary_counts":
        segment["geometry_diagnostics"]["counts"]["geometry_recovering"] = 99
    elif damage == "staging":
        (root / staging / "phits.out").write_text("changed")
    elif damage == "conflict":
        (root / manifest["segments"][0]["expected_output_path"]).write_text("conflict")
    summary_path(root).write_text(json.dumps(summary))
    before = snapshot(root)
    with pytest.raises(ValueError):
        preview(root, staging_directory=staging)
    assert snapshot(root) == before


@pytest.mark.parametrize("ack,reason", [(False, "reviewed"), (True, ""), (True, "C:/private/path"), (True, "/private/path")])
def test_explicit_acknowledgement_and_reason_required(tmp_path, ack, reason):
    root, _, _, summary = eligible(tmp_path)
    staging = summary["segments"][0]["retained_staging"]["staging_directory"]
    plan = preview(root, staging_directory=staging)
    before = snapshot(root)
    with pytest.raises(ValueError):
        apply(root, staging_directory=staging, expected_plan_digest=plan["plan_digest"],
              acknowledge_research_only=ack, reason=reason)
    assert snapshot(root) == before


def test_stale_plan_requires_new_preview_before_any_write(tmp_path):
    root, manifest, _, summary = eligible(tmp_path)
    staging = summary["segments"][0]["retained_staging"]["staging_directory"]
    plan = preview(root, staging_directory=staging)
    target = root / manifest["segments"][0]["expected_output_path"]
    target.write_bytes((root / staging / target.relative_to(root)).read_bytes())
    before = snapshot(root)
    with pytest.raises(ValueError, match="plan changed"):
        apply(root, staging_directory=staging, expected_plan_digest=plan["plan_digest"],
              acknowledge_research_only=True, reason="reviewed")
    assert snapshot(root) == before


@pytest.mark.parametrize("artifact", ["summary", "manifest", "phits_out", "staged", "published", "receipt"])
def test_single_byte_tampering_revokes_downstream_authority(tmp_path, artifact):
    root, manifest, _, summary = eligible(tmp_path)
    plan, _ = accept(root, summary)
    evidence = plan["plan"]
    paths = {"summary": summary_path(root), "manifest": root / evidence["manifest"]["path"],
             "phits_out": root / evidence["phits_out"]["path"],
             "staged": root / evidence["outputs"][0]["source"]["path"],
             "published": root / evidence["outputs"][0]["destination"],
             "receipt": root / RECEIPT_PATH}
    target = paths[artifact]
    raw = target.read_bytes()
    target.write_bytes(raw.replace(b"research_only", b"research_onlx", 1) if artifact == "receipt" else raw + b" ")
    before = snapshot(root)
    with pytest.raises(ValueError):
        validate_segment_execution_for_downstream(root, manifest, summary)
    assert snapshot(root) == before


def test_receipt_revalidates_after_relocation_without_rewriting_evidence(tmp_path):
    root, manifest, _, summary = eligible(tmp_path)
    _, receipt = accept(root, summary)
    before = snapshot(root)
    moved = tmp_path / "relocated"
    shutil.copytree(root, moved)
    assert validate(moved, summary, manifest) == receipt
    assert validate_segment_execution_for_downstream(moved, manifest, summary)
    assert snapshot(moved) == before


def test_larger_counts_have_no_acceptance_threshold():
    text = FORMAT.replace("           5", "           5000000000").replace(
        "           7", "           7000000000").replace("          12", "          12000000000")
    assert parse_research_geometry_completion(text.splitlines())["diagnostics"]["counts"]["geometry_recovering"] == 12000000000


@pytest.mark.parametrize("confirmed,reason", [(False, "reviewed"), (False, None), (True, None)])
def test_gui_decline_cancel_and_closure_do_not_publish(tmp_path, confirmed, reason):
    from dicomxphits.research_geometry_gui import ResearchGeometryReview
    root, _, _, summary = eligible(tmp_path)
    review = ResearchGeometryReview.prepare(root,
        summary["segments"][0]["retained_staging"]["staging_directory"], 5)
    before = snapshot(root)
    assert review.confirm(workspace_root=root, generation=5, reason=reason, confirmed=confirmed) is None
    assert snapshot(root) == before


@pytest.mark.parametrize("change", ["workspace", "generation", "empty_reason", "stale_evidence"])
def test_gui_confirmation_cannot_use_changed_selection_or_evidence(tmp_path, change):
    from dicomxphits.research_geometry_gui import ResearchGeometryReview
    root, _, _, summary = eligible(tmp_path)
    review = ResearchGeometryReview.prepare(root,
        summary["segments"][0]["retained_staging"]["staging_directory"], 5)
    if change == "stale_evidence":
        summary_path(root).write_bytes(summary_path(root).read_bytes() + b" ")
    before = snapshot(root)
    with pytest.raises(ValueError):
        review.confirm(workspace_root=tmp_path if change == "workspace" else root,
            generation=6 if change == "generation" else 5,
            reason="" if change == "empty_reason" else "Reviewed synthetic evidence", confirmed=True)
    assert snapshot(root) == before


def test_gui_uses_shared_backend_without_external_launch(tmp_path, monkeypatch):
    import subprocess
    from dicomxphits.research_geometry_gui import ResearchGeometryReview
    from dicomxphits.gui import rtdose_stage_state, RTDOSE_NOT_PREPARED
    root, manifest, _, summary = eligible(tmp_path)

    def forbidden(*args, **kwargs):
        pytest.fail("Acceptance must not launch an external process")
    monkeypatch.setattr(subprocess, "run", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(Path, "glob", forbidden)
    review = ResearchGeometryReview.prepare(root,
        summary["segments"][0]["retained_staging"]["staging_directory"], 5)
    text = review.text()
    assert all(value in text for value in ("4101", "4102", "4103", "12", "3 / 3", "RESEARCH ONLY"))
    review.confirm(workspace_root=root, generation=5, reason="Reviewed synthetic evidence", confirmed=True)
    assert validate_segment_execution_for_downstream(root, manifest, summary)
    assert rtdose_stage_state(root) == RTDOSE_NOT_PREPARED


def downstream_workspace(tmp_path):
    """Create prospective execution evidence, never retrofit a real result."""
    import subprocess
    from dicomxphits.gantry_geometry import CURRENT_GANTRY_GEOMETRY_CONTRACT, GANTRY_GEOMETRY_CONTRACT_FIELD
    from dicomxphits.prepare_3dcrt_workspace import ExternalToolPaths, write_libpath
    from test_prepare_rtdose import write_workspace, tally_output_text

    root, files = write_workspace(tmp_path)
    manifest_path = root / "segments/segment_manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest[GANTRY_GEOMETRY_CONTRACT_FIELD] = CURRENT_GANTRY_GEOMETRY_CONTRACT
    segment = manifest["segments"][0]
    segment["phits_input_path"] = "segments/seg_b0001_s0000/phits.inp"
    manifest_path.write_text(json.dumps(manifest))
    (root / segment["phits_input_path"]).write_text(
        "$OMP=1\ninfl:{libpath.inp}\n[ Parameters ]\n icntl=0\n maxbch=3\n"
        "[ T-Deposit ]\n title = Synthetic segment dose\n"
        f" file = {segment['expected_output_path']}\n[ E N D ]\n")
    for name in ("phits_generation_summary.json", "public_preparation_workspace_summary.json"):
        (root / "analysis" / name).write_text('{"synthetic":true}')
    for name in ("sumtally_generation_summary.json", "sumtally_execution_summary.json"):
        (root / "analysis" / name).unlink()
    shutil.rmtree(root / "sumtally")
    (root / segment["expected_output_path"]).unlink()
    tools = tmp_path / "fake-tools"
    tools.mkdir()
    executable = tools / "never-executed"
    executable.write_text("synthetic fake executable")
    paths = ExternalToolPaths(str(tools), str(executable), str(executable))
    write_libpath(root, phits_root_folder=str(tools))

    def runner(command, **kwargs):
        staging = Path(kwargs["cwd"])
        target = staging / segment["expected_output_path"]
        target.write_text(tally_output_text(" title = Synthetic segment dose\n"))
        target.with_name("deposit-target-3D_err.out").write_text("synthetic error")
        (staging / "phits.out").write_text(FORMAT)
        return subprocess.CompletedProcess(command, 0, stdout="synthetic", stderr="")
    summary = run_segments(workspace_root=root, paths=paths, runner=runner)
    return root, manifest, paths, summary, files


def downstream_flow(tmp_path, *, tamper_stage=None):
    import subprocess
    from dicomxphits.prepare_sumtally import generate_sumtally, run_sumtally
    from dicomxphits.prepare_rtdose import prepare_rtdose, run_rtdose
    from test_prepare_rtdose import write_dicom, write_coordinate_rtdose, tally_output_text

    root, manifest, paths, summary, _ = downstream_workspace(tmp_path)
    before = snapshot(root)
    accept(root, summary)

    def tamper(stage):
        if stage == tamper_stage:
            path = root / RECEIPT_PATH
            path.write_bytes(path.read_bytes() + b" ")

    tamper("generate")
    generation = generate_sumtally(workspace_root=root, paths=paths)
    assert generation["stage_status"] == "success"
    expected = Path(generation["outputs"]["sumtally_output"])

    def sum_runner(command, **kwargs):
        assert tamper_stage != "sum_run", "Invalid receipt reached a Sumtally runner"
        staging = Path(kwargs["cwd"])
        (staging / expected.name).write_text(tally_output_text(" title = Synthetic merged dose\n"))
        (staging / "phits.out").write_text("synthetic sum companion")
        return subprocess.CompletedProcess(command, 0, stdout="synthetic", stderr="")

    tamper("sum_run")
    execution = run_sumtally(workspace_root=root, paths=paths, runner=sum_runner)
    assert execution["stage_status"] == "success"
    template, ct = tmp_path / "template.dcm", tmp_path / "reference.dcm"
    write_dicom(template, modality="RTDOSE")
    write_dicom(ct)
    tamper("prepare")
    prepared = prepare_rtdose(workspace_root=root, paths=paths, paths_config={},
        template_dicom=template, ct_reference_dicom=ct, phits_out=root / "sumtally/phits.out")
    assert prepared["stage_status"] == "success"

    class FakeConverter:
        returncode = 0

        def communicate(self, input):
            assert tamper_stage != "dose_run", "Invalid receipt reached a converter"
            write_coordinate_rtdose(Path(input.splitlines()[3]).with_suffix(".dcm"))
            return "synthetic conversion", None

    tamper("dose_run")
    converted = run_rtdose(workspace_root=root, paths=paths, runner=lambda *a, **kw: FakeConverter())
    assert converted["stage_status"] == "success"
    marker = validate_segment_execution_for_downstream(root, manifest, summary)
    assert all(stage["research_exception"] == marker for stage in (generation, execution, prepared, converted))
    assert all((root / path).read_bytes() == data for path, data in before.items())
    assert json.loads(summary_path(root).read_text())["segments"][0]["status"] == "failed"


def test_receipt_flow_through_all_four_downstream_stages(tmp_path):
    downstream_flow(tmp_path)


@pytest.mark.parametrize("stage", ["generate", "sum_run", "prepare", "dose_run"])
def test_each_downstream_stage_revalidates_receipt_before_execution(tmp_path, stage):
    from dicomxphits.sumtally_inputs import file_sha256
    with pytest.raises(ValueError, match="Research acceptance is invalid"):
        downstream_flow(tmp_path, tamper_stage=stage)
    root = tmp_path / "workspace"
    receipt = json.loads((root / RECEIPT_PATH).read_text())
    assert file_sha256(summary_path(root)) == receipt["plan"]["summary"]["sha256"]
    assert json.loads(summary_path(root).read_text())["segments"][0]["status"] == "failed"


def test_preflight_and_every_bound_staging_file_are_revalidated(tmp_path):
    root, manifest, _, summary = eligible(tmp_path, preflight=True)
    before = snapshot(root)
    plan, _ = accept(root, summary)
    assert plan["plan"]["preflight"]["path"] == "analysis/segment_preflight.json"
    assert all((root / p).read_bytes() == data for p, data in before.items())
    path = root / "analysis/segment_preflight.json"
    path.write_bytes(path.read_bytes() + b" ")
    with pytest.raises(ValueError):
        validate_segment_execution_for_downstream(root, manifest, summary)


def test_more_than_one_failed_segment_is_not_eligible(tmp_path):
    root, _, _, summary = eligible(tmp_path, count=2, fail_all=True)
    before = snapshot(root)
    with pytest.raises(ValueError, match="exactly one"):
        preview(root, staging_directory=summary["segments"][0]["retained_staging"]["staging_directory"])
    assert snapshot(root) == before


def test_exact_manifest_derived_secondary_output_set_and_receipt_last(tmp_path, monkeypatch):
    import dicomxphits.research_geometry_recovery as backend
    root, _, _, summary = eligible(tmp_path, secondary=True)
    calls = []
    publish, publish_receipt = backend._publish_file_new_only, backend._publish_json_new_only

    def tally(*args, **kwargs):
        calls.append(args[2].name)
        assert not (root / RECEIPT_PATH).exists()
        return publish(*args, **kwargs)

    def receipt(*args, **kwargs):
        assert set(calls) == {"deposit-pdd.out", "deposit-target-3D.out", "deposit-target-3D_err.out"}
        calls.append("receipt")
        return publish_receipt(*args, **kwargs)

    monkeypatch.setattr(backend, "_publish_file_new_only", tally)
    monkeypatch.setattr(backend, "_publish_json_new_only", receipt)
    plan, _ = accept(root, summary)
    assert len(plan["plan"]["outputs"]) == 3
    assert calls[-1] == "receipt"
    validate(root)


@pytest.mark.parametrize("selection", ["", "../outside", "/absolute", "analysis/.phits-segment-run-other"])
def test_explicit_staging_cannot_be_substituted_or_discovered(tmp_path, selection):
    root, _, _, _ = eligible(tmp_path)
    before = snapshot(root)
    with pytest.raises((OSError, ValueError)):
        preview(root, staging_directory=selection)
    assert snapshot(root) == before


def test_competing_workspace_owner_blocks_preview_and_apply(tmp_path):
    import threading
    from dicomxphits.workspace_execution import WorkspaceExecutionLease, WorkspaceBusyError
    root, _, _, summary = eligible(tmp_path)
    staging = summary["segments"][0]["retained_staging"]["staging_directory"]
    plan = preview(root, staging_directory=staging)
    acquired, release = threading.Event(), threading.Event()
    before = snapshot(root)

    def owner():
        with WorkspaceExecutionLease(root, create=False):
            acquired.set()
            release.wait(20)
    worker = threading.Thread(target=owner)
    worker.start()
    assert acquired.wait(10)
    try:
        with pytest.raises(WorkspaceBusyError):
            preview(root, staging_directory=staging)
        with pytest.raises(WorkspaceBusyError):
            apply(root, staging_directory=staging, expected_plan_digest=plan["plan_digest"],
                  acknowledge_research_only=True, reason="reviewed")
    finally:
        release.set()
        worker.join(10)
    assert snapshot(root) == before


def test_larger_positive_recovering_total_is_eligible_for_explicit_acceptance(tmp_path):
    text = FORMAT.replace("           5", "           5000000000").replace(
        "           7", "           7000000000").replace("          12", "          12000000000")
    root, _, _, summary = eligible(tmp_path, text=text)
    plan, _ = accept(root, summary)
    assert plan["plan"]["diagnostics"]["counts"]["geometry_recovering"] == 12000000000
    validate(root)


@pytest.mark.parametrize("content", ["", "[]", "{}", "not JSON",
    '{"schema_version":"dicomxphits_research_geometry_recovery_acceptance_v1"}'])
def test_malformed_and_prototype_receipts_never_authorize_downstream(tmp_path, content):
    root, manifest, _, summary = eligible(tmp_path)
    (root / RECEIPT_PATH).write_text(content)
    before = snapshot(root)
    with pytest.raises(ValueError):
        validate_segment_execution_for_downstream(root, manifest, summary)
    assert snapshot(root) == before


@pytest.mark.parametrize("artifact", ["published", "staged_input", "extra_staging_file", "receipt_whitespace"])
def test_all_retained_and_receipt_bytes_are_protected(tmp_path, artifact):
    root, manifest, _, summary = eligible(tmp_path)
    plan, _ = accept(root, summary)
    context = plan["plan"]
    if artifact == "staged_input":
        path = root / context["staging"]["inputs"][0]["path"]
    elif artifact == "published":
        path = root / context["outputs"][0]["destination"]
        path.unlink()
    elif artifact == "extra_staging_file":
        path = root / context["staging"]["staging_directory"] / "unexpected.txt"
    else:
        path = root / RECEIPT_PATH
    path.write_bytes((path.read_bytes() if path.exists() else b"") + b" ")
    with pytest.raises(ValueError):
        validate_segment_execution_for_downstream(root, manifest, summary)


def test_acceptance_refuses_linked_staging_artifacts(tmp_path):
    root, _, _, summary = eligible(tmp_path)
    stage = root / summary["segments"][0]["retained_staging"]["staging_directory"]
    target = tmp_path / "outside.txt"
    target.write_text("outside must never be used")
    link = stage / "linked.txt"
    try:
        link.symlink_to(target)
    except OSError:
        pytest.skip("Symbolic link creation requires platform privileges")
    with pytest.raises(ValueError):
        preview(root, staging_directory=stage.relative_to(root).as_posix())
    assert target.read_text() == "outside must never be used"


def test_receipt_rejects_absolute_path_in_version_even_with_recomputed_checksum(tmp_path):
    from dicomxphits.segment_retry import digest_object
    from dicomxphits.safe_output import WorkspaceOutputGuard
    root, manifest, _, summary = eligible(tmp_path)
    _, receipt = accept(root, summary)
    receipt["tool_version"] = "/synthetic/unsupported/version"
    receipt["receipt_content_sha256"] = digest_object(
        {k: v for k, v in receipt.items() if k != "receipt_content_sha256"})
    with WorkspaceOutputGuard(root) as guard:
        guard.write_json(root / RECEIPT_PATH, receipt)
    with pytest.raises(ValueError):
        validate_segment_execution_for_downstream(root, manifest, summary)
