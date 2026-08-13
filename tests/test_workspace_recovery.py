from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

PUBLIC_SRC = Path(__file__).resolve().parents[1] / "src"
if str(PUBLIC_SRC) not in sys.path:
    sys.path.insert(0, str(PUBLIC_SRC))

import dicomxphits.gui as gui_module
import dicomxphits.workspace_recovery as recovery_module
from dicomxphits.fix_coordinates import AXIS_MAPPING, SCHEMA_VERSION
from dicomxphits.gui import GuiConfig, StageResult, run_workspace_recovery
from dicomxphits.sumtally_inputs import file_sha256, manifest_sha256
from dicomxphits.workspace_recovery import (
    FULL_DOWNSTREAM_SEQUENCE,
    RECOVERY_COMPLETE,
    RECOVERY_INVALID,
    RECOVERY_READY,
    WorkspaceRecoveryError,
    WorkspaceRecoveryInspection,
    inspect_existing_workspace,
    preserve_downstream_for_recovery,
    rebind_workspace_path,
    standard_ct2phits_handoff,
)


def write_file(path: Path, text: str = "x") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def write_recoverable_workspace(tmp_path: Path, *, old_root: str | None = None) -> Path:
    workspace = tmp_path / "case-3dcrt"
    segment = {
        "segment_id": "seg_001",
        "beam_number": 1,
        "delivery_type": "3dcrt",
        "beam_meterset_mu": 100.0,
        "segment_mu": 100.0,
        "mu_weight": 100.0,
        "mu_weight_unit": "MU",
        "phits_input_path": "segments/seg_001/phits.inp",
        "expected_output_path": "segments/seg_001/deposit-target-3D.out",
    }
    manifest = {
        "schema_version": "segment_manifest_v2",
        "case_id": "synthetic",
        "workflow_mode": "full_plan",
        "plan_total_mu": 100.0,
        "included_total_mu": 100.0,
        "dose_normalization_mu": 100.0,
        "segments": [segment],
    }
    write_file(
        workspace / "segments" / "segment_manifest.json",
        json.dumps(manifest),
    )
    output = write_file(
        workspace / segment["expected_output_path"],
        "synthetic PHITS tally",
    )
    write_file(
        workspace / "analysis" / "segment_execution_summary.json",
        json.dumps({"stage_status": "success"}),
    )
    recorded_root = old_root or str(workspace.resolve())
    recorded_output = (
        str(output.resolve())
        if old_root is None
        else old_root.rstrip("\\/")
        + "\\segments\\seg_001\\deposit-target-3D.out"
    )
    write_file(
        workspace / "analysis" / "sumtally_execution_summary.json",
        json.dumps(
            {
                "stage_status": "success",
                "workspace_root": recorded_root,
                "manifest_sha256": manifest_sha256(manifest),
                "segment_output_evidence": [
                    {"path": recorded_output, "sha256": file_sha256(output)}
                ],
            }
        ),
    )
    return workspace


def test_missing_generation_summary_recovers_from_matching_execution_digest(
    tmp_path: Path,
) -> None:
    workspace = write_recoverable_workspace(tmp_path)

    inspection = inspect_existing_workspace(workspace)

    assert inspection.state == RECOVERY_READY
    assert inspection.highest_verified_stage == "PHITS completed"
    assert inspection.stage_sequence == FULL_DOWNSTREAM_SEQUENCE
    assert inspection.phits_reusable is True
    assert "without rerunning PHITS" in inspection.message


def test_relocated_windows_evidence_rebinds_only_below_old_workspace(
    tmp_path: Path,
) -> None:
    workspace = write_recoverable_workspace(
        tmp_path,
        old_root=r"D:\old-machine\case-3dcrt",
    )

    inspection = inspect_existing_workspace(workspace)

    assert inspection.state == RECOVERY_READY
    assert rebind_workspace_path(
        r"D:\old-machine\case-3dcrt\segments\seg_001\deposit-target-3D.out",
        recorded_workspace_root=r"D:\old-machine\case-3dcrt",
        current_workspace_root=workspace,
    ) == (workspace / "segments" / "seg_001" / "deposit-target-3D.out").resolve()
    with pytest.raises(WorkspaceRecoveryError, match="outside"):
        rebind_workspace_path(
            r"D:\licensed-tool\phits.exe",
            recorded_workspace_root=r"D:\old-machine\case-3dcrt",
            current_workspace_root=workspace,
        )


def test_changed_segment_output_blocks_phits_reuse(tmp_path: Path) -> None:
    workspace = write_recoverable_workspace(tmp_path)
    write_file(
        workspace / "segments" / "seg_001" / "deposit-target-3D.out",
        "changed",
    )

    inspection = inspect_existing_workspace(workspace)

    assert inspection.state == RECOVERY_INVALID
    assert inspection.phits_reusable is False
    assert "SHA-256" in inspection.message


def test_missing_segment_output_blocks_phits_reuse(tmp_path: Path) -> None:
    workspace = write_recoverable_workspace(tmp_path)
    (workspace / "segments" / "seg_001" / "deposit-target-3D.out").unlink()

    inspection = inspect_existing_workspace(workspace)

    assert inspection.state == RECOVERY_INVALID
    assert inspection.phits_reusable is False
    assert "PHITS segment output is missing" in inspection.message


def test_standard_handoff_uses_one_bounded_deterministic_candidate(
    tmp_path: Path,
) -> None:
    rtphits = tmp_path / "RTphits"
    workspace = tmp_path / "results" / "case-3dcrt"
    candidate = rtphits / "work" / "case-ct2phits"
    write_file(
        candidate / "ct2phits_execution_summary.json",
        json.dumps({"status": "completed"}),
    )
    write_file(candidate / "RTPLAN.dcm")
    write_file(candidate / "CT" / "CT000001.dcm")
    (candidate / "DATfiles").mkdir(parents=True)

    handoff = standard_ct2phits_handoff(workspace, rtphits_root=rtphits)

    assert handoff == {
        "rtplan_path": str((candidate / "RTPLAN.dcm").resolve()),
        "ct_reference_dicom": str((candidate / "CT" / "CT000001.dcm").resolve()),
        "ct_datfiles_root": str((candidate / "DATfiles").resolve()),
    }
    assert standard_ct2phits_handoff(
        tmp_path / "case-without-suffix",
        rtphits_root=rtphits,
    ) is None


def test_downstream_recovery_preserves_history_without_moving_phits(
    tmp_path: Path,
) -> None:
    workspace = write_recoverable_workspace(tmp_path)
    phits_output = workspace / "segments" / "seg_001" / "deposit-target-3D.out"
    write_file(workspace / "sumtally" / "sumtally.inp", "historical")
    write_file(workspace / "rtdose" / "historical.dcm", "historical dose")
    write_file(
        workspace / "analysis" / "sumtally_generation_summary.json",
        "historical generation",
    )

    history = preserve_downstream_for_recovery(
        workspace,
        stage_sequence=FULL_DOWNSTREAM_SEQUENCE,
    )

    assert history is not None
    assert phits_output.read_text(encoding="utf-8") == "synthetic PHITS tally"
    assert not (workspace / "sumtally").exists()
    assert not (workspace / "rtdose").exists()
    manifest = json.loads(history.manifest_path.read_text(encoding="utf-8"))
    assert manifest["phits_segment_outputs_moved"] is False
    preserved = {item["original_relative_path"] for item in manifest["files"]}
    assert "sumtally/sumtally.inp" in preserved
    assert "rtdose/historical.dcm" in preserved
    assert "analysis/sumtally_generation_summary.json" in preserved
    assert inspect_existing_workspace(workspace).state == RECOVERY_READY


def test_gui_recovery_runs_only_inspected_downstream_suffix(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    inspection = WorkspaceRecoveryInspection(
        workspace,
        RECOVERY_READY,
        "PHITS completed",
        "generate_sumtally",
        FULL_DOWNSTREAM_SEQUENCE,
        "ready",
        True,
    )
    config = GuiConfig("", str(workspace), "", "", "", "", "", "")
    calls: list[str] = []
    monkeypatch.setattr(
        gui_module,
        "preserve_downstream_for_recovery",
        lambda *args, **kwargs: None,
    )

    def fake_stage_runner(_config: GuiConfig, stage_key: str) -> StageResult:
        calls.append(stage_key)
        return StageResult(
            stage_key,
            [stage_key],
            0,
            workspace / f"{stage_key}.json",
            {"stage_status": "success"},
            "",
            "",
        )

    run_workspace_recovery(config, inspection, stage_runner=fake_stage_runner)

    assert calls == list(FULL_DOWNSTREAM_SEQUENCE)
    assert not {"run_ct2phits", "prepare_workspace", "run_segments"}.intersection(calls)


def test_completed_recovery_requires_current_coordinate_and_semantic_proof(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = write_recoverable_workspace(tmp_path)
    binding = {"synthetic": "current"}
    prepare_path = write_file(
        workspace / "analysis" / "rtdose_conversion_prepare_summary.json",
        json.dumps(
            {
                "stage_status": "success",
                "rtdose_placement": {"schema_version": "synthetic"},
                "sumtally_manifest_binding": binding,
            }
        ),
    )
    final_output = write_file(workspace / "sumtally" / "dose.fixed.dcm", "dose")
    execution_path = workspace / "analysis" / "rtdose_conversion_execution_summary.json"
    execution = {
        "stage_status": "success",
        "workspace_root": str(workspace.resolve()),
        "rtdose_prepare_summary_sha256": file_sha256(prepare_path),
        "coordinate_corrected_rtdose_output": str(final_output.resolve()),
        "coordinate_corrected_rtdose_output_relative": "sumtally/dose.fixed.dcm",
        "coordinate_corrected_rtdose_output_exists": True,
        "coordinate_corrected_rtdose_output_sha256": file_sha256(final_output),
        "coordinate_placement_validation": {"validated": True},
        "coordinate_correction": {
            "schema_version": SCHEMA_VERSION,
            "axis_mapping": AXIS_MAPPING,
            "invariants": {
                "stored_value_multiset_preserved": True,
                "iec_x_to_dicom_x_reversal_applied": True,
            },
        },
        "final_semantic_validation": {"validated": True},
    }
    write_file(execution_path, json.dumps(execution))
    monkeypatch.setattr(
        recovery_module,
        "_current_sumtally_binding",
        lambda _workspace: binding,
    )

    completed = inspect_existing_workspace(workspace)

    assert completed.state == RECOVERY_COMPLETE
    assert completed.final_output == final_output.resolve()

    execution["coordinate_correction"]["axis_mapping"] = (
        "phits2dicom_frames_rows_columns_to_dicom_rows_frames_columns_v1"
    )
    write_file(execution_path, json.dumps(execution))

    stale_axis_mapping = inspect_existing_workspace(workspace)
    assert stale_axis_mapping.state == RECOVERY_READY
    assert stale_axis_mapping.stage_sequence == ("run_rtdose",)

    execution["coordinate_correction"]["axis_mapping"] = AXIS_MAPPING
    execution.pop("final_semantic_validation")
    write_file(execution_path, json.dumps(execution))

    incomplete = inspect_existing_workspace(workspace)
    assert incomplete.state == RECOVERY_READY
    assert incomplete.stage_sequence == ("run_rtdose",)

    execution["final_semantic_validation"] = {"validated": True}
    write_file(execution_path, json.dumps(execution))
    final_output.unlink()

    missing_output = inspect_existing_workspace(workspace)
    assert missing_output.state == RECOVERY_READY
    assert missing_output.stage_sequence == ("run_rtdose",)
