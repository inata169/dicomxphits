from __future__ import annotations

import argparse
import json
import math
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

from dicomxphits.prepare_3dcrt_workspace import (
    ExternalToolPaths,
    load_paths_config,
    merged_tool_paths,
    write_json,
)
from dicomxphits.safe_output import UnsafeWorkspacePathError, WorkspaceOutputGuard


SUMMARY_RELATIVE_PATH = Path("analysis") / "segment_execution_summary.json"
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
    resolved = path.resolve() if path.is_absolute() else (workspace_root / path).resolve()
    workspace_resolved = workspace_root.resolve()
    try:
        resolved.relative_to(workspace_resolved)
    except ValueError as exc:
        raise ValueError(f"{label} must resolve inside workspace root: {value}") from exc
    return resolved


def require_execution_paths(paths: ExternalToolPaths) -> None:
    if not paths.phits_executable_path:
        raise ValueError("Missing required external tool path setting: phits_executable_path")


def summary_path(workspace_root: Path) -> Path:
    return workspace_root / SUMMARY_RELATIVE_PATH


def blank_segment_summary(segment: dict[str, Any], *, status: str, reason: str | None = None) -> dict[str, Any]:
    return {
        "segment_id": str(segment.get("segment_id") or segment.get("segment_index") or "unknown"),
        "phits_input_path": str(segment.get("phits_input_path") or ""),
        "expected_output_path": str(segment.get("expected_output_path") or ""),
        "return_code": None,
        "stdout_log_path": None,
        "stderr_log_path": None,
        "status": status,
        "reason": reason,
    }


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
        if not phits_target.exists():
            guard.copy_file(phits_source, phits_target, overwrite=False)
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
) -> tuple[list[Path], list[Path]]:
    """Return workspace-local input dependencies and declared output paths."""

    root = workspace_root.resolve()
    pending = [phits_input.resolve()]
    inputs: list[Path] = []
    outputs: list[Path] = []
    seen_inputs: set[Path] = set()
    seen_outputs: set[Path] = set()
    while pending:
        source = pending.pop()
        if source in seen_inputs:
            continue
        try:
            source.relative_to(root)
        except ValueError as exc:
            raise ValueError(
                f"PHITS input dependency must resolve inside workspace root: {source}"
            ) from exc
        if not source.is_file():
            raise FileNotFoundError(f"PHITS input dependency not found: {source}")
        seen_inputs.add(source)
        inputs.append(source)
        with source.open("r", encoding="utf-8", errors="replace") as stream:
            for line in stream:
                include_match = PHITS_INCLUDE_PATTERN.match(line)
                if include_match is not None:
                    value = os.path.expandvars(os.path.expanduser(include_match.group(1)))
                    include = Path(value)
                    dependency = (
                        include.resolve()
                        if include.is_absolute()
                        else (root / include).resolve()
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
    )
    if expected_output.resolve() not in {path.resolve() for path in outputs}:
        raise ValueError(
            "expected_output_path is not declared by the selected PHITS input"
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
    if not phits_input.is_file():
        raise FileNotFoundError(f"PHITS input file not found: {phits_input}")
    environment = phits_environment(phits_input)

    output_dir = expected_output.parent
    stdout_path = output_dir / "phits_stdout.txt"
    stderr_path = output_dir / "phits_stderr.txt"

    with WorkspaceOutputGuard(workspace_root) as guard:
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
            result = runner(
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
            staged_expected_output = (
                execution_root
                / expected_output.resolve().relative_to(workspace_root.resolve())
            )
            if result.returncode == 0 and staged_expected_output.is_file():
                for output in declared_outputs:
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
        finally:
            guard.rmtree(execution_root, missing_ok=True)

    output_exists = expected_output.is_file()
    status = "success" if result.returncode == 0 and output_exists else "failed"
    return {
        "segment_id": str(segment.get("segment_id") or segment.get("segment_index") or "unknown"),
        "phits_input_path": str(phits_input),
        "expected_output_path": str(expected_output),
        "return_code": result.returncode,
        "stdout_log_path": str(stdout_path),
        "stderr_log_path": str(stderr_path),
        "status": status,
        "expected_output_exists": output_exists,
        "batch_out_path": collected["batch_out_path"],
        "phits_out_path": collected["phits_out_path"],
    }


def build_summary(
    *,
    workspace_root: Path,
    status: str,
    segments: list[dict[str, Any]],
    command_argv: list[str] | None,
    failure_reason: str | None = None,
) -> dict[str, Any]:
    succeeded = sum(1 for segment in segments if segment.get("status") == "success")
    failed = sum(1 for segment in segments if segment.get("status") in {"failed", "gate_failed"})
    skipped = sum(1 for segment in segments if segment.get("status") == "skipped")
    return {
        "schema_version": "dicomxphits_public_segment_execution_v1",
        "stage": "run_segments",
        "status": status,
        "stage_status": status,
        "workspace_root": str(workspace_root),
        "command": {"argv": command_argv or sys.argv},
        "segment_count": len(segments),
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
) -> dict[str, Any]:
    summary_file = summary_path(workspace_root)
    segment_summaries: list[dict[str, Any]] = []
    try:
        require_execution_paths(paths)
        manifest, _manifest_path = load_manifest(workspace_root)
        raw_segments = manifest.get("segments")
        if not isinstance(raw_segments, list):
            raise ValueError("segment manifest must contain a segments list")

        active_segments: list[tuple[int, dict[str, Any]]] = []
        for item in raw_segments:
            if not isinstance(item, dict):
                continue
            is_active, skip_reason = segment_active_state(item)
            if is_active:
                active_segments.append((len(segment_summaries), item))
                segment_summaries.append(blank_segment_summary(item, status="pending"))
            else:
                segment_summaries.append(blank_segment_summary(item, status="skipped", reason=skip_reason))

        for _summary_index, segment in active_segments:
            phits_input = resolve_workspace_file(
                workspace_root,
                str(segment.get("phits_input_path") or ""),
                label="phits_input_path",
            )
            resolve_workspace_file(
                workspace_root,
                str(segment.get("expected_output_path") or ""),
                label="expected_output_path",
            )
            if not phits_input.is_file():
                raise FileNotFoundError(f"PHITS input file not found: {phits_input}")
            phits_environment(phits_input)

        for summary_index, segment in active_segments:
            segment_summaries[summary_index] = (
                run_one_segment(
                    workspace_root=workspace_root,
                    segment=segment,
                    phits_executable_path=paths.phits_executable_path,
                    runner=runner,
                )
            )

        overall = "success" if all(item["status"] in {"success", "skipped"} for item in segment_summaries) else "failed"
        summary = build_summary(
            workspace_root=workspace_root,
            status=overall,
            segments=segment_summaries,
            command_argv=command_argv,
        )
        write_json(summary_file, summary, case_root=workspace_root)
        return summary
    except Exception as exc:
        for segment in segment_summaries:
            if segment.get("status") == "pending":
                segment["status"] = "gate_failed"
                segment["reason"] = str(exc)
        summary = build_summary(
            workspace_root=workspace_root,
            status="gate_failed",
            segments=segment_summaries,
            command_argv=command_argv,
            failure_reason=str(exc),
        )
        write_json(summary_file, summary, case_root=workspace_root)
        raise


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
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    workspace_root = Path(args.workspace_root)
    try:
        summary = run_segments(
            workspace_root=workspace_root,
            paths=paths_from_args(args),
            command_argv=sys.argv if argv is None else ["dicomxphits-run-segments", *argv],
        )
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        print(summary_path(workspace_root))
        return 2
    print(summary_path(workspace_root))
    return 0 if summary["status"] == "success" else 3


if __name__ == "__main__":
    raise SystemExit(main())
