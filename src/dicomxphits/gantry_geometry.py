from __future__ import annotations

from typing import Any, Mapping


GANTRY_GEOMETRY_CONTRACT_FIELD = "gantry_geometry_contract"
PREVIOUS_GANTRY_GEOMETRY_CONTRACT = "dicomxphits_iec_gantry_mlcx_geometry_v3"
CURRENT_GANTRY_GEOMETRY_CONTRACT = (
    "dicomxphits_iec_gantry_mlcx_collimator_geometry_v4"
)


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


def require_reusable_gantry_geometry_contract(
    manifest: Mapping[str, Any],
) -> str:
    contract = manifest.get(GANTRY_GEOMETRY_CONTRACT_FIELD)
    if contract == CURRENT_GANTRY_GEOMETRY_CONTRACT:
        return CURRENT_GANTRY_GEOMETRY_CONTRACT
    raise GantryGeometryContractError(
        "PHITS results do not identify the corrected collimator rotation; prepare "
        "a new workspace and rerun PHITS before Sumtally or RTDOSE"
    )
