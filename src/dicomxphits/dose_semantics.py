from __future__ import annotations

from copy import deepcopy
import io
from pathlib import Path
from typing import Any

import pydicom

from dicomxphits.safe_output import WorkspaceOutputGuard

from dicomxphits.public_dose_contract import PUBLIC_MODEL_TOTFACT_PER_MU_TEXT


RELATIVE_DOSE_NORMALIZATION_RULE = "phits_per_source_history_no_totfact"
RELATIVE_SUMTALLY_WEIGHTING_RULE = (
    "segment_mu_weighted_sum_divided_by_dose_normalization_mu"
)
ABSOLUTE_SUMTALLY_WEIGHTING_RULE = "active_segment_mu_weighted_sum"
RELATIVE_COMPARISON_RULE = (
    "both_operands_relative_no_rescaling_reference_global_max_denominator"
)
RELATIVE_DOSE_COMMENT = "RELATIVE: phits_per_source_history_no_totfact"
ABSOLUTE_DOSE_NORMALIZATION_RULE = (
    "approved_public_model_totfact_per_mu_applied_in_phits"
)
ABSOLUTE_DOSE_COMMENT = (
    "GY: public research model; "
    f"totfact_per_MU={PUBLIC_MODEL_TOTFACT_PER_MU_TEXT} source/MU"
)

_RELATIVE_DOSE_SEMANTICS: dict[str, Any] = {
    "mode": "relative",
    "dicom_dose_units": "RELATIVE",
    "absolute_calibration_approved": False,
    "absolute_dose_claim_authorized": False,
    "gy_per_mu_accuracy_claim_authorized": False,
    "totfact_per_mu_applied": False,
    "phits2dicom_factor": 1.0,
    "normalization_rule": RELATIVE_DOSE_NORMALIZATION_RULE,
    "sumtally_weighting_rule": RELATIVE_SUMTALLY_WEIGHTING_RULE,
    "comparison_rule": RELATIVE_COMPARISON_RULE,
}
_ABSOLUTE_DOSE_SEMANTICS: dict[str, Any] = {
    "mode": "absolute_public_reference_model",
    "dicom_dose_units": "GY",
    "absolute_calibration_approved": True,
    "absolute_dose_claim_authorized": True,
    "gy_per_mu_accuracy_claim_authorized": False,
    "totfact_per_mu_applied": True,
    "totfact_per_mu": PUBLIC_MODEL_TOTFACT_PER_MU_TEXT,
    "phits2dicom_factor": 1.0,
    "normalization_rule": ABSOLUTE_DOSE_NORMALIZATION_RULE,
    "sumtally_weighting_rule": ABSOLUTE_SUMTALLY_WEIGHTING_RULE,
    "comparison_rule": (
        "public_reference_model_absolute_dose_no_clinical_commissioning_claim"
    ),
}


def public_relative_dose_semantics() -> dict[str, Any]:
    return deepcopy(_RELATIVE_DOSE_SEMANTICS)


def public_absolute_dose_semantics() -> dict[str, Any]:
    return deepcopy(_ABSOLUTE_DOSE_SEMANTICS)


def require_absolute_units(
    *,
    input_dose_unit: str,
    output_dicom_dose_unit: str,
) -> None:
    if str(input_dose_unit).strip().upper() != "GY":
        raise ValueError("Public calibrated RTDOSE input_dose_unit must be GY")
    if str(output_dicom_dose_unit).strip().upper() != "GY":
        raise ValueError(
            "Public calibrated RTDOSE output_dicom_dose_unit must be GY"
        )


def require_relative_units(
    *,
    input_dose_unit: str,
    output_dicom_dose_unit: str,
) -> None:
    if str(input_dose_unit).strip().lower() != "relative":
        raise ValueError(
            "Public RTDOSE input_dose_unit must be relative until absolute calibration is approved"
        )
    if str(output_dicom_dose_unit).strip().lower() != "relative":
        raise ValueError(
            "Public RTDOSE output_dicom_dose_unit must be RELATIVE until absolute calibration is approved"
        )


def mark_rtdose_relative(path: Path) -> dict[str, Any]:
    ds = pydicom.dcmread(str(path))
    if str(getattr(ds, "Modality", "")).upper() != "RTDOSE":
        raise ValueError(f"Expected RTDOSE output before relative-dose labeling: {path}")
    previous_units = str(getattr(ds, "DoseUnits", "") or "")
    ds.DoseUnits = "RELATIVE"
    ds.DoseComment = RELATIVE_DOSE_COMMENT
    ds.save_as(str(path))
    return {
        "path": str(path),
        "previous_dose_units": previous_units,
        "dose_units": "RELATIVE",
        "dose_comment": RELATIVE_DOSE_COMMENT,
        "normalization_rule": RELATIVE_DOSE_NORMALIZATION_RULE,
    }


def mark_rtdose_absolute(
    path: Path, *, guard: WorkspaceOutputGuard | None = None
) -> dict[str, Any]:
    ds = pydicom.dcmread(str(path))
    if str(getattr(ds, "Modality", "")).upper() != "RTDOSE":
        raise ValueError(f"Expected RTDOSE output before absolute-dose labeling: {path}")
    previous_units = str(getattr(ds, "DoseUnits", "") or "")
    ds.DoseUnits = "GY"
    ds.DoseComment = ABSOLUTE_DOSE_COMMENT
    if guard is None:
        ds.save_as(str(path))
    else:
        stream = io.BytesIO()
        ds.save_as(stream)
        guard.write_bytes(path, stream.getvalue())
    return {
        "path": str(path),
        "previous_dose_units": previous_units,
        "dose_units": "GY",
        "dose_comment": ABSOLUTE_DOSE_COMMENT,
        "normalization_rule": ABSOLUTE_DOSE_NORMALIZATION_RULE,
    }


def require_relative_rtdose(path: Path, *, role: str) -> dict[str, Any]:
    ds = pydicom.dcmread(str(path), stop_before_pixels=True)
    modality = str(getattr(ds, "Modality", "") or "").upper()
    dose_units = str(getattr(ds, "DoseUnits", "") or "").upper()
    if modality != "RTDOSE":
        raise ValueError(f"{role} must be an RTDOSE DICOM: {path}")
    if dose_units != "RELATIVE":
        raise ValueError(
            f"{role} DoseUnits must be RELATIVE for public relative-dose comparison: {path}"
        )
    return {
        "role": role,
        "path": str(path),
        "modality": modality,
        "dose_units": dose_units,
    }
