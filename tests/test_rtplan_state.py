from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

PUBLIC_SRC = Path(__file__).resolve().parents[1] / "src"
if str(PUBLIC_SRC) not in sys.path:
    sys.path.insert(0, str(PUBLIC_SRC))

from dicomxphits.rtplan_state import (
    apply_control_point,
    beam_number,
    carried_control_point_states,
    final_cmw,
    get_referenced_beam_metersets,
    initial_state,
)


def device_definition(dtype: str, pairs: object = 1, boundaries: object | None = None) -> SimpleNamespace:
    values = {"RTBeamLimitingDeviceType": dtype, "NumberOfLeafJawPairs": pairs}
    if boundaries is not None:
        values["LeafPositionBoundaries"] = boundaries
    return SimpleNamespace(**values)


def position_item(dtype: str | None, positions: object | None = None) -> SimpleNamespace:
    values: dict[str, object] = {}
    if dtype is not None:
        values["RTBeamLimitingDeviceType"] = dtype
    if positions is not None:
        values["LeafJawPositions"] = positions
    return SimpleNamespace(**values)


def control_point(index: object | None = None, **values: object) -> SimpleNamespace:
    if index is not None:
        values["ControlPointIndex"] = index
    return SimpleNamespace(**values)


def beam(*control_points: SimpleNamespace, devices: list[SimpleNamespace] | None = None, **values: object) -> SimpleNamespace:
    if control_points:
        values["ControlPointSequence"] = list(control_points)
    if devices is not None:
        values["BeamLimitingDeviceSequence"] = devices
    return SimpleNamespace(**values)


def referenced_beam(number: object | None = None, meterset: object | None = None) -> SimpleNamespace:
    values: dict[str, object] = {}
    if number is not None:
        values["ReferencedBeamNumber"] = number
    if meterset is not None:
        values["BeamMeterset"] = meterset
    return SimpleNamespace(**values)


def test_initial_state_has_public_manifest_defaults() -> None:
    state = initial_state()

    assert state["control_point_index"] is None
    assert state["cmw"] == 0.0
    assert state["jaw_positions_mm"] == {}
    assert state["leaf_positions_mm"] == {"bank_1": [], "bank_2": []}
    assert state["warnings"] == []


def test_carried_control_point_states_handles_missing_or_empty_sequence() -> None:
    assert carried_control_point_states(SimpleNamespace()) == []
    assert carried_control_point_states(SimpleNamespace(ControlPointSequence=[])) == []


def test_apply_control_point_extracts_angles_directions_cmw_and_jaws() -> None:
    state = apply_control_point(
        control_point(
            "3",
            GantryAngle="181.5",
            GantryRotationDirection="CW",
            BeamLimitingDeviceAngle="12.25",
            BeamLimitingDeviceRotationDirection="NONE",
            PatientSupportAngle=5,
            CumulativeMetersetWeight="0.25",
            BeamLimitingDevicePositionSequence=[
                position_item("ASYMX", ["-40", "40"]),
                position_item("ASYMY", [-50, 50]),
                position_item("X", [-30, 30]),
                position_item("Y", [-60, 60]),
            ],
        ),
        initial_state(),
        {},
        {},
    )

    assert state["control_point_index"] == 3
    assert state["gantry_angle_deg"] == 181.5
    assert state["gantry_rotation_direction"] == "CW"
    assert state["collimator_angle_deg"] == 12.25
    assert state["collimator_rotation_direction"] == "NONE"
    assert state["couch_angle_deg"] == 5.0
    assert state["cmw"] == 0.25
    assert state["jaw_positions_mm"] == {
        "ASYMX": [-40.0, 40.0],
        "ASYMY": [-50.0, 50.0],
        "X": [-30.0, 30.0],
        "Y": [-60.0, 60.0],
    }


def test_carried_control_point_states_carries_forward_values_and_resets_warnings() -> None:
    states = carried_control_point_states(
        beam(
            control_point(
                0,
                GantryAngle=10,
                BeamLimitingDeviceAngle=20,
                PatientSupportAngle=0,
                CumulativeMetersetWeight=0,
                BeamLimitingDevicePositionSequence=[
                    position_item("ASYMX", [-40, 40]),
                    position_item("UNSUPPORTED", [1, 2]),
                ],
            ),
            control_point(
                1,
                CumulativeMetersetWeight=1,
                BeamLimitingDevicePositionSequence=[position_item("ASYMY", [-50, 50])],
            ),
        )
    )

    assert states[0]["gantry_angle_deg"] == 10.0
    assert states[1]["gantry_angle_deg"] == 10.0
    assert states[1]["collimator_angle_deg"] == 20.0
    assert states[1]["jaw_positions_mm"] == {"ASYMX": [-40.0, 40.0], "ASYMY": [-50.0, 50.0]}
    assert states[0]["warnings"] == ["Unsupported beam limiting device type: UNSUPPORTED"]
    assert states[1]["warnings"] == []


def test_carried_control_point_states_gets_initial_index_fallback_when_missing() -> None:
    states = carried_control_point_states(beam(control_point(), control_point()))

    assert [state["control_point_index"] for state in states] == [0, 0]


def test_apply_control_point_extracts_mlc_positions_and_boundaries() -> None:
    state = apply_control_point(
        control_point(0, BeamLimitingDevicePositionSequence=[position_item("MLCX", [-10, -5, 10, 5])]),
        initial_state(),
        {"MLCX": 2},
        {"MLCX": [-20.0, 0.0, 20.0]},
    )

    assert state["mlc_type"] == "MLCX"
    assert state["leaf_pair_count"] == 2
    assert state["leaf_position_boundaries_mm"] == [-20.0, 0.0, 20.0]
    assert state["leaf_positions_mm"] == {"bank_1": [-10.0, -5.0], "bank_2": [10.0, 5.0]}
    assert state["warnings"] == []


def test_apply_control_point_warns_for_missing_device_type() -> None:
    state = apply_control_point(
        control_point(0, BeamLimitingDevicePositionSequence=[position_item(None, [-1, 1])]),
        initial_state(),
        {},
        {},
    )

    assert state["warnings"] == ["Beam limiting device without RTBeamLimitingDeviceType"]


def test_apply_control_point_warns_for_unsupported_device_type() -> None:
    state = apply_control_point(
        control_point(0, BeamLimitingDevicePositionSequence=[position_item("BLOCK", [-1, 1])]),
        initial_state(),
        {},
        {},
    )

    assert state["warnings"] == ["Unsupported beam limiting device type: BLOCK"]


def test_apply_control_point_warns_for_mismatched_mlc_leaf_count() -> None:
    state = apply_control_point(
        control_point(0, BeamLimitingDevicePositionSequence=[position_item("MLCX", [-10, -5, -2, 10, 5, 2])]),
        initial_state(),
        {"MLCX": 2},
        {},
    )

    assert state["leaf_pair_count"] == 2
    assert state["warnings"] == ["MLCX LeafJawPositions count 6 does not match 2 leaf pairs"]


def test_carried_control_point_states_gets_mlc_metadata_from_beam_devices() -> None:
    states = carried_control_point_states(
        beam(
            control_point(0, BeamLimitingDevicePositionSequence=[position_item("MLCX", [-10, -5, 10, 5])]),
            devices=[device_definition("MLCX", "2", [-20, 0, 20])],
        )
    )

    assert states[0]["leaf_pair_count"] == 2
    assert states[0]["leaf_position_boundaries_mm"] == [-20.0, 0.0, 20.0]


def test_get_referenced_beam_metersets_extracts_valid_values_only() -> None:
    ds = SimpleNamespace(
        FractionGroupSequence=[
            SimpleNamespace(
                ReferencedBeamSequence=[
                    referenced_beam("1", "100.5"),
                    referenced_beam("bad", "200"),
                    referenced_beam("3", "bad"),
                    referenced_beam(),
                ]
            )
        ]
    )

    assert get_referenced_beam_metersets(ds) == {1: 100.5}
    assert get_referenced_beam_metersets(SimpleNamespace()) == {}


def test_beam_number_and_final_cmw_extract_optional_numeric_values() -> None:
    assert beam_number(SimpleNamespace(BeamNumber="7")) == 7
    assert beam_number(SimpleNamespace(BeamNumber="bad")) is None
    assert beam_number(SimpleNamespace()) is None
    assert final_cmw(SimpleNamespace(FinalCumulativeMetersetWeight="1.25")) == 1.25
    assert final_cmw(SimpleNamespace(FinalCumulativeMetersetWeight="bad")) is None
    assert final_cmw(SimpleNamespace()) is None
