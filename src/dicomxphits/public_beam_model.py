from __future__ import annotations

import math
from typing import Any, Iterable

from dicomxphits.public_spectrum import (
    PUBLIC_BEAM_MODEL_DISPLAY_NAME,
    PUBLIC_BEAM_MODEL_ID,
    PUBLIC_BEAM_MODEL_IS_FIXED,
    PUBLIC_BEAM_MODEL_NOMINAL_ENERGY_MV,
    PUBLIC_BEAM_MODEL_RADIATION_TYPE,
)
from dicomxphits.rtplan_helpers import dcm_get
from dicomxphits.rtplan_state import beam_number


PUBLIC_BEAM_MODEL_EVIDENCE_FIELD = "public_beam_model"
_MISSING = object()


def _safe_dicom_text(value: Any, *, fallback: str) -> str:
    if value is _MISSING or value is None:
        return fallback
    text = "".join(
        character if character.isprintable() else " " for character in str(value)
    ).strip()
    if not text:
        return fallback
    return text[:80]


def _beam_label(beam: Any) -> tuple[int | None, str | None, str]:
    number = beam_number(beam)
    raw_name = dcm_get(beam, "BeamName", _MISSING)
    safe_name = _safe_dicom_text(raw_name, fallback="") or None
    number_text = "<missing>" if number is None else str(number)
    name_text = f' BeamName "{safe_name}"' if safe_name else ""
    return number, safe_name, f"BeamNumber {number_text}{name_text}"


def _incompatible(beam_label: str, detail: str) -> ValueError:
    return ValueError(
        f"RT Plan {beam_label} {detail}; supported beam model is fixed "
        f"{PUBLIC_BEAM_MODEL_DISPLAY_NAME}; no PHITS input was generated"
    )


def _parse_nominal_energy(
    value: Any,
    *,
    beam_label: str,
    control_point_index: int,
) -> float:
    if isinstance(value, bool):
        raise _incompatible(
            beam_label,
            f"control point {control_point_index} NominalBeamEnergy "
            f"{_safe_dicom_text(value, fallback='<invalid>')!r} is not numeric",
        )
    try:
        energy = float(value)
    except (TypeError, ValueError) as exc:
        raise _incompatible(
            beam_label,
            f"control point {control_point_index} NominalBeamEnergy "
            f"{_safe_dicom_text(value, fallback='<invalid>')!r} is not numeric",
        ) from exc
    if not math.isfinite(energy) or energy <= 0.0:
        raise _incompatible(
            beam_label,
            f"control point {control_point_index} NominalBeamEnergy "
            f"{_safe_dicom_text(value, fallback='<invalid>')!r} must be finite and positive",
        )
    return energy


def _validate_beam(beam: Any) -> dict[str, Any]:
    number, name, label = _beam_label(beam)
    raw_radiation_type = dcm_get(beam, "RadiationType", _MISSING)
    radiation_type = _safe_dicom_text(
        raw_radiation_type,
        fallback="<missing>",
    ).upper()
    if radiation_type != PUBLIC_BEAM_MODEL_RADIATION_TYPE:
        raise _incompatible(
            label,
            f"RadiationType {radiation_type!r} is not "
            f"{PUBLIC_BEAM_MODEL_RADIATION_TYPE}",
        )

    control_points = list(dcm_get(beam, "ControlPointSequence", []) or [])
    if not control_points:
        raise _incompatible(label, "has no ControlPointSequence")

    effective_energy: float | None = None
    used_inheritance = False
    for sequence_index, control_point in enumerate(control_points):
        raw_index = dcm_get(control_point, "ControlPointIndex", sequence_index)
        try:
            control_point_index = int(raw_index)
        except (TypeError, ValueError):
            control_point_index = sequence_index
        raw_energy = dcm_get(control_point, "NominalBeamEnergy", _MISSING)
        if raw_energy is _MISSING or raw_energy is None:
            if sequence_index == 0:
                raise _incompatible(
                    label,
                    "control point 0 is missing NominalBeamEnergy",
                )
            used_inheritance = True
            continue

        energy = _parse_nominal_energy(
            raw_energy,
            beam_label=label,
            control_point_index=control_point_index,
        )
        if effective_energy is not None and energy != effective_energy:
            raise _incompatible(
                label,
                f"NominalBeamEnergy changes from {effective_energy:g} MV to "
                f"{energy:g} MV at control point {control_point_index}",
            )
        if energy != PUBLIC_BEAM_MODEL_NOMINAL_ENERGY_MV:
            raise _incompatible(
                label,
                f"NominalBeamEnergy {energy:g} MV is incompatible with nominal "
                f"{PUBLIC_BEAM_MODEL_NOMINAL_ENERGY_MV:g} MV",
            )
        effective_energy = energy

    if effective_energy is None:
        raise _incompatible(label, "has no effective NominalBeamEnergy")

    return {
        "beam_number": number,
        "beam_name": name,
        "radiation_type": radiation_type,
        "nominal_energy_mv": effective_energy,
        "control_point_inheritance_used": used_inheritance,
    }


def validate_public_beam_model(
    rtplan: Any,
    *,
    included_beam_numbers: Iterable[int],
) -> dict[str, Any]:
    included = tuple(dict.fromkeys(int(number) for number in included_beam_numbers))
    if not included:
        raise ValueError(
            "Public beam model validation requires at least one included treatment beam; "
            "no PHITS input was generated"
        )

    beams_by_number: dict[int, list[Any]] = {}
    for beam in dcm_get(rtplan, "BeamSequence", []) or []:
        number = beam_number(beam)
        if number is not None:
            beams_by_number.setdefault(number, []).append(beam)

    evidence: list[dict[str, Any]] = []
    for number in included:
        matches = beams_by_number.get(number, [])
        if len(matches) != 1:
            detail = "is missing" if not matches else "is duplicated"
            raise ValueError(
                f"RT Plan BeamNumber {number} {detail}; supported beam model is fixed "
                f"{PUBLIC_BEAM_MODEL_DISPLAY_NAME}; no PHITS input was generated"
            )
        evidence.append(_validate_beam(matches[0]))

    return {
        "model_id": PUBLIC_BEAM_MODEL_ID,
        "display_name": PUBLIC_BEAM_MODEL_DISPLAY_NAME,
        "radiation_type": PUBLIC_BEAM_MODEL_RADIATION_TYPE,
        "nominal_energy_mv": PUBLIC_BEAM_MODEL_NOMINAL_ENERGY_MV,
        "fixed": PUBLIC_BEAM_MODEL_IS_FIXED,
        "validation_status": "passed",
        "included_treatment_beams": evidence,
    }
