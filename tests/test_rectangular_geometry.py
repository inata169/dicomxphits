from __future__ import annotations

import copy
import inspect
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

PUBLIC_SRC = Path(__file__).resolve().parents[1] / "src"
if str(PUBLIC_SRC) not in sys.path:
    sys.path.insert(0, str(PUBLIC_SRC))

from dicomxphits.rectangular_geometry import (
    RectangularGeometryError,
    build_intermediate_geometry,
    validate_rectangular_segment_contract,
)
from dicomxphits.machine_config import public_default_machine_config
from dicomxphits.rectangular_phits_renderer import render_rectangular_phits_input
import dicomxphits.prepare_3dcrt_workspace as workspace_module
from dicomxphits.rtplan_segments import build_manifest


def item(dtype, positions):
    return SimpleNamespace(RTBeamLimitingDeviceType=dtype, LeafJawPositions=positions)


def control_point(
    index,
    cmw,
    *,
    include_mlc=True,
    include_x_jaw=True,
    x_jaw_positions=None,
    leaf_positions=None,
    y_jaw_positions=None,
):
    positions = []
    if include_x_jaw:
        positions.append(item("ASYMX", x_jaw_positions or [-40.0, 40.0]))
    positions.append(item("ASYMY", y_jaw_positions or [-50.0, 50.0]))
    if include_mlc:
        positions.append(item("MLCX", leaf_positions or [-20.0, -15.0, -10.0, -5.0, 20.0, 15.0, 10.0, 5.0]))
    point = SimpleNamespace(
        ControlPointIndex=index,
        GantryAngle=10.0,
        BeamLimitingDeviceAngle=20.0,
        PatientSupportAngle=0.0,
        GantryRotationDirection="NONE",
        BeamLimitingDeviceRotationDirection="NONE",
        CumulativeMetersetWeight=cmw,
        BeamLimitingDevicePositionSequence=positions,
    )
    if index == 0:
        point.NominalBeamEnergy = 6.0
    return point


def beam(
    *,
    include_mlc=True,
    include_x_jaw=True,
    include_leaf_boundaries=True,
    beam_type="STATIC",
    x_jaw_positions=None,
    leaf_positions=None,
    leaf_boundaries=None,
    y_jaw_positions=None,
):
    devices = []
    if include_x_jaw:
        devices.append(SimpleNamespace(RTBeamLimitingDeviceType="ASYMX", NumberOfLeafJawPairs=1))
    devices.append(SimpleNamespace(RTBeamLimitingDeviceType="ASYMY", NumberOfLeafJawPairs=1))
    if include_mlc:
        mlc_device = SimpleNamespace(RTBeamLimitingDeviceType="MLCX", NumberOfLeafJawPairs=4)
        if include_leaf_boundaries:
            mlc_device.LeafPositionBoundaries = leaf_boundaries or [-10.0, -5.0, 0.0, 5.0, 10.0]
        devices.append(mlc_device)
    return SimpleNamespace(
        BeamNumber=1,
        BeamName="Public test beam",
        BeamType=beam_type,
        RadiationType="PHOTON",
        TreatmentDeliveryType="TREATMENT",
        FinalCumulativeMetersetWeight=1.0,
        BeamLimitingDeviceSequence=devices,
        ControlPointSequence=[
            control_point(
                0,
                0.0,
                include_mlc=include_mlc,
                include_x_jaw=include_x_jaw,
                x_jaw_positions=x_jaw_positions,
                leaf_positions=leaf_positions,
                y_jaw_positions=y_jaw_positions,
            ),
            control_point(
                1,
                1.0,
                include_mlc=include_mlc,
                include_x_jaw=include_x_jaw,
                x_jaw_positions=x_jaw_positions,
                leaf_positions=leaf_positions,
                y_jaw_positions=y_jaw_positions,
            ),
        ],
    )


def rtplan(
    *,
    include_mlc=True,
    include_x_jaw=True,
    include_leaf_boundaries=True,
    beam_type="STATIC",
    x_jaw_positions=None,
    leaf_positions=None,
    leaf_boundaries=None,
    y_jaw_positions=None,
):
    return SimpleNamespace(
        SOPInstanceUID="1.2.826.0.1.3680043.10.54321.999",
        RTPlanLabel="PUBLIC_RECT_TEST",
        BeamSequence=[
            beam(
                include_mlc=include_mlc,
                include_x_jaw=include_x_jaw,
                include_leaf_boundaries=include_leaf_boundaries,
                beam_type=beam_type,
                x_jaw_positions=x_jaw_positions,
                leaf_positions=leaf_positions,
                leaf_boundaries=leaf_boundaries,
                y_jaw_positions=y_jaw_positions,
            )
        ],
        FractionGroupSequence=[
            SimpleNamespace(
                ReferencedBeamSequence=[
                    SimpleNamespace(ReferencedBeamNumber=1, BeamMeterset=100.0),
                ]
            )
        ],
    )


def manifest_for(ds):
    manifest, _beam_rows, _cp_rows = build_manifest(
        ds,
        case_id="public_rect_test",
        workflow_mode="full_plan",
        include_beams=None,
        dose_normalization_mu=None,
        output_name="deposit-target-3D.out",
    )
    return manifest


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


def rectangular_segment(**overrides):
    segment = {
        "segment_id": "seg_b0001_s0000",
        "delivery_type": "3dcrt_static",
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
        "segment_mu": 100.0,
    }
    segment.update(overrides)
    return segment


def test_manifest_exporter_emits_rectangular_contract_for_static_3dcrt():
    manifest = manifest_for(rtplan())
    segment = manifest["segments"][0]

    assert segment["delivery_type"] == "3dcrt_static"
    assert segment["segment_id"] == "seg_b0001_s0000"
    assert "/" not in segment["segment_id"]
    assert "\\" not in segment["segment_id"]
    assert ".dcm" not in segment["segment_id"].lower()
    assert "uid" not in segment["segment_id"].lower()
    assert "patient" not in segment["segment_id"].lower()
    assert segment["static_aperture_classification"]["status"] == "static"
    assert segment["aperture_change_diagnostics"]["dynamic_like"] is False
    assert segment["resolved_jaw_positions_mm"] == {"x1": -40.0, "x2": 40.0, "y1": -50.0, "y2": 50.0}
    assert segment["mlc_aperture_state"] == "present"
    assert segment["resolved_mlc_positions_mm"]["bank_a"] == [-20.0, -15.0, -10.0, -5.0]
    assert segment["resolved_mlc_positions_mm"]["bank_b"] == [20.0, 15.0, 10.0, 5.0]


def test_manifest_exporter_resolves_missing_x_jaws_from_mlc_extent():
    manifest = manifest_for(rtplan(include_x_jaw=False))
    segment = manifest["segments"][0]

    assert segment["jaw_positions_mm"] == {"ASYMY": [-50.0, 50.0]}
    assert segment["resolved_jaw_positions_mm"] == {"x1": -20.0, "x2": 20.0, "y1": -50.0, "y2": 50.0}

    geometry = build_intermediate_geometry(segment, machine_config())

    assert geometry["jaw_positions_cm"] == {"x1": -2.0, "x2": 2.0, "y1": -5.0, "y2": 5.0}
    assert geometry["mlc_positions_cm"]["bank_a"] == [-2.0, -1.5, -1.0, -0.5]
    assert geometry["mlc_positions_cm"]["bank_b"] == [2.0, 1.5, 1.0, 0.5]


def test_manifest_exporter_resolves_missing_x_jaws_from_active_mlc_leaf_pairs_only():
    manifest = manifest_for(
        rtplan(
            include_x_jaw=False,
            leaf_boundaries=[-100.0, -50.0, 0.0, 50.0, 100.0],
            leaf_positions=[-90.0, -20.0, -15.0, -80.0, 90.0, 20.0, 15.0, 80.0],
            y_jaw_positions=[-50.0, 50.0],
        )
    )
    segment = manifest["segments"][0]

    assert segment["leaf_position_boundaries_mm"] == [-100.0, -50.0, 0.0, 50.0, 100.0]
    assert segment["resolved_jaw_positions_mm"] == {"x1": -20.0, "x2": 20.0, "y1": -50.0, "y2": 50.0}

    geometry = build_intermediate_geometry(segment, machine_config())

    assert geometry["jaw_positions_cm"] == {"x1": -2.0, "x2": 2.0, "y1": -5.0, "y2": 5.0}


def test_manifest_exporter_does_not_infer_missing_x_jaws_without_leaf_boundaries():
    manifest = manifest_for(rtplan(include_x_jaw=False, include_leaf_boundaries=False))
    segment = manifest["segments"][0]

    assert segment["resolved_jaw_positions_mm"] == {"x1": None, "x2": None, "y1": -50.0, "y2": 50.0}

    with pytest.raises(RectangularGeometryError, match="jaw_positions_mm.x1"):
        build_intermediate_geometry(segment, machine_config())


def test_manifest_exporter_emits_explicit_no_mlc_marker():
    manifest = manifest_for(rtplan(include_mlc=False))
    segment = manifest["segments"][0]

    assert segment["delivery_type"] == "3dcrt_static"
    assert segment["mlc_aperture_state"] == "no_mlc"
    assert segment["resolved_mlc_positions_mm"] is None


@pytest.mark.parametrize("delivery_type", [None, "3dcrt", "vmat", "unknown"])
def test_rectangular_contract_rejects_missing_or_non_static_delivery(delivery_type):
    segment = rectangular_segment(delivery_type=delivery_type)

    with pytest.raises(RectangularGeometryError, match="delivery_type"):
        validate_rectangular_segment_contract(segment, machine_config())


@pytest.mark.parametrize(
    "classification, diagnostics",
    [
        (None, {"status": "static", "dynamic_like": False, "jaw_changed": False, "mlc_changed": False}),
        ({"status": "static"}, None),
        ({"status": "static"}, {"status": "dynamic", "dynamic_like": False, "jaw_changed": False, "mlc_changed": False}),
        ({"status": "static"}, {"status": "static", "dynamic_like": True, "jaw_changed": False, "mlc_changed": False}),
        ({"status": "static"}, {"status": "static", "dynamic_like": False, "jaw_changed": True, "mlc_changed": False}),
    ],
)
def test_rectangular_contract_rejects_missing_or_dynamic_aperture_diagnostics(classification, diagnostics):
    segment = rectangular_segment(
        static_aperture_classification=classification,
        aperture_change_diagnostics=diagnostics,
    )

    with pytest.raises(RectangularGeometryError):
        validate_rectangular_segment_contract(segment, machine_config())


@pytest.mark.parametrize(
    "jaws",
    [
        {"x1": 40.0, "x2": -40.0, "y1": -50.0, "y2": 50.0},
        {"x1": -40.0, "x2": 40.0, "y1": 50.0, "y2": -50.0},
        {"x1": -40.0, "x2": 40.0, "y1": float("inf"), "y2": 50.0},
    ],
)
def test_rectangular_contract_rejects_invalid_jaws(jaws):
    segment = rectangular_segment(resolved_jaw_positions_mm=jaws)

    with pytest.raises(RectangularGeometryError):
        validate_rectangular_segment_contract(segment, machine_config())


def test_intermediate_geometry_rejects_public_scope_overrun():
    segment = rectangular_segment(
        resolved_jaw_positions_mm={"x1": -150.0, "x2": 150.0, "y1": -150.0, "y2": 150.0},
        resolved_mlc_positions_mm={
            "bank_a": [-150.0, -150.0, -150.0, -150.0],
            "bank_b": [150.0, 150.0, 150.0, 150.0],
        },
    )

    with pytest.raises(RectangularGeometryError, match=r"public aperture scope: X minimum -150\.0"):
        build_intermediate_geometry(segment, machine_config())


def test_intermediate_geometry_uses_jaw_mlc_common_aperture_for_scope():
    segment = rectangular_segment(
        resolved_jaw_positions_mm={"x1": -100.0, "x2": 100.0, "y1": -100.0, "y2": 100.0},
        resolved_mlc_positions_mm={
            "bank_a": [-150.0, -150.0, -150.0, -150.0],
            "bank_b": [150.0, 150.0, 150.0, 150.0],
        },
    )

    geometry = build_intermediate_geometry(segment, machine_config())

    assert geometry["jaw_positions_cm"]["x1"] == -10.0


def test_public_export_rejects_exact_decimal_overrun_before_workspace_creation(monkeypatch, tmp_path):
    ds = rtplan(
        include_mlc=False,
        x_jaw_positions=["-100.000", "100.001"],
        y_jaw_positions=["-100.000", "100.000"],
    )
    monkeypatch.setattr(workspace_module, "load_rtplan", lambda _path: ds)
    workspace = tmp_path / "workspace"

    with pytest.raises(ValueError, match=r"control_point=0: X maximum 100\.001"):
        workspace_module.export_segment_manifest(
            rtplan_path=tmp_path / "synthetic.dcm",
            case_root=workspace,
            case_id="scope_overrun",
            workflow_mode="full_plan",
            expected_output_name="deposit-target-3D.out",
        )

    assert not workspace.exists()


def test_rectangular_contract_allows_no_mlc_without_positions():
    segment = rectangular_segment(mlc_aperture_state="no_mlc", resolved_mlc_positions_mm=None)

    validate_rectangular_segment_contract(segment, machine_config())


def test_rectangular_contract_accepts_fully_open_mlc_positions():
    segment = rectangular_segment(mlc_aperture_state="fully_open_mlc")

    geometry = build_intermediate_geometry(segment, machine_config())

    assert geometry["mlc_aperture_state"] == "fully_open_mlc"
    assert geometry["mlc_positions_cm"]["bank_a"] == [-2.0, -1.5, -1.0, -0.5]


def test_rectangular_contract_allows_fully_open_mlc_without_positions():
    segment = rectangular_segment(mlc_aperture_state="fully_open_mlc", resolved_mlc_positions_mm=None)

    geometry = build_intermediate_geometry(segment, machine_config())

    assert geometry["mlc_aperture_state"] == "fully_open_mlc"
    assert geometry["mlc_positions_cm"] is None


def test_rectangular_contract_rejects_bank_length_mismatch():
    segment = rectangular_segment(
        resolved_mlc_positions_mm={"bank_a": [-20.0, -15.0], "bank_b": [20.0, 15.0]}
    )

    with pytest.raises(RectangularGeometryError, match="leaf_pair_count"):
        validate_rectangular_segment_contract(segment, machine_config())


def test_rectangular_contract_rejects_invalid_leaf_pair_ordering():
    segment = rectangular_segment(
        resolved_mlc_positions_mm={
            "bank_a": [-20.0, 15.0, -10.0, -5.0],
            "bank_b": [20.0, 15.0, 10.0, 5.0],
        }
    )

    with pytest.raises(RectangularGeometryError, match="bank_a\\[1\\]"):
        validate_rectangular_segment_contract(segment, machine_config())


def test_intermediate_geometry_converts_mm_to_cm_and_records_units():
    geometry = build_intermediate_geometry(rectangular_segment(), machine_config())

    assert geometry["geometry_mode"] == "rectangular_3dcrt"
    assert geometry["units"] == {"geometry": "cm", "angles": "deg", "density": "g/cm3"}
    assert geometry["jaw_positions_cm"] == {"x1": -4.0, "x2": 4.0, "y1": -5.0, "y2": 5.0}
    assert geometry["mlc_positions_cm"]["bank_b"] == [2.0, 1.5, 1.0, 0.5]
    assert geometry["source"]["position_cm"] == [0.0, 0.0, -100.0]
    assert geometry["y_diaphragm"]["upstream_z_cm"] == -46.1
    assert geometry["mlc_geometry"]["leaf_depth_cm"] == 6.0


def test_public_default_projects_aperture_to_approved_head_geometry():
    segment = rectangular_segment(
        resolved_mlc_positions_mm={
            "bank_a": [-20.0] * 80,
            "bank_b": [20.0] * 80,
        }
    )

    geometry = build_intermediate_geometry(
        segment,
        public_default_machine_config(),
    )

    assert geometry["jaw_positions_cm"] == {
        "x1": -4.0,
        "x2": 4.0,
        "y1": -5.0,
        "y2": 5.0,
    }
    assert geometry["y_diaphragm_positions_cm"] == pytest.approx({
        "x1": -4.0,
        "x2": 4.0,
        "y1": -2.855,
        "y2": 2.855,
    })
    assert geometry["mlc_positions_cm"]["bank_a"] == [-0.966] * 80
    assert geometry["mlc_positions_cm"]["bank_b"] == [0.966] * 80
    assert geometry["mlc_geometry"]["leaf_widths_cm"] == [0.2415] * 80
    assert geometry["mlc_geometry"]["leaf_depth_cm"] == 20.0
    assert geometry["source"]["width_x_cm"] == 0.3
    assert geometry["transport"]["photon_cutoff_mev"] == 0.01

    rendered = render_rectangular_phits_input(
        geometry,
        "deposit.out",
        voxel_counts=(2, 2, 2),
    )
    assert "2001 rpp -20.966 -0.966 -9.66 -9.4185 -60.07 -50.07" in rendered


@pytest.mark.parametrize(
    "segment",
    [
        rectangular_segment(segment_mu=0.0),
        rectangular_segment(segment_mu=None, segment_weight=0.0),
        rectangular_segment(segment_mu=None, segment_weight=float("inf")),
    ],
)
def test_intermediate_geometry_rejects_invalid_fluence_weight(segment):
    with pytest.raises(RectangularGeometryError):
        build_intermediate_geometry(segment, machine_config())


def test_intermediate_geometry_uses_relative_weight_when_mu_is_absent():
    segment = rectangular_segment(segment_mu=None, segment_weight=0.25)

    geometry = build_intermediate_geometry(segment, machine_config())

    assert geometry["fluence_weight"] == {"kind": "relative_weight", "value": 0.25}


def test_intermediate_geometry_does_not_mutate_inputs():
    segment = rectangular_segment()
    config = machine_config()
    original_segment = copy.deepcopy(segment)
    original_config = copy.deepcopy(config)

    build_intermediate_geometry(segment, config)

    assert segment == original_segment
    assert config == original_config


def test_intermediate_geometry_contains_no_phits_text_sections():
    geometry = build_intermediate_geometry(rectangular_segment(), machine_config())
    text = repr(geometry)

    assert "[ Surface ]" not in text
    assert "[ Cell ]" not in text
    assert "[ Material ]" not in text
    assert "[ T-Deposit ]" not in text


def test_intermediate_geometry_rejects_invalid_machine_config():
    config = machine_config(sad_mm=0.0)

    with pytest.raises(RectangularGeometryError, match="invalid machine config"):
        build_intermediate_geometry(rectangular_segment(), config)


def test_intermediate_geometry_differs_for_different_apertures():
    first = build_intermediate_geometry(rectangular_segment(), machine_config())
    second = build_intermediate_geometry(
        rectangular_segment(resolved_jaw_positions_mm={"x1": -30.0, "x2": 30.0, "y1": -50.0, "y2": 50.0}),
        machine_config(),
    )

    assert first["jaw_positions_cm"] != second["jaw_positions_cm"]


def test_rectangular_converter_is_standalone_from_private_modules():
    import dicomxphits.rectangular_geometry as module

    source = inspect.getsource(module)

    assert "extract" not in source
    assert "flatten" not in source
    assert "gen_phits" not in source
