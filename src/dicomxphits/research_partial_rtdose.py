"""Export a validated retained tally through the research-only conversion path."""
from __future__ import annotations

import io
import json
import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

import pydicom

from dicomxphits.dose_semantics import mark_rtdose_absolute
from dicomxphits.fix_coordinates import fix_coordinates
from dicomxphits.prepare_3dcrt_workspace import ExternalToolPaths
from dicomxphits.prepare_rtdose import (
    copy_template,
    patch_rtdose_inputs_for_ipp,
    phits2dicom_input_content,
    phits2dicom_template_preflight,
    run_phits2dicom,
)
from dicomxphits.prepare_sumtally import (
    SUMTALLY_MODE,
    WEIGHT_FIELD,
    derive_tally_patterns_from_manifest,
    localize_sumtally_segment_paths,
    run_phits_sumtally,
    transitive_phits_include_paths,
)
from dicomxphits.research_geometry_recovery import _path, _record
from dicomxphits.research_partial_tally import RetainedSnapshot, inspect_snapshot
from dicomxphits.rtdose_geometry import derive_rtdose_placement, validate_rtdose_placement
from dicomxphits.rtdose_plan_references import (
    build_course_dose_evidence,
    synchronize_plan_rtdose,
    validate_full_plan_context,
    validate_plan_rtdose,
)
from dicomxphits.safe_output import WorkspaceOutputGuard
from dicomxphits.segment_retry import (
    _has_link_or_reparse_component,
    digest_object,
    validate_selected_executable,
)
from dicomxphits.sumtally_inputs import (
    build_sumtally,
    checked_text_lines,
    file_sha256,
    generate_sum_inp,
    validate_sumtally_normalization_input,
)
from dicomxphits.sumtally_relative_error_recovery import (
    MAX_JSON_BYTES,
    _publish_file_new_only,
    _publish_json_new_only,
    _stable_bytes,
)
from dicomxphits.workspace_execution import WorkspaceExecutionLease

OUTPUT_DIRECTORY = Path("research_partial_rtdose")
RECEIPT = OUTPUT_DIRECTORY / "receipt.json"
DOSE_NAME = "research-partial.dcm"
SCHEMA = "dicomxphits_research_partial_tally_rtdose_v1"


@dataclass(frozen=True)
class ExportInputs:
    tools: ExternalToolPaths
    rtplan: Path
    ct_reference: Path
    template: Path


def _digest(path: Path) -> str:
    if not path.is_absolute() or not path.is_file() or _has_link_or_reparse_component(path):
        raise ValueError(f"Missing or unsafe research export input: {path.name}")
    return file_sha256(path)


def _semantics(root, snapshot, rtplan, ct_reference):
    inputs = {"rtplan_sha256": _digest(rtplan), "ct_reference_sha256": _digest(ct_reference)}
    plan = validate_full_plan_context(rtplan_path=rtplan, workspace_root=root, ct_reference_path=ct_reference)
    if inputs != {"rtplan_sha256": _digest(rtplan), "ct_reference_sha256": _digest(ct_reference)}:
        raise ValueError("Frozen plan or CT reference changed while being validated")
    course = build_course_dose_evidence(plan_evidence=plan, base_factor=1.0)
    placement = derive_rtdose_placement(snapshot.mesh_geometry,
                                        rtplan_isocenter_dicom_mm=plan["rtplan_isocenter_dicom_mm"])
    return inputs, plan, course, placement


def _plan(root, staging, inputs, guard):
    output = guard.prepare(root / OUTPUT_DIRECTORY)
    if os.path.lexists(output):
        if not output.is_dir():
            raise ValueError("Research export destination is not a directory")
        if os.path.lexists(guard.prepare(root / RECEIPT)):
            raise ValueError("Research export receipt already exists. Re-open the saved result.")
    snapshot = inspect_snapshot(root, staging, guard)
    auxiliary, plan_evidence, course, placement = _semantics(root, snapshot, inputs.rtplan, inputs.ct_reference)
    validate_selected_executable(root, snapshot.binding, inputs.tools)
    if not inputs.tools.phits2dicom_executable_path:
        raise ValueError("Select the phits2dicom executable before export")
    auxiliary.update(
        template_sha256=_digest(inputs.template),
        phits2dicom_sha256=_digest(Path(inputs.tools.phits2dicom_executable_path)),
    )
    phits2dicom_template_preflight(inputs.template)
    plan = {
        "snapshot": snapshot.evidence,
        "auxiliary": auxiliary,
        "receipt_path": RECEIPT.as_posix(),
        "destination_exists": output.is_dir(),
    }
    return plan, snapshot, plan_evidence, course, placement


def preview(root: Path, staging: str, inputs: ExportInputs) -> dict:
    root = root.resolve()
    with WorkspaceOutputGuard(root, read_only=True) as guard:
        plan, *_ = _plan(root, staging, inputs, guard)
    return {"plan": plan, "plan_digest": digest_object(plan)}


def _pin_files(root, guard, snapshots):
    for path, expected in snapshots.items():
        if _record(root, path, guard)["sha256"] != expected:
            raise ValueError("A private research export input changed before execution")


def _check_tool_copies(root, guard, snapshots, files):
    if any(source not in snapshots for source, _ in files):
        raise ValueError("A tool staged a file outside the confirmed input set")
    _pin_files(root, guard, {copy: snapshots[source] for source, copy in files})


def _build_aggregation(private, guard, snapshot: RetainedSnapshot):
    sum_dir = guard.mkdir(private / "sumtally")
    output = sum_dir / "deposit-target-3D_sum.out"
    wrapper = sum_dir / "aggregate.inp"
    weights = sum_dir / "sumtally.inp"
    libpath = sum_dir / "libpath.inp"
    content, helper = build_sumtally(
        snapshot.manifest, case_root=private, output_name=output.name,
        weight_field=WEIGHT_FIELD, mode=SUMTALLY_MODE,
    )
    content, out_files, _, _ = localize_sumtally_segment_paths(
        content, helper, workspace_root=private, sumtally_dir=sum_dir,
    )
    guard.write_text(weights, content, newline="\n", overwrite=False)
    validate_sumtally_normalization_input(
        weights, manifest=snapshot.manifest,
        recorded_evidence=helper["sumtally_normalization_evidence"],
    )
    guard.copy_file(private / "libpath.inp", libpath, overwrite=False)
    guard.prepare_file_target(wrapper)
    generate_sum_inp(
        private / snapshot.source, out_files, output.name, helper["sumfactor"],
        SUMTALLY_MODE, derive_tally_patterns_from_manifest(snapshot.manifest, []),
        wrapper, include_base_dir=private, output_dir_basis=sum_dir,
    )
    dependencies = transitive_phits_include_paths(wrapper, execution_cwd=sum_dir)
    if any(not path.is_relative_to(private) for path in dependencies):
        raise ValueError("Research Sumtally wrapper references files outside private staging")
    controls = []
    for path in [wrapper, *dependencies]:
        guard.prepare(path)
        with checked_text_lines(path) as lines:
            for line in lines:
                if re.match(r"^\s*(?:icntl|isumtally)\s*=", line, re.I):
                    controls.append((path, line.split("#", 1)[0].replace(" ", "").replace("\t", "").strip().lower()))
    if sorted(controls) != sorted([(wrapper, "icntl=13"), (weights, "isumtally=2")]):
        raise ValueError("Research PHITS input is not the supported tally-aggregation mode")
    if weights not in dependencies:
        raise ValueError("Research Sumtally inputs do not include the validated weights")
    evidence = {path: file_sha256(path) for path in [wrapper, *dependencies]}
    return wrapper, output, evidence


def _comment(snapshot):
    comment = f"RESEARCH ONLY - PARTIAL PHITS {snapshot['saved_batches']}/{snapshot['planned_batches']}"
    if len(comment) > 64:
        raise ValueError("Research DoseComment does not fit the DICOM attribute")
    return comment


def _check_dose(path, snapshot, plan, course, placement):
    dataset = pydicom.dcmread(path, stop_before_pixels=True)
    if dataset.get("DoseComment") != _comment(snapshot):
        raise ValueError("Research-only DICOM label is missing or changed")
    validate_plan_rtdose(path, plan_evidence=plan, course_dose_evidence=course)
    validate_rtdose_placement(path, expected_placement=placement)


def _convert(private, guard, snapshot, inputs, plan, course, placement, revalidate,
             sumtally_runner, converter_runner):
    wrapper, sum_output, aggregate_files = _build_aggregation(private, guard, snapshot)
    for relative, record in {**snapshot.inputs, **snapshot.tallies}.items():
        aggregate_files[private / relative] = record["sha256"]

    def check_aggregation():
        revalidate()
        _pin_files(private, guard, aggregate_files)

    def check_staged_aggregation(files):
        check_aggregation()
        _check_tool_copies(private, guard, aggregate_files, files)

    result, geometry, error, _, _ = run_phits_sumtally(
        phits_executable_path=inputs.tools.phits_executable_path,
        sum_input=wrapper, stdout_path=wrapper.with_name("stdout.txt"),
        stderr_path=wrapper.with_name("stderr.txt"), workspace_root=private,
        expected_output=sum_output, expected_geometry=snapshot.mesh_geometry,
        runner=sumtally_runner, validate_staged=check_staged_aggregation,
    )
    if result.returncode != 0 or geometry is None or error is not None:
        raise ValueError(error or "Research tally aggregation did not create a validated dose grid")
    aggregate_files[sum_output] = file_sha256(sum_output)
    phits_out = wrapper.with_name("phits.out")
    aggregate_files[phits_out] = _record(private, phits_out, guard)["sha256"]

    template = copy_template(inputs.template, private)
    phits2dicom_template_preflight(template)
    dat_dir = guard.mkdir(private / "rtdose" / "dat")
    dose_copy = guard.copy_file(sum_output, dat_dir / sum_output.name, overwrite=False)
    out_copy = guard.copy_file(phits_out, dat_dir / phits_out.name, overwrite=False)
    ct_copy = dat_dir / "ct.dcm"
    # The selected CT is a read-only external source. Write only into private staging.
    guard.write_bytes(ct_copy, inputs.ct_reference.read_bytes(), overwrite=False)
    patch_rtdose_inputs_for_ipp(workspace_root=private, phits_dose=dose_copy,
                                phits_out=out_copy, ct_reference_workspace_copy=ct_copy)
    stdin = phits2dicom_input_content(
        template_dicom=template, ct_reference=ct_copy, phits_dose=dose_copy,
        phits_out=out_copy, dat_dir=dat_dir, factor=float(course["effective_phits2dicom_factor"]),
    )
    converter_files = {path: file_sha256(path) for path in (template, ct_copy, dose_copy, out_copy)}

    def check_converter():
        check_aggregation()
        _pin_files(private, guard, converter_files)
        if converter_files[template] != _digest(inputs.template) or converter_files[ct_copy] != _digest(inputs.ct_reference):
            raise ValueError("DICOM converter inputs differ from the confirmed inputs")

    def check_staged_converter(files):
        check_converter()
        _check_tool_copies(private, guard, converter_files, files)

    raw_dose = dose_copy.with_suffix(".dcm")
    return_code, _, promoted, _ = run_phits2dicom(
        executable_path=inputs.tools.phits2dicom_executable_path, stdin_content=stdin,
        stdout_path=dat_dir / "stdout.txt", stderr_path=dat_dir / "stderr.txt",
        workspace_root=private, expected_outputs=(raw_dose,), runner=converter_runner,
        validate_staged=check_staged_converter,
    )
    if return_code != 0 or not promoted:
        raise ValueError("Research DICOM conversion did not create its expected RT Dose")
    mark_rtdose_absolute(raw_dose, guard=guard)
    synchronize_plan_rtdose(raw_dose, plan_evidence=plan, course_dose_evidence=course, guard=guard)
    corrected = private / DOSE_NAME
    fix_coordinates(raw_dose, corrected, expected_placement=placement, guard=guard)
    dataset = pydicom.dcmread(corrected)
    dataset.DoseComment = _comment(snapshot.evidence)
    stream = io.BytesIO()
    dataset.save_as(stream)
    guard.write_bytes(corrected, stream.getvalue())
    _check_dose(corrected, snapshot.evidence, plan, course, placement)
    check_converter()
    return corrected


def export(root: Path, staging: str, inputs: ExportInputs, *, expected_digest: str,
           acknowledge_research_only: bool, sumtally_runner=subprocess.run, converter_runner=subprocess.Popen) -> dict:
    if acknowledge_research_only is not True:
        raise ValueError("Explicit research-only acknowledgement is required")
    root = root.resolve()
    with WorkspaceExecutionLease(root, create=False) as lease, WorkspaceOutputGuard(root) as guard:
        plan, snapshot, semantics, course, placement = _plan(root, staging, inputs, guard)
        if digest_object(plan) != expected_digest:
            raise ValueError("Research export evidence changed. Preview it again.")

        def revalidate(*, after_creating_destination=False):
            current = _plan(root, staging, inputs, guard)[0]
            if after_creating_destination:
                current["destination_exists"] = plan["destination_exists"]
            if current != plan:
                raise ValueError("Confirmed research export evidence changed")

        private = guard.make_staging_directory(root, prefix=".prt-")
        try:
            for relative, record in {**snapshot.inputs, **snapshot.tallies}.items():
                destination = private / relative
                guard.copy_file(_path(root, record["path"], guard), destination, overwrite=False)
                if file_sha256(destination) != record["sha256"]:
                    raise ValueError("A private research copy differs from the retained evidence")
            with WorkspaceOutputGuard(private) as private_guard:
                corrected = _convert(
                    private, private_guard, snapshot, inputs, semantics, course, placement, revalidate,
                    lease.run if sumtally_runner is subprocess.run else sumtally_runner,
                    lease.popen if converter_runner is subprocess.Popen else converter_runner,
                )
            before = _record(root, corrected, guard)["sha256"]
            revalidate()
            guard.mkdir(root / OUTPUT_DIRECTORY)
            destination = guard.make_staging_directory(root / OUTPUT_DIRECTORY, prefix="export-") / DOSE_NAME
            _publish_file_new_only(guard, corrected, destination, expected_sha256=before,
                                   validate_before_publish=lambda: revalidate(after_creating_destination=True))
            _check_dose(destination, snapshot.evidence, semantics, course, placement)
            record = _record(root, destination, guard)
            if record["sha256"] != before:
                raise ValueError("Published research RT Dose differs from the validated export")
            receipt = {
                "schema_version": SCHEMA, "research_only": True, "operator_acknowledgement": True,
                "plan": plan, "plan_digest": expected_digest, "rtdose": record,
            }
            receipt["receipt_content_sha256"] = digest_object(receipt)

            def finalize():
                revalidate(after_creating_destination=True)
                if _record(root, destination, guard) != record:
                    raise ValueError("Research RT Dose changed before receipt publication")

            _publish_json_new_only(guard, root / RECEIPT, receipt, validate_before_publish=finalize)
            return receipt
        finally:
            guard.rmtree(private, missing_ok=True)


def verify(root: Path, *, rtplan: Path, ct_reference: Path) -> dict:
    root = root.resolve()
    with WorkspaceOutputGuard(root, read_only=True) as guard:
        raw, receipt_sha256 = _stable_bytes(root / RECEIPT, guard=guard, label="Research RT Dose receipt",
                                            maximum_bytes=MAX_JSON_BYTES)
        receipt = json.loads(raw)
        canonical = (json.dumps(receipt, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        keys = {"schema_version", "research_only", "operator_acknowledgement", "plan", "plan_digest",
                "rtdose", "receipt_content_sha256"}
        if (
            not isinstance(receipt, dict) or set(receipt) != keys or receipt["schema_version"] != SCHEMA
            or receipt["research_only"] is not True or receipt["operator_acknowledgement"] is not True
            or raw not in (canonical, canonical.replace(b"\n", b"\r\n"))
            or digest_object({k: v for k, v in receipt.items() if k != "receipt_content_sha256"})
            != receipt["receipt_content_sha256"]
            or digest_object(receipt["plan"]) != receipt["plan_digest"]
        ):
            raise ValueError("Research RT Dose receipt is malformed or changed")
        plan = receipt["plan"]
        snapshot = inspect_snapshot(root, plan["snapshot"]["staging_directory"], guard)
        if snapshot.evidence != plan["snapshot"] or plan["receipt_path"] != RECEIPT.as_posix():
            raise ValueError("Research receipt no longer matches the saved tally evidence")
        current, semantics, course, placement = _semantics(root, snapshot, rtplan, ct_reference)
        if any(plan["auxiliary"].get(key) != value for key, value in current.items()):
            raise ValueError("Research receipt no longer matches the frozen plan and CT reference")
        record = receipt["rtdose"]
        dose = _path(root, record["path"], guard)
        if (dose.parent.parent != root / OUTPUT_DIRECTORY or not dose.parent.name.startswith("export-")
                or dose.name != DOSE_NAME or _record(root, dose, guard) != record):
            raise ValueError("Research RT Dose is missing or changed")
        _check_dose(dose, snapshot.evidence, semantics, course, placement)
        if (_record(root, dose, guard) != record
                or _record(root, root / RECEIPT, guard)["sha256"] != receipt_sha256):
            raise ValueError("Research RT Dose or receipt changed during semantic validation")
        return receipt
