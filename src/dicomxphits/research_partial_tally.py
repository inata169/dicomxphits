"""Validate the saved tally snapshot for a research RT Dose export."""
from __future__ import annotations

import os
import re
import time
from dataclasses import dataclass
from pathlib import Path

from dicomxphits.phits_geometry_diagnostics import GEOMETRY_DIAGNOSTIC_LABELS
from dicomxphits.phits_observation_format import (
    MAX_TALLY_BYTES,
    assignments,
    number,
    paired_tally_values,
    parse_restart_metadata,
    prepared_contract,
)
from dicomxphits.phits_terminal_evidence import (
    MAX_INPUT_BYTES,
    MAX_LOG_BYTES,
    OPENMP_335,
    PHASE,
    SCHEMA as TERMINAL_SCHEMA,
    is_post_batch_exit,
    is_stack_overflow,
    require_no_recorded_phits_error,
    validate_finalization,
)
from dicomxphits.prepare_3dcrt_workspace import active_segments
from dicomxphits.prepare_sumtally import (
    validate_calculation_tally_geometry_binding,
    validate_manifest_for_sumtally,
)
from dicomxphits.research_geometry_recovery import MANIFEST, PREFLIGHT, SUMMARY, _path, _record
from dicomxphits.rtdose_geometry import parse_tally_mesh_geometry, segment_tally_geometry_binding
from dicomxphits.run_segments import (
    SEGMENT_EXECUTION_SCHEMA_V4,
    SEGMENT_EXECUTION_SCHEMA_V5,
    phits_error_output_path,
    phits_staging_contract,
    validate_segment_execution_summary,
)
from dicomxphits.segment_preflight import require_current_result
from dicomxphits.segment_retry import (
    FAILED_STAGING_SCHEMA,
    PREPARATION_FILES,
    digest_object,
    validate_binding,
    validate_parent,
    validate_results,
)
from dicomxphits.sumtally_relative_error_recovery import _stable_bytes, _stable_json
from dicomxphits.workspace_recovery import rebind_workspace_path

RESTART_MARKER = "# Information for Restart Calculation\n"
_BATCH = re.compile(r"^\s*bat\[\s*([0-9]{1,16})\s*\]\s+ncas\s*=\s*([0-9]{1,20})\.?\s*$", re.I)
_SEED = re.compile(r"^\s*bitrseed\s*=\s*([01]{64})\s*$")
_GEOMETRY_PREFIXES = tuple(
    label.lower().removesuffix("s") for label in GEOMETRY_DIAGNOSTIC_LABELS.values()
) + ("geometry error summary",)


@dataclass(frozen=True)
class RetainedSnapshot:
    manifest: dict
    binding: dict
    primary: str
    source: str
    inputs: dict
    tallies: dict
    mesh_geometry: dict
    evidence: dict


def _last_batch_seed(log: str, expected_batch: int, maxcas: int) -> str:
    last = 0
    seed = None
    awaiting_seed = False
    for line in log.splitlines():
        folded = line.lstrip().lower()
        if folded.startswith(_GEOMETRY_PREFIXES):
            raise ValueError("PHITS contains geometry diagnostics outside the supported missing-summary case")
        if folded.startswith("bat["):
            match = _BATCH.fullmatch(line)
            if match is None or awaiting_seed:
                raise ValueError("PHITS batch progress is malformed")
            batch, histories = map(int, match.groups())
            if batch != last + 1 or histories != batch * maxcas:
                raise ValueError("PHITS batch progress disagrees with preparation")
            last = batch
            awaiting_seed = True
        elif awaiting_seed and line.strip():
            match = _SEED.fullmatch(line)
            if match is None:
                raise ValueError("PHITS batch progress lacks the recorded start seed")
            seed = match[1]
            awaiting_seed = False
    if awaiting_seed or last != expected_batch or seed is None:
        raise ValueError("PHITS did not report the last planned batch and its start seed")
    return seed


def _bound_record(root, record, expected, guard):
    if not isinstance(record, dict) or record.get("path") != expected:
        raise ValueError("Retained artifact is not at its recorded invocation path")
    path = _path(root, expected, guard)
    actual = _record(root, path, guard)
    if any(actual[key] != record.get(key) for key in actual) or not actual["size"]:
        raise ValueError("Retained evidence is empty or differs from the failed invocation")
    return actual


def _bound_bytes(root, record, guard, maximum_bytes):
    raw, digest = _stable_bytes(
        _path(root, record["path"], guard), guard=guard,
        label="Retained PHITS snapshot", maximum_bytes=maximum_bytes,
    )
    if len(raw) != record["size"] or digest != record["sha256"]:
        raise ValueError("Retained PHITS snapshot changed while being read")
    return raw


def _validate_depth_tally(raw, prepared, relative, expected_metadata, planned):
    text = raw.decode("ascii").replace("\r\n", "\n")
    body, separator, restart = text.partition(RESTART_MARKER)
    header, page, data = body.partition("#newpage:\n")
    if not separator or not page or not header.startswith("[ T-Deposit ]\n"):
        raise ValueError("Unsupported retained depth tally format")
    fields = assignments(header.split("\n", 1)[1])
    if any(fields.get(key) != prepared.get(key) for key in
           ("file", "axis", "mesh", "unit", "part", "material", "output")):
        raise ValueError("Retained depth tally identity disagrees with the prepared tally")
    if fields["file"] != relative or fields["axis"] != "z":
        raise ValueError("Unsupported additional retained tally")
    for axis in "xyz":
        for key in ("n" + axis, axis + "min", axis + "max"):
            if number(fields.get(key, "")) != number(prepared.get(key, "")):
                raise ValueError("Retained depth tally mesh disagrees with preparation")
    metadata = parse_restart_metadata(restart, live_maxbch=planned)
    if any(metadata[key] != expected_metadata[key] for key in ("resc3", "maxcas", "istdev", "bitrseed")):
        raise ValueError("Retained depth tally restart state disagrees with the dose pair")

    rows = []
    row_pattern = re.compile(
        r"\s*([+\-.0-9EeDd]+)\s+([+\-.0-9EeDd]+)\s+([+\-.0-9EeDd]+)\s+([+\-.0-9EeDd]+)\s*"
    )
    for line in data.splitlines():
        if match := row_pattern.fullmatch(line):
            rows.append(tuple(number(cell) for cell in match.groups()))
    count = int(number(fields["nz"]))
    lower, upper = number(fields["zmin"]), number(fields["zmax"])
    step = (upper - lower) / count
    if len(rows) != count or any(
        start != float(f"{lower + index * step:.4e}")
        or end != float(f"{lower + (index + 1) * step:.4e}")
        or dose < 0 or error < 0
        for index, (start, end, dose, error) in enumerate(rows)
    ):
        raise ValueError("Retained depth tally does not cover its complete prepared grid")


def _post_batch_record(result):
    record = result.get("terminal_evidence")
    if (is_post_batch_exit(result.get("return_code")) and isinstance(record, dict)
            and record.get("schema_version") == TERMINAL_SCHEMA):
        return record
    return None


def has_partial_tally_candidate(summary):
    """Check the recorded eligibility route before enabling the preview button."""
    if not isinstance(summary, dict) or summary.get("stage_status") != "failed":
        return False
    segments = summary.get("segments")
    return isinstance(segments, list) and any(
        isinstance(result, dict) and result.get("status") == "failed"
        and (is_stack_overflow(result.get("return_code"))
             or (summary.get("stop_requested") is None and _post_batch_record(result) is not None))
        for result in segments
    )


def _validate_terminal_record(root, primary, result, retained, log_record, log_text, runtime, guard):
    record = _post_batch_record(result)
    expected = {
        "schema_version": TERMINAL_SCHEMA,
        "run_id": retained["run_id"],
        "segment_id": retained["segment_id"],
        "exit_code": result["return_code"],
        "runtime": runtime,
        "staging_directory": retained["staging_directory"],
    }
    if (record is None or set(record) != {*expected, "logs"}
            or digest_object({key: record[key] for key in expected}) != digest_object(expected)):
        raise ValueError("PHITS terminal evidence does not match the failed invocation")

    logs = record["logs"]
    if (not isinstance(logs, dict) or set(logs) != {"stdout", "stderr", "phits_out"}
            or digest_object(logs["phits_out"]) != digest_object({**log_record, "output_path": "phits.out"})):
        raise ValueError("PHITS terminal logs do not match the retained invocation")
    console = {}
    for role in ("stdout", "stderr"):
        path = primary.parent / f"phits_{role}.txt"
        evidence = logs[role]
        if (not isinstance(evidence, dict) or set(evidence) != {"path", "size", "sha256"}
                or evidence["path"] != path.relative_to(root).as_posix()
                or type(evidence["size"]) is not int or not 0 <= evidence["size"] <= MAX_LOG_BYTES
                or rebind_workspace_path(result[f"{role}_log_path"], recorded_workspace_root=str(root),
                                         current_workspace_root=root) != path):
            raise ValueError("PHITS console log is not at its bound invocation path")
        console[role] = _bound_bytes(root, evidence, guard, MAX_LOG_BYTES).decode("utf-8")
    require_no_recorded_phits_error(log_text)
    validate_finalization(console["stdout"], console["stderr"], runtime)
    return {"route": "bound_post_batch", "phase": PHASE, "terminal_evidence": record}


def inspect_snapshot(root: Path, staging: str, guard, *, legacy_receipt: bool = False) -> RetainedSnapshot:
    summary, summary_sha = _stable_json(root / SUMMARY, guard=guard, label="PHITS execution")
    manifest, manifest_sha = _stable_json(root / MANIFEST, guard=guard, label="segment manifest")
    validate_manifest_for_sumtally(manifest)
    schema = validate_segment_execution_summary(summary, require_success=False)
    active = active_segments(manifest)
    failed = [item for item in summary["segments"] if item["status"] != "skipped"]
    if (
        schema not in {SEGMENT_EXECUTION_SCHEMA_V4, SEGMENT_EXECUTION_SCHEMA_V5}
        or summary["stage_status"] != "failed" or summary.get("failure_reason") is not None
        or summary.get("workspace_root") != str(root)
        or len(active) != 1 or len(failed) != 1 or manifest.get("workflow_mode") != "full_plan"
    ):
        raise ValueError("Research export requires one failed active segment in a bound full-plan workspace")
    segment = active[0]
    result = failed[0]
    code = result.get("return_code")
    stack_overflow = is_stack_overflow(code)
    if (
        (not stack_overflow and (legacy_receipt or summary.get("stop_requested") is not None
                                 or _post_batch_record(result) is None))
        or result["status"] != "failed" or result["segment_id"] != segment["segment_id"]
        or result["reason"] != f"PHITS returned nonzero exit code {code}"
        or result.get("producer_run_id") != summary["run_id"] or result.get("retained")
        or result.get("expected_output_exists") is not False
    ):
        raise ValueError("PHITS failure lacks an eligible exit and bound terminal evidence")
    diagnostics = result.get("geometry_diagnostics") or {}
    if (diagnostics.get("status") != "invalid" or diagnostics.get("counts") is not None
            or diagnostics.get("reason") != "missing PHITS geometry diagnostics: "
            + ", ".join(GEOMETRY_DIAGNOSTIC_LABELS.values())):
        raise ValueError("PHITS geometry evidence is outside the supported missing-summary case")

    binding = summary["execution_binding"]
    validate_binding(root, manifest, binding, local_only=True)
    if (
        Path((binding["tool"] or {}).get("executable") or "").name.lower() != OPENMP_335
        or {item["path"] for item in binding["preparation"]} != set(PREPARATION_FILES)
    ):
        raise ValueError("Required PHITS 3.35 OpenMP preparation or executable evidence is missing")
    validate_results(root, summary)
    validate_parent(root, summary)
    require_current_result(root, summary)
    preflight = _record(root, root / PREFLIGHT, guard) if os.path.lexists(root / PREFLIGHT) else None

    staging_path = _path(root, staging, guard)
    retained = result.get("retained_staging")
    if (
        not isinstance(retained, dict) or retained.get("schema_version") != FAILED_STAGING_SCHEMA
        or retained.get("staging_directory") != staging or staging_path.parent != root / "analysis"
        or not staging_path.name.startswith(".phits-segment-run-")
        or retained.get("run_id") != summary["run_id"]
        or retained.get("segment_id") != segment["segment_id"]
        or retained.get("missing_required_outputs") != []
    ):
        raise ValueError("Selected directory is not the retained staging of the failed invocation")

    source = _path(root, segment["phits_input_path"], guard)
    primary = _path(root, segment["expected_output_path"], guard)
    for field, expected in (("phits_input_path", source), ("expected_output_path", primary)):
        if rebind_workspace_path(result[field], recorded_workspace_root=str(root),
                                 current_workspace_root=root) != expected:
            raise ValueError("Failed segment paths do not match the current manifest")
    source_relative = source.relative_to(root).as_posix()
    primary_relative = primary.relative_to(root).as_posix()
    error_relative = phits_error_output_path(primary).relative_to(root).as_posix()

    inputs, outputs = phits_staging_contract(workspace_root=root, phits_input=source, guard=guard)
    original_inputs = {path.relative_to(root).as_posix() for path in inputs}
    required = {path.relative_to(root).as_posix() for path in outputs} | {error_relative, "phits.out"}
    captured_inputs = {item["input_path"]: item for item in retained["inputs"]}
    captured_outputs = {item["output_path"]: item for item in retained["outputs"]}
    if (set(captured_inputs) != original_inputs or len(captured_inputs) != len(retained["inputs"])
            or set(captured_outputs) != required or len(captured_outputs) != len(retained["outputs"])):
        raise ValueError("Retained files do not match the manifest-derived input and output set")
    recorded_inputs = {item["path"]: item["sha256"] for item in binding["segments"][0]["inputs"]}
    retained_inputs = {
        item: _bound_record(root, record, f"{staging}/{item}", guard)
        for item, record in captured_inputs.items()
    }
    if {item: record["sha256"] for item, record in retained_inputs.items()} != recorded_inputs:
        raise ValueError("Retained inputs do not match the prospective execution binding")
    retained_outputs = {
        item: _bound_record(root, record, f"{staging}/{item}", guard)
        for item, record in captured_outputs.items()
    }
    output_parents = {Path(item).parent for item in required - {"phits.out"}}
    for parent in output_parents:
        directory = staging_path / parent
        for entry in directory.iterdir():
            if entry.suffix.lower() == ".out" and entry.relative_to(staging_path).as_posix() not in required:
                raise ValueError("Unexpected additional retained tally")

    log = retained_outputs.pop("phits.out")
    companion = rebind_workspace_path(result["phits_out_path"], recorded_workspace_root=str(root),
                                      current_workspace_root=root)
    if (companion != primary.parent / "phits.out"
            or _record(root, companion, guard)["sha256"] != log["sha256"]
            or log["sha256"] != result["phits_out_sha256"]):
        raise ValueError("Retained PHITS log differs from the recorded failed execution")

    input_text = _bound_bytes(root, retained_inputs[source_relative], guard, MAX_INPUT_BYTES).decode("utf-8")
    mesh, runtime = prepared_contract(input_text, primary_relative)
    maxcas, planned = runtime["maxcas"], runtime["maxbch"]
    log_text = _bound_bytes(root, log, guard, MAX_LOG_BYTES).decode("utf-8", "replace")
    batch_seed = _last_batch_seed(log_text, planned, maxcas)
    if stack_overflow:
        failure_evidence = {"route": "recorded_stack_overflow", "phase": "unavailable"}
    else:
        failure_evidence = _validate_terminal_record(root, primary, result, retained, log, log_text, runtime, guard)
    _, _, metadata = paired_tally_values(
        _bound_bytes(root, retained_outputs[primary_relative], guard, MAX_TALLY_BYTES),
        _bound_bytes(root, retained_outputs[error_relative], guard, MAX_TALLY_BYTES),
        mesh, maxcas, time.monotonic() + 60, live_maxbch=planned, live_numeric=True,
    )
    saved = metadata["resc3"]
    if metadata["istdev"] != 1 or saved <= 0 or saved != planned - 1 or metadata["bitrseed"] != batch_seed:
        raise ValueError("Retained tally is not the complete snapshot preceding the final batch")
    blocks = [
        assignments(match[1]) for match in re.finditer(
            r"(?ims)^\s*\[\s*T-Deposit\s*\]\s*\n(.*?)(?=^\s*\[|\Z)", input_text
        )
    ]
    for relative in required - {"phits.out", primary_relative, error_relative}:
        prepared = [block for block in blocks if block.get("file") == relative]
        if len(prepared) != 1:
            raise ValueError("Additional tally has no unambiguous prepared input")
        _validate_depth_tally(_bound_bytes(root, retained_outputs[relative], guard, MAX_TALLY_BYTES),
                              prepared[0], relative, metadata, planned)
    primary_path = _path(root, retained_outputs[primary_relative]["path"], guard)
    mesh_binding = segment_tally_geometry_binding([primary_path])
    validate_calculation_tally_geometry_binding(manifest, mesh_binding)
    mesh_geometry = parse_tally_mesh_geometry(primary_path)
    evidence = {
        "staging_directory": staging, "run_id": summary["run_id"], "segment_id": segment["segment_id"],
        "exit_code": code, "saved_batches": saved, "planned_batches": planned,
        "histories_per_batch": maxcas, "final_geometry_diagnostics": "unavailable",
        "summary_sha256": summary_sha, "manifest_sha256": manifest_sha, "preflight": preflight,
        "execution_binding_sha256": digest_object(binding), "phits_log": log,
        "retained_inputs": retained_inputs, "tallies": retained_outputs,
        "mesh_geometry": mesh_geometry,
    }
    if not legacy_receipt:
        evidence["failure_evidence"] = failure_evidence
    return RetainedSnapshot(manifest, binding, primary_relative, source_relative,
                            retained_inputs, retained_outputs, mesh_geometry, evidence)
