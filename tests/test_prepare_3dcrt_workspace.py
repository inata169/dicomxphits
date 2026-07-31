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

import dicomxphits.prepare_3dcrt_workspace as workspace_module
from dicomxphits.prepare_3dcrt_workspace import (
    ExternalToolPaths,
    build_parser,
    export_segment_manifest,
    generate_rectangular_phits_workspace,
    prepare_public_3dcrt_workspace,
    validate_public_strict_3dcrt_gate,
    write_libpath,
)


def active_segment(**overrides):
    segment = {
        "segment_id": "seg_001",
        "delivery_type": "3dcrt",
        "beam_meterset_mu": 100.0,
        "segment_mu": 100.0,
        "mu_weight": 100.0,
        "mu_weight_unit": "MU",
        "phits_input_path": "segments/seg_001/phits.inp",
        "expected_output_path": "segments/seg_001/deposit-target-3D.out",
    }
    segment.update(overrides)
    return segment


def manifest_with(*segments):
    return {"schema_version": "segment_manifest_v2", "case_id": "synthetic", "segments": list(segments)}


def test_rtplan_segments_direct_script_help_reaches_argparse() -> None:
    script = PUBLIC_SRC / "dicomxphits" / "rtplan_segments.py"

    result = subprocess.run(
        [sys.executable, str(script), "--help"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert "Export 3D CRT/static IMRT segment manifest" in result.stdout


def rectangular_segment(**overrides):
    segment = {
        "segment_id": "seg_b0001_s0000",
        "delivery_type": "3dcrt_static",
        "beam_meterset_mu": 100.0,
        "segment_mu": 100.0,
        "mu_weight": 100.0,
        "mu_weight_unit": "MU",
        "static_aperture_classification": {"status": "static", "source": "test"},
        "aperture_change_diagnostics": {
            "status": "static",
            "dynamic_like": False,
            "jaw_changed": False,
            "mlc_changed": False,
        },
        "resolved_jaw_positions_mm": {"x1": -40.0, "x2": 40.0, "y1": -50.0, "y2": 50.0},
        "mlc_aperture_state": "present",
        "resolved_mlc_positions_mm": {
            "bank_a": [-20.0, -15.0, -10.0, -5.0],
            "bank_b": [20.0, 15.0, 10.0, 5.0],
        },
        "gantry_angle_deg": 10.0,
        "collimator_angle_deg": 20.0,
        "couch_angle_deg": 0.0,
        "phits_input_path": "phits_inputs/original-exporter-path.inp",
        "expected_output_path": "segments/seg_b0001_s0000/deposit-target-3D.out",
    }
    segment.update(overrides)
    return segment


def machine_config(**overrides):
    config = {
        "schema_version": "dicomxphits_public_machine_config_v1",
        "units": {"geometry": "mm", "density": "g/cm3"},
        "coordinate_system": {"origin": "isocenter", "z_axis": "beam", "z_positive": "downstream"},
        "sad_mm": 1000.0,
        "source": {"model": "point", "position_mm": [0.0, 0.0, -1000.0]},
        "materials": {"shielding": {"density_g_cm3": 17.0, "material_block": "74W 1"}},
        "y_diaphragm": {"upstream_z_mm": -461.0, "downstream_z_mm": -380.0, "material": "shielding"},
        "mlc": {
            "leaf_pair_count": 4,
            "leaf_widths_mm": [5.0, 5.0, 5.0, 5.0],
            "leaf_depth_mm": 60.0,
            "upstream_z_mm": -350.0,
            "downstream_z_mm": -300.0,
            "material": "shielding",
        },
    }
    config.update(overrides)
    return config


def write_machine_config(tmp_path, config=None):
    path = tmp_path / "machine_config.json"
    path.write_text(json.dumps(config or machine_config()), encoding="utf-8")
    return path


def write_ct_assets(tmp_path, *, voxel_counts=(2, 2, 2)):
    root = tmp_path / "ct2phits_assets"
    root.mkdir()
    nx, ny, nz = voxel_counts
    (root / "CTusrparam.dat").write_text(
        f"set: c81[{nx}]\nset: c82[{ny}]\nset: c83[{nz}]\n",
        encoding="utf-8",
    )
    for name in (
        "CTtrans.inp",
        "CTsurf.dat",
        "CTmaterial.dat",
        "CTuniverse.inp",
        "CTvoxel.inp",
    ):
        (root / name).write_text(f"$ synthetic {name}\n", encoding="utf-8")
    return root


def smoke_machine_config():
    return machine_config(
        materials={
            "shielding": {
                "density_g_cm3": 1.0,
                "material_block": "1H 2\n16O 1",
            }
        },
    )


def complete_paths():
    return ExternalToolPaths(
        phits_root_folder="/opt/phits-root",
        phits_executable_path="/opt/phits-root/bin/phits",
        phits2dicom_executable_path="/opt/phits-root/bin/phits2dicom",
    )


def no_phits_inputs(workspace):
    return list(Path(workspace).glob("segments/**/phits.inp"))


def install_manifest_export(monkeypatch, manifest):
    def fake_export_segment_manifest(**kwargs):
        case_root = Path(kwargs["case_root"])
        manifest_path = case_root / "segments" / "segment_manifest.json"
        manifest_path.parent.mkdir(parents=True)
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        return manifest, manifest_path

    monkeypatch.setattr(
        "dicomxphits.prepare_3dcrt_workspace.export_segment_manifest",
        fake_export_segment_manifest,
    )

    def fake_prepare_ct2phits_assets(**kwargs):
        root = Path(kwargs["output_root"])
        root.mkdir(parents=True)
        (root / "CTusrparam.dat").write_text(
            "set: c81[101]\nset: c82[101]\nset: c83[101]\n",
            encoding="utf-8",
        )
        for name in (
            "CTtrans.inp",
            "CTsurf.dat",
            "CTmaterial.dat",
            "CTuniverse.inp",
            "CTvoxel.inp",
        ):
            (root / name).write_text(f"$ synthetic {name}\n", encoding="utf-8")
        assets = workspace_module.validate_ct_assets(
            root,
            confirmed_non_patient_phantom=True,
        )
        return workspace_module.PreparedCt2PhitsSet(
            assets=assets,
            raw_sha256={"CTusrparam.dat": "synthetic"},
            ct_origin_dicom_cm=(0.0, 0.0, 0.0),
            rtplan_isocenter_dicom_cm=(0.0, 0.0, 0.0),
            ct_shift_iec_cm=(0.0, 0.0, 0.0),
            frame_of_reference_uid="synthetic-frame",
            ct_series_instance_uid="synthetic-series",
            ct_slice_count=1,
        )

    monkeypatch.setattr(
        "dicomxphits.prepare_3dcrt_workspace.prepare_ct2phits_assets",
        fake_prepare_ct2phits_assets,
    )


def test_strict_gate_requires_active_segment():
    with pytest.raises(ValueError, match="at least one non-skipped segment"):
        validate_public_strict_3dcrt_gate(manifest_with())

    skipped = active_segment(skip_reason="filtered")
    with pytest.raises(ValueError, match="at least one non-skipped segment"):
        validate_public_strict_3dcrt_gate(manifest_with(skipped))


def test_strict_gate_requires_3dcrt_delivery_type():
    manifest = manifest_with(active_segment(delivery_type="vmat"))

    with pytest.raises(ValueError, match="delivery_type must be 3dcrt"):
        validate_public_strict_3dcrt_gate(manifest)


@pytest.mark.parametrize("field", ["beam_meterset_mu", "segment_mu", "mu_weight"])
@pytest.mark.parametrize("value", [None, 0.0, -1.0, float("inf")])
def test_strict_gate_requires_positive_finite_mu_values(field, value):
    manifest = manifest_with(active_segment(**{field: value}))

    with pytest.raises(ValueError, match=field):
        validate_public_strict_3dcrt_gate(manifest)


@pytest.mark.parametrize("value", [None, 0.0, -1.0, float("inf")])
def test_strict_gate_rejects_invalid_beam_mu_on_skipped_segments(value):
    valid = active_segment(segment_id="seg_001", beam_number=1)
    skipped = active_segment(
        segment_id="seg_002",
        beam_number=2,
        beam_meterset_mu=value,
        segment_mu=0.0,
        mu_weight=0.0,
        skip_reason="delivery_type unsupported",
    )
    manifest = manifest_with(valid, skipped)

    with pytest.raises(ValueError, match="beam 2: beam_meterset_mu"):
        validate_public_strict_3dcrt_gate(manifest)


def test_strict_gate_accepts_valid_3dcrt_mu_segment():
    summary = validate_public_strict_3dcrt_gate(manifest_with(active_segment()))

    assert summary["status"] == "passed"
    assert summary["active_segment_count"] == 1
    assert summary["strict_mu_mode"] is True


def test_write_libpath_uses_phits_root_folder(tmp_path):
    path = write_libpath(tmp_path, phits_root_folder="/opt/phits-root")

    assert path.read_text(encoding="utf-8") == "file(1)  = /opt/phits-root # PHITS install folder name\n"


def test_legacy_tool_smoke_mode_is_rejected_before_workspace_creation(tmp_path):
    rtplan = tmp_path / "synthetic_rtplan.dcm"
    rtplan.write_text("placeholder", encoding="utf-8")
    workspace = tmp_path / "workspace"

    with pytest.raises(ValueError, match="geometry_mode must be one of"):
        prepare_public_3dcrt_workspace(
            rtplan_path=rtplan,
            workspace_root=workspace,
            paths=ExternalToolPaths(
                phits_root_folder="/opt/phits-root",
                phits_executable_path="",
            ),
            case_id="synthetic",
            geometry_mode="tool_smoke",
        )

    assert not workspace.exists()


def test_prepare_workspace_adapter_is_standalone_without_project_root():
    parser_actions = {action.dest for action in build_parser()._actions}

    assert "project_root" not in inspect.signature(prepare_public_3dcrt_workspace).parameters
    assert "project_root" not in inspect.signature(export_segment_manifest).parameters
    assert "project_root" not in parser_actions


def test_parser_exposes_geometry_mode_and_machine_config_path():
    parser_actions = {action.dest for action in build_parser()._actions}

    assert "geometry_mode" in parser_actions
    assert "machine_config_path" in parser_actions
    assert "relative_dose_only" in parser_actions
    assert build_parser().parse_args(
        ["--rtplan", "plan.dcm", "--workspace-root", "workspace"]
    ).geometry_mode == "rectangular_3dcrt"
    assert build_parser().parse_args(
        ["--rtplan", "plan.dcm", "--workspace-root", "workspace"]
    ).relative_dose_only is False
    assert tuple(
        next(
            action
            for action in build_parser()._actions
            if action.dest == "geometry_mode"
        ).choices
    ) == ("rectangular_3dcrt",)


def test_rectangular_3dcrt_requires_ct_assets_before_workspace_creation(tmp_path):
    rtplan = tmp_path / "synthetic_rtplan.dcm"
    rtplan.write_text("placeholder", encoding="utf-8")
    workspace = tmp_path / "workspace"

    with pytest.raises(ValueError, match="requires --ct-datfiles-root"):
        prepare_public_3dcrt_workspace(
            rtplan_path=rtplan,
            workspace_root=workspace,
            paths=ExternalToolPaths(
                phits_root_folder="/opt/phits-root",
                phits_executable_path="",
            ),
        )

    assert not workspace.exists()


def test_rectangular_3dcrt_requires_non_patient_confirmation_before_workspace_creation(
    tmp_path,
):
    rtplan = tmp_path / "synthetic_rtplan.dcm"
    rtplan.write_text("placeholder", encoding="utf-8")
    workspace = tmp_path / "workspace"

    with pytest.raises(ValueError, match="explicit non-patient phantom confirmation"):
        prepare_public_3dcrt_workspace(
            rtplan_path=rtplan,
            workspace_root=workspace,
            paths=ExternalToolPaths(
                phits_root_folder="/opt/phits-root",
                phits_executable_path="",
            ),
            ct_datfiles_root=tmp_path / "DATfiles",
            ct_reference_dicom=tmp_path / "CT.dcm",
        )

    assert not workspace.exists()


def test_rectangular_3dcrt_default_needs_no_vendor_or_iaea_runtime_input(
    monkeypatch,
    tmp_path,
):
    segment = rectangular_segment(
        resolved_mlc_positions_mm={
            "bank_a": [-20.0] * 80,
            "bank_b": [20.0] * 80,
        }
    )
    install_manifest_export(monkeypatch, manifest_with(segment))
    rtplan = tmp_path / "synthetic_rtplan.dcm"
    rtplan.write_text("placeholder", encoding="utf-8")
    workspace = tmp_path / "workspace"

    summary = prepare_public_3dcrt_workspace(
        rtplan_path=rtplan,
        workspace_root=workspace,
        paths=ExternalToolPaths(
            phits_root_folder="/opt/phits-root",
            phits_executable_path="",
        ),
        ct_datfiles_root=tmp_path / "DATfiles",
        ct_reference_dicom=tmp_path / "CT.dcm",
        confirmed_non_patient_phantom=True,
    )

    generation = summary["phits_generation"]
    text = (workspace / generation["generated_phits_inputs"][0]).read_text(
        encoding="utf-8"
    )
    assert generation["machine_config_source"] == "built_in_public_default"
    assert "set: c10[20] $ Collimator angle (deg)" in text
    assert "set: c20[10] $ Gantry angle (deg)" in text
    assert "tr2   0 0 0" in text
    assert "tr3   0.0000 0.0000 0.0000" in text
    assert "infl:{CTusrparam.dat}" in text
    assert "fill=5000" in text
    assert "nx = 101" in text
    assert "ny = 101" in text
    assert text.count("nz = 101") == 2
    assert "file = segments/seg_b0001_s0000/deposit-target-3D.out" in text
    assert "file = segments/seg_b0001_s0000/deposit-pdd.out" in text
    assert " ne = 59" in text
    assert " emin(12) = 0.7" in text
    assert " emin(14) = 0.01" in text
    assert "MAT[1] $ author_tuned_tungsten_alloy" in text
    assert ".IAEAphsp" not in text
    assert ".IAEAheader" not in text
    assert "scoring placeholder" not in text
    assert "Public rectangular 3D-CRT PHITS input" not in text
    assert " totfact = 8.7608E+11" in text
    parameters = text.split("[ Parameters ]\n", 1)[1].split("\n[ S o u r c e ]", 1)[0]
    source = text.split("[ S o u r c e ]\n", 1)[1].split("\n[ Surface ]", 1)[0]
    assert "totfact" not in parameters
    assert " totfact = 8.7608E+11" in source
    assert generation["absolute_dose_calibration"]["totfact_per_mu"] == (
        "8.7608E+11"
    )
    assert "vendor" not in text.lower()
    assert "facility" not in text.lower()


def test_rectangular_3dcrt_preserves_validated_gantry_source_and_transform_pair(
    tmp_path,
):
    workspace = tmp_path / "workspace"
    manifest = manifest_with(
        rectangular_segment(
            gantry_angle_deg=90.0,
            collimator_angle_deg=45.0,
            resolved_mlc_positions_mm={
                "bank_a": [-20.0] * 80,
                "bank_b": [20.0] * 80,
            },
        )
    )

    summary = generate_rectangular_phits_workspace(
        manifest=manifest,
        case_root=workspace,
        machine_config_path=None,
        apply_approved_totfact=False,
        ct_asset_root=write_ct_assets(tmp_path),
        confirmed_non_patient_phantom=True,
    )

    text = (
        workspace / summary["generated_phits_inputs"][0]
    ).read_text(encoding="utf-8")
    source = text.split("[ S o u r c e ]\n", 1)[1].split("\n[ Surface ]", 1)[0]
    transform = text.split("[ Transform ]\n", 1)[1].split("\n[ T-Deposit ]", 1)[0]
    assert "x0 = 99.85" in source
    assert "x1 = 100.15" in source
    assert "z0 = 0" in source
    assert "z1 = 0" in source
    assert "dir = 0" in source
    assert "phi = 180" in source
    assert "set: c10[45] $ Collimator angle (deg)" in transform
    assert "set: c20[90] $ Gantry angle (deg)" in transform
    assert "      sin(c20/180*pi)" in transform
    assert "     -sin(c20/180*pi)" in transform


def test_rectangular_3dcrt_rejects_nonzero_couch_without_partial_output(tmp_path):
    workspace = tmp_path / "workspace"

    with pytest.raises(ValueError, match="couch angle 0 degrees only"):
        generate_rectangular_phits_workspace(
            manifest=manifest_with(
                rectangular_segment(
                    couch_angle_deg=10.0,
                    resolved_mlc_positions_mm={
                        "bank_a": [-20.0] * 80,
                        "bank_b": [20.0] * 80,
                    },
                )
            ),
            case_root=workspace,
            machine_config_path=None,
            apply_approved_totfact=False,
            ct_asset_root=write_ct_assets(tmp_path),
            confirmed_non_patient_phantom=True,
        )

    assert no_phits_inputs(workspace) == []
    assert not (workspace / "analysis" / "phits_generation_summary.json").exists()
    assert not (workspace / "CTusrparam.dat").exists()


def test_rectangular_3dcrt_rejects_stale_factor_before_output(tmp_path):
    workspace = tmp_path / "workspace"

    with pytest.raises(ValueError, match="totfact_per_MU is stale"):
        generate_rectangular_phits_workspace(
            manifest=manifest_with(rectangular_segment()),
            case_root=workspace,
            machine_config_path=write_machine_config(tmp_path),
        )

    assert no_phits_inputs(workspace) == []
    assert not (workspace / "analysis" / "phits_generation_summary.json").exists()


def test_prepare_adapter_rejects_stale_factor_before_workspace_creation(tmp_path):
    rtplan = tmp_path / "synthetic_rtplan.dcm"
    rtplan.write_text("placeholder", encoding="utf-8")
    workspace = tmp_path / "workspace"

    with pytest.raises(ValueError, match="totfact_per_MU is stale"):
        prepare_public_3dcrt_workspace(
            rtplan_path=rtplan,
            workspace_root=workspace,
            paths=complete_paths(),
            machine_config_path=write_machine_config(tmp_path),
            ct_datfiles_root=tmp_path / "DATfiles",
            ct_reference_dicom=tmp_path / "CT.dcm",
            confirmed_non_patient_phantom=True,
        )

    assert not workspace.exists()


def test_rectangular_3dcrt_writes_one_input_per_active_segment_in_manifest_order(monkeypatch, tmp_path):
    manifest = manifest_with(
        rectangular_segment(
            segment_id="Seg Alpha",
            phits_input_path="phits_inputs/exported_alpha.inp",
            expected_output_path="outputs/alpha.out",
        ),
        rectangular_segment(
            segment_id="SEG+B",
            phits_input_path="phits_inputs/exported_b.inp",
            expected_output_path="outputs/b.out",
        ),
    )
    install_manifest_export(monkeypatch, manifest)
    rtplan = tmp_path / "synthetic_rtplan.dcm"
    rtplan.write_text("placeholder", encoding="utf-8")
    workspace = tmp_path / "workspace"

    summary = prepare_public_3dcrt_workspace(
        rtplan_path=rtplan,
        workspace_root=workspace,
        paths=complete_paths(),
        geometry_mode="rectangular_3dcrt",
        machine_config_path=write_machine_config(tmp_path),
        apply_approved_totfact=False,
        ct_datfiles_root=tmp_path / "DATfiles",
        ct_reference_dicom=tmp_path / "CT.dcm",
        confirmed_non_patient_phantom=True,
    )

    expected_inputs = ["segments/seg_alpha/phits.inp", "segments/seg_b/phits.inp"]
    generation = summary["phits_generation"]
    assert summary["geometry_mode"] == "rectangular_3dcrt"
    assert summary["rtplan_path"] == "synthetic_rtplan.dcm"
    assert summary["workspace_root"] == "."
    assert generation["geometry_mode"] == "rectangular_3dcrt"
    assert generation["generated_segment_count"] == 2
    assert generation["generated_phits_inputs"] == expected_inputs
    assert generation["segment_ids"] == ["seg_alpha", "seg_b"]
    assert generation["phits_execution_performed"] is False
    assert summary["phits_execution_performed"] is False
    for relative_input in expected_inputs:
        text = (workspace / relative_input).read_text(encoding="utf-8")
        assert "Public CT-derived voxel phantom calibration input" in text
        assert "infl:{CTusrparam.dat}" in text
        assert "fill=5000" in text
        assert "[ S o u r c e ]" in text
        assert "[ T-Deposit ]" in text
        assert " output = dose" in text
        assert " part = all" in text
        assert "minimal water sphere" not in text
    first_text = (workspace / expected_inputs[0]).read_text(encoding="utf-8")
    assert " file(6) = phits.out" in first_text
    assert " file = outputs/alpha.out" in first_text
    persisted_manifest = json.loads((workspace / "segments" / "segment_manifest.json").read_text(encoding="utf-8"))
    active_segments = [segment for segment in persisted_manifest["segments"] if not segment.get("skip_reason")]
    assert [segment["phits_input_path"] for segment in active_segments] == expected_inputs
    assert [segment["expected_output_path"] for segment in active_segments] == ["outputs/alpha.out", "outputs/b.out"]
    assert all((workspace / segment["phits_input_path"]).is_file() for segment in active_segments)
    summary_text = (workspace / "analysis" / "public_preparation_workspace_summary.json").read_text(encoding="utf-8")
    assert str(tmp_path) not in summary_text


def test_rectangular_3dcrt_ignores_inactive_segments(monkeypatch, tmp_path):
    manifest = manifest_with(
        rectangular_segment(segment_id="active", expected_output_path="outputs/active.out"),
        rectangular_segment(segment_id="inactive", skip_reason="filtered", expected_output_path="outputs/inactive.out"),
    )
    install_manifest_export(monkeypatch, manifest)
    rtplan = tmp_path / "synthetic_rtplan.dcm"
    rtplan.write_text("placeholder", encoding="utf-8")
    workspace = tmp_path / "workspace"

    summary = prepare_public_3dcrt_workspace(
        rtplan_path=rtplan,
        workspace_root=workspace,
        paths=complete_paths(),
        geometry_mode="rectangular_3dcrt",
        machine_config_path=write_machine_config(tmp_path),
        apply_approved_totfact=False,
        ct_datfiles_root=tmp_path / "DATfiles",
        ct_reference_dicom=tmp_path / "CT.dcm",
        confirmed_non_patient_phantom=True,
    )

    assert summary["phits_generation"]["generated_phits_inputs"] == ["segments/active/phits.inp"]
    assert (workspace / "segments" / "active" / "phits.inp").is_file()
    assert not (workspace / "segments" / "inactive" / "phits.inp").exists()
    persisted_manifest = json.loads((workspace / "segments" / "segment_manifest.json").read_text(encoding="utf-8"))
    assert persisted_manifest["segments"][0]["phits_input_path"] == "segments/active/phits.inp"
    assert persisted_manifest["segments"][1]["phits_input_path"] == "phits_inputs/original-exporter-path.inp"


def test_rectangular_3dcrt_zero_active_segments_fails_before_output(tmp_path):
    workspace = tmp_path / "workspace"
    machine_config_path = write_machine_config(tmp_path)

    with pytest.raises(ValueError, match="at least one active segment"):
        generate_rectangular_phits_workspace(
            manifest=manifest_with(rectangular_segment(skip_reason="filtered")),
            case_root=workspace,
            machine_config_path=machine_config_path,
            apply_approved_totfact=False,
        )

    assert no_phits_inputs(workspace) == []
    assert not (workspace / "analysis" / "phits_generation_summary.json").exists()


def test_rectangular_3dcrt_later_invalid_segment_writes_no_partial_outputs(tmp_path):
    workspace = tmp_path / "workspace"
    machine_config_path = write_machine_config(tmp_path)
    manifest = manifest_with(
        rectangular_segment(segment_id="valid_one", expected_output_path="outputs/one.out"),
        rectangular_segment(
            segment_id="invalid_two",
            expected_output_path="outputs/two.out",
            resolved_jaw_positions_mm={"x1": 40.0, "x2": -40.0, "y1": -50.0, "y2": 50.0},
        ),
    )

    with pytest.raises(ValueError):
        generate_rectangular_phits_workspace(
            manifest=manifest,
            case_root=workspace,
            machine_config_path=machine_config_path,
            apply_approved_totfact=False,
        )

    assert no_phits_inputs(workspace) == []
    assert not (workspace / "analysis" / ".rectangular_phits_staging").exists()
    assert not (workspace / "analysis" / "phits_generation_summary.json").exists()


def test_rectangular_3dcrt_failure_does_not_modify_existing_phits_input(tmp_path):
    workspace = tmp_path / "workspace"
    existing = workspace / "segments" / "seg_b0001_s0000" / "phits.inp"
    existing.parent.mkdir(parents=True)
    existing.write_text("OLD\n", encoding="utf-8")

    with pytest.raises(ValueError, match="refusing to overwrite"):
        generate_rectangular_phits_workspace(
            manifest=manifest_with(rectangular_segment()),
            case_root=workspace,
            machine_config_path=write_machine_config(tmp_path),
            apply_approved_totfact=False,
        )

    assert existing.read_text(encoding="utf-8") == "OLD\n"


@pytest.mark.parametrize("bad_path", ["/private/output.out", "../output.out", "segments/../output.out"])
def test_rectangular_3dcrt_rejects_absolute_or_traversal_expected_output(tmp_path, bad_path):
    workspace = tmp_path / "workspace"

    with pytest.raises(ValueError, match="relative|must not contain"):
        generate_rectangular_phits_workspace(
            manifest=manifest_with(rectangular_segment(expected_output_path=bad_path)),
            case_root=workspace,
            machine_config_path=write_machine_config(tmp_path),
            apply_approved_totfact=False,
        )

    assert no_phits_inputs(workspace) == []


def test_rectangular_3dcrt_rejects_duplicate_sanitized_segment_ids_before_output(tmp_path):
    workspace = tmp_path / "workspace"

    with pytest.raises(ValueError, match="duplicate sanitized segment_id"):
        generate_rectangular_phits_workspace(
            manifest=manifest_with(
                rectangular_segment(segment_id="Seg A", expected_output_path="outputs/a.out"),
                rectangular_segment(segment_id="seg+a", expected_output_path="outputs/b.out"),
            ),
            case_root=workspace,
            machine_config_path=write_machine_config(tmp_path),
            apply_approved_totfact=False,
        )

    assert no_phits_inputs(workspace) == []


def test_rectangular_3dcrt_unresolved_material_fails_before_output(tmp_path):
    workspace = tmp_path / "workspace"
    bad_config = machine_config(y_diaphragm={"upstream_z_mm": -461.0, "downstream_z_mm": -380.0, "material": "missing"})

    with pytest.raises(ValueError, match="material"):
        generate_rectangular_phits_workspace(
            manifest=manifest_with(rectangular_segment()),
            case_root=workspace,
            machine_config_path=write_machine_config(tmp_path, bad_config),
            apply_approved_totfact=False,
        )

    assert no_phits_inputs(workspace) == []


def test_rectangular_3dcrt_failure_summary_does_not_claim_generated_inputs(tmp_path):
    workspace = tmp_path / "workspace"

    with pytest.raises(ValueError):
        generate_rectangular_phits_workspace(
            manifest=manifest_with(rectangular_segment(expected_output_path="../output.out")),
            case_root=workspace,
            machine_config_path=write_machine_config(tmp_path),
            apply_approved_totfact=False,
        )

    failure_summary = workspace / "analysis" / "phits_generation_summary.json"
    assert not failure_summary.exists()


def test_rectangular_3dcrt_success_summary_is_written_only_after_final_writes_succeed(monkeypatch, tmp_path):
    workspace = tmp_path / "workspace"

    def fail_write(**_kwargs):
        raise RuntimeError("simulated final write failure")

    monkeypatch.setattr(
        "dicomxphits.prepare_3dcrt_workspace.write_ct_rectangular_phits_inputs_atomically",
        fail_write,
    )

    with pytest.raises(RuntimeError, match="simulated final write failure"):
        generate_rectangular_phits_workspace(
            manifest=manifest_with(rectangular_segment()),
            case_root=workspace,
            machine_config_path=write_machine_config(tmp_path),
            apply_approved_totfact=False,
            ct_asset_root=write_ct_assets(tmp_path),
            confirmed_non_patient_phantom=True,
        )

    assert not (workspace / "analysis" / "phits_generation_summary.json").exists()


def test_rectangular_3dcrt_atomic_writer_cleans_final_outputs_and_staging_on_failure(monkeypatch, tmp_path):
    workspace = tmp_path / "workspace"
    calls = 0
    original_copy = workspace_module._copy_to_new_file_or_fail

    def fail_on_second_copy(source, destination):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("simulated second final write failure")
        original_copy(source, destination)

    monkeypatch.setattr("dicomxphits.prepare_3dcrt_workspace._copy_to_new_file_or_fail", fail_on_second_copy)

    with pytest.raises(RuntimeError, match="second final write failure"):
        generate_rectangular_phits_workspace(
            manifest=manifest_with(
                rectangular_segment(segment_id="first", expected_output_path="outputs/first.out"),
                rectangular_segment(segment_id="second", expected_output_path="outputs/second.out"),
            ),
            case_root=workspace,
            machine_config_path=write_machine_config(tmp_path),
            apply_approved_totfact=False,
            ct_asset_root=write_ct_assets(tmp_path),
            confirmed_non_patient_phantom=True,
        )

    assert no_phits_inputs(workspace) == []
    assert not (workspace / "analysis" / ".rectangular_phits_staging").exists()
    assert not (workspace / "analysis" / "phits_generation_summary.json").exists()


def test_rectangular_3dcrt_generated_input_is_complete_ct_runtime(tmp_path):
    workspace = tmp_path / "workspace"
    generate_rectangular_phits_workspace(
        manifest=manifest_with(
            rectangular_segment(
                segment_id="seg_smoke",
                expected_output_path="segments/seg_smoke/deposit-target-3D.out",
            )
        ),
        case_root=workspace,
        machine_config_path=write_machine_config(tmp_path, smoke_machine_config()),
        apply_approved_totfact=False,
        ct_asset_root=write_ct_assets(tmp_path),
        confirmed_non_patient_phantom=True,
    )
    phits_input = workspace / "segments" / "seg_smoke" / "phits.inp"
    text = phits_input.read_text(encoding="utf-8")
    assert "infl:{CTusrparam.dat}" in text
    assert "fill=5000" in text
    assert "nx = 101" in text
    assert "ny = 101" in text
    assert text.count("nz = 101") == 2
    assert "deposit-pdd.out" in text
    assert "placeholder" not in text.lower()
