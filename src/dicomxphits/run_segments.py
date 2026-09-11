from __future__ import annotations

import argparse
import json
import math
import os
import re
import subprocess
import sys
import time
import uuid
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping

from dicomxphits.prepare_3dcrt_workspace import (
    ExternalToolPaths,
    load_paths_config,
    merged_tool_paths,
    write_json,
)
from dicomxphits.gantry_geometry import (
    require_reusable_gantry_geometry_contract,
)
from dicomxphits.phits_geometry_diagnostics import (
    PhitsGeometryDiagnosticsError,
    invalid_phits_geometry_diagnostics,
    parse_phits_geometry_diagnostics_file,
)
from dicomxphits.safe_output import UnsafeWorkspacePathError, WorkspaceOutputGuard
from dicomxphits.sumtally_inputs import file_sha256, manifest_sha256


SUMMARY_RELATIVE_PATH = Path("analysis") / "segment_execution_summary.json"
SEGMENT_EXECUTION_SCHEMA_V2 = "dicomxphits_public_segment_execution_v2"
SEGMENT_EXECUTION_SCHEMA_V3 = "dicomxphits_public_segment_execution_v3"
SEGMENT_EXECUTION_SCHEMA_V4 = "dicomxphits_public_segment_execution_v4"
SEGMENT_EXECUTION_SCHEMA_V5 = "dicomxphits_public_segment_execution_v5"
SEGMENT_EXECUTION_SCHEMAS = frozenset(
    {SEGMENT_EXECUTION_SCHEMA_V2, SEGMENT_EXECUTION_SCHEMA_V3, SEGMENT_EXECUTION_SCHEMA_V4, SEGMENT_EXECUTION_SCHEMA_V5}
)
SEGMENT_PROGRESS_STATUSES = frozenset(
    {"pending", "running", "success", "failed", "gate_failed", "skipped"}
)
EXECUTION_PROGRESS_STATUSES = frozenset(
    {"running", "success", "failed", "gate_failed"}
)
ROOT_BATCH_OUT = "batch.out"
ROOT_PHITS_OUT = "phits.out"
OMP_DIRECTIVE_PATTERN = re.compile(r"^\s*\$OMP\s*=\s*(\d+)\s*$", re.IGNORECASE)
PHITS_INCLUDE_PATTERN = re.compile(r"^\s*infl:\s*\{\s*([^}]+?)\s*\}", re.IGNORECASE)
PHITS_OUTPUT_PATTERN = re.compile(
    r"^\s*(?:file|sfile)\s*=\s*([^\s#$]+)", re.IGNORECASE
)


def load_json_object(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return data


def load_manifest(workspace_root: Path) -> tuple[dict[str, Any], Path]:
    manifest_path = workspace_root / "segments" / "segment_manifest.json"
    if not manifest_path.is_file():
        raise FileNotFoundError(f"segment manifest not found: {manifest_path}")
    return load_json_object(manifest_path), manifest_path


def finite_positive(value: Any) -> bool:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return False
    return math.isfinite(number) and number > 0.0


def segment_mu_active(segment: dict[str, Any]) -> bool:
    for key in ("segment_mu", "mu_weight", "beam_meterset_mu"):
        if key in segment:
            return finite_positive(segment.get(key))
    return False


def segment_active_state(segment: dict[str, Any]) -> tuple[bool, str | None]:
    if segment.get("skip_reason"):
        return False, str(segment.get("skip_reason"))
    if bool(segment.get("skip")) or bool(segment.get("skipped")):
        return False, "skip flag set"
    if "active" in segment:
        return bool(segment.get("active")), None if bool(segment.get("active")) else "active flag false"
    if segment_mu_active(segment):
        return True, None
    return False, "zero or missing MU"


def resolve_workspace_file(workspace_root: Path, value: str, *, label: str) -> Path:
    if not value:
        raise ValueError(f"{label} is required")
    path = Path(value)
    candidate = path if path.is_absolute() else workspace_root / path
    absolute = Path(os.path.abspath(os.fspath(candidate)))
    resolved = absolute.resolve()
    workspace_resolved = workspace_root.resolve()
    try:
        resolved.relative_to(workspace_resolved)
    except ValueError as exc:
        raise ValueError(f"{label} must resolve inside workspace root: {value}") from exc
    return absolute


def require_execution_paths(paths: ExternalToolPaths) -> None:
    if not paths.phits_executable_path:
        raise ValueError("Missing required external tool path setting: phits_executable_path")


def summary_path(workspace_root: Path) -> Path:
    return workspace_root / SUMMARY_RELATIVE_PATH


def _utc_text(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("UTC clock must return a timezone-aware datetime")
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _default_utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _default_run_id() -> str:
    return uuid.uuid4().hex


def _nonnegative_duration(value: float) -> float:
    return max(0.0, float(value))


def _is_nonnegative_number(value: object) -> bool:
    return (
        not isinstance(value, bool)
        and isinstance(value, (int, float))
        and math.isfinite(float(value))
        and float(value) >= 0.0
    )


def _is_nonnegative_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _parse_utc_text(value: object, *, field_name: str) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ValueError(f"{field_name} must be an ISO-8601 UTC timestamp")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise ValueError(f"{field_name} must be an ISO-8601 UTC timestamp") from exc
    if parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        raise ValueError(f"{field_name} must be an ISO-8601 UTC timestamp")
    return parsed


def blank_segment_summary(
    segment: dict[str, Any],
    *,
    status: str,
    manifest_ordinal: int,
    active_ordinal: int | None,
    reason: str | None = None,
) -> dict[str, Any]:
    return {
        "segment_id": str(segment.get("segment_id") or segment.get("segment_index") or "unknown"),
        "manifest_ordinal": manifest_ordinal,
        "active_ordinal": active_ordinal,
        "phits_input_path": str(segment.get("phits_input_path") or ""),
        "expected_output_path": str(segment.get("expected_output_path") or ""),
        "return_code": None,
        "stdout_log_path": None,
        "stderr_log_path": None,
        "geometry_diagnostics": None,
        "status": status,
        "reason": reason,
        "started_at": None,
        "finished_at": None,
        "started_elapsed_seconds": None,
        "duration_seconds": None,
    }


def validate_segment_execution_summary(
    summary: Mapping[str, Any],
    *,
    require_success: bool,
) -> str:
    schema = summary.get("schema_version")
    if schema not in SEGMENT_EXECUTION_SCHEMAS:
        raise ValueError("Unsupported PHITS segment execution summary schema")
    if not isinstance(summary.get("segments"), list):
        raise ValueError("PHITS segment execution summary is missing segments")
    if schema == SEGMENT_EXECUTION_SCHEMA_V2:
        v2_success = any(
            summary.get(field) == "success" for field in ("stage_status", "status")
        )
        if require_success and not v2_success:
            raise ValueError("PHITS segment execution summary is not successful")
        return schema
    if summary.get("stage") != "run_segments":
        raise ValueError("PHITS segment execution summary has the wrong stage")
    status = summary.get("stage_status")
    allowed = EXECUTION_PROGRESS_STATUSES | ({"stopped"} if schema == SEGMENT_EXECUTION_SCHEMA_V5 else set())
    if status != summary.get("status") or status not in allowed:
        raise ValueError("PHITS segment execution summary has an invalid overall status")
    if require_success and status != "success":
        raise ValueError("PHITS segment execution summary is not successful")
    run_id = summary.get("run_id")
    if not isinstance(run_id, str) or not run_id.strip():
        raise ValueError("PHITS segment progress is missing its invocation identifier")
    _parse_utc_text(summary.get("started_at"), field_name="started_at")
    _parse_utc_text(summary.get("updated_at"), field_name="updated_at")
    if not _is_nonnegative_number(summary.get("elapsed_seconds")):
        raise ValueError("PHITS segment progress has an invalid elapsed duration")
    if not isinstance(summary.get("workspace_root"), str) or not summary.get("workspace_root"):
        raise ValueError("PHITS segment progress is missing its workspace root")
    manifest_digest = summary.get("manifest_sha256")
    if manifest_digest is not None and (
        not isinstance(manifest_digest, str)
        or re.fullmatch(r"[0-9a-f]{64}", manifest_digest) is None
    ):
        raise ValueError("PHITS segment progress has an invalid manifest digest")
    if status in {"running", "success", "failed", "stopped"} and manifest_digest is None:
        raise ValueError("PHITS segment progress is missing its manifest digest")

    segments = summary["segments"]
    count_fields = (
        "segment_count",
        "active_segment_count",
        "completed_active_segment_count",
        "remaining_active_segment_count",
        "succeeded",
        "failed",
        "skipped",
    )
    if any(not _is_nonnegative_int(summary.get(field)) for field in count_fields):
        raise ValueError("PHITS segment progress has invalid segment counts")
    if summary.get("segment_count") != len(segments):
        raise ValueError("PHITS segment progress segment count does not match its entries")

    observed_statuses: list[str] = []
    running_items: list[Mapping[str, Any]] = []
    active_ordinals: list[int] = []
    for position, item in enumerate(segments, start=1):
        if not isinstance(item, Mapping):
            raise ValueError("PHITS segment progress contains a non-object segment")
        item_status = item.get("status")
        if item_status not in SEGMENT_PROGRESS_STATUSES:
            raise ValueError("PHITS segment progress contains an invalid segment status")
        observed_statuses.append(str(item_status))
        if item.get("manifest_ordinal") != position:
            raise ValueError("PHITS segment progress has an invalid manifest ordinal")
        active_ordinal = item.get("active_ordinal")
        if item_status == "skipped":
            if active_ordinal is not None:
                raise ValueError("Skipped PHITS segment has an active ordinal")
        else:
            if not isinstance(active_ordinal, int) or isinstance(active_ordinal, bool):
                raise ValueError("Active PHITS segment is missing its active ordinal")
            active_ordinals.append(active_ordinal)
        if item_status == "running":
            running_items.append(item)
        has_started = item.get("started_at") is not None
        if item_status in {"running", "success", "failed"} or has_started:
            _parse_utc_text(item.get("started_at"), field_name="segment started_at")
            if not _is_nonnegative_number(item.get("started_elapsed_seconds")):
                raise ValueError("PHITS segment has an invalid start duration")
        has_terminal_timing = item_status in {"success", "failed"} or (
            item_status == "gate_failed" and has_started
        )
        if has_terminal_timing:
            _parse_utc_text(item.get("finished_at"), field_name="segment finished_at")
            if not _is_nonnegative_number(item.get("duration_seconds")):
                raise ValueError("PHITS segment has an invalid duration")
        elif item.get("finished_at") is not None or item.get("duration_seconds") is not None:
            raise ValueError("Incomplete PHITS segment contains terminal timing")
        if item_status in {"pending", "running"} and (
            item.get("return_code") is not None
            or item.get("geometry_diagnostics") is not None
            or item.get("expected_output_sha256") is not None
            or item.get("phits_out_sha256") is not None
        ):
            raise ValueError("Incomplete PHITS segment contains result evidence")
        if item_status == "success":
            if item.get("return_code") != 0:
                raise ValueError(
                    "Successful PHITS segment does not have a zero return code"
                )
            if any(
                not isinstance(item.get(field), str)
                or re.fullmatch(r"[0-9a-f]{64}", str(item.get(field))) is None
                for field in ("expected_output_sha256", "phits_out_sha256")
            ):
                raise ValueError("Successful PHITS segment is missing output digests")
            diagnostics = item.get("geometry_diagnostics")
            if not isinstance(diagnostics, Mapping) or diagnostics.get("status") != "clean":
                raise ValueError("Successful PHITS segment is missing clean geometry evidence")

    active_count = len([value for value in observed_statuses if value != "skipped"])
    succeeded = observed_statuses.count("success")
    failed = observed_statuses.count("failed") + observed_statuses.count("gate_failed")
    skipped = observed_statuses.count("skipped")
    remaining = observed_statuses.count("pending") + observed_statuses.count("running")
    if active_ordinals != list(range(1, active_count + 1)):
        raise ValueError("PHITS segment progress active ordinals are not contiguous")
    expected_counts = {
        "active_segment_count": active_count,
        "completed_active_segment_count": succeeded,
        "remaining_active_segment_count": remaining,
        "succeeded": succeeded,
        "failed": failed,
        "skipped": skipped,
    }
    if any(summary.get(key) != value for key, value in expected_counts.items()):
        raise ValueError("PHITS segment progress counts do not match its entries")
    current = summary.get("current_segment")
    if len(running_items) > 1:
        raise ValueError("PHITS segment progress contains multiple running segments")
    if running_items:
        running = running_items[0]
        if not isinstance(current, Mapping) or any(
            current.get(key) != running.get(key)
            for key in ("segment_id", "manifest_ordinal", "active_ordinal")
        ):
            raise ValueError("PHITS segment progress current segment is inconsistent")
    elif current is not None:
        raise ValueError("PHITS segment progress names a segment that is not running")
    if status != "running" and running_items:
        raise ValueError("Terminal PHITS segment progress contains a running segment")
    if status == "success" and any(
        value not in {"success", "skipped"} for value in observed_statuses
    ):
        raise ValueError("Successful PHITS progress contains incomplete segments")
    if schema in {SEGMENT_EXECUTION_SCHEMA_V4, SEGMENT_EXECUTION_SCHEMA_V5}:
        from dicomxphits.segment_retry import validate_v4
        validate_v4(summary)
    if schema == SEGMENT_EXECUTION_SCHEMA_V5:
        from dicomxphits.segment_stop import validate_stop_evidence
        validate_stop_evidence(summary)
    return schema


def collect_root_outputs(
    workspace_root: Path,
    execution_root: Path,
    output_dir: Path,
    *,
    guard: WorkspaceOutputGuard,
) -> dict[str, str | None]:
    guard.mkdir(output_dir)
    collected: dict[str, str | None] = {"batch_out_path": None, "phits_out_path": None}
    batch_source = execution_root / ROOT_BATCH_OUT
    if os.path.lexists(batch_source):
        guard.prepare(batch_source)
        if not batch_source.is_file():
            raise UnsafeWorkspacePathError(
                f"PHITS root output is not a regular file: {batch_source}"
            )
        batch_target = output_dir / ROOT_BATCH_OUT
        guard.copy_file(batch_source, batch_target)
        collected["batch_out_path"] = str(batch_target)
    phits_source = execution_root / ROOT_PHITS_OUT
    if os.path.lexists(phits_source):
        guard.prepare(phits_source)
        if not phits_source.is_file():
            raise UnsafeWorkspacePathError(
                f"PHITS root output is not a regular file: {phits_source}"
            )
        phits_target = output_dir / ROOT_PHITS_OUT
        guard.prepare(phits_target)
        guard.copy_file(phits_source, phits_target)
        collected["phits_out_path"] = str(phits_target)
    return collected


def remove_stale_root_outputs(
    workspace_root: Path, *, guard: WorkspaceOutputGuard
) -> None:
    for name in (ROOT_BATCH_OUT, ROOT_PHITS_OUT):
        path = workspace_root / name
        if os.path.lexists(path):
            guard.unlink(path)


def remove_stale_expected_output(
    expected_output: Path, *, guard: WorkspaceOutputGuard
) -> None:
    if os.path.lexists(expected_output):
        if not expected_output.is_file():
            raise ValueError(f"expected_output_path exists but is not a file: {expected_output}")
        guard.unlink(expected_output)


def phits_launcher_input(
    *,
    workspace_root: Path,
    phits_input: Path,
) -> str:
    relative = phits_input.resolve().relative_to(workspace_root.resolve()).as_posix()
    if any(character in relative for character in ("\r", "\n", "\"", "'")):
        raise ValueError("phits_input_path contains unsupported launcher characters")
    return f"file = {relative}\n"


def phits_environment(phits_input: Path) -> dict[str, str]:
    environment = os.environ.copy()
    with phits_input.open("r", encoding="utf-8", errors="replace") as stream:
        for line in stream:
            stripped = line.strip()
            if stripped.startswith("["):
                break
            match = OMP_DIRECTIVE_PATTERN.match(stripped)
            if match is None:
                continue
            threads = int(match.group(1))
            if threads <= 0:
                raise ValueError("$OMP thread count must be a positive integer")
            environment["OMP_NUM_THREADS"] = str(threads)
            return environment
    raise ValueError("PHITS input is missing a valid positive $OMP directive")


def phits_staging_contract(
    *,
    workspace_root: Path,
    phits_input: Path,
    guard: WorkspaceOutputGuard,
) -> tuple[list[Path], list[Path]]:
    """Return workspace-local input dependencies and declared output paths."""

    root = Path(os.path.abspath(os.fspath(workspace_root)))
    root_resolved = root.resolve()
    pending = [phits_input]
    inputs: list[Path] = []
    outputs: list[Path] = []
    seen_inputs: set[Path] = set()
    seen_outputs: set[Path] = set()
    while pending:
        source = pending.pop()
        source_resolved = source.resolve()
        if source_resolved in seen_inputs:
            continue
        try:
            source_resolved.relative_to(root_resolved)
        except ValueError as exc:
            raise ValueError(
                f"PHITS input dependency must resolve inside workspace root: {source}"
            ) from exc
        guard.prepare(source)
        if not source.is_file():
            raise FileNotFoundError(f"PHITS input dependency not found: {source}")
        seen_inputs.add(source_resolved)
        inputs.append(source)
        with source.open("r", encoding="utf-8", errors="replace") as stream:
            for line in stream:
                include_match = PHITS_INCLUDE_PATTERN.match(line)
                if include_match is not None:
                    value = os.path.expandvars(os.path.expanduser(include_match.group(1)))
                    dependency = resolve_workspace_file(
                        root,
                        value,
                        label="PHITS input dependency",
                    )
                    pending.append(dependency)
                output_match = PHITS_OUTPUT_PATTERN.match(line)
                if output_match is not None:
                    output = resolve_workspace_file(
                        root,
                        output_match.group(1),
                        label="PHITS declared output",
                    )
                    if output not in seen_outputs:
                        seen_outputs.add(output)
                        outputs.append(output)
    return inputs, outputs


def persistent_segment_outputs(
    *,
    expected_output: Path,
    declared_outputs: list[Path],
) -> list[Path]:
    if expected_output.resolve() not in {path.resolve() for path in declared_outputs}:
        raise ValueError(
            "expected_output_path is not declared by the selected PHITS input"
        )
    output_dir = expected_output.parent
    return [
        *declared_outputs,
        *(phits_error_output_path(output) for output in declared_outputs),
        output_dir / "phits_stdout.txt",
        output_dir / "phits_stderr.txt",
        output_dir / ROOT_BATCH_OUT,
        output_dir / ROOT_PHITS_OUT,
    ]


def phits_error_output_path(output: Path) -> Path:
    """Return the PHITS statistical-error companion for a tally output."""

    return output.with_name(f"{output.stem}_err{output.suffix}")


def stage_phits_segment_run(
    *,
    workspace_root: Path,
    phits_input: Path,
    expected_output: Path,
    guard: WorkspaceOutputGuard,
) -> tuple[Path, Path, list[Path]]:
    inputs, outputs = phits_staging_contract(
        workspace_root=workspace_root,
        phits_input=phits_input,
        guard=guard,
    )
    persistent_segment_outputs(
        expected_output=expected_output,
        declared_outputs=outputs,
    )
    execution_root = guard.make_staging_directory(
        workspace_root / "analysis",
        prefix=".phits-segment-run-",
    )
    for source in inputs:
        relative = source.resolve().relative_to(workspace_root.resolve())
        guard.copy_file(source, execution_root / relative, overwrite=False)
    for output in outputs:
        relative = output.resolve().relative_to(workspace_root.resolve())
        guard.mkdir((execution_root / relative).parent)
    staged_input = execution_root / phits_input.resolve().relative_to(
        workspace_root.resolve()
    )
    return execution_root, staged_input, outputs


def run_one_segment(
    *,
    workspace_root: Path,
    segment: dict[str, Any],
    phits_executable_path: str,
    runner=subprocess.run,
    input_binding: list[dict[str, str]] | None = None,
    observation_context=None,
) -> dict[str, Any]:
    phits_input = resolve_workspace_file(
        workspace_root,
        str(segment.get("phits_input_path") or ""),
        label="phits_input_path",
    )
    expected_output = resolve_workspace_file(
        workspace_root,
        str(segment.get("expected_output_path") or ""),
        label="expected_output_path",
    )
    output_dir = expected_output.parent
    stdout_path = output_dir / "phits_stdout.txt"
    stderr_path = output_dir / "phits_stderr.txt"

    with WorkspaceOutputGuard(workspace_root) as guard:
        guard.prepare(phits_input)
        if not phits_input.is_file():
            raise FileNotFoundError(f"PHITS input file not found: {phits_input}")
        environment = phits_environment(phits_input)
        guard.mkdir(output_dir)
        guard.prepare(expected_output)
        remove_stale_expected_output(expected_output, guard=guard)
        remove_stale_root_outputs(workspace_root, guard=guard)
        execution_root, staged_input, declared_outputs = stage_phits_segment_run(
            workspace_root=workspace_root,
            phits_input=phits_input,
            expected_output=expected_output,
            guard=guard,
        )
        try:
            if input_binding is not None:
                for evidence in input_binding:
                    if file_sha256(execution_root / evidence["path"]) != evidence["sha256"]:
                        raise ValueError("Staged input changed after execution preflight")
            error_outputs = [
                phits_error_output_path(output) for output in declared_outputs
            ]
            persistent_outputs = persistent_segment_outputs(
                expected_output=expected_output,
                declared_outputs=declared_outputs,
            )
            for output in persistent_outputs:
                guard.prepare_file_target(output, create_parents=True)
            for output in error_outputs:
                if os.path.lexists(output):
                    guard.unlink(output)
            from dicomxphits.phits_observation import make_observer
            staged_dose = execution_root / expected_output.resolve().relative_to(workspace_root.resolve())
            observer = make_observer(workspace_root, execution_root, staged_input, staged_dose, observation_context)
            def observing_runner(*args, **kwargs):
                if observer is None:
                    return runner(*args, **kwargs)
                try:
                    observer.start()
                except Exception:
                    observer.close(guard)
                    return runner(*args, **kwargs)
                try:
                    return runner(*args, stdout_observer=observer.feed_stdout,
                        _observation_poll=lambda: observer.publish(guard), **kwargs)
                finally:
                    observer.close(guard)
            result = observing_runner(
                [phits_executable_path],
                input=phits_launcher_input(
                    workspace_root=execution_root,
                    phits_input=staged_input,
                ),
                cwd=execution_root,
                capture_output=True,
                text=True,
                shell=False,
                env=environment,
            )
            staged_phits_out = execution_root / ROOT_PHITS_OUT
            try:
                geometry_diagnostics = parse_phits_geometry_diagnostics_file(
                    staged_phits_out
                )
            except PhitsGeometryDiagnosticsError as exc:
                geometry_diagnostics = invalid_phits_geometry_diagnostics(str(exc))
            geometry_clean = geometry_diagnostics.get("status") == "clean"
            staged_expected_output = (
                execution_root
                / expected_output.resolve().relative_to(workspace_root.resolve())
            )
            expected_error_output = phits_error_output_path(expected_output)
            staged_expected_error_output = (
                execution_root
                / expected_error_output.resolve().relative_to(
                    workspace_root.resolve()
                )
            )
            if (
                result.returncode == 0
                and staged_expected_output.is_file()
                and staged_expected_error_output.is_file()
                and geometry_clean
            ):
                non_expected_outputs = [
                    output
                    for output in declared_outputs
                    if output.resolve() != expected_output.resolve()
                ]
                for output in [
                    *error_outputs,
                    *non_expected_outputs,
                    expected_output,
                ]:
                    relative = output.resolve().relative_to(workspace_root.resolve())
                    staged_output = execution_root / relative
                    if not os.path.lexists(staged_output):
                        continue
                    guard.copy_file(
                        staged_output,
                        output,
                        overwrite=output.resolve() != expected_output.resolve(),
                    )
            guard.write_text(stdout_path, result.stdout or "")
            guard.write_text(stderr_path, result.stderr or "")
            collected = collect_root_outputs(
                workspace_root,
                execution_root,
                output_dir,
                guard=guard,
            )
            geometry_diagnostics["source_path"] = collected["phits_out_path"]
        finally:
            guard.rmtree(execution_root, missing_ok=True)

    output_exists = expected_output.is_file()
    status = (
        "success"
        if result.returncode == 0 and output_exists and geometry_clean
        else "failed"
    )
    reason = None
    if status == "failed":
        if result.returncode != 0:
            reason = f"PHITS returned nonzero exit code {result.returncode}"
        elif not geometry_clean:
            reason = str(
                geometry_diagnostics.get("reason")
                or "PHITS reported nonzero geometry diagnostics"
            )
        elif not output_exists:
            reason = "PHITS did not produce all required segment outputs"
    phits_out_path = (
        Path(collected["phits_out_path"])
        if collected["phits_out_path"] is not None
        else None
    )
    return {
        "segment_id": str(segment.get("segment_id") or segment.get("segment_index") or "unknown"),
        "phits_input_path": str(phits_input),
        "expected_output_path": str(expected_output),
        "return_code": result.returncode,
        "stdout_log_path": str(stdout_path),
        "stderr_log_path": str(stderr_path),
        "status": status,
        "reason": reason,
        "expected_output_exists": output_exists,
        "expected_output_sha256": (
            file_sha256(expected_output) if output_exists else None
        ),
        "geometry_diagnostics": geometry_diagnostics,
        "batch_out_path": collected["batch_out_path"],
        "phits_out_path": collected["phits_out_path"],
        "phits_out_sha256": (
            file_sha256(phits_out_path)
            if phits_out_path is not None and phits_out_path.is_file()
            else None
        ),
    }


def build_summary(
    *,
    workspace_root: Path,
    status: str,
    segments: list[dict[str, Any]],
    command_argv: list[str] | None,
    run_id: str,
    started_at: str,
    updated_at: str,
    elapsed_seconds: float,
    current_segment: dict[str, Any] | None,
    manifest_digest: str | None = None,
    failure_reason: str | None = None,
) -> dict[str, Any]:
    succeeded = sum(1 for segment in segments if segment.get("status") == "success")
    failed = sum(1 for segment in segments if segment.get("status") in {"failed", "gate_failed"})
    skipped = sum(1 for segment in segments if segment.get("status") == "skipped")
    active = len(segments) - skipped
    remaining = sum(
        1 for segment in segments if segment.get("status") in {"pending", "running"}
    )
    return {
        "schema_version": SEGMENT_EXECUTION_SCHEMA_V3,
        "stage": "run_segments",
        "run_id": run_id,
        "status": status,
        "stage_status": status,
        "workspace_root": str(workspace_root),
        "manifest_sha256": manifest_digest,
        "command": {"argv": command_argv or sys.argv},
        "started_at": started_at,
        "updated_at": updated_at,
        "elapsed_seconds": elapsed_seconds,
        "segment_count": len(segments),
        "active_segment_count": active,
        "completed_active_segment_count": succeeded,
        "remaining_active_segment_count": remaining,
        "current_segment": current_segment,
        "succeeded": succeeded,
        "failed": failed,
        "skipped": skipped,
        "segments": segments,
        "failure_reason": failure_reason,
    }


def run_segments(
    *,
    workspace_root: Path,
    paths: ExternalToolPaths,
    command_argv: list[str] | None = None,
    runner=subprocess.run,
    monotonic_clock: Callable[[], float] = time.monotonic,
    utc_now: Callable[[], datetime] = _default_utc_now,
    run_id_factory: Callable[[], str] = _default_run_id,
    summary_writer: Callable[[Path, dict[str, Any]], None] | None = None,
    run_incomplete: bool = False,
    expected_summary_sha256: str | None = None,
    stop_control=None,
    preflight_nonce: str | None = None,
) -> dict[str, Any]:
    from dicomxphits.segment_retry import plan_incomplete
    from dicomxphits.workspace_execution import WorkspaceExecutionLease

    root = workspace_root.expanduser().resolve()
    if preflight_nonce is not None:
        from dicomxphits.segment_preflight import Session, PreparationCancelled, read_receipt
        run_id = str(run_id_factory())
        # The outer lease spans preparation, cancellation and terminal receipt.
        with WorkspaceOutputGuard(root):
            read_receipt(root)  # Never overwrite malformed or unknown-version evidence.
            with Session(root, preflight_nonce, run_id, stop_control) as preparation:
                try:
                    preparation.checkpoint()
                    result = run_segments(workspace_root=root, paths=paths,
                        command_argv=command_argv, runner=runner,
                        monotonic_clock=monotonic_clock, utc_now=utc_now,
                        run_id_factory=lambda: run_id, summary_writer=summary_writer,
                        run_incomplete=run_incomplete,
                        expected_summary_sha256=expected_summary_sha256,
                        stop_control=stop_control)
                    preparation.finish(result)
                    return result
                except PreparationCancelled:
                    return dict(preparation.receipt)
                finally:
                    if stop_control is not None:
                        stop_control.close()
    # Rejected retry preflight must not replace the previous execution summary.
    if run_incomplete:
        with WorkspaceExecutionLease(root, create=False) as lease:
            plan = plan_incomplete(root, paths, expected_summary_sha256=expected_summary_sha256)
            if not plan["scheduled"]:
                if stop_control is not None:
                    stop_control.close()
                return plan["summary"]
            with lease.invocation():
                return _run_segments_locked(workspace_root=root, paths=paths,
                    command_argv=command_argv, runner=lease.run if runner is subprocess.run else runner,
                    monotonic_clock=monotonic_clock, utc_now=utc_now,
                    run_id_factory=run_id_factory, summary_writer=summary_writer, retry_plan=plan,
                    stop_control=stop_control)
    with WorkspaceOutputGuard(root):
        with WorkspaceExecutionLease(root) as lease:
            with lease.invocation():
                return _run_segments_locked(workspace_root=root, paths=paths,
                    command_argv=command_argv, runner=lease.run if runner is subprocess.run else runner,
                    monotonic_clock=monotonic_clock, utc_now=utc_now,
                    run_id_factory=run_id_factory, summary_writer=summary_writer, stop_control=stop_control)


def _run_segments_locked(
    *, workspace_root, paths, command_argv, runner, monotonic_clock, utc_now,
    run_id_factory, summary_writer, retry_plan=None, stop_control=None,
):
    from dicomxphits.segment_retry import capture_binding, result_evidence, validate_binding, validate_results
    workspace_root = workspace_root.expanduser().resolve()
    summary_file = summary_path(workspace_root)
    segment_summaries: list[dict[str, Any]] = []
    manifest_digest: str | None = None
    run_id = str(run_id_factory()).strip()
    if not run_id:
        raise ValueError("segment execution invocation identifier must not be empty")
    started_tick = float(monotonic_clock())
    started_at = _utc_text(utc_now())
    current_segment: dict[str, Any] | None = None
    execution_binding = None
    parent_attempt = None
    stop_requested = None
    # Only the owned direct runner understands the optional stdout prefix tap.
    observe_native = getattr(runner, "__self__", None) is not None and type(runner.__self__).__name__ == "WorkspaceExecutionLease"

    def persist(status: str, *, failure_reason: str | None = None) -> dict[str, Any]:
        summary = build_summary(
            workspace_root=workspace_root,
            status=status,
            segments=segment_summaries,
            command_argv=command_argv,
            run_id=run_id,
            started_at=started_at,
            updated_at=_utc_text(utc_now()),
            elapsed_seconds=_nonnegative_duration(monotonic_clock() - started_tick),
            current_segment=current_segment,
            manifest_digest=manifest_digest,
            failure_reason=failure_reason,
        )
        summary.update(schema_version=SEGMENT_EXECUTION_SCHEMA_V5,
            stop_control_enabled=stop_control is not None, stop_requested=deepcopy(stop_requested),
            execution_binding=execution_binding, parent_attempt=parent_attempt,
            retained_active_segment_count=sum(bool(s.get("retained")) for s in segment_summaries))
        validate_segment_execution_summary(summary, require_success=False)
        if summary_writer is None:
            write_json(summary_file, summary, case_root=workspace_root)
        else:
            summary_writer(summary_file, summary)
        return summary

    def poll_stop():
        nonlocal stop_requested
        if stop_control is None:
            return
        from dicomxphits.segment_stop import valid_request
        from dicomxphits.segment_preflight import current_session
        for request in stop_control.take():
            preparation = current_session()
            if preparation is not None and preparation.handle_cancel(request):
                continue
            if preparation is not None and not preparation.receipt["child_committed"]:
                stop_control.reject()
                continue
            if (not valid_request(request, workspace=str(workspace_root), run_id=run_id)
                or execution_binding is None or execution_binding["retry_unavailable"]):
                stop_control.reject()
                continue
            if stop_requested is not None:
                continue
            stop_requested = {key: request[key] for key in ("request_id", "workspace_root", "run_id")}
            stop_requested.update(acknowledged_at=_utc_text(utc_now()),
                acknowledged_elapsed_seconds=_nonnegative_duration(monotonic_clock() - started_tick),
                boundary_segment=deepcopy(current_segment))
            persist("running")

    def controlled_runner(*args, **kwargs):
        from dicomxphits.segment_stop import run_while_polling
        observation_poll = kwargs.pop("_observation_poll", None)
        def poll():
            poll_stop()
            if observation_poll is not None:
                observation_poll()
        return run_while_polling(runner, poll, *args, **kwargs)

    try:
        from dicomxphits.segment_preflight import current_session
        preparation = current_session()
        if preparation is not None:
            preparation.poll = poll_stop
        require_execution_paths(paths)
        manifest, _manifest_path = load_manifest(workspace_root)
        manifest_digest = manifest_sha256(manifest)
        require_reusable_gantry_geometry_contract(manifest)
        raw_segments = manifest.get("segments")
        if not isinstance(raw_segments, list):
            raise ValueError("segment manifest must contain a segments list")

        active_segments: list[tuple[int, dict[str, Any]]] = []
        active_ordinal = 0
        for manifest_index, item in enumerate(raw_segments):
            if not isinstance(item, dict):
                continue
            is_active, skip_reason = segment_active_state(item)
            if is_active:
                active_ordinal += 1
                active_segments.append((len(segment_summaries), item))
                segment_summaries.append(
                    blank_segment_summary(
                        item,
                        status="pending",
                        manifest_ordinal=manifest_index + 1,
                        active_ordinal=active_ordinal,
                    )
                )
            else:
                segment_summaries.append(
                    blank_segment_summary(
                        item,
                        status="skipped",
                        manifest_ordinal=manifest_index + 1,
                        active_ordinal=None,
                        reason=skip_reason,
                    )
                )

        for item in segment_summaries:
            item.update(retained=False, producer_run_id=None)
        if retry_plan is not None:
            if run_id == retry_plan["summary"]["run_id"]:
                raise ValueError("Retry must use a fresh invocation identifier")
            for index, old in enumerate(retry_plan["summary"]["segments"]):
                if old["status"] == "success":
                    segment_summaries[index] = {**deepcopy(old), "retained": True}
            active_segments = [(i, s) for i, s in active_segments if not segment_summaries[i]["retained"]]

        execution_binding = capture_binding(workspace_root, manifest, paths)
        if retry_plan is not None and execution_binding != retry_plan["summary"]["execution_binding"]:
            raise ValueError("Execution conditions changed after retry preview")
        contracts = {s["segment_id"]: s for s in execution_binding["segments"]}
        with WorkspaceOutputGuard(workspace_root) as guard:
            guard.prepare_file_target(summary_file, create_parents=True)
            for _summary_index, segment in active_segments:
                phits_input = resolve_workspace_file(
                    workspace_root,
                    str(segment.get("phits_input_path") or ""),
                    label="phits_input_path",
                )
                expected_output = resolve_workspace_file(
                    workspace_root,
                    str(segment.get("expected_output_path") or ""),
                    label="expected_output_path",
                )
                guard.prepare(phits_input)
                if not phits_input.is_file():
                    raise FileNotFoundError(
                        f"PHITS input file not found: {phits_input}"
                    )
                phits_environment(phits_input)
                _inputs, declared_outputs = phits_staging_contract(
                    workspace_root=workspace_root,
                    phits_input=phits_input,
                    guard=guard,
                )
                for output in persistent_segment_outputs(
                    expected_output=expected_output,
                    declared_outputs=declared_outputs,
                ):
                    guard.prepare_file_target(output, create_parents=True)

            if retry_plan is not None:
                guard.mkdir(workspace_root / "analysis" / "segment_attempt_history")
                history = guard.make_staging_directory(
                    workspace_root / "analysis" / "segment_attempt_history", prefix="attempt-")
                preserved = history / "summary.json"
                guard.copy_file(summary_file, preserved, overwrite=False)
                if file_sha256(preserved) != retry_plan["source_sha256"]:
                    raise ValueError("Retry source changed before preservation")
                parent_attempt = {"path": preserved.relative_to(workspace_root).as_posix(),
                    "sha256": retry_plan["source_sha256"]}

        if preparation is None:
            persist("running")
        for summary_index, segment in active_segments:
            if preparation is not None:
                preparation.publish("verifying", force=True)
            validate_binding(workspace_root, manifest, execution_binding, paths)
            validate_results(workspace_root, {"execution_binding": execution_binding,
                "segments": segment_summaries})
            poll_stop()
            if stop_requested is not None:
                break
            if preparation is not None:
                preparation.commit()
            segment_started_tick = float(monotonic_clock())
            segment_started_at = _utc_text(utc_now())
            prior = segment_summaries[summary_index]
            segment_summaries[summary_index] = {
                **prior,
                "status": "running",
                "producer_run_id": run_id,
                "reason": None,
                "started_at": segment_started_at,
                "started_elapsed_seconds": _nonnegative_duration(
                    segment_started_tick - started_tick
                ),
            }
            current_segment = {
                "segment_id": prior["segment_id"],
                "manifest_ordinal": prior["manifest_ordinal"],
                "active_ordinal": prior["active_ordinal"],
            }
            live_summary = persist("running")
            result = run_one_segment(
                workspace_root=workspace_root,
                segment=segment,
                phits_executable_path=paths.phits_executable_path,
                runner=controlled_runner if stop_control is not None or observe_native else runner,
                input_binding=contracts[prior["segment_id"]]["inputs"],
                observation_context=live_summary if observe_native else None,
            )
            if preparation is not None:
                preparation.publish("verifying", force=True)
            validate_binding(workspace_root, manifest, execution_binding, paths)
            result.update(retained=False, producer_run_id=run_id)
            if result["status"] == "success":
                result["output_evidence"] = result_evidence(workspace_root, contracts[prior["segment_id"]])
            finished_tick = float(monotonic_clock())
            segment_summaries[summary_index] = {
                **result,
                "manifest_ordinal": prior["manifest_ordinal"],
                "active_ordinal": prior["active_ordinal"],
                "started_at": segment_started_at,
                "finished_at": _utc_text(utc_now()),
                "started_elapsed_seconds": _nonnegative_duration(
                    segment_started_tick - started_tick
                ),
                "duration_seconds": _nonnegative_duration(
                    finished_tick - segment_started_tick
                ),
            }
            current_segment = None
            persist("running")
            poll_stop()
            if stop_requested is not None:
                break

        overall = (
            "success"
            if all(
                item["status"] in {"success", "skipped"}
                for item in segment_summaries
            )
            else "stopped" if stop_requested is not None and not any(
                item["status"] in {"failed", "gate_failed"} for item in segment_summaries
            ) else "failed"
        )
        if overall in {"success", "stopped"}:
            validate_binding(workspace_root, manifest, execution_binding, paths)
            validate_results(workspace_root, {"execution_binding": execution_binding,
                "segments": segment_summaries})
        return persist(overall)
    except Exception as exc:
        if retry_plan is not None and parent_attempt is None:
            raise
        current_segment = None
        for segment in segment_summaries:
            if segment.get("status") in {"pending", "running"}:
                segment["status"] = "gate_failed"
                segment["reason"] = str(exc)
                if segment.get("started_at") is not None:
                    segment["finished_at"] = _utc_text(utc_now())
                    segment["duration_seconds"] = _nonnegative_duration(
                        monotonic_clock()
                        - started_tick
                        - float(segment.get("started_elapsed_seconds") or 0.0)
                    )
        persist("gate_failed", failure_reason=str(exc))
        raise
    finally:
        if stop_control is not None:
            stop_control.close()


def paths_from_args(args: argparse.Namespace) -> ExternalToolPaths:
    paths_config = load_paths_config(Path(args.paths_json)) if args.paths_json else None
    return merged_tool_paths(
        paths_config=paths_config,
        phits_root_folder=args.phits_root_folder,
        phits_executable_path=args.phits_executable_path,
        phits2dicom_executable_path=args.phits2dicom_executable_path,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run public dicomxphits PHITS segment inputs.")
    parser.add_argument("--workspace-root", required=True)
    parser.add_argument("--paths-json", default=None)
    parser.add_argument("--phits-root-folder", default=None)
    parser.add_argument("--phits-executable-path", default=None)
    parser.add_argument("--phits2dicom-executable-path", default=None)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--plan-incomplete", action="store_true")
    mode.add_argument("--run-incomplete", action="store_true")
    parser.add_argument("--expected-summary-sha256", default=None)
    parser.add_argument("--control-stdin", action="store_true")
    parser.add_argument("--preflight-nonce", default=None)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    workspace_root = Path(args.workspace_root)
    control = None
    try:
        if args.plan_incomplete:
            from dicomxphits.segment_retry import plan_incomplete
            plan = plan_incomplete(workspace_root, paths_from_args(args))
            print(json.dumps({k: v for k, v in plan.items() if k != "summary"}, ensure_ascii=False))
            return 0
        if args.control_stdin:
            from dicomxphits.segment_stop import StopControl
            control = StopControl()
            control.start_reader(os.fdopen(os.dup(sys.stdin.fileno()), "rb", buffering=0))
        summary = run_segments(
            workspace_root=workspace_root,
            paths=paths_from_args(args),
            command_argv=sys.argv if argv is None else ["dicomxphits-run-segments", *argv],
            run_incomplete=args.run_incomplete,
            expected_summary_sha256=args.expected_summary_sha256,
            stop_control=control,
            preflight_nonce=args.preflight_nonce or uuid.uuid4().hex,
        )
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        print(summary_path(workspace_root))
        return 2
    finally:
        if control is not None:
            control.close()
    from dicomxphits.segment_preflight import SCHEMA as PREFLIGHT_SCHEMA, RELATIVE_PATH
    if summary.get("schema_version") == PREFLIGHT_SCHEMA:
        print(workspace_root / RELATIVE_PATH)
        return 5 if summary.get("phase") == "cancelled_before_launch" else 2
    print(summary_path(workspace_root))
    return 0 if summary["status"] == "success" else 4 if summary["status"] == "stopped" else 3


if __name__ == "__main__":
    raise SystemExit(main())
