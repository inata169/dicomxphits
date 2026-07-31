"""Exact-decimal guard for the centered 20 x 20 cm2 public v1.0.0 aperture."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any, Iterable


PUBLIC_APERTURE_DECISION_FIELD = "public_effective_aperture_decision"
PUBLIC_APERTURE_LIMIT_MM = Decimal("100.000")
PUBLIC_APERTURE_MAX_WIDTH_MM = Decimal("200.000")


def _decimal(value: Any, *, label: str) -> Decimal:
    if isinstance(value, bool) or value is None:
        raise ValueError(f"{label} is missing or is not an exact decimal value")
    if isinstance(value, float):
        raise ValueError(f"{label} was already converted through binary floating point")
    try:
        number = value if isinstance(value, Decimal) else Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"{label} is not a valid decimal value") from exc
    if not number.is_finite():
        raise ValueError(f"{label} must be finite")
    return number


def _decimal_pair(values: Any, *, label: str) -> tuple[Decimal, Decimal]:
    if not isinstance(values, (list, tuple)) or len(values) != 2:
        raise ValueError(f"{label} requires exactly two positions")
    low = _decimal(values[0], label=f"{label}[0]")
    high = _decimal(values[1], label=f"{label}[1]")
    if low >= high:
        raise ValueError(f"{label} positions must be strictly ordered")
    return low, high


def _decimal_list(values: Any, *, label: str) -> list[Decimal]:
    if not isinstance(values, (list, tuple)):
        raise ValueError(f"{label} is missing")
    return [_decimal(value, label=f"{label}[{index}]") for index, value in enumerate(values)]


def _only_axis_jaw(
    positions: dict[str, Any],
    definition_counts: dict[str, Any],
    device_types: tuple[str, ...],
    *,
    axis: str,
) -> tuple[str, tuple[Decimal, Decimal]]:
    declared = [dtype for dtype in device_types if definition_counts.get(dtype)]
    if len(declared) != 1:
        raise ValueError(f"{axis} jaw state is missing or ambiguous")
    dtype = declared[0]
    if definition_counts.get(dtype) != 1 or dtype not in positions:
        raise ValueError(f"{axis} jaw state is missing or ambiguous")
    return dtype, _decimal_pair(positions[dtype], label=f"{dtype} jaw")


def _optional_axis_jaw(
    positions: dict[str, Any],
    definition_counts: dict[str, Any],
    device_types: tuple[str, ...],
    *,
    axis: str,
) -> tuple[str | None, tuple[Decimal, Decimal] | None]:
    declared = [dtype for dtype in device_types if definition_counts.get(dtype)]
    positioned = [dtype for dtype in device_types if dtype in positions]
    if not declared and not positioned:
        return None, None
    if len(declared) != 1:
        raise ValueError(f"{axis} jaw state is missing or ambiguous")
    dtype = declared[0]
    if definition_counts.get(dtype) != 1 or positioned != [dtype]:
        raise ValueError(f"{axis} jaw state is missing or ambiguous")
    return dtype, _decimal_pair(positions[dtype], label=f"{dtype} jaw")


def _effective_bounds(state: dict[str, Any]) -> dict[str, Decimal]:
    issues = state.get("public_aperture_resolution_issues")
    if not isinstance(issues, list):
        raise ValueError("public aperture resolution evidence is missing")
    if issues:
        raise ValueError("; ".join(str(issue) for issue in issues))
    definition_counts = state.get("beam_device_definition_counts")
    jaw_positions = state.get("jaw_positions_decimal_mm")
    if not isinstance(definition_counts, dict) or not isinstance(jaw_positions, dict):
        raise ValueError("exact-decimal jaw evidence is missing")
    _x_type, x_jaw = _optional_axis_jaw(
        jaw_positions, definition_counts, ("ASYMX", "X"), axis="X"
    )
    _y_type, (jaw_y_min, jaw_y_max) = _only_axis_jaw(
        jaw_positions, definition_counts, ("ASYMY", "Y"), axis="Y"
    )

    mlc_positions = state.get("mlc_positions_decimal_mm")
    if not isinstance(mlc_positions, dict):
        raise ValueError("exact-decimal MLC state is missing")
    declared_mlc = sorted(
        dtype for dtype, count in definition_counts.items()
        if str(dtype).startswith("MLC") and count
    )
    if not declared_mlc:
        if x_jaw is None:
            raise ValueError("X jaw state is missing or ambiguous")
        jaw_x_min, jaw_x_max = x_jaw
        return {
            "x_min": jaw_x_min,
            "x_max": jaw_x_max,
            "y_min": jaw_y_min,
            "y_max": jaw_y_max,
        }
    if declared_mlc != ["MLCX"] or definition_counts.get("MLCX") != 1:
        raise ValueError("MLC device definition must contain exactly one MLCX device")
    banks = mlc_positions.get("MLCX")
    if not isinstance(banks, dict):
        raise ValueError("MLCX position state is missing after Control Point inheritance")
    bank_1 = _decimal_list(banks.get("bank_1"), label="MLCX bank_1")
    bank_2 = _decimal_list(banks.get("bank_2"), label="MLCX bank_2")
    pair_count = state.get("mlc_pair_counts", {}).get("MLCX")
    if isinstance(pair_count, bool) or not isinstance(pair_count, int) or pair_count <= 0:
        raise ValueError("MLCX leaf-pair count is missing or invalid")
    if len(bank_1) != pair_count or len(bank_2) != pair_count:
        raise ValueError("MLCX bank lengths do not match the declared leaf-pair count")
    boundaries = _decimal_list(
        state.get("mlc_leaf_boundaries_decimal_mm", {}).get("MLCX"),
        label="MLCX leaf boundaries",
    )
    if len(boundaries) != pair_count + 1:
        raise ValueError("MLCX leaf boundaries do not match the declared leaf-pair count")
    if any(left >= right for left, right in zip(boundaries, boundaries[1:])):
        raise ValueError("MLCX leaf boundaries must be strictly ordered")

    rectangles: list[tuple[Decimal, Decimal, Decimal, Decimal]] = []
    for index, (leaf_left, leaf_right) in enumerate(zip(bank_1, bank_2)):
        if leaf_left > leaf_right:
            raise ValueError(f"MLCX leaf pair {index} positions are unordered")
        x_min = leaf_left if x_jaw is None else max(x_jaw[0], leaf_left)
        x_max = leaf_right if x_jaw is None else min(x_jaw[1], leaf_right)
        y_min = max(jaw_y_min, boundaries[index])
        y_max = min(jaw_y_max, boundaries[index + 1])
        if x_min < x_max and y_min < y_max:
            rectangles.append((x_min, x_max, y_min, y_max))
    if not rectangles:
        raise ValueError("resolved jaw-MLC common aperture is empty")
    return {
        "x_min": min(row[0] for row in rectangles),
        "x_max": max(row[1] for row in rectangles),
        "y_min": min(row[2] for row in rectangles),
        "y_max": max(row[3] for row in rectangles),
    }


def require_v1_effective_apertures(
    beam_states: Iterable[tuple[int | None, list[dict[str, Any]]]],
) -> dict[str, Any]:
    control_points: list[dict[str, Any]] = []
    for beam_number, states in beam_states:
        if not states:
            raise ValueError(f"beam={beam_number} has no resolved Control Points")
        for ordinal, state in enumerate(states):
            cp_index = state.get("control_point_index")
            cp_label = cp_index if isinstance(cp_index, int) and not isinstance(cp_index, bool) else ordinal
            try:
                bounds = _effective_bounds(state)
            except ValueError as exc:
                raise ValueError(f"beam={beam_number} control_point={cp_label}: {exc}") from exc
            for axis in ("x", "y"):
                low = bounds[f"{axis}_min"]
                high = bounds[f"{axis}_max"]
                width = high - low
                if low < -PUBLIC_APERTURE_LIMIT_MM:
                    raise ValueError(
                        f"beam={beam_number} control_point={cp_label}: "
                        f"{axis.upper()} minimum {low} mm is below -100.000 mm"
                    )
                if high > PUBLIC_APERTURE_LIMIT_MM:
                    raise ValueError(
                        f"beam={beam_number} control_point={cp_label}: "
                        f"{axis.upper()} maximum {high} mm exceeds +100.000 mm"
                    )
                if width > PUBLIC_APERTURE_MAX_WIDTH_MM:
                    raise ValueError(
                        f"beam={beam_number} control_point={cp_label}: "
                        f"{axis.upper()} width {width} mm exceeds 200.000 mm"
                    )
            control_points.append(
                {
                    "beam_number": beam_number,
                    "control_point_index": cp_label,
                    "x_min_mm": format(bounds["x_min"], "f"),
                    "x_max_mm": format(bounds["x_max"], "f"),
                    "y_min_mm": format(bounds["y_min"], "f"),
                    "y_max_mm": format(bounds["y_max"], "f"),
                }
            )
    if not control_points:
        raise ValueError("public effective-aperture evaluation requires at least one Control Point")
    return {
        "status": "accepted",
        "comparison_semantics": "exact-decimal-no-tolerance-no-rounding",
        # Public v1.0.0 centered 20 x 20 cm2 support boundary.
        "support_box_mm": {
            "x_min": "-100.000",
            "x_max": "100.000",
            "y_min": "-100.000",
            "y_max": "100.000",
        },
        "max_axis_width_mm": "200.000",
        "control_points": control_points,
    }
