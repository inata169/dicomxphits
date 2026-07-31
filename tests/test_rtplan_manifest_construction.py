from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

PUBLIC_SRC = Path(__file__).resolve().parents[1] / "src"
if str(PUBLIC_SRC) not in sys.path:
    sys.path.insert(0, str(PUBLIC_SRC))

from dicomxphits.rtplan_interpolation import interpolated_state_at
from dicomxphits.rtplan_manifest_construction import build_manifest as build_manifest_direct
from dicomxphits.rtplan_manifest_construction import interval_segments_for_beam, segment_file_stem
from dicomxphits.rtplan_segments import build_manifest, deep_merge_sampling_policy, states_table


def item(dtype, positions):
    return SimpleNamespace(RTBeamLimitingDeviceType=dtype, LeafJawPositions=positions)


def control_point(index, cmw):
    return SimpleNamespace(
        ControlPointIndex=index,
        GantryAngle=10.0,
        BeamLimitingDeviceAngle=20.0,
        PatientSupportAngle=0.0,
        GantryRotationDirection="NONE",
        CumulativeMetersetWeight=cmw,
        BeamLimitingDevicePositionSequence=[
            item("ASYMX", [-40.0, 40.0]),
            item("ASYMY", [-50.0, 50.0]),
            item("MLCX", [-20.0, -15.0, -10.0, -5.0, 20.0, 15.0, 10.0, 5.0]),
        ],
    )


def dynamic_control_point(index, cmw, *, gantry_angle, gantry_direction="NONE", collimator_angle=20.0, collimator_direction="NONE"):
    cp = control_point(index, cmw)
    cp.GantryAngle = gantry_angle
    cp.GantryRotationDirection = gantry_direction
    cp.BeamLimitingDeviceAngle = collimator_angle
    cp.BeamLimitingDeviceRotationDirection = collimator_direction
    return cp


def beam(*control_points, beam_type="STATIC"):
    return SimpleNamespace(
        BeamNumber=1,
        BeamName="Manifest construction test beam",
        BeamType=beam_type,
        TreatmentDeliveryType="TREATMENT",
        FinalCumulativeMetersetWeight=1.0,
        BeamLimitingDeviceSequence=[
            SimpleNamespace(RTBeamLimitingDeviceType="ASYMX", NumberOfLeafJawPairs=1),
            SimpleNamespace(RTBeamLimitingDeviceType="ASYMY", NumberOfLeafJawPairs=1),
            SimpleNamespace(
                RTBeamLimitingDeviceType="MLCX",
                NumberOfLeafJawPairs=4,
                LeafPositionBoundaries=[-10.0, -5.0, 0.0, 5.0, 10.0],
            ),
        ],
        ControlPointSequence=list(control_points),
    )


def rtplan(test_beam):
    return SimpleNamespace(
        SOPInstanceUID="1.2.826.0.1.3680043.10.54321.397",
        RTPlanLabel="PUBLIC_MANIFEST_TEST",
        BeamSequence=[test_beam],
        FractionGroupSequence=[
            SimpleNamespace(
                ReferencedBeamSequence=[
                    SimpleNamespace(ReferencedBeamNumber=1, BeamMeterset=100.0),
                ]
            )
        ],
    )


def test_build_manifest_import_compatibility_preserves_structure():
    ds = rtplan(beam(control_point(0, 0.0), control_point(1, 1.0)))
    sampling_policy = deep_merge_sampling_policy({"dynamic_imrt": {"interval_subdivision": 3}})

    via_segments = build_manifest(
        ds,
        case_id="manifest_test",
        workflow_mode="full_plan",
        include_beams=None,
        dose_normalization_mu=None,
        output_name="deposit-target-3D.out",
        sampling_policy=sampling_policy,
        sampling_config_path="rtplan_sampling.yaml",
    )
    via_helper = build_manifest_direct(
        ds,
        case_id="manifest_test",
        workflow_mode="full_plan",
        include_beams=None,
        dose_normalization_mu=None,
        output_name="deposit-target-3D.out",
        sampling_policy=sampling_policy,
        sampling_config_path="rtplan_sampling.yaml",
        states_table_builder=states_table,
    )

    assert via_segments == via_helper
    assert via_segments[0]["segments"][0]["segment_id"] == "seg_b0001_s0000"
    assert via_segments[0]["segments"][0]["expected_output_path"] == (
        "phits_outputs/beam_0001_segment_0000/deposit-target-3D.out"
    )


def test_zero_cmw_interval_metadata_is_preserved():
    test_beam = beam(control_point(0, 0.0), control_point(1, 0.0), beam_type="DYNAMIC")
    states = [{"control_point_index": 0, "cmw": 0.0}, {"control_point_index": 1, "cmw": 0.0}]

    segments = interval_segments_for_beam(
        test_beam,
        beam_mu=100.0,
        delivery_type="dynamic_imrt",
        states=states,
        final_cmw_value=1.0,
        output_name="deposit-target-3D.out",
        tolerances={"cmw_tolerance": 1.0e-6, "angle_tolerance_deg": 0.01, "jaw_tolerance_mm": 0.01, "leaf_tolerance_mm": 0.01},
        sampling_policy={"dynamic_imrt": {"interval_subdivision": 2}},
        sampling_config_path="rtplan_sampling.yaml",
    )

    assert len(segments) == 1
    assert segments[0]["skip_reason"] == "zero CMW delta"
    assert segments[0]["source_interval_index"] == 0
    assert segments[0]["subinterval_count"] == 2
    assert segments[0]["sampling_config_path"] == "rtplan_sampling.yaml"


def test_descriptor_manifest_dynamic_interval_compatibility_and_rotation_direction():
    first = dynamic_control_point(0, 0.0, gantry_angle=10.0, gantry_direction="NONE", collimator_angle=350.0, collimator_direction="CC")
    second = dynamic_control_point(1, 1.0, gantry_angle=10.0, gantry_direction="NONE", collimator_angle=10.0, collimator_direction="CC")
    ds = rtplan(beam(first, second, beam_type="DYNAMIC"))

    manifest, beam_rows, cp_rows = build_manifest(
        ds,
        case_id="dynamic_descriptor_test",
        workflow_mode="full_plan",
        include_beams=None,
        dose_normalization_mu=None,
        output_name="deposit-target-3D.out",
        sampling_policy=deep_merge_sampling_policy({"dynamic_imrt": {"interval_subdivision": 2}}),
        sampling_config_path="rtplan_sampling.yaml",
    )

    active_segments = [segment for segment in manifest["segments"] if not segment.get("skip_reason")]
    assert len(cp_rows) == 2
    assert cp_rows[0]["collimator_angle_deg"] == 350.0
    assert cp_rows[1]["collimator_angle_deg"] == 10.0
    assert len(active_segments) == 2
    assert beam_rows[0]["delivery_type"] == "dynamic_imrt"
    assert beam_rows[0]["segment_count"] == 2
    assert active_segments[0]["source_interval_index"] == 0
    assert active_segments[0]["subinterval_index"] == 0
    assert active_segments[0]["subinterval_count"] == 2
    assert active_segments[0]["cmw_role"] == "interval_weight_coordinate"
    assert active_segments[0]["gantry_angle_deg"] == 10.0
    assert active_segments[0]["collimator_angle_deg"] == 265.0
    assert active_segments[1]["gantry_angle_deg"] == 10.0
    assert active_segments[1]["collimator_angle_deg"] == 95.0
    assert active_segments[0]["expected_output_path"] == "phits_outputs/beam_0001_segment_0000/deposit-target-3D.out"
    assert active_segments[1]["expected_output_path"] == "phits_outputs/beam_0001_segment_0001/deposit-target-3D.out"


def test_descriptor_manifest_propagates_interpolation_warnings_without_output_shape_expansion():
    first = dynamic_control_point(0, 0.0, gantry_angle=10.0, gantry_direction="")
    second = dynamic_control_point(1, 1.0, gantry_angle=10.005, gantry_direction="")
    expected_state, expected_warnings = interpolated_state_at(
        {
            "warnings": [],
            "gantry_angle_deg": first.GantryAngle,
            "gantry_rotation_direction": first.GantryRotationDirection,
            "collimator_angle_deg": first.BeamLimitingDeviceAngle,
            "collimator_rotation_direction": first.BeamLimitingDeviceRotationDirection,
            "couch_angle_deg": first.PatientSupportAngle,
            "cmw": first.CumulativeMetersetWeight,
            "jaw_positions_mm": {},
            "leaf_positions_mm": {"bank_1": [], "bank_2": []},
            "leaf_pair_count": 0,
            "leaf_position_boundaries_mm": [],
        },
        {
            "warnings": [],
            "gantry_angle_deg": second.GantryAngle,
            "gantry_rotation_direction": second.GantryRotationDirection,
            "collimator_angle_deg": second.BeamLimitingDeviceAngle,
            "collimator_rotation_direction": second.BeamLimitingDeviceRotationDirection,
            "couch_angle_deg": second.PatientSupportAngle,
            "cmw": second.CumulativeMetersetWeight,
            "jaw_positions_mm": {},
            "leaf_positions_mm": {"bank_1": [], "bank_2": []},
            "leaf_pair_count": 0,
            "leaf_position_boundaries_mm": [],
        },
        0.5,
        {"cmw_tolerance": 1.0e-6, "angle_tolerance_deg": 0.01, "jaw_tolerance_mm": 0.01, "leaf_tolerance_mm": 0.01},
    )
    ds = rtplan(beam(first, second, beam_type="DYNAMIC"))

    manifest, beam_rows, _cp_rows = build_manifest(
        ds,
        case_id="warning_descriptor_test",
        workflow_mode="full_plan",
        include_beams=None,
        dose_normalization_mu=None,
        output_name="deposit-target-3D.out",
        sampling_policy=deep_merge_sampling_policy({"dynamic_imrt": {"interval_subdivision": 1}}),
        sampling_config_path=None,
    )

    segment = manifest["segments"][0]
    assert expected_warnings == ["Gantry rotation direction missing or invalid; fixed gantry angle assumed"]
    assert segment["warnings"] == expected_warnings
    assert segment["gantry_angle_deg"] == expected_state["gantry_angle_deg"]
    assert "collimator_rotation_direction" not in segment
    assert beam_rows[0]["warnings"] == []


def test_descriptor_manifest_keeps_unsupported_delivery_as_skipped_segment():
    setup_beam = beam(control_point(0, 0.0), beam_type="STATIC")
    setup_beam.TreatmentDeliveryType = "SETUP"
    ds = rtplan(setup_beam)

    manifest, beam_rows, _cp_rows = build_manifest(
        ds,
        case_id="unsupported_descriptor_test",
        workflow_mode="full_plan",
        include_beams=None,
        dose_normalization_mu=None,
        output_name="deposit-target-3D.out",
        sampling_policy=deep_merge_sampling_policy(),
    )

    assert beam_rows[0]["delivery_type"] == "unsupported"
    assert beam_rows[0]["segment_count"] == 0
    assert beam_rows[0]["skipped_segment_count"] == 1
    assert beam_rows[0]["warnings"] == ["TreatmentDeliveryType is SETUP"]
    assert manifest["segments"][0]["skip_reason"] == "delivery_type unsupported is not generation-capable in this workflow"
    assert manifest["segments"][0]["warnings"] == ["TreatmentDeliveryType is SETUP"]


def test_segment_file_stem_is_deterministic():
    assert segment_file_stem(1, 0) == "beam_0001_segment_0000"
    assert segment_file_stem(None, 2) == "beam_unknown_segment_0002"


def test_rtplan_segments_direct_script_help_still_works():
    script = PUBLIC_SRC / "dicomxphits" / "rtplan_segments.py"

    result = subprocess.run([sys.executable, str(script), "--help"], capture_output=True, text=True)

    assert result.returncode == 0
    assert "--rtplan" in result.stdout
