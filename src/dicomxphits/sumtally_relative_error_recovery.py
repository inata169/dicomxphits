from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import secrets
from pathlib import Path
from typing import Any, Mapping

from dicomxphits.prepare_rtdose import validate_sumtally_manifest_binding
from dicomxphits.prepare_sumtally import transitive_phits_include_paths
from dicomxphits.phits_observation_format import MAX_TALLY_BYTES
from dicomxphits.run_segments import phits_error_output_path
from dicomxphits.safe_output import WorkspaceOutputGuard
from dicomxphits.sumtally_inputs import file_sha256


PLAN_SCHEMA_VERSION = "dicomxphits_sumtally_relative_error_recovery_plan_v1"
RECEIPT_SCHEMA_VERSION = "dicomxphits_sumtally_relative_error_recovery_v1"
RECOVERY_CONTRACT_VERSION = "retained_sumtally_relative_error_recovery_v1"
GENERATION_SCHEMA_VERSION = "dicomxphits_public_sumtally_generation_v1"
EXECUTION_SCHEMA_VERSION = "dicomxphits_public_sumtally_execution_v1"
RECEIPT_RELATIVE_PATH = (
    Path("analysis") / "sumtally_relative_error_recovery_summary.json"
)
GENERATION_RELATIVE_PATH = Path("analysis") / "sumtally_generation_summary.json"
EXECUTION_RELATIVE_PATH = Path("analysis") / "sumtally_execution_summary.json"
MAX_JSON_BYTES = 16 * 1024**2
STAGING_NAME = re.compile(r"\.sumtally-run-[0-9a-f]{16}\Z")


class SumtallyRelativeErrorRecoveryUnavailable(ValueError):
    """The retained evidence cannot safely authorize recovery."""


def _absolute(path: Path) -> Path:
    return Path(os.path.abspath(os.fspath(path)))


def _same_path(left: Path, right: Path) -> bool:
    return os.path.normcase(os.fspath(_absolute(left))) == os.path.normcase(
        os.fspath(_absolute(right))
    )


def _canonical_sha256(value: Any) -> str:
    try:
        payload = json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("ascii")
    except (TypeError, ValueError) as exc:
        raise SumtallyRelativeErrorRecoveryUnavailable(
            "recovery evidence is not canonically serializable"
        ) from exc
    return hashlib.sha256(payload).hexdigest()


def _relative(root: Path, path: Path) -> str:
    try:
        relative = _absolute(path).relative_to(_absolute(root))
    except ValueError as exc:
        raise SumtallyRelativeErrorRecoveryUnavailable(
            f"recovery path escapes the selected workspace: {path}"
        ) from exc
    return relative.as_posix()


def _workspace_path(
    root: Path,
    value: str | Path,
    *,
    guard: WorkspaceOutputGuard,
) -> Path:
    path = Path(value)
    if not path.is_absolute():
        path = root / path
    path = _absolute(path)
    _relative(root, path)
    guard.prepare(path)
    return path


def _stable_bytes(
    path: Path,
    *,
    guard: WorkspaceOutputGuard,
    label: str,
    maximum_bytes: int | None = None,
) -> tuple[bytes, str]:
    path = guard.prepare(_absolute(path))
    if not path.is_file():
        raise SumtallyRelativeErrorRecoveryUnavailable(
            f"{label} must be an existing ordinary file"
        )
    if maximum_bytes is not None and path.stat().st_size > maximum_bytes:
        raise SumtallyRelativeErrorRecoveryUnavailable(f"{label} exceeds its size limit")
    before = file_sha256(path)
    try:
        content = path.read_bytes()
    except OSError as exc:
        raise SumtallyRelativeErrorRecoveryUnavailable(f"{label} is not readable") from exc
    digest = hashlib.sha256(content).hexdigest()
    if digest != before or file_sha256(path) != before:
        raise SumtallyRelativeErrorRecoveryUnavailable(f"{label} changed while being read")
    return content, digest


def _stable_json(
    path: Path,
    *,
    guard: WorkspaceOutputGuard,
    label: str,
) -> tuple[dict[str, Any], str]:
    raw, digest = _stable_bytes(
        path,
        guard=guard,
        label=label,
        maximum_bytes=MAX_JSON_BYTES,
    )
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise SumtallyRelativeErrorRecoveryUnavailable(f"{label} is not valid JSON") from exc
    if not isinstance(value, dict):
        raise SumtallyRelativeErrorRecoveryUnavailable(f"{label} JSON root must be an object")
    return value, digest


def _require_same_workspace(
    root: Path,
    generation: Mapping[str, Any],
    execution: Mapping[str, Any],
) -> None:
    summaries = (
        ("generation", generation, GENERATION_SCHEMA_VERSION),
        ("execution", execution, EXECUTION_SCHEMA_VERSION),
    )
    for label, summary, expected_schema in summaries:
        if summary.get("schema_version") != expected_schema:
            raise SumtallyRelativeErrorRecoveryUnavailable(
                f"Sumtally {label} summary has an unsupported schema_version"
            )
        recorded = str(summary.get("workspace_root") or "")
        if not recorded or not _same_path(Path(recorded), root):
            raise SumtallyRelativeErrorRecoveryUnavailable(
                f"Sumtally {label} evidence is not bound to the selected unchanged workspace"
            )
        if summary.get("stage_status") != "success":
            raise SumtallyRelativeErrorRecoveryUnavailable(
                f"Sumtally {label} summary is not successful"
            )


def _prepare_summary_paths(
    root: Path,
    generation: Mapping[str, Any],
    execution: Mapping[str, Any],
    *,
    guard: WorkspaceOutputGuard,
) -> None:
    outputs = generation.get("outputs")
    if not isinstance(outputs, Mapping):
        raise SumtallyRelativeErrorRecoveryUnavailable(
            "Sumtally generation output evidence is unavailable"
        )
    for field in ("sum_input", "sumtally_input", "sumtally_output"):
        value = str(outputs.get(field) or "")
        if not value:
            raise SumtallyRelativeErrorRecoveryUnavailable(
                f"Sumtally generation evidence is missing outputs.{field}"
            )
        _workspace_path(root, value, guard=guard)
    execution_output = str(execution.get("expected_sumtally_output") or "")
    if not execution_output:
        raise SumtallyRelativeErrorRecoveryUnavailable(
            "Sumtally execution output evidence is unavailable"
        )
    _workspace_path(root, execution_output, guard=guard)
    for field in ("segment_output_evidence", "wrapper_include_evidence"):
        records = generation.get(field)
        if not isinstance(records, list):
            raise SumtallyRelativeErrorRecoveryUnavailable(
                f"Sumtally {field} is unavailable"
            )
        for record in records:
            if not isinstance(record, Mapping) or not str(record.get("path") or ""):
                raise SumtallyRelativeErrorRecoveryUnavailable(
                    f"Sumtally {field} is invalid"
                )
            _workspace_path(root, str(record["path"]), guard=guard)


def _relative_digest_records(root: Path, records: Any) -> list[dict[str, str]]:
    if not isinstance(records, list):
        raise SumtallyRelativeErrorRecoveryUnavailable(
            "Sumtally dependency digest evidence is unavailable"
        )
    result: list[dict[str, str]] = []
    for record in records:
        if not isinstance(record, Mapping):
            raise SumtallyRelativeErrorRecoveryUnavailable(
                "Sumtally dependency digest evidence is invalid"
            )
        path = str(record.get("path") or "")
        digest = str(record.get("sha256") or "")
        if not path or not digest:
            raise SumtallyRelativeErrorRecoveryUnavailable(
                "Sumtally dependency digest evidence is incomplete"
            )
        evidence_path = Path(path)
        if not evidence_path.is_absolute():
            evidence_path = root / evidence_path
        result.append({"path": _relative(root, evidence_path), "sha256": digest})
    return sorted(result, key=lambda item: item["path"].casefold())


def _pair_receipt_fields(pair: Mapping[str, Any]) -> dict[str, Any]:
    return {
        field: pair[field]
        for field in (
            "schema_version",
            "semantics",
            "dose_sha256",
            "error_sha256",
            "sum_input_sha256",
            "mesh_geometry_sha256",
            "cell_count",
            "pair_metadata_sha256",
            "validated",
        )
    }


def _current_context(
    root: Path,
    *,
    guard: WorkspaceOutputGuard,
) -> dict[str, Any]:
    generation_path = root / GENERATION_RELATIVE_PATH
    execution_path = root / EXECUTION_RELATIVE_PATH
    generation, generation_sha256 = _stable_json(
        generation_path,
        guard=guard,
        label="Sumtally generation summary",
    )
    execution, execution_sha256 = _stable_json(
        execution_path,
        guard=guard,
        label="Sumtally execution summary",
    )
    _require_same_workspace(root, generation, execution)
    if execution.get("combined_relative_error_evidence") is not None:
        raise SumtallyRelativeErrorRecoveryUnavailable(
            "direct combined relative-error evidence is already present or conflicting"
        )
    _prepare_summary_paths(root, generation, execution, guard=guard)
    manifest = _workspace_path(
        root,
        Path("segments") / "segment_manifest.json",
        guard=guard,
    )
    try:
        binding = validate_sumtally_manifest_binding(
            workspace_root=root,
            generation=generation,
            execution=execution,
        )
    except Exception as exc:
        raise SumtallyRelativeErrorRecoveryUnavailable(
            f"current Sumtally evidence does not validate: {exc}"
        ) from exc
    outputs = generation["outputs"]
    sum_input = _workspace_path(root, str(outputs["sum_input"]), guard=guard)
    sumtally_input = _workspace_path(
        root,
        str(outputs["sumtally_input"]),
        guard=guard,
    )
    dose = _workspace_path(
        root,
        str(binding["sumtally_output_path"]),
        guard=guard,
    )
    error = phits_error_output_path(dose)
    _relative(root, error)
    guard.prepare(error)
    bound_manifest = _workspace_path(
        root,
        str(binding["manifest_path"]),
        guard=guard,
    )
    if not _same_path(bound_manifest, manifest):
        raise SumtallyRelativeErrorRecoveryUnavailable(
            "validated Sumtally manifest path differs from the guarded public manifest"
        )
    for label, path, expected in (
        ("generated Sumtally wrapper", sum_input, binding["sum_input_sha256"]),
        (
            "generated sumtally input",
            sumtally_input,
            binding["sumtally_input_sha256"],
        ),
    ):
        _raw, current_sha256 = _stable_bytes(path, guard=guard, label=label)
        if current_sha256 != expected:
            raise SumtallyRelativeErrorRecoveryUnavailable(
                f"{label} does not match recorded Sumtally evidence"
            )
    recorded_includes = _relative_digest_records(
        root, generation["wrapper_include_evidence"]
    )
    for record in recorded_includes:
        include_path = _workspace_path(root, record["path"], guard=guard)
        try:
            include_path.relative_to(sum_input.parent)
        except ValueError as exc:
            raise SumtallyRelativeErrorRecoveryUnavailable(
                "a recorded Sumtally include is outside its execution directory"
            ) from exc
        _raw, current_sha256 = _stable_bytes(
            include_path,
            guard=guard,
            label="generated Sumtally include",
        )
        if current_sha256 != record["sha256"]:
            raise SumtallyRelativeErrorRecoveryUnavailable(
                "generated Sumtally include does not match recorded evidence"
            )
    if (
        file_sha256(generation_path) != generation_sha256
        or file_sha256(execution_path) != execution_sha256
    ):
        raise SumtallyRelativeErrorRecoveryUnavailable(
            "Sumtally summary evidence changed while being validated"
        )
    return {
        "generation": generation,
        "execution": execution,
        "generation_sha256": generation_sha256,
        "execution_sha256": execution_sha256,
        "binding": binding,
        "generation_path": generation_path,
        "execution_path": execution_path,
        "manifest": manifest,
        "sum_input": sum_input,
        "sumtally_input": sumtally_input,
        "dose": dose,
        "error": error,
    }


def _publish_file_new_only(
    guard: WorkspaceOutputGuard,
    source: Path,
    destination: Path,
    *,
    expected_sha256: str,
) -> None:
    """Atomically publish a guarded source without replacing a destination."""

    destination = guard.prepare_file_target(destination, create_parents=True)
    if os.path.lexists(destination):
        raise FileExistsError(f"recovery destination already exists: {destination}")
    temporary = destination.with_name(
        f".{destination.name}.dicomxphits-{secrets.token_hex(8)}.tmp"
    )
    try:
        guard.copy_file(source, temporary, overwrite=False)
        if file_sha256(temporary) != expected_sha256:
            raise SumtallyRelativeErrorRecoveryUnavailable(
                "retained error changed while being copied; nothing was published"
            )
        guard.prepare_file_target(destination)
        if os.name == "nt":
            os.rename(temporary, destination)
        else:
            os.link(temporary, destination)
    finally:
        if os.path.lexists(temporary):
            guard.unlink(temporary)


def _publish_json_new_only(
    guard: WorkspaceOutputGuard,
    destination: Path,
    value: Mapping[str, Any],
) -> None:
    """Atomically publish one JSON object without replacing a destination."""

    destination = guard.prepare_file_target(destination, create_parents=True)
    if os.path.lexists(destination):
        raise FileExistsError(f"recovery destination already exists: {destination}")
    temporary = destination.with_name(
        f".{destination.name}.dicomxphits-{secrets.token_hex(8)}.tmp"
    )
    try:
        guard.write_json(temporary, value, overwrite=False)
        guard.prepare_file_target(destination)
        if os.name == "nt":
            os.rename(temporary, destination)
        else:
            os.link(temporary, destination)
    finally:
        if os.path.lexists(temporary):
            guard.unlink(temporary)


def _receipt_core(
    root: Path,
    context: Mapping[str, Any],
    pair: Mapping[str, Any],
) -> dict[str, Any]:
    binding = context["binding"]
    generation = context["generation"]
    return {
        "schema_version": RECEIPT_SCHEMA_VERSION,
        "contract_version": RECOVERY_CONTRACT_VERSION,
        "workspace": ".",
        "generation_summary": {
            "path": GENERATION_RELATIVE_PATH.as_posix(),
            "sha256": context["generation_sha256"],
        },
        "execution_summary": {
            "path": EXECUTION_RELATIVE_PATH.as_posix(),
            "sha256": context["execution_sha256"],
        },
        "manifest": {
            "path": _relative(root, context["manifest"]),
            "sha256": binding["manifest_sha256"],
        },
        "sum_input": {
            "path": _relative(root, context["sum_input"]),
            "sha256": binding["sum_input_sha256"],
        },
        "sumtally_input": {
            "path": _relative(root, context["sumtally_input"]),
            "sha256": binding["sumtally_input_sha256"],
        },
        "segment_output_evidence": _relative_digest_records(
            root, generation["segment_output_evidence"]
        ),
        "wrapper_include_evidence": _relative_digest_records(
            root, generation["wrapper_include_evidence"]
        ),
        "official_pair": {
            "dose_path": _relative(root, context["dose"]),
            "error_path": _relative(root, context["error"]),
            **_pair_receipt_fields(pair),
        },
    }


def _validate_receipt_object(
    root: Path,
    receipt: Mapping[str, Any],
    context: Mapping[str, Any],
    pair: Mapping[str, Any],
    *,
    guard: WorkspaceOutputGuard,
) -> None:
    receipt_without_identity = dict(receipt)
    recorded_identity = receipt_without_identity.pop("receipt_sha256", None)
    if not isinstance(recorded_identity, str) or len(recorded_identity) != 64:
        raise SumtallyRelativeErrorRecoveryUnavailable(
            "recovery receipt canonical identity is missing"
        )
    if _canonical_sha256(receipt_without_identity) != recorded_identity:
        raise SumtallyRelativeErrorRecoveryUnavailable(
            "recovery receipt canonical identity is invalid"
        )
    plan_sha256 = receipt_without_identity.pop("recovery_plan_sha256", None)
    if not isinstance(plan_sha256, str) or not re.fullmatch(r"[0-9a-f]{64}", plan_sha256):
        raise SumtallyRelativeErrorRecoveryUnavailable(
            "recovery receipt plan identity is invalid"
        )
    confirmed_plan = receipt_without_identity.pop("confirmed_plan", None)
    if not isinstance(confirmed_plan, dict):
        raise SumtallyRelativeErrorRecoveryUnavailable(
            "recovery receipt confirmed plan is missing"
        )
    if _canonical_sha256(confirmed_plan) != plan_sha256:
        raise SumtallyRelativeErrorRecoveryUnavailable(
            "recovery receipt confirmed plan identity is invalid"
        )
    expected = _receipt_core(root, context, pair)
    if receipt_without_identity != expected:
        raise SumtallyRelativeErrorRecoveryUnavailable(
            "recovery receipt is stale or does not match current Sumtally evidence"
        )
    destination_state = confirmed_plan.get("destination_state")
    if destination_state not in {
        "missing_error_and_receipt",
        "identical_existing_error_without_receipt",
    }:
        raise SumtallyRelativeErrorRecoveryUnavailable(
            "recovery receipt confirmed plan has an invalid destination state"
        )
    staging_value = confirmed_plan.get("staging_directory")
    if not isinstance(staging_value, str) or not staging_value:
        raise SumtallyRelativeErrorRecoveryUnavailable(
            "recovery receipt confirmed plan has no retained staging directory"
        )
    staging = _workspace_path(root, staging_value, guard=guard)
    current_plan = _build_preview(
        root,
        staging,
        guard=guard,
        permit_existing_receipt=True,
    )["plan"]
    current_plan["destination_state"] = destination_state
    if current_plan != confirmed_plan:
        raise SumtallyRelativeErrorRecoveryUnavailable(
            "recovery receipt confirmed plan does not match retained staging evidence"
        )


def resolved_combined_relative_error_evidence(
    workspace_root: Path,
) -> tuple[dict[str, Any], str]:
    """Return Structure-only pair evidence authorized by the fixed receipt."""

    from dicomxphits.structure_relative_error import validate_combined_tally_pair

    root = _absolute(workspace_root)
    receipt_path = root / RECEIPT_RELATIVE_PATH
    with WorkspaceOutputGuard(root, read_only=True) as guard:
        context = _current_context(root, guard=guard)
        receipt, receipt_sha256 = _stable_json(
            receipt_path,
            guard=guard,
            label="Sumtally relative-error recovery receipt",
        )
        try:
            pair = validate_combined_tally_pair(
                dose_path=context["dose"],
                error_path=context["error"],
                sum_input_path=context["sum_input"],
                expected_geometry=context["binding"]["tally_geometry_binding"][
                    "mesh_geometry"
                ],
            )
        except Exception as exc:
            raise SumtallyRelativeErrorRecoveryUnavailable(
                f"current official combined dose/error pair is invalid: {exc}"
            ) from exc
        if pair["dose_sha256"] != context["binding"]["sumtally_output_sha256"]:
            raise SumtallyRelativeErrorRecoveryUnavailable(
                "official combined dose does not match terminal Sumtally evidence"
            )
        _validate_receipt_object(root, receipt, context, pair, guard=guard)
        return pair, receipt_sha256


def _build_preview(
    root: Path,
    staging: Path,
    *,
    guard: WorkspaceOutputGuard,
    permit_existing_receipt: bool = False,
) -> dict[str, Any]:
    from dicomxphits.structure_relative_error import validate_combined_tally_pair

    if not _same_path(staging.parent, root) or not STAGING_NAME.fullmatch(staging.name):
        raise SumtallyRelativeErrorRecoveryUnavailable(
            "the selected staging directory must be one .sumtally-run-<16 hex> directory directly below the workspace"
        )
    guard.prepare(staging / ".recovery-boundary")
    if not staging.is_dir():
        raise SumtallyRelativeErrorRecoveryUnavailable(
            "the selected retained staging path is not an ordinary directory"
        )
    receipt_path = root / RECEIPT_RELATIVE_PATH
    guard.prepare(receipt_path)
    if os.path.lexists(receipt_path) and not permit_existing_receipt:
        try:
            resolved_combined_relative_error_evidence(root)
        except Exception as exc:
            raise SumtallyRelativeErrorRecoveryUnavailable(
                f"an existing recovery receipt is invalid or conflicting: {exc}"
            ) from exc
        raise SumtallyRelativeErrorRecoveryUnavailable(
            "recovery is already complete and the current receipt is valid"
        )

    context = _current_context(root, guard=guard)
    sum_input = context["sum_input"]
    staged_sum_input = staging / sum_input.name
    guard.prepare(staged_sum_input)
    includes = transitive_phits_include_paths(
        sum_input,
        execution_cwd=sum_input.parent,
    )
    recorded_include_paths = {
        os.path.normcase(
            os.fspath(
                _workspace_path(root, record["path"], guard=guard)
            )
        )
        for record in _relative_digest_records(
            root, context["generation"]["wrapper_include_evidence"]
        )
    }
    current_include_paths = {
        os.path.normcase(os.fspath(_absolute(path))) for path in includes
    }
    if current_include_paths != recorded_include_paths:
        raise SumtallyRelativeErrorRecoveryUnavailable(
            "current generated Sumtally include set differs from recorded evidence"
        )
    staged_inputs: list[dict[str, str]] = []
    for current in [sum_input, *includes]:
        try:
            relative = current.relative_to(sum_input.parent)
        except ValueError as exc:
            raise SumtallyRelativeErrorRecoveryUnavailable(
                "a generated Sumtally include is outside its execution directory"
            ) from exc
        retained = staging / relative
        _current_raw, current_sha256 = _stable_bytes(
            current,
            guard=guard,
            label="current generated Sumtally input",
        )
        _retained_raw, retained_sha256 = _stable_bytes(
            retained,
            guard=guard,
            label="retained generated Sumtally input",
        )
        if retained_sha256 != current_sha256:
            raise SumtallyRelativeErrorRecoveryUnavailable(
                "retained generated Sumtally input differs from current evidence"
            )
        staged_inputs.append(
            {
                "current_path": _relative(root, current),
                "retained_path": _relative(root, retained),
                "sha256": current_sha256,
            }
        )
    if staged_inputs[0]["sha256"] != context["binding"]["sum_input_sha256"]:
        raise SumtallyRelativeErrorRecoveryUnavailable(
            "generated wrapper digest does not match Sumtally evidence"
        )

    try:
        output_relative = context["dose"].relative_to(sum_input.parent)
    except ValueError as exc:
        raise SumtallyRelativeErrorRecoveryUnavailable(
            "official Sumtally dose is outside its recorded execution directory"
        ) from exc
    retained_dose = staging / output_relative
    retained_error = phits_error_output_path(retained_dose)
    guard.prepare(retained_error)
    _dose_raw, retained_dose_sha256 = _stable_bytes(
        retained_dose,
        guard=guard,
        label="retained combined Sumtally dose",
        maximum_bytes=MAX_TALLY_BYTES,
    )
    _official_raw, official_dose_sha256 = _stable_bytes(
        context["dose"],
        guard=guard,
        label="official combined Sumtally dose",
        maximum_bytes=MAX_TALLY_BYTES,
    )
    if retained_dose_sha256 != official_dose_sha256 or official_dose_sha256 != context[
        "binding"
    ]["sumtally_output_sha256"]:
        raise SumtallyRelativeErrorRecoveryUnavailable(
            "retained and official combined dose evidence is not byte-identical"
        )
    try:
        retained_pair = validate_combined_tally_pair(
            dose_path=retained_dose,
            error_path=retained_error,
            sum_input_path=staged_sum_input,
            expected_geometry=context["binding"]["tally_geometry_binding"][
                "mesh_geometry"
            ],
        )
    except Exception as exc:
        raise SumtallyRelativeErrorRecoveryUnavailable(
            f"retained combined dose/error pair is invalid: {exc}"
        ) from exc

    if os.path.lexists(context["error"]):
        _error_raw, official_error_sha256 = _stable_bytes(
            context["error"],
            guard=guard,
            label="existing official combined Sumtally error",
            maximum_bytes=MAX_TALLY_BYTES,
        )
        if official_error_sha256 != retained_pair["error_sha256"]:
            raise SumtallyRelativeErrorRecoveryUnavailable(
                "existing official combined Sumtally error conflicts with retained evidence"
            )
        try:
            existing_pair = validate_combined_tally_pair(
                dose_path=context["dose"],
                error_path=context["error"],
                sum_input_path=sum_input,
                expected_geometry=context["binding"]["tally_geometry_binding"][
                    "mesh_geometry"
                ],
            )
        except Exception as exc:
            raise SumtallyRelativeErrorRecoveryUnavailable(
                f"existing official combined dose/error pair is invalid: {exc}"
            ) from exc
        if _pair_receipt_fields(existing_pair) != _pair_receipt_fields(retained_pair):
            raise SumtallyRelativeErrorRecoveryUnavailable(
                "existing official combined error does not match the retained pair contract"
            )
        destination_state = "identical_existing_error_without_receipt"
    else:
        destination_state = "missing_error_and_receipt"

    official_pair = {
        **retained_pair,
        "dose_path": str(context["dose"]),
        "error_path": str(context["error"]),
    }
    receipt_core = _receipt_core(root, context, official_pair)
    plan = {
        "schema_version": PLAN_SCHEMA_VERSION,
        "contract_version": RECOVERY_CONTRACT_VERSION,
        "workspace": ".",
        "staging_directory": _relative(root, staging),
        "destination_state": destination_state,
        "receipt_path": RECEIPT_RELATIVE_PATH.as_posix(),
        "retained_inputs": staged_inputs,
        "retained_pair": {
            "dose_path": _relative(root, retained_dose),
            "error_path": _relative(root, retained_error),
            **_pair_receipt_fields(retained_pair),
        },
        "intended_receipt": receipt_core,
    }
    return {
        "status": "eligible",
        "recovery_plan_sha256": _canonical_sha256(plan),
        "plan": plan,
    }


def preview_sumtally_relative_error_recovery(
    workspace_root: Path,
    staging_directory: Path,
) -> dict[str, Any]:
    """Validate one explicit retained staging directory without writing."""

    root = _absolute(workspace_root)
    staging = _absolute(staging_directory)
    with WorkspaceOutputGuard(root, read_only=True) as guard:
        return _build_preview(root, staging, guard=guard)


def apply_sumtally_relative_error_recovery(
    workspace_root: Path,
    staging_directory: Path,
    expected_plan_sha256: str,
) -> dict[str, Any]:
    """Publish the exact confirmed error and Structure-only receipt new-only."""

    root = _absolute(workspace_root)
    staging = _absolute(staging_directory)
    if not re.fullmatch(r"[0-9a-f]{64}", expected_plan_sha256):
        raise SumtallyRelativeErrorRecoveryUnavailable(
            "expected recovery plan identity must be one lowercase SHA-256 digest"
        )
    with WorkspaceOutputGuard(root) as guard:
        preview = _build_preview(root, staging, guard=guard)
        if preview["recovery_plan_sha256"] != expected_plan_sha256:
            raise SumtallyRelativeErrorRecoveryUnavailable(
                "recovery plan changed after preview; obtain and confirm a new preview"
            )
        plan = preview["plan"]
        retained_error = root / plan["retained_pair"]["error_path"]
        official_error = root / plan["intended_receipt"]["official_pair"]["error_path"]
        receipt_path = root / RECEIPT_RELATIVE_PATH
        if plan["destination_state"] == "missing_error_and_receipt":
            _publish_file_new_only(
                guard,
                retained_error,
                official_error,
                expected_sha256=plan["retained_pair"]["error_sha256"],
            )
        if file_sha256(official_error) != plan["retained_pair"]["error_sha256"]:
            raise SumtallyRelativeErrorRecoveryUnavailable(
                "published official error does not match the confirmed retained evidence"
            )
        post_publication = _build_preview(root, staging, guard=guard)["plan"]
        for field in (
            "schema_version",
            "contract_version",
            "workspace",
            "staging_directory",
            "receipt_path",
            "retained_inputs",
            "retained_pair",
            "intended_receipt",
        ):
            if post_publication[field] != plan[field]:
                raise SumtallyRelativeErrorRecoveryUnavailable(
                    "recovery evidence changed after error publication; receipt was not published"
                )
        if post_publication["destination_state"] != (
            "identical_existing_error_without_receipt"
        ):
            raise SumtallyRelativeErrorRecoveryUnavailable(
                "recovery destination state changed after error publication"
            )
        receipt = {
            **plan["intended_receipt"],
            "recovery_plan_sha256": expected_plan_sha256,
            "confirmed_plan": plan,
        }
        receipt["receipt_sha256"] = _canonical_sha256(receipt)
        _publish_json_new_only(guard, receipt_path, receipt)
    pair, receipt_file_sha256 = resolved_combined_relative_error_evidence(root)
    return {
        "status": "recovered",
        "recovery_plan_sha256": expected_plan_sha256,
        "receipt_path": RECEIPT_RELATIVE_PATH.as_posix(),
        "receipt_file_sha256": receipt_file_sha256,
        "pair_evidence": pair,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Preview or apply bounded recovery of retained Sumtally statistical-error evidence."
        )
    )
    parser.add_argument("--workspace-root", type=Path, required=True)
    parser.add_argument("--staging-directory", type=Path, required=True)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--expected-plan-sha256")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.apply != bool(args.expected_plan_sha256):
        raise SystemExit(
            "--apply and --expected-plan-sha256 must be supplied together"
        )
    try:
        if args.apply:
            result = apply_sumtally_relative_error_recovery(
                args.workspace_root,
                args.staging_directory,
                args.expected_plan_sha256,
            )
        else:
            result = preview_sumtally_relative_error_recovery(
                args.workspace_root,
                args.staging_directory,
            )
    except (OSError, ValueError) as exc:
        print(f"Recovery unavailable: {exc}")
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
