from __future__ import annotations

from typing import Any


MLC_PREFIXES = ("MLC",)


def dcm_get(obj: Any, name: str, default: Any = None) -> Any:
    return getattr(obj, name, default)


def as_float(value: Any, default: float | None = None) -> float | None:
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def as_int(value: Any, default: int | None = None) -> int | None:
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def as_float_list(values: Any) -> list[float]:
    if values is None:
        return []
    try:
        return [float(v) for v in list(values)]
    except (TypeError, ValueError):
        return []


def exact_decimal_text(value: Any) -> str | None:
    """Preserve a DICOM DS source lexeme without passing through float."""

    original = getattr(value, "original_string", None)
    if original is not None:
        return str(original)
    if isinstance(value, bool) or isinstance(value, float) or value is None:
        return None
    return str(value)


def as_exact_decimal_text_list(values: Any) -> list[str | None]:
    if values is None:
        return []
    try:
        return [exact_decimal_text(value) for value in list(values)]
    except TypeError:
        return []


def is_mlc_device(device_type: str) -> bool:
    return any(device_type.startswith(prefix) for prefix in MLC_PREFIXES)


def beam_leaf_pair_counts(beam: Any) -> dict[str, int]:
    counts: dict[str, int] = {}
    for device in dcm_get(beam, "BeamLimitingDeviceSequence", []) or []:
        dtype = str(dcm_get(device, "RTBeamLimitingDeviceType", "") or "")
        pair_count = as_int(dcm_get(device, "NumberOfLeafJawPairs"), None)
        if dtype and pair_count is not None:
            counts[dtype] = pair_count
    return counts


def beam_device_definition_counts(beam: Any) -> dict[str, int]:
    counts: dict[str, int] = {}
    for device in dcm_get(beam, "BeamLimitingDeviceSequence", []) or []:
        dtype = str(dcm_get(device, "RTBeamLimitingDeviceType", "") or "")
        if dtype:
            counts[dtype] = counts.get(dtype, 0) + 1
    return counts


def beam_leaf_position_boundaries(beam: Any) -> dict[str, list[float]]:
    boundaries: dict[str, list[float]] = {}
    for device in dcm_get(beam, "BeamLimitingDeviceSequence", []) or []:
        dtype = str(dcm_get(device, "RTBeamLimitingDeviceType", "") or "")
        if dtype and is_mlc_device(dtype):
            values = as_float_list(dcm_get(device, "LeafPositionBoundaries"))
            if values:
                boundaries[dtype] = values
    return boundaries


def beam_leaf_boundaries_decimal(beam: Any) -> dict[str, list[str | None]]:
    boundaries: dict[str, list[str | None]] = {}
    for device in dcm_get(beam, "BeamLimitingDeviceSequence", []) or []:
        dtype = str(dcm_get(device, "RTBeamLimitingDeviceType", "") or "")
        if dtype and is_mlc_device(dtype):
            boundaries[dtype] = as_exact_decimal_text_list(
                dcm_get(device, "LeafPositionBoundaries")
            )
    return boundaries
