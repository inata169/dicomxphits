from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any, Mapping

from dicomxphits.fix_coordinates import (
    AXIS_MAPPING as COORDINATE_CORRECTION_AXIS_MAPPING,
    SCHEMA_VERSION as COORDINATE_CORRECTION_SCHEMA_VERSION,
)
from dicomxphits.prepare_3dcrt_workspace import (
    active_segments,
    validate_public_strict_3dcrt_gate,
)
from dicomxphits.safe_output import WorkspaceOutputGuard
from dicomxphits.sumtally_inputs import file_sha256, manifest_sha256


RECOVERY_COMPLETE = "complete"
RECOVERY_READY = "ready"
RECOVERY_INVALID = "invalid"

FULL_DOWNSTREAM_SEQUENCE = (
    "generate_sumtally",
    "run_sumtally",
    "prepare_rtdose",
    "run_rtdose",
)
RTDOSE_SEQUENCE = ("prepare_rtdose", "run_rtdose")
RTDOSE_RUN_SEQUENCE = ("run_rtdose",)

SUMMARY_PATHS = {
    "segments": Path("analysis") / "segment_execution_summary.json",
    "sumtally_generate": Path("analysis") / "sumtally_generation_summary.json",
    "sumtally_run": Path("analysis") / "sumtally_execution_summary.json",
    "rtdose_prepare": Path("analysis") / "rtdose_conversion_prepare_summary.json",
    "rtdose_run": Path("analysis") / "rtdose_conversion_execution_summary.json",
}


class WorkspaceRecoveryError(ValueError):
    """A controlled existing-workspace inspection or recovery failure."""


@dataclass(frozen=True)
class WorkspaceRecoveryInspection:
    workspace_root: Path
    state: str
    highest_verified_stage: str
    next_stage: str | None
    stage_sequence: tuple[str, ...]
    message: str
    phits_reusable: bool
    final_output: Path | None = None

    @property
    def can_create_rtdose(self) -> bool:
        return self.state == RECOVERY_READY and bool(self.stage_sequence)


@dataclass(frozen=True)
class RecoveryHistory:
    root: Path
    manifest_path: Path
    preserved_files: tuple[Path, ...]


def _load_object(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _succeeded(summary: Mapping[str, Any] | None) -> bool:
    if not summary:
        return False
    return any(
        summary.get(field) in {"completed", "success", "prepared"}
        for field in ("stage_status", "status")
    )


def _path_key(path: Path) -> str:
    return os.path.normcase(str(path.resolve()))


def _workspace_path(workspace_root: Path, value: str | Path) -> Path:
    raw = Path(value)
    candidate = raw if raw.is_absolute() else workspace_root / raw
    resolved = candidate.resolve()
    try:
        resolved.relative_to(workspace_root.resolve())
    except ValueError as exc:
        raise WorkspaceRecoveryError(
            f"Workspace artifact escapes the selected workspace: {value}"
        ) from exc
    return resolved


def _portable_parts(value: str) -> tuple[str, ...] | None:
    if re.match(r"^[A-Za-z]:[\\/]", value) or "\\" in value:
        path = PureWindowsPath(value)
    else:
        path = PurePosixPath(value)
    return tuple(path.parts)


def rebind_workspace_path(
    value: str | Path,
    *,
    recorded_workspace_root: str | Path | None,
    current_workspace_root: Path,
) -> Path:
    """Map one recorded in-workspace path to the explicitly selected root."""

    text = str(value).strip()
    if not text:
        raise WorkspaceRecoveryError("Recorded workspace artifact path is empty")
    current_root = current_workspace_root.resolve()
    path = Path(text)
    if not path.is_absolute() and not re.match(r"^[A-Za-z]:[\\/]", text):
        return _workspace_path(current_root, path)

    old_root_text = str(recorded_workspace_root or "").strip()
    if not old_root_text:
        try:
            path.resolve().relative_to(current_root)
        except ValueError as exc:
            raise WorkspaceRecoveryError(
                "Absolute artifact path has no recorded workspace root"
            ) from exc
        return path.resolve()

    value_parts = _portable_parts(text)
    root_parts = _portable_parts(old_root_text)
    assert value_parts is not None and root_parts is not None
    if len(value_parts) < len(root_parts):
        raise WorkspaceRecoveryError("Recorded artifact is outside its workspace root")
    folded_value = tuple(part.casefold() for part in value_parts[: len(root_parts)])
    folded_root = tuple(part.casefold() for part in root_parts)
    if folded_value != folded_root:
        raise WorkspaceRecoveryError("Recorded artifact is outside its workspace root")
    relative = value_parts[len(root_parts) :]
    if not relative or any(part in {"", ".", ".."} for part in relative):
        raise WorkspaceRecoveryError("Recorded artifact path is not a safe workspace file")
    return _workspace_path(current_root, Path(*relative))


def _manifest_and_outputs(workspace_root: Path) -> tuple[dict[str, Any], list[Path]]:
    manifest_path = workspace_root / "segments" / "segment_manifest.json"
    manifest = _load_object(manifest_path)
    if manifest is None:
        raise WorkspaceRecoveryError(
            "This folder is not a readable prepared 3D-CRT workspace."
        )
    try:
        validate_public_strict_3dcrt_gate(manifest)
    except Exception as exc:
        raise WorkspaceRecoveryError(
            "The prepared 3D-CRT manifest no longer passes the public fixed-field gate."
        ) from exc
    outputs: list[Path] = []
    for segment in active_segments(manifest):
        value = str(segment.get("expected_output_path") or "").strip()
        if not value:
            raise WorkspaceRecoveryError(
                "An active PHITS segment is missing its expected output path."
            )
        output = _workspace_path(workspace_root, value)
        if not output.is_file():
            raise WorkspaceRecoveryError(
                "A required PHITS segment output is missing; PHITS results cannot be reused."
            )
        outputs.append(output)
    if not outputs:
        raise WorkspaceRecoveryError("The workspace has no active PHITS segment outputs.")
    return manifest, outputs


def _digest_evidence_sources(workspace_root: Path) -> list[dict[str, Any]]:
    generation = _load_object(workspace_root / SUMMARY_PATHS["sumtally_generate"])
    execution = _load_object(workspace_root / SUMMARY_PATHS["sumtally_run"])
    preparation = _load_object(workspace_root / SUMMARY_PATHS["rtdose_prepare"])
    candidates = [generation, execution]
    if preparation is not None:
        binding = preparation.get("sumtally_manifest_binding")
        if isinstance(binding, dict):
            candidates.append(
                {
                    **binding,
                    "workspace_root": preparation.get("workspace_root"),
                    "stage_status": "success",
                }
            )
    history_root = workspace_root / "recovery_history"
    if history_root.is_dir():
        for history in sorted(history_root.iterdir(), reverse=True):
            try:
                history.resolve().relative_to(workspace_root.resolve())
            except (OSError, ValueError):
                continue
            if not history.is_dir():
                continue
            for key in ("sumtally_generate", "sumtally_run", "rtdose_prepare"):
                historical = _load_object(history / SUMMARY_PATHS[key])
                if historical is None:
                    continue
                if key == "rtdose_prepare":
                    binding = historical.get("sumtally_manifest_binding")
                    if isinstance(binding, dict):
                        candidates.append(
                            {
                                **binding,
                                "workspace_root": historical.get("workspace_root"),
                                "stage_status": "success",
                            }
                        )
                else:
                    candidates.append(historical)
    return [item for item in candidates if isinstance(item, dict) and _succeeded(item)]


def _validate_phits_digest_evidence(
    workspace_root: Path,
    *,
    manifest: dict[str, Any],
    outputs: list[Path],
) -> dict[str, Any]:
    current_manifest_sha256 = manifest_sha256(manifest)
    expected = {_path_key(path): path for path in outputs}
    for summary in _digest_evidence_sources(workspace_root):
        if summary.get("manifest_sha256") != current_manifest_sha256:
            continue
        recorded = summary.get("segment_output_evidence")
        if not isinstance(recorded, list):
            continue
        current: dict[str, str] = {}
        try:
            for item in recorded:
                if not isinstance(item, dict):
                    raise WorkspaceRecoveryError("Invalid PHITS digest evidence")
                path = rebind_workspace_path(
                    str(item.get("path") or ""),
                    recorded_workspace_root=summary.get("workspace_root"),
                    current_workspace_root=workspace_root,
                )
                digest = str(item.get("sha256") or "")
                if not digest or not path.is_file():
                    raise WorkspaceRecoveryError("Incomplete PHITS digest evidence")
                current[_path_key(path)] = digest
        except WorkspaceRecoveryError:
            continue
        if set(current) != set(expected):
            continue
        if all(file_sha256(expected[key]) == digest for key, digest in current.items()):
            return summary
    raise WorkspaceRecoveryError(
        "Matching SHA-256 evidence for every PHITS segment output is unavailable; "
        "PHITS results cannot be reused safely."
    )


def _current_sumtally_binding(workspace_root: Path) -> dict[str, Any] | None:
    generation = _load_object(workspace_root / SUMMARY_PATHS["sumtally_generate"])
    execution = _load_object(workspace_root / SUMMARY_PATHS["sumtally_run"])
    if not _succeeded(generation) or not _succeeded(execution):
        return None
    assert generation is not None and execution is not None
    if generation.get("workspace_root") not in {None, str(workspace_root.resolve())}:
        return None
    if execution.get("workspace_root") not in {None, str(workspace_root.resolve())}:
        return None
    try:
        from dicomxphits.prepare_rtdose import validate_sumtally_manifest_binding

        return validate_sumtally_manifest_binding(
            workspace_root=workspace_root,
            generation=generation,
            execution=execution,
        )
    except Exception:
        return None


def _prepared_matches(
    workspace_root: Path,
    current_binding: Mapping[str, Any],
) -> bool:
    preparation = _load_object(workspace_root / SUMMARY_PATHS["rtdose_prepare"])
    return bool(
        _succeeded(preparation)
        and isinstance(preparation, dict)
        and isinstance(preparation.get("rtdose_placement"), dict)
        and preparation.get("sumtally_manifest_binding") == current_binding
    )


def _validated_final_output(workspace_root: Path) -> Path | None:
    preparation_path = workspace_root / SUMMARY_PATHS["rtdose_prepare"]
    execution = _load_object(workspace_root / SUMMARY_PATHS["rtdose_run"])
    if not _succeeded(execution) or execution is None or not preparation_path.is_file():
        return None
    if not isinstance(execution.get("coordinate_placement_validation"), dict):
        return None
    if execution["coordinate_placement_validation"].get("validated") is not True:
        return None
    semantic_validation = execution.get("final_semantic_validation")
    coordinate_correction = execution.get("coordinate_correction")
    invariants = (
        coordinate_correction.get("invariants")
        if isinstance(coordinate_correction, dict)
        else None
    )
    if (
        not isinstance(semantic_validation, dict)
        or semantic_validation.get("validated") is not True
        or not isinstance(coordinate_correction, dict)
        or coordinate_correction.get("schema_version")
        != COORDINATE_CORRECTION_SCHEMA_VERSION
        or coordinate_correction.get("axis_mapping")
        != COORDINATE_CORRECTION_AXIS_MAPPING
        or not isinstance(invariants, dict)
        or invariants.get("stored_value_multiset_preserved") is not True
        or invariants.get("iec_x_to_dicom_x_reversal_applied") is not True
        or execution.get("coordinate_corrected_rtdose_output_exists") is not True
    ):
        return None
    if execution.get("rtdose_prepare_summary_sha256") != file_sha256(preparation_path):
        return None
    try:
        output = rebind_workspace_path(
            str(execution.get("coordinate_corrected_rtdose_output") or ""),
            recorded_workspace_root=execution.get("workspace_root"),
            current_workspace_root=workspace_root,
        )
    except WorkspaceRecoveryError:
        return None
    relative_value = str(
        execution.get("coordinate_corrected_rtdose_output_relative") or ""
    )
    recorded_sha256 = str(
        execution.get("coordinate_corrected_rtdose_output_sha256") or ""
    )
    try:
        relative_output = _workspace_path(workspace_root, relative_value)
    except WorkspaceRecoveryError:
        return None
    if relative_output != output or not recorded_sha256:
        return None
    if not output.is_file() or output.suffix.lower() != ".dcm":
        return None
    return output if file_sha256(output) == recorded_sha256 else None


def inspect_existing_workspace(workspace_root: Path) -> WorkspaceRecoveryInspection:
    root = workspace_root.expanduser().resolve()
    if not root.is_dir():
        return WorkspaceRecoveryInspection(
            root,
            RECOVERY_INVALID,
            "None",
            None,
            (),
            "The selected existing 3D-CRT workspace folder does not exist.",
            False,
        )
    try:
        manifest, outputs = _manifest_and_outputs(root)
        segment_summary = _load_object(root / SUMMARY_PATHS["segments"])
        if not _succeeded(segment_summary):
            raise WorkspaceRecoveryError(
                "PHITS execution evidence is missing or unsuccessful; PHITS results cannot be reused."
            )
        _validate_phits_digest_evidence(root, manifest=manifest, outputs=outputs)
    except WorkspaceRecoveryError as exc:
        return WorkspaceRecoveryInspection(
            root,
            RECOVERY_INVALID,
            "Workspace prepared",
            None,
            (),
            str(exc),
            False,
        )

    current_sumtally = _current_sumtally_binding(root)
    if current_sumtally is not None and _prepared_matches(root, current_sumtally):
        final_output = _validated_final_output(root)
        if final_output is not None:
            return WorkspaceRecoveryInspection(
                root,
                RECOVERY_COMPLETE,
                "DICOM RT Dose completed",
                None,
                (),
                "The current coordinate-corrected DICOM RT Dose is available.",
                True,
                final_output,
            )
        return WorkspaceRecoveryInspection(
            root,
            RECOVERY_READY,
            "RTDOSE prepared",
            "run_rtdose",
            RTDOSE_RUN_SEQUENCE,
            "PHITS and Sumtally results are verified. RTDOSE conversion can continue.",
            True,
        )
    if current_sumtally is not None:
        return WorkspaceRecoveryInspection(
            root,
            RECOVERY_READY,
            "Sumtally completed",
            "prepare_rtdose",
            RTDOSE_SEQUENCE,
            "PHITS and Sumtally results are verified. RTDOSE inputs will be rebuilt.",
            True,
        )
    return WorkspaceRecoveryInspection(
        root,
        RECOVERY_READY,
        "PHITS completed",
        "generate_sumtally",
        FULL_DOWNSTREAM_SEQUENCE,
        "PHITS results are verified. Incomplete Sumtally and RTDOSE evidence can be rebuilt without rerunning PHITS.",
        True,
    )


def standard_ct2phits_handoff(
    workspace_root: Path,
    *,
    rtphits_root: Path,
) -> dict[str, str] | None:
    name = workspace_root.name
    if not name.casefold().endswith("-3dcrt"):
        return None
    candidate_name = name[: -len("-3dcrt")] + "-ct2phits"
    validated_root = rtphits_root.expanduser().resolve()
    candidate = (validated_root / "work" / candidate_name).resolve()
    try:
        candidate.relative_to(validated_root)
    except ValueError:
        return None
    summary = _load_object(candidate / "ct2phits_execution_summary.json")
    if not summary or summary.get("status") != "completed":
        return None
    handoff = {
        "rtplan_path": candidate / "RTPLAN.dcm",
        "ct_reference_dicom": candidate / "CT" / "CT000001.dcm",
        "ct_datfiles_root": candidate / "DATfiles",
    }
    if not handoff["rtplan_path"].is_file():
        return None
    if not handoff["ct_reference_dicom"].is_file():
        return None
    if not handoff["ct_datfiles_root"].is_dir():
        return None
    return {key: str(path.resolve()) for key, path in handoff.items()}


def _recovery_conflicts(
    workspace_root: Path,
    stage_sequence: tuple[str, ...],
) -> list[Path]:
    conflicts: list[Path] = []
    if stage_sequence == FULL_DOWNSTREAM_SEQUENCE:
        conflicts.extend((workspace_root / "sumtally", workspace_root / "rtdose"))
        conflicts.extend(workspace_root / path for key, path in SUMMARY_PATHS.items() if key != "segments")
    elif stage_sequence == RTDOSE_SEQUENCE:
        conflicts.append(workspace_root / "rtdose")
        conflicts.extend(
            workspace_root / SUMMARY_PATHS[key]
            for key in ("rtdose_prepare", "rtdose_run")
        )
        sumtally = workspace_root / "sumtally"
        if sumtally.is_dir():
            conflicts.extend(
                path
                for path in sumtally.iterdir()
                if path.is_file() and (path.suffix.lower() == ".dcm" or ".fixed." in path.name)
            )
    elif stage_sequence == RTDOSE_RUN_SEQUENCE:
        conflicts.append(workspace_root / SUMMARY_PATHS["rtdose_run"])
        conflicts.extend(
            (
                workspace_root / "rtdose" / "phits2dicom_stdout.txt",
                workspace_root / "rtdose" / "phits2dicom_stderr.txt",
            )
        )
        for folder in (
            workspace_root / "sumtally",
            workspace_root / "rtdose" / "DATfiles",
        ):
            if not folder.is_dir():
                continue
            conflicts.extend(
                path
                for path in folder.iterdir()
                if path.is_file()
                and (
                    path.suffix.lower() == ".dcm"
                    or ".fixed." in path.name
                )
            )
    existing = [path for path in conflicts if os.path.lexists(path)]
    existing.sort(key=lambda path: len(path.parts))
    selected: list[Path] = []
    for path in existing:
        if any(parent == path or parent in path.parents for parent in selected):
            continue
        selected.append(path)
    return selected


def _copy_history_item(
    source: Path,
    *,
    workspace_root: Path,
    history_root: Path,
    guard: WorkspaceOutputGuard,
    records: list[dict[str, Any]],
) -> None:
    guard.prepare(source)
    relative = source.resolve().relative_to(workspace_root.resolve())
    if source.is_file():
        destination = history_root / relative
        guard.copy_file(source, destination, overwrite=False)
        source_size = source.stat().st_size
        source_sha256 = file_sha256(source)
        if destination.stat().st_size != source_size or file_sha256(destination) != source_sha256:
            raise WorkspaceRecoveryError(
                f"Recovery history copy did not match its source: {relative}"
            )
        records.append(
            {
                "original_relative_path": relative.as_posix(),
                "preserved_relative_path": destination.relative_to(workspace_root).as_posix(),
                "size": source_size,
                "sha256": source_sha256,
            }
        )
        return
    if not source.is_dir():
        raise WorkspaceRecoveryError(f"Recovery conflict is not a regular file or directory: {source}")
    for directory, directory_names, file_names in os.walk(source, followlinks=False):
        directory_path = Path(directory)
        for name in (*directory_names, *file_names):
            guard.prepare(directory_path / name)
        for name in file_names:
            _copy_history_item(
                directory_path / name,
                workspace_root=workspace_root,
                history_root=history_root,
                guard=guard,
                records=records,
            )


def preserve_downstream_for_recovery(
    workspace_root: Path,
    *,
    stage_sequence: tuple[str, ...],
) -> RecoveryHistory | None:
    root = workspace_root.expanduser().resolve()
    conflicts = _recovery_conflicts(root, stage_sequence)
    if not conflicts:
        return None
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    with WorkspaceOutputGuard(root) as guard:
        history_root = guard.make_staging_directory(
            root / "recovery_history",
            prefix=f"{timestamp}-",
        )
        records: list[dict[str, Any]] = []
        deletion_started = False
        try:
            for source in conflicts:
                _copy_history_item(
                    source,
                    workspace_root=root,
                    history_root=history_root,
                    guard=guard,
                    records=records,
                )
            manifest_path = history_root / "recovery_manifest.json"
            guard.write_json(
                manifest_path,
                {
                    "schema_version": "dicomxphits_workspace_recovery_history_v1",
                    "status": "preserved",
                    "workspace_root": ".",
                    "first_recovery_stage": stage_sequence[0] if stage_sequence else None,
                    "phits_segment_outputs_moved": False,
                    "files": records,
                },
                overwrite=False,
            )
            deletion_started = True
            for record in records:
                original = root / Path(record["original_relative_path"])
                guard.unlink(original)
            for source in conflicts:
                if source.is_dir():
                    guard.rmtree(source)
                elif os.path.lexists(source):
                    guard.unlink(source)
        except Exception:
            if not deletion_started:
                guard.rmtree(history_root, missing_ok=True)
            raise
    return RecoveryHistory(
        history_root,
        manifest_path,
        tuple(history_root / Path(record["original_relative_path"]) for record in records),
    )
