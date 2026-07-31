from __future__ import annotations

import copy
import sys
from pathlib import Path

import pytest

PUBLIC_SRC = Path(__file__).resolve().parents[1] / "src"
if str(PUBLIC_SRC) not in sys.path:
    sys.path.insert(0, str(PUBLIC_SRC))

from dicomxphits.rtplan_interpolation import (
    angle_delta_deg,
    direction_text,
    interpolate_angle_deg,
    interpolate_list,
    interpolate_number,
    interpolated_state_at,
    validate_gantry_direction_for_interval,
)


TOLERANCES = {
    "cmw_tolerance": 1.0e-6,
    "angle_tolerance_deg": 0.01,
    "jaw_tolerance_mm": 0.01,
    "leaf_tolerance_mm": 0.01,
}


def state(**overrides: object) -> dict[str, object]:
    values: dict[str, object] = {
        "warnings": ["carried warning"],
        "gantry_angle_deg": 0.0,
        "collimator_angle_deg": 10.0,
        "couch_angle_deg": 20.0,
        "gantry_rotation_direction": "NONE",
        "collimator_rotation_direction": "NONE",
        "cmw": 0.0,
        "jaw_positions_mm": {"ASYMX": [-40.0, 40.0], "ASYMY": [-50.0, 50.0]},
        "mlc_type": "MLCX",
        "leaf_pair_count": 2,
        "leaf_position_boundaries_mm": [-10.0, 0.0, 10.0],
        "leaf_positions_mm": {"bank_1": [-1.0, -2.0], "bank_2": [1.0, 2.0]},
    }
    values.update(overrides)
    return values


@pytest.mark.parametrize(
    ("start", "end", "direction", "expected"),
    [
        (350.0, 10.0, None, 20.0),
        (10.0, 350.0, None, -20.0),
        (350.0, 10.0, "CW", 20.0),
        (350.0, 10.0, "CC", -340.0),
        (10.0, 350.0, "CW", 340.0),
        (10.0, 350.0, "CC", -20.0),
    ],
)
def test_angle_delta_deg_handles_direction_and_wraparound(
    start: float,
    end: float,
    direction: str | None,
    expected: float,
) -> None:
    assert angle_delta_deg(start, end, direction) == pytest.approx(expected)


def test_interpolate_angle_deg_handles_none_and_wraparound() -> None:
    assert interpolate_angle_deg(None, 20.0, t=0.5) == 20.0
    assert interpolate_angle_deg(10.0, None, t=0.5) == 10.0
    assert interpolate_angle_deg(350.0, 10.0, None, 0.5) == pytest.approx(0.0)
    assert interpolate_angle_deg(350.0, 10.0, "CC", 0.5) == pytest.approx(180.0)


def test_interpolate_number_handles_none_and_fraction() -> None:
    assert interpolate_number(None, 3.0, 0.25) == 3.0
    assert interpolate_number(2.0, None, 0.25) == 2.0
    assert interpolate_number(2.0, 6.0, 0.25) == pytest.approx(3.0)


def test_interpolate_list_handles_fraction_and_mismatched_lengths() -> None:
    assert interpolate_list([0.0, 10.0], [10.0, 30.0], 0.25) == pytest.approx([2.5, 15.0])
    assert interpolate_list([1.0, 2.0], [10.0], 0.5) == [1.0, 2.0]


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, ""),
        (" cw ", "CW"),
        ("None", "NONE"),
    ],
)
def test_direction_text_normalizes_values(value: object, expected: str) -> None:
    assert direction_text(value) == expected


def test_validate_gantry_direction_accepts_fixed_angle_none_direction() -> None:
    direction, warnings = validate_gantry_direction_for_interval(
        state(gantry_angle_deg=10.0, gantry_rotation_direction="NONE"),
        state(gantry_angle_deg=10.005, gantry_rotation_direction="NONE"),
        TOLERANCES,
    )

    assert direction == "NONE"
    assert warnings == []


def test_validate_gantry_direction_warns_for_missing_fixed_angle_direction() -> None:
    direction, warnings = validate_gantry_direction_for_interval(
        state(gantry_angle_deg=10.0, gantry_rotation_direction=""),
        state(gantry_angle_deg=10.005, gantry_rotation_direction=""),
        TOLERANCES,
    )

    assert direction is None
    assert warnings == ["Gantry rotation direction missing or invalid; fixed gantry angle assumed"]


def test_validate_gantry_direction_rejects_none_for_nonzero_change() -> None:
    with pytest.raises(ValueError, match="direction NONE"):
        validate_gantry_direction_for_interval(
            state(gantry_angle_deg=10.0, gantry_rotation_direction="NONE"),
            state(gantry_angle_deg=12.0, gantry_rotation_direction="NONE"),
            TOLERANCES,
        )


def test_validate_gantry_direction_rejects_missing_or_invalid_nonzero_change() -> None:
    with pytest.raises(ValueError, match="missing or invalid"):
        validate_gantry_direction_for_interval(
            state(gantry_angle_deg=10.0, gantry_rotation_direction=""),
            state(gantry_angle_deg=12.0, gantry_rotation_direction="BAD"),
            TOLERANCES,
        )


def test_validate_gantry_direction_rejects_inconsistent_nonzero_direction() -> None:
    with pytest.raises(ValueError, match="Inconsistent gantry rotation direction"):
        validate_gantry_direction_for_interval(
            state(gantry_angle_deg=10.0, gantry_rotation_direction="CW"),
            state(gantry_angle_deg=12.0, gantry_rotation_direction="CC"),
            TOLERANCES,
        )


def test_validate_gantry_direction_warns_for_inconsistent_fixed_direction() -> None:
    direction, warnings = validate_gantry_direction_for_interval(
        state(gantry_angle_deg=10.0, gantry_rotation_direction="CW"),
        state(gantry_angle_deg=10.005, gantry_rotation_direction="CC"),
        TOLERANCES,
    )

    assert direction == "CW"
    assert warnings == ["Gantry rotation direction changed on fixed-angle interval; fixed gantry angle assumed"]


def test_interpolated_state_at_interpolates_angles_cmw_jaws_and_mlc() -> None:
    start = state(gantry_angle_deg=350.0, gantry_rotation_direction="CW", cmw=0.0)
    end = state(
        gantry_angle_deg=10.0,
        gantry_rotation_direction="CW",
        collimator_angle_deg=30.0,
        couch_angle_deg=40.0,
        cmw=1.0,
        jaw_positions_mm={"ASYMX": [-20.0, 20.0], "ASYMY": [-30.0, 30.0]},
        leaf_positions_mm={"bank_1": [-3.0, -4.0], "bank_2": [3.0, 4.0]},
    )

    interpolated, warnings = interpolated_state_at(start, end, 0.5, TOLERANCES)

    assert warnings == []
    assert interpolated["warnings"] == ["carried warning"]
    assert interpolated["gantry_angle_deg"] == pytest.approx(0.0)
    assert interpolated["collimator_angle_deg"] == pytest.approx(20.0)
    assert interpolated["couch_angle_deg"] == pytest.approx(30.0)
    assert interpolated["cmw"] == pytest.approx(0.5)
    assert interpolated["jaw_positions_mm"]["ASYMX"] == pytest.approx([-30.0, 30.0])
    assert interpolated["jaw_positions_mm"]["ASYMY"] == pytest.approx([-40.0, 40.0])
    assert interpolated["mlc_type"] == "MLCX"
    assert interpolated["leaf_pair_count"] == 2
    assert interpolated["leaf_position_boundaries_mm"] == [-10.0, 0.0, 10.0]
    assert interpolated["leaf_positions_mm"]["bank_1"] == pytest.approx([-2.0, -3.0])
    assert interpolated["leaf_positions_mm"]["bank_2"] == pytest.approx([2.0, 3.0])


def test_interpolated_state_at_appends_angle_warnings_and_preserves_inputs() -> None:
    start = state(gantry_angle_deg=10.0, gantry_rotation_direction="")
    end = state(gantry_angle_deg=10.005, gantry_rotation_direction="")
    start_before = copy.deepcopy(start)
    end_before = copy.deepcopy(end)

    interpolated, warnings = interpolated_state_at(start, end, 0.5, TOLERANCES)

    assert warnings == ["Gantry rotation direction missing or invalid; fixed gantry angle assumed"]
    assert interpolated["warnings"] == [
        "carried warning",
        "Gantry rotation direction missing or invalid; fixed gantry angle assumed",
    ]
    assert start == start_before
    assert end == end_before
