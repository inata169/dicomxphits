from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

PUBLIC_SRC = Path(__file__).resolve().parents[1] / "src"
if str(PUBLIC_SRC) not in sys.path:
    sys.path.insert(0, str(PUBLIC_SRC))

from dicomxphits.rtplan_delivery import (
    aperture_close,
    classify_delivery_type,
    has_mlc,
    has_positive_cmw_intervals,
    has_rotating_gantry,
    lists_close,
    values_close,
)


TOLERANCES = {
    "cmw_tolerance": 1.0e-6,
    "angle_tolerance_deg": 0.01,
    "jaw_tolerance_mm": 0.01,
    "leaf_tolerance_mm": 0.01,
}


def beam(**values: object) -> SimpleNamespace:
    return SimpleNamespace(**values)


def state(**overrides: object) -> dict[str, object]:
    values: dict[str, object] = {
        "gantry_angle_deg": 0.0,
        "collimator_angle_deg": 0.0,
        "couch_angle_deg": 0.0,
        "gantry_rotation_direction": "NONE",
        "cmw": 0.0,
        "jaw_positions_mm": {"ASYMX": [-40.0, 40.0], "ASYMY": [-50.0, 50.0]},
        "leaf_pair_count": 0,
        "leaf_positions_mm": {"bank_1": [], "bank_2": []},
    }
    values.update(overrides)
    return values


@pytest.mark.parametrize(
    ("left", "right", "expected"),
    [
        (1.0, 1.0, True),
        (1.0, 1.005, True),
        (1.0, 1.02, False),
        (None, None, True),
        (None, 1.0, False),
    ],
)
def test_values_close(left: float | None, right: float | None, expected: bool) -> None:
    assert values_close(left, right, 0.01) is expected


@pytest.mark.parametrize(
    ("left", "right", "expected"),
    [
        ([1.0, 2.0], [1.0, 2.0], True),
        ([1.0, 2.0], [1.005, 1.995], True),
        ([1.0, 2.0], [1.02, 2.0], False),
        ([1.0], [1.0, 2.0], False),
    ],
)
def test_lists_close(left: list[float], right: list[float], expected: bool) -> None:
    assert lists_close(left, right, 0.01) is expected


def test_aperture_close_accepts_matching_angles_jaws_and_mlc() -> None:
    left = state(
        leaf_pair_count=2,
        leaf_positions_mm={"bank_1": [-1.0, -2.0], "bank_2": [1.0, 2.0]},
    )
    right = state(
        leaf_pair_count=2,
        leaf_positions_mm={"bank_1": [-1.005, -2.0], "bank_2": [1.0, 2.005]},
    )

    assert aperture_close(left, right, TOLERANCES)


@pytest.mark.parametrize(
    "right",
    [
        state(gantry_angle_deg=0.02),
        state(jaw_positions_mm={"ASYMX": [-40.0, 41.0], "ASYMY": [-50.0, 50.0]}),
        state(leaf_pair_count=2, leaf_positions_mm={"bank_1": [-1.0], "bank_2": [2.0]}),
    ],
)
def test_aperture_close_rejects_angle_jaw_and_mlc_mismatches(right: dict[str, object]) -> None:
    left = state(leaf_pair_count=2, leaf_positions_mm={"bank_1": [-1.0], "bank_2": [1.0]})

    assert not aperture_close(left, right, TOLERANCES)


def test_aperture_close_requires_matching_optional_jaw_and_mlc_keys() -> None:
    assert not aperture_close(
        state(jaw_positions_mm={"ASYMX": [-40.0, 40.0]}),
        state(jaw_positions_mm={}),
        TOLERANCES,
    )
    assert not aperture_close(
        state(leaf_positions_mm={"bank_1": [-1.0], "bank_2": [1.0]}),
        state(leaf_positions_mm={"bank_1": [], "bank_2": []}),
        TOLERANCES,
    )


def test_has_mlc_detects_positive_leaf_pair_count_only() -> None:
    assert not has_mlc([])
    assert not has_mlc([state(leaf_pair_count=0)])
    assert has_mlc([state(leaf_pair_count=0), state(leaf_pair_count=2)])


@pytest.mark.parametrize(
    ("states", "expected"),
    [
        ([], False),
        ([state(gantry_rotation_direction="NONE")], False),
        ([state(gantry_rotation_direction="")], False),
        ([state(gantry_rotation_direction="CW")], True),
        ([state(gantry_rotation_direction="CC")], True),
    ],
)
def test_has_rotating_gantry(states: list[dict[str, object]], expected: bool) -> None:
    assert has_rotating_gantry(states) is expected


def test_has_positive_cmw_intervals_uses_tolerance() -> None:
    assert not has_positive_cmw_intervals([], TOLERANCES["cmw_tolerance"])
    assert not has_positive_cmw_intervals([state(cmw=0.0), state(cmw=1.0e-7)], TOLERANCES["cmw_tolerance"])
    assert has_positive_cmw_intervals([state(cmw=0.0), state(cmw=0.5)], TOLERANCES["cmw_tolerance"])


def test_classify_delivery_type_handles_empty_and_unsupported_inputs() -> None:
    assert classify_delivery_type(beam(), [], TOLERANCES) == (
        "unknown",
        ["No ControlPointSequence entries are available"],
    )
    assert classify_delivery_type(beam(TreatmentDeliveryType="SETUP"), [state()], TOLERANCES) == (
        "unsupported",
        ["TreatmentDeliveryType is SETUP"],
    )


def test_classify_delivery_type_detects_vmat_and_dynamic_imrt() -> None:
    assert classify_delivery_type(beam(BeamType="STATIC"), [state(gantry_rotation_direction="CW")], TOLERANCES) == (
        "vmat",
        [],
    )
    assert classify_delivery_type(beam(BeamType="DYNAMIC"), [state(), state(cmw=1.0)], TOLERANCES) == (
        "dynamic_imrt",
        [],
    )


def test_classify_delivery_type_accepts_fixed_aperture_as_3dcrt() -> None:
    assert classify_delivery_type(beam(BeamType="STATIC"), [state(), state(cmw=1.0)], TOLERANCES) == (
        "3dcrt",
        [],
    )


def test_classify_delivery_type_detects_static_imrt_from_mlc_and_positive_cmw() -> None:
    states = [
        state(leaf_pair_count=2, leaf_positions_mm={"bank_1": [-1.0, -2.0], "bank_2": [1.0, 2.0]}, cmw=0.0),
        state(leaf_pair_count=2, leaf_positions_mm={"bank_1": [-1.5, -2.0], "bank_2": [1.0, 2.0]}, cmw=1.0),
    ]

    assert classify_delivery_type(beam(BeamType="STATIC"), states, TOLERANCES) == ("static_imrt", [])


def test_classify_delivery_type_warns_for_many_fixed_aperture_states() -> None:
    assert classify_delivery_type(beam(BeamType="STATIC"), [state(), state(cmw=0.5), state(cmw=1.0)], TOLERANCES) == (
        "3dcrt",
        ["Multiple control points share a fixed aperture; classified as 3dcrt"],
    )


def test_classify_delivery_type_reports_unclassifiable_sequence() -> None:
    states = [
        state(cmw=0.0),
        state(jaw_positions_mm={"ASYMX": [-30.0, 30.0], "ASYMY": [-50.0, 50.0]}, cmw=0.0),
    ]

    assert classify_delivery_type(beam(BeamType="STATIC"), states, TOLERANCES) == (
        "unknown",
        ["Unable to classify delivery type from available control point data"],
    )
