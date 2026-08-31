from __future__ import annotations

import argparse
import json
import math
import os
import re
import shutil
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

from dicomxphits.calculation_config import (
    NormalizedCalculationConfig,
    load_calculation_config,
    public_default_calculation_config,
    require_rendered_3d_mesh,
    validate_rtdose_serialization_preflight,
)
from dicomxphits.ct2phits_datfiles import (
    PreparedCt2PhitsSet,
    prepare_ct2phits_assets,
)
from dicomxphits.machine_config import (
    load_machine_config,
    public_default_machine_config,
)
from dicomxphits.gantry_geometry import (
    CURRENT_GANTRY_GEOMETRY_CONTRACT,
    GANTRY_GEOMETRY_CONTRACT_FIELD,
    bind_current_gantry_geometry_contract,
)
from dicomxphits.prepare_ct_calibration import (
    CtAssetSet,
    render_ct_runtime_input,
    validate_ct_assets,
)
from dicomxphits.public_dose_contract import (
    approved_public_model_calibration,
)
from dicomxphits.public_aperture_guard import (
    PUBLIC_APERTURE_DECISION_FIELD,
    require_v1_effective_apertures,
)
from dicomxphits.public_beam_model import (
    PUBLIC_BEAM_MODEL_EVIDENCE_FIELD,
    validate_public_beam_model,
)
from dicomxphits.rectangular_geometry import build_intermediate_geometry
from dicomxphits.public_spectrum import PUBLIC_SPECTRUM_NAME, PUBLIC_SPECTRUM_TEXT
from dicomxphits.rtplan_state import beam_number, carried_control_point_states
from dicomxphits.safe_output import WorkspaceOutputGuard
from dicomxphits.rtplan_segments import (
    build_manifest,
    dcm_get,
    load_rtplan,
    load_sampling_policy,
    parse_beam_filter,
    write_outputs,
)


DEFAULT_EXPECTED_OUTPUT_NAME = "deposit-target-3D.out"
GEOMETRY_MODE_RECTANGULAR_3DCRT = "rectangular_3dcrt"
GEOMETRY_MODES = (GEOMETRY_MODE_RECTANGULAR_3DCRT,)
RECTANGULAR_PHITS_INPUT_NAME = "phits.inp"
RECTANGULAR_CT_GENERATION_MODE = "rectangular_3dcrt_public_ct_voxel_phits_inputs"
DEFAULT_SEGMENT_MAXCAS = 1_000_000
DEFAULT_SEGMENT_MAXBCH = 10
DEFAULT_SEGMENT_OMP_THREADS = 8


@dataclass(frozen=True)
class ExternalToolPaths:
    phits_root_folder: str
    phits_executable_path: str
    phits2dicom_executable_path: str | None = None


def _repo_root_from_public_module() -> Path:
    return Path(__file__).resolve().parents[4]


def ensure_repo_scripts_on_path(project_root: Path | None = None) -> Path:
    root = (project_root or _repo_root_from_public_module()).resolve()
    scripts_dir = root / "scripts"
    if not scripts_dir.is_dir():
        raise RuntimeError(f"scripts directory not found: {scripts_dir}")
    scripts_text = str(scripts_dir)
    if scripts_text not in sys.path:
        sys.path.insert(0, scripts_text)
    return root


def load_paths_config(path: Path) -> ExternalToolPaths:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError(f"Path config must be a JSON object: {path}")
    return ExternalToolPaths(
        phits_root_folder=str(data.get("phits_root_folder") or ""),
        phits_executable_path=str(data.get("phits_executable_path") or ""),
        phits2dicom_executable_path=(
            str(data.get("phits2dicom_executable_path"))
            if data.get("phits2dicom_executable_path")
            else None
        ),
    )


def merged_tool_paths(
    *,
    paths_config: ExternalToolPaths | None,
    phits_root_folder: str | None,
    phits_executable_path: str | None,
    phits2dicom_executable_path: str | None,
) -> ExternalToolPaths:
    return ExternalToolPaths(
        phits_root_folder=phits_root_folder or (paths_config.phits_root_folder if paths_config else ""),
        phits_executable_path=phits_executable_path or (paths_config.phits_executable_path if paths_config else ""),
        phits2dicom_executable_path=(
            phits2dicom_executable_path
            if phits2dicom_executable_path is not None
            else (paths_config.phits2dicom_executable_path if paths_config else None)
        ),
    )


def require_tool_paths(paths: ExternalToolPaths, *, geometry_mode: str) -> None:
    missing: list[str] = []
    if not paths.phits_root_folder:
        missing.append("phits_root_folder")
    if missing:
        raise ValueError("Missing required external tool path setting(s): " + ", ".join(missing))


def finite_positive(value: Any) -> bool:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return False
    return math.isfinite(number) and number > 0.0


def finite_nonnegative(value: Any) -> bool:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return False
    return math.isfinite(number) and number >= 0.0


def require_positive_integer(value: Any, *, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{label} must be a positive integer")
    return value


def positive_decimal_integer(value: str) -> int:
    if re.fullmatch(r"[0-9]+", value) is None:
        raise argparse.ArgumentTypeError("must be a decimal positive integer")
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be a decimal positive integer")
    return parsed


def active_segments(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    segments = manifest.get("segments")
    if not isinstance(segments, list):
        raise ValueError("segment manifest must contain a segments list")
    return [segment for segment in segments if isinstance(segment, dict) and not segment.get("skip_reason")]


def manifest_segments(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    segments = manifest.get("segments")
    if not isinstance(segments, list):
        raise ValueError("segment manifest must contain a segments list")
    return [segment for segment in segments if isinstance(segment, dict)]


def validate_public_strict_3dcrt_gate(manifest: dict[str, Any]) -> dict[str, Any]:
    active = active_segments(manifest)
    if not active:
        raise ValueError("Strict 3D-CRT gate failed: at least one non-skipped segment is required")

    failures: list[str] = []
    seen_beams: set[Any] = set()
    for index, segment in enumerate(manifest_segments(manifest), start=1):
        beam_key = segment.get("beam_number", f"manifest segment {index}")
        if beam_key in seen_beams:
            continue
        seen_beams.add(beam_key)
        label = str(segment.get("beam_number_label") or f"beam {beam_key}")
        delivery_type = str(segment.get("delivery_type") or "")
        skipped_non_treatment = bool(segment.get("skip_reason")) and delivery_type == "unsupported"
        valid_beam_mu = (
            finite_nonnegative(segment.get("beam_meterset_mu"))
            if skipped_non_treatment
            else finite_positive(segment.get("beam_meterset_mu"))
        )
        if not valid_beam_mu:
            requirement = "nonnegative" if skipped_non_treatment else "positive"
            failures.append(
                f"{label}: beam_meterset_mu must be present, {requirement}, and finite"
            )

    for index, segment in enumerate(active, start=1):
        label = str(segment.get("segment_id") or f"active segment {index}")
        delivery_type = str(segment.get("delivery_type") or "")
        if delivery_type not in {"3dcrt", "3dcrt_static"}:
            failures.append(f"{label}: delivery_type must be 3dcrt_static, got {delivery_type or '<missing>'}")
        if not finite_positive(segment.get("segment_mu")):
            failures.append(f"{label}: segment_mu must be present, positive, and finite")
        if not finite_positive(segment.get("mu_weight")):
            failures.append(f"{label}: mu_weight must be present, positive, and finite")
        if str(segment.get("mu_weight_unit") or "") != "MU":
            failures.append(f"{label}: mu_weight_unit must be MU")

    if failures:
        raise ValueError("Strict 3D-CRT gate failed: " + "; ".join(failures))

    return {
        "status": "passed",
        "active_segment_count": len(active),
        "required_delivery_type": "3dcrt_static",
        "strict_mu_mode": True,
    }


def write_json(path: Path, data: dict[str, Any], *, case_root: Path) -> None:
    with WorkspaceOutputGuard(case_root, create_root=True) as guard:
        guard.write_json(path, data)


def public_relative_path(value: str, *, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{label} must be a non-empty relative path")
    normalized = value.replace("\\", "/")
    if "\n" in normalized or "\r" in normalized:
        raise ValueError(f"{label} must not contain newlines")
    path = PurePosixPath(normalized)
    if path.is_absolute():
        raise ValueError(f"{label} must be relative")
    parts = path.parts
    if not parts or any(part in {"", ".", ".."} for part in parts):
        raise ValueError(f"{label} must not contain empty, '.', or '..' path components")
    if any(":" in part for part in parts):
        raise ValueError(f"{label} must not contain drive or scheme markers")
    return path.as_posix()


def path_inside_workspace(workspace_root: Path, relative_path: str) -> Path:
    root = Path(os.path.abspath(os.fspath(workspace_root)))
    candidate = Path(os.path.abspath(os.fspath(root / relative_path)))
    try:
        candidate.resolve().relative_to(root.resolve())
    except ValueError as exc:
        raise ValueError(f"output path escapes workspace: {relative_path}") from exc
    return candidate


def sanitize_segment_id(value: Any) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError("segment_id must be a non-empty string")
    sanitized = re.sub(r"[^a-z0-9_-]+", "_", value.strip().lower())
    sanitized = re.sub(r"_+", "_", sanitized).strip("_")
    if not sanitized:
        raise ValueError(f"segment_id {value!r} has no public-safe characters")
    return sanitized


def write_libpath(case_root: Path, *, phits_root_folder: str) -> Path:
    path = case_root / "libpath.inp"
    portable_root = phits_root_folder.replace("\\", "/")
    with WorkspaceOutputGuard(case_root, create_root=True) as guard:
        guard.write_text(
            path,
            f"file(1)  = {portable_root} # PHITS install folder name\n",
        )
    return path


def export_segment_manifest(
    *,
    rtplan_path: Path,
    case_root: Path,
    case_id: str | None,
    workflow_mode: str,
    expected_output_name: str,
) -> tuple[dict[str, Any], Path]:
    ds = load_rtplan(rtplan_path)
    resolved_case_id = case_id or str(dcm_get(ds, "RTPlanLabel", "") or rtplan_path.stem)
    sampling_policy, sampling_config_path = load_sampling_policy(None)
    manifest, beam_rows, cp_rows = build_manifest(
        ds,
        case_id=resolved_case_id,
        workflow_mode=workflow_mode,
        include_beams=parse_beam_filter(None),
        dose_normalization_mu=None,
        output_name=expected_output_name,
        sampling_policy=sampling_policy,
        sampling_config_path=sampling_config_path,
    )
    validate_public_strict_3dcrt_gate(manifest)
    included_beam_numbers = tuple(
        dict.fromkeys(
            int(segment["beam_number"])
            for segment in active_segments(manifest)
        )
    )
    manifest[PUBLIC_BEAM_MODEL_EVIDENCE_FIELD] = validate_public_beam_model(
        ds,
        included_beam_numbers=included_beam_numbers,
    )
    manifest[PUBLIC_APERTURE_DECISION_FIELD] = require_v1_effective_apertures(
        [
            (beam_number(beam), carried_control_point_states(beam))
            for beam in dcm_get(ds, "BeamSequence", []) or []
        ]
    )
    bind_current_gantry_geometry_contract(manifest)
    write_outputs(case_root, manifest, beam_rows, cp_rows)
    return manifest, case_root / "segments" / "segment_manifest.json"


def validate_geometry_mode_args(*, geometry_mode: str, machine_config_path: Path | None) -> None:
    if geometry_mode not in GEOMETRY_MODES:
        raise ValueError(f"geometry_mode must be one of: {', '.join(GEOMETRY_MODES)}")


def rectangular_phits_input_path(sanitized_segment_id: str) -> str:
    return PurePosixPath("segments", sanitized_segment_id, RECTANGULAR_PHITS_INPUT_NAME).as_posix()


def preflight_rectangular_segments(
    *,
    manifest: dict[str, Any],
    case_root: Path,
) -> list[dict[str, Any]]:
    active = active_segments(manifest)
    if not active:
        raise ValueError("rectangular_3dcrt requires at least one active segment")

    seen_ids: dict[str, str] = {}
    prepared: list[dict[str, Any]] = []
    for index, segment in enumerate(active, start=1):
        raw_segment_id = segment.get("segment_id")
        sanitized_id = sanitize_segment_id(raw_segment_id)
        if sanitized_id in seen_ids:
            raise ValueError(
                "duplicate sanitized segment_id "
                f"{sanitized_id!r}: {seen_ids[sanitized_id]!r} and {raw_segment_id!r}"
            )
        seen_ids[sanitized_id] = str(raw_segment_id)

        input_path = rectangular_phits_input_path(sanitized_id)
        expected_output = public_relative_path(
            str(segment.get("expected_output_path") or ""),
            label=f"{raw_segment_id or f'active segment {index}'} expected_output_path",
        )
        final_input_path = path_inside_workspace(case_root, input_path)
        path_inside_workspace(case_root, expected_output)
        if final_input_path.exists():
            raise ValueError(f"refusing to overwrite existing PHITS input: {input_path}")

        prepared_segment = dict(segment)
        prepared_segment["_public_sanitized_segment_id"] = sanitized_id
        prepared_segment["_public_phits_input_path"] = input_path
        prepared_segment["_public_expected_output_path"] = expected_output
        prepared_segment["_public_final_input_path"] = final_input_path
        prepared.append(prepared_segment)
    return prepared


def _copy_to_new_file_or_fail(
    source: Path,
    destination: Path,
    *,
    guard: WorkspaceOutputGuard,
) -> None:
    try:
        guard.copy_file(source, destination, overwrite=False)
    except FileExistsError as exc:
        raise ValueError(
            f"refusing to overwrite existing PHITS input: {destination}"
        ) from exc


def write_rectangular_phits_inputs_atomically(
    *,
    case_root: Path,
    rendered_inputs: list[tuple[dict[str, Any], str]],
) -> None:
    with WorkspaceOutputGuard(case_root, create_root=True) as guard:
        staging_root = guard.make_staging_directory(
            case_root / "analysis",
            prefix=".rectangular_phits_staging-",
        )

        linked_paths: list[Path] = []
        try:
            staged_paths: list[tuple[Path, Path]] = []
            for index, (segment, rendered_text) in enumerate(rendered_inputs, start=1):
                staged_path = staging_root / f"{index:06d}.inp"
                guard.write_text(staged_path, rendered_text, overwrite=False)
                staged_paths.append((staged_path, segment["_public_final_input_path"]))

            for _staged_path, final_path in staged_paths:
                guard.prepare(final_path, create_parents=True)

            for staged_path, final_path in staged_paths:
                _copy_to_new_file_or_fail(staged_path, final_path, guard=guard)
                linked_paths.append(final_path)
        except Exception:
            for path in linked_paths:
                guard.unlink(path, missing_ok=True)
            raise
        finally:
            guard.rmtree(staging_root, missing_ok=True)


def write_ct_rectangular_phits_inputs_atomically(
    *,
    case_root: Path,
    rendered_inputs: list[tuple[dict[str, Any], str]],
    asset_set: CtAssetSet,
) -> None:
    with WorkspaceOutputGuard(case_root, create_root=True) as guard:
        staging_root = guard.make_staging_directory(
            case_root / "analysis",
            prefix=".rectangular_ct_phits_staging-",
        )

        linked_paths: list[Path] = []
        try:
            staged_paths: list[tuple[Path, Path]] = []
            for name, source in asset_set.files.items():
                final_path = case_root / name
                guard.prepare(final_path)
                if final_path.exists():
                    raise ValueError(f"refusing to overwrite existing CT asset: {name}")
                staged_path = staging_root / name
                guard.write_bytes(staged_path, source.read_bytes(), overwrite=False)
                staged_paths.append((staged_path, final_path))

            spectrum_final = case_root / PUBLIC_SPECTRUM_NAME
            guard.prepare(spectrum_final)
            if spectrum_final.exists():
                raise ValueError(
                    f"refusing to overwrite existing public spectrum: {PUBLIC_SPECTRUM_NAME}"
                )
            spectrum_staged = staging_root / PUBLIC_SPECTRUM_NAME
            guard.write_text(spectrum_staged, PUBLIC_SPECTRUM_TEXT, overwrite=False)
            staged_paths.append((spectrum_staged, spectrum_final))

            for index, (segment, rendered_text) in enumerate(rendered_inputs, start=1):
                staged_path = staging_root / f"{index:06d}.inp"
                guard.write_text(staged_path, rendered_text, overwrite=False)
                final_path = segment["_public_final_input_path"]
                guard.prepare(final_path, create_parents=True)
                staged_paths.append((staged_path, final_path))

            for staged_path, final_path in staged_paths:
                _copy_to_new_file_or_fail(staged_path, final_path, guard=guard)
                linked_paths.append(final_path)
        except Exception:
            for path in linked_paths:
                guard.unlink(path, missing_ok=True)
            raise
        finally:
            guard.rmtree(staging_root, missing_ok=True)


def persist_rectangular_manifest_paths(
    *,
    manifest: dict[str, Any],
    prepared_segments: list[dict[str, Any]],
    manifest_path: Path,
    calculation_geometry_sha256: str,
    calculation_tally_geometry_sha256: str,
) -> None:
    active = active_segments(manifest)
    if len(active) != len(prepared_segments):
        raise ValueError("rectangular manifest path persistence lost active segment alignment")
    for segment, prepared_segment in zip(active, prepared_segments):
        segment["phits_input_path"] = prepared_segment["_public_phits_input_path"]
        segment["expected_output_path"] = prepared_segment["_public_expected_output_path"]
        segment["calculation_geometry_sha256"] = calculation_geometry_sha256
        segment["calculation_tally_geometry_sha256"] = (
            calculation_tally_geometry_sha256
        )
    write_json(manifest_path, manifest, case_root=manifest_path.parents[1])


def generate_rectangular_phits_workspace(
    *,
    manifest: dict[str, Any],
    case_root: Path,
    machine_config_path: Path | None,
    manifest_path: Path | None = None,
    apply_approved_totfact: bool = True,
    ct_asset_root: Path | None = None,
    confirmed_non_patient_phantom: bool = False,
    ct_preparation: PreparedCt2PhitsSet | None = None,
    maxcas: int = DEFAULT_SEGMENT_MAXCAS,
    maxbch: int = DEFAULT_SEGMENT_MAXBCH,
    omp_threads: int = DEFAULT_SEGMENT_OMP_THREADS,
    calculation_config: NormalizedCalculationConfig | None = None,
    calculation_rtdose_preflight: dict[str, Any] | None = None,
) -> dict[str, Any]:
    bind_current_gantry_geometry_contract(manifest)
    maxcas = require_positive_integer(maxcas, label="maxcas")
    maxbch = require_positive_integer(maxbch, label="maxbch")
    omp_threads = require_positive_integer(omp_threads, label="omp_threads")
    effective_calculation_config = (
        calculation_config or public_default_calculation_config()
    )
    if machine_config_path is None:
        machine_config = public_default_machine_config()
        machine_config_source = "built_in_public_default"
    else:
        machine_config = load_machine_config(machine_config_path)
        machine_config_source = "user_supplied"
    calibration = (
        approved_public_model_calibration(
            machine_config,
            transport_geometry_contract=CURRENT_GANTRY_GEOMETRY_CONTRACT,
        )
        if apply_approved_totfact
        else None
    )
    prepared_segments = preflight_rectangular_segments(manifest=manifest, case_root=case_root)

    geometries = [
        build_intermediate_geometry(segment, machine_config)
        for segment in prepared_segments
    ]
    if ct_asset_root is None:
        raise ValueError("rectangular_3dcrt requires validated CT2PHITS assets")
    asset_set = validate_ct_assets(
        ct_asset_root,
        confirmed_non_patient_phantom=confirmed_non_patient_phantom,
    )
    rendered_inputs = []
    for segment, geometry in zip(prepared_segments, geometries):
        output_3d = segment["_public_expected_output_path"]
        output_parent = PurePosixPath(output_3d).parent
        output_pdd = (output_parent / "deposit-pdd.out").as_posix()
        rendered_inputs.append(
            (
                segment,
                render_ct_runtime_input(
                    geometry,
                    voxel_counts=asset_set.voxel_counts,
                    output_3d=output_3d,
                    output_pdd=output_pdd,
                    totfact_per_mu=(
                        calibration["totfact_per_mu"]
                        if calibration is not None
                        else None
                    ),
                    maxcas_per_batch=maxcas,
                    batches=maxbch,
                    omp_threads=omp_threads,
                    calculation_config=(
                        effective_calculation_config
                        if effective_calculation_config.source == "user_supplied"
                        else None
                    ),
                ),
            )
        )
    for _segment, rendered_text in rendered_inputs:
        require_rendered_3d_mesh(rendered_text, effective_calculation_config)
    generation_mode = RECTANGULAR_CT_GENERATION_MODE
    write_ct_rectangular_phits_inputs_atomically(
        case_root=case_root,
        rendered_inputs=rendered_inputs,
        asset_set=asset_set,
    )
    if manifest_path is not None:
        persist_rectangular_manifest_paths(
            manifest=manifest,
            prepared_segments=prepared_segments,
            manifest_path=manifest_path,
            calculation_geometry_sha256=(
                effective_calculation_config.semantic_sha256
            ),
            calculation_tally_geometry_sha256=(
                effective_calculation_config.tally_geometry_sha256()
            ),
        )

    summary = {
        "case_id": manifest.get("case_id"),
        "workflow_mode": manifest.get("workflow_mode"),
        "generated_segment_count": len(prepared_segments),
        "geometry_mode": GEOMETRY_MODE_RECTANGULAR_3DCRT,
        "generation_mode": generation_mode,
        GANTRY_GEOMETRY_CONTRACT_FIELD: CURRENT_GANTRY_GEOMETRY_CONTRACT,
        "machine_config_source": machine_config_source,
        "calculation_config": effective_calculation_config.evidence(
            rtdose_preflight=calculation_rtdose_preflight,
        ),
        "segment_runtime": {
            "maxcas": maxcas,
            "maxbch": maxbch,
            "omp_threads": omp_threads,
            "omp_directive": f"$OMP = {omp_threads}",
        },
        "absolute_dose_calibration": (
            calibration
            if calibration is not None
            else {
                "status": "not_applied",
                "totfact_per_mu": None,
            }
        ),
        "manifest_is_canonical": True,
        "ct_voxel_assets": (
            {
                "status": "validated_and_copied",
                "source_contract": (
                    "raw_ct2phits_datfiles_plus_ct_reference"
                    if ct_preparation is not None
                    else "prepared_assets"
                ),
                "voxel_counts": list(asset_set.voxel_counts),
                "asset_sha256": dict(asset_set.sha256),
                "raw_datfiles_sha256": (
                    dict(ct_preparation.raw_sha256)
                    if ct_preparation is not None
                    else None
                ),
                "ct_origin_dicom_cm": (
                    list(ct_preparation.ct_origin_dicom_cm)
                    if ct_preparation is not None
                    else None
                ),
                "rtplan_isocenter_dicom_cm": (
                    list(ct_preparation.rtplan_isocenter_dicom_cm)
                    if ct_preparation is not None
                    else None
                ),
                "ct_shift_iec_cm": (
                    list(ct_preparation.ct_shift_iec_cm)
                    if ct_preparation is not None
                    else None
                ),
                "frame_of_reference_match": (
                    True if ct_preparation is not None else None
                ),
                "ct_slice_count": (
                    ct_preparation.ct_slice_count
                    if ct_preparation is not None
                    else None
                ),
                "confirmed_non_patient_phantom": True,
            }
            if asset_set is not None
            else {
                "status": "not_supplied_legacy_smoke_only",
                "confirmed_non_patient_phantom": False,
            }
        ),
        "generated_phits_inputs": [segment["_public_phits_input_path"] for segment in prepared_segments],
        "expected_output_paths": [segment["_public_expected_output_path"] for segment in prepared_segments],
        "segment_ids": [segment["_public_sanitized_segment_id"] for segment in prepared_segments],
        "input_generation_note": (
            "Complete public CT-voxel PHITS input preparation; no PHITS execution performed."
            if asset_set is not None
            else "Legacy geometry-rendering smoke integration only; not a release runtime."
        ),
        "phits_execution_performed": False,
        "phits2dicom_performed": False,
        "gpr_comparing_performed": False,
    }
    write_json(
        case_root / "analysis" / "phits_generation_summary.json",
        summary,
        case_root=case_root,
    )
    return summary


def prepare_public_3dcrt_workspace(
    *,
    rtplan_path: Path,
    workspace_root: Path,
    paths: ExternalToolPaths,
    case_id: str | None = None,
    workflow_mode: str = "full_plan",
    expected_output_name: str = DEFAULT_EXPECTED_OUTPUT_NAME,
    geometry_mode: str = GEOMETRY_MODE_RECTANGULAR_3DCRT,
    machine_config_path: Path | None = None,
    calculation_config_path: Path | None = None,
    apply_approved_totfact: bool = True,
    ct_datfiles_root: Path | None = None,
    ct_reference_dicom: Path | None = None,
    confirmed_non_patient_phantom: bool = False,
    maxcas: int = DEFAULT_SEGMENT_MAXCAS,
    maxbch: int = DEFAULT_SEGMENT_MAXBCH,
    omp_threads: int = DEFAULT_SEGMENT_OMP_THREADS,
) -> dict[str, Any]:
    maxcas = require_positive_integer(maxcas, label="maxcas")
    maxbch = require_positive_integer(maxbch, label="maxbch")
    omp_threads = require_positive_integer(omp_threads, label="omp_threads")
    validate_geometry_mode_args(geometry_mode=geometry_mode, machine_config_path=machine_config_path)
    require_tool_paths(paths, geometry_mode=geometry_mode)
    calculation_config = (
        public_default_calculation_config()
        if calculation_config_path is None
        else load_calculation_config(calculation_config_path)
    )
    if geometry_mode == GEOMETRY_MODE_RECTANGULAR_3DCRT:
        if ct_datfiles_root is None:
            raise ValueError(
                "rectangular_3dcrt requires --ct-datfiles-root with raw CT2PHITS DATfiles"
            )
        if ct_reference_dicom is None:
            raise ValueError(
                "rectangular_3dcrt requires --ct-reference-dicom from the same "
                "non-patient phantom CT series"
            )
        if not confirmed_non_patient_phantom:
            raise ValueError(
                "rectangular_3dcrt requires explicit non-patient phantom confirmation"
            )
        preflight_machine_config = (
            public_default_machine_config()
            if machine_config_path is None
            else load_machine_config(machine_config_path)
        )
        if apply_approved_totfact:
            approved_public_model_calibration(
                preflight_machine_config,
                transport_geometry_contract=CURRENT_GANTRY_GEOMETRY_CONTRACT,
            )

    with tempfile.TemporaryDirectory(prefix="dicomxphits-ct-assets-") as temp_dir:
        ct_preparation = prepare_ct2phits_assets(
            raw_datfiles_root=ct_datfiles_root,
            ct_reference_dicom=ct_reference_dicom,
            rtplan_path=rtplan_path,
            output_root=Path(temp_dir) / "prepared",
            confirmed_non_patient_phantom=confirmed_non_patient_phantom,
        )
        calculation_rtdose_preflight = validate_rtdose_serialization_preflight(
            calculation_config,
            rtplan_isocenter_dicom_mm=tuple(
                value * 10.0
                for value in ct_preparation.rtplan_isocenter_dicom_cm
            ),
        )
        manifest, manifest_path = export_segment_manifest(
            rtplan_path=rtplan_path,
            case_root=workspace_root,
            case_id=case_id,
            workflow_mode=workflow_mode,
            expected_output_name=expected_output_name,
        )
        gate_summary = validate_public_strict_3dcrt_gate(manifest)
        libpath_path = write_libpath(
            workspace_root,
            phits_root_folder=paths.phits_root_folder,
        )
        phits_summary = generate_rectangular_phits_workspace(
            manifest=manifest,
            case_root=workspace_root,
            machine_config_path=machine_config_path,
            manifest_path=manifest_path,
            apply_approved_totfact=apply_approved_totfact,
            ct_asset_root=ct_preparation.assets.root,
            confirmed_non_patient_phantom=True,
            ct_preparation=ct_preparation,
            maxcas=maxcas,
            maxbch=maxbch,
            omp_threads=omp_threads,
            calculation_config=calculation_config,
            calculation_rtdose_preflight=calculation_rtdose_preflight,
        )
    rtplan_summary_path = rtplan_path.name
    workspace_summary_path = "."
    output_paths = {
        "segment_manifest": public_relative_path(
            str(manifest_path.relative_to(workspace_root)),
            label="segment_manifest",
        ),
        "libpath": public_relative_path(str(libpath_path.relative_to(workspace_root)), label="libpath"),
        "phits_generation_summary": "analysis/phits_generation_summary.json",
        "workspace_summary": "analysis/public_preparation_workspace_summary.json",
    }

    summary = {
        "schema_version": "dicomxphits_public_prepare_3dcrt_workspace_v1",
        "stage": "prepare_3dcrt_workspace",
        "rtplan_path": rtplan_summary_path,
        "workspace_root": workspace_summary_path,
        "geometry_mode": geometry_mode,
        "command": {
            "argv": sys.argv,
            "note": "Adapter stage summary; no PHITS execution is performed in this stage.",
        },
        "returncode": 0,
        "stdout_path": None,
        "stderr_path": None,
        "outputs": output_paths,
        "path_config": {
            "phits_root_folder": paths.phits_root_folder,
            "phits_executable_path": paths.phits_executable_path,
            "phits2dicom_executable_path": paths.phits2dicom_executable_path,
        },
        "strict_gate": gate_summary,
        PUBLIC_BEAM_MODEL_EVIDENCE_FIELD: manifest[
            PUBLIC_BEAM_MODEL_EVIDENCE_FIELD
        ],
        "segment_runtime": {
            "maxcas": maxcas,
            "maxbch": maxbch,
            "omp_threads": omp_threads,
            "omp_directive": f"$OMP = {omp_threads}",
        },
        "calculation_config": phits_summary["calculation_config"],
        "phits_generation": phits_summary,
        "phits_execution_performed": False,
    }
    summary_path = workspace_root / "analysis" / "public_preparation_workspace_summary.json"
    write_json(summary_path, summary, case_root=workspace_root)
    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Prepare a public dicomxphits strict 3D-CRT segment manifest and PHITS workspace."
    )
    parser.add_argument("--rtplan", required=True, help="Input RT Plan DICOM path")
    parser.add_argument("--workspace-root", required=True, help="Output workspace root")
    parser.add_argument("--case-id", default=None)
    parser.add_argument("--workflow-mode", choices=("full_plan", "selected_beam", "dry_run"), default="full_plan")
    parser.add_argument("--expected-output-name", default=DEFAULT_EXPECTED_OUTPUT_NAME)
    parser.add_argument("--paths-json", default=None, help="External path config JSON")
    parser.add_argument("--phits-root-folder", default=None)
    parser.add_argument("--phits-executable-path", default=None)
    parser.add_argument("--phits2dicom-executable-path", default=None)
    parser.add_argument(
        "--maxcas",
        type=positive_decimal_integer,
        default=DEFAULT_SEGMENT_MAXCAS,
        help="Positive histories per batch for generated segment inputs",
    )
    parser.add_argument(
        "--maxbch",
        type=positive_decimal_integer,
        default=DEFAULT_SEGMENT_MAXBCH,
        help="Positive batch count for generated segment inputs",
    )
    parser.add_argument(
        "--omp-threads",
        type=positive_decimal_integer,
        default=DEFAULT_SEGMENT_OMP_THREADS,
        help="Positive OpenMP thread count for generated segment inputs",
    )
    parser.add_argument(
        "--geometry-mode",
        choices=GEOMETRY_MODES,
        default=GEOMETRY_MODE_RECTANGULAR_3DCRT,
    )
    parser.add_argument("--machine-config-path", default=None)
    parser.add_argument("--calculation-config-path", default=None)
    parser.add_argument(
        "--ct-datfiles-root",
        default=None,
        help="Directory containing the raw files emitted by ct2phits.exe",
    )
    parser.add_argument(
        "--ct-reference-dicom",
        default=None,
        help=(
            "One CT DICOM slice from the same non-patient phantom series; "
            "its directory is scanned to determine the CT origin"
        ),
    )
    parser.add_argument(
        "--confirm-non-patient-phantom",
        action="store_true",
        help=(
            "Confirm that the CT2PHITS DATfiles and CT reference come from "
            "non-patient phantom data"
        ),
    )
    parser.add_argument(
        "--relative-dose-only",
        action="store_true",
        help=(
            "Do not apply the approved public-model totfact. Required for a "
            "changed research machine config unless it has its own calibration."
        ),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        paths_config = load_paths_config(Path(args.paths_json)) if args.paths_json else None
        paths = merged_tool_paths(
            paths_config=paths_config,
            phits_root_folder=args.phits_root_folder,
            phits_executable_path=args.phits_executable_path,
            phits2dicom_executable_path=args.phits2dicom_executable_path,
        )
        summary = prepare_public_3dcrt_workspace(
            rtplan_path=Path(args.rtplan),
            workspace_root=Path(args.workspace_root),
            paths=paths,
            case_id=args.case_id,
            workflow_mode=args.workflow_mode,
            expected_output_name=args.expected_output_name,
            geometry_mode=args.geometry_mode,
            machine_config_path=Path(args.machine_config_path) if args.machine_config_path else None,
            calculation_config_path=(
                Path(args.calculation_config_path)
                if args.calculation_config_path
                else None
            ),
            apply_approved_totfact=not args.relative_dose_only,
            ct_datfiles_root=(
                Path(args.ct_datfiles_root)
                if args.ct_datfiles_root
                else None
            ),
            ct_reference_dicom=(
                Path(args.ct_reference_dicom)
                if args.ct_reference_dicom
                else None
            ),
            confirmed_non_patient_phantom=args.confirm_non_patient_phantom,
            maxcas=args.maxcas,
            maxbch=args.maxbch,
            omp_threads=args.omp_threads,
        )
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(summary["outputs"]["workspace_summary"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
