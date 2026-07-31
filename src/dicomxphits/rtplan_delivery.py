from __future__ import annotations

from typing import Any

from dicomxphits.rtplan_helpers import as_float, dcm_get


def values_close(a: float | None, b: float | None, tolerance: float) -> bool:
    if a is None or b is None:
        return a is b
    return abs(float(a) - float(b)) <= tolerance


def lists_close(a: list[float], b: list[float], tolerance: float) -> bool:
    if len(a) != len(b):
        return False
    return all(abs(x - y) <= tolerance for x, y in zip(a, b))


def aperture_close(a: dict[str, Any], b: dict[str, Any], tolerances: dict[str, float]) -> bool:
    for key in ("gantry_angle_deg", "collimator_angle_deg", "couch_angle_deg"):
        if not values_close(as_float(a.get(key), None), as_float(b.get(key), None), tolerances["angle_tolerance_deg"]):
            return False
    jaw_keys = set((a.get("jaw_positions_mm") or {}).keys()) | set((b.get("jaw_positions_mm") or {}).keys())
    for key in jaw_keys:
        if not lists_close(
            list((a.get("jaw_positions_mm") or {}).get(key, [])),
            list((b.get("jaw_positions_mm") or {}).get(key, [])),
            tolerances["jaw_tolerance_mm"],
        ):
            return False
    for bank in ("bank_1", "bank_2"):
        if not lists_close(
            list((a.get("leaf_positions_mm") or {}).get(bank, [])),
            list((b.get("leaf_positions_mm") or {}).get(bank, [])),
            tolerances["leaf_tolerance_mm"],
        ):
            return False
    return True


def has_mlc(states: list[dict[str, Any]]) -> bool:
    return any(int(state.get("leaf_pair_count") or 0) > 0 for state in states)


def has_rotating_gantry(states: list[dict[str, Any]]) -> bool:
    for state in states:
        direction = str(state.get("gantry_rotation_direction") or "").upper()
        if direction and direction != "NONE":
            return True
    return False


def has_positive_cmw_intervals(states: list[dict[str, Any]], cmw_tolerance: float) -> bool:
    for start, end in zip(states, states[1:]):
        delta = float(end.get("cmw", 0.0)) - float(start.get("cmw", 0.0))
        if delta > cmw_tolerance:
            return True
    return False


def classify_delivery_type(beam: Any, states: list[dict[str, Any]], tolerances: dict[str, float]) -> tuple[str, list[str]]:
    warnings: list[str] = []
    if not states:
        return "unknown", ["No ControlPointSequence entries are available"]
    beam_type = str(dcm_get(beam, "BeamType", "") or "").upper()
    treatment_delivery = str(dcm_get(beam, "TreatmentDeliveryType", "") or "").upper()
    if treatment_delivery and treatment_delivery not in ("TREATMENT", "CONTINUATION"):
        return "unsupported", [f"TreatmentDeliveryType is {treatment_delivery}"]
    if has_rotating_gantry(states):
        return "vmat", []
    if beam_type == "DYNAMIC":
        return "dynamic_imrt", []
    if len(states) <= 2 and all(aperture_close(states[0], state, tolerances) for state in states[1:]):
        return "3dcrt", []
    if has_mlc(states) and has_positive_cmw_intervals(states, tolerances["cmw_tolerance"]):
        return "static_imrt", []
    if len(states) > 2 and all(aperture_close(states[0], state, tolerances) for state in states[1:]):
        warnings.append("Multiple control points share a fixed aperture; classified as 3dcrt")
        return "3dcrt", warnings
    return "unknown", ["Unable to classify delivery type from available control point data"]
