from __future__ import annotations

import math
from typing import Any, Mapping


GANTRY_GEOMETRY_CONTRACT_FIELD = "gantry_geometry_contract"
PREVIOUS_GANTRY_GEOMETRY_CONTRACT = "dicomxphits_iec_gantry_direction_v2"
CURRENT_GANTRY_GEOMETRY_CONTRACT = "dicomxphits_iec_gantry_mlcx_geometry_v3"
LEGACY_ZERO_GANTRY_CONTRACT = "legacy_zero_gantry_geometry_unchanged"


class GantryGeometryContractError(ValueError):
    """Raised when PHITS transport geometry cannot be tied to the IEC contract."""


def bind_current_gantry_geometry_contract(manifest: dict[str, Any]) -> None:
    existing = manifest.get(GANTRY_GEOMETRY_CONTRACT_FIELD)
    if existing not in {None, CURRENT_GANTRY_GEOMETRY_CONTRACT}:
        raise GantryGeometryContractError(
            "segment manifest has an unsupported gantry geometry contract; "
            "prepare a new workspace"
        )
    manifest[GANTRY_GEOMETRY_CONTRACT_FIELD] = CURRENT_GANTRY_GEOMETRY_CONTRACT


def _active_segments(manifest: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    segments = manifest.get("segments")
    if not isinstance(segments, list):
        raise GantryGeometryContractError(
            "segment manifest must contain a segments list"
        )
    active = [
        segment
        for segment in segments
        if isinstance(segment, Mapping) and not segment.get("skip_reason")
    ]
    if not active:
        raise GantryGeometryContractError(
            "segment manifest has no active segment geometry"
        )
    return active


def _has_only_explicit_zero_gantry(manifest: Mapping[str, Any]) -> bool:
    for segment in _active_segments(manifest):
        value = segment.get("gantry_angle_deg")
        if isinstance(value, bool):
            return False
        try:
            angle = float(value)
        except (TypeError, ValueError):
            return False
        if not math.isfinite(angle) or not math.isclose(
            angle,
            0.0,
            rel_tol=0.0,
            abs_tol=1.0e-9,
        ):
            return False
    return True


def _has_only_reflection_invariant_mlcx(manifest: Mapping[str, Any]) -> bool:
    for segment in _active_segments(manifest):
        positions = segment.get("resolved_mlc_positions_mm")
        if positions in (None, {}):
            continue
        if not isinstance(positions, Mapping):
            return False
        bank_a = positions.get("bank_a")
        bank_b = positions.get("bank_b")
        if not isinstance(bank_a, list) or not isinstance(bank_b, list):
            return False
        if len(bank_a) != len(bank_b):
            return False
        for a_value, b_value in zip(bank_a, bank_b, strict=True):
            if isinstance(a_value, bool) or isinstance(b_value, bool):
                return False
            try:
                a = float(a_value)
                b = float(b_value)
            except (TypeError, ValueError):
                return False
            if not math.isfinite(a) or not math.isfinite(b):
                return False
            if not math.isclose(a, -b, rel_tol=0.0, abs_tol=1.0e-9):
                return False
    return True


def require_reusable_gantry_geometry_contract(
    manifest: Mapping[str, Any],
    *,
    allow_legacy_zero_gantry: bool,
) -> str:
    contract = manifest.get(GANTRY_GEOMETRY_CONTRACT_FIELD)
    if contract == CURRENT_GANTRY_GEOMETRY_CONTRACT:
        return CURRENT_GANTRY_GEOMETRY_CONTRACT
    if (
        contract == PREVIOUS_GANTRY_GEOMETRY_CONTRACT
        and _has_only_reflection_invariant_mlcx(manifest)
    ):
        return PREVIOUS_GANTRY_GEOMETRY_CONTRACT
    if (
        contract is None
        and allow_legacy_zero_gantry
        and _has_only_explicit_zero_gantry(manifest)
        and _has_only_reflection_invariant_mlcx(manifest)
    ):
        return LEGACY_ZERO_GANTRY_CONTRACT
    raise GantryGeometryContractError(
        "PHITS beam geometry provenance is missing or predates the IEC gantry/MLCX "
        "corrections; prepare a new workspace and rerun PHITS before Sumtally or "
        "RTDOSE"
    )
