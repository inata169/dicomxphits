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


def test_retained_large_sources_use_metadata_without_rehashing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "large-tally.out"
    source.write_bytes(b"validated tally content")
    snapshot = module._retained_file_snapshot(
        source,
        label="combined Sumtally dose output",
        expected_sha256=module.file_sha256(source),
        poll_sha256=False,
    )
    monkeypatch.setattr(
        module,
        "file_sha256",
        lambda *_args, **_kwargs: pytest.fail(
            "retained large sources must not be rehashed"
        ),
    )

    module._verify_retained_file_snapshot(snapshot)

    source.write_bytes(b"changed tally content!!")
    with pytest.raises(StructureRelativeErrorUnavailable, match="source changed"):
        module._verify_retained_file_snapshot(snapshot)


def test_retained_validation_tracks_all_proven_source_groups(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    analysis = workspace / "analysis"
    segments = workspace / "segments"
    sumtally = workspace / "sumtally"
    for directory in (analysis, segments, sumtally):
        directory.mkdir(parents=True, exist_ok=True)

    def write(path: Path, content: bytes) -> str:
        path.write_bytes(content)
        return module.file_sha256(path)

    segment_manifest = segments / "segment_manifest.json"
    write(segment_manifest, b"{}\n")
    segment_output = segments / "segment.out"
    segment_sha256 = write(segment_output, b"segment tally")
    sum_input = sumtally / "segment_sum.inp"
    sum_input_sha256 = write(sum_input, b"sum wrapper")
    sumtally_input = sumtally / "sumtally.inp"
    sumtally_input_sha256 = write(sumtally_input, b"sum input")
    dose = sumtally / "dose.out"
    dose_sha256 = write(dose, b"combined dose")
    error = sumtally / "dose_err.out"
    error_sha256 = write(error, b"combined error")

    generation = {
        "stage_status": "success",
        "workspace_root": str(workspace),
        "outputs": {"sum_input": str(sum_input)},
    }
    execution = {
        "stage_status": "success",
        "workspace_root": str(workspace),
    }
    (analysis / "sumtally_generation_summary.json").write_text(
        json.dumps(generation), encoding="utf-8"
    )
    (analysis / "sumtally_execution_summary.json").write_text(
        json.dumps(execution), encoding="utf-8"
    )
    (analysis / "segment_preflight.json").write_text("{}\n", encoding="utf-8")

    snapshot_root = tmp_path / "ct2phits"
    ct_root = snapshot_root / "CT"
    datfiles = snapshot_root / "DATfiles"
    ct_root.mkdir(parents=True)
    datfiles.mkdir()
    reference = ct_root / "reference.dcm"
    reference_sha256 = write(reference, b"frozen CT")
    rtplan = snapshot_root / "RTPLAN.dcm"
    rtplan_sha256 = write(rtplan, b"frozen RT Plan")
    raw_hashes = {
        name: write(datfiles / name, f"{name}\n".encode("ascii"))
        for name in module.RAW_CT2PHITS_NAMES
    }
    ct_manifest_path = snapshot_root / "ct2phits_workspace_manifest.json"
    ct_manifest_path.write_text(
        json.dumps(
            {
                "ct_series": {
                    "copied_files": ["CT/reference.dcm"],
                    "sha256": {"CT/reference.dcm": reference_sha256},
                },
                "rtplan": {"sha256": rtplan_sha256},
            }
        ),
        encoding="utf-8",
    )
    ct_summary_path = snapshot_root / "ct2phits_execution_summary.json"
    ct_summary_path.write_text(
        json.dumps({"raw_datfiles_sha256": raw_hashes}),
        encoding="utf-8",
    )
    preparation_path = analysis / "public_preparation_workspace_summary.json"
    preparation_path.write_text(
        json.dumps(
            {
                "phits_generation": {
                    "ct_voxel_assets": {"raw_datfiles_sha256": raw_hashes}
                }
            }
        ),
        encoding="utf-8",
    )
    rtstruct = tmp_path / "RTSTRUCT.dcm"
    rtstruct_sha256 = write(rtstruct, b"selected RT Structure Set")
    binding = {
        "manifest_path": str(segment_manifest),
        "manifest_sha256": "1" * 64,
        "sumtally_input_path": str(sumtally_input),
        "sumtally_input_sha256": sumtally_input_sha256,
        "segment_output_evidence": [
            {"path": str(segment_output), "sha256": segment_sha256}
        ],
        "wrapper_include_evidence": [
            {"path": str(sumtally_input), "sha256": sumtally_input_sha256}
        ],
    }
    pair = {
        "dose_path": str(dose),
        "dose_sha256": dose_sha256,
        "error_path": str(error),
        "error_sha256": error_sha256,
        "sum_input_sha256": sum_input_sha256,
    }
    ct_evidence = {
        "ct2phits_manifest_sha256": module.file_sha256(ct_manifest_path),
        "ct2phits_execution_summary_sha256": module.file_sha256(ct_summary_path),
        "workspace_preparation_sha256": module.file_sha256(preparation_path),
        "ct_reference_sha256": reference_sha256,
    }
    placement = {"validated": True}
    control_evidence = {
        "files": [
            {
                "label": label,
                "path": str(path),
                "sha256": module.file_sha256(path),
            }
            for label, path in (
                (
                    "Sumtally generation summary",
                    analysis / "sumtally_generation_summary.json",
                ),
                (
                    "Sumtally execution summary",
                    analysis / "sumtally_execution_summary.json",
                ),
                ("segment preflight receipt", analysis / "segment_preflight.json"),
                ("segment manifest", segment_manifest),
            )
        ],
        "sum_input_path": str(sum_input),
    }

    retained = module._capture_retained_validation(
        workspace_root=workspace,
        rtstruct_path=rtstruct,
        rtplan_path=rtplan,
        ct_reference_path=reference,
        roi_number=7,
        sumtally_binding=binding,
        pair_evidence=pair,
        control_evidence=control_evidence,
        ct_evidence=ct_evidence,
        ct_directory_evidence={
            "path": str(ct_root),
            "entries": [reference.name],
        },
        placement=placement,
        rtstruct_sha256=rtstruct_sha256,
    )
    assert module._verify_retained_validation(
        retained,
        workspace_root=workspace,
        rtstruct_path=rtstruct,
        rtplan_path=rtplan,
        ct_reference_path=reference,
        roi_number=7,
    ) == (binding, pair, ct_evidence, placement)

    added_ct = ct_root / "added.dcm"
    added_ct.write_bytes(b"matching-series race placeholder")
    with pytest.raises(
        StructureRelativeErrorUnavailable,
        match="membership does not match validated evidence",
    ):
        module._capture_retained_validation(
            workspace_root=workspace,
            rtstruct_path=rtstruct,
            rtplan_path=rtplan,
            ct_reference_path=reference,
            roi_number=7,
            sumtally_binding=binding,
            pair_evidence=pair,
            control_evidence=control_evidence,
            ct_evidence=ct_evidence,
            ct_directory_evidence={
                "path": str(ct_root),
                "entries": [reference.name],
            },
            placement=placement,
            rtstruct_sha256=rtstruct_sha256,
        )
    added_ct.unlink()

    generation_path = analysis / "sumtally_generation_summary.json"
    original_generation = generation_path.read_bytes()
    generation_path.write_text(
        json.dumps({"stage_status": "failed"}),
        encoding="utf-8",
    )
    with pytest.raises(
        StructureRelativeErrorUnavailable,
        match="validated digest evidence",
    ):
        module._capture_retained_validation(
            workspace_root=workspace,
            rtstruct_path=rtstruct,
            rtplan_path=rtplan,
            ct_reference_path=reference,
            roi_number=7,
            sumtally_binding=binding,
            pair_evidence=pair,
            control_evidence=control_evidence,
            ct_evidence=ct_evidence,
            ct_directory_evidence={
                "path": str(ct_root),
                "entries": [reference.name],
            },
            placement=placement,
            rtstruct_sha256=rtstruct_sha256,
        )
    generation_path.write_bytes(original_generation)
    retained = module._capture_retained_validation(
        workspace_root=workspace,
        rtstruct_path=rtstruct,
        rtplan_path=rtplan,
        ct_reference_path=reference,
        roi_number=7,
        sumtally_binding=binding,
        pair_evidence=pair,
        control_evidence=control_evidence,
        ct_evidence=ct_evidence,
        ct_directory_evidence={
            "path": str(ct_root),
            "entries": [reference.name],
        },
        placement=placement,
        rtstruct_sha256=rtstruct_sha256,
    )

    dose.write_bytes(b"changed dose!")
    with pytest.raises(StructureRelativeErrorUnavailable, match="source changed"):
        module._verify_retained_validation(
            retained,
            workspace_root=workspace,
            rtstruct_path=rtstruct,
            rtplan_path=rtplan,
            ct_reference_path=reference,
            roi_number=7,
        )


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

    decimal_series = SimpleNamespace(
        slices=(
            SimpleNamespace(
                position=np.asarray([0.0, 0.0, 0.0]),
                distance_mm=0.0,
            ),
        ),
        rows=3,
        columns=3,
        row_spacing_mm=0.1,
        column_spacing_mm=0.1,
        slice_spacing_mm=0.1,
        row_direction=np.asarray([1.0, 0.0, 0.0]),
        column_direction=np.asarray([0.0, 1.0, 0.0]),
        normal_direction=np.asarray([0.0, 0.0, 1.0]),
    )
    decimal_boundary = {
        "output_shape_frames_rows_columns": [1, 1, 1],
        "image_position_patient_mm": [0.15, 0.02, 0.0],
        "image_orientation_patient": [1.0, 0.0, 0.0, 0.0, 1.0, 0.0],
        "pixel_spacing_mm": [0.1, 0.1],
        "grid_frame_offset_vector_mm": [0.0],
    }
    assert 0.15 / 0.1 + 0.5 != 2.0
    with pytest.raises(StructureRelativeErrorUnavailable, match="boundary"):
        _structure_membership_on_dose_grid(
            placement=decimal_boundary,
            series=decimal_series,
            ct_mask=np.ones((1, 3, 3), dtype=bool),
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
    ct_evidence = {
        "ct_series_evidence_sha256": "4" * 64,
        "ct2phits_manifest_sha256": "5" * 64,
        "ct2phits_execution_summary_sha256": "6" * 64,
        "workspace_preparation_sha256": "9" * 64,
        "ct_reference_sha256": "7" * 64,
    }
    placement = module.derive_rtdose_placement(
        GEOMETRY,
        rtplan_isocenter_dicom_mm=[0.5, 0.5, 0.0],
    )
    retained_validation = {"synthetic": True}
    rtstruct_snapshot = module._retained_file_snapshot(
        rtstruct_path,
        label="selected RT Structure Set",
        expected_sha256=module.file_sha256(rtstruct_path),
        poll_sha256=False,
    )

    def verify_retained(*_args, **_kwargs):
        module._verify_retained_file_snapshot(rtstruct_snapshot)
        return binding, pair, ct_evidence, placement
    monkeypatch.setattr(
        module,
        "_current_combined_source",
        lambda _root: (
            np.asarray([10.0, 8.0, 6.0, 4.0]),
            np.asarray([0.1, 0.0, 0.3, 0.2]),
            MESH,
            binding,
            pair,
            {},
        ),
    )
    monkeypatch.setattr(
        module,
        "_frozen_ct_series",
        lambda _path, **_kwargs: (
            _fake_series(),
            ct_evidence,
            {"path": str(tmp_path), "entries": [rtstruct_path.name]},
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
    monkeypatch.setattr(
        module,
        "_capture_retained_validation",
        lambda **_kwargs: retained_validation,
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
        "_current_combined_source",
        lambda *_args, **_kwargs: pytest.fail(
            "retained-result validation must not reparse combined tally grids"
        ),
    )
    monkeypatch.setattr(
        module,
        "_frozen_ct_series",
        lambda *_args, **_kwargs: pytest.fail(
            "retained-result validation must not reload frozen CT pixels"
        ),
    )
    monkeypatch.setattr(
        module,
        "validate_full_plan_context",
        lambda **_kwargs: pytest.fail(
            "retained-result validation must not reparse DICOM context"
        ),
    )
    monkeypatch.setattr(
        module,
        "load_rtstruct_roi_mask_by_number",
        lambda *_args, **_kwargs: pytest.fail(
            "retained-result validation must not reevaluate Structure membership"
        ),
    )
    monkeypatch.setattr(
        module,
        "_verify_retained_validation",
        verify_retained,
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
    with pytest.raises(StructureRelativeErrorUnavailable, match="source changed"):
        revalidate_structure_relative_error_result(
            **request,
            expected_result=result,
        )
    rtstruct_path.write_bytes(b"synthetic RT Structure Set placeholder")
    rtstruct_snapshot.clear()
    rtstruct_snapshot.update(
        module._retained_file_snapshot(
            rtstruct_path,
            label="selected RT Structure Set",
            expected_sha256=module.file_sha256(rtstruct_path),
            poll_sha256=False,
        )
    )

    persisted_path.write_text("{}\n", encoding="utf-8")
    with pytest.raises(StructureRelativeErrorUnavailable, match="stale|mismatched"):
        revalidate_structure_relative_error_result(
            **request,
            expected_result=result,
        )
    assert persisted_path.read_text(encoding="utf-8") == "{}\n"


def test_windows_result_publication_does_not_require_hard_links(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    result_path = workspace / "analysis" / "structure_relative_error" / "result.json"
    record = {"schema_version": "synthetic", "value": 1}

    monkeypatch.setattr(module, "_ATOMIC_NO_REPLACE_RENAME", True)
    monkeypatch.setattr(
        module.os,
        "link",
        lambda *_args, **_kwargs: pytest.fail(
            "Windows-compatible publication must not require hard links"
        ),
    )

    assert module._publish_new_record(workspace, result_path, record) == record
    assert json.loads(result_path.read_text(encoding="utf-8")) == record
    assert list(result_path.parent.iterdir()) == [result_path]


@pytest.mark.skipif(module.os.name != "nt", reason="Windows rename semantics")
def test_windows_result_publication_never_replaces_existing_path(
    tmp_path: Path,
) -> None:
    temporary = tmp_path / "temporary.json"
    result_path = tmp_path / "result.json"
    temporary.write_text("new\n", encoding="utf-8")
    result_path.write_text("existing\n", encoding="utf-8")

    with pytest.raises(FileExistsError):
        module._publish_temporary_without_replacement(temporary, result_path)

    assert result_path.read_text(encoding="utf-8") == "existing\n"
    assert temporary.read_text(encoding="utf-8") == "new\n"


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
    monkeypatch.setattr(
        gui_module,
        "_current_sumtally_binding",
        lambda _root, **_kwargs: None,
    )
    assert structure_evaluation_enabled(**common) is False
    monkeypatch.setattr(
        gui_module,
        "_current_sumtally_binding",
        lambda _root, **_kwargs: {"verified": True},
    )
    assert structure_evaluation_enabled(**common) is True
    assert structure_evaluation_enabled(**{**common, "roi_number": "PTV"}) is False
    assert structure_evaluation_enabled(**{**common, "busy": True}) is False
    assert structure_roi_number(" 7 ") == 7
    with pytest.raises(GuiValidationError):
        structure_roi_number("PTV")


def test_gui_action_requires_validated_combined_error_evidence(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    analysis = workspace / "analysis"
    segments = workspace / "segments"
    analysis.mkdir(parents=True)
    segments.mkdir()
    manifest = {"segments": [{"segment_id": "segment-1"}]}
    (segments / "segment_manifest.json").write_text(
        json.dumps(manifest),
        encoding="utf-8",
    )
    manifest_digest = gui_module.manifest_sha256(manifest)
    normalization = {"validated": True}
    generation = {
        "stage_status": "success",
        "manifest_sha256": manifest_digest,
        "sum_input_sha256": "1" * 64,
        "sumtally_input_sha256": "2" * 64,
        "sumtally_normalization": gui_module.ACTIVE_TREATMENT_SUMTALLY_NORMALIZATION,
        "sumtally_normalization_evidence": normalization,
        "segment_output_evidence": [],
        "wrapper_include_evidence": [],
    }
    pair = {
        "schema_version": module.PAIR_SCHEMA_VERSION,
        "semantics": module.PAIR_SEMANTICS,
        "dose_path": str(workspace / "sumtally" / "dose.out"),
        "dose_sha256": "3" * 64,
        "error_path": str(workspace / "sumtally" / "dose_err.out"),
        "error_sha256": "4" * 64,
        "sum_input_sha256": generation["sum_input_sha256"],
        "mesh_geometry_sha256": "5" * 64,
        "cell_count": 4,
        "pair_metadata_sha256": "6" * 64,
        "validated": True,
    }
    execution = {
        **generation,
        "expected_sumtally_output_updated_by_run": True,
        "expected_sumtally_output_sha256": pair["dose_sha256"],
        "combined_relative_error_evidence": pair,
    }
    generation_path = (
        workspace
        / gui_module.stage_by_key("generate_sumtally").summary_relative_path
    )
    execution_path = (
        workspace / gui_module.stage_by_key("run_sumtally").summary_relative_path
    )
    generation_path.write_text(json.dumps(generation), encoding="utf-8")
    execution_path.write_text(json.dumps(execution), encoding="utf-8")

    assert (
        gui_module._current_sumtally_binding(
            workspace,
            require_combined_error=True,
        )
        is not None
    )

    execution.pop("combined_relative_error_evidence")
    execution_path.write_text(json.dumps(execution), encoding="utf-8")
    assert (
        gui_module._current_sumtally_binding(
            workspace,
            require_combined_error=True,
        )
        is None
    )

    pair["validated"] = False
    execution["combined_relative_error_evidence"] = pair
    execution_path.write_text(json.dumps(execution), encoding="utf-8")
    assert (
        gui_module._current_sumtally_binding(
            workspace,
            require_combined_error=True,
        )
        is None
    )


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
