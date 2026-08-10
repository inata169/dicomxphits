from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import numpy as np
import pydicom
import pytest
from pydicom.dataset import Dataset, FileDataset
from pydicom.tag import Tag

PUBLIC_SRC = Path(__file__).resolve().parents[1] / "src"
if str(PUBLIC_SRC) not in sys.path:
    sys.path.insert(0, str(PUBLIC_SRC))
PUBLIC_ROOT = Path(__file__).resolve().parents[1]

import dicomxphits.prepare_rtdose as prepare_rtdose_module
from dicomxphits.prepare_3dcrt_workspace import ExternalToolPaths
from dicomxphits.dose_semantics import require_relative_rtdose
from dicomxphits.prepare_rtdose import (
    PHITS2DICOM_REQUIRED_TEMPLATE_TAGS,
    prepare_rtdose,
    run_rtdose,
    select_ct_reference,
)
from dicomxphits.sumtally_inputs import (
    ACTIVE_TREATMENT_INPUT_DOSE_STATE,
    ACTIVE_TREATMENT_SUMTALLY_NORMALIZATION,
    file_sha256,
    manifest_sha256,
    plan_mu_normalization_evidence,
)


def required_tag_value(tag: tuple[int, int], vr: str):
    if tag == (0x0028, 0x0009):
        return [Tag(0x3004, 0x000C)]
    if tag == (0x7FE0, 0x0010):
        return b"\x00\x00"
    if tag in {(0x0020, 0x0032), (0x0020, 0x0037), (0x0028, 0x0030), (0x3004, 0x000C)}:
        return ["0", "0", "0"] if tag != (0x0028, 0x0030) else ["1", "1"]
    if vr in {"US", "SS", "UL", "SL"}:
        return 0
    if vr in {"IS", "DS"}:
        return "0"
    if vr in {"FL", "FD"}:
        return 0.0
    if vr == "AT":
        return [Tag(0x3004, 0x000C)]
    if vr == "DA":
        return "20260101"
    if vr == "TM":
        return "000000"
    if vr == "UI":
        return "1.2.826.0.1.3680043.10.54321.1"
    if vr == "CS":
        return "SYNTHETIC"
    return "SYNTHETIC"


def add_phits2dicom_template_tags(ds: FileDataset) -> None:
    for tag in PHITS2DICOM_REQUIRED_TEMPLATE_TAGS:
        if tag in ds:
            continue
        vr = pydicom.datadict.dictionary_VR(tag)
        ds.add_new(tag, vr, required_tag_value(tag, vr))


def write_dicom(path: Path, *, modality: str = "CT", frame_uid: str = "1.2.3", study_uid: str = "1.2.4") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    file_meta = Dataset()
    sop_classes = {
        "CT": pydicom.uid.CTImageStorage,
        "RTDOSE": pydicom.uid.RTDoseStorage,
    }
    file_meta.MediaStorageSOPClassUID = sop_classes[modality]
    file_meta.MediaStorageSOPInstanceUID = f"{study_uid}.1"
    file_meta.TransferSyntaxUID = pydicom.uid.ExplicitVRLittleEndian
    ds = FileDataset(str(path), {}, file_meta=file_meta, preamble=b"\0" * 128)
    ds.SOPClassUID = file_meta.MediaStorageSOPClassUID
    ds.SOPInstanceUID = file_meta.MediaStorageSOPInstanceUID
    ds.Modality = modality
    ds.FrameOfReferenceUID = frame_uid
    ds.StudyInstanceUID = study_uid
    ds.ImagePositionPatient = ["1.0", "2.0", "3.0"]
    if modality == "RTDOSE":
        add_phits2dicom_template_tags(ds)
    ds.save_as(str(path))


def write_rtplan(
    path: Path,
    *,
    sop_instance_uid: str = "1.2.826.0.1.3680043.10.54321.9001",
    frame_uid: str = "1.2.3",
    beam_metersets: dict[int, float] | None = None,
    treatment_delivery_type: str | None = "TREATMENT",
) -> Path:
    metersets = beam_metersets or {1: 100.0}
    path.parent.mkdir(parents=True, exist_ok=True)
    file_meta = Dataset()
    file_meta.MediaStorageSOPClassUID = pydicom.uid.RTPlanStorage
    file_meta.MediaStorageSOPInstanceUID = sop_instance_uid
    file_meta.TransferSyntaxUID = pydicom.uid.ExplicitVRLittleEndian
    ds = FileDataset(str(path), {}, file_meta=file_meta, preamble=b"\0" * 128)
    ds.SOPClassUID = file_meta.MediaStorageSOPClassUID
    ds.SOPInstanceUID = sop_instance_uid
    ds.Modality = "RTPLAN"
    ds.FrameOfReferenceUID = frame_uid
    ds.BeamSequence = []
    referenced_beams = []
    for number, meterset in metersets.items():
        beam = Dataset()
        beam.BeamNumber = number
        if treatment_delivery_type is not None:
            beam.TreatmentDeliveryType = treatment_delivery_type
        control_point = Dataset()
        control_point.IsocenterPosition = [10.0, -20.0, 30.0]
        beam.ControlPointSequence = [control_point]
        ds.BeamSequence.append(beam)
        reference = Dataset()
        reference.ReferencedBeamNumber = number
        reference.BeamMeterset = meterset
        referenced_beams.append(reference)
    fraction_group = Dataset()
    fraction_group.FractionGroupNumber = 1
    fraction_group.ReferencedBeamSequence = referenced_beams
    ds.FractionGroupSequence = [fraction_group]
    ds.save_as(str(path))
    return path


def write_rtplan_snapshot_evidence(rtplan_path: Path) -> None:
    manifest_path = rtplan_path.parent / "ct2phits_workspace_manifest.json"
    manifest = {
        "status": "completed",
        "rtplan": {
            "snapshot_path": rtplan_path.name,
            "sha256": file_sha256(rtplan_path),
        },
    }
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")


def tally_output_text(body: str = "") -> str:
    return (
        "[ T-Deposit ]\n"
        "  xmin = -0.7\n"
        "  xmax = 0.5\n"
        "  nx = 4\n"
        "  ymin = -0.3\n"
        "  ymax = 0.1\n"
        "  ny = 2\n"
        "  zmin = -0.9\n"
        "  zmax = 0.3\n"
        "  nz = 3\n"
        f"{body}"
    )


def write_coordinate_rtdose(path: Path) -> None:
    write_dicom(path, modality="RTDOSE")
    ds = pydicom.dcmread(str(path))
    ds.NumberOfFrames = 3
    ds.Rows = 2
    ds.Columns = 4
    ds.PixelSpacing = [2.0, 3.0]
    ds.GridFrameOffsetVector = [0.0, 4.0, 8.0]
    ds.ImageOrientationPatient = [1.0, 0.0, 0.0, 0.0, 1.0, 0.0]
    ds.ImagePositionPatient = [-4.0, -5.0, -6.0]
    ds.SamplesPerPixel = 1
    ds.PhotometricInterpretation = "MONOCHROME2"
    ds.BitsAllocated = 16
    ds.BitsStored = 16
    ds.HighBit = 15
    ds.PixelRepresentation = 0
    ds.DoseGridScaling = 0.125
    ds.PixelData = np.arange(24, dtype=np.uint16).reshape(3, 2, 4).tobytes()
    ds.DoseSummationType = "BEAM"
    stale_plan = Dataset()
    stale_plan.ReferencedSOPClassUID = pydicom.uid.RTPlanStorage
    stale_plan.ReferencedSOPInstanceUID = "1.2.826.0.1.3680043.10.54321.9999"
    stale_group = Dataset()
    stale_group.ReferencedFractionGroupNumber = 99
    stale_beam = Dataset()
    stale_beam.ReferencedBeamNumber = 99
    stale_group.ReferencedBeamSequence = [stale_beam]
    stale_plan.ReferencedFractionGroupSequence = [stale_group]
    ds.ReferencedRTPlanSequence = [stale_plan]
    ds.save_as(str(path))


def paths(phits2dicom: str | None = None) -> ExternalToolPaths:
    return ExternalToolPaths(
        phits_root_folder="/opt/phits-root",
        phits_executable_path="/opt/phits-root/bin/phits",
        phits2dicom_executable_path=phits2dicom,
    )


def write_workspace(tmp_path: Path, *, beam_mu: bool = False, units: str = "GY") -> tuple[Path, dict]:
    workspace = tmp_path / "workspace"
    analysis = workspace / "analysis"
    analysis.mkdir(parents=True)
    plan_uid = "1.2.826.0.1.3680043.10.54321.9001"
    rtplan = write_rtplan(workspace / "RTPLAN.dcm", sop_instance_uid=plan_uid)
    write_rtplan_snapshot_evidence(rtplan)
    manifest = {
        "schema_version": "segment_manifest_v2",
        "case_id": "synthetic",
        "plan_uid": plan_uid,
        "workflow_mode": "full_plan",
        "plan_total_mu": 100.0,
        "included_total_mu": 100.0,
        "dose_normalization_mu": 100.0,
        "segments": [
            {
                "segment_id": "seg_b0001_s0000",
                "beam_number": 1,
                "beam_meterset_mu": 100.0,
                "segment_mu": 100.0,
                "mu_weight": 100.0,
                "mu_weight_unit": "MU",
                "delivery_type": "3dcrt_static",
                "skip_reason": None,
                "expected_output_path": "segments/seg_b0001_s0000/deposit-target-3D.out",
            }
        ],
    }
    manifest_path = workspace / "segments" / "segment_manifest.json"
    manifest_path.parent.mkdir(parents=True)
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    bound_manifest_sha256 = manifest_sha256(manifest)
    normalization_evidence = plan_mu_normalization_evidence(manifest)
    sumtally_output = workspace / "sumtally" / "deposit-target-3D_sum_all_active_segments_totalfield.out"
    sumtally_output.parent.mkdir(parents=True)
    sumtally_output.write_text(tally_output_text("merged dose\n"), encoding="utf-8")
    sum_input = workspace / "sumtally" / "segment_sum.inp"
    sum_input.write_text("generated wrapper", encoding="utf-8")
    sumtally_input = workspace / "sumtally" / "sumtally.inp"
    sumtally_input.write_text(
        "\n".join(
            [
                "sumtally start",
                "  isumtally = 2",
                "  sfile = deposit-target-3D_sum_all_active_segments_totalfield.out",
                f"  sumfactor = {normalization_evidence['sumfactor']:.12g}",
                "  nfile = 1",
                "  segments/seg_b0001_s0000/deposit-target-3D.out  100",
                "sumtally end",
                "",
            ]
        ),
        encoding="utf-8",
    )
    segment_output = (
        workspace / "segments" / "seg_b0001_s0000" / "deposit-target-3D.out"
    )
    segment_output.parent.mkdir(parents=True)
    segment_output.write_text(tally_output_text("segment dose\n"), encoding="utf-8")
    sum_input_sha256 = file_sha256(sum_input)
    sumtally_input_sha256 = file_sha256(sumtally_input)
    segment_output_evidence = [
        {"path": str(segment_output.resolve()), "sha256": file_sha256(segment_output)}
    ]
    wrapper_include_evidence = [
        {"path": str(sumtally_input.resolve()), "sha256": sumtally_input_sha256}
    ]
    phits_out = workspace / "sumtally" / "phits.out"
    phits_out.write_text("phits companion", encoding="utf-8")
    generation = {
        "stage_status": "success",
        "manifest_sha256": bound_manifest_sha256,
        "sum_input_sha256": sum_input_sha256,
        "sumtally_input_sha256": sumtally_input_sha256,
        "segment_output_evidence": segment_output_evidence,
        "wrapper_include_evidence": wrapper_include_evidence,
        "outputs": {
            "sumtally_output": str(sumtally_output),
            "sum_input": str(sum_input),
            "sumtally_input": str(sumtally_input),
        },
        "sumtally_normalization": (
            "beamMU" if beam_mu else ACTIVE_TREATMENT_SUMTALLY_NORMALIZATION
        ),
        "sumtally_normalization_evidence": normalization_evidence,
        "rt_dose_conversion_hint": (
            {
                "input_dose_state": "beam_mu",
                "sumtally_normalization": "beamMU",
                "is_beam_mu_output": True,
            }
            if beam_mu
            else {
                "input_dose_state": ACTIVE_TREATMENT_INPUT_DOSE_STATE,
                "input_dose_unit": "GY",
                "sumtally_normalization": ACTIVE_TREATMENT_SUMTALLY_NORMALIZATION,
                "is_beam_mu_output": False,
                "phits2dicom_factor": 1.0,
            }
        ),
    }
    execution = {
        "stage_status": "success",
        "manifest_sha256": bound_manifest_sha256,
        "sum_input_sha256": sum_input_sha256,
        "sumtally_input_sha256": sumtally_input_sha256,
        "segment_output_evidence": segment_output_evidence,
        "wrapper_include_evidence": wrapper_include_evidence,
        "sumtally_normalization": generation["sumtally_normalization"],
        "sumtally_normalization_evidence": normalization_evidence,
        "rt_dose_conversion_hint": generation["rt_dose_conversion_hint"],
        "expected_sumtally_output": str(sumtally_output),
        "expected_sumtally_output_updated_by_run": True,
        "expected_sumtally_output_sha256": file_sha256(sumtally_output),
        "outputs": {"phits_out": str(phits_out)},
        "input_dose_unit": units,
    }
    (analysis / "sumtally_generation_summary.json").write_text(json.dumps(generation), encoding="utf-8")
    (analysis / "sumtally_execution_summary.json").write_text(json.dumps(execution), encoding="utf-8")
    return workspace, {
        "sumtally_output": sumtally_output,
        "phits_out": phits_out,
        "rtplan": rtplan,
    }


def rewrite_sumtally_output_evidence(workspace: Path, output: Path) -> None:
    text = output.read_text(encoding="utf-8")
    if "xmin" not in text.lower():
        output.write_text(tally_output_text(text), encoding="utf-8")
    execution_path = workspace / "analysis" / "sumtally_execution_summary.json"
    execution = json.loads(execution_path.read_text(encoding="utf-8"))
    execution["expected_sumtally_output"] = str(output)
    execution["expected_sumtally_output_updated_by_run"] = True
    execution["expected_sumtally_output_sha256"] = file_sha256(output)
    execution_path.write_text(json.dumps(execution), encoding="utf-8")


def simulate_legacy_in_place_ipp_patch(
    workspace: Path,
    files: dict,
    *,
    newline: str,
) -> bytes:
    original_text = tally_output_text("  title = Synthetic legacy merged dose\n")
    if newline == "crlf":
        original_text = original_text.replace("\n", "\r\n")
    original = original_text.encode("utf-8")
    files["sumtally_output"].write_bytes(original)

    generation_path = workspace / "analysis" / "sumtally_generation_summary.json"
    execution_path = workspace / "analysis" / "sumtally_execution_summary.json"
    generation = json.loads(generation_path.read_text(encoding="utf-8"))
    execution = json.loads(execution_path.read_text(encoding="utf-8"))
    segment_path = Path(generation["segment_output_evidence"][0]["path"])
    segment_path.write_bytes(original)
    segment_sha256 = file_sha256(segment_path)
    for summary in (generation, execution):
        summary["segment_output_evidence"][0]["sha256"] = segment_sha256
    execution["expected_sumtally_output"] = str(files["sumtally_output"])
    execution["expected_sumtally_output_updated_by_run"] = True
    execution["expected_sumtally_output_sha256"] = file_sha256(
        files["sumtally_output"]
    )
    generation_path.write_text(json.dumps(generation), encoding="utf-8")
    execution_path.write_text(json.dumps(execution), encoding="utf-8")

    prepare_rtdose_module.patch_deposit_title_ipp(
        files["sumtally_output"],
        ipp=[1.0, 2.0, 3.0],
    )
    return files["sumtally_output"].read_bytes()


def rewrite_sumtally_manifest_digests(
    workspace: Path,
    manifest: dict,
) -> None:
    digest = manifest_sha256(manifest)
    for name in (
        "sumtally_generation_summary.json",
        "sumtally_execution_summary.json",
    ):
        path = workspace / "analysis" / name
        summary = json.loads(path.read_text(encoding="utf-8"))
        summary["manifest_sha256"] = digest
        path.write_text(json.dumps(summary), encoding="utf-8")


def add_non_treatment_setup_beam(
    workspace: Path,
    rtplan_path: Path,
    *,
    active: bool = False,
    setup_mu: float = 10.0,
) -> None:
    plan = pydicom.dcmread(str(rtplan_path))
    setup_beam = Dataset()
    setup_beam.BeamNumber = 2
    setup_beam.TreatmentDeliveryType = "SETUP"
    plan.BeamSequence.append(setup_beam)
    setup_reference = Dataset()
    setup_reference.ReferencedBeamNumber = 2
    setup_reference.BeamMeterset = setup_mu
    plan.FractionGroupSequence[0].ReferencedBeamSequence.append(setup_reference)
    plan.save_as(str(rtplan_path))
    write_rtplan_snapshot_evidence(rtplan_path)

    manifest_path = workspace / "segments" / "segment_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    referenced_total_mu = 100.0 + setup_mu
    manifest["plan_total_mu"] = referenced_total_mu
    manifest["included_total_mu"] = referenced_total_mu
    manifest["dose_normalization_mu"] = referenced_total_mu
    manifest["segments"].append(
        {
            "segment_id": "seg_b0002_s0000",
            "beam_number": 2,
            "beam_meterset_mu": setup_mu,
            "segment_mu": setup_mu if active else 0.0,
            "mu_weight": setup_mu if active else 0.0,
            "mu_weight_unit": "MU",
            "delivery_type": "unsupported",
            "skip_reason": (
                None
                if active
                else "delivery_type unsupported is not generation-capable"
            ),
        }
    )
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    rewrite_sumtally_manifest_digests(workspace, manifest)
    if not active and setup_mu >= 0.0:
        evidence = plan_mu_normalization_evidence(manifest)
        for name in (
            "sumtally_generation_summary.json",
            "sumtally_execution_summary.json",
        ):
            summary_path = workspace / "analysis" / name
            summary = json.loads(summary_path.read_text(encoding="utf-8"))
            summary["sumtally_normalization_evidence"] = evidence
            summary_path.write_text(json.dumps(summary), encoding="utf-8")


def test_prepare_rtdose_records_factor_one_contract_and_inputs(tmp_path):
    workspace, files = write_workspace(tmp_path)
    template = tmp_path / "template.dcm"
    ct = tmp_path / "ct_reference.dcm"
    write_dicom(template, modality="RTDOSE")
    write_dicom(ct, modality="CT")

    summary = prepare_rtdose(
        workspace_root=workspace,
        paths=paths(phits2dicom=None),
        paths_config={},
        template_dicom=template,
        ct_reference_dicom=ct,
        phits_out=files["phits_out"],
        command_argv=["prepare"],
    )

    assert summary["stage_status"] == "success"
    assert summary["input_dose_state"] == "sumtally_active_treatment_mu_sum"
    assert summary["sumtally_normalization"] == (
        "active_treatment_segments_totalfield_segment_mu_sum"
    )
    assert summary["is_beam_mu_output"] is False
    assert summary["input_dose_unit"] == "GY"
    assert summary["output_dicom_dose_unit"] == "GY"
    assert summary["factor"] == 1.0
    assert len(summary["phits_dose_sha256_after_prepare"]) == 64
    assert "Factor 1.0 selected" in summary["factor_selection_reason"]
    assert summary["dose_semantics"]["mode"] == "absolute_public_reference_model"
    assert summary["dose_semantics"]["dicom_dose_units"] == "GY"
    assert summary["dose_semantics"]["totfact_per_mu_applied"] is True
    assert summary["dose_semantics"]["totfact_per_mu"] == "8.7608E+11"
    assert summary["dose_semantics"]["normalization_rule"] == (
        "approved_public_model_totfact_per_mu_applied_in_phits"
    )
    assert summary["dose_semantics"]["comparison_rule"] == (
        "public_reference_model_absolute_dose_no_clinical_commissioning_claim"
    )
    assert summary["phits_dose_source_path"] == str(files["sumtally_output"].resolve())
    assert summary["phits_out_source_path"] == str(files["phits_out"].resolve())
    assert Path(summary["phits_dose"]).parent.name == "DATfiles"
    assert Path(summary["phits_out"]).parent.name == "DATfiles"
    assert summary["phits2dicom_inputs_are_workspace_copies"] is True
    assert summary["upstream_sources_unchanged"] is True
    assert all(
        record["unchanged_by_prepare"]
        for record in summary["upstream_source_evidence"].values()
        if isinstance(record, dict) and "unchanged_by_prepare" in record
    )
    assert summary["phits2dicom_input_path"].endswith("phits2dicom.inp")
    assert len(summary["phits2dicom_input_sha256"]) == 64
    referenced_inputs = summary["phits2dicom_referenced_input_evidence"]
    assert set(referenced_inputs) == {
        "template_dicom",
        "ct_reference",
        "phits_dose",
        "phits_out",
    }
    assert all(len(record["sha256"]) == 64 for record in referenced_inputs.values())
    assert summary["dat_dir"].endswith("DATfiles")
    assert summary["path_config"]["phits2dicom_executable_path"] is None
    assert summary["image_position_patient_patch"]["image_position_patient"] == [1.0, 2.0, 3.0]
    assert summary["template_dicom_preflight"]["missing_tag_count"] == 0


def test_prepare_rejects_legacy_sumtally_normalization_before_conversion(tmp_path):
    workspace, files = write_workspace(tmp_path)
    for name in (
        "sumtally_generation_summary.json",
        "sumtally_execution_summary.json",
    ):
        summary_path = workspace / "analysis" / name
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        summary.pop("sumtally_normalization_evidence")
        summary["sumtally_normalization"] = "all_segments_totalfield_segment_mu"
        summary["rt_dose_conversion_hint"] = {
            "input_dose_state": "sumtally_mu_weighted",
            "sumtally_normalization": "all_segments_totalfield_segment_mu",
            "is_beam_mu_output": False,
        }
        summary_path.write_text(json.dumps(summary), encoding="utf-8")
    template = tmp_path / "template.dcm"
    ct = tmp_path / "ct_reference.dcm"
    write_dicom(template, modality="RTDOSE")
    write_dicom(ct, modality="CT")

    with pytest.raises(ValueError, match="normalization evidence") as exc_info:
        prepare_rtdose(
            workspace_root=workspace,
            paths=paths(),
            paths_config={},
            template_dicom=template,
            ct_reference_dicom=ct,
            phits_out=files["phits_out"],
            command_argv=["prepare"],
        )

    message = str(exc_info.value)
    assert "Allow overwrite of downstream stage summaries" in message
    assert "PHITS does not need to be rerun" in message


@pytest.mark.parametrize(
    ("field", "value", "error"),
    [
        (
            "sumtally_normalization",
            "all_segments_totalfield_segment_mu",
            "Run normalization contract",
        ),
        (
            "rt_dose_conversion_hint",
            {"input_dose_state": "sumtally_mu_weighted"},
            "Run RTDOSE conversion hint",
        ),
    ],
)
def test_prepare_rejects_stale_sumtally_run_contract(
    tmp_path,
    field,
    value,
    error,
):
    workspace, files = write_workspace(tmp_path)
    execution_path = workspace / "analysis" / "sumtally_execution_summary.json"
    execution = json.loads(execution_path.read_text(encoding="utf-8"))
    execution[field] = value
    execution_path.write_text(json.dumps(execution), encoding="utf-8")
    template = tmp_path / "template.dcm"
    ct = tmp_path / "ct_reference.dcm"
    write_dicom(template, modality="RTDOSE")
    write_dicom(ct, modality="CT")

    with pytest.raises(ValueError, match=error):
        prepare_rtdose(
            workspace_root=workspace,
            paths=paths(),
            paths_config={},
            template_dicom=template,
            ct_reference_dicom=ct,
            phits_out=files["phits_out"],
            command_argv=["prepare"],
        )


def test_prepare_rejects_execution_normalization_evidence_mismatch(tmp_path):
    workspace, files = write_workspace(tmp_path)
    execution_path = workspace / "analysis" / "sumtally_execution_summary.json"
    execution = json.loads(execution_path.read_text(encoding="utf-8"))
    execution["sumtally_normalization_evidence"]["sumfactor"] = 1.0
    execution_path.write_text(json.dumps(execution), encoding="utf-8")
    template = tmp_path / "template.dcm"
    ct = tmp_path / "ct_reference.dcm"
    write_dicom(template, modality="RTDOSE")
    write_dicom(ct, modality="CT")

    with pytest.raises(ValueError, match="Run normalization evidence"):
        prepare_rtdose(
            workspace_root=workspace,
            paths=paths(),
            paths_config={},
            template_dicom=template,
            ct_reference_dicom=ct,
            phits_out=files["phits_out"],
            command_argv=["prepare"],
        )


def test_prepare_rejects_sumtally_output_replaced_after_run(tmp_path):
    workspace, files = write_workspace(tmp_path)
    files["sumtally_output"].write_text(
        "unrelated replacement dose",
        encoding="utf-8",
    )
    template = tmp_path / "template.dcm"
    ct = tmp_path / "ct_reference.dcm"
    write_dicom(template, modality="RTDOSE")
    write_dicom(ct, modality="CT")

    with pytest.raises(
        ValueError,
        match="does not match Sumtally Run evidence",
    ):
        prepare_rtdose(
            workspace_root=workspace,
            paths=paths(),
            paths_config={},
            template_dicom=template,
            ct_reference_dicom=ct,
            phits_out=files["phits_out"],
            command_argv=["prepare"],
        )


def test_prepare_rejects_template_missing_phits2dicom_overwrite_tags(tmp_path):
    workspace, files = write_workspace(tmp_path)
    template = tmp_path / "template.dcm"
    ct = tmp_path / "ct_reference.dcm"
    write_dicom(template, modality="RTDOSE")
    write_dicom(ct, modality="CT")
    ds = pydicom.dcmread(str(template), force=True)
    del ds.PixelData
    ds.save_as(str(template))

    with pytest.raises(ValueError, match="template preflight failed"):
        prepare_rtdose(
            workspace_root=workspace,
            paths=paths(),
            paths_config={},
            template_dicom=template,
            ct_reference_dicom=ct,
            phits_out=files["phits_out"],
            command_argv=["prepare"],
        )

    failure = json.loads((workspace / "analysis" / "rtdose_conversion_prepare_summary.json").read_text(encoding="utf-8"))
    assert failure["stage_status"] == "gate_failed"
    assert "PixelData" in failure["failure_reason"]


def test_prepare_allows_tags_absent_from_official_sample_template(tmp_path):
    workspace, files = write_workspace(tmp_path)
    template = tmp_path / "template.dcm"
    ct = tmp_path / "ct_reference.dcm"
    write_dicom(template, modality="RTDOSE")
    write_dicom(ct, modality="CT")
    ds = pydicom.dcmread(str(template), force=True)
    for attr in (
        "SliceThickness",
        "SpacingBetweenSlices",
        "SliceLocation",
        "RescaleIntercept",
        "RescaleSlope",
        "FrameReferenceTime",
        "ActualFrameDuration",
        "RadionuclideTotalDose",
        "RadionuclideHalfLife",
        "NumberOfSlices",
        "ImagesInAcquisition",
    ):
        if attr in ds:
            delattr(ds, attr)
    ds.save_as(str(template))

    summary = prepare_rtdose(
        workspace_root=workspace,
        paths=paths(),
        paths_config={},
        template_dicom=template,
        ct_reference_dicom=ct,
        phits_out=files["phits_out"],
        command_argv=["prepare"],
    )

    assert summary["stage_status"] == "success"
    assert summary["template_dicom_preflight"]["missing_tag_count"] == 0


def test_prepare_accepts_packaged_public_safe_template(tmp_path):
    workspace, files = write_workspace(tmp_path)
    template = PUBLIC_ROOT / "templates" / "phits2dicom_rtdose_template.dcm"
    ct = tmp_path / "ct_reference.dcm"
    write_dicom(ct, modality="CT")

    summary = prepare_rtdose(
        workspace_root=workspace,
        paths=paths(),
        paths_config={},
        template_dicom=template,
        ct_reference_dicom=ct,
        phits_out=files["phits_out"],
        command_argv=["prepare"],
    )

    copied = pydicom.dcmread(summary["template_dicom_workspace_copy_path"], force=True)
    assert summary["stage_status"] == "success"
    assert summary["template_dicom_preflight"]["missing_tag_count"] == 0
    assert str(copied.PatientName) == "SYNTHETIC^PATIENT"
    assert copied.PatientID == "SYNTHETIC_PATIENT_ID"
    assert set(bytes(copied.PixelData)) == {0}


def test_prepare_patches_workspace_deposit_titles_and_records_file_sizes(tmp_path):
    workspace, files = write_workspace(tmp_path)
    files["sumtally_output"].write_text(
        "[ T-Deposit ]\n"
        "  title = Synthetic merged dose\n"
        "  file = dose.out\n",
        encoding="utf-8",
    )
    rewrite_sumtally_output_evidence(workspace, files["sumtally_output"])
    files["phits_out"].write_text(
        "[ T-Deposit ]\n"
        "  title = Synthetic companion dose\n",
        encoding="utf-8",
    )
    template = tmp_path / "template.dcm"
    ct = tmp_path / "ct_reference.dcm"
    write_dicom(template, modality="RTDOSE")
    write_dicom(ct, modality="CT")

    summary = prepare_rtdose(
        workspace_root=workspace,
        paths=paths(),
        paths_config={},
        template_dicom=template,
        ct_reference_dicom=ct,
        phits_out=files["phits_out"],
        command_argv=["prepare"],
    )

    patch = summary["image_position_patient_patch"]
    assert patch["warnings"] == []
    for item in patch["files"]:
        assert item["patched_title_count"] == 1
        assert item["skipped_existing_ipp"] == 0
        assert item["file_size_after"] >= item["file_size_before"]
        assert item["content_changed"] is True
    assert "Synthetic merged dose" in files["sumtally_output"].read_text(encoding="utf-8")
    assert "Synthetic companion dose" in files["phits_out"].read_text(encoding="utf-8")
    assert "ImagePositionPatient  1.00000  2.00000  3.00000 mm" in Path(
        summary["phits_dose"]
    ).read_text(encoding="utf-8")
    assert "ImagePositionPatient  1.00000  2.00000  3.00000 mm" in Path(
        summary["phits_out"]
    ).read_text(encoding="utf-8")


@pytest.mark.parametrize("newline", ["lf", "crlf"])
def test_prepare_recovers_only_known_legacy_ipp_patch_without_sumtally_rerun(
    tmp_path,
    newline,
):
    workspace, files = write_workspace(tmp_path)
    current_legacy_bytes = simulate_legacy_in_place_ipp_patch(
        workspace,
        files,
        newline=newline,
    )
    execution = json.loads(
        (
            workspace / "analysis" / "sumtally_execution_summary.json"
        ).read_text(encoding="utf-8")
    )
    assert file_sha256(files["sumtally_output"]) != execution[
        "expected_sumtally_output_sha256"
    ]
    template = tmp_path / "template.dcm"
    ct = tmp_path / "ct_reference.dcm"
    write_dicom(template, modality="RTDOSE")
    write_dicom(ct, modality="CT")

    summary = prepare_rtdose(
        workspace_root=workspace,
        paths=paths(),
        paths_config={},
        template_dicom=template,
        ct_reference_dicom=ct,
        phits_out=files["phits_out"],
        command_argv=["prepare"],
    )

    integrity = summary["sumtally_manifest_binding"]["sumtally_output_integrity"]
    assert summary["stage_status"] == "success"
    assert integrity["status"] == "legacy_in_place_ipp_title_patch_recovered"
    assert integrity["recovery_applied"] is True
    assert integrity["recovered_sha256"] == execution[
        "expected_sumtally_output_sha256"
    ]
    assert files["sumtally_output"].read_bytes() == current_legacy_bytes
    assert summary["upstream_sources_unchanged"] is True
    assert "ImagePositionPatient  1.00000  2.00000  3.00000 mm" in Path(
        summary["phits_dose"]
    ).read_text(encoding="utf-8")


def test_prepare_rejects_legacy_ipp_patch_with_any_additional_change(tmp_path):
    workspace, files = write_workspace(tmp_path)
    current_legacy_bytes = simulate_legacy_in_place_ipp_patch(
        workspace,
        files,
        newline="crlf",
    )
    files["sumtally_output"].write_bytes(
        current_legacy_bytes + b"unexpected additional change\n"
    )
    template = tmp_path / "template.dcm"
    ct = tmp_path / "ct_reference.dcm"
    write_dicom(template, modality="RTDOSE")
    write_dicom(ct, modality="CT")

    with pytest.raises(
        ValueError,
        match="Sumtally output content does not match Sumtally Run evidence",
    ):
        prepare_rtdose(
            workspace_root=workspace,
            paths=paths(),
            paths_config={},
            template_dicom=template,
            ct_reference_dicom=ct,
            phits_out=files["phits_out"],
            command_argv=["prepare"],
        )


def test_prepare_rejects_workspace_external_phits_dose_or_out(tmp_path):
    workspace, files = write_workspace(tmp_path)
    external_dose = tmp_path / "outside_dose.out"
    external_dose.write_text("dose", encoding="utf-8")
    generation_path = workspace / "analysis" / "sumtally_generation_summary.json"
    generation = json.loads(generation_path.read_text(encoding="utf-8"))
    generation["outputs"]["sumtally_output"] = str(external_dose)
    generation_path.write_text(json.dumps(generation), encoding="utf-8")
    rewrite_sumtally_output_evidence(workspace, external_dose)
    template = tmp_path / "template.dcm"
    ct = tmp_path / "ct_reference.dcm"
    write_dicom(template, modality="RTDOSE")
    write_dicom(ct, modality="CT")

    with pytest.raises(ValueError, match="phits_dose must be inside workspace"):
        prepare_rtdose(
            workspace_root=workspace,
            paths=paths(),
            paths_config={},
            template_dicom=template,
            ct_reference_dicom=ct,
            phits_out=files["phits_out"],
            command_argv=["prepare"],
        )

    workspace, files = write_workspace(tmp_path / "external_out")
    external_out = tmp_path / "outside_phits.out"
    external_out.write_text("out", encoding="utf-8")
    with pytest.raises(ValueError, match="phits_out must be inside workspace"):
        prepare_rtdose(
            workspace_root=workspace,
            paths=paths(),
            paths_config={},
            template_dicom=template,
            ct_reference_dicom=ct,
            phits_out=external_out,
            command_argv=["prepare"],
        )


def test_prepare_patches_only_t_deposit_titles(tmp_path):
    workspace, files = write_workspace(tmp_path)
    files["sumtally_output"].write_text(
        "[ T-Track ]\n"
        "  title = Track title must remain\n"
        "[ T-Deposit ]\n"
        "  title = Dose title changes\n",
        encoding="utf-8",
    )
    rewrite_sumtally_output_evidence(workspace, files["sumtally_output"])
    files["phits_out"].write_text(
        "[ T-Track ]\n"
        "  title = Companion track title\n",
        encoding="utf-8",
    )
    template = tmp_path / "template.dcm"
    ct = tmp_path / "ct_reference.dcm"
    write_dicom(template, modality="RTDOSE")
    write_dicom(ct, modality="CT")

    summary = prepare_rtdose(
        workspace_root=workspace,
        paths=paths(),
        paths_config={},
        template_dicom=template,
        ct_reference_dicom=ct,
        phits_out=files["phits_out"],
        command_argv=["prepare"],
    )

    dose_text = files["sumtally_output"].read_text(encoding="utf-8")
    out_text = files["phits_out"].read_text(encoding="utf-8")
    assert "title = Track title must remain" in dose_text
    assert "title = Companion track title" in out_text
    assert "Dose title changes" in dose_text
    staged_dose_text = Path(summary["phits_dose"]).read_text(encoding="utf-8")
    assert "title = Track title must remain" in staged_dose_text
    assert "Dose title changes" not in staged_dose_text
    assert "ImagePositionPatient" in staged_dose_text
    assert summary["image_position_patient_patch"]["files"][0]["patched_title_count"] == 1
    assert summary["image_position_patient_patch"]["files"][1]["patched_title_count"] == 0


def test_prepare_skips_matching_existing_ipp_without_rewrite(tmp_path):
    workspace, files = write_workspace(tmp_path)
    files["sumtally_output"].write_text(
        "[ T-Deposit ]\n"
        "  title = (ImagePositionPatient  1.00000  2.00000  3.00000 mm)\n",
        encoding="utf-8",
    )
    rewrite_sumtally_output_evidence(workspace, files["sumtally_output"])
    files["phits_out"].write_text(
        "[ T-Deposit ]\n"
        "  title = (ImagePositionPatient  1.00000  2.00000  3.00000 mm)\n",
        encoding="utf-8",
    )
    template = tmp_path / "template.dcm"
    ct = tmp_path / "ct_reference.dcm"
    write_dicom(template, modality="RTDOSE")
    write_dicom(ct, modality="CT")
    before_dose = files["sumtally_output"].read_text(encoding="utf-8")
    before_out = files["phits_out"].read_text(encoding="utf-8")

    summary = prepare_rtdose(
        workspace_root=workspace,
        paths=paths(),
        paths_config={},
        template_dicom=template,
        ct_reference_dicom=ct,
        phits_out=files["phits_out"],
        command_argv=["prepare"],
    )

    patch = summary["image_position_patient_patch"]
    assert files["sumtally_output"].read_text(encoding="utf-8") == before_dose
    assert files["phits_out"].read_text(encoding="utf-8") == before_out
    assert patch["files"][0]["skipped_existing_ipp"] == 1
    assert patch["files"][0]["content_changed"] is False
    assert patch["files"][1]["skipped_existing_ipp"] == 1
    assert patch["files"][1]["content_changed"] is False
    assert patch["warnings"] == []
    assert patch["gate_failures"] == []


def test_prepare_accepts_existing_ipp_with_title_precision_rounding(tmp_path):
    workspace, files = write_workspace(tmp_path)
    files["sumtally_output"].write_text(
        "[ T-Deposit ]\n"
        "  title = (ImagePositionPatient  1.12346  2.12346  3.12346 mm)\n",
        encoding="utf-8",
    )
    rewrite_sumtally_output_evidence(workspace, files["sumtally_output"])
    files["phits_out"].write_text(
        "[ T-Deposit ]\n"
        "  title = (ImagePositionPatient  1.12346  2.12346  3.12346 mm)\n",
        encoding="utf-8",
    )
    template = tmp_path / "template.dcm"
    ct = tmp_path / "ct_reference.dcm"
    write_dicom(template, modality="RTDOSE")
    write_dicom(ct, modality="CT")
    ds = pydicom.dcmread(str(ct))
    ds.ImagePositionPatient = ["1.123456", "2.123456", "3.123456"]
    ds.save_as(str(ct))

    summary = prepare_rtdose(
        workspace_root=workspace,
        paths=paths(),
        paths_config={},
        template_dicom=template,
        ct_reference_dicom=ct,
        phits_out=files["phits_out"],
        command_argv=["prepare"],
    )

    patch = summary["image_position_patient_patch"]
    assert summary["stage_status"] == "success"
    assert patch["files"][0]["skipped_existing_ipp"] == 1
    assert patch["files"][1]["skipped_existing_ipp"] == 1
    assert patch["gate_failures"] == []


def test_prepare_rejects_mismatched_existing_ipp_without_partial_patch(tmp_path):
    workspace, files = write_workspace(tmp_path)
    files["sumtally_output"].write_text(
        "[ T-Deposit ]\n"
        "  title = Missing IPP should not be patched if companion fails\n",
        encoding="utf-8",
    )
    rewrite_sumtally_output_evidence(workspace, files["sumtally_output"])
    files["phits_out"].write_text(
        "[ T-Deposit ]\n"
        "  title = (ImagePositionPatient  9.00000  9.00000  9.00000 mm)\n",
        encoding="utf-8",
    )
    template = tmp_path / "template.dcm"
    ct = tmp_path / "ct_reference.dcm"
    write_dicom(template, modality="RTDOSE")
    write_dicom(ct, modality="CT")
    before_dose = files["sumtally_output"].read_text(encoding="utf-8")
    before_out = files["phits_out"].read_text(encoding="utf-8")

    with pytest.raises(ValueError, match="ImagePositionPatient title gate failure"):
        prepare_rtdose(
            workspace_root=workspace,
            paths=paths(),
            paths_config={},
            template_dicom=template,
            ct_reference_dicom=ct,
            phits_out=files["phits_out"],
            command_argv=["prepare"],
        )

    failure = json.loads((workspace / "analysis" / "rtdose_conversion_prepare_summary.json").read_text(encoding="utf-8"))
    assert failure["stage_status"] == "gate_failed"
    assert "differs from CT reference" in failure["failure_reason"]
    assert files["sumtally_output"].read_text(encoding="utf-8") == before_dose
    assert files["phits_out"].read_text(encoding="utf-8") == before_out


def test_prepare_rejects_malformed_existing_ipp(tmp_path):
    workspace, files = write_workspace(tmp_path)
    files["sumtally_output"].write_text(
        "[ T-Deposit ]\n"
        "  title = (ImagePositionPatient broken mm)\n",
        encoding="utf-8",
    )
    rewrite_sumtally_output_evidence(workspace, files["sumtally_output"])
    template = tmp_path / "template.dcm"
    ct = tmp_path / "ct_reference.dcm"
    write_dicom(template, modality="RTDOSE")
    write_dicom(ct, modality="CT")

    with pytest.raises(ValueError, match="existing ImagePositionPatient title is malformed"):
        prepare_rtdose(
            workspace_root=workspace,
            paths=paths(),
            paths_config={},
            template_dicom=template,
            ct_reference_dicom=ct,
            phits_out=files["phits_out"],
            command_argv=["prepare"],
        )


def test_prepare_rejects_missing_or_malformed_ct_reference_ipp(tmp_path):
    workspace, files = write_workspace(tmp_path)
    template = tmp_path / "template.dcm"
    ct = tmp_path / "ct_reference.dcm"
    write_dicom(template, modality="RTDOSE")
    write_dicom(ct, modality="CT")
    ds = pydicom.dcmread(str(ct), stop_before_pixels=True)
    del ds.ImagePositionPatient
    ds.save_as(str(ct))

    with pytest.raises(ValueError, match="ImagePositionPatient is missing"):
        prepare_rtdose(
            workspace_root=workspace,
            paths=paths(),
            paths_config={},
            template_dicom=template,
            ct_reference_dicom=ct,
            phits_out=files["phits_out"],
            command_argv=["prepare"],
        )

    workspace, files = write_workspace(tmp_path / "malformed")
    write_dicom(ct, modality="CT")
    ds = pydicom.dcmread(str(ct), stop_before_pixels=True)
    ds.ImagePositionPatient = ["1.0", "2.0"]
    ds.save_as(str(ct))
    with pytest.raises(ValueError, match="three finite numeric values"):
        prepare_rtdose(
            workspace_root=workspace,
            paths=paths(),
            paths_config={},
            template_dicom=template,
            ct_reference_dicom=ct,
            phits_out=files["phits_out"],
            command_argv=["prepare"],
        )


def test_prepare_rejects_beammu_or_unit_mismatch(tmp_path):
    workspace, files = write_workspace(tmp_path, beam_mu=True)
    template = tmp_path / "template.dcm"
    ct = tmp_path / "ct_reference.dcm"
    write_dicom(template, modality="RTDOSE")
    write_dicom(ct, modality="CT")

    with pytest.raises(ValueError, match="beamMU"):
        prepare_rtdose(
            workspace_root=workspace,
            paths=paths(),
            paths_config={},
            template_dicom=template,
            ct_reference_dicom=ct,
            phits_out=files["phits_out"],
            command_argv=["prepare"],
        )

    workspace, files = write_workspace(tmp_path / "mismatch")
    with pytest.raises(ValueError, match="input_dose_unit"):
        prepare_rtdose(
            workspace_root=workspace,
            paths=paths(),
            paths_config={},
            template_dicom=template,
            ct_reference_dicom=ct,
            phits_out=files["phits_out"],
            input_dose_unit="cGy",
            output_dicom_dose_unit="Gy",
            command_argv=["prepare"],
        )

    workspace, files = write_workspace(tmp_path / "absolute")
    with pytest.raises(ValueError, match="must be GY"):
        prepare_rtdose(
            workspace_root=workspace,
            paths=paths(),
            paths_config={},
            template_dicom=template,
            ct_reference_dicom=ct,
            phits_out=files["phits_out"],
            input_dose_unit="gy_per_mu",
            output_dicom_dose_unit="Gy",
            command_argv=["prepare"],
        )

    assert not (workspace / "rtdose" / "DATfiles" / "phits2dicom.inp").exists()


def test_phits2dicom_input_is_lf_and_slash_normalized(tmp_path):
    workspace, files = write_workspace(tmp_path)
    template = tmp_path / "template.dcm"
    ct = tmp_path / "ct_reference.dcm"
    write_dicom(template, modality="RTDOSE")
    write_dicom(ct, modality="CT")

    summary = prepare_rtdose(
        workspace_root=workspace,
        paths=paths(),
        paths_config={},
        template_dicom=template,
        ct_reference_dicom=ct,
        phits_out=files["phits_out"],
        command_argv=["prepare"],
    )

    content = Path(summary["phits2dicom_input_path"]).read_bytes()
    assert b"\r\n" not in content
    text = content.decode("utf-8")
    assert "\\" not in text
    assert summary["phits2dicom_stdin_content"] == text


def test_ct_reference_priority_and_sync_uses_workspace_copy(tmp_path):
    workspace, files = write_workspace(tmp_path)
    template = tmp_path / "template.dcm"
    explicit_ct = tmp_path / "explicit_ct.dcm"
    config_ct = tmp_path / "config_ct.dcm"
    generated_ct = tmp_path / "generated_ct.dcm"
    reference = tmp_path / "reference_identity.dcm"
    write_dicom(template, modality="RTDOSE")
    write_dicom(explicit_ct, modality="CT", frame_uid="1.1.1", study_uid="1.1.2")
    write_dicom(config_ct, modality="CT", frame_uid="2.1.1", study_uid="2.1.2")
    write_dicom(generated_ct, modality="CT", frame_uid="3.1.1", study_uid="3.1.2")
    write_dicom(reference, modality="RTDOSE", frame_uid="9.9.9", study_uid="8.8.8")
    plan = pydicom.dcmread(str(files["rtplan"]))
    plan.FrameOfReferenceUID = "9.9.9"
    plan.save_as(str(files["rtplan"]))
    write_rtplan_snapshot_evidence(files["rtplan"])

    selected, source = select_ct_reference(
        workspace_root=workspace,
        paths_config={"ct_reference_dicom_path": str(config_ct)},
        explicit_ct_reference=explicit_ct,
        generated_ct_reference=generated_ct,
        smoke_dummy_ct_reference=None,
    )
    assert selected == explicit_ct
    assert source == "explicit_ct_reference"

    summary = prepare_rtdose(
        workspace_root=workspace,
        paths=paths(),
        paths_config={"ct_reference_dicom_path": str(config_ct)},
        template_dicom=template,
        generated_ct_reference_dicom=generated_ct,
        reference_dicom_for_identity=reference,
        phits_out=files["phits_out"],
        command_argv=["prepare"],
    )

    assert summary["ct_reference_original_path"] == str(config_ct)
    copied = pydicom.dcmread(summary["ct_reference_workspace_copy_path"], stop_before_pixels=True)
    original = pydicom.dcmread(str(config_ct), stop_before_pixels=True)
    assert copied.FrameOfReferenceUID == "9.9.9"
    assert original.FrameOfReferenceUID == "2.1.1"
    assert summary["ct_reference_identity_sync"]["copied"]["StudyInstanceUID"] == "8.8.8"


def test_prepare_records_template_original_and_workspace_copy(tmp_path):
    workspace, files = write_workspace(tmp_path)
    template = tmp_path / "template.dcm"
    ct = tmp_path / "ct_reference.dcm"
    write_dicom(template, modality="RTDOSE")
    write_dicom(ct, modality="CT")

    summary = prepare_rtdose(
        workspace_root=workspace,
        paths=paths(),
        paths_config={},
        template_dicom=template,
        ct_reference_dicom=ct,
        phits_out=files["phits_out"],
        command_argv=["prepare"],
    )

    assert summary["template_dicom_original_path"] == str(template)
    assert Path(summary["template_dicom_workspace_copy_path"]).is_file()
    assert workspace in Path(summary["template_dicom_workspace_copy_path"]).parents


def test_prepare_writes_failure_summary_for_missing_inputs(tmp_path):
    workspace, files = write_workspace(tmp_path)
    missing_template = tmp_path / "missing_template.dcm"
    ct = tmp_path / "ct_reference.dcm"
    write_dicom(ct, modality="CT")

    with pytest.raises(FileNotFoundError, match="template DICOM"):
        prepare_rtdose(
            workspace_root=workspace,
            paths=paths(),
            paths_config={},
            template_dicom=missing_template,
            ct_reference_dicom=ct,
            phits_out=files["phits_out"],
            command_argv=["prepare"],
        )
    failure = json.loads((workspace / "analysis" / "rtdose_conversion_prepare_summary.json").read_text(encoding="utf-8"))
    assert failure["stage_status"] == "gate_failed"
    assert failure["phits2dicom_execution_started"] is False


def test_run_requires_executable_and_detects_new_dicom(tmp_path):
    workspace, files = write_workspace(tmp_path)
    template = tmp_path / "template.dcm"
    ct = tmp_path / "ct_reference.dcm"
    exe = tmp_path / "phits2dicom"
    write_dicom(template, modality="RTDOSE")
    write_dicom(ct, modality="CT")
    exe.write_text("exe", encoding="utf-8")
    prepare = prepare_rtdose(
        workspace_root=workspace,
        paths=paths(phits2dicom=str(exe)),
        paths_config={},
        template_dicom=template,
        ct_reference_dicom=ct,
        phits_out=files["phits_out"],
        command_argv=["prepare"],
    )

    calls = {}

    class FakeProc:
        returncode = 0

        def communicate(self, input):
            calls["input"] = input
            staged_dose = Path(input.splitlines()[3])
            calls["staged_dose"] = staged_dose
            write_coordinate_rtdose(staged_dose.with_suffix(".dcm"))
            return "ok", None

    def fake_runner(cmd, **kwargs):
        calls["cmd"] = cmd
        calls["cwd"] = kwargs["cwd"]
        calls["text"] = kwargs["text"]
        calls["stdin"] = kwargs["stdin"]
        calls["stdout"] = kwargs["stdout"]
        calls["stderr"] = kwargs["stderr"]
        return FakeProc()

    summary = run_rtdose(
        workspace_root=workspace,
        paths=paths(phits2dicom=str(exe)),
        command_argv=["run"],
        runner=fake_runner,
    )

    assert calls["cmd"] == [str(exe)]
    assert Path(calls["cwd"]) == calls["staged_dose"].parent
    assert Path(calls["cwd"]) != Path(prepare["dat_dir"]).absolute()
    assert calls["text"] is True
    assert calls["input"].startswith("PHITS2DICOM")
    assert calls["staged_dose"] != Path(prepare["phits_dose"])
    calls["staged_dose"].resolve().relative_to(workspace.resolve())
    assert prepare["rtdose_placement"]["rtplan_isocenter_dicom_mm"] == [
        10.0,
        -20.0,
        30.0,
    ]
    assert prepare["rtdose_placement"]["image_position_patient_mm"] == pytest.approx(
        [6.5, -27.0, 28.0],
        rel=0.0,
        abs=1.0e-6,
    )
    assert summary["returncode"] == 0
    assert summary["command"]["cwd"] == calls["cwd"]
    assert summary["phits2dicom_execution_started"] is True
    assert summary["rtdose_prepare_summary_sha256"] == file_sha256(
        workspace / "analysis" / "rtdose_conversion_prepare_summary.json"
    )
    assert summary["new_dicom_outputs"][0]["path"].endswith("deposit-target-3D_sum_all_active_segments_totalfield.dcm")
    assert summary["expected_rtdose_output"].endswith("deposit-target-3D_sum_all_active_segments_totalfield.dcm")
    assert summary["expected_rtdose_output_exists"] is True
    assert summary["coordinate_corrected_rtdose_output_exists"] is True
    output = Path(summary["expected_rtdose_output"])
    ds = pydicom.dcmread(str(output), stop_before_pixels=True)
    assert ds.DoseUnits == "GY"
    assert ds.DoseSummationType == "PLAN"
    assert len(ds.ReferencedRTPlanSequence) == 1
    assert ds.ReferencedRTPlanSequence[0].ReferencedSOPInstanceUID == (
        "1.2.826.0.1.3680043.10.54321.9001"
    )
    assert not hasattr(
        ds.ReferencedRTPlanSequence[0], "ReferencedFractionGroupSequence"
    )
    assert "totfact_per_MU=8.7608E+11 source/MU" in ds.DoseComment
    assert summary["absolute_dose_labeling"]["dose_units"] == "GY"
    assert summary["plan_reference_synchronization"][
        "previous_dose_summation_type"
    ] == "BEAM"
    assert summary["plan_reference_synchronization"]["invariants"] == {
        "pixel_data_preserved": True,
        "dose_and_geometry_fields_preserved": True,
    }
    assert summary["final_semantic_validation"]["validated"] is True
    corrected = pydicom.dcmread(summary["coordinate_corrected_rtdose_output"])
    assert corrected.DoseSummationType == "PLAN"
    assert corrected.ReferencedRTPlanSequence[0].ReferencedSOPInstanceUID == (
        "1.2.826.0.1.3680043.10.54321.9001"
    )
    assert sorted(corrected.pixel_array.ravel().tolist()) == list(range(24))
    assert float(corrected.DoseGridScaling) == 0.125
    assert [float(value) for value in corrected.ImagePositionPatient] == pytest.approx(
        [6.5, -27.0, 28.0],
        rel=0.0,
        abs=1.0e-6,
    )
    assert summary["rtdose_placement"][
        "output_volume_center_dicom_mm"
    ] == pytest.approx(
        [11.0, -23.0, 29.0],
        rel=0.0,
        abs=1.0e-6,
    )
    assert summary["coordinate_placement_validation"]["validated"] is True
    assert summary["coordinate_placement_validation"]["maximum_absolute_component_residual_mm"] <= 1.0e-6
    assert summary["dose_semantics"]["absolute_calibration_approved"] is True
    assert Path(summary["stdout_path"]).read_text(encoding="utf-8") == "ok"


def test_run_rejects_final_only_phits2dicom_output_and_cleans_staging(tmp_path):
    workspace, files = write_workspace(tmp_path)
    template = tmp_path / "template.dcm"
    ct = tmp_path / "ct_reference.dcm"
    exe = tmp_path / "phits2dicom"
    write_dicom(template, modality="RTDOSE")
    write_dicom(ct, modality="CT")
    exe.write_text("exe", encoding="utf-8")
    prepare = prepare_rtdose(
        workspace_root=workspace,
        paths=paths(phits2dicom=str(exe)),
        paths_config={},
        template_dicom=template,
        ct_reference_dicom=ct,
        phits_out=files["phits_out"],
        command_argv=["prepare"],
    )
    final_output = Path(prepare["phits_dose"]).with_suffix(".dcm")
    calls = {}

    class FakeProc:
        returncode = 0

        def communicate(self, input):
            calls["staged_output"] = Path(input.splitlines()[3]).with_suffix(
                ".dcm"
            )
            write_coordinate_rtdose(final_output)
            (Path(calls["cwd"]) / "cwd-relative-bypass.txt").write_text(
                "must remain staged",
                encoding="utf-8",
            )
            return "ok", None

    def fake_runner(cmd, **kwargs):
        calls["cwd"] = kwargs["cwd"]
        return FakeProc()

    summary = run_rtdose(
        workspace_root=workspace,
        paths=paths(phits2dicom=str(exe)),
        command_argv=["run"],
        runner=fake_runner,
    )

    assert Path(calls["cwd"]) == calls["staged_output"].parent
    assert Path(calls["cwd"]) != Path(prepare["dat_dir"]).absolute()
    assert not (Path(prepare["dat_dir"]) / "cwd-relative-bypass.txt").exists()
    assert not Path(calls["cwd"]).exists()
    assert summary["stage_status"] == "failed"
    assert summary["phits2dicom_staged_output_promoted"] is False
    assert summary["plan_reference_synchronization"] is None
    assert summary["failure_reason"] == (
        "phits2dicom did not create the expected output in guarded staging"
    )


def test_run_rejects_phits_dose_changed_after_prepare(tmp_path):
    workspace, files = write_workspace(tmp_path)
    template = tmp_path / "template.dcm"
    ct = tmp_path / "ct_reference.dcm"
    exe = tmp_path / "phits2dicom"
    write_dicom(template, modality="RTDOSE")
    write_dicom(ct, modality="CT")
    exe.write_text("exe", encoding="utf-8")
    prepare_rtdose(
        workspace_root=workspace,
        paths=paths(phits2dicom=str(exe)),
        paths_config={},
        template_dicom=template,
        ct_reference_dicom=ct,
        phits_out=files["phits_out"],
        command_argv=["prepare"],
    )
    files["sumtally_output"].write_text(
        "changed after RTDOSE Prepare",
        encoding="utf-8",
    )
    calls = []

    with pytest.raises(
        ValueError,
        match="Upstream phits_dose changed after RTDOSE Prepare",
    ):
        run_rtdose(
            workspace_root=workspace,
            paths=paths(phits2dicom=str(exe)),
            command_argv=["run"],
            runner=lambda cmd, **kwargs: calls.append(cmd),
        )

    assert calls == []

def test_run_rejects_upstream_phits_out_changed_after_prepare(tmp_path):
    workspace, files = write_workspace(tmp_path)
    template = tmp_path / "template.dcm"
    ct = tmp_path / "ct_reference.dcm"
    exe = tmp_path / "phits2dicom"
    write_dicom(template, modality="RTDOSE")
    write_dicom(ct, modality="CT")
    exe.write_text("exe", encoding="utf-8")
    prepare_rtdose(
        workspace_root=workspace,
        paths=paths(phits2dicom=str(exe)),
        paths_config={},
        template_dicom=template,
        ct_reference_dicom=ct,
        phits_out=files["phits_out"],
        command_argv=["prepare"],
    )
    files["phits_out"].write_text(
        "changed after RTDOSE Prepare",
        encoding="utf-8",
    )
    calls = []

    with pytest.raises(
        ValueError,
        match="Upstream phits_out changed after RTDOSE Prepare",
    ):
        run_rtdose(
            workspace_root=workspace,
            paths=paths(phits2dicom=str(exe)),
            command_argv=["run"],
            runner=lambda cmd, **kwargs: calls.append(cmd),
        )

    assert calls == []



def test_run_rejects_phits2dicom_input_changed_after_prepare(tmp_path):
    workspace, files = write_workspace(tmp_path)
    template = tmp_path / "template.dcm"
    ct = tmp_path / "ct_reference.dcm"
    exe = tmp_path / "phits2dicom"
    write_dicom(template, modality="RTDOSE")
    write_dicom(ct, modality="CT")
    exe.write_text("exe", encoding="utf-8")
    prepare = prepare_rtdose(
        workspace_root=workspace,
        paths=paths(phits2dicom=str(exe)),
        paths_config={},
        template_dicom=template,
        ct_reference_dicom=ct,
        phits_out=files["phits_out"],
        command_argv=["prepare"],
    )
    phits2dicom_input = Path(prepare["phits2dicom_input_path"])
    phits2dicom_input.write_text(
        phits2dicom_input.read_text(encoding="utf-8") + "\nchanged\n",
        encoding="utf-8",
    )
    calls = []

    with pytest.raises(
        ValueError,
        match="phits2dicom input changed after RTDOSE Prepare",
    ):
        run_rtdose(
            workspace_root=workspace,
            paths=paths(phits2dicom=str(exe)),
            command_argv=["run"],
            runner=lambda cmd, **kwargs: calls.append(cmd),
        )

    assert calls == []


@pytest.mark.parametrize(
    ("role", "summary_field"),
    [
        ("template_dicom", "template_dicom_workspace_copy_path"),
        ("ct_reference", "ct_reference_workspace_copy_path"),
        ("phits_out", "phits_out"),
    ],
)
def test_run_rejects_converter_referenced_input_changed_after_prepare(
    tmp_path,
    role,
    summary_field,
):
    workspace, files = write_workspace(tmp_path)
    template = tmp_path / "template.dcm"
    ct = tmp_path / "ct_reference.dcm"
    exe = tmp_path / "phits2dicom"
    write_dicom(template, modality="RTDOSE")
    write_dicom(ct, modality="CT")
    exe.write_text("exe", encoding="utf-8")
    prepare = prepare_rtdose(
        workspace_root=workspace,
        paths=paths(phits2dicom=str(exe)),
        paths_config={},
        template_dicom=template,
        ct_reference_dicom=ct,
        phits_out=files["phits_out"],
        command_argv=["prepare"],
    )
    referenced_input = Path(prepare[summary_field])
    referenced_input.write_bytes(referenced_input.read_bytes() + b"changed")
    calls = []

    with pytest.raises(
        ValueError,
        match=f"referenced input {role} changed after RTDOSE Prepare",
    ):
        run_rtdose(
            workspace_root=workspace,
            paths=paths(phits2dicom=str(exe)),
            command_argv=["run"],
            runner=lambda cmd, **kwargs: calls.append(cmd),
        )

    assert calls == []


def test_prepare_rejects_frozen_plan_uid_mismatch(tmp_path):
    workspace, files = write_workspace(tmp_path)
    template = tmp_path / "template.dcm"
    ct = tmp_path / "ct_reference.dcm"
    write_dicom(template, modality="RTDOSE")
    write_dicom(ct, modality="CT")
    plan = pydicom.dcmread(str(files["rtplan"]))
    plan.SOPInstanceUID = "1.2.826.0.1.3680043.10.54321.9002"
    plan.save_as(str(files["rtplan"]))
    write_rtplan_snapshot_evidence(files["rtplan"])

    with pytest.raises(ValueError, match="does not match segment manifest plan_uid"):
        prepare_rtdose(
            workspace_root=workspace,
            paths=paths(),
            paths_config={},
            template_dicom=template,
            ct_reference_dicom=ct,
            phits_out=files["phits_out"],
            command_argv=["prepare"],
        )

    failure = json.loads(
        (workspace / "analysis" / "rtdose_conversion_prepare_summary.json").read_text(
            encoding="utf-8"
        )
    )
    assert failure["stage_status"] == "gate_failed"
    assert failure["phits2dicom_execution_started"] is False


def test_prepare_rejects_frozen_plan_content_changed_with_same_identity(tmp_path):
    workspace, files = write_workspace(tmp_path)
    template = tmp_path / "template.dcm"
    ct = tmp_path / "ct_reference.dcm"
    write_dicom(template, modality="RTDOSE")
    write_dicom(ct, modality="CT")
    plan = pydicom.dcmread(str(files["rtplan"]))
    plan.BeamSequence[0].BeamName = "CHANGED_AFTER_WORKSPACE_PREPARE"
    plan.save_as(str(files["rtplan"]))

    with pytest.raises(
        ValueError,
        match="does not match CT2PHITS SHA-256 evidence",
    ):
        prepare_rtdose(
            workspace_root=workspace,
            paths=paths(),
            paths_config={},
            template_dicom=template,
            ct_reference_dicom=ct,
            phits_out=files["phits_out"],
            command_argv=["prepare"],
        )


def test_prepare_legacy_plan_binding_reconstructs_segment_geometry(
    monkeypatch,
    tmp_path,
):
    workspace, files = write_workspace(tmp_path)
    (workspace / "ct2phits_workspace_manifest.json").unlink()
    manifest_path = workspace / "segments" / "segment_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["rtplan_sampling"] = {}
    manifest["tolerances"] = {}
    manifest["segments"][0]["expected_output_path"] = (
        "segments/seg_b0001_s0000/deposit-target-3D.out"
    )
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    rewrite_sumtally_manifest_digests(workspace, manifest)
    monkeypatch.setattr(
        "dicomxphits.rtdose_plan_references.build_manifest",
        lambda *args, **kwargs: (
            {
                "segments": [
                    {
                        **segment,
                        "phits_input_path": "phits_inputs/beam_0001_segment_0000.inp",
                    }
                    for segment in manifest["segments"]
                ]
            },
            [],
            [],
        ),
    )
    template = tmp_path / "template.dcm"
    ct = tmp_path / "ct_reference.dcm"
    write_dicom(template, modality="RTDOSE")
    write_dicom(ct, modality="CT")

    summary = prepare_rtdose(
        workspace_root=workspace,
        paths=paths(),
        paths_config={},
        template_dicom=template,
        ct_reference_dicom=ct,
        phits_out=files["phits_out"],
        command_argv=["prepare"],
    )

    assert summary["full_plan_evidence"]["rtplan_binding"]["mode"] == (
        "reconstructed_segment_geometry"
    )


@pytest.mark.parametrize(
    ("manifest_update", "error"),
    [
        ({"workflow_mode": "selected_beam"}, "requires workflow_mode full_plan"),
        ({"included_total_mu": 90.0}, "included_total_mu does not reconcile"),
    ],
)
def test_prepare_rejects_incomplete_full_plan_evidence(
    tmp_path,
    manifest_update,
    error,
):
    workspace, files = write_workspace(tmp_path)
    manifest_path = workspace / "segments" / "segment_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest.update(manifest_update)
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    rewrite_sumtally_manifest_digests(workspace, manifest)
    template = tmp_path / "template.dcm"
    ct = tmp_path / "ct_reference.dcm"
    write_dicom(template, modality="RTDOSE")
    write_dicom(ct, modality="CT")

    with pytest.raises(ValueError, match=error):
        prepare_rtdose(
            workspace_root=workspace,
            paths=paths(),
            paths_config={},
            template_dicom=template,
            ct_reference_dicom=ct,
            phits_out=files["phits_out"],
            command_argv=["prepare"],
        )


def test_prepare_rejects_manifest_changed_after_sumtally_run(tmp_path):
    workspace, files = write_workspace(tmp_path)
    manifest_path = workspace / "segments" / "segment_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["case_id"] = "internally-consistent-but-not-calculated"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    template = tmp_path / "template.dcm"
    ct = tmp_path / "ct_reference.dcm"
    write_dicom(template, modality="RTDOSE")
    write_dicom(ct, modality="CT")

    with pytest.raises(
        ValueError,
        match="does not match Sumtally Generate evidence",
    ):
        prepare_rtdose(
            workspace_root=workspace,
            paths=paths(),
            paths_config={},
            template_dicom=template,
            ct_reference_dicom=ct,
            phits_out=files["phits_out"],
            command_argv=["prepare"],
        )


def test_prepare_rejects_sumtally_run_input_digest_mismatch(tmp_path):
    workspace, files = write_workspace(tmp_path)
    execution_path = workspace / "analysis" / "sumtally_execution_summary.json"
    execution = json.loads(execution_path.read_text(encoding="utf-8"))
    execution["sum_input_sha256"] = "0" * 64
    execution_path.write_text(json.dumps(execution), encoding="utf-8")
    template = tmp_path / "template.dcm"
    ct = tmp_path / "ct_reference.dcm"
    write_dicom(template, modality="RTDOSE")
    write_dicom(ct, modality="CT")

    with pytest.raises(
        ValueError,
        match="Run input evidence does not match Sumtally Generate",
    ):
        prepare_rtdose(
            workspace_root=workspace,
            paths=paths(),
            paths_config={},
            template_dicom=template,
            ct_reference_dicom=ct,
            phits_out=files["phits_out"],
            command_argv=["prepare"],
        )


def test_prepare_rejects_sumtally_run_dependency_digest_mismatch(tmp_path):
    workspace, files = write_workspace(tmp_path)
    execution_path = workspace / "analysis" / "sumtally_execution_summary.json"
    execution = json.loads(execution_path.read_text(encoding="utf-8"))
    execution["segment_output_evidence"][0]["sha256"] = "0" * 64
    execution_path.write_text(json.dumps(execution), encoding="utf-8")
    template = tmp_path / "template.dcm"
    ct = tmp_path / "ct_reference.dcm"
    write_dicom(template, modality="RTDOSE")
    write_dicom(ct, modality="CT")

    with pytest.raises(
        ValueError,
        match="Run dependency evidence does not match Sumtally Generate",
    ):
        prepare_rtdose(
            workspace_root=workspace,
            paths=paths(),
            paths_config={},
            template_dicom=template,
            ct_reference_dicom=ct,
            phits_out=files["phits_out"],
            command_argv=["prepare"],
        )


@pytest.mark.parametrize("delivery_type", [None, "CONTINUATION"])
def test_prepare_accepts_existing_supported_treatment_delivery_types(
    tmp_path,
    delivery_type,
):
    workspace, files = write_workspace(tmp_path)
    write_rtplan(
        files["rtplan"],
        treatment_delivery_type=delivery_type,
    )
    write_rtplan_snapshot_evidence(files["rtplan"])
    template = tmp_path / "template.dcm"
    ct = tmp_path / "ct_reference.dcm"
    write_dicom(template, modality="RTDOSE")
    write_dicom(ct, modality="CT")

    summary = prepare_rtdose(
        workspace_root=workspace,
        paths=paths(),
        paths_config={},
        template_dicom=template,
        ct_reference_dicom=ct,
        phits_out=files["phits_out"],
        command_argv=["prepare"],
    )

    assert summary["stage_status"] == "success"
    assert summary["sumtally_manifest_binding"]["validated"] is True


def test_prepare_rejects_inconsistent_control_point_isocenters(tmp_path):
    workspace, files = write_workspace(tmp_path)
    plan = pydicom.dcmread(str(files["rtplan"]))
    conflicting_control_point = Dataset()
    conflicting_control_point.IsocenterPosition = [11.0, -20.0, 30.0]
    plan.BeamSequence[0].ControlPointSequence.append(conflicting_control_point)
    plan.save_as(str(files["rtplan"]))
    write_rtplan_snapshot_evidence(files["rtplan"])
    template = tmp_path / "template.dcm"
    ct = tmp_path / "ct_reference.dcm"
    write_dicom(template, modality="RTDOSE")
    write_dicom(ct, modality="CT")

    with pytest.raises(
        ValueError,
        match="inconsistent control-point IsocenterPosition values",
    ):
        prepare_rtdose(
            workspace_root=workspace,
            paths=paths(),
            paths_config={},
            template_dicom=template,
            ct_reference_dicom=ct,
            phits_out=files["phits_out"],
            command_argv=["prepare"],
        )

    failure = json.loads(
        (workspace / "analysis" / "rtdose_conversion_prepare_summary.json").read_text(
            encoding="utf-8"
        )
    )
    assert failure["stage_status"] == "gate_failed"
    assert failure["phits2dicom_execution_started"] is False


def test_prepare_accepts_skipped_non_treatment_setup_beam(tmp_path):
    workspace, files = write_workspace(tmp_path)
    add_non_treatment_setup_beam(workspace, files["rtplan"])
    template = tmp_path / "template.dcm"
    ct = tmp_path / "ct_reference.dcm"
    write_dicom(template, modality="RTDOSE")
    write_dicom(ct, modality="CT")

    summary = prepare_rtdose(
        workspace_root=workspace,
        paths=paths(),
        paths_config={},
        template_dicom=template,
        ct_reference_dicom=ct,
        phits_out=files["phits_out"],
        command_argv=["prepare"],
    )

    evidence = summary["full_plan_evidence"]
    assert evidence["referenced_beam_numbers"] == [1]
    assert evidence["skipped_non_treatment_beam_numbers"] == [2]
    assert evidence["treatment_total_mu"] == 100.0
    assert evidence["plan_total_mu"] == 110.0
    assert evidence["dose_normalization_mu"] == 110.0


def test_prepare_accepts_zero_mu_skipped_non_treatment_setup_beam(tmp_path):
    workspace, files = write_workspace(tmp_path)
    add_non_treatment_setup_beam(
        workspace,
        files["rtplan"],
        setup_mu=0.0,
    )
    template = tmp_path / "template.dcm"
    ct = tmp_path / "ct_reference.dcm"
    write_dicom(template, modality="RTDOSE")
    write_dicom(ct, modality="CT")

    summary = prepare_rtdose(
        workspace_root=workspace,
        paths=paths(),
        paths_config={},
        template_dicom=template,
        ct_reference_dicom=ct,
        phits_out=files["phits_out"],
        command_argv=["prepare"],
    )

    evidence = summary["full_plan_evidence"]
    assert evidence["skipped_non_treatment_beam_metersets"] == {"2": 0.0}
    assert evidence["treatment_total_mu"] == 100.0
    assert evidence["plan_total_mu"] == 100.0


def test_prepare_rejects_negative_mu_skipped_non_treatment_setup_beam(tmp_path):
    workspace, files = write_workspace(tmp_path)
    add_non_treatment_setup_beam(
        workspace,
        files["rtplan"],
        setup_mu=-1.0,
    )
    template = tmp_path / "template.dcm"
    ct = tmp_path / "ct_reference.dcm"
    write_dicom(template, modality="RTDOSE")
    write_dicom(ct, modality="CT")

    with pytest.raises(ValueError, match="finite nonnegative number"):
        prepare_rtdose(
            workspace_root=workspace,
            paths=paths(),
            paths_config={},
            template_dicom=template,
            ct_reference_dicom=ct,
            phits_out=files["phits_out"],
            command_argv=["prepare"],
        )


def test_prepare_rejects_active_non_treatment_setup_beam(tmp_path):
    workspace, files = write_workspace(tmp_path)
    add_non_treatment_setup_beam(
        workspace,
        files["rtplan"],
        active=True,
    )
    template = tmp_path / "template.dcm"
    ct = tmp_path / "ct_reference.dcm"
    write_dicom(template, modality="RTDOSE")
    write_dicom(ct, modality="CT")

    with pytest.raises(
        ValueError,
        match="Active segment references non-treatment BeamNumber 2",
    ):
        prepare_rtdose(
            workspace_root=workspace,
            paths=paths(),
            paths_config={},
            template_dicom=template,
            ct_reference_dicom=ct,
            phits_out=files["phits_out"],
            command_argv=["prepare"],
        )


def test_run_resolves_relative_phits2dicom_executable_before_changing_cwd(monkeypatch, tmp_path):
    workspace, files = write_workspace(tmp_path)
    template = tmp_path / "template.dcm"
    ct = tmp_path / "ct_reference.dcm"
    exe = tmp_path / "relative_phits2dicom"
    write_dicom(template, modality="RTDOSE")
    write_dicom(ct, modality="CT")
    exe.write_text("exe", encoding="utf-8")
    prepare = prepare_rtdose(
        workspace_root=workspace,
        paths=paths(phits2dicom="relative_phits2dicom"),
        paths_config={},
        template_dicom=template,
        ct_reference_dicom=ct,
        phits_out=files["phits_out"],
        command_argv=["prepare"],
    )
    monkeypatch.chdir(tmp_path)

    calls = {}

    class FakeProc:
        returncode = 0

        def communicate(self, input):
            calls["staged_dose"] = Path(input.splitlines()[3])
            write_coordinate_rtdose(calls["staged_dose"].with_suffix(".dcm"))
            return "ok", None

    def fake_runner(cmd, **kwargs):
        calls["cmd"] = cmd
        calls["cwd"] = kwargs["cwd"]
        return FakeProc()

    summary = run_rtdose(
        workspace_root=workspace,
        paths=paths(phits2dicom="relative_phits2dicom"),
        command_argv=["run"],
        runner=fake_runner,
    )

    assert calls["cmd"] == [str(exe.resolve())]
    assert Path(calls["cwd"]) == calls["staged_dose"].parent
    assert Path(calls["cwd"]) != Path(summary["dat_dir"]).absolute()
    assert summary["stage_status"] == "success"


def test_run_fails_when_final_plan_reference_is_corrupted(
    monkeypatch,
    tmp_path,
):
    workspace, files = write_workspace(tmp_path)
    template = tmp_path / "template.dcm"
    ct = tmp_path / "ct_reference.dcm"
    exe = tmp_path / "phits2dicom"
    write_dicom(template, modality="RTDOSE")
    write_dicom(ct, modality="CT")
    exe.write_text("exe", encoding="utf-8")
    prepare = prepare_rtdose(
        workspace_root=workspace,
        paths=paths(phits2dicom=str(exe)),
        paths_config={},
        template_dicom=template,
        ct_reference_dicom=ct,
        phits_out=files["phits_out"],
        command_argv=["prepare"],
    )

    class FakeProc:
        returncode = 0

        def communicate(self, input):
            staged_dose = Path(input.splitlines()[3])
            write_coordinate_rtdose(staged_dose.with_suffix(".dcm"))
            return "ok", None

    original_fix_coordinates = prepare_rtdose_module.fix_coordinates

    def corrupting_fix_coordinates(input_path, output_path, **kwargs):
        summary = original_fix_coordinates(input_path, output_path, **kwargs)
        output = pydicom.dcmread(str(output_path))
        output.ReferencedRTPlanSequence[0].ReferencedSOPInstanceUID = (
            "1.2.826.0.1.3680043.10.54321.9998"
        )
        output.save_as(str(output_path))
        return summary

    monkeypatch.setattr(
        prepare_rtdose_module,
        "fix_coordinates",
        corrupting_fix_coordinates,
    )

    summary = run_rtdose(
        workspace_root=workspace,
        paths=paths(phits2dicom=str(exe)),
        command_argv=["run"],
        runner=lambda cmd, **kwargs: FakeProc(),
    )

    failure = json.loads(
        (workspace / "analysis" / "rtdose_conversion_execution_summary.json").read_text(
            encoding="utf-8"
        )
    )
    assert failure["stage_status"] == "failed"
    assert failure["phits2dicom_execution_started"] is True
    assert failure == summary
    assert failure["returncode"] == 0
    assert failure["expected_rtdose_output_updated_by_run"] is True
    assert failure["expected_rtdose_output_after_conversion"]["sha256"]
    assert failure["coordinate_corrected_rtdose_output_exists"] is True
    assert failure["coordinate_placement_validation"]["validated"] is True
    assert failure["final_semantic_validation"] is None
    assert "wrong RT Plan SOP Instance UID" in failure["failure_reason"]
    assert Path(failure["stdout_path"]).read_text(encoding="utf-8") == "ok"
    assert Path(failure["stderr_path"]).read_text(encoding="utf-8") == ""


def test_run_fails_when_final_coordinate_placement_is_corrupted(
    monkeypatch,
    tmp_path,
):
    workspace, files = write_workspace(tmp_path)
    template = tmp_path / "template.dcm"
    ct = tmp_path / "ct_reference.dcm"
    exe = tmp_path / "phits2dicom"
    write_dicom(template, modality="RTDOSE")
    write_dicom(ct, modality="CT")
    exe.write_text("exe", encoding="utf-8")
    prepare = prepare_rtdose(
        workspace_root=workspace,
        paths=paths(phits2dicom=str(exe)),
        paths_config={},
        template_dicom=template,
        ct_reference_dicom=ct,
        phits_out=files["phits_out"],
        command_argv=["prepare"],
    )

    class FakeProc:
        returncode = 0

        def communicate(self, input):
            staged_dose = Path(input.splitlines()[3])
            write_coordinate_rtdose(staged_dose.with_suffix(".dcm"))
            return "ok", None

    original_fix_coordinates = prepare_rtdose_module.fix_coordinates

    def corrupting_fix_coordinates(input_path, output_path, **kwargs):
        summary = original_fix_coordinates(input_path, output_path, **kwargs)
        output = pydicom.dcmread(str(output_path))
        position = [float(value) for value in output.ImagePositionPatient]
        position[0] += 0.01
        output.ImagePositionPatient = position
        output.save_as(str(output_path))
        return summary

    monkeypatch.setattr(
        prepare_rtdose_module,
        "fix_coordinates",
        corrupting_fix_coordinates,
    )

    summary = run_rtdose(
        workspace_root=workspace,
        paths=paths(phits2dicom=str(exe)),
        command_argv=["run"],
        runner=lambda cmd, **kwargs: FakeProc(),
    )

    failure = json.loads(
        (workspace / "analysis" / "rtdose_conversion_execution_summary.json").read_text(
            encoding="utf-8"
        )
    )
    assert failure["stage_status"] == "failed"
    assert failure["phits2dicom_execution_started"] is True
    assert failure == summary
    assert failure["returncode"] == 0
    assert failure["expected_rtdose_output_updated_by_run"] is True
    assert failure["expected_rtdose_output_after_conversion"]["sha256"]
    assert failure["coordinate_corrected_rtdose_output_exists"] is True
    assert failure["coordinate_correction"]
    assert failure["coordinate_placement_validation"] is None
    assert failure["final_semantic_validation"] is None
    assert "patient-coordinate residual exceeds 1e-6 mm" in failure["failure_reason"]
    assert Path(failure["stdout_path"]).read_text(encoding="utf-8") == "ok"
    assert Path(failure["stderr_path"]).read_text(encoding="utf-8") == ""


def test_relative_comparison_contract_requires_both_operands_relative(tmp_path):
    reference = tmp_path / "reference.dcm"
    evaluation = tmp_path / "evaluation.dcm"
    write_dicom(reference, modality="RTDOSE")
    write_dicom(evaluation, modality="RTDOSE")
    for path in (reference, evaluation):
        ds = pydicom.dcmread(str(path))
        ds.DoseUnits = "RELATIVE"
        ds.save_as(str(path))

    assert require_relative_rtdose(reference, role="reference")["dose_units"] == "RELATIVE"
    assert require_relative_rtdose(evaluation, role="evaluation")["dose_units"] == "RELATIVE"

    ds = pydicom.dcmread(str(reference))
    ds.DoseUnits = "GY"
    ds.save_as(str(reference))
    with pytest.raises(ValueError, match="DoseUnits must be RELATIVE"):
        require_relative_rtdose(reference, role="reference")


def test_run_rejects_stale_preexisting_rtdose_output(tmp_path):
    workspace, files = write_workspace(tmp_path)
    template = tmp_path / "template.dcm"
    ct = tmp_path / "ct_reference.dcm"
    exe = tmp_path / "phits2dicom"
    write_dicom(template, modality="RTDOSE")
    write_dicom(ct, modality="CT")
    exe.write_text("exe", encoding="utf-8")
    prepare = prepare_rtdose(
        workspace_root=workspace,
        paths=paths(phits2dicom=str(exe)),
        paths_config={},
        template_dicom=template,
        ct_reference_dicom=ct,
        phits_out=files["phits_out"],
        command_argv=["prepare"],
    )
    stale_output = Path(prepare["phits_dose"]).with_suffix(".dcm")
    stale_output.write_text("stale dose dicom", encoding="utf-8")

    class FakeProc:
        returncode = 0

        def communicate(self, input):
            return "ok without new output", None

    summary = run_rtdose(
        workspace_root=workspace,
        paths=paths(phits2dicom=str(exe)),
        command_argv=["run"],
        runner=lambda cmd, **kwargs: FakeProc(),
    )

    assert summary["stage_status"] == "failed"
    assert summary["returncode"] == 0
    assert summary["expected_rtdose_output_exists"] is True
    assert summary["expected_rtdose_output_preexisting"] is True
    assert summary["expected_rtdose_output_updated_by_run"] is False
    assert summary["new_dicom_outputs"] == []


def test_run_rejects_mtime_only_preexisting_rtdose_update(tmp_path):
    workspace, files = write_workspace(tmp_path)
    template = tmp_path / "template.dcm"
    ct = tmp_path / "ct_reference.dcm"
    exe = tmp_path / "phits2dicom"
    write_dicom(template, modality="RTDOSE")
    write_dicom(ct, modality="CT")
    exe.write_text("exe", encoding="utf-8")
    prepare = prepare_rtdose(
        workspace_root=workspace,
        paths=paths(phits2dicom=str(exe)),
        paths_config={},
        template_dicom=template,
        ct_reference_dicom=ct,
        phits_out=files["phits_out"],
        command_argv=["prepare"],
    )
    stale_output = Path(prepare["phits_dose"]).with_suffix(".dcm")
    stale_output.write_text("stale dose dicom", encoding="utf-8")
    stale_mtime_ns = stale_output.stat().st_mtime_ns

    class FakeProc:
        returncode = 0

        def communicate(self, input):
            changed_mtime_ns = stale_mtime_ns + 1_000_000_000
            os.utime(stale_output, ns=(changed_mtime_ns, changed_mtime_ns))
            return "touched only", None

    summary = run_rtdose(
        workspace_root=workspace,
        paths=paths(phits2dicom=str(exe)),
        command_argv=["run"],
        runner=lambda cmd, **kwargs: FakeProc(),
    )

    assert summary["stage_status"] == "failed"
    assert summary["expected_rtdose_output_updated_by_run"] is False
    before = summary["expected_rtdose_output_before_run"]
    after_conversion = summary["expected_rtdose_output_after_conversion"]
    assert after_conversion["mtime_ns"] != before["mtime_ns"]
    assert after_conversion["sha256"] == before["sha256"]
    assert summary["plan_reference_synchronization"] is None


def test_run_missing_executable_writes_failure_summary(tmp_path):
    workspace, files = write_workspace(tmp_path)
    template = tmp_path / "template.dcm"
    ct = tmp_path / "ct_reference.dcm"
    write_dicom(template, modality="RTDOSE")
    write_dicom(ct, modality="CT")
    prepare_rtdose(
        workspace_root=workspace,
        paths=paths(phits2dicom=None),
        paths_config={},
        template_dicom=template,
        ct_reference_dicom=ct,
        phits_out=files["phits_out"],
        command_argv=["prepare"],
    )

    with pytest.raises(ValueError, match="phits2dicom_executable_path"):
        run_rtdose(workspace_root=workspace, paths=paths(phits2dicom=None), command_argv=["run"])

    failure = json.loads((workspace / "analysis" / "rtdose_conversion_execution_summary.json").read_text(encoding="utf-8"))
    assert failure["stage_status"] == "gate_failed"
    assert failure["phits2dicom_execution_started"] is False
