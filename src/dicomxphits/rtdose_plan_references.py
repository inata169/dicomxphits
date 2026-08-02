from __future__ import annotations

import hashlib
import math
from pathlib import Path
from typing import Any

import pydicom
from pydicom.dataset import Dataset
from pydicom.sequence import Sequence
from pydicom.uid import RTPlanStorage

from dicomxphits.prepare_sumtally import load_json_object
from dicomxphits.rtplan_manifest_construction import build_manifest
from dicomxphits.sumtally_inputs import file_sha256, manifest_sha256


PLAN_SUMMATION_TYPE = "PLAN"
MANIFEST_SCHEMA_VERSION = "segment_manifest_v2"
MU_TOLERANCE = 1.0e-6
CT2PHITS_MANIFEST_NAME = "ct2phits_workspace_manifest.json"


def _required_text(dataset: Dataset, name: str, *, label: str) -> str:
    value = str(getattr(dataset, name, "") or "").strip()
    if not value:
        raise ValueError(f"{label} is missing required {name}")
    return value


def _positive_int(value: Any, *, label: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{label} must be a positive integer")
    try:
        result = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} must be a positive integer") from exc
    if result <= 0:
        raise ValueError(f"{label} must be a positive integer")
    return result


def _finite_positive(value: Any, *, label: str) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} must be a finite positive number") from exc
    if not math.isfinite(result) or result <= 0.0:
        raise ValueError(f"{label} must be a finite positive number")
    return result


def _finite_nonnegative(value: Any, *, label: str) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} must be a finite nonnegative number") from exc
    if not math.isfinite(result) or result < 0.0:
        raise ValueError(f"{label} must be a finite nonnegative number")
    return result


def _close_mu(actual: float, expected: float) -> bool:
    return math.isclose(actual, expected, rel_tol=0.0, abs_tol=MU_TOLERANCE)


def _referenced_plan_beams(
    rtplan: Dataset,
) -> tuple[dict[int, float], dict[int, float], list[int]]:
    beam_delivery_types: dict[int, str] = {}
    for index, beam in enumerate(getattr(rtplan, "BeamSequence", []) or [], start=1):
        number = _positive_int(
            getattr(beam, "BeamNumber", None),
            label=f"RT Plan BeamSequence item {index} BeamNumber",
        )
        if number in beam_delivery_types:
            raise ValueError(f"RT Plan contains duplicate BeamNumber {number}")
        beam_delivery_types[number] = str(
            getattr(beam, "TreatmentDeliveryType", "") or ""
        ).upper()

    fraction_groups = list(getattr(rtplan, "FractionGroupSequence", []) or [])
    if not fraction_groups:
        raise ValueError("RT Plan has no FractionGroupSequence")

    treatment_metersets: dict[int, float] = {}
    non_treatment_metersets: dict[int, float] = {}
    referenced_numbers: set[int] = set()
    fraction_group_numbers: list[int] = []
    for group_index, group in enumerate(fraction_groups, start=1):
        group_number = _positive_int(
            getattr(group, "FractionGroupNumber", group_index),
            label=f"RT Plan fraction group {group_index} number",
        )
        fraction_group_numbers.append(group_number)
        referenced_beams = list(getattr(group, "ReferencedBeamSequence", []) or [])
        if not referenced_beams:
            raise ValueError(
                f"RT Plan fraction group {group_number} has no ReferencedBeamSequence"
            )
        for item_index, referenced_beam in enumerate(referenced_beams, start=1):
            number = _positive_int(
                getattr(referenced_beam, "ReferencedBeamNumber", None),
                label=(
                    f"RT Plan fraction group {group_number} referenced beam "
                    f"item {item_index} number"
                ),
            )
            if number in referenced_numbers:
                raise ValueError(
                    f"RT Plan references BeamNumber {number} in more than one fraction group"
                )
            if number not in beam_delivery_types:
                raise ValueError(
                    f"RT Plan fraction group references missing BeamNumber {number}"
                )
            delivery_type = beam_delivery_types[number]
            meterset_parser = (
                _finite_positive
                if delivery_type in {"", "TREATMENT", "CONTINUATION"}
                else _finite_nonnegative
            )
            meterset = meterset_parser(
                getattr(referenced_beam, "BeamMeterset", None),
                label=f"RT Plan BeamNumber {number} BeamMeterset",
            )
            referenced_numbers.add(number)
            if delivery_type in {
                "",
                "TREATMENT",
                "CONTINUATION",
            }:
                treatment_metersets[number] = meterset
            else:
                non_treatment_metersets[number] = meterset
    if not treatment_metersets:
        raise ValueError("RT Plan has no treatment-eligible referenced beams")
    return treatment_metersets, non_treatment_metersets, fraction_group_numbers


def _reconstructed_geometry_binding(
    *,
    rtplan: Dataset,
    manifest: dict[str, Any],
) -> dict[str, Any]:
    segments = manifest.get("segments")
    sampling_policy = manifest.get("rtplan_sampling")
    tolerances = manifest.get("tolerances")
    if not isinstance(segments, list) or not isinstance(sampling_policy, dict):
        raise ValueError(
            "Frozen RT Plan SHA-256 evidence is missing and the segment manifest "
            "cannot reconstruct RT Plan geometry; rerun CT2PHITS and workspace "
            "preparation"
        )
    if not isinstance(tolerances, dict):
        raise ValueError(
            "Frozen RT Plan SHA-256 evidence is missing and manifest tolerances "
            "are unavailable; rerun CT2PHITS and workspace preparation"
        )
    output_names = {
        Path(str(segment.get("expected_output_path") or "").replace("\\", "/")).name
        for segment in segments
        if isinstance(segment, dict) and segment.get("expected_output_path")
    }
    if len(output_names) != 1:
        raise ValueError(
            "Frozen RT Plan SHA-256 evidence is missing and the segment output "
            "contract is ambiguous; rerun CT2PHITS and workspace preparation"
        )
    try:
        reconstructed, _beam_rows, _cp_rows = build_manifest(
            rtplan,
            case_id=str(manifest.get("case_id") or ""),
            workflow_mode=str(manifest.get("workflow_mode") or ""),
            include_beams=None,
            dose_normalization_mu=_finite_positive(
                manifest.get("dose_normalization_mu"),
                label="Segment manifest dose_normalization_mu",
            ),
            output_name=next(iter(output_names)),
            sampling_policy=sampling_policy,
            tolerances=tolerances,
            sampling_config_path=(
                str(manifest.get("sampling_config_path"))
                if manifest.get("sampling_config_path") is not None
                else None
            ),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(
            "Frozen RT Plan geometry could not be reconstructed from the "
            "segment manifest"
        ) from exc
    reconstructed_segments = reconstructed.get("segments")
    if not isinstance(reconstructed_segments, list):
        raise ValueError("Reconstructed RT Plan manifest is missing segments")
    recorded_geometry = [
        {key: value for key, value in segment.items() if key != "phits_input_path"}
        for segment in segments
        if isinstance(segment, dict)
    ]
    reconstructed_geometry = [
        {key: value for key, value in segment.items() if key != "phits_input_path"}
        for segment in reconstructed_segments
        if isinstance(segment, dict)
    ]
    if len(recorded_geometry) != len(segments) or len(reconstructed_geometry) != len(
        reconstructed_segments
    ):
        raise ValueError("RT Plan segment geometry contains an invalid segment record")
    if reconstructed_geometry != recorded_geometry:
        raise ValueError(
            "Frozen RT Plan segment geometry does not match the prepared manifest"
        )
    segment_geometry_sha256 = manifest_sha256({"segments": recorded_geometry})
    return {
        "mode": "reconstructed_segment_geometry",
        "segment_geometry_sha256": segment_geometry_sha256,
        "validated": True,
    }


def validate_frozen_rtplan_binding(
    *,
    rtplan_path: Path,
    rtplan: Dataset,
    manifest: dict[str, Any],
) -> dict[str, Any]:
    ct2phits_manifest_path = rtplan_path.resolve().parent / CT2PHITS_MANIFEST_NAME
    if not ct2phits_manifest_path.is_file():
        return _reconstructed_geometry_binding(rtplan=rtplan, manifest=manifest)
    ct2phits_manifest = load_json_object(ct2phits_manifest_path)
    if ct2phits_manifest.get("status") != "completed":
        raise ValueError("CT2PHITS frozen RT Plan manifest is not completed")
    rtplan_record = ct2phits_manifest.get("rtplan")
    if not isinstance(rtplan_record, dict):
        raise ValueError("CT2PHITS manifest is missing frozen RT Plan evidence")
    snapshot_value = str(rtplan_record.get("snapshot_path") or "")
    expected_sha256 = str(rtplan_record.get("sha256") or "")
    if not snapshot_value or not expected_sha256:
        raise ValueError("CT2PHITS manifest is missing frozen RT Plan SHA-256 evidence")
    recorded_snapshot = (ct2phits_manifest_path.parent / snapshot_value).resolve()
    if recorded_snapshot != rtplan_path.resolve():
        raise ValueError("RTDOSE RT Plan is not the CT2PHITS frozen snapshot")
    current_sha256 = file_sha256(rtplan_path)
    if current_sha256 != expected_sha256:
        raise ValueError(
            "Frozen RT Plan content does not match CT2PHITS SHA-256 evidence"
        )
    return {
        "mode": "ct2phits_snapshot_sha256",
        "ct2phits_manifest_path": str(ct2phits_manifest_path),
        "rtplan_sha256": current_sha256,
        "validated": True,
    }


def validate_full_plan_context(
    *,
    rtplan_path: Path,
    workspace_root: Path,
    ct_reference_path: Path,
) -> dict[str, Any]:
    if not rtplan_path.is_file():
        raise FileNotFoundError(f"Frozen RT Plan DICOM not found: {rtplan_path}")
    if not ct_reference_path.is_file():
        raise FileNotFoundError(f"CT reference DICOM not found: {ct_reference_path}")

    rtplan = pydicom.dcmread(str(rtplan_path), stop_before_pixels=True)
    modality = _required_text(rtplan, "Modality", label="Frozen RT Plan").upper()
    if modality != "RTPLAN":
        raise ValueError("Frozen RT Plan input must have Modality RTPLAN")
    sop_class_uid = _required_text(rtplan, "SOPClassUID", label="Frozen RT Plan")
    if sop_class_uid != str(RTPlanStorage):
        raise ValueError("Frozen RT Plan input must use RT Plan Storage SOP Class")
    sop_instance_uid = _required_text(
        rtplan, "SOPInstanceUID", label="Frozen RT Plan"
    )
    frame_uid = _required_text(
        rtplan, "FrameOfReferenceUID", label="Frozen RT Plan"
    )

    ct = pydicom.dcmread(str(ct_reference_path), stop_before_pixels=True)
    if _required_text(ct, "Modality", label="CT reference").upper() != "CT":
        raise ValueError("RTDOSE CT reference input must have Modality CT")
    ct_frame_uid = _required_text(
        ct, "FrameOfReferenceUID", label="CT reference"
    )
    if ct_frame_uid != frame_uid:
        raise ValueError(
            "Frozen RT Plan and CT reference FrameOfReferenceUID values do not match"
        )

    manifest_path = workspace_root / "segments" / "segment_manifest.json"
    manifest = load_json_object(manifest_path)
    if manifest.get("schema_version") != MANIFEST_SCHEMA_VERSION:
        raise ValueError(
            f"RTDOSE requires {MANIFEST_SCHEMA_VERSION} segment manifest evidence"
        )
    if manifest.get("workflow_mode") != "full_plan":
        raise ValueError("RTDOSE PLAN output requires workflow_mode full_plan")
    if str(manifest.get("plan_uid") or "") != sop_instance_uid:
        raise ValueError("Frozen RT Plan SOPInstanceUID does not match segment manifest plan_uid")
    rtplan_binding = validate_frozen_rtplan_binding(
        rtplan_path=rtplan_path,
        rtplan=rtplan,
        manifest=manifest,
    )

    (
        expected_metersets,
        non_treatment_metersets,
        fraction_group_numbers,
    ) = _referenced_plan_beams(rtplan)
    all_referenced_metersets = {
        **expected_metersets,
        **non_treatment_metersets,
    }
    segments = manifest.get("segments")
    if not isinstance(segments, list) or not segments:
        raise ValueError("Full-plan segment manifest has no segments")

    active_mu: dict[int, float] = {}
    active_segment_counts: dict[int, int] = {}
    skipped_positive_mu: list[str] = []
    skipped_non_treatment_beams: set[int] = set()
    for index, segment in enumerate(segments, start=1):
        if not isinstance(segment, dict):
            raise ValueError(f"Segment manifest item {index} must be an object")
        number = _positive_int(
            segment.get("beam_number"),
            label=f"Segment manifest item {index} beam_number",
        )
        segment_mu = _finite_nonnegative(
            segment.get("segment_mu"),
            label=f"Segment manifest item {index} segment_mu",
        )
        if number not in all_referenced_metersets:
            raise ValueError(
                f"Segment manifest item {index} references BeamNumber {number} "
                "outside the RT Plan fraction groups"
            )
        if segment.get("skip_reason"):
            if segment_mu > MU_TOLERANCE:
                skipped_positive_mu.append(str(segment.get("segment_id") or index))
            if number in non_treatment_metersets:
                declared_beam_mu = _finite_nonnegative(
                    segment.get("beam_meterset_mu"),
                    label=f"Segment manifest item {index} beam_meterset_mu",
                )
                if not _close_mu(
                    declared_beam_mu,
                    non_treatment_metersets[number],
                ):
                    raise ValueError(
                        f"Skipped non-treatment BeamNumber {number} meterset "
                        "does not match the frozen RT Plan"
                    )
                skipped_non_treatment_beams.add(number)
            continue
        if segment_mu <= 0.0:
            raise ValueError(
                f"Active segment manifest item {index} segment_mu must be positive"
            )
        declared_beam_mu = _finite_positive(
            segment.get("beam_meterset_mu"),
            label=f"Segment manifest item {index} beam_meterset_mu",
        )
        expected_beam_mu = expected_metersets.get(number)
        if expected_beam_mu is None:
            raise ValueError(
                f"Active segment references non-treatment BeamNumber {number}"
            )
        if not _close_mu(declared_beam_mu, expected_beam_mu):
            raise ValueError(
                f"Segment manifest BeamNumber {number} meterset does not match the frozen RT Plan"
            )
        active_mu[number] = active_mu.get(number, 0.0) + segment_mu
        active_segment_counts[number] = active_segment_counts.get(number, 0) + 1

    if skipped_positive_mu:
        raise ValueError(
            "Full-plan manifest contains skipped positive-MU segments: "
            + ", ".join(skipped_positive_mu)
        )
    if skipped_non_treatment_beams != set(non_treatment_metersets):
        raise ValueError(
            "Non-treatment RT Plan beams must be represented only by skipped "
            "zero-MU manifest segments"
        )
    if set(active_mu) != set(expected_metersets):
        raise ValueError(
            "Active segment beam coverage does not match the frozen RT Plan treatment beams"
        )
    for number, expected_mu in expected_metersets.items():
        if not _close_mu(active_mu[number], expected_mu):
            raise ValueError(
                f"Active segment MU for BeamNumber {number} does not match the frozen RT Plan"
            )

    treatment_total_mu = sum(expected_metersets.values())
    referenced_plan_total_mu = sum(all_referenced_metersets.values())
    for key in ("plan_total_mu", "included_total_mu", "dose_normalization_mu"):
        value = _finite_positive(manifest.get(key), label=f"Segment manifest {key}")
        if not _close_mu(value, referenced_plan_total_mu):
            raise ValueError(
                f"Segment manifest {key} does not match frozen RT Plan referenced "
                "beam total meterset"
            )

    return {
        "dose_summation_type": PLAN_SUMMATION_TYPE,
        "rtplan_path": str(rtplan_path.resolve()),
        "referenced_sop_class_uid": sop_class_uid,
        "referenced_sop_instance_uid": sop_instance_uid,
        "frame_of_reference_uid": frame_uid,
        "fraction_group_numbers": fraction_group_numbers,
        "referenced_beam_numbers": sorted(expected_metersets),
        "referenced_beam_metersets": {
            str(number): expected_metersets[number]
            for number in sorted(expected_metersets)
        },
        "skipped_non_treatment_beam_numbers": sorted(non_treatment_metersets),
        "skipped_non_treatment_beam_metersets": {
            str(number): non_treatment_metersets[number]
            for number in sorted(non_treatment_metersets)
        },
        "active_segment_counts": {
            str(number): active_segment_counts[number]
            for number in sorted(active_segment_counts)
        },
        "treatment_total_mu": treatment_total_mu,
        "plan_total_mu": referenced_plan_total_mu,
        "dose_normalization_mu": referenced_plan_total_mu,
        "rtplan_binding": rtplan_binding,
        "manifest_path": str(manifest_path),
        "manifest_sha256": manifest_sha256(manifest),
        "workflow_mode": "full_plan",
        "coverage_validated": True,
    }


def _pixel_sha256(dataset: Dataset) -> str:
    pixel_data = getattr(dataset, "PixelData", None)
    if pixel_data is None:
        raise ValueError("RTDOSE is missing PixelData")
    return hashlib.sha256(bytes(pixel_data)).hexdigest()


def _geometry_snapshot(dataset: Dataset) -> dict[str, Any]:
    names = (
        "NumberOfFrames",
        "Rows",
        "Columns",
        "PixelSpacing",
        "GridFrameOffsetVector",
        "ImagePositionPatient",
        "ImageOrientationPatient",
        "FrameOfReferenceUID",
        "DoseGridScaling",
        "DoseUnits",
    )
    return {
        name: str(getattr(dataset, name, ""))
        for name in names
    }


def validate_plan_rtdose(
    path: Path,
    *,
    plan_evidence: dict[str, Any],
) -> dict[str, Any]:
    dataset = pydicom.dcmread(str(path), stop_before_pixels=True)
    if str(getattr(dataset, "Modality", "") or "").upper() != "RTDOSE":
        raise ValueError("Final output must have Modality RTDOSE")
    if str(getattr(dataset, "DoseUnits", "") or "").upper() != "GY":
        raise ValueError("Final RTDOSE DoseUnits must be GY")
    if str(getattr(dataset, "DoseSummationType", "") or "").upper() != PLAN_SUMMATION_TYPE:
        raise ValueError("Final RTDOSE DoseSummationType must be PLAN")
    frame_uid = _required_text(dataset, "FrameOfReferenceUID", label="Final RTDOSE")
    if frame_uid != str(plan_evidence["frame_of_reference_uid"]):
        raise ValueError("Final RTDOSE FrameOfReferenceUID does not match the frozen RT Plan")

    references = list(getattr(dataset, "ReferencedRTPlanSequence", []) or [])
    if len(references) != 1:
        raise ValueError("Final RTDOSE must contain exactly one ReferencedRTPlanSequence item")
    reference = references[0]
    referenced_class = _required_text(
        reference, "ReferencedSOPClassUID", label="Final RTDOSE plan reference"
    )
    referenced_instance = _required_text(
        reference, "ReferencedSOPInstanceUID", label="Final RTDOSE plan reference"
    )
    if referenced_class != str(plan_evidence["referenced_sop_class_uid"]):
        raise ValueError("Final RTDOSE references the wrong RT Plan SOP Class UID")
    if referenced_instance != str(plan_evidence["referenced_sop_instance_uid"]):
        raise ValueError("Final RTDOSE references the wrong RT Plan SOP Instance UID")
    if getattr(reference, "ReferencedFractionGroupSequence", None):
        raise ValueError("PLAN RTDOSE must not retain a fraction-group reference hierarchy")
    if getattr(reference, "ReferencedBeamSequence", None):
        raise ValueError("PLAN RTDOSE must not retain a beam reference hierarchy")
    if getattr(dataset, "ReferencedFractionGroupSequence", None):
        raise ValueError("PLAN RTDOSE must not contain a top-level fraction-group reference")
    if getattr(dataset, "ReferencedBeamSequence", None):
        raise ValueError("PLAN RTDOSE must not contain a top-level beam reference")

    return {
        "path": str(path),
        "dose_summation_type": PLAN_SUMMATION_TYPE,
        "referenced_rtplan_item_count": 1,
        "referenced_sop_class_uid": referenced_class,
        "referenced_sop_instance_uid": referenced_instance,
        "frame_of_reference_uid": frame_uid,
        "dose_units": "GY",
        "validated": True,
    }


def synchronize_plan_rtdose(
    path: Path,
    *,
    plan_evidence: dict[str, Any],
) -> dict[str, Any]:
    dataset = pydicom.dcmread(str(path))
    if str(getattr(dataset, "Modality", "") or "").upper() != "RTDOSE":
        raise ValueError("Plan reference synchronization requires Modality RTDOSE")
    frame_uid = _required_text(dataset, "FrameOfReferenceUID", label="Converted RTDOSE")
    if frame_uid != str(plan_evidence["frame_of_reference_uid"]):
        raise ValueError("Converted RTDOSE FrameOfReferenceUID does not match the frozen RT Plan")

    pixel_sha256_before = _pixel_sha256(dataset)
    geometry_before = _geometry_snapshot(dataset)
    previous_summation_type = str(getattr(dataset, "DoseSummationType", "") or "")
    previous_references = list(getattr(dataset, "ReferencedRTPlanSequence", []) or [])

    reference = Dataset()
    reference.ReferencedSOPClassUID = str(plan_evidence["referenced_sop_class_uid"])
    reference.ReferencedSOPInstanceUID = str(plan_evidence["referenced_sop_instance_uid"])
    dataset.DoseSummationType = PLAN_SUMMATION_TYPE
    dataset.ReferencedRTPlanSequence = Sequence([reference])
    for name in ("ReferencedFractionGroupSequence", "ReferencedBeamSequence"):
        if hasattr(dataset, name):
            delattr(dataset, name)
    dataset.save_as(str(path))

    updated = pydicom.dcmread(str(path))
    pixel_sha256_after = _pixel_sha256(updated)
    geometry_after = _geometry_snapshot(updated)
    if pixel_sha256_after != pixel_sha256_before:
        raise ValueError("RTDOSE PixelData changed during plan reference synchronization")
    if geometry_after != geometry_before:
        raise ValueError("RTDOSE dose or geometry fields changed during plan reference synchronization")
    validation = validate_plan_rtdose(path, plan_evidence=plan_evidence)
    return {
        "path": str(path),
        "previous_dose_summation_type": previous_summation_type,
        "previous_referenced_rtplan_item_count": len(previous_references),
        "dose_summation_type": PLAN_SUMMATION_TYPE,
        "referenced_sop_class_uid": str(plan_evidence["referenced_sop_class_uid"]),
        "referenced_sop_instance_uid": str(plan_evidence["referenced_sop_instance_uid"]),
        "pixel_data_sha256_before": pixel_sha256_before,
        "pixel_data_sha256_after": pixel_sha256_after,
        "invariants": {
            "pixel_data_preserved": True,
            "dose_and_geometry_fields_preserved": True,
        },
        "validation": validation,
    }
