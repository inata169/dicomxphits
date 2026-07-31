from __future__ import annotations

import inspect
import json
import subprocess
import sys
from pathlib import Path

import pytest

PUBLIC_SRC = Path(__file__).resolve().parents[1] / "src"
if str(PUBLIC_SRC) not in sys.path:
    sys.path.insert(0, str(PUBLIC_SRC))

from dicomxphits.prepare_3dcrt_workspace import ExternalToolPaths
from dicomxphits.prepare_sumtally import (
    DEFAULT_SUMTALLY_OUTPUT_NAME,
    build_generate_parser,
    generate_sumtally,
    run_main,
    run_sumtally,
    select_sumtally_base_input,
)


def active_segment(index=0, **overrides):
    segment = {
        "segment_id": f"seg_{index + 1:03d}",
        "beam_number": 1,
        "segment_index": index,
        "delivery_type": "3dcrt",
        "beam_meterset_mu": 100.0,
        "segment_mu": 50.0,
        "mu_weight": 50.0,
        "mu_weight_unit": "MU",
        "phits_input_path": f"segments/seg_{index + 1:03d}/phits.inp",
        "expected_output_path": f"segments/seg_{index + 1:03d}/deposit-target-3D.out",
    }
    segment.update(overrides)
    return segment


def write_workspace(tmp_path, *segments, metadata=None):
    workspace = tmp_path / "workspace"
    manifest = {
        "schema_version": "segment_manifest_v2",
        "case_id": "synthetic",
        "workflow_mode": "full_plan",
        "dose_normalization_mu": 100.0,
        "segments": list(segments) or [active_segment(0), active_segment(1)],
    }
    manifest_path = workspace / "segments" / "segment_manifest.json"
    manifest_path.parent.mkdir(parents=True)
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    for segment in manifest["segments"]:
        phits_path = workspace / segment["phits_input_path"]
        phits_path.parent.mkdir(parents=True, exist_ok=True)
        expected_output_name = Path(str(segment["expected_output_path"]).replace("\\", "/")).name
        phits_path.write_text(
            "[ Parameters ]\n"
            "  icntl = 0\n"
            "  file(6) = phits.out\n"
            "[ T-Deposit ]\n"
            "  title = Segment dose placeholder\n"
            f"  file = {expected_output_name}\n"
            "[ E N D ]\n",
            encoding="utf-8",
        )
    if metadata is not None:
        summary_path = workspace / "analysis" / "public_preparation_workspace_summary.json"
        summary_path.parent.mkdir(parents=True, exist_ok=True)
        summary_path.write_text(json.dumps(metadata), encoding="utf-8")
    return workspace, manifest


def paths(phits2dicom=None):
    return ExternalToolPaths(
        phits_root_folder="/opt/phits-root",
        phits_executable_path="/opt/phits-root/bin/phits",
        phits2dicom_executable_path=phits2dicom,
    )


def test_generate_sumtally_records_all_segments_totalfield_contract(tmp_path):
    workspace, _ = write_workspace(tmp_path)

    summary = generate_sumtally(workspace_root=workspace, paths=paths(), command_argv=["generate"])

    assert summary["stage_status"] == "success"
    assert summary["sumtally_scope"] == "all_active_segments"
    assert summary["sumtally_mode"] == "totalfield"
    assert summary["weight_field"] == "segment_mu"
    assert summary["sumtally_normalization"] == "all_segments_totalfield_segment_mu"
    assert summary["rt_dose_conversion_hint"] == {
        "input_dose_state": "sumtally_mu_weighted",
        "sumtally_normalization": "all_segments_totalfield_segment_mu",
        "is_beam_mu_output": False,
    }
    assert (workspace / "sumtally" / "sumtally.inp").is_file()
    assert Path(summary["outputs"]["sum_input"]).is_file()
    assert summary["outputs"]["sumtally_output"].endswith(DEFAULT_SUMTALLY_OUTPUT_NAME)
    assert summary["sumtally_input_path_basis"] == "sumtally_cwd_relative"
    assert summary["sumtally_segment_paths"][0]["resolved_output_path"].replace("\\", "/").endswith("segments/seg_001/deposit-target-3D.out")
    assert summary["sumtally_segment_paths"][0]["sumtally_cwd_relative_output_path"] == "../segments/seg_001/deposit-target-3D.out"
    assert summary["sumtally_segment_paths"][0]["sumtally_written_output_path"] == "../segments/seg_001/deposit-target-3D.out"
    content = (workspace / "sumtally" / "sumtally.inp").read_text(encoding="utf-8")
    assert "isumtally = 2" in content
    assert "seg_001/deposit-target-3D.out  50" in content


def test_generate_sumtally_is_standalone_without_project_root(tmp_path):
    workspace, _ = write_workspace(tmp_path)

    summary = generate_sumtally(workspace_root=workspace, paths=paths(), command_argv=["generate"])
    parser_actions = {action.dest for action in build_generate_parser()._actions}

    assert summary["stage_status"] == "success"
    assert "project_root" not in inspect.signature(generate_sumtally).parameters
    assert "project_root" not in parser_actions


def test_generate_sumtally_paths_are_readable_from_sumtally_cwd(tmp_path):
    workspace, _ = write_workspace(tmp_path)

    summary = generate_sumtally(workspace_root=workspace, paths=paths(), command_argv=["generate"])
    sumtally_dir = workspace / "sumtally"
    content = (sumtally_dir / "sumtally.inp").read_text(encoding="utf-8")
    written_paths = [
        line.split()[0]
        for line in content.splitlines()
        if "deposit-target-3D.out" in line and not line.lstrip().startswith("sfile")
    ]
    assert written_paths
    for written in written_paths:
        assert (sumtally_dir / written).resolve().parent.name in {"seg_001", "seg_002"}


def test_generate_sumtally_external_segment_output_uses_absolute_fallback(tmp_path):
    external_output = tmp_path / "external" / "dose.out"
    segment = active_segment(0, expected_output_path=str(external_output))
    workspace, _ = write_workspace(tmp_path, segment)

    summary = generate_sumtally(workspace_root=workspace, paths=paths(), command_argv=["generate"])

    record = summary["sumtally_segment_paths"][0]
    assert summary["sumtally_input_path_basis"] == "mixed_cwd_relative_absolute_fallback"
    assert record["sumtally_cwd_relative_output_path"] is None
    assert record["sumtally_path_basis"] == "absolute_fallback_workspace_external"
    assert record["sumtally_written_output_path"] == external_output.resolve().as_posix()
    content = (workspace / "sumtally" / "sumtally.inp").read_text(encoding="utf-8")
    assert external_output.resolve().as_posix() in content


def test_generate_sumtally_derives_tally_pattern_from_manifest_output_name(tmp_path):
    segment = active_segment(0, expected_output_path="segments/seg_001/dose.out")
    workspace, _ = write_workspace(tmp_path, segment)

    summary = generate_sumtally(workspace_root=workspace, paths=paths(), command_argv=["generate"])

    wrapper_content = Path(summary["outputs"]["sum_input"]).read_text(encoding="utf-8")
    assert "file = segments/seg_001/dose.out" in summary["tally_patterns"]
    assert "file = dose.out" in summary["tally_patterns"]
    assert "dose" not in summary["tally_patterns"]
    assert "file = dose.out" in wrapper_content
    assert "infl:{sumtally.inp}" in wrapper_content
    assert "[ T-Deposit ] off" not in wrapper_content


def test_generate_sumtally_does_not_match_generic_output_name_stem(tmp_path):
    segment = active_segment(0, expected_output_path="segments/seg_001/dose.out")
    workspace, _ = write_workspace(tmp_path, segment)
    phits_input = workspace / "segments" / "seg_001" / "phits.inp"
    phits_input.write_text(
        "[ Parameters ]\n"
        "  icntl = 0\n"
        "  file(6) = phits.out\n"
        "[ T-Deposit ]\n"
        "  title = Target dose\n"
        "  file = dose.out\n"
        "[ T-Deposit ]\n"
        "  title = Unrelated dose-like tally\n"
        "  file = predose.out\n"
        "[ E N D ]\n",
        encoding="utf-8",
    )

    summary = generate_sumtally(workspace_root=workspace, paths=paths(), command_argv=["generate"])

    wrapper_content = Path(summary["outputs"]["sum_input"]).read_text(encoding="utf-8")
    assert wrapper_content.count("infl:{sumtally.inp}") == 1
    assert "file = predose.out" in wrapper_content
    assert "[ T-Deposit ] off" in wrapper_content


def test_generate_sumtally_matches_manifest_relative_output_path(tmp_path):
    segment = active_segment(0, expected_output_path="phits_outputs/seg_001/dose.out")
    workspace, _ = write_workspace(tmp_path, segment)
    phits_input = workspace / "segments" / "seg_001" / "phits.inp"
    phits_input.write_text(
        "[ Parameters ]\n"
        "  icntl = 0\n"
        "  file(6) = phits.out\n"
        "[ T-Deposit ]\n"
        "  title = Target manifest-relative dose\n"
        "  file = phits_outputs/seg_001/dose.out\n"
        "[ T-Deposit ]\n"
        "  title = Unrelated dose-like tally\n"
        "  file = phits_outputs/seg_001/predose.out\n"
        "[ E N D ]\n",
        encoding="utf-8",
    )

    summary = generate_sumtally(workspace_root=workspace, paths=paths(), command_argv=["generate"])

    wrapper_content = Path(summary["outputs"]["sum_input"]).read_text(encoding="utf-8")
    assert "file = phits_outputs/seg_001/dose.out" in summary["tally_patterns"]
    assert wrapper_content.count("infl:{sumtally.inp}") == 1
    assert "file = phits_outputs/seg_001/predose.out" in wrapper_content
    assert "[ T-Deposit ] off" in wrapper_content


def test_phits2dicom_path_absence_does_not_block_generation(tmp_path):
    workspace, _ = write_workspace(tmp_path)

    summary = generate_sumtally(workspace_root=workspace, paths=paths(phits2dicom=None), command_argv=["generate"])

    assert summary["stage_status"] == "success"
    assert summary["path_config"]["phits2dicom_executable_path"] is None


def test_base_input_selection_precedence(tmp_path):
    explicit_workspace, manifest = write_workspace(tmp_path / "explicit")
    explicit = explicit_workspace / "custom_base.inp"
    explicit.write_text("[ Parameters ]\n", encoding="utf-8")
    selected = select_sumtally_base_input(
        workspace_root=explicit_workspace,
        manifest=manifest,
        explicit_base_input=explicit,
    )
    assert selected.path == explicit
    assert selected.rule == "explicit_base_input"

    metadata_workspace, manifest = write_workspace(
        tmp_path / "metadata",
        metadata={"phits_generation": {"primary_phits_input": "segments/seg_002/phits.inp"}},
    )
    selected = select_sumtally_base_input(workspace_root=metadata_workspace, manifest=manifest)
    assert selected.path == metadata_workspace / "segments" / "seg_002" / "phits.inp"
    assert selected.rule == "workspace_metadata"

    fallback_workspace, manifest = write_workspace(tmp_path / "fallback")
    selected = select_sumtally_base_input(workspace_root=fallback_workspace, manifest=manifest)
    assert selected.path == fallback_workspace / "segments" / "seg_001" / "phits.inp"
    assert selected.rule == "first_active_segment_phits_input"


@pytest.mark.parametrize(
    "segment, message",
    [
        (active_segment(0, skip_reason="filtered"), "at least one non-skipped segment"),
        (active_segment(0, delivery_type="vmat"), "delivery_type must be 3dcrt"),
        (active_segment(0, beam_meterset_mu=0.0), "beam_meterset_mu"),
        (active_segment(0, segment_mu=0.0), "segment_mu"),
    ],
)
def test_generate_sumtally_writes_failure_summary_on_gate_failure(tmp_path, segment, message):
    workspace, _ = write_workspace(tmp_path, segment)

    with pytest.raises(Exception, match=message):
        generate_sumtally(workspace_root=workspace, paths=paths(), command_argv=["generate"])

    summary = json.loads((workspace / "analysis" / "sumtally_generation_summary.json").read_text(encoding="utf-8"))
    assert summary["stage_status"] == "gate_failed"
    assert summary["phits_execution_started"] is False
    assert message in summary["failure_reason"]


def test_run_sumtally_rejects_missing_segment_outputs(tmp_path):
    workspace, _ = write_workspace(tmp_path)
    generate_sumtally(workspace_root=workspace, paths=paths(), command_argv=["generate"])

    with pytest.raises(FileNotFoundError, match="Expected segment PHITS output"):
        run_sumtally(workspace_root=workspace, paths=paths(), command_argv=["run"])

    summary = json.loads((workspace / "analysis" / "sumtally_execution_summary.json").read_text(encoding="utf-8"))
    assert summary["stage_status"] == "gate_failed"
    assert summary["phits_execution_started"] is False


def test_run_sumtally_records_execution_outputs(monkeypatch, tmp_path):
    workspace, _ = write_workspace(tmp_path)
    generation = generate_sumtally(workspace_root=workspace, paths=paths(), command_argv=["generate"])
    for dose_path in [workspace / "segments" / "seg_001" / "deposit-target-3D.out", workspace / "segments" / "seg_002" / "deposit-target-3D.out"]:
        dose_path.write_text("segment dose", encoding="utf-8")
    expected_output = Path(generation["outputs"]["sumtally_output"])

    calls = {}

    def fake_runner(cmd, **kwargs):
        calls["cmd"] = cmd
        calls["cwd"] = kwargs["cwd"]
        calls["stdin_name"] = kwargs["stdin"].name
        calls["capture_output"] = kwargs["capture_output"]
        calls["text"] = kwargs["text"]
        calls["shell"] = kwargs["shell"]
        expected_output.write_text("merged dose", encoding="utf-8")
        return subprocess.CompletedProcess(cmd, 0, stdout="sum ok", stderr="sum warn")

    summary = run_sumtally(
        workspace_root=workspace,
        paths=paths(phits2dicom=None),
        command_argv=["run"],
        runner=fake_runner,
    )

    assert calls["cmd"] == ["/opt/phits-root/bin/phits"]
    assert calls["cwd"] == Path(generation["outputs"]["sum_input"]).parent
    assert calls["stdin_name"] == generation["outputs"]["sum_input"]
    assert calls["capture_output"] is True
    assert calls["text"] is True
    assert calls["shell"] is False
    assert summary["returncode"] == 0
    assert summary["phits_execution_started"] is True
    assert summary["expected_sumtally_output_exists"] is True
    assert summary["expected_sumtally_output_size"] == len("merged dose")
    assert Path(summary["stdout_path"]).read_text(encoding="utf-8") == "sum ok"
    assert Path(summary["stderr_path"]).read_text(encoding="utf-8") == "sum warn"
    assert summary["rt_dose_conversion_hint"]["is_beam_mu_output"] is False


def test_run_main_returns_nonzero_when_sumtally_summary_failed(monkeypatch, tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    def fake_run_sumtally(**kwargs):
        return {"stage_status": "failed"}

    monkeypatch.setattr("dicomxphits.prepare_sumtally.run_sumtally", fake_run_sumtally)

    result = run_main(
        [
            "--workspace-root",
            str(workspace),
            "--phits-executable-path",
            "/opt/phits-root/bin/phits",
        ]
    )

    assert result == 3
