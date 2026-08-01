from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

import pydicom
from pydicom.misc import is_dicom

from dicomxphits.ct2phits_datfiles import (
    RAW_CT2PHITS_NAMES,
    Ct2PhitsDatfilesError,
    _ct_series_origin,
    _finite_vector,
    _require_axial_hfs_ct,
    _rtplan_isocenter,
    prepare_ct2phits_assets,
    validate_raw_ct2phits_datfiles,
)
from dicomxphits.prepare_ct_calibration import CtCalibrationError


CT2PHITS_GENERATED_NAMES = (*RAW_CT2PHITS_NAMES, "CTtrans.dat")
CT2PHITS_INPUT_NAME = "ct2phits.inp"
CT2PHITS_MANIFEST_NAME = "ct2phits_workspace_manifest.json"
CT2PHITS_SUMMARY_NAME = "ct2phits_execution_summary.json"
CT2PHITS_BATCH_NAME = "RTphits_win.bat"
CT2PHITS_TABLE_RELATIVE = Path("data") / "HumanVoxelTable.data"
CT2PHITS_COARSE_GRAINING = (8, 8, 2)
CT_SLICE_SPACING_TOLERANCE_MM = 1.0e-6
RTPLAN_SNAPSHOT_NAME = "RTPLAN.dcm"
PROCESS_TREE_TERMINATION_TIMEOUT_SECONDS = 10.0


class Ct2PhitsFrontendError(ValueError):
    """Raised when the CT2PHITS frontend cannot complete safely."""


@dataclass(frozen=True)
class SelectedCtSeries:
    source_root: Path
    series_instance_uid: str
    frame_of_reference_uid: str
    files: tuple[Path, ...]
    rows: int
    columns: int


@dataclass(frozen=True)
class Ct2PhitsFrontendResult:
    workspace_root: Path
    datfiles_root: Path
    ct_reference_dicom: Path
    prepared_assets_root: Path
    manifest_path: Path
    summary_path: Path


Runner = Callable[
    [Sequence[str], Path, float],
    subprocess.CompletedProcess[str],
]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _copy_stable_ct_slice(source: Path, destination: Path) -> str:
    try:
        source_sha256_before = _sha256(source)
        shutil.copyfile(source, destination)
        snapshot_sha256 = _sha256(destination)
        source_sha256_after = _sha256(source)
    except OSError as exc:
        raise Ct2PhitsFrontendError(
            f"could not create stable CT DICOM snapshot: {source.name}"
        ) from exc
    if not (
        source_sha256_before == snapshot_sha256 == source_sha256_after
    ):
        raise Ct2PhitsFrontendError(
            f"CT DICOM changed while creating the workspace snapshot: {source.name}"
        )
    return snapshot_sha256


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _is_within_dicomxphits_repository(path: Path) -> bool:
    for candidate in (path, *path.parents):
        if (candidate / "pyproject.toml").is_file() and (
            candidate / "src" / "dicomxphits"
        ).is_dir():
            return True
    return False


def _read_ct_header(path: Path) -> Any | None:
    try:
        return pydicom.dcmread(
            str(path),
            stop_before_pixels=True,
            force=False,
            specific_tags=[
                "Modality",
                "PatientPosition",
                "ImageOrientationPatient",
                "ImagePositionPatient",
                "FrameOfReferenceUID",
                "SeriesInstanceUID",
                "Rows",
                "Columns",
            ],
        )
    except Exception:
        return None


def _is_dicom_or_ct_candidate(path: Path) -> bool:
    name = path.name.upper()
    ct_named = name == "CT" or name.startswith(("CT.", "CT_", "CT-"))
    return path.suffix.lower() == ".dcm" or ct_named or is_dicom(str(path))


def select_ct_series(
    ct_dicom_root: Path,
    *,
    series_instance_uid: str | None = None,
) -> SelectedCtSeries:
    root = ct_dicom_root.resolve()
    if not root.is_dir():
        raise Ct2PhitsFrontendError(
            f"CT DICOM input directory does not exist: {ct_dicom_root}"
        )

    series: dict[str, list[tuple[Path, Any]]] = {}
    for path in sorted(root.iterdir()):
        if not path.is_file():
            continue
        if path.is_symlink():
            raise Ct2PhitsFrontendError(
                f"CT DICOM input files must not be symbolic links: {path.name}"
            )
        dataset = _read_ct_header(path)
        if dataset is None:
            if _is_dicom_or_ct_candidate(path):
                raise Ct2PhitsFrontendError(
                    f"unreadable CT DICOM candidate: {path.name}"
                )
            continue
        if str(getattr(dataset, "Modality", "") or "") != "CT":
            continue
        uid = str(getattr(dataset, "SeriesInstanceUID", "") or "")
        if not uid:
            raise Ct2PhitsFrontendError(
                f"CT DICOM is missing SeriesInstanceUID: {path.name}"
            )
        series.setdefault(uid, []).append((path, dataset))

    if not series:
        raise Ct2PhitsFrontendError("no readable CT DICOM series was found")
    if series_instance_uid is None:
        if len(series) != 1:
            raise Ct2PhitsFrontendError(
                "multiple CT DICOM series were found; specify --ct-series-instance-uid"
            )
        selected_uid = next(iter(series))
    else:
        selected_uid = series_instance_uid.strip()
        if not selected_uid or selected_uid not in series:
            raise Ct2PhitsFrontendError(
                "the requested CT SeriesInstanceUID was not found"
            )

    selected = series[selected_uid]
    frame_uids: set[str] = set()
    dimensions: set[tuple[int, int]] = set()
    positioned: list[tuple[tuple[float, float, float], Path]] = []
    for path, dataset in selected:
        try:
            _require_axial_hfs_ct(dataset, path=path)
        except Ct2PhitsDatfilesError as exc:
            raise Ct2PhitsFrontendError(str(exc)) from exc
        frame_uid = str(getattr(dataset, "FrameOfReferenceUID", "") or "")
        if not frame_uid:
            raise Ct2PhitsFrontendError(
                f"CT DICOM is missing FrameOfReferenceUID: {path.name}"
            )
        frame_uids.add(frame_uid)
        try:
            rows = int(getattr(dataset, "Rows", 0))
            columns = int(getattr(dataset, "Columns", 0))
        except (TypeError, ValueError) as exc:
            raise Ct2PhitsFrontendError(
                f"CT DICOM Rows and Columns must be integers: {path.name}"
            ) from exc
        dimensions.add((rows, columns))
        try:
            position = _finite_vector(
                getattr(dataset, "ImagePositionPatient", None),
                length=3,
                label="CT ImagePositionPatient",
            )
        except Ct2PhitsDatfilesError as exc:
            raise Ct2PhitsFrontendError(str(exc)) from exc
        positioned.append((position, path))

    if len(frame_uids) != 1:
        raise Ct2PhitsFrontendError(
            "selected CT series contains inconsistent FrameOfReferenceUID values"
        )
    if len(dimensions) != 1:
        raise Ct2PhitsFrontendError(
            "selected CT series contains inconsistent Rows or Columns values"
        )
    rows, columns = next(iter(dimensions))
    if rows <= 0 or columns <= 0:
        raise Ct2PhitsFrontendError(
            "selected CT series Rows and Columns must be positive"
        )
    in_plane_positions = {
        (position[0], position[1]) for position, _path in positioned
    }
    if len(in_plane_positions) != 1:
        raise Ct2PhitsFrontendError(
            "selected CT series contains inconsistent ImagePositionPatient X or Y values"
        )
    z_positions = sorted(position[2] for position, _path in positioned)
    if len(set(z_positions)) != len(z_positions):
        raise Ct2PhitsFrontendError(
            "selected CT series contains duplicate ImagePositionPatient Z values"
        )
    if len(z_positions) >= 3:
        expected_spacing = z_positions[1] - z_positions[0]
        adjacent_spacings = [
            current - previous
            for previous, current in zip(z_positions, z_positions[1:])
        ]
        if not all(
            math.isclose(
                spacing,
                expected_spacing,
                rel_tol=0.0,
                abs_tol=CT_SLICE_SPACING_TOLERANCE_MM,
            )
            for spacing in adjacent_spacings[1:]
        ):
            raise Ct2PhitsFrontendError(
                "selected CT series contains non-uniform ImagePositionPatient Z spacing"
            )
    positioned.sort(key=lambda item: item[0][2])
    return SelectedCtSeries(
        source_root=root,
        series_instance_uid=selected_uid,
        frame_of_reference_uid=next(iter(frame_uids)),
        files=tuple(path for _position, path in positioned),
        rows=rows,
        columns=columns,
    )


def _validate_external_layout(
    *,
    rtphits_root: Path,
    workspace_root: Path,
) -> tuple[Path, Path, Path, Path]:
    root = rtphits_root.resolve()
    if not root.is_dir():
        raise Ct2PhitsFrontendError(
            f"RT-PHITS root directory does not exist: {rtphits_root}"
        )
    batch = root / CT2PHITS_BATCH_NAME
    if not batch.is_file():
        raise Ct2PhitsFrontendError(
            f"required RT-PHITS batch file is missing: {CT2PHITS_BATCH_NAME}"
        )
    table = root / CT2PHITS_TABLE_RELATIVE
    if not table.is_file():
        raise Ct2PhitsFrontendError(
            "required CT2PHITS HU conversion table is missing: "
            + CT2PHITS_TABLE_RELATIVE.as_posix()
        )

    workspace = workspace_root.resolve()
    if workspace.exists():
        raise Ct2PhitsFrontendError(
            f"CT2PHITS workspace output already exists: {workspace}"
        )
    if workspace == root or not _is_relative_to(workspace, root):
        raise Ct2PhitsFrontendError(
            "CT2PHITS workspace must be a new directory below the supplied RT-PHITS root"
        )
    if _is_within_dicomxphits_repository(workspace):
        raise Ct2PhitsFrontendError(
            "CT2PHITS workspace must remain outside the dicomxphits repository"
        )
    return root, workspace, batch, table


def _relative_rtphits_directory(path: Path, *, rtphits_root: Path) -> str:
    relative = path.relative_to(rtphits_root).as_posix()
    if '"' in relative:
        raise Ct2PhitsFrontendError("RT-PHITS relative paths must not contain quotes")
    return relative.rstrip("/") + "/"


def render_ct2phits_input(
    *,
    rtphits_root: Path,
    ct_root: Path,
    datfiles_root: Path,
    slice_count: int,
    rows: int,
    columns: int,
) -> str:
    if slice_count <= 0:
        raise Ct2PhitsFrontendError("CT2PHITS requires at least one CT slice")
    if rows <= 0 or columns <= 0:
        raise Ct2PhitsFrontendError(
            "CT2PHITS Rows and Columns must be positive"
        )
    ct_relative = _relative_rtphits_directory(ct_root, rtphits_root=rtphits_root)
    datfiles_relative = _relative_rtphits_directory(
        datfiles_root,
        rtphits_root=rtphits_root,
    )
    coarse = " ".join(str(value) for value in CT2PHITS_COARSE_GRAINING)
    return (
        "CT2PHITS input\n"
        '"data/HumanVoxelTable.data"\n'
        f'"{ct_relative}"\n'
        f'"{datfiles_relative}"\n'
        f"1 {slice_count}\n"
        f"1 {columns} 1 {rows}\n"
        f"{coarse}\n"
        "1\n"
    )


def _default_runner(
    command: Sequence[str],
    cwd: Path,
    timeout_seconds: float,
) -> subprocess.CompletedProcess[str]:
    command_list = list(command)
    with (
        tempfile.TemporaryFile(mode="w+", encoding="utf-8", newline="") as stdout,
        tempfile.TemporaryFile(mode="w+", encoding="utf-8", newline="") as stderr,
    ):
        process = subprocess.Popen(
            command_list,
            cwd=str(cwd),
            stdout=stdout,
            stderr=stderr,
            text=True,
        )
        try:
            returncode = process.wait(timeout=timeout_seconds)
        except subprocess.TimeoutExpired:
            try:
                terminated = subprocess.run(
                    [
                        "taskkill.exe",
                        "/PID",
                        str(process.pid),
                        "/T",
                        "/F",
                    ],
                    check=False,
                    capture_output=True,
                    text=True,
                    timeout=PROCESS_TREE_TERMINATION_TIMEOUT_SECONDS,
                )
            except (OSError, subprocess.TimeoutExpired) as exc:
                process.kill()
                process.wait(timeout=PROCESS_TREE_TERMINATION_TIMEOUT_SECONDS)
                raise OSError(
                    "failed to terminate the timed-out Windows process tree"
                ) from exc
            if terminated.returncode != 0:
                if process.poll() is None:
                    process.kill()
                    process.wait(timeout=PROCESS_TREE_TERMINATION_TIMEOUT_SECONDS)
                raise OSError(
                    "taskkill failed to terminate the timed-out Windows process tree: "
                    + terminated.stderr.strip()
                )
            try:
                process.wait(timeout=PROCESS_TREE_TERMINATION_TIMEOUT_SECONDS)
            except subprocess.TimeoutExpired as exc:
                process.kill()
                process.wait(timeout=PROCESS_TREE_TERMINATION_TIMEOUT_SECONDS)
                raise OSError(
                    "timed-out Windows process tree did not terminate"
                ) from exc
            stdout.flush()
            stderr.flush()
            stdout.seek(0)
            stderr.seek(0)
            raise subprocess.TimeoutExpired(
                command_list,
                timeout_seconds,
                output=stdout.read(),
                stderr=stderr.read(),
            ) from None
        stdout.flush()
        stderr.flush()
        stdout.seek(0)
        stderr.seek(0)
        return subprocess.CompletedProcess(
            command_list,
            returncode,
            stdout.read(),
            stderr.read(),
        )


def _output_text(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def _generated_inventory(
    datfiles_root: Path,
    *,
    started_ns: int,
) -> dict[str, dict[str, Any]]:
    inventory: dict[str, dict[str, Any]] = {}
    missing: list[str] = []
    empty: list[str] = []
    stale: list[str] = []
    for name in CT2PHITS_GENERATED_NAMES:
        path = datfiles_root / name
        if not path.is_file():
            missing.append(name)
            continue
        if path.is_symlink():
            raise Ct2PhitsFrontendError(
                f"generated CT2PHITS files must not be symbolic links: {name}"
            )
        stat = path.stat()
        if stat.st_size <= 0:
            empty.append(name)
            continue
        if stat.st_mtime_ns < started_ns:
            stale.append(name)
        inventory[name] = {
            "path": f"DATfiles/{name}",
            "size_bytes": stat.st_size,
            "mtime_ns": stat.st_mtime_ns,
            "sha256": _sha256(path),
        }
    if missing:
        raise Ct2PhitsFrontendError(
            "required CT2PHITS generated files are missing: " + ", ".join(missing)
        )
    if empty:
        raise Ct2PhitsFrontendError(
            "required CT2PHITS generated files are empty: " + ", ".join(empty)
        )
    if stale:
        raise Ct2PhitsFrontendError(
            "CT2PHITS generated files are stale for the current run: "
            + ", ".join(stale)
        )
    return inventory


def run_ct2phits_frontend(
    *,
    ct_dicom_root: Path,
    rtplan_path: Path,
    rtphits_root: Path,
    workspace_root: Path,
    confirmed_non_patient_phantom: bool,
    series_instance_uid: str | None = None,
    timeout_seconds: float = 300.0,
    runner: Runner = _default_runner,
    platform_system: str | None = None,
) -> Ct2PhitsFrontendResult:
    if not confirmed_non_patient_phantom:
        raise Ct2PhitsFrontendError(
            "CT2PHITS execution requires explicit confirmation that the source is non-patient phantom data"
        )
    current_platform = platform_system or platform.system()
    if current_platform != "Windows":
        raise Ct2PhitsFrontendError("CT2PHITS execution is supported on Windows only")
    if not math.isfinite(timeout_seconds) or timeout_seconds <= 0:
        raise Ct2PhitsFrontendError("timeout seconds must be positive and finite")

    root, workspace, batch, _table = _validate_external_layout(
        rtphits_root=rtphits_root,
        workspace_root=workspace_root,
    )
    selected = select_ct_series(
        ct_dicom_root,
        series_instance_uid=series_instance_uid,
    )
    rtplan_source = rtplan_path.resolve()
    try:
        ct_origin, frame_uid, _series_uid, selected_count = _ct_series_origin(
            selected.files[0]
        )
        _rtplan_isocenter(
            rtplan_source,
            expected_frame_uid=frame_uid,
        )
    except Ct2PhitsDatfilesError as exc:
        raise Ct2PhitsFrontendError(str(exc)) from exc
    try:
        rtplan_source_sha256 = _sha256(rtplan_source)
    except OSError as exc:
        raise Ct2PhitsFrontendError(
            f"could not hash RT Plan input: {rtplan_source}"
        ) from exc
    if selected_count != len(selected.files):
        raise Ct2PhitsFrontendError(
            "selected CT series count changed during preflight inspection"
        )

    ct_root = workspace / "CT"
    datfiles_root = workspace / "DATfiles"
    prepared_root = workspace / "prepared_ct_assets"
    logs_root = workspace / "logs"
    manifest_path = workspace / CT2PHITS_MANIFEST_NAME
    summary_path = workspace / CT2PHITS_SUMMARY_NAME
    input_path = workspace / CT2PHITS_INPUT_NAME
    rtplan_snapshot = workspace / RTPLAN_SNAPSHOT_NAME

    workspace.mkdir(parents=True)
    ct_root.mkdir()
    datfiles_root.mkdir()
    logs_root.mkdir()
    shutil.copyfile(rtplan_source, rtplan_snapshot)
    if _sha256(rtplan_snapshot) != rtplan_source_sha256:
        raise Ct2PhitsFrontendError(
            "RT Plan input changed while creating the workspace snapshot"
        )
    try:
        rtplan_isocenter = _rtplan_isocenter(
            rtplan_snapshot,
            expected_frame_uid=frame_uid,
        )
    except Ct2PhitsDatfilesError as exc:
        raise Ct2PhitsFrontendError(str(exc)) from exc
    copied_files: list[str] = []
    copied_sha256: dict[str, str] = {}
    for index, source in enumerate(selected.files, start=1):
        name = f"CT{index:06d}.dcm"
        copied_path = f"CT/{name}"
        copied_sha256[copied_path] = _copy_stable_ct_slice(
            source,
            ct_root / name,
        )
        copied_files.append(copied_path)
    frozen_selected = select_ct_series(
        ct_root,
        series_instance_uid=selected.series_instance_uid,
    )
    try:
        ct_origin, frame_uid, _series_uid, frozen_count = _ct_series_origin(
            frozen_selected.files[0]
        )
        rtplan_isocenter = _rtplan_isocenter(
            rtplan_snapshot,
            expected_frame_uid=frame_uid,
        )
    except Ct2PhitsDatfilesError as exc:
        raise Ct2PhitsFrontendError(str(exc)) from exc
    if frozen_count != len(copied_files) or len(frozen_selected.files) != len(
        copied_files
    ):
        raise Ct2PhitsFrontendError(
            "CT series count changed while creating the workspace snapshot"
        )
    selected = frozen_selected
    ct_reference = selected.files[0]
    input_path.write_text(
        render_ct2phits_input(
            rtphits_root=root,
            ct_root=ct_root,
            datfiles_root=datfiles_root,
            slice_count=len(copied_files),
            rows=selected.rows,
            columns=selected.columns,
        ),
        encoding="utf-8",
        newline="\n",
    )

    manifest: dict[str, Any] = {
        "schema_version": "dicomxphits_ct2phits_workspace_v1",
        "stage": "ct2phits_frontend",
        "status": "prepared",
        "confirmed_non_patient_phantom": True,
        "ct_series": {
            "series_instance_uid": selected.series_instance_uid,
            "frame_of_reference_uid": selected.frame_of_reference_uid,
            "slice_count": len(copied_files),
            "rows": selected.rows,
            "columns": selected.columns,
            "copied_files": copied_files,
            "sha256": copied_sha256,
            "ct_origin_dicom_cm": list(ct_origin),
        },
        "rtplan": {
            "source_name": rtplan_path.name,
            "snapshot_path": RTPLAN_SNAPSHOT_NAME,
            "sha256": rtplan_source_sha256,
            "isocenter_dicom_cm": list(rtplan_isocenter),
            "frame_of_reference_match": True,
        },
        "ct2phits_input": {
            "path": CT2PHITS_INPUT_NAME,
            "signature": "CT2PHITS input",
            "slice_range": [1, len(copied_files)],
            "clipping": [1, selected.columns, 1, selected.rows],
            "coarse_graining": list(CT2PHITS_COARSE_GRAINING),
            "coordinate_mode": 1,
        },
        "generated_output_contract": list(CT2PHITS_GENERATED_NAMES),
        "downstream_raw_datfiles_contract": list(RAW_CT2PHITS_NAMES),
        "cttrans_contract": {
            "generated_cttrans_dat": "DATfiles/CTtrans.dat",
            "downstream_role": (
                "inventory_only; prepare_ct2phits_assets generates the validated CTtrans.inp"
            ),
        },
    }
    _write_json(manifest_path, manifest)

    input_relative = input_path.relative_to(root)
    command = (
        os.environ.get("COMSPEC", "cmd.exe"),
        "/d",
        "/s",
        "/c",
        str(batch.relative_to(root)),
        str(input_relative),
    )
    command_record = [Path(command[0]).name, *command[1:]]
    stdout_path = logs_root / "ct2phits.stdout.log"
    stderr_path = logs_root / "ct2phits.stderr.log"
    started_ns = time.time_ns()
    started_at = datetime.now(timezone.utc).isoformat()
    returncode: int | None = None
    timed_out = False
    stdout = ""
    stderr = ""
    failure: str | None = None
    inventory: dict[str, dict[str, Any]] = {}
    raw_hashes: dict[str, str] | None = None
    prepared_hashes: dict[str, str] | None = None
    try:
        completed = runner(command, root, timeout_seconds)
        returncode = completed.returncode
        stdout = _output_text(completed.stdout)
        stderr = _output_text(completed.stderr)
        if returncode != 0:
            raise Ct2PhitsFrontendError(
                f"RTphits_win.bat returned non-zero exit code {returncode}"
            )
        inventory = _generated_inventory(datfiles_root, started_ns=started_ns)
        raw = validate_raw_ct2phits_datfiles(
            datfiles_root,
            confirmed_non_patient_phantom=True,
        )
        prepared = prepare_ct2phits_assets(
            raw_datfiles_root=datfiles_root,
            ct_reference_dicom=ct_reference,
            rtplan_path=rtplan_snapshot,
            output_root=prepared_root,
            confirmed_non_patient_phantom=True,
        )
        raw_hashes = dict(raw.sha256)
        post_prepare_raw = validate_raw_ct2phits_datfiles(
            datfiles_root,
            confirmed_non_patient_phantom=True,
        )
        if (
            raw_hashes != dict(prepared.raw_sha256)
            or raw_hashes != dict(post_prepare_raw.sha256)
        ):
            raise Ct2PhitsFrontendError(
                "raw CT2PHITS DATfiles changed during downstream handoff"
            )
        post_handoff_inventory = _generated_inventory(
            datfiles_root,
            started_ns=started_ns,
        )
        if inventory != post_handoff_inventory:
            raise Ct2PhitsFrontendError(
                "CT2PHITS generated files changed during downstream handoff"
            )
        inventory = post_handoff_inventory
        prepared_hashes = dict(prepared.assets.sha256)
    except subprocess.TimeoutExpired as exc:
        timed_out = True
        stdout = _output_text(exc.stdout)
        stderr = _output_text(exc.stderr)
        failure = f"RTphits_win.bat timed out after {timeout_seconds:g} seconds"
    except (
        Ct2PhitsFrontendError,
        Ct2PhitsDatfilesError,
        CtCalibrationError,
        OSError,
    ) as exc:
        failure = str(exc)
    finally:
        stdout_path.write_text(stdout, encoding="utf-8", newline="\n")
        stderr_path.write_text(stderr, encoding="utf-8", newline="\n")

    status = "failed" if failure is not None else "completed"
    finished_ns = time.time_ns()
    manifest["status"] = status
    _write_json(manifest_path, manifest)
    summary: dict[str, Any] = {
        "schema_version": "dicomxphits_ct2phits_execution_v1",
        "stage": "ct2phits_frontend",
        "status": status,
        "command": command_record,
        "cwd": ".",
        "timeout_seconds": timeout_seconds,
        "started_at_utc": started_at,
        "finished_at_utc": datetime.now(timezone.utc).isoformat(),
        "duration_seconds": (finished_ns - started_ns) / 1_000_000_000,
        "timed_out": timed_out,
        "returncode": returncode,
        "stdout_path": "logs/ct2phits.stdout.log",
        "stderr_path": "logs/ct2phits.stderr.log",
        "failure_reason": failure,
        "generated_inventory": inventory,
        "raw_datfiles_sha256": raw_hashes,
        "prepared_assets_sha256": prepared_hashes,
        "workspace_preparation_handoff": {
            "ct_datfiles_root": "DATfiles",
            "ct_reference_dicom": "CT/CT000001.dcm",
            "prepared_assets_root": (
                "prepared_ct_assets" if prepared_hashes is not None else None
            ),
            "validated_with": [
                "validate_raw_ct2phits_datfiles",
                "prepare_ct2phits_assets",
            ],
        },
    }
    _write_json(summary_path, summary)
    if failure is not None:
        raise Ct2PhitsFrontendError(
            f"{failure}; see {summary_path}"
        )
    return Ct2PhitsFrontendResult(
        workspace_root=workspace,
        datfiles_root=datfiles_root,
        ct_reference_dicom=ct_reference,
        prepared_assets_root=prepared_root,
        manifest_path=manifest_path,
        summary_path=summary_path,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run the Windows RT-PHITS CT2PHITS batch path for a confirmed "
            "non-patient CT phantom and validate its DATfiles handoff."
        )
    )
    parser.add_argument("--ct-dicom-root", required=True)
    parser.add_argument("--rtplan", required=True)
    parser.add_argument("--rtphits-root", required=True)
    parser.add_argument("--workspace-root", required=True)
    parser.add_argument("--ct-series-instance-uid", default=None)
    parser.add_argument("--timeout-seconds", type=float, default=300.0)
    parser.add_argument(
        "--confirm-non-patient-phantom",
        action="store_true",
        help="Confirm that the CT and RTPLAN inputs describe non-patient phantom data",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = run_ct2phits_frontend(
            ct_dicom_root=Path(args.ct_dicom_root),
            rtplan_path=Path(args.rtplan),
            rtphits_root=Path(args.rtphits_root),
            workspace_root=Path(args.workspace_root),
            confirmed_non_patient_phantom=args.confirm_non_patient_phantom,
            series_instance_uid=args.ct_series_instance_uid,
            timeout_seconds=args.timeout_seconds,
        )
    except Ct2PhitsFrontendError as exc:
        print(f"CT2PHITS frontend failed: {exc}", file=sys.stderr)
        return 2
    print(result.summary_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
