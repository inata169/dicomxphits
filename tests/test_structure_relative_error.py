from __future__ import annotations

import json
from pathlib import Path
import subprocess
from types import SimpleNamespace

import numpy as np
import pytest

import dicomxphits.gui as gui_module
import dicomxphits.structure_relative_error as module
import dicomxphits.workspace_execution as workspace_execution_module
from dicomxphits.gui import (
    GuiValidationError,
    STRUCTURE_EVALUATION_UPSTREAM_STAGES,
    StructureEvaluationRequestGuard,
    structure_evaluation_enabled,
    structure_roi_number,
)
from dicomxphits.phits_observation_format import Mesh
from dicomxphits.prepare_sumtally import run_phits_sumtally
from dicomxphits.structure_relative_error import (
    CONTRACT_VERSION,
    NON_CLINICAL_LABEL,
    PAIR_SEMANTICS,
    StructureRelativeErrorUnavailable,
    _statistics_percent,
    _structure_membership_on_dose_grid,
    _values_in_rtdose_order,
    evaluate_structure_relative_error,
    format_structure_relative_error,
    revalidate_structure_relative_error_result,
    validate_combined_tally_pair,
)
from dicomxphits.workspace_recovery import normalize_relocated_sumtally_summaries


MESH = Mesh(
    "Authored completed fixture",
    "dose.out",
    (2, 1, 2),
    ((-0.1, 0.1), (-0.05, 0.05), (-0.1, 0.1)),
)
GEOMETRY = {
    "axes": {
        "x": {"minimum_cm": -0.1, "maximum_cm": 0.1, "bin_count": 2},
        "y": {"minimum_cm": -0.05, "maximum_cm": 0.05, "bin_count": 1},
        "z": {"minimum_cm": -0.1, "maximum_cm": 0.1, "bin_count": 2},
    }
}


def _header(*, output: bool) -> str:
    rows = ["title = Authored completed fixture", "mesh = xyz"]
    for axis, bounds, count in zip("xyz", MESH.bounds, MESH.counts, strict=True):
        rows.extend(
            (
                f"{axis}-type = 2",
                f"{axis}min = {bounds[0]:.6f}",
                f"{axis}max = {bounds[1]:.6f}",
                f"n{axis} = {count}",
            )
        )
    rows.extend(
        (
            "unit = 0",
            "material = all",
            "output = dose",
            "axis = xy",
            "file = dose.out",
            "part = all",
            "epsout = 1",
        )
    )
    if output:
        rows.extend(
            ("letmat = 0", "dedxfnc = 0", "deposit = 0", "2D-type = 3", "mother = all")
        )
    return "\n".join(rows) + "\n"


def _deck() -> str:
    return (
        "$OMP = 2\n[ Parameters ]\n maxcas = 10\n maxbch = 10\n"
        "[ T-Deposit ]\n"
        + _header(output=False)
    )


def _tally(role: str, values: list[float]) -> bytes:
    nx, ny, nz = MESH.counts
    rows = ["[ T-Deposit ]", _header(output=True), "#newpage:"]
    for index in range(1, nz + 1):
        if index > 1:
            rows.append(" newpage:")
        zlo, zhi = MESH.bounds[2]
        dz = (zhi - zlo) / nz
        page_values = values[(index - 1) * nx * ny : index * nx * ny]
        rows.extend(
            (
                f"#   no. = {index:2d}   iz  = {index:2d}   part. = all",
                f"#   z = ( {zlo + (index - 1) * dz:.4E} - {zlo + index * dz:.4E} )",
                f"'no. = {index:2d},  iz = {index:2d}'",
                "msuc: {Authored completed fixture}",
                r"msdl: {\it calculated by \PHITS  3.35}",
                f"#  ny = {ny:3d}   nx = {nx:3d}",
                "# ( ( data(x,y), x = 1, nx ), y = ny, 1, -1 )",
                "",
                "hc:  y = 0.0000000 to 0.0000000 by 0.1000000 ; x = -0.05000000 to 0.05000000 by 0.1000000 ;",
                " ".join(str(value) for value in page_values),
                "",
                "#" + "-" * 78,
                "hc: y= 0.005 to 0.995 by 0.01 ; x= 0.5 to 0.5 by 1 ;",
                " ".join(str(value) for value in range(1, 101)),
                "z: xorg(0.0)",
                "y: " + ("Dose [Gy/source]" if role == "dose" else "Relative Error"),
                "e:",
                "z: xorg[-1.03/0.05]",
                "p: ymin(-1) ymax(1)",
                "",
            )
        )
    rows.extend(
        (
            "# Information for Restart Calculation",
            "# This calculation was newly started",
            "# istdev = 2 # 1:Batch variance, 2:History variance",
            "# resc2 = 1.00000000000000000E+01 # Total source weight or Total source weight / maxcas",
            "# resc3 = 1.00000000000000000E+01 # Total history number or Total batch number",
            "# maxcas = 10 # History / Batch, only used for istdev=1",
            f"# bitrseed = {'0' * 64} # bit data of rseed",
        )
    )
    return ("\n".join(rows) + "\n").encode("ascii")


def _fake_series() -> SimpleNamespace:
    first_slice = SimpleNamespace(
        position=np.asarray([0.0, 0.0, 0.0]),
        distance_mm=0.0,
    )
    return SimpleNamespace(
        slices=(first_slice,),
        rows=2,
        columns=2,
        row_spacing_mm=1.0,
        column_spacing_mm=1.0,
        slice_spacing_mm=1.0,
        row_direction=np.asarray([1.0, 0.0, 0.0]),
        column_direction=np.asarray([0.0, 1.0, 0.0]),
        normal_direction=np.asarray([0.0, 0.0, 1.0]),
    )


def test_validate_and_promote_combined_sumtally_error_pair(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    sumtally = workspace / "sumtally"
    sumtally.mkdir(parents=True)
    sum_input = sumtally / "sum.inp"
    sum_input.write_text(_deck(), encoding="utf-8")
    dose_output = sumtally / "dose.out"
    error_output = sumtally / "dose_err.out"

    def fake_runner(command, **kwargs):
        execution_root = Path(kwargs["cwd"])
        (execution_root / "dose.out").write_bytes(
            _tally("dose", [10.0, 8.0, 6.0, 4.0])
        )
        (execution_root / "dose_err.out").write_bytes(
            _tally("error", [0.1, 0.0, 0.3, 0.2])
        )
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    result, geometry, geometry_error, pair, pair_error = run_phits_sumtally(
        phits_executable_path="synthetic-phits",
        sum_input=sum_input,
        stdout_path=sumtally / "stdout.txt",
        stderr_path=sumtally / "stderr.txt",
        workspace_root=workspace,
        expected_output=dose_output,
        expected_error_output=error_output,
        expected_geometry=GEOMETRY,
        environment={},
        runner=fake_runner,
    )

    assert result.returncode == 0
    assert geometry_error is None and geometry["matches_segment_tallies"] is True
    assert pair_error is None
    assert pair["semantics"] == PAIR_SEMANTICS
    assert pair["dose_path"] == str(dose_output.resolve())
    assert pair["error_path"] == str(error_output.resolve())
    assert error_output.is_file()
    assert validate_combined_tally_pair(
        dose_path=dose_output,
        error_path=error_output,
        sum_input_path=sum_input,
        expected_geometry=GEOMETRY,
    ) == pair


def test_missing_combined_error_keeps_dose_but_is_unavailable(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    sumtally = workspace / "sumtally"
    sumtally.mkdir(parents=True)
    sum_input = sumtally / "sum.inp"
    sum_input.write_text(_deck(), encoding="utf-8")
    dose_output = sumtally / "dose.out"

    def fake_runner(command, **kwargs):
        Path(kwargs["cwd"], "dose.out").write_bytes(
            _tally("dose", [10.0, 8.0, 6.0, 4.0])
        )
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    result = run_phits_sumtally(
        phits_executable_path="synthetic-phits",
        sum_input=sum_input,
        stdout_path=sumtally / "stdout.txt",
        stderr_path=sumtally / "stderr.txt",
        workspace_root=workspace,
        expected_output=dose_output,
        expected_error_output=sumtally / "dose_err.out",
        expected_geometry=GEOMETRY,
        environment={},
        runner=fake_runner,
    )

    assert result[0].returncode == 0 and dose_output.is_file()
    assert result[3] is None
    assert "unavailable" in result[4]


def test_axis_mapping_and_approved_statistics_are_exact() -> None:
    reordered = _values_in_rtdose_order(np.asarray([1.0, 2.0, 3.0, 4.0]), MESH)
    assert reordered.tolist() == [[[2.0, 1.0], [4.0, 3.0]]]
    assert _statistics_percent(np.asarray([0.1, 0.2])) == {
        "mean": pytest.approx(15.0),
        "median": pytest.approx(15.0),
        "p95": pytest.approx(19.5),
    }


def test_mapping_uses_unique_ct_voxel_cells_and_rejects_boundaries() -> None:
    placement = {
        "output_shape_frames_rows_columns": [1, 2, 2],
        "image_position_patient_mm": [0.0, 0.0, 0.0],
        "image_orientation_patient": [1.0, 0.0, 0.0, 0.0, 1.0, 0.0],
        "pixel_spacing_mm": [1.0, 1.0],
        "grid_frame_offset_vector_mm": [0.0],
    }
    mask = np.asarray([[[True, False], [False, True]]])
    mapped = _structure_membership_on_dose_grid(
        placement=placement,
        series=_fake_series(),
        ct_mask=mask,
    )
    assert mapped.tolist() == mask.tolist()

    boundary = dict(placement)
    boundary["image_position_patient_mm"] = [0.5, 0.0, 0.0]
    with pytest.raises(StructureRelativeErrorUnavailable, match="boundary"):
        _structure_membership_on_dose_grid(
            placement=boundary,
            series=_fake_series(),
            ct_mask=mask,
        )


def test_evaluation_filters_counts_persists_scalars_and_fails_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    rtstruct_path = tmp_path / "RTSTRUCT.dcm"
    rtstruct_path.write_bytes(b"synthetic RT Structure Set placeholder")
    binding = {
        "manifest_sha256": "1" * 64,
        "tally_geometry_binding": {"mesh_geometry": GEOMETRY},
    }
    pair = {
        "dose_sha256": "2" * 64,
        "error_sha256": "3" * 64,
        "semantics": PAIR_SEMANTICS,
    }
    monkeypatch.setattr(
        module,
        "_current_combined_source",
        lambda _root: (
            np.asarray([10.0, 8.0, 6.0, 4.0]),
            np.asarray([0.1, 0.0, 0.3, 0.2]),
            MESH,
            binding,
            pair,
        ),
    )
    monkeypatch.setattr(
        module,
        "_frozen_ct_series",
        lambda _path, **_kwargs: (
            _fake_series(),
            {
                "ct_series_evidence_sha256": "4" * 64,
                "ct2phits_manifest_sha256": "5" * 64,
                "ct2phits_execution_summary_sha256": "6" * 64,
                "workspace_preparation_sha256": "9" * 64,
                "ct_reference_sha256": "7" * 64,
            },
        ),
    )
    monkeypatch.setattr(
        module,
        "validate_full_plan_context",
        lambda **_kwargs: {"rtplan_isocenter_dicom_mm": [0.5, 0.5, 0.0]},
    )
    monkeypatch.setattr(
        module,
        "load_rtstruct_roi_mask_by_number",
        lambda *_args, **_kwargs: (
            np.ones((1, 2, 2), dtype=bool),
            "Synthetic PTV",
            module.file_sha256(rtstruct_path),
        ),
    )
    request = {
        "workspace_root": workspace,
        "rtstruct_path": rtstruct_path,
        "roi_number": 7,
        "rtplan_path": tmp_path / "RTPLAN.dcm",
        "ct_reference_path": tmp_path / "CT.dcm",
    }

    result = evaluate_structure_relative_error(**request)

    assert result["contract_version"] == CONTRACT_VERSION
    assert result["population"] == {
        "mapped_structure_voxel_count": 4,
        "above_threshold_voxel_count": 3,
        "eligible_voxel_count": 2,
        "zero_relative_error_exclusion_count": 1,
    }
    assert result["statistics_percent"] == {
        "mean": pytest.approx(20.0),
        "median": pytest.approx(20.0),
        "p95": pytest.approx(29.0),
    }
    assert NON_CLINICAL_LABEL in format_structure_relative_error(result)
    persisted_path = Path(result["result_path"])
    persisted = json.loads(persisted_path.read_text(encoding="utf-8"))
    assert persisted["evaluation_sha256"] == persisted_path.stem
    assert "display_roi_name" not in persisted
    serialized = persisted_path.read_text(encoding="utf-8")
    assert "Synthetic PTV" not in serialized
    assert "Patient" not in serialized
    assert "dmax_value" not in serialized.lower()

    repeated = evaluate_structure_relative_error(**request)
    assert repeated["evaluation_sha256"] == result["evaluation_sha256"]
    monkeypatch.setattr(
        module,
        "load_rtstruct_roi_mask_by_number",
        lambda *_args, **_kwargs: pytest.fail(
            "retained-result validation must not reevaluate Structure membership"
        ),
    )
    monkeypatch.setattr(
        workspace_execution_module,
        "WorkspaceExecutionLease",
        lambda *_args, **_kwargs: pytest.fail(
            "retained-result validation must not compete for the execution lease"
        ),
    )
    revalidated = revalidate_structure_relative_error_result(
        **request,
        expected_result=result,
    )
    assert revalidated["evaluation_sha256"] == result["evaluation_sha256"]

    pair["dose_sha256"] = "a" * 64
    with pytest.raises(StructureRelativeErrorUnavailable, match="identity.*stale"):
        revalidate_structure_relative_error_result(
            **request,
            expected_result=result,
        )
    assert list(persisted_path.parent.glob("*.json")) == [persisted_path]
    pair["dose_sha256"] = "2" * 64

    rtstruct_path.write_bytes(b"changed synthetic RT Structure Set placeholder")
    with pytest.raises(StructureRelativeErrorUnavailable, match="identity.*stale"):
        revalidate_structure_relative_error_result(
            **request,
            expected_result=result,
        )
    rtstruct_path.write_bytes(b"synthetic RT Structure Set placeholder")

    persisted_path.write_text("{}\n", encoding="utf-8")
    with pytest.raises(StructureRelativeErrorUnavailable, match="stale|mismatched"):
        revalidate_structure_relative_error_result(
            **request,
            expected_result=result,
        )
    assert persisted_path.read_text(encoding="utf-8") == "{}\n"


def test_gui_action_requires_verified_sumtally_and_explicit_inputs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = tmp_path / "workspace"
    analysis = workspace / "analysis"
    analysis.mkdir(parents=True)
    common = {
        "workspace_root": str(workspace),
        "rtstruct_path": "RTSTRUCT.dcm",
        "roi_number": "7",
        "rtplan_path": "RTPLAN.dcm",
        "ct_reference_path": "CT.dcm",
        "busy": False,
    }
    monkeypatch.setattr(gui_module, "_current_sumtally_binding", lambda _root: None)
    assert structure_evaluation_enabled(**common) is False
    monkeypatch.setattr(
        gui_module,
        "_current_sumtally_binding",
        lambda _root: {"verified": True},
    )
    assert structure_evaluation_enabled(**common) is True
    assert structure_evaluation_enabled(**{**common, "roi_number": "PTV"}) is False
    assert structure_evaluation_enabled(**{**common, "busy": True}) is False
    assert structure_roi_number(" 7 ") == 7
    with pytest.raises(GuiValidationError):
        structure_roi_number("PTV")


def test_gui_result_ticket_rejects_changed_or_changed_back_inputs() -> None:
    guard = StructureEvaluationRequestGuard()
    original = ("workspace", "RTSTRUCT.dcm", "7", "RTPLAN.dcm", "CT.dcm")
    ticket = guard.begin(original)

    assert guard.is_current(ticket, original) is True
    assert guard.is_current(ticket, (*original[:2], "8", *original[3:])) is False

    guard.invalidate()

    assert guard.is_current(ticket, original) is False


def test_gui_invalidates_structure_results_for_every_upstream_stage() -> None:
    assert STRUCTURE_EVALUATION_UPSTREAM_STAGES == {
        "run_ct2phits",
        "prepare_workspace",
        "run_segments",
        "generate_sumtally",
        "run_sumtally",
    }
    assert "prepare_rtdose" not in STRUCTURE_EVALUATION_UPSTREAM_STAGES
    assert "run_rtdose" not in STRUCTURE_EVALUATION_UPSTREAM_STAGES
    assert "evaluate_structure_rerr" not in STRUCTURE_EVALUATION_UPSTREAM_STAGES


def test_relocation_rebinds_only_combined_pair_paths(tmp_path: Path) -> None:
    old = tmp_path / "old-workspace"
    current = tmp_path / "current-workspace"
    execution = {
        "workspace_root": str(old),
        "combined_relative_error_evidence": {
            "dose_path": str(old / "sumtally" / "dose.out"),
            "error_path": str(old / "sumtally" / "dose_err.out"),
            "dose_sha256": "1" * 64,
            "error_sha256": "2" * 64,
        },
    }

    _generation, normalized = normalize_relocated_sumtally_summaries(
        current,
        generation={"workspace_root": str(old)},
        execution=execution,
    )

    evidence = normalized["combined_relative_error_evidence"]
    assert evidence["dose_path"] == str(current / "sumtally" / "dose.out")
    assert evidence["error_path"] == str(current / "sumtally" / "dose_err.out")
    assert evidence["dose_sha256"] == "1" * 64
