from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

PUBLIC_SRC = Path(__file__).resolve().parents[1] / "src"
if str(PUBLIC_SRC) not in sys.path:
    sys.path.insert(0, str(PUBLIC_SRC))

from dicomxphits.rtplan_core_mapping import describe_beam, describe_rtplan_beams, descriptor_states
from dicomxphits.rtplan_interpolation import interpolated_state_at


TOLERANCES = {
    "cmw_tolerance": 1.0e-6,
    "angle_tolerance_deg": 0.01,
    "jaw_tolerance_mm": 0.01,
    "leaf_tolerance_mm": 0.01,
}


def item(dtype, positions):
    return SimpleNamespace(RTBeamLimitingDeviceType=dtype, LeafJawPositions=positions)


def control_point(index, cmw, *, gantry_direction="NONE", leaf_offset=0.0):
    return SimpleNamespace(
        ControlPointIndex=index,
        GantryAngle=10.0 + index,
        BeamLimitingDeviceAngle=20.0,
        PatientSupportAngle=0.0,
        GantryRotationDirection=gantry_direction,
        CumulativeMetersetWeight=cmw,
        BeamLimitingDevicePositionSequence=[
            item("ASYMX", [-40.0, 40.0]),
            item("ASYMY", [-50.0, 50.0]),
            item("MLCX", [-20.0 + leaf_offset, -15.0, 20.0 + leaf_offset, 15.0]),
        ],
    )


def beam(*control_points, beam_number=1, beam_type="STATIC", treatment_delivery_type="TREATMENT"):
    return SimpleNamespace(
        BeamNumber=beam_number,
        BeamName="Synthetic core mapping beam",
        BeamType=beam_type,
        TreatmentDeliveryType=treatment_delivery_type,
        FinalCumulativeMetersetWeight=1.0,
        BeamLimitingDeviceSequence=[
            SimpleNamespace(RTBeamLimitingDeviceType="ASYMX", NumberOfLeafJawPairs=1),
            SimpleNamespace(RTBeamLimitingDeviceType="ASYMY", NumberOfLeafJawPairs=1),
            SimpleNamespace(
                RTBeamLimitingDeviceType="MLCX",
                NumberOfLeafJawPairs=2,
                LeafPositionBoundaries=[-10.0, 0.0, 10.0],
            ),
        ],
        ControlPointSequence=list(control_points),
    )


def rtplan(*beams):
    return SimpleNamespace(BeamSequence=list(beams))


def test_describe_beam_normalizes_control_point_aperture_descriptor():
    descriptor = describe_beam(
        beam(control_point(0, 0.0), control_point(1, 1.0)),
        beam_meterset_mu=120.0,
        tolerances=TOLERANCES,
    )

    assert descriptor.beam_number == 1
    assert descriptor.beam_name == "Synthetic core mapping beam"
    assert descriptor.beam_meterset_mu == 120.0
    assert descriptor.final_cumulative_meterset_weight == 1.0
    assert descriptor.delivery_type == "static_imrt"
    assert descriptor.unsupported_reason is None
    assert len(descriptor.control_points) == 2
    assert descriptor.control_points[0].jaw_positions_mm["ASYMX"] == [-40.0, 40.0]
    assert descriptor.control_points[0].collimator_rotation_direction is None
    assert descriptor.control_points[0].leaf_pair_count == 2
    assert descriptor.control_points[0].leaf_positions_mm == {
        "bank_1": [-20.0, -15.0],
        "bank_2": [20.0, 15.0],
    }


def test_descriptor_states_round_trip_existing_manifest_state_shape():
    descriptor = describe_beam(
        beam(control_point(0, 0.0), control_point(1, 1.0, leaf_offset=5.0)),
        beam_meterset_mu=100.0,
        tolerances=TOLERANCES,
    )

    states = descriptor_states(descriptor)

    assert states[1]["control_point_index"] == 1
    assert states[1]["cmw"] == 1.0
    assert "collimator_rotation_direction" in states[1]
    assert states[1]["leaf_positions_mm"]["bank_1"] == [-15.0, -15.0]
    assert states[1]["leaf_position_boundaries_mm"] == [-10.0, 0.0, 10.0]


def test_describe_rtplan_beams_preserves_order_and_classifies_vmat():
    first = beam(control_point(0, 0.0), control_point(1, 1.0), beam_number=1)
    second = beam(
        control_point(0, 0.0, gantry_direction="CW"),
        control_point(1, 1.0, gantry_direction="CW"),
        beam_number=2,
        beam_type="DYNAMIC",
    )

    descriptors = describe_rtplan_beams(
        rtplan(first, second),
        beam_metersets={1: 100.0, 2: 200.0},
        tolerances=TOLERANCES,
    )

    assert [descriptor.beam_number for descriptor in descriptors] == [1, 2]
    assert [descriptor.beam_meterset_mu for descriptor in descriptors] == [100.0, 200.0]
    assert descriptors[1].delivery_type == "vmat"


def test_unsupported_descriptor_carries_reason_without_manifest_schema_change():
    descriptor = describe_beam(
        beam(control_point(0, 0.0), treatment_delivery_type="SETUP"),
        beam_meterset_mu=0.0,
        tolerances=TOLERANCES,
    )

    assert descriptor.delivery_type == "unsupported"
    assert descriptor.unsupported_reason == "TreatmentDeliveryType is SETUP"


def test_descriptor_states_preserve_collimator_rotation_direction_for_interpolation():
    start = control_point(0, 0.0)
    start.BeamLimitingDeviceAngle = 350.0
    start.BeamLimitingDeviceRotationDirection = "CC"
    end = control_point(1, 1.0)
    end.GantryAngle = start.GantryAngle
    end.BeamLimitingDeviceAngle = 10.0
    end.BeamLimitingDeviceRotationDirection = "CC"
    descriptor = describe_beam(
        beam(start, end, beam_type="DYNAMIC"),
        beam_meterset_mu=100.0,
        tolerances=TOLERANCES,
    )

    states = descriptor_states(descriptor)
    interpolated, warnings = interpolated_state_at(states[0], states[1], 0.5, TOLERANCES)

    assert warnings == []
    assert descriptor.control_points[0].collimator_rotation_direction == "CC"
    assert states[0]["collimator_rotation_direction"] == "CC"
    assert states[1]["collimator_rotation_direction"] == "CC"
    assert interpolated["collimator_angle_deg"] == pytest.approx(180.0)
