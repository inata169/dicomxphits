from __future__ import annotations

import sys
from pathlib import Path

import pytest

PUBLIC_SRC = Path(__file__).resolve().parents[1] / "src"
if str(PUBLIC_SRC) not in sys.path:
    sys.path.insert(0, str(PUBLIC_SRC))

from dicomxphits.public_aperture_guard import require_v1_effective_apertures
from dicomxphits.rtplan_rectangular_contract import (
    rectangular_jaw_positions,
    rectangular_mlc_aperture_state,
    rectangular_mlc_positions,
    rectangular_mlc_x_extent,
    rectangular_segment_id,
)


def mlc_state(**overrides):
    state = {
        "jaw_positions_mm": {"ASYMY": [-50.0, 50.0]},
        "leaf_pair_count": 4,
        "leaf_position_boundaries_mm": [-100.0, -50.0, 0.0, 50.0, 100.0],
        "leaf_positions_mm": {
            "bank_1": [-90.0, -20.0, -15.0, -80.0],
            "bank_2": [90.0, 20.0, 15.0, 80.0],
        },
        "mlc_type": "MLCX",
    }
    state.update(overrides)
    return state


def test_rectangular_segment_id_is_deterministic_and_public_safe():
    assert rectangular_segment_id(1, 0) == "seg_b0001_s0000"
    assert rectangular_segment_id(23, 7) == "seg_b0023_s0007"
    assert rectangular_segment_id(None, 3) == "seg_bunknown_s0003"


def test_rectangular_jaw_positions_prefers_explicit_x_jaws():
    state = mlc_state(jaw_positions_mm={"ASYMX": [-40.0, 40.0], "ASYMY": [-50.0, 50.0]})

    assert rectangular_jaw_positions(state) == {"x1": -40.0, "x2": 40.0, "y1": -50.0, "y2": 50.0}


def test_rectangular_jaw_positions_resolves_missing_x_jaws_from_active_leaf_pairs():
    state = mlc_state()

    assert rectangular_jaw_positions(state) == {"x1": -20.0, "x2": 20.0, "y1": -50.0, "y2": 50.0}
    assert rectangular_mlc_x_extent(state, [-50.0, 50.0]) == [-20.0, 20.0]


def test_rectangular_jaw_positions_leaves_missing_x_jaws_unresolved_without_leaf_boundaries():
    state = mlc_state(leaf_position_boundaries_mm=[])

    assert rectangular_jaw_positions(state) == {"x1": None, "x2": None, "y1": -50.0, "y2": 50.0}
    assert rectangular_mlc_x_extent(state, [-50.0, 50.0]) == []


def exact_mlc_state_without_x_jaw(**overrides):
    state = {
        "control_point_index": 0,
        "public_aperture_resolution_issues": [],
        "beam_device_definition_counts": {"ASYMY": 1, "MLCX": 1},
        "jaw_positions_decimal_mm": {"ASYMY": ["-50.000", "50.000"]},
        "mlc_positions_decimal_mm": {
            "MLCX": {
                "bank_1": ["-90.000", "-20.000", "-15.000", "-80.000"],
                "bank_2": ["90.000", "20.000", "15.000", "80.000"],
            }
        },
        "mlc_pair_counts": {"MLCX": 4},
        "mlc_leaf_boundaries_decimal_mm": {
            "MLCX": ["-100.000", "-50.000", "0.000", "50.000", "100.000"]
        },
    }
    state.update(overrides)
    return state


def test_public_aperture_guard_uses_mlcx_when_x_jaw_is_not_declared():
    decision = require_v1_effective_apertures([(1, [exact_mlc_state_without_x_jaw()])])

    assert decision["control_points"] == [
        {
            "beam_number": 1,
            "control_point_index": 0,
            "x_min_mm": "-20.000",
            "x_max_mm": "20.000",
            "y_min_mm": "-50.000",
            "y_max_mm": "50.000",
        }
    ]


def test_public_aperture_guard_rejects_visible_mlcx_overrun_without_x_jaw():
    state = exact_mlc_state_without_x_jaw()
    state["mlc_positions_decimal_mm"]["MLCX"]["bank_1"][1] = "-100.001"

    with pytest.raises(ValueError, match=r"X minimum -100\.001 mm is below -100\.000 mm"):
        require_v1_effective_apertures([(1, [state])])


def test_rectangular_mlc_positions_maps_internal_banks_to_public_contract_names():
    state = mlc_state()

    assert rectangular_mlc_positions(state) == {
        "bank_a": [-90.0, -20.0, -15.0, -80.0],
        "bank_b": [90.0, 20.0, 15.0, 80.0],
    }


def test_rectangular_mlc_aperture_state_preserves_explicit_markers():
    assert rectangular_mlc_aperture_state({"mlc_aperture_state": "no_mlc", "mlc_type": "MLCX"}) == "no_mlc"
    assert rectangular_mlc_aperture_state({"mlc_aperture_state": "fully_open_mlc"}) == "fully_open_mlc"
    assert rectangular_mlc_aperture_state({"mlc_aperture_state": "present"}) == "present"


def test_rectangular_mlc_aperture_state_defaults_from_mlc_type():
    assert rectangular_mlc_aperture_state({"mlc_type": "MLCX"}) == "present"
    assert rectangular_mlc_aperture_state({}) == "no_mlc"
