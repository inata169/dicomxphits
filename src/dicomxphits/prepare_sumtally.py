from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path, PureWindowsPath
from typing import Any, Callable

from dicomxphits.prepare_3dcrt_workspace import (
    ExternalToolPaths,
    active_segments,
    finite_positive,
    load_paths_config,
    merged_tool_paths,
    validate_public_strict_3dcrt_gate,
    write_json,
)
from dicomxphits.run_segments import phits_environment
from dicomxphits.safe_output import WorkspaceOutputGuard
from dicomxphits.rtdose_geometry import (
    segment_tally_geometry_binding,
    sumtally_output_geometry_evidence,
)
from dicomxphits.sumtally_inputs import (
    ACTIVE_TREATMENT_INPUT_DOSE_STATE,
    ACTIVE_TREATMENT_SUMTALLY_NORMALIZATION,
    TARGET_TALLY_PATTERNS,
    build_sumtally,
    file_sha256,
    generate_sum_inp,
    manifest_sha256,
    validate_sumtally_normalization_input,
)
from dicomxphits.gantry_geometry import (
    require_reusable_gantry_geometry_contract,
)


DEFAULT_SUMTALLY_OUTPUT_NAME = "deposit-target-3D_sum_all_active_segments_totalfield.out"
SUMTALLY_SCOPE = "all_active_segments"
SUMTALLY_MODE = "totalfield"
WEIGHT_FIELD = "segment_mu"
SUMTALLY_NORMALIZATION = ACTIVE_TREATMENT_SUMTALLY_NORMALIZATION
RT_DOSE_CONVERSION_HINT = {
    "input_dose_state": ACTIVE_TREATMENT_INPUT_DOSE_STATE,
    "input_dose_unit": "GY",
    "sumtally_normalization": SUMTALLY_NORMALIZATION,
    "is_beam_mu_output": False,
    "phits2dicom_factor": 1.0,
}
WINDOWS_INVALID_FILENAME_CHARACTERS = frozenset('<>:"/\\|?*')
WINDOWS_RESERVED_FILENAME_STEMS = frozenset(
    {
        "CON",
        "PRN",
        "AUX",
        "NUL",
        "CONIN$",
        "CONOUT$",
        "COM¹",
        "COM²",
        "COM³",
        "LPT¹",
        "LPT²",
        "LPT³",
    }
    | {f"COM{index}" for index in range(1, 10)}
    | {f"LPT{index}" for index in range(1, 10)}
)


def validate_sumtally_output_name(value: str) -> str:
    """Require a portable single filename for the staged Sumtally output."""

    if not isinstance(value, str) or not value:
        raise ValueError("Sumtally output name must be a single portable file name")
    windows_stem = value.split(".", 1)[0].upper()
    if (
        value in {".", ".."}
        or any(
            character in WINDOWS_INVALID_FILENAME_CHARACTERS
            for character in value
        )
        or any(ord(character) < 32 for character in value)
        or value.endswith((" ", "."))
        or windows_stem in WINDOWS_RESERVED_FILENAME_STEMS
        or Path(value).is_absolute()
        or bool(PureWindowsPath(value).drive)
    ):
        raise ValueError("Sumtally output name must be a single portable file name")
    return value


PHITS_INCLUDE_PATTERN = re.compile(
    r"^\s*infl:\s*\{\s*([^}]+?)\s*\}",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class BaseInputSelection:
    path: Path
    rule: str
    segment_id: str | None = None
    segment_index: Any = None


def require_generation_paths(paths: ExternalToolPaths) -> None:
    if not paths.phits_root_folder:
        raise ValueError("Missing required external tool path setting: phits_root_folder")


def require_execution_paths(paths: ExternalToolPaths) -> None:
    if not paths.phits_executable_path:
        raise ValueError("Missing required external tool path setting: phits_executable_path")


def load_json_object(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return data


def resolve_workspace_path(workspace_root: Path, value: str | Path) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return workspace_root / path


def normalize_path(path: str | Path) -> str:
    return str(path).replace("\\", "/")


def path_relative_to_sumtally_cwd(path: Path, *, workspace_root: Path, sumtally_dir: Path) -> tuple[str | None, str, str]:
    resolved = path.resolve()
    workspace_resolved = workspace_root.resolve()
    sumtally_resolved = sumtally_dir.resolve()
    try:
        resolved.relative_to(workspace_resolved)
        cwd_relative = Path(os.path.relpath(resolved, sumtally_resolved)).as_posix()
        return cwd_relative, cwd_relative, "sumtally_cwd_relative"
    except ValueError:
        absolute = resolved.as_posix()
        return None, absolute, "absolute_fallback_workspace_external"


def localize_sumtally_segment_paths(
    content: str,
    helper_summary: dict[str, Any],
    *,
    workspace_root: Path,
    sumtally_dir: Path,
) -> tuple[str, list[tuple[str, float]], str, list[dict[str, Any]]]:
    updated = content
    out_files: list[tuple[str, float]] = []
    path_records: list[dict[str, Any]] = []
    bases: set[str] = set()
    for row in helper_summary.get("segments", []):
        if not isinstance(row, dict):
            continue
        resolved_output_path = Path(str(row["resolved_output_path"]))
        cwd_relative, written, basis = path_relative_to_sumtally_cwd(
            resolved_output_path,
            workspace_root=workspace_root,
            sumtally_dir=sumtally_dir,
        )
        bases.add(basis)
        original = normalize_path(row["resolved_output_path"])
        if original != written:
            updated = updated.replace(original, written, 1)
        row["sumtally_cwd_relative_output_path"] = cwd_relative
        row["sumtally_written_output_path"] = written
        row["sumtally_path_basis"] = basis
        out_files.append((written, row["weight"]))
        path_records.append(
            {
                "beam_number": row.get("beam_number"),
                "segment_index": row.get("segment_index"),
                "expected_output_path": row.get("expected_output_path"),
                "resolved_output_path": str(resolved_output_path.resolve()),
                "sumtally_cwd_relative_output_path": cwd_relative,
                "sumtally_written_output_path": written,
                "sumtally_path_basis": basis,
                "weight": row.get("weight"),
            }
        )
    summary_basis = "sumtally_cwd_relative" if bases == {"sumtally_cwd_relative"} else "mixed_cwd_relative_absolute_fallback"
    return updated, out_files, summary_basis, path_records


def load_manifest(workspace_root: Path) -> tuple[dict[str, Any], Path]:
    manifest_path = workspace_root / "segments" / "segment_manifest.json"
    if not manifest_path.is_file():
        raise FileNotFoundError(f"segment manifest not found: {manifest_path}")
    return load_json_object(manifest_path), manifest_path


def workspace_summary_path(workspace_root: Path) -> Path:
    return workspace_root / "analysis" / "public_preparation_workspace_summary.json"


def phits_generation_summary_path(workspace_root: Path) -> Path:
    return workspace_root / "analysis" / "phits_generation_summary.json"


def metadata_candidate_values(workspace_root: Path) -> list[str]:
    values: list[str] = []
    for path in (workspace_summary_path(workspace_root), phits_generation_summary_path(workspace_root)):
        if not path.is_file():
            continue
        data = load_json_object(path)
        for key in ("sumtally_base_input", "sumtally_base_input_path", "primary_phits_input"):
            value = data.get(key)
            if isinstance(value, str) and value:
                values.append(value)
        phits_generation = data.get("phits_generation")
        if isinstance(phits_generation, dict):
            for key in ("sumtally_base_input", "sumtally_base_input_path", "primary_phits_input"):
                value = phits_generation.get(key)
                if isinstance(value, str) and value:
                    values.append(value)
            generated = phits_generation.get("generated_phits_inputs")
            if isinstance(generated, list):
                values.extend(str(item) for item in generated if item)
        generated = data.get("generated_phits_inputs")
        if isinstance(generated, list):
            values.extend(str(item) for item in generated if item)
    return values


def select_sumtally_base_input(
    *,
    workspace_root: Path,
    manifest: dict[str, Any],
    explicit_base_input: Path | None = None,
) -> BaseInputSelection:
    if explicit_base_input is not None:
        return BaseInputSelection(
            path=resolve_workspace_path(workspace_root, explicit_base_input),
            rule="explicit_base_input",
        )

    for value in metadata_candidate_values(workspace_root):
        candidate = resolve_workspace_path(workspace_root, value)
        if candidate.is_file():
            return BaseInputSelection(path=candidate, rule="workspace_metadata")

    active = active_segments(manifest)
    if not active:
        raise ValueError("No active segment is available for Sumtally base input selection")
    segment = active[0]
    phits_input_path = str(segment.get("phits_input_path") or "")
    if not phits_input_path:
        raise ValueError("First active segment is missing phits_input_path")
    return BaseInputSelection(
        path=resolve_workspace_path(workspace_root, phits_input_path),
        rule="first_active_segment_phits_input",
        segment_id=str(segment.get("segment_id")) if segment.get("segment_id") is not None else None,
        segment_index=segment.get("segment_index"),
    )


def validate_manifest_for_sumtally(manifest: dict[str, Any]) -> dict[str, Any]:
    require_reusable_gantry_geometry_contract(manifest)
    gate = validate_public_strict_3dcrt_gate(manifest)
    for segment in active_segments(manifest):
        expected_output_path = str(segment.get("expected_output_path") or "")
        phits_input_path = str(segment.get("phits_input_path") or "")
        label = str(segment.get("segment_id") or f"segment {segment.get('segment_index')}")
        if not expected_output_path:
            raise ValueError(f"{label}: expected_output_path is required for Sumtally generation")
        if not phits_input_path:
            raise ValueError(f"{label}: phits_input_path is required for Sumtally generation")
        if not finite_positive(segment.get(WEIGHT_FIELD)):
            raise ValueError(f"{label}: {WEIGHT_FIELD} must be present, positive, and finite")
    return gate


def resolve_phits_include_path(path_value: str, *, execution_cwd: Path) -> Path:
    path = Path(path_value)
    if not path.is_absolute():
        path = execution_cwd / path
    return path.resolve()


def transitive_phits_include_paths(
    root_input: Path,
    *,
    execution_cwd: Path,
) -> list[Path]:
    root = root_input.resolve()
    pending = [root]
    visited = {root}
    dependencies: set[Path] = set()
    while pending:
        source = pending.pop()
        if not source.is_file():
            raise FileNotFoundError(f"PHITS input dependency not found: {source}")
        for line in source.read_text(encoding="utf-8", errors="replace").splitlines():
            match = PHITS_INCLUDE_PATTERN.match(line)
            if not match:
                continue
            dependency = resolve_phits_include_path(
                match.group(1),
                execution_cwd=execution_cwd,
            )
            if not dependency.is_file():
                raise FileNotFoundError(
                    f"PHITS include dependency not found: {dependency}"
                )
            dependencies.add(dependency)
            if dependency not in visited:
                visited.add(dependency)
                pending.append(dependency)
    return sorted(dependencies, key=lambda path: str(path).casefold())


def file_digest_evidence(paths: list[Path]) -> list[dict[str, str]]:
    evidence: list[dict[str, str]] = []
    resolved_paths = {item.resolve() for item in paths}
    for path in sorted(resolved_paths, key=lambda item: str(item).casefold()):
        if not path.is_file():
            raise FileNotFoundError(f"Sumtally input dependency not found: {path}")
        evidence.append({"path": str(path), "sha256": file_sha256(path)})
    return evidence


def validate_file_digest_evidence(
    recorded: Any,
    *,
    current_paths: list[Path],
    label: str,
) -> list[dict[str, str]]:
    if not isinstance(recorded, list):
        raise ValueError(
            f"Sumtally generation summary is missing {label} digest evidence; "
            "rerun Sumtally Generate"
        )
    recorded_by_path: dict[Path, str] = {}
    for item in recorded:
        if not isinstance(item, dict):
            raise ValueError(
                f"Sumtally generation summary has invalid {label} digest evidence; "
                "rerun Sumtally Generate"
            )
        path_value = str(item.get("path") or "")
        sha256 = str(item.get("sha256") or "")
        if not path_value or not sha256:
            raise ValueError(
                f"Sumtally generation summary has incomplete {label} digest evidence; "
                "rerun Sumtally Generate"
            )
        path = Path(path_value).resolve()
        if path in recorded_by_path:
            raise ValueError(
                f"Sumtally generation summary has duplicate {label} digest evidence; "
                "rerun Sumtally Generate"
            )
        recorded_by_path[path] = sha256

    current = file_digest_evidence(current_paths)
    current_by_path = {
        Path(item["path"]).resolve(): item["sha256"] for item in current
    }
    if set(recorded_by_path) != set(current_by_path):
        raise ValueError(
            f"Sumtally {label} dependency set changed after Sumtally Generate; "
            "rerun Sumtally Generate"
        )
    for path, sha256 in current_by_path.items():
        if recorded_by_path[path] != sha256:
            raise ValueError(
                f"Sumtally {label} changed after Sumtally Generate: {path}; "
                "rerun Sumtally Generate"
            )
    return current


def derive_tally_patterns_from_manifest(manifest: dict[str, Any], default_patterns: list[str]) -> list[str]:
    patterns: list[str] = []
    for segment in active_segments(manifest):
        expected_output_path = str(segment.get("expected_output_path") or "")
        if not expected_output_path:
            continue
        normalized = expected_output_path.replace("\\", "/")
        name = Path(normalized).name
        for value in (f"file = {normalized}", f"file = {name}"):
            if value and value not in patterns:
                patterns.append(value)
    for value in default_patterns:
        if value and value not in patterns:
            patterns.append(value)
    if not patterns:
        raise ValueError("No target tally patterns could be derived from the segment manifest")
    return patterns


def write_failure_summary(
    *,
    path: Path,
    stage: str,
    workspace_root: Path,
    reason: str,
    command_argv: list[str] | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "schema_version": "dicomxphits_public_sumtally_stage_v1",
        "stage": stage,
        "stage_status": "gate_failed",
        "workspace_root": str(workspace_root),
        "failure_reason": reason,
        "command": {"argv": command_argv or sys.argv},
        "returncode": None,
        "phits_execution_started": False,
    }
    if extra:
        summary.update(extra)
    write_json(path, summary, case_root=workspace_root)
    return summary


def generate_sumtally(
    *,
    workspace_root: Path,
    paths: ExternalToolPaths,
    output_name: str = DEFAULT_SUMTALLY_OUTPUT_NAME,
    base_input: Path | None = None,
    command_argv: list[str] | None = None,
) -> dict[str, Any]:
    with WorkspaceOutputGuard(workspace_root):
        pass
    workspace_root = workspace_root.resolve()
    generation_summary_path = workspace_root / "analysis" / "sumtally_generation_summary.json"
    try:
        output_name = validate_sumtally_output_name(output_name)
        require_generation_paths(paths)

        manifest, manifest_path = load_manifest(workspace_root)
        bound_manifest_sha256 = manifest_sha256(manifest)
        strict_gate = validate_manifest_for_sumtally(manifest)
        validate_segment_outputs_exist(workspace_root, manifest)
        tally_patterns = derive_tally_patterns_from_manifest(manifest, list(TARGET_TALLY_PATTERNS))
        selection = select_sumtally_base_input(
            workspace_root=workspace_root,
            manifest=manifest,
            explicit_base_input=base_input,
        )
        if not selection.path.is_file():
            raise FileNotFoundError(f"Sumtally base PHITS input not found: {selection.path}")

        content, helper_summary = build_sumtally(
            manifest,
            case_root=workspace_root,
            output_name=output_name,
            weight_field=WEIGHT_FIELD,
            mode=SUMTALLY_MODE,
        )

        sumtally_dir = workspace_root / "sumtally"
        sumtally_path = sumtally_dir / "sumtally.inp"
        sum_input_path = sumtally_dir / f"{selection.path.stem}_sum.inp"
        libpath_path = sumtally_dir / "libpath.inp"
        with WorkspaceOutputGuard(workspace_root) as guard:
            guard.mkdir(sumtally_dir)
            for output_path in (sumtally_path, sum_input_path, libpath_path):
                guard.prepare(output_path)
            content, out_files, path_basis, segment_path_records = localize_sumtally_segment_paths(
                content,
                helper_summary,
                workspace_root=workspace_root,
                sumtally_dir=sumtally_dir,
            )
            guard.write_text(sumtally_path, content, newline="\n")
            normalization_evidence = validate_sumtally_normalization_input(
                sumtally_path,
                manifest=manifest,
                recorded_evidence=helper_summary["sumtally_normalization_evidence"],
            )
            portable_root = paths.phits_root_folder.replace("\\", "/")
            guard.write_text(
                libpath_path,
                f"file(1)  = {portable_root} # PHITS install folder name\n",
                newline="\r\n",
            )
            with tempfile.TemporaryDirectory(prefix="dicomxphits-sumtally-") as temporary:
                temporary_sum_input = Path(temporary) / sum_input_path.name
                generate_sum_inp(
                    selection.path,
                    out_files,
                    output_name,
                    float(helper_summary["sumfactor"]),
                    SUMTALLY_MODE,
                    tally_patterns,
                    temporary_sum_input,
                    sumtally_filename=sumtally_path.name,
                    include_base_dir=workspace_root,
                    output_dir_basis=sum_input_path.parent,
                )
                guard.write_bytes(sum_input_path, temporary_sum_input.read_bytes())
            sum_input_sha256 = file_sha256(sum_input_path)
            sumtally_input_sha256 = file_sha256(sumtally_path)
        segment_output_evidence = file_digest_evidence(
            expected_segment_outputs(workspace_root, manifest)
        )
        tally_geometry_binding = segment_tally_geometry_binding(
            expected_segment_outputs(workspace_root, manifest)
        )
        wrapper_include_evidence = file_digest_evidence(
            transitive_phits_include_paths(
                sum_input_path,
                execution_cwd=sum_input_path.parent,
            )
        )

        summary = {
            "schema_version": "dicomxphits_public_sumtally_generation_v1",
            "stage": "generate_sumtally",
            "stage_status": "success",
            "workspace_root": str(workspace_root),
            "command": {"argv": command_argv or sys.argv},
            "returncode": 0,
            "phits_execution_started": False,
            "sumtally_scope": SUMTALLY_SCOPE,
            "sumtally_mode": SUMTALLY_MODE,
            "weight_field": WEIGHT_FIELD,
            "sumtally_normalization": SUMTALLY_NORMALIZATION,
            "rt_dose_conversion_hint": dict(RT_DOSE_CONVERSION_HINT),
            "sumtally_normalization_evidence": normalization_evidence,
            "strict_gate": strict_gate,
            "manifest_path": str(manifest_path),
            "manifest_sha256": bound_manifest_sha256,
            "sum_input_sha256": sum_input_sha256,
            "sumtally_input_sha256": sumtally_input_sha256,
            "segment_output_evidence": segment_output_evidence,
            "tally_geometry_binding": tally_geometry_binding,
            "wrapper_include_evidence": wrapper_include_evidence,
            "path_config": {
                "phits_root_folder": paths.phits_root_folder,
                "phits_executable_path": paths.phits_executable_path,
                "phits2dicom_executable_path": paths.phits2dicom_executable_path,
            },
            "sumtally_base_input": str(selection.path),
            "sumtally_base_input_selection_rule": selection.rule,
            "sumtally_base_input_segment_id": selection.segment_id,
            "sumtally_base_input_segment_index": selection.segment_index,
            "sumtally_input_path_basis": path_basis,
            "sumtally_segment_paths": segment_path_records,
            "tally_patterns": tally_patterns,
            "outputs": {
                "sumtally_input": str(sumtally_path),
                "sum_input": str(sum_input_path),
                "libpath": str(libpath_path),
                "sumtally_output": str(sumtally_dir / output_name),
                "generation_summary": str(generation_summary_path),
            },
            "sumtally_helper_summary": helper_summary,
        }
        write_json(generation_summary_path, summary, case_root=workspace_root)
        return summary
    except Exception as exc:
        write_failure_summary(
            path=generation_summary_path,
            stage="generate_sumtally",
            workspace_root=workspace_root,
            reason=str(exc),
            command_argv=command_argv,
            extra={
                "sumtally_scope": SUMTALLY_SCOPE,
                "sumtally_mode": SUMTALLY_MODE,
                "weight_field": WEIGHT_FIELD,
                "sumtally_normalization": SUMTALLY_NORMALIZATION,
                "rt_dose_conversion_hint": dict(RT_DOSE_CONVERSION_HINT),
            },
        )
        raise


def expected_segment_outputs(workspace_root: Path, manifest: dict[str, Any]) -> list[Path]:
    return [
        resolve_workspace_path(workspace_root, str(segment.get("expected_output_path") or ""))
        for segment in active_segments(manifest)
    ]


def validate_segment_outputs_exist(workspace_root: Path, manifest: dict[str, Any]) -> None:
    missing = [path for path in expected_segment_outputs(workspace_root, manifest) if not path.is_file()]
    if missing:
        joined = ", ".join(str(path) for path in missing)
        raise FileNotFoundError(f"Expected segment PHITS output file(s) not found: {joined}")


def run_phits_sumtally(
    *,
    phits_executable_path: str,
    sum_input: Path,
    stdout_path: Path,
    stderr_path: Path,
    workspace_root: Path,
    expected_output: Path,
    expected_geometry: dict[str, Any] | None = None,
    environment: dict[str, str] | None = None,
    runner=subprocess.run,
    on_start: Callable[[], None] | None = None,
) -> tuple[subprocess.CompletedProcess[str], dict[str, Any] | None, str | None]:
    if environment is None:
        environment = phits_environment(sum_input)
    with WorkspaceOutputGuard(workspace_root) as guard:
        for output in (
            expected_output,
            stdout_path,
            stderr_path,
            sum_input.parent / "batch.out",
            sum_input.parent / "phits.out",
        ):
            guard.prepare_file_target(output, create_parents=True)
        execution_root = guard.make_staging_directory(
            workspace_root,
            prefix=".sumtally-run-",
        )
        try:
            staged_sum_input = execution_root / sum_input.name
            guard.copy_file(sum_input, staged_sum_input, overwrite=False)
            for dependency in transitive_phits_include_paths(
                sum_input,
                execution_cwd=sum_input.parent,
            ):
                try:
                    relative = dependency.resolve().relative_to(
                        sum_input.parent.resolve()
                    )
                except ValueError:
                    continue
                guard.copy_file(
                    dependency,
                    execution_root / relative,
                    overwrite=False,
                )
            try:
                output_relative = expected_output.resolve().relative_to(
                    sum_input.parent.resolve()
                )
            except ValueError as exc:
                raise ValueError(
                    "Sumtally output must remain below its execution directory"
                ) from exc
            staged_output = execution_root / output_relative
            guard.mkdir(staged_output.parent)
            with staged_sum_input.open(
                "r", encoding="utf-8", errors="replace"
            ) as stdin:
                if on_start is not None:
                    on_start()
                result = runner(
                    [phits_executable_path],
                    stdin=stdin,
                    cwd=execution_root,
                    capture_output=True,
                    text=True,
                    shell=False,
                    env=environment,
                )
            geometry_evidence = None
            geometry_validation_error = None
            if os.path.lexists(staged_output):
                guard.prepare_file_target(staged_output)
                staged_output_non_empty = staged_output.stat().st_size > 0
                if result.returncode == 0 and staged_output_non_empty:
                    if expected_geometry is not None:
                        try:
                            geometry_evidence = sumtally_output_geometry_evidence(
                                staged_output,
                                expected_geometry=expected_geometry,
                            )
                        except Exception as exc:
                            geometry_validation_error = (
                                "Sumtally output geometry validation failed: " + str(exc)
                            )
                    if geometry_validation_error is None:
                        guard.copy_file(staged_output, expected_output)
                        if geometry_evidence is not None:
                            geometry_evidence = {
                                **geometry_evidence,
                                "path": str(expected_output.resolve()),
                            }
            for name in ("batch.out", "phits.out"):
                staged_root_output = execution_root / name
                if os.path.lexists(staged_root_output):
                    guard.copy_file(staged_root_output, sum_input.parent / name)
            guard.write_text(stdout_path, result.stdout or "")
            guard.write_text(stderr_path, result.stderr or "")
        finally:
            guard.rmtree(execution_root, missing_ok=True)
    return result, geometry_evidence, geometry_validation_error


def sumtally_output_snapshot(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    stat = path.stat()
    return {
        "size": stat.st_size,
        "mtime_ns": stat.st_mtime_ns,
        "sha256": file_sha256(path),
    }


def run_sumtally(
    *,
    workspace_root: Path,
    paths: ExternalToolPaths,
    sum_input: Path | None = None,
    command_argv: list[str] | None = None,
    runner=subprocess.run,
) -> dict[str, Any]:
    with WorkspaceOutputGuard(workspace_root):
        pass
    workspace_root = workspace_root.resolve()
    execution_summary_path = workspace_root / "analysis" / "sumtally_execution_summary.json"
    phits_started = False
    try:
        require_execution_paths(paths)
        manifest, _ = load_manifest(workspace_root)
        validate_manifest_for_sumtally(manifest)
        validate_segment_outputs_exist(workspace_root, manifest)

        generation_summary_path = workspace_root / "analysis" / "sumtally_generation_summary.json"
        generation_summary = load_json_object(generation_summary_path)
        if generation_summary.get("stage_status") != "success":
            raise ValueError("Sumtally generation summary is not successful")
        current_manifest_sha256 = manifest_sha256(manifest)
        generation_manifest_sha256 = str(
            generation_summary.get("manifest_sha256") or ""
        )
        if not generation_manifest_sha256:
            raise ValueError(
                "Sumtally generation summary is missing manifest_sha256; "
                "rerun Sumtally Generate"
            )
        if generation_manifest_sha256 != current_manifest_sha256:
            raise ValueError(
                "Segment manifest changed after Sumtally Generate; "
                "rerun Sumtally Generate"
            )
        outputs = generation_summary.get("outputs")
        if not isinstance(outputs, dict):
            raise ValueError(
                "Sumtally generation summary is missing generated input paths; "
                "rerun Sumtally Generate"
            )
        recorded_sum_input_value = str(outputs.get("sum_input") or "")
        recorded_sumtally_input_value = str(outputs.get("sumtally_input") or "")
        if not recorded_sum_input_value or not recorded_sumtally_input_value:
            raise ValueError(
                "Sumtally generation summary is missing generated input paths; "
                "rerun Sumtally Generate"
            )
        generated_sum_input = resolve_workspace_path(
            workspace_root,
            recorded_sum_input_value,
        ).resolve()
        generated_sumtally_input = resolve_workspace_path(
            workspace_root,
            recorded_sumtally_input_value,
        ).resolve()
        requested_sum_input = (
            resolve_workspace_path(workspace_root, sum_input)
            if sum_input is not None
            else generated_sum_input
        )
        if requested_sum_input.resolve() != generated_sum_input:
            raise ValueError(
                "--sum-input must reference the wrapper recorded by Sumtally "
                "Generate; rerun Sumtally Generate for a different input"
            )
        selected_sum_input = generated_sum_input
        if not selected_sum_input.is_file():
            raise FileNotFoundError(f"Sumtally wrapper input not found: {selected_sum_input}")
        if not generated_sumtally_input.is_file():
            raise FileNotFoundError(
                f"Generated Sumtally input not found: {generated_sumtally_input}"
            )
        generation_sum_input_sha256 = str(
            generation_summary.get("sum_input_sha256") or ""
        )
        generation_sumtally_input_sha256 = str(
            generation_summary.get("sumtally_input_sha256") or ""
        )
        if not generation_sum_input_sha256 or not generation_sumtally_input_sha256:
            raise ValueError(
                "Sumtally generation summary is missing input digest evidence; "
                "rerun Sumtally Generate"
            )
        current_sum_input_sha256 = file_sha256(selected_sum_input)
        current_sumtally_input_sha256 = file_sha256(generated_sumtally_input)
        if current_sum_input_sha256 != generation_sum_input_sha256:
            raise ValueError(
                "Generated Sumtally wrapper changed after Sumtally Generate; "
                "rerun Sumtally Generate"
            )
        if current_sumtally_input_sha256 != generation_sumtally_input_sha256:
            raise ValueError(
                "Generated sumtally.inp changed after Sumtally Generate; "
                "rerun Sumtally Generate"
            )
        normalization_evidence = validate_sumtally_normalization_input(
            generated_sumtally_input,
            manifest=manifest,
            recorded_evidence=generation_summary.get(
                "sumtally_normalization_evidence"
            ),
        )
        if generation_summary.get("sumtally_normalization") != SUMTALLY_NORMALIZATION:
            raise ValueError(
                "Sumtally normalization contract is stale; rerun Sumtally Generate"
            )
        if generation_summary.get("rt_dose_conversion_hint") != RT_DOSE_CONVERSION_HINT:
            raise ValueError(
                "Sumtally RTDOSE conversion hint is stale; rerun Sumtally Generate"
            )
        current_segment_output_evidence = validate_file_digest_evidence(
            generation_summary.get("segment_output_evidence"),
            current_paths=expected_segment_outputs(workspace_root, manifest),
            label="segment output",
        )
        current_wrapper_include_evidence = validate_file_digest_evidence(
            generation_summary.get("wrapper_include_evidence"),
            current_paths=transitive_phits_include_paths(
                selected_sum_input,
                execution_cwd=selected_sum_input.parent,
            ),
            label="wrapper include",
        )
        current_tally_geometry_binding = segment_tally_geometry_binding(
            expected_segment_outputs(workspace_root, manifest)
        )
        recorded_tally_geometry_binding = generation_summary.get(
            "tally_geometry_binding"
        )
        if not isinstance(recorded_tally_geometry_binding, dict):
            raise ValueError(
                "Sumtally generation summary is missing tally geometry evidence; "
                "rerun Sumtally Generate"
            )
        if current_tally_geometry_binding != recorded_tally_geometry_binding:
            raise ValueError(
                "Active segment tally geometry changed after Sumtally Generate; "
                "rerun Sumtally Generate"
            )
        expected_output = Path(
            os.path.abspath(
                os.fspath(
                    resolve_workspace_path(
                        workspace_root,
                        str(outputs["sumtally_output"]),
                    )
                )
            )
        )
        stdout_path = workspace_root / "sumtally" / "sumtally_stdout.txt"
        stderr_path = workspace_root / "sumtally" / "sumtally_stderr.txt"

        with WorkspaceOutputGuard(workspace_root) as guard:
            guard.prepare_file_target(
                expected_output,
                create_parents=True,
            )
            guard.prepare_file_target(
                execution_summary_path,
                create_parents=True,
            )
        output_before = sumtally_output_snapshot(expected_output)
        environment = phits_environment(selected_sum_input)
        def mark_phits_started() -> None:
            nonlocal phits_started
            phits_started = True

        (
            result,
            sumtally_geometry_evidence,
            geometry_validation_error,
        ) = run_phits_sumtally(
            phits_executable_path=paths.phits_executable_path,
            sum_input=selected_sum_input,
            stdout_path=stdout_path,
            stderr_path=stderr_path,
            workspace_root=workspace_root,
            expected_output=expected_output,
            expected_geometry=current_tally_geometry_binding["mesh_geometry"],
            environment=environment,
            runner=runner,
            on_start=mark_phits_started,
        )
        output_after = sumtally_output_snapshot(expected_output)
        output_exists = output_after is not None
        output_size = output_after["size"] if output_after is not None else None
        output_non_empty = output_size is not None and output_size > 0
        output_sha256 = output_after["sha256"] if output_after is not None else None
        output_updated = output_after is not None and (
            output_before is None
            or output_after["sha256"] != output_before["sha256"]
        )
        summary = {
            "schema_version": "dicomxphits_public_sumtally_execution_v1",
            "stage": "run_sumtally",
            "stage_status": (
                "success"
                if (
                    result.returncode == 0
                    and output_updated
                    and output_non_empty
                    and geometry_validation_error is None
                )
                else "failed"
            ),
            "workspace_root": str(workspace_root),
            "command": {
                "argv": command_argv or sys.argv,
                "phits_command": [paths.phits_executable_path],
                "stdin": str(selected_sum_input),
                "cwd": str(selected_sum_input.parent),
                "shell": False,
            },
            "returncode": result.returncode,
            "stdout_path": str(stdout_path),
            "stderr_path": str(stderr_path),
            "phits_execution_started": phits_started,
            "expected_sumtally_output": str(expected_output),
            "expected_sumtally_output_exists": output_exists,
            "expected_sumtally_output_size": output_size,
            "expected_sumtally_output_non_empty": output_non_empty,
            "expected_sumtally_output_sha256": output_sha256,
            "expected_sumtally_output_updated_by_run": output_updated,
            "expected_sumtally_output_before_run": output_before,
            "expected_sumtally_output_after_run": output_after,
            "sumtally_scope": generation_summary.get("sumtally_scope"),
            "sumtally_mode": generation_summary.get("sumtally_mode"),
            "weight_field": generation_summary.get("weight_field"),
            "sumtally_normalization": generation_summary.get("sumtally_normalization"),
            "rt_dose_conversion_hint": generation_summary.get("rt_dose_conversion_hint"),
            "sumtally_normalization_evidence": normalization_evidence,
            "manifest_sha256": current_manifest_sha256,
            "sum_input_sha256": current_sum_input_sha256,
            "sumtally_input_sha256": current_sumtally_input_sha256,
            "segment_output_evidence": current_segment_output_evidence,
            "wrapper_include_evidence": current_wrapper_include_evidence,
            "tally_geometry_binding": current_tally_geometry_binding,
            "sumtally_output_geometry_evidence": sumtally_geometry_evidence,
        }
        if geometry_validation_error is not None:
            summary["failure_reason"] = geometry_validation_error
        write_json(execution_summary_path, summary, case_root=workspace_root)
        return summary
    except Exception as exc:
        write_failure_summary(
            path=execution_summary_path,
            stage="run_sumtally",
            workspace_root=workspace_root,
            reason=str(exc),
            command_argv=command_argv,
            extra={"phits_execution_started": phits_started},
        )
        raise


def paths_from_args(args: argparse.Namespace) -> ExternalToolPaths:
    paths_config = load_paths_config(Path(args.paths_json)) if args.paths_json else None
    return merged_tool_paths(
        paths_config=paths_config,
        phits_root_folder=args.phits_root_folder,
        phits_executable_path=args.phits_executable_path,
        phits2dicom_executable_path=args.phits2dicom_executable_path,
    )


def build_generate_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate public dicomxphits all-segments Sumtally inputs.")
    parser.add_argument("--workspace-root", required=True)
    parser.add_argument("--paths-json", default=None)
    parser.add_argument("--phits-root-folder", default=None)
    parser.add_argument("--phits-executable-path", default=None)
    parser.add_argument("--phits2dicom-executable-path", default=None)
    parser.add_argument("--output-name", default=DEFAULT_SUMTALLY_OUTPUT_NAME)
    parser.add_argument("--base-input", default=None)
    return parser


def build_run_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run public dicomxphits Sumtally with PHITS.")
    parser.add_argument("--workspace-root", required=True)
    parser.add_argument("--paths-json", default=None)
    parser.add_argument("--phits-root-folder", default=None)
    parser.add_argument("--phits-executable-path", default=None)
    parser.add_argument("--phits2dicom-executable-path", default=None)
    parser.add_argument("--sum-input", default=None)
    return parser


def generate_main(argv: list[str] | None = None) -> int:
    args = build_generate_parser().parse_args(argv)
    try:
        summary = generate_sumtally(
            workspace_root=Path(args.workspace_root),
            paths=paths_from_args(args),
            output_name=args.output_name,
            base_input=Path(args.base_input) if args.base_input else None,
            command_argv=sys.argv if argv is None else ["dicomxphits-generate-sumtally", *argv],
        )
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(summary["outputs"]["generation_summary"])
    return 0


def run_main(argv: list[str] | None = None) -> int:
    args = build_run_parser().parse_args(argv)
    try:
        summary = run_sumtally(
            workspace_root=Path(args.workspace_root),
            paths=paths_from_args(args),
            sum_input=Path(args.sum_input) if args.sum_input else None,
            command_argv=sys.argv if argv is None else ["dicomxphits-run-sumtally", *argv],
        )
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(workspace_summary_path(Path(args.workspace_root)).parent / "sumtally_execution_summary.json")
    return 0 if summary.get("stage_status") == "success" else 3


if __name__ == "__main__":
    raise SystemExit(generate_main())
