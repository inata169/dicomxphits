from __future__ import annotations

from copy import deepcopy
from typing import Any

from dicomxphits.rtplan_helpers import as_float


def angle_delta_deg(start: float, end: float, direction: str | None = None) -> float:
    direction_text = str(direction or "").upper()
    start_norm = float(start) % 360.0
    end_norm = float(end) % 360.0
    # IEC gantry angles increase in the clockwise direction. DICOM RT
    # RotationDirection values are interpreted relative to that convention.
    if direction_text == "CW":
        return (end_norm - start_norm) % 360.0
    if direction_text == "CC":
        return -((start_norm - end_norm) % 360.0)
    delta = (end_norm - start_norm + 180.0) % 360.0 - 180.0
    return delta


def interpolate_angle_deg(
    start: float | None,
    end: float | None,
    direction: str | None = None,
    t: float = 0.5,
) -> float | None:
    if start is None or end is None:
        return start if end is None else end
    return (float(start) + angle_delta_deg(float(start), float(end), direction) * float(t)) % 360.0


def interpolate_number(start: float | None, end: float | None, t: float = 0.5) -> float | None:
    if start is None or end is None:
        return start if end is None else end
    return float(start) + (float(end) - float(start)) * float(t)


def interpolate_list(start: list[float], end: list[float], t: float = 0.5) -> list[float]:
    if len(start) != len(end):
        return list(start)
    return [float(a) + (float(b) - float(a)) * float(t) for a, b in zip(start, end)]


def direction_text(value: Any) -> str:
    return str(value or "").strip().upper()


def validate_gantry_direction_for_interval(
    start: dict[str, Any],
    end: dict[str, Any],
    tolerances: dict[str, float],
) -> tuple[str | None, list[str]]:
    start_angle = as_float(start.get("gantry_angle_deg"), None)
    end_angle = as_float(end.get("gantry_angle_deg"), None)
    if start_angle is None or end_angle is None:
        return None, []
    start_dir = direction_text(start.get("gantry_rotation_direction"))
    end_dir = direction_text(end.get("gantry_rotation_direction"))
    direction = start_dir or end_dir
    shortest_delta = abs(angle_delta_deg(start_angle, end_angle, None))
    if direction == "NONE":
        if shortest_delta > tolerances["angle_tolerance_deg"]:
            raise ValueError(f"Gantry rotation direction NONE but angle change is {shortest_delta:.6g} deg")
        return "NONE", []
    if direction not in {"CW", "CC"}:
        if shortest_delta <= tolerances["angle_tolerance_deg"]:
            return None, ["Gantry rotation direction missing or invalid; fixed gantry angle assumed"]
        raise ValueError("Gantry rotation direction missing or invalid for nonzero angle interval")
    if start_dir and end_dir and start_dir != end_dir:
        if shortest_delta <= tolerances["angle_tolerance_deg"]:
            return direction, ["Gantry rotation direction changed on fixed-angle interval; fixed gantry angle assumed"]
        raise ValueError(f"Inconsistent gantry rotation direction: {start_dir} -> {end_dir}")
    return direction, []


def interpolated_state_at(
    start: dict[str, Any],
    end: dict[str, Any],
    t: float,
    tolerances: dict[str, float],
) -> tuple[dict[str, Any], list[str]]:
    gantry_direction, angle_warnings = validate_gantry_direction_for_interval(start, end, tolerances)
    collimator_direction = start.get("collimator_rotation_direction") or end.get("collimator_rotation_direction")
    state = deepcopy(start)
    state["warnings"] = list(start.get("warnings", []))
    state["gantry_angle_deg"] = interpolate_angle_deg(
        as_float(start.get("gantry_angle_deg"), None),
        as_float(end.get("gantry_angle_deg"), None),
        gantry_direction,
        t,
    )
    state["collimator_angle_deg"] = interpolate_angle_deg(
        as_float(start.get("collimator_angle_deg"), None),
        as_float(end.get("collimator_angle_deg"), None),
        collimator_direction,
        t,
    )
    state["couch_angle_deg"] = interpolate_angle_deg(
        as_float(start.get("couch_angle_deg"), None),
        as_float(end.get("couch_angle_deg"), None),
        None,
        t,
    )
    state["cmw"] = interpolate_number(as_float(start.get("cmw"), 0.0), as_float(end.get("cmw"), 0.0), t)

    jaw_keys = set((start.get("jaw_positions_mm") or {}).keys()) | set((end.get("jaw_positions_mm") or {}).keys())
    state["jaw_positions_mm"] = {}
    for key in sorted(jaw_keys):
        start_values = list((start.get("jaw_positions_mm") or {}).get(key, []))
        end_values = list((end.get("jaw_positions_mm") or {}).get(key, []))
        state["jaw_positions_mm"][key] = interpolate_list(start_values, end_values, t) if end_values else start_values

    state["mlc_type"] = start.get("mlc_type") or end.get("mlc_type")
    state["leaf_pair_count"] = int(start.get("leaf_pair_count") or end.get("leaf_pair_count") or 0)
    state["leaf_position_boundaries_mm"] = list(
        start.get("leaf_position_boundaries_mm") or end.get("leaf_position_boundaries_mm") or []
    )
    state["leaf_positions_mm"] = {}
    for bank in ("bank_1", "bank_2"):
        start_values = list((start.get("leaf_positions_mm") or {}).get(bank, []))
        end_values = list((end.get("leaf_positions_mm") or {}).get(bank, []))
        state["leaf_positions_mm"][bank] = interpolate_list(start_values, end_values, t) if end_values else start_values
    if angle_warnings:
        state["warnings"] = list(state.get("warnings", [])) + angle_warnings
    return state, angle_warnings
