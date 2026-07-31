from __future__ import annotations

import math
from typing import Any

from dicomxphits.rtplan_helpers import as_float, as_float_list


def rectangular_segment_id(beam_num: int | None, segment_index: int) -> str:
    beam_label = "unknown" if beam_num is None else f"{beam_num:04d}"
    return f"seg_b{beam_label}_s{segment_index:04d}"


def rectangular_jaw_positions(state: dict[str, Any]) -> dict[str, float | None]:
    jaws = state.get("jaw_positions_mm") or {}
    x_values = list(jaws.get("ASYMX") or jaws.get("X") or [])
    y_values = list(jaws.get("ASYMY") or jaws.get("Y") or [])
    if len(x_values) < 2:
        x_values = rectangular_mlc_x_extent(state, y_values)
    return {
        "x1": as_float(x_values[0], None) if len(x_values) > 0 else None,
        "x2": as_float(x_values[1], None) if len(x_values) > 1 else None,
        "y1": as_float(y_values[0], None) if len(y_values) > 0 else None,
        "y2": as_float(y_values[1], None) if len(y_values) > 1 else None,
    }


def rectangular_mlc_x_extent(state: dict[str, Any], y_values: list[Any]) -> list[float]:
    y1 = as_float(y_values[0], None) if len(y_values) > 0 else None
    y2 = as_float(y_values[1], None) if len(y_values) > 1 else None
    if y1 is None or y2 is None or not math.isfinite(y1) or not math.isfinite(y2) or y1 >= y2:
        return []
    boundaries = as_float_list(state.get("leaf_position_boundaries_mm"))
    pair_count = int(state.get("leaf_pair_count") or 0)
    if pair_count <= 0 or len(boundaries) != pair_count + 1:
        return []
    positions = state.get("leaf_positions_mm") or {}
    bank_1 = list(positions.get("bank_1") or [])
    bank_2 = list(positions.get("bank_2") or [])
    if len(bank_1) < pair_count or len(bank_2) < pair_count:
        return []
    values: list[float] = []
    for index in range(pair_count):
        lower = boundaries[index]
        upper = boundaries[index + 1]
        if not math.isfinite(lower) or not math.isfinite(upper) or lower >= upper:
            return []
        if lower >= y2 or upper <= y1:
            continue
        for value in (bank_1[index], bank_2[index]):
            number = as_float(value, None)
            if number is None or not math.isfinite(number):
                return []
            values.append(number)
    if not values:
        return []
    return [min(values), max(values)]


def rectangular_mlc_positions(state: dict[str, Any]) -> dict[str, list[float]]:
    positions = state.get("leaf_positions_mm") or {}
    return {
        "bank_a": [float(value) for value in list(positions.get("bank_1") or [])],
        "bank_b": [float(value) for value in list(positions.get("bank_2") or [])],
    }


def rectangular_mlc_aperture_state(state: dict[str, Any]) -> str:
    explicit = state.get("mlc_aperture_state")
    if explicit in {"present", "fully_open_mlc", "no_mlc"}:
        return str(explicit)
    if state.get("mlc_type"):
        return "present"
    return "no_mlc"
