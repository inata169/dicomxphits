"""Accept saved geometry recoveries for research; never execute transport."""
from __future__ import annotations

import argparse
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any, Mapping

from dicomxphits import __version__
from dicomxphits.phits_geometry_diagnostics import (
    parse_phits_geometry_diagnostics_file, parse_research_geometry_completion,
)
from dicomxphits.safe_output import WorkspaceOutputGuard
from dicomxphits.segment_retry import (
    FAILED_STAGING_SCHEMA, RESEARCH_RECEIPT_PATH, capture_failed_staging,
    digest_object, validate_binding, validate_parent, validate_results,
)
from dicomxphits.sumtally_inputs import checked_text_lines, file_sha256, manifest_sha256
from dicomxphits.sumtally_relative_error_recovery import (
    _publish_file_new_only, _publish_json_new_only, _stable_bytes, _stable_json,
)
from dicomxphits.workspace_execution import WorkspaceExecutionLease

RECEIPT_PATH = RESEARCH_RECEIPT_PATH
SCHEMA = "dicomxphits_research_geometry_recovery_acceptance_v2"
POLICY = "zero_loss_zero_unrecovered_recorded_recoveries_v1"
PURPOSE = "research_only_saved_geometry_recovery"
NOT_FOR = ["clinical_use", "commissioning", "patient_QA", "vendor_certification"]
SUMMARY = "analysis/segment_execution_summary.json"
MANIFEST = "segments/segment_manifest.json"
PREFLIGHT = "analysis/segment_preflight.json"


def _path(root, value, guard):
    if (not isinstance(value, str) or not value or "\\" in value
            or PureWindowsPath(value).drive or PurePosixPath(value).is_absolute()
            or any(p in {"..", ".", ""} for p in value.split("/"))):
        raise ValueError("Research artifact paths must be canonical workspace-relative paths")
    return guard.prepare(root / value)


def _record(root, path, guard):
    path = guard.prepare(path)
    if not path.is_file():
        raise ValueError("Research evidence must be an existing ordinary file")
    before = path.stat()
    digest = file_sha256(path)
    after = path.stat()
    if any(getattr(before, k) != getattr(after, k) for k in
           ("st_dev", "st_ino", "st_size", "st_mtime_ns", "st_ctime_ns")):
        raise ValueError("Research evidence changed while being read")
    return {"path": path.relative_to(root).as_posix(), "size": after.st_size, "sha256": digest}


def _operator_reason(reason):
    if not isinstance(reason, str) or not reason.strip() or len(reason) > 2048:
        raise ValueError("A non-empty research acceptance reason of at most 2048 characters is required")
    if re.search(r"[A-Za-z]:[\\/]|\\\\|(?<!\w)/\S", reason):
        raise ValueError("The research reason must not contain an absolute path")
    return reason.strip()


def _context(root, staging_directory, guard, *, destinations=None):
    from dicomxphits.run_segments import (
        phits_staging_contract, phits_error_output_path,
        validate_segment_execution_summary, SEGMENT_EXECUTION_SCHEMA_V4,
        SEGMENT_EXECUTION_SCHEMA_V5,
    )
    from dicomxphits.workspace_recovery import rebind_workspace_path
    from dicomxphits.segment_preflight import validate_receipt as validate_preflight, MAX_RECEIPT_BYTES

    summary, summary_sha = _stable_json(root / SUMMARY, guard=guard, label="segment summary")
    manifest, manifest_sha = _stable_json(root / MANIFEST, guard=guard, label="segment manifest")
    from dicomxphits.gantry_geometry import require_reusable_gantry_geometry_contract
    from dicomxphits.prepare_3dcrt_workspace import validate_public_strict_3dcrt_gate
    require_reusable_gantry_geometry_contract(manifest)
    validate_public_strict_3dcrt_gate(manifest)
    schema = validate_segment_execution_summary(summary, require_success=False)
    if schema not in {SEGMENT_EXECUTION_SCHEMA_V4, SEGMENT_EXECUTION_SCHEMA_V5}:
        raise ValueError("Historical execution lacks prospective staging invocation evidence")
    if summary.get("stage_status") != "failed" or summary.get("failure_reason") is not None:
        raise ValueError("Research acceptance requires an otherwise valid terminal geometry failure")
    active = [s for s in summary["segments"] if s["status"] != "skipped"]
    failed = [s for s in active if s["status"] != "success"]
    if len(failed) != 1 or failed[0]["status"] != "failed":
        raise ValueError("Research acceptance requires exactly one failed active segment")
    failed = failed[0]
    identifier = failed["segment_id"]
    if (type(failed.get("return_code")) is not int or failed["return_code"] != 0
            or failed.get("reason") != "PHITS reported nonzero geometry diagnostics"
            or failed.get("producer_run_id") != summary["run_id"] or failed.get("retained")):
        raise ValueError("The failed segment has another failure or invocation identity")
    binding = summary["execution_binding"]
    validate_binding(root, manifest, binding, local_only=True)
    validate_results(root, summary)
    validate_parent(root, summary)
    preflight_path = guard.prepare(root / PREFLIGHT)
    preflight = None
    if os.path.lexists(preflight_path):
        if preflight_path.stat().st_size > MAX_RECEIPT_BYTES:
            raise ValueError("Oversized preflight receipt")
        value, _ = _stable_json(preflight_path, guard=guard, label="preflight")
        validate_preflight(value)
        if (value["workspace_root"] != summary.get("workspace_root")
                or value["phase"] != "finished" or not value["child_committed"]
                or value["result_run_id"] != summary["run_id"]
                or value["run_id"] != summary["run_id"]
                or value["summary_sha256"] != summary_sha):
            raise ValueError("Current preflight does not bind the failed invocation")
        preflight = _record(root, preflight_path, guard)

    def rebound(value):
        return guard.prepare(rebind_workspace_path(value,
            recorded_workspace_root=summary.get("workspace_root"), current_workspace_root=root))

    for result in active:
        if result["status"] == "success":
            parsed = parse_phits_geometry_diagnostics_file(rebound(result["phits_out_path"]))
            if parsed["counts"] != result["geometry_diagnostics"]["counts"]:
                raise ValueError("Successful companion geometry evidence disagrees")
    segment = next(s for s in manifest["segments"] if s.get("segment_id") == identifier)
    source = _path(root, segment["phits_input_path"], guard)
    expected = _path(root, segment["expected_output_path"], guard)
    if rebound(failed["phits_input_path"]) != source or rebound(failed["expected_output_path"]) != expected:
        raise ValueError("Failed segment manifest paths disagree")
    staged = _path(root, staging_directory, guard)
    if staged.parent != root / "analysis" or not staged.name.startswith(".phits-segment-run-"):
        raise ValueError("Explicit staging must be directly below workspace analysis")
    captured = failed.get("retained_staging")
    if not isinstance(captured, dict) or captured.get("schema_version") != FAILED_STAGING_SCHEMA:
        raise ValueError("Historical execution lacks prospective staging invocation evidence")
    if captured.get("staging_directory") != staging_directory:
        raise ValueError("Explicit staging does not match the failed invocation")
    contract = next(s for s in binding["segments"] if s["segment_id"] == identifier)
    inputs, declared = phits_staging_contract(workspace_root=root, phits_input=source, guard=guard)
    current = capture_failed_staging(root, staged, segment_id=identifier,
        run_id=summary["run_id"], input_binding=contract["inputs"],
        declared_outputs=declared, expected_output=expected, guard=guard)
    if current != captured or current["missing_required_outputs"]:
        raise ValueError("Retained staging invocation evidence changed or is incomplete")
    phits_out = rebound(failed["phits_out_path"])
    phits_record = _record(root, phits_out, guard)
    if (phits_record["sha256"] != failed.get("phits_out_sha256")
            or phits_record["sha256"] != file_sha256(guard.prepare(staged / "phits.out"))):
        raise ValueError("PHITS companion and retained output disagree")
    with checked_text_lines(phits_out) as stream:
        completion = parse_research_geometry_completion(stream)
    recorded = failed.get("geometry_diagnostics")
    if (not isinstance(recorded, dict) or recorded.get("status") != "error"
            or recorded.get("counts") != completion["diagnostics"]["counts"]
            or recorded.get("schema_version") != completion["diagnostics"]["schema_version"]
            or "reason" in recorded):
        raise ValueError("Recorded and reparsed PHITS diagnostics disagree")
    if (any(type(v) is not int for v in recorded["counts"].values())
            or ("region_pair_counts" in recorded
                and recorded["region_pair_counts"] != completion["region_pair_counts"])):
        raise ValueError("Recorded geometry counts or pair distribution are invalid")
    limits = []
    for input_path in inputs:
        raw, _ = _stable_bytes(input_path, guard=guard, label="prepared input", maximum_bytes=4 * 1024**2)
        limits.extend(re.findall(r"(?im)^\s*maxbch\s*=\s*([0-9]{1,20})\s*(?:#.*)?$", raw.decode("utf-8")))
    if len(limits) != 1 or int(limits[0]) <= 0 or completion["completed_batches"] != int(limits[0]):
        raise ValueError("PHITS final batch does not equal prepared maxbch")
    required = set(declared + [phits_error_output_path(expected)])
    required.update(phits_error_output_path(p) for p in declared
                    if (staged / phits_error_output_path(p).relative_to(root)).is_file())
    permitted = {staged / p.relative_to(root) for p in required}
    for item in current["files"]:
        candidate = _path(root, item["path"], guard)
        if (candidate.parent == staged / expected.parent.relative_to(root)
                and candidate.suffix.casefold() == ".out"
                and candidate.name not in {"phits.out", "batch.out"}
                and candidate not in permitted):
            raise ValueError("Unexpected retained candidate tally outside the manifest-derived set")
    outputs = []
    state = []
    for target in sorted(required):
        evidence = _record(root, staged / target.relative_to(root), guard)
        if evidence["size"] <= 0:
            raise ValueError("Retained tally must not be empty")
        target = guard.prepare(target)
        present = os.path.lexists(target)
        if present and _record(root, target, guard)["sha256"] != evidence["sha256"]:
            raise ValueError("Published destination conflicts with retained tally")
        outputs.append({"source": evidence, "destination": target.relative_to(root).as_posix(),
                        "published": {**evidence, "path": target.relative_to(root).as_posix()}})
        state.append({"path": target.relative_to(root).as_posix(), "present": present})
    if destinations is not None:
        if (not isinstance(destinations, list) or len(destinations) != len(state)
                or [v.get("path") for v in destinations] != [v["path"] for v in state]
                or any(type(v.get("present")) is not bool for v in destinations)):
            raise ValueError("Invalid confirmed destination state")
        state = destinations
    normalized = {k: v for k, v in recorded.items() if k != "source_path"}
    if "source_path" in recorded:
        if rebound(recorded["source_path"]) != phits_out:
            raise ValueError("Diagnostic source identity disagrees")
        normalized["source_path"] = phits_record["path"]
    return {"schema_version": SCHEMA, "policy": POLICY, "accepted_segment_id": identifier,
            "summary": {"path": SUMMARY, "sha256": summary_sha},
            "manifest": {"path": MANIFEST, "sha256": manifest_sha,
                         "content_sha256": manifest_sha256(manifest)},
            "preflight": preflight, "execution_binding_sha256": digest_object(binding),
            "phits_out": phits_record, "recorded_diagnostics": normalized,
            **completion, "maxbch": int(limits[0]), "staging": current,
            "outputs": outputs, "destination_state": state}


def preview(workspace_root: Path, *, staging_directory: str) -> dict[str, Any]:
    root = workspace_root.expanduser().resolve()
    with WorkspaceExecutionLease(root, create=False), WorkspaceOutputGuard(root, read_only=True) as guard:
        if os.path.lexists(guard.prepare(root / RECEIPT_PATH)):
            raise ValueError("A research acceptance receipt already exists")
        plan = _context(root, staging_directory, guard)
        return {"plan": plan, "plan_digest": digest_object(plan)}


def apply(workspace_root: Path, *, staging_directory: str, expected_plan_digest: str,
          acknowledge_research_only: bool, reason: str) -> dict[str, Any]:
    if acknowledge_research_only is not True:
        raise ValueError("Explicit research-only acknowledgement is required")
    reason = _operator_reason(reason)
    root = workspace_root.expanduser().resolve()
    with WorkspaceExecutionLease(root, create=False), WorkspaceOutputGuard(root) as guard:
        if os.path.lexists(guard.prepare(root / RECEIPT_PATH)):
            raise ValueError("A research acceptance receipt already exists")
        plan = _context(root, staging_directory, guard)
        if digest_object(plan) != expected_plan_digest:
            raise ValueError("Research acceptance plan changed; preview it again")

        def recheck():
            if _context(root, staging_directory, guard, destinations=plan["destination_state"]) != plan:
                raise ValueError("Research acceptance evidence changed before publication")

        receipt = {"schema_version": SCHEMA, "research_only": True, "purpose": PURPOSE,
                   "created_at": datetime.now(timezone.utc).isoformat(), "tool_version": __version__,
                   "plan_digest": expected_plan_digest, "plan": plan,
                   "operator_acknowledgement": True, "reason": reason, "not_for": NOT_FOR}
        receipt["receipt_content_sha256"] = digest_object(receipt)
        for output in plan["outputs"]:
            destination = _path(root, output["destination"], guard)
            recheck()
            if not os.path.lexists(destination):
                _publish_file_new_only(guard, _path(root, output["source"]["path"], guard), destination,
                    expected_sha256=output["source"]["sha256"], validate_before_publish=recheck)
        def finalize():
            recheck()
            for output in plan["outputs"]:
                if _record(root, _path(root, output["destination"], guard), guard) != output["published"]:
                    raise ValueError("Published tally changed before receipt publication")

        _publish_json_new_only(guard, root / RECEIPT_PATH, receipt, validate_before_publish=finalize)
        return receipt


def validate(workspace_root: Path, summary: Mapping[str, Any] | None = None,
             manifest: Mapping[str, Any] | None = None) -> dict[str, Any]:
    root = workspace_root.expanduser().resolve()
    with WorkspaceExecutionLease(root, create=False), WorkspaceOutputGuard(root, read_only=True) as guard:
        receipt, _ = _stable_json(root / RECEIPT_PATH, guard=guard, label="research receipt")
        raw, _ = _stable_bytes(root / RECEIPT_PATH, guard=guard, label="research receipt")
        canonical = (json.dumps(receipt, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        if raw not in (canonical, canonical.replace(b"\n", b"\r\n")):
            raise ValueError("Research receipt serialization changed")
        fields = {"schema_version", "research_only", "purpose", "created_at", "tool_version",
                  "plan_digest", "plan", "operator_acknowledgement", "reason", "not_for",
                  "receipt_content_sha256"}
        if (set(receipt) != fields or receipt.get("schema_version") != SCHEMA
                or receipt.get("research_only") is not True or receipt.get("purpose") != PURPOSE
                or receipt.get("operator_acknowledgement") is not True or receipt.get("not_for") != NOT_FOR
                or not isinstance(receipt.get("tool_version"), str)
                or re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+[A-Za-z0-9.+-]*", receipt["tool_version"]) is None):
            raise ValueError("Unsupported or malformed research acceptance receipt")
        _operator_reason(receipt["reason"])
        created = datetime.fromisoformat(receipt["created_at"])
        if created.utcoffset() is None or created.utcoffset().total_seconds() != 0:
            raise ValueError("Receipt creation time must be UTC")
        core = {k: v for k, v in receipt.items() if k != "receipt_content_sha256"}
        if digest_object(core) != receipt["receipt_content_sha256"]:
            raise ValueError("Research receipt content changed")
        plan = receipt["plan"]
        if not isinstance(plan, dict) or digest_object(plan) != receipt["plan_digest"]:
            raise ValueError("Research receipt plan digest disagrees")
        current = _context(root, plan["staging"]["staging_directory"], guard,
                           destinations=plan["destination_state"])
        if current != plan:
            raise ValueError("Research receipt no longer matches execution evidence")
        for output in current["outputs"]:
            observed = _record(root, _path(root, output["destination"], guard), guard)
            if (observed["sha256"], observed["size"]) != (output["source"]["sha256"], output["source"]["size"]):
                raise ValueError("Published research output changed")
        for supplied, path in ((summary, SUMMARY), (manifest, MANIFEST)):
            if supplied is not None:
                actual, _ = _stable_json(root / path, guard=guard, label="supplied evidence")
                if actual != supplied:
                    raise ValueError("Supplied evidence differs from current research evidence")
        return receipt


def marker(workspace_root: Path, receipt: Mapping[str, Any]) -> dict[str, str]:
    return {"receipt_sha256": file_sha256(workspace_root / RECEIPT_PATH),
            "accepted_segment_id": receipt["plan"]["accepted_segment_id"]}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Review saved geometry recovery for research use without recalculation.")
    parser.add_argument("--workspace-root", type=Path, required=True)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--preview", action="store_true")
    mode.add_argument("--apply", action="store_true")
    mode.add_argument("--verify-only", action="store_true")
    parser.add_argument("--staging-directory")
    parser.add_argument("--plan-digest")
    parser.add_argument("--acknowledge-research-only", action="store_true")
    parser.add_argument("--reason", default="")
    args = parser.parse_args(argv)
    try:
        if args.verify_only:
            validate(args.workspace_root)
            print("Research-only receipt verified. Original PHITS status remains failed.")
            return 0
        if not args.staging_directory:
            raise ValueError("Explicit --staging-directory is required")
        if args.preview:
            result = preview(args.workspace_root, staging_directory=args.staging_directory)
        else:
            result = apply(args.workspace_root, staging_directory=args.staging_directory,
                expected_plan_digest=args.plan_digest, acknowledge_research_only=args.acknowledge_research_only,
                reason=args.reason)
        print(json.dumps(result, ensure_ascii=True, indent=2))
        return 0
    except (OSError, ValueError, TypeError, KeyError, StopIteration) as exc:
        print(f"Research acceptance unavailable: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
