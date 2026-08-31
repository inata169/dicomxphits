from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

PUBLIC_SRC = Path(__file__).resolve().parents[1] / "src"
if str(PUBLIC_SRC) not in sys.path:
    sys.path.insert(0, str(PUBLIC_SRC))

import dicomxphits.gui as gui_module
import dicomxphits.prepare_rtdose as prepare_rtdose_module
import dicomxphits.workspace_recovery as recovery_module
from dicomxphits.fix_coordinates import AXIS_MAPPING, SCHEMA_VERSION
from dicomxphits.gantry_geometry import (
    CURRENT_GANTRY_GEOMETRY_CONTRACT,
    GANTRY_GEOMETRY_CONTRACT_FIELD,
    PREVIOUS_GANTRY_GEOMETRY_CONTRACT,
)
from dicomxphits.gui import GuiConfig, StageResult, run_workspace_recovery
from dicomxphits.phits_geometry_diagnostics import (
    GEOMETRY_DIAGNOSTICS_SCHEMA_VERSION,
)
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
    rtdose_plan_evidence_is_current,
    standard_ct2phits_handoff,
)


def write_file(path: Path, text: str = "x") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def synthetic_course_dose_evidence(
    *,
    rtplan_sha256: str = "a" * 64,
    planned_fraction_count: int = 1,
) -> dict[str, object]:
    return {
        "contract_version": "dicomxphits_plan_course_dose_v1",
        "input_dose_state": "sumtally_one_fraction_delivery_dose",
        "input_dose_unit": "GY",
        "fraction_group_number": 1,
        "planned_fraction_count": planned_fraction_count,
        "public_model_base_factor": 1.0,
        "effective_phits2dicom_factor": float(planned_fraction_count),
        "equation": "course_dose = dose_per_fraction * NumberOfFractionsPlanned",
        "rtplan_sha256": rtplan_sha256,
        "validated": True,
    }


def synthetic_full_plan_evidence(
    rtplan_path: Path,
    *,
    workspace_root: Path | None = None,
) -> dict[str, object]:
    planned_fraction_count = int(rtplan_path.read_text(encoding="utf-8"))
    evidence: dict[str, object] = {
        "rtplan_path": str(rtplan_path.resolve()),
        "rtplan_sha256": file_sha256(rtplan_path),
        "fraction_group_number": 1,
        "planned_fraction_count": planned_fraction_count,
    }
    if workspace_root is not None:
        evidence["manifest_path"] = str(
            (workspace_root / "segments" / "segment_manifest.json").resolve()
        )
    return evidence


def write_recoverable_workspace(
    tmp_path: Path,
    *,
    old_root: str | None = None,
    gantry_angle_deg: float = 90.0,
    collimator_angle_deg: float = 0.0,
    geometry_contract: str | None = CURRENT_GANTRY_GEOMETRY_CONTRACT,
    resolved_mlc_positions_mm: dict[str, list[float]] | None = None,
) -> Path:
    workspace = tmp_path / "case-3dcrt"
    segment = {
        "segment_id": "seg_001",
        "beam_number": 1,
        "delivery_type": "3dcrt",
        "beam_meterset_mu": 100.0,
        "segment_mu": 100.0,
        "mu_weight": 100.0,
        "mu_weight_unit": "MU",
        "gantry_angle_deg": gantry_angle_deg,
        "collimator_angle_deg": collimator_angle_deg,
        "phits_input_path": "segments/seg_001/phits.inp",
        "expected_output_path": "segments/seg_001/deposit-target-3D.out",
    }
    if resolved_mlc_positions_mm is not None:
        segment["mlc_aperture_state"] = "present"
        segment["resolved_mlc_positions_mm"] = resolved_mlc_positions_mm
    manifest = {
        "schema_version": "segment_manifest_v2",
        "case_id": "synthetic",
        "workflow_mode": "full_plan",
        "plan_total_mu": 100.0,
        "included_total_mu": 100.0,
        "dose_normalization_mu": 100.0,
        "segments": [segment],
    }
    if geometry_contract is not None:
        manifest[GANTRY_GEOMETRY_CONTRACT_FIELD] = geometry_contract
    write_file(
        workspace / "segments" / "segment_manifest.json",
        json.dumps(manifest),
    )
    output = write_file(
        workspace / segment["expected_output_path"],
        "synthetic PHITS tally",
    )
    phits_out = write_file(
        output.parent / "phits.out",
        "Number of lost particles = 0\n"
        "Number of geometry recovering = 0\n"
        "Number of unrecovered errors = 0\n",
    )
    recorded_root = old_root or str(workspace.resolve())
    recorded_output = (
        str(output.resolve())
        if old_root is None
        else old_root.rstrip("\\/")
        + "\\segments\\seg_001\\deposit-target-3D.out"
    )
    recorded_phits_out = (
        str(phits_out.resolve())
        if old_root is None
        else old_root.rstrip("\\/") + "\\segments\\seg_001\\phits.out"
    )
    write_file(
        workspace / "analysis" / "segment_execution_summary.json",
        json.dumps(
            {
                "schema_version": "dicomxphits_public_segment_execution_v2",
                "stage_status": "success",
                "workspace_root": recorded_root,
                "manifest_sha256": manifest_sha256(manifest),
                "segments": [
                    {
                        "segment_id": "seg_001",
                        "status": "success",
                        "expected_output_path": recorded_output,
                        "expected_output_sha256": file_sha256(output),
                        "phits_out_path": recorded_phits_out,
                        "phits_out_sha256": file_sha256(phits_out),
                        "geometry_diagnostics": {
                            "schema_version": GEOMETRY_DIAGNOSTICS_SCHEMA_VERSION,
                            "status": "clean",
                            "counts": {
                                "lost_particles": 0,
                                "geometry_recovering": 0,
                                "unrecovered_errors": 0,
                            },
                        },
                    }
                ],
            }
        ),
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


def test_old_nonzero_gantry_transport_is_not_reusable(tmp_path: Path) -> None:
    workspace = write_recoverable_workspace(
        tmp_path,
        gantry_angle_deg=90.0,
        geometry_contract=None,
    )

    inspection = inspect_existing_workspace(workspace)

    assert inspection.state == RECOVERY_INVALID
    assert inspection.phits_reusable is False
    assert "rerun PHITS" in inspection.message


def test_legacy_zero_angle_transport_is_not_reusable_under_v5(tmp_path: Path) -> None:
    workspace = write_recoverable_workspace(
        tmp_path,
        gantry_angle_deg=0.0,
        geometry_contract=None,
    )

    inspection = inspect_existing_workspace(workspace)

    assert inspection.state == RECOVERY_INVALID
    assert inspection.phits_reusable is False
    assert "rerun PHITS" in inspection.message


def test_v4_nonzero_collimator_transport_is_not_reusable(tmp_path: Path) -> None:
    workspace = write_recoverable_workspace(
        tmp_path,
        gantry_angle_deg=0.0,
        collimator_angle_deg=30.0,
        geometry_contract=PREVIOUS_GANTRY_GEOMETRY_CONTRACT,
    )

    inspection = inspect_existing_workspace(workspace)

    assert inspection.state == RECOVERY_INVALID
    assert inspection.phits_reusable is False
    assert "rerun PHITS" in inspection.message


def test_v4_zero_collimator_transport_is_not_reusable(
    tmp_path: Path,
) -> None:
    workspace = write_recoverable_workspace(
        tmp_path,
        gantry_angle_deg=0.0,
        geometry_contract=PREVIOUS_GANTRY_GEOMETRY_CONTRACT,
        resolved_mlc_positions_mm={
            "bank_a": [-40.0, -15.0],
            "bank_b": [40.0, 15.0],
        },
    )

    inspection = inspect_existing_workspace(workspace)

    assert inspection.state == RECOVERY_INVALID
    assert inspection.phits_reusable is False
    assert "rerun PHITS" in inspection.message


@pytest.mark.parametrize(
    "resolved_mlc_positions_mm",
    [
        None,
        {
            "bank_a": [-40.0, -15.0],
            "bank_b": [40.0, 15.0],
        },
    ],
)
def test_v4_contract_rejects_nonzero_gantry_transport(
    tmp_path: Path,
    resolved_mlc_positions_mm: dict[str, list[float]] | None,
) -> None:
    workspace = write_recoverable_workspace(
        tmp_path,
        gantry_angle_deg=90.0,
        geometry_contract=PREVIOUS_GANTRY_GEOMETRY_CONTRACT,
        resolved_mlc_positions_mm=resolved_mlc_positions_mm,
    )

    inspection = inspect_existing_workspace(workspace)

    assert inspection.state == RECOVERY_INVALID
    assert inspection.phits_reusable is False
    assert "rerun PHITS" in inspection.message


@pytest.mark.parametrize(
    "diagnostics",
    [
        None,
        {
            "schema_version": GEOMETRY_DIAGNOSTICS_SCHEMA_VERSION,
            "status": "error",
            "counts": {
                "lost_particles": 0,
                "geometry_recovering": 1,
                "unrecovered_errors": 0,
            },
        },
    ],
)
def test_missing_or_nonclean_geometry_diagnostics_block_phits_reuse(
    tmp_path: Path,
    diagnostics: dict[str, object] | None,
) -> None:
    workspace = write_recoverable_workspace(tmp_path)
    summary_path = workspace / "analysis" / "segment_execution_summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    summary["segments"][0]["geometry_diagnostics"] = diagnostics
    summary_path.write_text(json.dumps(summary), encoding="utf-8")

    inspection = inspect_existing_workspace(workspace)

    assert inspection.state == RECOVERY_INVALID
    assert inspection.phits_reusable is False
    assert "diagnostic evidence" in inspection.message


def test_legacy_zero_gantry_rejects_asymmetric_mlcx_transport(tmp_path: Path) -> None:
    workspace = write_recoverable_workspace(
        tmp_path,
        gantry_angle_deg=0.0,
        geometry_contract=None,
        resolved_mlc_positions_mm={
            "bank_a": [-40.0, -15.0],
            "bank_b": [10.0, 25.0],
        },
    )

    inspection = inspect_existing_workspace(workspace)

    assert inspection.state == RECOVERY_INVALID
    assert inspection.phits_reusable is False
    assert "rerun PHITS" in inspection.message


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
    assert rebind_workspace_path(
        "/data/Case/segments/output.out",
        recorded_workspace_root="/data/Case",
        current_workspace_root=workspace,
    ) == (workspace / "segments" / "output.out").resolve()
    with pytest.raises(WorkspaceRecoveryError, match="outside"):
        rebind_workspace_path(
            "/data/case/segments/output.out",
            recorded_workspace_root="/data/Case",
            current_workspace_root=workspace,
        )


def test_relocated_sumtally_summaries_remain_verified_without_rerun(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    old_root = r"D:\old-machine\case-3dcrt"
    workspace = write_recoverable_workspace(tmp_path, old_root=old_root)
    manifest = json.loads(
        (workspace / "segments" / "segment_manifest.json").read_text(
            encoding="utf-8"
        )
    )
    segment = workspace / "segments" / "seg_001" / "deposit-target-3D.out"
    sumtally_input = write_file(workspace / "sumtally" / "sumtally.inp")
    sumtally_output = write_file(workspace / "sumtally" / "dose.out")
    recorded_segment = old_root + r"\segments\seg_001\deposit-target-3D.out"
    generation = {
        "stage_status": "success",
        "workspace_root": old_root,
        "manifest_sha256": manifest_sha256(manifest),
        "segment_output_evidence": [
            {"path": recorded_segment, "sha256": file_sha256(segment)}
        ],
        "outputs": {
            "sumtally_input": old_root + r"\sumtally\sumtally.inp",
            "sumtally_output": old_root + r"\sumtally\dose.out",
        },
    }
    execution = {
        **generation,
        "expected_sumtally_output": old_root + r"\sumtally\dose.out",
    }
    write_file(
        workspace / "analysis" / "sumtally_generation_summary.json",
        json.dumps(generation),
    )
    write_file(
        workspace / "analysis" / "sumtally_execution_summary.json",
        json.dumps(execution),
    )
    binding = {"synthetic": "current"}

    def validate_relocated_summaries(*, workspace_root, generation, execution):
        assert generation["workspace_root"] == str(workspace.resolve())
        assert execution["workspace_root"] == str(workspace.resolve())
        assert Path(generation["outputs"]["sumtally_input"]) == sumtally_input.resolve()
        assert Path(generation["outputs"]["sumtally_output"]) == sumtally_output.resolve()
        assert Path(execution["expected_sumtally_output"]) == sumtally_output.resolve()
        assert Path(generation["segment_output_evidence"][0]["path"]) == (
            segment.resolve()
        )
        return binding

    monkeypatch.setattr(
        prepare_rtdose_module,
        "validate_sumtally_manifest_binding",
        validate_relocated_summaries,
    )

    inspection = inspect_existing_workspace(workspace)

    assert inspection.state == RECOVERY_READY
    assert inspection.highest_verified_stage == "Sumtally completed"
    assert inspection.stage_sequence == ("prepare_rtdose", "run_rtdose")


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


def test_changed_phits_geometry_summary_blocks_phits_reuse(tmp_path: Path) -> None:
    workspace = write_recoverable_workspace(tmp_path)
    write_file(
        workspace / "segments" / "seg_001" / "phits.out",
        "Number of lost particles = 0\n"
        "Number of geometry recovering = 1\n"
        "Number of unrecovered errors = 0\n",
    )

    inspection = inspect_existing_workspace(workspace)

    assert inspection.state == RECOVERY_INVALID
    assert inspection.phits_reusable is False
    assert "SHA-256" in inspection.message


def test_geometry_diagnostics_must_bind_current_manifest(tmp_path: Path) -> None:
    workspace = write_recoverable_workspace(tmp_path)
    summary_path = workspace / "analysis" / "segment_execution_summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    summary["manifest_sha256"] = "0" * 64
    summary_path.write_text(json.dumps(summary), encoding="utf-8")

    inspection = inspect_existing_workspace(workspace)

    assert inspection.state == RECOVERY_INVALID
    assert inspection.phits_reusable is False
    assert "current manifest" in inspection.message


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
    assert not (workspace / "sumtally" / "sumtally.inp").exists()
    assert not (workspace / "rtdose" / "historical.dcm").exists()
    if sys.platform == "win32":
        # The output guard intentionally keeps validated directory handles open
        # on Windows, so only their preserved files can be removed safely.
        assert (workspace / "sumtally").is_dir()
        assert (workspace / "rtdose").is_dir()
    else:
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
    monkeypatch.setattr(
        gui_module,
        "inspect_existing_workspace",
        lambda _workspace: inspection,
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


def test_gui_recovery_reinspects_before_preserving_or_running(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = write_recoverable_workspace(tmp_path)
    inspection = inspect_existing_workspace(workspace)
    assert inspection.stage_sequence == FULL_DOWNSTREAM_SEQUENCE
    write_file(
        workspace / "segments" / "seg_001" / "deposit-target-3D.out",
        "changed after inspection",
    )
    preserved: list[tuple[str, ...]] = []
    stages: list[str] = []
    monkeypatch.setattr(
        gui_module,
        "preserve_downstream_for_recovery",
        lambda *_args, **_kwargs: preserved.append(("called",)),
    )

    def fake_stage_runner(_config: GuiConfig, stage_key: str) -> StageResult:
        stages.append(stage_key)
        raise AssertionError("stage runner must not start after workspace mutation")

    config = GuiConfig("", str(workspace), "", "", "", "", "", "")
    with pytest.raises(WorkspaceRecoveryError, match="changed after inspection"):
        run_workspace_recovery(config, inspection, stage_runner=fake_stage_runner)

    assert preserved == []
    assert stages == []


def test_gui_recovery_rejects_a_changed_workspace_selection(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    inspected_workspace = tmp_path / "inspected"
    configured_workspace = tmp_path / "configured-later"
    inspected_workspace.mkdir()
    configured_workspace.mkdir()
    inspection = WorkspaceRecoveryInspection(
        inspected_workspace,
        RECOVERY_READY,
        "PHITS completed",
        "generate_sumtally",
        FULL_DOWNSTREAM_SEQUENCE,
        "ready",
        True,
    )
    preserved: list[str] = []
    monkeypatch.setattr(
        gui_module,
        "preserve_downstream_for_recovery",
        lambda *_args, **_kwargs: preserved.append("called"),
    )
    config = GuiConfig("", str(configured_workspace), "", "", "", "", "", "")

    with pytest.raises(WorkspaceRecoveryError, match="selection changed"):
        run_workspace_recovery(config, inspection)

    assert preserved == []


def test_completed_recovery_requires_current_coordinate_and_semantic_proof(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = write_recoverable_workspace(tmp_path)
    binding = {"synthetic": "current"}
    rtplan_path = write_file(workspace / "RTPLAN.dcm", "1")
    ct_reference_path = write_file(workspace / "rtdose" / "ct_reference.dcm")
    plan_evidence = synthetic_full_plan_evidence(
        rtplan_path,
        workspace_root=workspace,
    )
    old_root = r"D:\old-machine\case-3dcrt"
    recorded_plan_evidence = {
        **plan_evidence,
        "rtplan_path": old_root + r"\RTPLAN.dcm",
        "manifest_path": old_root + r"\segments\segment_manifest.json",
    }
    course_dose_evidence = synthetic_course_dose_evidence(
        rtplan_sha256=str(plan_evidence["rtplan_sha256"]),
    )
    prepare_path = write_file(
        workspace / "analysis" / "rtdose_conversion_prepare_summary.json",
        json.dumps(
            {
                "stage_status": "success",
                "rtdose_placement": {"schema_version": "synthetic"},
                "sumtally_manifest_binding": binding,
                "course_dose_contract_version": "dicomxphits_plan_course_dose_v1",
                "course_dose_evidence": course_dose_evidence,
                "full_plan_evidence": recorded_plan_evidence,
                "workspace_root": old_root,
                "ct_reference_workspace_copy_path": old_root
                + r"\rtdose\ct_reference.dcm",
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
        "course_dose_contract_version": "dicomxphits_plan_course_dose_v1",
        "course_dose_evidence": course_dose_evidence,
        "coordinate_correction": {
            "schema_version": SCHEMA_VERSION,
            "axis_mapping": AXIS_MAPPING,
            "invariants": {
                "stored_value_multiset_preserved": True,
                "iec_x_to_dicom_x_reversal_applied": True,
            },
        },
        "final_semantic_validation": {
            "course_dose_contract_version": "dicomxphits_plan_course_dose_v1",
            "validated": True,
        },
    }
    write_file(execution_path, json.dumps(execution))
    monkeypatch.setattr(
        recovery_module,
        "_current_sumtally_binding",
        lambda _workspace: binding,
    )
    monkeypatch.setattr(
        recovery_module,
        "validate_full_plan_context",
        lambda **kwargs: synthetic_full_plan_evidence(
            Path(kwargs["rtplan_path"]),
            workspace_root=Path(kwargs["workspace_root"]),
        ),
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

    execution["final_semantic_validation"] = {
        "course_dose_contract_version": "dicomxphits_plan_course_dose_v1",
        "validated": True,
    }
    execution.pop("course_dose_evidence")
    write_file(execution_path, json.dumps(execution))

    stale_course_dose = inspect_existing_workspace(workspace)
    assert stale_course_dose.state == RECOVERY_READY
    assert stale_course_dose.stage_sequence == ("run_rtdose",)

    execution["course_dose_evidence"] = course_dose_evidence
    write_file(execution_path, json.dumps(execution))
    final_output.unlink()

    missing_output = inspect_existing_workspace(workspace)
    assert missing_output.state == RECOVERY_READY
    assert missing_output.stage_sequence == ("run_rtdose",)


def test_completed_recovery_rejects_a_changed_frozen_fraction_plan(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = write_recoverable_workspace(tmp_path)
    binding = {"synthetic": "current"}
    rtplan_path = write_file(workspace / "RTPLAN.dcm", "1")
    ct_reference_path = write_file(workspace / "rtdose" / "ct_reference.dcm")
    plan_evidence = synthetic_full_plan_evidence(rtplan_path)
    course_dose_evidence = synthetic_course_dose_evidence(
        rtplan_sha256=str(plan_evidence["rtplan_sha256"]),
    )
    prepare_path = write_file(
        workspace / "analysis" / "rtdose_conversion_prepare_summary.json",
        json.dumps(
            {
                "stage_status": "success",
                "workspace_root": str(workspace.resolve()),
                "ct_reference_workspace_copy_path": str(ct_reference_path.resolve()),
                "rtdose_placement": {"schema_version": "synthetic"},
                "sumtally_manifest_binding": binding,
                "course_dose_contract_version": "dicomxphits_plan_course_dose_v1",
                "course_dose_evidence": course_dose_evidence,
                "full_plan_evidence": plan_evidence,
            }
        ),
    )
    final_output = write_file(workspace / "sumtally" / "dose.fixed.dcm", "dose")
    execution = {
        "stage_status": "success",
        "workspace_root": str(workspace.resolve()),
        "rtdose_prepare_summary_sha256": file_sha256(prepare_path),
        "coordinate_corrected_rtdose_output": str(final_output.resolve()),
        "coordinate_corrected_rtdose_output_relative": "sumtally/dose.fixed.dcm",
        "coordinate_corrected_rtdose_output_exists": True,
        "coordinate_corrected_rtdose_output_sha256": file_sha256(final_output),
        "coordinate_placement_validation": {"validated": True},
        "course_dose_contract_version": "dicomxphits_plan_course_dose_v1",
        "course_dose_evidence": course_dose_evidence,
        "coordinate_correction": {
            "schema_version": SCHEMA_VERSION,
            "axis_mapping": AXIS_MAPPING,
            "invariants": {
                "stored_value_multiset_preserved": True,
                "iec_x_to_dicom_x_reversal_applied": True,
            },
        },
        "final_semantic_validation": {
            "course_dose_contract_version": "dicomxphits_plan_course_dose_v1",
            "validated": True,
        },
    }
    write_file(
        workspace / "analysis" / "rtdose_conversion_execution_summary.json",
        json.dumps(execution),
    )
    monkeypatch.setattr(
        recovery_module,
        "_current_sumtally_binding",
        lambda _workspace: binding,
    )
    monkeypatch.setattr(
        recovery_module,
        "validate_full_plan_context",
        lambda **kwargs: synthetic_full_plan_evidence(Path(kwargs["rtplan_path"])),
    )

    assert inspect_existing_workspace(workspace).state == RECOVERY_COMPLETE
    assert rtdose_plan_evidence_is_current(workspace, execution) is True

    write_file(rtplan_path, "2")

    assert rtdose_plan_evidence_is_current(workspace, execution) is False
    stale = inspect_existing_workspace(workspace)
    assert stale.state == RECOVERY_READY
    assert stale.stage_sequence == ("prepare_rtdose", "run_rtdose")
