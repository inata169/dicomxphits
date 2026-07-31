from __future__ import annotations

from copy import deepcopy
from typing import Any

from dicomxphits.rtplan_helpers import (
    as_exact_decimal_text_list,
    as_float,
    as_float_list,
    as_int,
    beam_device_definition_counts,
    beam_leaf_boundaries_decimal,
    beam_leaf_pair_counts,
    beam_leaf_position_boundaries,
    dcm_get,
    is_mlc_device,
)


def initial_state() -> dict[str, Any]:
    return {
        "control_point_index": None,
        "gantry_angle_deg": None,
        "gantry_rotation_direction": None,
        "collimator_angle_deg": None,
        "collimator_rotation_direction": None,
        "couch_angle_deg": None,
        "cmw": 0.0,
        "jaw_positions_mm": {},
        "jaw_positions_decimal_mm": {},
        "mlc_type": None,
        "leaf_positions_mm": {"bank_1": [], "bank_2": []},
        "mlc_positions_decimal_mm": {},
        "leaf_position_boundaries_mm": [],
        "leaf_pair_count": 0,
        "mlc_pair_counts": {},
        "mlc_leaf_boundaries_decimal_mm": {},
        "beam_device_definition_counts": {},
        "public_aperture_resolution_issues": [],
        "warnings": [],
    }


def apply_control_point(
    cp: Any,
    previous: dict[str, Any],
    leaf_pair_counts: dict[str, int],
    leaf_position_boundaries: dict[str, list[float]],
) -> dict[str, Any]:
    state = deepcopy(previous)
    state["warnings"] = []
    state["public_aperture_resolution_issues"] = []
    state["control_point_index"] = as_int(dcm_get(cp, "ControlPointIndex"), state.get("control_point_index"))

    for key, tag in (
        ("gantry_angle_deg", "GantryAngle"),
        ("collimator_angle_deg", "BeamLimitingDeviceAngle"),
        ("couch_angle_deg", "PatientSupportAngle"),
    ):
        value = as_float(dcm_get(cp, tag), None)
        if value is not None:
            state[key] = value

    for key, tag in (
        ("gantry_rotation_direction", "GantryRotationDirection"),
        ("collimator_rotation_direction", "BeamLimitingDeviceRotationDirection"),
    ):
        value = dcm_get(cp, tag)
        if value is not None:
            state[key] = str(value)

    cmw = as_float(dcm_get(cp, "CumulativeMetersetWeight"), None)
    if cmw is not None:
        state["cmw"] = cmw

    seen_position_types: set[str] = set()
    for item in dcm_get(cp, "BeamLimitingDevicePositionSequence", []) or []:
        dtype = str(dcm_get(item, "RTBeamLimitingDeviceType", "") or "")
        raw_positions = dcm_get(item, "LeafJawPositions")
        positions = as_float_list(raw_positions)
        decimal_positions = as_exact_decimal_text_list(raw_positions)
        if not dtype:
            state["warnings"].append("Beam limiting device without RTBeamLimitingDeviceType")
            continue
        if dtype in seen_position_types:
            state["public_aperture_resolution_issues"].append(
                f"duplicate {dtype} position entries in one Control Point"
            )
        seen_position_types.add(dtype)
        if dtype in ("ASYMX", "ASYMY", "X", "Y"):
            state["jaw_positions_mm"][dtype] = positions
            state["jaw_positions_decimal_mm"][dtype] = decimal_positions
            continue
        if is_mlc_device(dtype):
            half = len(positions) // 2
            pair_count = leaf_pair_counts.get(dtype, half)
            state["mlc_type"] = dtype
            state["leaf_pair_count"] = int(pair_count or 0)
            state["leaf_position_boundaries_mm"] = list(leaf_position_boundaries.get(dtype, []))
            state["leaf_positions_mm"] = {
                "bank_1": positions[:half],
                "bank_2": positions[half:],
            }
            state["mlc_positions_decimal_mm"][dtype] = {
                "bank_1": decimal_positions[:half],
                "bank_2": decimal_positions[half:],
            }
            if pair_count and half != pair_count:
                state["warnings"].append(
                    f"{dtype} LeafJawPositions count {len(positions)} does not match {pair_count} leaf pairs"
                )
            continue
        state["warnings"].append(f"Unsupported beam limiting device type: {dtype}")
    return state


def carried_control_point_states(beam: Any) -> list[dict[str, Any]]:
    leaf_counts = beam_leaf_pair_counts(beam)
    leaf_boundaries = beam_leaf_position_boundaries(beam)
    device_definition_counts = beam_device_definition_counts(beam)
    decimal_leaf_boundaries = beam_leaf_boundaries_decimal(beam)
    states: list[dict[str, Any]] = []
    state = initial_state()
    state["mlc_pair_counts"] = dict(leaf_counts)
    state["mlc_leaf_boundaries_decimal_mm"] = deepcopy(decimal_leaf_boundaries)
    state["beam_device_definition_counts"] = device_definition_counts
    for idx, cp in enumerate(dcm_get(beam, "ControlPointSequence", []) or []):
        state = apply_control_point(cp, state, leaf_counts, leaf_boundaries)
        if state.get("control_point_index") is None:
            state["control_point_index"] = idx
        states.append(deepcopy(state))
    return states


def get_referenced_beam_metersets(ds: Any) -> dict[int, float]:
    metersets: dict[int, float] = {}
    for fraction_group in dcm_get(ds, "FractionGroupSequence", []) or []:
        for referenced_beam in dcm_get(fraction_group, "ReferencedBeamSequence", []) or []:
            beam_number = as_int(dcm_get(referenced_beam, "ReferencedBeamNumber"), None)
            beam_mu = as_float(dcm_get(referenced_beam, "BeamMeterset"), None)
            if beam_number is not None and beam_mu is not None:
                metersets[beam_number] = beam_mu
    return metersets


def beam_number(beam: Any) -> int | None:
    return as_int(dcm_get(beam, "BeamNumber"), None)


def final_cmw(beam: Any) -> float | None:
    return as_float(dcm_get(beam, "FinalCumulativeMetersetWeight"), None)
