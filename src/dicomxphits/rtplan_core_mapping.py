from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from dicomxphits.rtplan_delivery import classify_delivery_type
from dicomxphits.rtplan_helpers import dcm_get
from dicomxphits.rtplan_state import beam_number, carried_control_point_states, final_cmw


@dataclass(frozen=True)
class ControlPointDescriptor:
    control_point_index: int | None
    cmw: float | None
    gantry_angle_deg: float | None
    gantry_rotation_direction: str | None
    collimator_angle_deg: float | None
    collimator_rotation_direction: str | None
    couch_angle_deg: float | None
    jaw_positions_mm: dict[str, list[float]]
    mlc_type: str | None
    leaf_pair_count: int
    leaf_positions_mm: dict[str, list[float]]
    leaf_position_boundaries_mm: list[float]
    warnings: list[str]


@dataclass(frozen=True)
class BeamDescriptor:
    beam: Any
    beam_number: int | None
    beam_name: str
    beam_meterset_mu: float
    final_cumulative_meterset_weight: float | None
    delivery_type: str
    delivery_warnings: list[str]
    control_points: list[ControlPointDescriptor]

    @property
    def unsupported_reason(self) -> str | None:
        if self.delivery_type not in {"unknown", "unsupported"}:
            return None
        return "; ".join(self.delivery_warnings) if self.delivery_warnings else self.delivery_type


def describe_control_point_state(state: dict[str, Any]) -> ControlPointDescriptor:
    return ControlPointDescriptor(
        control_point_index=state.get("control_point_index"),
        cmw=state.get("cmw"),
        gantry_angle_deg=state.get("gantry_angle_deg"),
        gantry_rotation_direction=state.get("gantry_rotation_direction"),
        collimator_angle_deg=state.get("collimator_angle_deg"),
        collimator_rotation_direction=state.get("collimator_rotation_direction"),
        couch_angle_deg=state.get("couch_angle_deg"),
        jaw_positions_mm=deepcopy(state.get("jaw_positions_mm", {})),
        mlc_type=state.get("mlc_type"),
        leaf_pair_count=int(state.get("leaf_pair_count") or 0),
        leaf_positions_mm=deepcopy(state.get("leaf_positions_mm", {"bank_1": [], "bank_2": []})),
        leaf_position_boundaries_mm=list(state.get("leaf_position_boundaries_mm") or []),
        warnings=list(state.get("warnings", [])),
    )


def descriptor_states(descriptor: BeamDescriptor) -> list[dict[str, Any]]:
    states: list[dict[str, Any]] = []
    for cp in descriptor.control_points:
        states.append(
            {
                "control_point_index": cp.control_point_index,
                "cmw": cp.cmw,
                "gantry_angle_deg": cp.gantry_angle_deg,
                "gantry_rotation_direction": cp.gantry_rotation_direction,
                "collimator_angle_deg": cp.collimator_angle_deg,
                "collimator_rotation_direction": cp.collimator_rotation_direction,
                "couch_angle_deg": cp.couch_angle_deg,
                "jaw_positions_mm": deepcopy(cp.jaw_positions_mm),
                "mlc_type": cp.mlc_type,
                "leaf_pair_count": cp.leaf_pair_count,
                "leaf_positions_mm": deepcopy(cp.leaf_positions_mm),
                "leaf_position_boundaries_mm": list(cp.leaf_position_boundaries_mm),
                "warnings": list(cp.warnings),
            }
        )
    return states


def describe_beam(beam: Any, *, beam_meterset_mu: float, tolerances: dict[str, float]) -> BeamDescriptor:
    states = carried_control_point_states(beam)
    delivery_type, delivery_warnings = classify_delivery_type(beam, states, tolerances)
    return BeamDescriptor(
        beam=beam,
        beam_number=beam_number(beam),
        beam_name=str(dcm_get(beam, "BeamName", "") or ""),
        beam_meterset_mu=float(beam_meterset_mu),
        final_cumulative_meterset_weight=final_cmw(beam),
        delivery_type=delivery_type,
        delivery_warnings=delivery_warnings,
        control_points=[describe_control_point_state(state) for state in states],
    )


def describe_rtplan_beams(
    ds: Any,
    *,
    beam_metersets: dict[int | None, float],
    tolerances: dict[str, float],
) -> list[BeamDescriptor]:
    return [
        describe_beam(
            beam,
            beam_meterset_mu=beam_metersets.get(beam_number(beam), 0.0),
            tolerances=tolerances,
        )
        for beam in dcm_get(ds, "BeamSequence", []) or []
    ]
