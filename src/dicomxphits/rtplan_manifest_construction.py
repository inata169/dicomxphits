from __future__ import annotations

import math
from copy import deepcopy
from pathlib import Path, PurePath
from typing import Any, Callable

from dicomxphits.rtplan_core_mapping import describe_rtplan_beams, descriptor_states
from dicomxphits.rtplan_helpers import as_float, as_int, dcm_get
from dicomxphits.rtplan_interpolation import interpolated_state_at, interpolate_number
from dicomxphits.rtplan_rectangular_contract import (
    rectangular_jaw_positions,
    rectangular_mlc_aperture_state,
    rectangular_mlc_positions,
    rectangular_segment_id,
)
from dicomxphits.rtplan_state import (
    beam_number,
    get_referenced_beam_metersets,
    initial_state,
)


SCHEMA_VERSION = "segment_manifest_v2"
MIDPOINT_APPROXIMATION = "midpoint_interval_v1"
SUBINTERVAL_APPROXIMATION = "subinterval_midpoint_v1"
DELIVERY_TYPES = ("3dcrt_static", "static_imrt", "dynamic_imrt", "vmat", "unknown", "unsupported")
DEFAULT_TOLERANCES = {
    "cmw_tolerance": 1.0e-6,
    "angle_tolerance_deg": 0.01,
    "jaw_tolerance_mm": 0.01,
    "leaf_tolerance_mm": 0.01,
}


def _finite_positive(value: float | None) -> bool:
    return value is not None and math.isfinite(float(value)) and float(value) > 0.0


def _positive_int(value: Any, *, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{label} must be a positive integer")
    if value <= 0:
        raise ValueError(f"{label} must be a positive integer")
    return int(value)


def sampling_policy_for_delivery(
    sampling_policy: dict[str, dict[str, Any]],
    delivery_type: str,
) -> dict[str, Any]:
    return dict(sampling_policy.get(delivery_type, {"interval_subdivision": 1}))


def segment_file_stem(beam_num: int | None, segment_index: int) -> str:
    beam_label = "unknown" if beam_num is None else f"{beam_num:04d}"
    return f"beam_{beam_label}_segment_{segment_index:04d}"


def expected_output_path(case_root: Path, beam_num: int | None, segment_index: int, output_name: str) -> str:
    stem = segment_file_stem(beam_num, segment_index)
    return str(Path("phits_outputs") / stem / output_name).replace("\\", "/")


def public_delivery_type(delivery_type: str) -> str:
    return "3dcrt_static" if delivery_type == "3dcrt" else delivery_type


def base_segment(
    *,
    beam: Any,
    beam_mu: float,
    delivery_type: str,
    final_cmw_value: float | None,
    segment_index: int,
    cp_start: int | None,
    cp_end: int | None,
    state: dict[str, Any] | None,
    cmw_start: float | None,
    cmw_end: float | None,
    delta_cmw_raw: float | None,
    segment_weight: float,
    segment_mu: float,
    output_name: str,
    warnings: list[str] | None = None,
    skip_reason: str | None = None,
    approximation: str | None = None,
    sampling_config_path: str | None = None,
    sampling_policy: dict[str, Any] | None = None,
    source_interval_index: int | None = None,
    source_interval_positive_index: int | None = None,
    subinterval_index: int | None = None,
    subinterval_count: int | None = None,
    subinterval_t_start: float | None = None,
    subinterval_t_mid: float | None = None,
    subinterval_t_end: float | None = None,
    source_cmw_start: float | None = None,
    source_cmw_end: float | None = None,
    source_delta_cmw_raw: float | None = None,
    source_segment_mu: float | None = None,
    subinterval_delta_cmw_raw: float | None = None,
    subinterval_segment_mu: float | None = None,
) -> dict[str, Any]:
    bnum = beam_number(beam)
    state = state or initial_state()
    segment_warnings = list(state.get("warnings", []))
    if warnings:
        segment_warnings.extend(warnings)
    stem = segment_file_stem(bnum, segment_index)
    public_type = public_delivery_type(delivery_type)
    mlc_state = rectangular_mlc_aperture_state(state)
    expected_path = expected_output_path(Path("."), bnum, segment_index, output_name)
    expected_parent = str(PurePath(expected_path).parent).replace("\\", "/")
    segment = {
        "schema_version": SCHEMA_VERSION,
        "approximation": approximation,
        "segment_id": rectangular_segment_id(bnum, segment_index),
        "beam": bnum,
        "beam_number": bnum,
        "beam_name": str(dcm_get(beam, "BeamName", "") or ""),
        "beam_meterset_mu": float(beam_mu),
        "final_cumulative_meterset_weight": final_cmw_value,
        "delivery_type": public_type,
        "source_delivery_type": delivery_type,
        "segment_index": int(segment_index),
        "cp_start": cp_start,
        "cp_end": cp_end,
        "cmw_start": cmw_start,
        "cmw_end": cmw_end,
        "delta_cmw_raw": delta_cmw_raw,
        "segment_weight": float(segment_weight),
        "segment_mu": float(segment_mu),
        "mu_weight": float(segment_mu),
        "mu_weight_unit": "MU",
        "gantry_angle_deg": as_float(state.get("gantry_angle_deg"), 0.0),
        "collimator_angle_deg": as_float(state.get("collimator_angle_deg"), 0.0),
        "couch_angle_deg": as_float(state.get("couch_angle_deg"), 0.0),
        "jaw_positions_mm": deepcopy(state.get("jaw_positions_mm", {})),
        "resolved_jaw_positions_mm": rectangular_jaw_positions(state),
        "mlc_type": state.get("mlc_type"),
        "leaf_positions_mm": deepcopy(state.get("leaf_positions_mm", {"bank_1": [], "bank_2": []})),
        "leaf_position_boundaries_mm": list(state.get("leaf_position_boundaries_mm") or []),
        "mlc_aperture_state": mlc_state,
        "resolved_mlc_positions_mm": rectangular_mlc_positions(state) if mlc_state in {"present", "fully_open_mlc"} else None,
        "static_aperture_classification": {
            "status": "static" if public_type == "3dcrt_static" else "unsupported",
            "source": "rtplan_manifest_control_points",
        },
        "aperture_change_diagnostics": {
            "status": "static" if public_type == "3dcrt_static" else "unsupported",
            "dynamic_like": public_type != "3dcrt_static",
            "jaw_changed": False if public_type == "3dcrt_static" else None,
            "mlc_changed": False if public_type == "3dcrt_static" else None,
        },
        "phits_input_path": str(Path("phits_inputs") / f"{stem}.inp").replace("\\", "/"),
        "expected_output_path": expected_path,
        "dir": expected_parent,
        "output": output_name,
        "global_segment": stem,
        "warnings": segment_warnings,
        "skip_reason": skip_reason,
    }
    if sampling_policy is not None:
        segment["sampling_policy"] = deepcopy(sampling_policy)
        segment["sampling_config_path"] = sampling_config_path
    if source_interval_index is not None:
        segment.update(
            {
                "source_interval_index": int(source_interval_index),
                "source_interval_positive_index": source_interval_positive_index,
                "subinterval_index": subinterval_index,
                "subinterval_count": subinterval_count,
                "subinterval_t_start": subinterval_t_start,
                "subinterval_t_mid": subinterval_t_mid,
                "subinterval_t_end": subinterval_t_end,
                "source_cmw_start": source_cmw_start,
                "source_cmw_end": source_cmw_end,
                "source_delta_cmw_raw": source_delta_cmw_raw,
                "source_segment_mu": source_segment_mu,
                "subinterval_delta_cmw_raw": subinterval_delta_cmw_raw,
                "subinterval_segment_mu": subinterval_segment_mu,
                "cmw_role": "interval_weight_coordinate",
            }
        )
    return segment


def interval_segments_for_beam(
    beam: Any,
    beam_mu: float,
    delivery_type: str,
    states: list[dict[str, Any]],
    final_cmw_value: float | None,
    output_name: str,
    tolerances: dict[str, float],
    sampling_policy: dict[str, dict[str, Any]],
    sampling_config_path: str | None,
) -> list[dict[str, Any]]:
    if not _finite_positive(final_cmw_value):
        raise ValueError(f"Beam {beam_number(beam)} {delivery_type} requires positive finite FinalCumulativeMetersetWeight")

    segments: list[dict[str, Any]] = []
    active_weight_sum = 0.0
    positive_interval_index = 0
    delivery_sampling = sampling_policy_for_delivery(sampling_policy, delivery_type)
    interval_subdivision = _positive_int(
        delivery_sampling.get("interval_subdivision", 1),
        label=f"rtplan_sampling.{delivery_type}.interval_subdivision",
    )
    for source_interval_index, (start, end) in enumerate(zip(states, states[1:])):
        delta = float(end.get("cmw", 0.0)) - float(start.get("cmw", 0.0))
        cp_start = as_int(start.get("control_point_index"), None)
        cp_end = as_int(end.get("control_point_index"), None)
        if delta < -tolerances["cmw_tolerance"]:
            raise ValueError(f"Beam {beam_number(beam)} CP {cp_start} -> CP {cp_end} has negative CMW delta {delta}")
        if abs(delta) <= tolerances["cmw_tolerance"]:
            segments.append(
                base_segment(
                    beam=beam,
                    beam_mu=beam_mu,
                    delivery_type=delivery_type,
                    final_cmw_value=final_cmw_value,
                    segment_index=len(segments),
                    cp_start=cp_start,
                    cp_end=cp_end,
                    state=start,
                    cmw_start=as_float(start.get("cmw"), 0.0),
                    cmw_end=as_float(end.get("cmw"), 0.0),
                    delta_cmw_raw=delta,
                    segment_weight=0.0,
                    segment_mu=0.0,
                    output_name=output_name,
                    warnings=[f"Skipped CP {cp_start} -> CP {cp_end}: zero CMW delta {delta}"],
                    skip_reason="zero CMW delta",
                    approximation=MIDPOINT_APPROXIMATION if delivery_type in {"dynamic_imrt", "vmat"} else None,
                    sampling_config_path=sampling_config_path,
                    sampling_policy=delivery_sampling,
                    source_interval_index=source_interval_index,
                    source_interval_positive_index=None,
                    subinterval_index=None,
                    subinterval_count=interval_subdivision,
                )
            )
            continue

        segment_weight = delta / float(final_cmw_value)
        active_weight_sum += segment_weight
        source_cmw_start = as_float(start.get("cmw"), 0.0)
        source_cmw_end = as_float(end.get("cmw"), 0.0)
        source_segment_mu = beam_mu * segment_weight
        for sub_idx in range(interval_subdivision):
            t_start = sub_idx / interval_subdivision
            t_end = (sub_idx + 1) / interval_subdivision
            t_mid = (t_start + t_end) * 0.5
            if delivery_type == "static_imrt":
                representative_state = start
                warnings = []
                approximation = None
            else:
                representative_state, warnings = interpolated_state_at(start, end, t_mid, tolerances)
                warnings = []
                approximation = (
                    MIDPOINT_APPROXIMATION
                    if interval_subdivision == 1
                    else SUBINTERVAL_APPROXIMATION
                )
            sub_delta = delta / interval_subdivision
            sub_weight = segment_weight / interval_subdivision
            sub_mu = source_segment_mu / interval_subdivision
            segments.append(
                base_segment(
                    beam=beam,
                    beam_mu=beam_mu,
                    delivery_type=delivery_type,
                    final_cmw_value=final_cmw_value,
                    segment_index=len(segments),
                    cp_start=cp_start,
                    cp_end=cp_end,
                    state=representative_state,
                    cmw_start=interpolate_number(source_cmw_start, source_cmw_end, t_start),
                    cmw_end=interpolate_number(source_cmw_start, source_cmw_end, t_end),
                    delta_cmw_raw=sub_delta,
                    segment_weight=sub_weight,
                    segment_mu=sub_mu,
                    output_name=output_name,
                    warnings=warnings,
                    approximation=approximation,
                    sampling_config_path=sampling_config_path,
                    sampling_policy=delivery_sampling,
                    source_interval_index=source_interval_index,
                    source_interval_positive_index=positive_interval_index,
                    subinterval_index=sub_idx,
                    subinterval_count=interval_subdivision,
                    subinterval_t_start=t_start,
                    subinterval_t_mid=t_mid,
                    subinterval_t_end=t_end,
                    source_cmw_start=source_cmw_start,
                    source_cmw_end=source_cmw_end,
                    source_delta_cmw_raw=delta,
                    source_segment_mu=source_segment_mu,
                    subinterval_delta_cmw_raw=sub_delta,
                    subinterval_segment_mu=sub_mu,
                )
            )
        positive_interval_index += 1

    if segments and abs(active_weight_sum - 1.0) > 1.0e-4:
        warning = (
            f"Beam {beam_number(beam)} positive interval segment_weight sum {active_weight_sum:.8g} "
            "differs from 1.0"
        )
        for segment in segments:
            if not segment.get("skip_reason"):
                segment["warnings"] = list(segment.get("warnings", [])) + [warning]
    return segments


def build_segments_for_beam(
    beam: Any,
    beam_mu: float,
    delivery_type: str,
    states: list[dict[str, Any]],
    final_cmw_value: float | None,
    output_name: str,
    tolerances: dict[str, float],
    sampling_policy: dict[str, dict[str, Any]],
    sampling_config_path: str | None,
) -> list[dict[str, Any]]:
    if delivery_type == "3dcrt":
        if not states:
            return []
        state = states[0]
        return [
            base_segment(
                beam=beam,
                beam_mu=beam_mu,
                delivery_type=delivery_type,
                final_cmw_value=final_cmw_value,
                segment_index=0,
                cp_start=as_int(state.get("control_point_index"), 0),
                cp_end=as_int(states[-1].get("control_point_index"), as_int(state.get("control_point_index"), 0)),
                state=state,
                cmw_start=as_float(state.get("cmw"), 0.0),
                cmw_end=as_float(states[-1].get("cmw"), as_float(state.get("cmw"), 0.0)),
                delta_cmw_raw=final_cmw_value,
                segment_weight=1.0,
                segment_mu=beam_mu,
                output_name=output_name,
            )
        ]

    if delivery_type not in {"static_imrt", "dynamic_imrt", "vmat"}:
        return [
            base_segment(
                beam=beam,
                beam_mu=beam_mu,
                delivery_type=delivery_type,
                final_cmw_value=final_cmw_value,
                segment_index=0,
                cp_start=None,
                cp_end=None,
                state=states[0] if states else None,
                cmw_start=None,
                cmw_end=None,
                delta_cmw_raw=None,
                segment_weight=0.0,
                segment_mu=0.0,
                output_name=output_name,
                skip_reason=f"delivery_type {delivery_type} is not generation-capable in this workflow",
            )
        ]

    return interval_segments_for_beam(
        beam,
        beam_mu,
        delivery_type,
        states,
        final_cmw_value,
        output_name,
        tolerances,
        sampling_policy,
        sampling_config_path,
    )


def build_manifest(
    ds: Any,
    *,
    case_id: str,
    workflow_mode: str,
    include_beams: set[int] | None,
    dose_normalization_mu: float | None,
    output_name: str,
    sampling_policy: dict[str, dict[str, Any]],
    tolerances: dict[str, float] | None = None,
    sampling_config_path: str | None = None,
    states_table_builder: Callable[[Any], list[dict[str, Any]]] | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    tolerances = dict(tolerances or DEFAULT_TOLERANCES)
    beam_mus = get_referenced_beam_metersets(ds)
    plan_total_mu = sum(beam_mus.values())
    segments: list[dict[str, Any]] = []
    beam_summaries: list[dict[str, Any]] = []
    warnings: list[str] = []

    for descriptor in describe_rtplan_beams(ds, beam_metersets=beam_mus, tolerances=tolerances):
        beam = descriptor.beam
        bnum = descriptor.beam_number
        if include_beams is not None and bnum not in include_beams:
            continue
        states = descriptor_states(descriptor)
        delivery_type = descriptor.delivery_type
        delivery_warnings = list(descriptor.delivery_warnings)
        beam_mu = descriptor.beam_meterset_mu
        if bnum not in beam_mus:
            delivery_warnings.append(f"BeamMeterset missing for beam {bnum}; using 0.0 MU")
        final_cmw_value = descriptor.final_cumulative_meterset_weight
        beam_segments = build_segments_for_beam(
            beam,
            beam_mu,
            delivery_type,
            states,
            final_cmw_value,
            output_name,
            tolerances,
            sampling_policy,
            sampling_config_path,
        )
        for segment in beam_segments:
            if delivery_warnings:
                segment["warnings"] = list(segment.get("warnings", [])) + delivery_warnings
        segments.extend(beam_segments)
        beam_summaries.append(
            {
                "beam_number": bnum,
                "beam_name": str(dcm_get(beam, "BeamName", "") or ""),
                "beam_meterset_mu": beam_mu,
                "final_cumulative_meterset_weight": final_cmw_value,
                "delivery_type": delivery_type,
                "segment_count": len([s for s in beam_segments if not s.get("skip_reason")]),
                "skipped_segment_count": len([s for s in beam_segments if s.get("skip_reason")]),
                "sampling_policy": sampling_policy_for_delivery(sampling_policy, delivery_type),
                "warnings": delivery_warnings,
            }
        )

    included_total_mu = sum(row["beam_meterset_mu"] for row in beam_summaries)
    if dose_normalization_mu is None:
        dose_normalization_mu = included_total_mu
    if abs(plan_total_mu - included_total_mu) > 1.0e-6:
        message = (
            f"plan_total_mu ({plan_total_mu}) differs from included_total_mu ({included_total_mu}) "
            f"in {workflow_mode} mode"
        )
        if workflow_mode == "full_plan":
            raise ValueError(message)
        warnings.append(message)

    manifest_approximation = (
        SUBINTERVAL_APPROXIMATION
        if any(segment.get("approximation") == SUBINTERVAL_APPROXIMATION for segment in segments)
        else MIDPOINT_APPROXIMATION
    )
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "approximation": manifest_approximation,
        "case_id": case_id,
        "plan_uid": str(dcm_get(ds, "SOPInstanceUID", "") or dcm_get(ds, "RTPlanLabel", "") or ""),
        "workflow_mode": workflow_mode,
        "plan_total_mu": plan_total_mu,
        "included_total_mu": included_total_mu,
        "dose_normalization_mu": dose_normalization_mu,
        "tolerances": tolerances,
        "rtplan_sampling": sampling_policy,
        "sampling_config_path": sampling_config_path,
        "sampling_policy_role": "workflow approximation policy, not a physical machine model parameter",
        "delivery_type_values": list(DELIVERY_TYPES),
        "segments": segments,
        "warnings": warnings,
    }
    cp_rows = states_table_builder(ds) if states_table_builder is not None else []
    return manifest, beam_summaries, cp_rows
