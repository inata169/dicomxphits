"""Evidence and planning for explicitly requested incomplete-segment execution."""
from __future__ import annotations

import hashlib
import json
import os
import re
from copy import deepcopy
from pathlib import Path

from dicomxphits.safe_output import WorkspaceOutputGuard
from dicomxphits.sumtally_inputs import file_sha256, manifest_sha256
from dicomxphits.workspace_execution import LOCK_NAME, WorkspaceExecutionLease

BINDING_SCHEMA = "dicomxphits_segment_execution_binding_v1"
PREPARATION_FILES = (
    "analysis/phits_generation_summary.json",
    "analysis/public_preparation_workspace_summary.json",
)


def digest_object(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
        allow_nan=False).encode("utf-8")).hexdigest()


def _api():
    from dicomxphits import run_segments as api
    return api


def _local_path(root, value):
    api = _api()
    path = api.resolve_workspace_file(root, value, label="execution evidence")
    if ".." in Path(value).parts:
        raise ValueError("Unsafe execution evidence path")
    return path


def _evidence(root, paths):
    return [{"path": path.resolve().relative_to(root).as_posix(),
             "sha256": file_sha256(path)} for path in sorted(set(paths))]


def capture_binding(root, manifest, paths, *, include_runtime=True):
    """Capture actual staged dependencies; unavailable tool evidence forbids retry.

The explicitly configured installation is the bounded runtime dependency set.
No system lookup or executable-name search is performed. Workspace contents are
bound separately and excluded from the installation digest when nested there.
"""
    api = _api()
    root = root.resolve()
    current_manifest, _ = api.load_manifest(root)
    if manifest_sha256(current_manifest) != manifest_sha256(manifest):
        raise ValueError("Execution manifest changed during execution")
    unavailable = []
    segments = []
    input_files = set()
    ids = []
    with WorkspaceOutputGuard(root, read_only=True) as guard:
        for segment in manifest["segments"]:
            identifier = str(segment.get("segment_id") or segment.get("segment_index") or "unknown")
            ids.append(identifier)
            if not api.segment_active_state(segment)[0]:
                continue
            source = _local_path(root, segment.get("phits_input_path", ""))
            guard.prepare(source)
            environment_digest = digest_object(api.phits_environment(source))
            expected = _local_path(root, segment.get("expected_output_path", ""))
            inputs, outputs = api.phits_staging_contract(
                workspace_root=root, phits_input=source, guard=guard)
            input_files.update(inputs)
            writes = api.persistent_segment_outputs(expected_output=expected, declared_outputs=outputs)
            required = set(outputs + [api.phits_error_output_path(p) for p in outputs])
            required.update([expected.parent / "phits_stdout.txt",
                expected.parent / "phits_stderr.txt", expected.parent / api.ROOT_PHITS_OUT])
            for path in inputs:
                text = path.read_text(encoding="utf-8", errors="strict")
                # Prepared inputs use recursive infl includes and built-in source
                # spectra. External file sources are not part of this contract.
                if re.search(r"(?im)^\s*(?:file\s*\((?!6\s*\))\d+\)|s-type\s*=\s*(?:17|18))", text):
                    unavailable.append("Unsupported external input dependency form")
            segments.append({"segment_id": identifier,
                "inputs": _evidence(root, inputs),
                # Preserve lexical targets here; guarded publication preflight
                # rejects linked outputs without following their destinations.
                "writes": sorted(p.relative_to(root).as_posix() for p in set(writes)),
                "required_outputs": sorted(p.relative_to(root).as_posix() for p in required),
                # Hash environment, never persist its potentially sensitive values.
                "environment_sha256": environment_digest})
        if len(ids) != len(set(ids)):
            raise ValueError("Duplicate segment identities")
        prep = []
        for relative in PREPARATION_FILES:
            path = root / relative
            if path.parent.exists():
                guard.prepare(path)
            if path.is_file():
                prep.extend(_evidence(root, [path]))
            else:
                unavailable.append("Preparation evidence is missing")
        all_inputs = {p.resolve().relative_to(root).as_posix() for p in input_files}
        all_inputs.update(PREPARATION_FILES)
        all_inputs.update({"segments/segment_manifest.json", api.SUMMARY_RELATIVE_PATH.as_posix()})
        write_owner = {}
        for segment in segments:
            for relative in segment["writes"]:
                if relative in all_inputs or relative in write_owner or relative == LOCK_NAME:
                    raise ValueError("Segment output collision with another segment or bound input")
                if relative.startswith("analysis/segment_attempt_history/"):
                    raise ValueError("Segment output collides with retained history")
                write_owner[relative] = segment["segment_id"]
        if len(segments) > 1 and set(write_owner).intersection({api.ROOT_PHITS_OUT, api.ROOT_BATCH_OUT}):
            raise ValueError("Shared root cleanup collides with segment output")
        if all_inputs.intersection({api.ROOT_BATCH_OUT, api.ROOT_PHITS_OUT, LOCK_NAME}):
            raise ValueError("Segment cleanup collides with a bound input")
    tool = None
    executable = Path(paths.phits_executable_path or "")
    installation = Path(paths.phits_root_folder or "")
    if not include_runtime:
        pass
    elif (not executable.is_absolute() or not installation.is_absolute()
        or not executable.is_file() or not installation.is_dir()
        or installation.resolve() == Path(installation.anchor)
        or installation.resolve() == root or root in installation.resolve().parents):
        unavailable.append("Configured PHITS installation identity is unavailable")
    else:
        files = []
        installation = installation.resolve()
        for directory, dirs, names in os.walk(installation, followlinks=False):
            base = Path(directory)
            for name in list(dirs):
                candidate = base / name
                if candidate.resolve() == root:
                    dirs.remove(name)
                elif candidate.is_symlink() or getattr(candidate.lstat(), "st_file_attributes", 0) & 0x400:
                    raise ValueError("Linked runtime dependency is not supported")
            for name in names:
                candidate = base / name
                if candidate.is_symlink() or getattr(candidate.lstat(), "st_file_attributes", 0) & 0x400:
                    raise ValueError("Linked runtime dependency is not supported")
                files.append({"path": candidate.relative_to(installation).as_posix(),
                    "sha256": file_sha256(candidate)})
        tool = {"root": str(installation), "executable": str(executable.resolve()),
            "executable_sha256": file_sha256(executable),
            "files": sorted(files, key=lambda item: item["path"])}
    return {"schema_version": BINDING_SCHEMA, "workspace_root": str(root),
        "manifest_sha256": manifest_sha256(manifest), "segment_ids": ids,
        "segments": segments, "preparation": prep, "tool": tool,
        "retry_unavailable": sorted(set(unavailable))}


def check_binding_shape(binding):
    if not isinstance(binding, dict) or binding.get("schema_version") != BINDING_SCHEMA:
        raise ValueError("Missing execution binding")
    for name in ("segment_ids", "segments", "preparation", "retry_unavailable"):
        if not isinstance(binding.get(name), list):
            raise ValueError("Malformed execution binding")
    if any(not isinstance(value, str) or not value for value in binding["segment_ids"]):
        raise ValueError("Malformed execution binding identities")
    if len(binding["segment_ids"]) != len(set(binding["segment_ids"])):
        raise ValueError("Duplicate execution binding identities")
    if not isinstance(binding.get("workspace_root"), str):
        raise ValueError("Missing binding workspace")
    if not isinstance(binding.get("manifest_sha256"), str) or not re.fullmatch(r"[0-9a-f]{64}", binding["manifest_sha256"]):
        raise ValueError("Invalid binding digest")
    def files(value):
        if not isinstance(value, list):
            raise ValueError("Missing file evidence")
        paths = []
        for item in value:
            if (not isinstance(item, dict) or not isinstance(item.get("path"), str)
                or not item["path"] or not isinstance(item.get("sha256"), str)
                or not re.fullmatch(r"[0-9a-f]{64}", item["sha256"])):
                raise ValueError("Malformed file evidence")
            paths.append(item["path"])
        if len(paths) != len(set(paths)):
            raise ValueError("Duplicate file evidence")
    files(binding["preparation"])
    seen = set()
    for item in binding["segments"]:
        if not isinstance(item, dict) or not isinstance(item.get("segment_id"), str):
            raise ValueError("Malformed segment binding")
        if item["segment_id"] in seen:
            raise ValueError("Duplicate segment binding")
        seen.add(item["segment_id"])
        files(item.get("inputs"))
        for key in ("writes", "required_outputs"):
            value = item.get(key)
            if not isinstance(value, list) or any(not isinstance(p, str) or not p for p in value):
                raise ValueError("Malformed segment output set")
            if len(value) != len(set(value)):
                raise ValueError("Duplicate segment output paths")
    if any(not isinstance(reason, str) for reason in binding["retry_unavailable"]):
        raise ValueError("Invalid retry availability")


def validate_binding(root, manifest, binding, paths=None, *, local_only=False):
    from dicomxphits.prepare_3dcrt_workspace import ExternalToolPaths
    check_binding_shape(binding)
    root = root.resolve()
    if not local_only and binding.get("workspace_root") != str(root):
        raise ValueError("Retry requires the original workspace root")
    if binding.get("manifest_sha256") != manifest_sha256(manifest):
        raise ValueError("Execution manifest changed; prepare a new workspace")
    if paths is None:
        tool = binding.get("tool") or {}
        paths = ExternalToolPaths(phits_root_folder=tool.get("root"),
            phits_executable_path=tool.get("executable"), phits2dicom_executable_path=None)
    observed = capture_binding(root, manifest, paths, include_runtime=not local_only)
    expected = deepcopy(binding)
    if local_only:
        # Downstream inspection does not launch PHITS. Its recorded installation
        # is not authority to read tools on another computer after relocation.
        expected["workspace_root"] = str(root)
        for value in (expected, observed):
            value.pop("tool", None)
            value.pop("retry_unavailable", None)
            for segment in value["segments"]:
                segment.pop("environment_sha256", None)
    if observed != expected:
        raise ValueError("Execution inputs, dependencies, or runtime changed; prepare a new workspace")


def result_evidence(root, segment_binding):
    paths = [_local_path(root, item) for item in segment_binding["required_outputs"]]
    # Bind optional outputs if present as well, so retained logs are protected.
    paths.extend(_local_path(root, item) for item in segment_binding["writes"]
        if _local_path(root, item).is_file())
    with WorkspaceOutputGuard(root, read_only=True) as guard:
        for path in paths:
            guard.prepare(path)
            if not path.is_file():
                raise ValueError("Required completed segment artifact is missing")
        return _evidence(root, paths)


def validate_results(root, summary):
    from dicomxphits.phits_geometry_diagnostics import require_clean_phits_geometry_diagnostics
    binding = summary["execution_binding"]
    by_id = {item["segment_id"]: item for item in binding["segments"]}
    for result in summary["segments"]:
        if result["status"] != "success":
            continue
        contract = by_id.get(result["segment_id"])
        if contract is None or result.get("output_evidence") != result_evidence(root, contract):
            raise ValueError("Completed segment artifacts changed; prepare a new workspace")
        require_clean_phits_geometry_diagnostics(result["geometry_diagnostics"])


def validate_v4(summary):
    binding = summary.get("execution_binding")
    if binding is None and summary.get("stage_status") == "gate_failed":
        return
    check_binding_shape(binding)
    if binding["segment_ids"] != [item.get("segment_id") for item in summary["segments"]]:
        raise ValueError("Execution binding segment identities do not match")
    if binding.get("manifest_sha256") != summary.get("manifest_sha256"):
        raise ValueError("Execution binding manifest does not match")
    if [i["segment_id"] for i in binding["segments"]] != [i["segment_id"] for i in summary["segments"] if i["status"] != "skipped"]:
        raise ValueError("Active segment binding does not match")
    for item in summary["segments"]:
        if not isinstance(item.get("retained"), bool):
            raise ValueError("Missing retained segment flag")
        if item.get("retained") and item.get("status") != "success":
            raise ValueError("Only success may be retained")
        if item.get("status") == "success":
            if type(item.get("return_code")) is not int or item["return_code"] != 0:
                raise ValueError("Invalid successful return code")
            if not isinstance(item.get("output_evidence"), list) or not item["output_evidence"]:
                raise ValueError("Missing complete output evidence")
            if not isinstance(item.get("producer_run_id"), str) or not item["producer_run_id"]:
                raise ValueError("Missing result producer identity")
            if not item["retained"] and item["producer_run_id"] != summary["run_id"]:
                raise ValueError("New result belongs to another invocation")
    retained = sum(item.get("retained", False) for item in summary["segments"])
    if summary.get("retained_active_segment_count") != retained:
        raise ValueError("Incorrect retained segment count")
    if retained and not isinstance(summary.get("parent_attempt"), dict):
        raise ValueError("Missing retained attempt provenance")


def plan_incomplete(root, paths, *, expected_summary_sha256=None):
    api = _api()
    root = root.expanduser().resolve()
    # Existing lock only: planning must never create an ownership artifact.
    with WorkspaceExecutionLease(root, create=False) as lease:
        if lease.executing:
            raise ValueError("An invocation is still running in this workspace")
        manifest, _ = api.load_manifest(root)
        source_path = api.summary_path(root)
        with WorkspaceOutputGuard(root, read_only=True) as guard:
            guard.prepare(source_path)
            source_bytes = source_path.read_bytes()
        source_digest = hashlib.sha256(source_bytes).hexdigest()
        if expected_summary_sha256 is not None and source_digest != expected_summary_sha256:
            raise ValueError("Retry preview changed; create a new preview")
        summary = json.loads(source_bytes)
        if api.validate_segment_execution_summary(summary, require_success=False) != api.SEGMENT_EXECUTION_SCHEMA_V4:
            raise ValueError("Legacy evidence cannot authorize retry; prepare a new workspace")
        binding = summary.get("execution_binding")
        check_binding_shape(binding)
        if binding["retry_unavailable"]:
            raise ValueError("Retry evidence unavailable; prepare a new workspace: " + "; ".join(binding["retry_unavailable"]))
        from dicomxphits.prepare_3dcrt_workspace import validate_public_strict_3dcrt_gate
        validate_public_strict_3dcrt_gate(manifest)
        api.require_reusable_gantry_geometry_contract(manifest)
        validate_binding(root, manifest, binding, paths)
        validate_results(root, summary)
        validate_parent(root, summary)
        from dicomxphits.workspace_recovery import validate_segment_progress_for_workspace
        validate_segment_progress_for_workspace(root, summary)
        return {"workspace_root": str(root), "source_sha256": source_digest,
            "retained": [i["segment_id"] for i in summary["segments"] if i["status"] == "success"],
            "scheduled": [i["segment_id"] for i in summary["segments"] if i["status"] not in {"success", "skipped"}],
            "skipped": [i["segment_id"] for i in summary["segments"] if i["status"] == "skipped"],
            "summary": summary}


def validate_parent(root, summary, *, seen=None):
    parent = summary.get("parent_attempt")
    if parent is None:
        return
    if not isinstance(parent, dict):
        raise ValueError("Malformed attempt provenance")
    path = _local_path(root, str(parent.get("path") or ""))
    seen = set() if seen is None else seen
    if path in seen or len(seen) >= 256:
        raise ValueError("Cyclic or excessive attempt history")
    seen.add(path)
    if path.parent.parent != root / "analysis" / "segment_attempt_history":
        raise ValueError("Unsafe attempt history path")
    with WorkspaceOutputGuard(root, read_only=True) as guard:
        guard.prepare(path)
        data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() != parent.get("sha256"):
        raise ValueError("Attempt history digest mismatch")
    old = json.loads(data)
    _api().validate_segment_execution_summary(old, require_success=False)
    if old["execution_binding"] != summary["execution_binding"] or old["run_id"] == summary["run_id"]:
        raise ValueError("Attempt history binding mismatch")
    by_id = {i["segment_id"]: i for i in old["segments"]}
    for item in summary["segments"]:
        if item.get("retained"):
            original = deepcopy(by_id.get(item["segment_id"]))
            if original is None:
                raise ValueError("Missing retained source")
            original["retained"] = True
            if original != item:
                raise ValueError("Retained result differs from preserved source")
    validate_parent(root, old, seen=seen)
