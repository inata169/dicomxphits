from __future__ import annotations

import json
import math
import os
import re
import subprocess
import sys
import threading
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable, Mapping, MutableMapping, Sequence


PUBLIC_ROOT = Path(__file__).resolve().parents[2]
GEOMETRY_MODE_RECTANGULAR_3DCRT = "rectangular_3dcrt"
GEOMETRY_MODES = (GEOMETRY_MODE_RECTANGULAR_3DCRT,)
GUI_DEFAULTS_ENV_VAR = "DICOMXPHITS_GUI_DEFAULTS_JSON"
GUI_DEFAULTS_FILE_NAME = "dicomxphits.gui.local.json"
GUI_SETTINGS_VERSION = 2
DEFAULT_CT2PHITS_TIMEOUT_SECONDS = 300.0
PERSISTED_GUI_FIELDS = (
    "geometry_mode",
    "rtphits_root",
    "phits_root_folder",
    "phits_executable_path",
    "phits2dicom_executable_path",
    "rtdose_template_dicom",
    "machine_config_path",
)
GUI_HELP_TEXT = """\
usage: dicomxphits-gui [-h]

Launch the dicomxphits v1.0.0 guided GUI for validated 3D-CRT fixed-field
workflows only. The first stage uses the accepted Windows CT2PHITS frontend.
IMRT, dynamic MLC delivery, and VMAT are not supported as validated public
workflows.

options:
  -h, --help  show this help message and exit
"""


class GuiValidationError(ValueError):
    """Raised before any external command is started."""


@dataclass(frozen=True)
class GuiConfig:
    rtplan_path: str
    workspace_root: str
    phits_root_folder: str
    phits_executable_path: str
    phits2dicom_executable_path: str
    rtdose_template_dicom: str
    ct_reference_dicom: str
    machine_config_path: str
    allow_overwrite: bool = False
    geometry_mode: str = GEOMETRY_MODE_RECTANGULAR_3DCRT
    ct_datfiles_root: str = ""
    confirmed_non_patient_phantom: bool = False
    source_rtplan_path: str = ""
    ct_dicom_root: str = ""
    rtphits_root: str = ""
    ct2phits_workspace_root: str = ""
    ct_series_instance_uid: str = ""
    ct2phits_timeout_seconds: float = DEFAULT_CT2PHITS_TIMEOUT_SECONDS


@dataclass(frozen=True)
class StageSpec:
    key: str
    label: str
    command: tuple[str, ...]
    required_paths: tuple[tuple[str, str, bool], ...]
    summary_relative_path: Path
    workspace_must_exist: bool
    fail_on_existing_summary: bool
    workspace_field: str = "workspace_root"


@dataclass(frozen=True)
class StageResult:
    stage_key: str
    command: list[str]
    return_code: int
    summary_path: Path
    summary: dict[str, object] | None
    stdout: str
    stderr: str


@dataclass
class StageExecutionGuard:
    active_stage: str | None = None

    def begin(self, stage_key: str) -> None:
        if self.active_stage is not None:
            raise GuiValidationError(
                f"{self.active_stage} is already running; wait before starting {stage_key}"
            )
        self.active_stage = stage_key

    def finish(self) -> None:
        self.active_stage = None


def public_root() -> Path:
    return PUBLIC_ROOT


def stage_specs() -> tuple[StageSpec, ...]:
    workspace_only = (("workspace_root", "3D-CRT workspace", True),)
    phits_root = (("phits_root_folder", "PHITS root folder", True),)
    phits_executable = (("phits_executable_path", "PHITS executable path", False),)
    phits2dicom_executable = (
        ("phits2dicom_executable_path", "phits2dicom executable path", False),
    )
    return (
        StageSpec(
            key="run_ct2phits",
            label="CT2PHITS",
            command=("dicomxphits-run-ct2phits",),
            required_paths=(
                ("source_rtplan_path", "source RT Plan", False),
                ("ct_dicom_root", "CT DICOM folder", True),
                ("rtphits_root", "RT-PHITS root", True),
            ),
            summary_relative_path=Path("ct2phits_execution_summary.json"),
            workspace_must_exist=False,
            fail_on_existing_summary=True,
            workspace_field="ct2phits_workspace_root",
        ),
        StageSpec(
            key="prepare_workspace",
            label="Workspace Prepare",
            command=("dicomxphits-prepare-3dcrt-workspace",),
            required_paths=(
                ("rtplan_path", "RTPLAN path", False),
                ("workspace_root", "3D-CRT workspace", True),
                ("ct_datfiles_root", "CT2PHITS DATfiles directory", True),
                ("ct_reference_dicom", "CT reference DICOM", False),
                *phits_root,
                *phits_executable,
                *phits2dicom_executable,
            ),
            summary_relative_path=Path("analysis")
            / "public_preparation_workspace_summary.json",
            workspace_must_exist=False,
            fail_on_existing_summary=True,
        ),
        StageSpec(
            key="run_segments",
            label="PHITS Segment Execution",
            command=("dicomxphits-run-segments",),
            required_paths=(*workspace_only, *phits_executable),
            summary_relative_path=Path("analysis") / "segment_execution_summary.json",
            workspace_must_exist=True,
            fail_on_existing_summary=True,
        ),
        StageSpec(
            key="generate_sumtally",
            label="Sumtally Generate",
            command=("dicomxphits-generate-sumtally",),
            required_paths=(*workspace_only, *phits_root),
            summary_relative_path=Path("analysis") / "sumtally_generation_summary.json",
            workspace_must_exist=True,
            fail_on_existing_summary=True,
        ),
        StageSpec(
            key="run_sumtally",
            label="Sumtally Run",
            command=("dicomxphits-run-sumtally",),
            required_paths=(*workspace_only, *phits_executable),
            summary_relative_path=Path("analysis") / "sumtally_execution_summary.json",
            workspace_must_exist=True,
            fail_on_existing_summary=True,
        ),
        StageSpec(
            key="prepare_rtdose",
            label="RTDOSE Prepare",
            command=("dicomxphits-prepare-rtdose",),
            required_paths=(
                *workspace_only,
                ("rtdose_template_dicom", "RTDOSE template DICOM", False),
                ("ct_reference_dicom", "CT reference DICOM", False),
            ),
            summary_relative_path=Path("analysis")
            / "rtdose_conversion_prepare_summary.json",
            workspace_must_exist=True,
            fail_on_existing_summary=True,
        ),
        StageSpec(
            key="run_rtdose",
            label="RTDOSE Run",
            command=("dicomxphits-run-rtdose",),
            required_paths=(*workspace_only, *phits2dicom_executable),
            summary_relative_path=Path("analysis")
            / "rtdose_conversion_execution_summary.json",
            workspace_must_exist=True,
            fail_on_existing_summary=True,
        ),
    )


def stage_by_key(stage_key: str) -> StageSpec:
    for spec in stage_specs():
        if spec.key == stage_key:
            return spec
    raise KeyError(f"unknown stage: {stage_key}")


def _path_value(config: GuiConfig, field_name: str) -> str:
    return str(getattr(config, field_name)).strip()


def _resolved_path(config: GuiConfig, field_name: str) -> Path:
    value = _path_value(config, field_name)
    if not value:
        raise GuiValidationError(f"{field_name} is required")
    return Path(value).expanduser().resolve()


def geometry_mode_value(config: GuiConfig) -> str:
    value = str(
        getattr(config, "geometry_mode", GEOMETRY_MODE_RECTANGULAR_3DCRT) or ""
    ).strip()
    return value or GEOMETRY_MODE_RECTANGULAR_3DCRT


def geometry_mode_guidance(geometry_mode: str) -> str:
    if geometry_mode == GEOMETRY_MODE_RECTANGULAR_3DCRT:
        return (
            "Geometry mode rectangular_3dcrt: rectangular geometry generation only; "
            "no dose validation or clinical validity certification."
        )
    return f"Geometry mode {geometry_mode}: unrecognized."


def _inside_public_tree(path: Path, public_tree: Path) -> bool:
    resolved = path.resolve()
    public_resolved = public_tree.resolve()
    return resolved == public_resolved or public_resolved in resolved.parents


def _ct2phits_timeout_value(config: GuiConfig) -> float:
    try:
        value = float(config.ct2phits_timeout_seconds)
    except (TypeError, ValueError) as exc:
        raise GuiValidationError("CT2PHITS timeout must be a number") from exc
    if not math.isfinite(value) or value <= 0:
        raise GuiValidationError("CT2PHITS timeout must be positive and finite")
    return value


def validate_stage(
    config: GuiConfig,
    spec: StageSpec,
    *,
    public_tree: Path | None = None,
) -> Path:
    public_tree = public_tree or public_root()
    geometry_mode = geometry_mode_value(config)
    required_paths = spec.required_paths

    if spec.key in {"run_ct2phits", "prepare_workspace"}:
        if not config.confirmed_non_patient_phantom:
            raise GuiValidationError(
                "Confirm that the CT and RT Plan describe non-patient phantom data"
            )

    if spec.key == "run_ct2phits":
        _ct2phits_timeout_value(config)

    if spec.key == "prepare_workspace":
        if geometry_mode not in GEOMETRY_MODES:
            raise GuiValidationError(f"unknown geometry_mode: {geometry_mode}")
        required_paths = tuple(
            requirement
            for requirement in required_paths
            if requirement[0]
            not in {"phits_executable_path", "phits2dicom_executable_path"}
        )
        if (
            geometry_mode == GEOMETRY_MODE_RECTANGULAR_3DCRT
            and _path_value(config, "machine_config_path")
        ):
            machine_config = _resolved_path(config, "machine_config_path")
            if not machine_config.is_file():
                raise GuiValidationError(
                    "machine_config_path must be an existing regular file"
                )

    missing: list[str] = []
    for field_name, label, expect_dir in required_paths:
        if field_name == spec.workspace_field:
            if not _path_value(config, field_name):
                missing.append(label)
            continue
        try:
            path = _resolved_path(config, field_name)
        except GuiValidationError:
            missing.append(label)
            continue
        exists = path.is_dir() if expect_dir else path.is_file()
        if not exists:
            missing.append(label)
    if missing:
        raise GuiValidationError("Missing required path(s): " + ", ".join(missing))

    workspace = _resolved_path(config, spec.workspace_field)
    if _inside_public_tree(workspace, public_tree):
        raise GuiValidationError("workspace root must be outside public_release/dicomxphits")

    if spec.key == "run_ct2phits":
        rtphits_root = _resolved_path(config, "rtphits_root")
        if workspace == rtphits_root or rtphits_root not in workspace.parents:
            raise GuiValidationError("CT2PHITS workspace must be below the RT-PHITS root")
        if workspace.exists():
            raise GuiValidationError("CT2PHITS workspace must be new and must not exist")
    else:
        if spec.workspace_must_exist and not workspace.is_dir():
            raise GuiValidationError("workspace root does not exist")
        if (
            not spec.workspace_must_exist
            and not workspace.exists()
            and not workspace.parent.is_dir()
        ):
            raise GuiValidationError("workspace parent directory does not exist")
        if (
            not spec.workspace_must_exist
            and workspace.exists()
            and any(workspace.iterdir())
            and not config.allow_overwrite
        ):
            raise GuiValidationError("workspace root already contains files")

    summary_path = workspace / spec.summary_relative_path
    if (
        spec.fail_on_existing_summary
        and summary_path.exists()
        and not config.allow_overwrite
    ):
        raise GuiValidationError(f"stage output already exists: {summary_path}")
    return workspace


def build_stage_command(config: GuiConfig, spec: StageSpec) -> list[str]:
    workspace = _resolved_path(config, spec.workspace_field)
    command = [*spec.command, "--workspace-root", str(workspace)]

    if spec.key == "run_ct2phits":
        command.extend(
            [
                "--ct-dicom-root",
                str(_resolved_path(config, "ct_dicom_root")),
                "--rtplan",
                str(_resolved_path(config, "source_rtplan_path")),
                "--rtphits-root",
                str(_resolved_path(config, "rtphits_root")),
                "--timeout-seconds",
                f"{_ct2phits_timeout_value(config):g}",
            ]
        )
        series_uid = str(config.ct_series_instance_uid or "").strip()
        if series_uid:
            command.extend(["--ct-series-instance-uid", series_uid])
        command.append("--confirm-non-patient-phantom")
    elif spec.key == "prepare_workspace":
        geometry_mode = geometry_mode_value(config)
        command.extend(
            [
                "--rtplan",
                str(_resolved_path(config, "rtplan_path")),
                "--phits-root-folder",
                str(_resolved_path(config, "phits_root_folder")),
                "--geometry-mode",
                geometry_mode,
            ]
        )
        if (
            geometry_mode == GEOMETRY_MODE_RECTANGULAR_3DCRT
            and _path_value(config, "machine_config_path")
        ):
            command.extend(
                [
                    "--machine-config-path",
                    str(_resolved_path(config, "machine_config_path")),
                ]
            )
        if geometry_mode == GEOMETRY_MODE_RECTANGULAR_3DCRT:
            command.extend(
                [
                    "--ct-datfiles-root",
                    str(_resolved_path(config, "ct_datfiles_root")),
                    "--ct-reference-dicom",
                    str(_resolved_path(config, "ct_reference_dicom")),
                    "--confirm-non-patient-phantom",
                ]
            )
    elif spec.key == "run_segments":
        command.extend(
            [
                "--phits-executable-path",
                str(_resolved_path(config, "phits_executable_path")),
            ]
        )
    elif spec.key == "generate_sumtally":
        command.extend(
            [
                "--phits-root-folder",
                str(_resolved_path(config, "phits_root_folder")),
            ]
        )
    elif spec.key == "run_sumtally":
        command.extend(
            [
                "--phits-executable-path",
                str(_resolved_path(config, "phits_executable_path")),
            ]
        )
    elif spec.key == "prepare_rtdose":
        command.extend(
            [
                "--template-dicom",
                str(_resolved_path(config, "rtdose_template_dicom")),
                "--ct-reference-dicom",
                str(_resolved_path(config, "ct_reference_dicom")),
                "--phits-out",
                str((workspace / "sumtally" / "phits.out").resolve()),
            ]
        )
    elif spec.key == "run_rtdose":
        command.extend(
            [
                "--phits2dicom-executable-path",
                str(_resolved_path(config, "phits2dicom_executable_path")),
            ]
        )
    return command


def read_summary(path: Path) -> dict[str, object] | None:
    if not path.is_file():
        return None
    with path.open("r", encoding="utf-8") as stream:
        data = json.load(stream)
    if isinstance(data, dict):
        return data
    return {"summary_error": "summary JSON root is not an object"}


def run_stage(
    config: GuiConfig,
    stage_key: str,
    *,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
    public_tree: Path | None = None,
) -> StageResult:
    spec = stage_by_key(stage_key)
    workspace = validate_stage(config, spec, public_tree=public_tree)
    command = build_stage_command(config, spec)
    if spec.key == "run_ct2phits":
        cwd = _resolved_path(config, "rtphits_root")
    else:
        cwd = workspace if workspace.exists() else workspace.parent
    result = runner(command, cwd=cwd, capture_output=True, text=True, shell=False)
    summary_path = workspace / spec.summary_relative_path
    return StageResult(
        stage_key=stage_key,
        command=command,
        return_code=result.returncode,
        summary_path=summary_path,
        summary=read_summary(summary_path),
        stdout=result.stdout or "",
        stderr=result.stderr or "",
    )


def _base_default_values() -> dict[str, str]:
    return {
        "source_rtplan_path": "",
        "ct_dicom_root": "",
        "rtphits_root": "",
        "ct2phits_workspace_root": "",
        "ct_series_instance_uid": "",
        "ct2phits_timeout_seconds": f"{DEFAULT_CT2PHITS_TIMEOUT_SECONDS:g}",
        "rtplan_path": "",
        "workspace_root": "",
        "phits_root_folder": "",
        "phits_executable_path": "",
        "phits2dicom_executable_path": "",
        "rtdose_template_dicom": str(
            public_root() / "templates" / "phits2dicom_rtdose_template.dcm"
        ),
        "ct_reference_dicom": "",
        "machine_config_path": "",
        "ct_datfiles_root": "",
        "geometry_mode": GEOMETRY_MODE_RECTANGULAR_3DCRT,
    }


def gui_defaults_path() -> Path:
    env_path = os.environ.get(GUI_DEFAULTS_ENV_VAR)
    if env_path:
        return Path(env_path).expanduser()
    return public_root() / "config" / GUI_DEFAULTS_FILE_NAME


def _read_gui_settings(defaults_path: Path | None = None) -> dict[str, object]:
    path = defaults_path or gui_defaults_path()
    try:
        with path.open("r", encoding="utf-8-sig") as stream:
            data = json.load(stream)
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}
    return data if isinstance(data, dict) else {}


def _default_values(defaults_path: Path | None = None) -> dict[str, str]:
    values = _base_default_values()
    data = _read_gui_settings(defaults_path)
    for key in values:
        value = data.get(key)
        if isinstance(value, str):
            values[key] = value
    legacy_ct_root = data.get("ct_asset_root")
    if not values["ct_datfiles_root"] and isinstance(legacy_ct_root, str):
        values["ct_datfiles_root"] = legacy_ct_root
    if not values["source_rtplan_path"] and values["rtplan_path"]:
        values["source_rtplan_path"] = values["rtplan_path"]
    if values["geometry_mode"] not in GEOMETRY_MODES:
        values["geometry_mode"] = GEOMETRY_MODE_RECTANGULAR_3DCRT
    return values


def _browse_directories(defaults_path: Path | None = None) -> dict[str, str]:
    data = _read_gui_settings(defaults_path)
    raw = data.get("browse_directories")
    if not isinstance(raw, dict):
        return {}
    return {
        str(key): value
        for key, value in raw.items()
        if isinstance(key, str) and isinstance(value, str)
    }


def _save_gui_settings(
    values: Mapping[str, str],
    browse_directories: Mapping[str, str],
    defaults_path: Path | None = None,
) -> Path:
    path = defaults_path or gui_defaults_path()
    payload: dict[str, object] = {
        "settings_version": GUI_SETTINGS_VERSION,
        "browse_directories": {
            key: value
            for key, value in sorted(browse_directories.items())
            if isinstance(key, str) and isinstance(value, str)
        },
    }
    for key in PERSISTED_GUI_FIELDS:
        value = values.get(key)
        if isinstance(value, str):
            payload[key] = value
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)
    return path


def browse_initial_directory(
    field_name: str,
    values: Mapping[str, str],
    browse_directories: Mapping[str, str],
) -> Path:
    def nearest_existing_directory(candidate: Path) -> Path | None:
        if candidate.is_dir():
            return candidate
        for parent in candidate.parents:
            if parent.is_dir():
                return parent
        return None

    remembered = str(browse_directories.get(field_name, "")).strip()
    if remembered:
        candidate = Path(remembered).expanduser()
        existing = nearest_existing_directory(candidate)
        if existing is not None:
            return existing
    current = str(values.get(field_name, "")).strip()
    if current:
        candidate = Path(current).expanduser()
        existing = nearest_existing_directory(candidate)
        if existing is not None:
            return existing
    return public_root()


def remember_browse_directory(
    field_name: str,
    selected: str | Path,
    *,
    selected_is_directory: bool,
    browse_directories: MutableMapping[str, str],
    remember_parent: bool = False,
) -> None:
    path = Path(selected).expanduser()
    directory = path if selected_is_directory else path.parent
    if remember_parent:
        directory = directory.parent
    browse_directories[field_name] = str(directory)


def _safe_case_stem(rtplan_path: str | Path) -> str:
    stem = Path(rtplan_path).stem.strip()
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", stem).strip("._-")
    return (cleaned or "phantom-case")[:64]


def workspace_path_from_parent(
    parent: str | Path,
    rtplan_path: str | Path,
    field_name: str,
) -> Path:
    suffixes = {
        "ct2phits_workspace_root": "ct2phits",
        "workspace_root": "3dcrt",
    }
    try:
        suffix = suffixes[field_name]
    except KeyError as exc:
        raise ValueError(f"unsupported workspace field: {field_name}") from exc
    return Path(parent).expanduser() / f"{_safe_case_stem(rtplan_path)}-{suffix}"


def suggest_case_paths(
    rtplan_path: str | Path,
    *,
    rtphits_root: str | Path | None = None,
    workspace_parent: str | Path | None = None,
) -> dict[str, str]:
    plan = Path(rtplan_path).expanduser()
    suggestions = {"ct_dicom_root": str(plan.parent)}
    if rtphits_root and str(rtphits_root).strip():
        suggestions["ct2phits_workspace_root"] = str(
            workspace_path_from_parent(
                Path(rtphits_root).expanduser() / "work",
                plan,
                "ct2phits_workspace_root",
            )
        )
    if workspace_parent and str(workspace_parent).strip():
        suggestions["workspace_root"] = str(
            workspace_path_from_parent(workspace_parent, plan, "workspace_root")
        )
    return suggestions


def ct2phits_handoff_values(
    workspace_root: Path,
    summary: Mapping[str, object] | None,
    *,
    require_files: bool = True,
) -> dict[str, str]:
    if not summary or summary.get("status") != "completed":
        raise GuiValidationError("CT2PHITS summary does not report completion")
    workspace = workspace_root.expanduser().resolve()
    handoff = {
        "rtplan_path": workspace / "RTPLAN.dcm",
        "ct_reference_dicom": workspace / "CT" / "CT000001.dcm",
        "ct_datfiles_root": workspace / "DATfiles",
    }
    if require_files:
        missing = [
            key
            for key, path in handoff.items()
            if not (path.is_dir() if key == "ct_datfiles_root" else path.is_file())
        ]
        if missing:
            raise GuiValidationError(
                "Completed CT2PHITS handoff is missing: " + ", ".join(missing)
            )
    return {key: str(path) for key, path in handoff.items()}


def _ct2phits_handoff_from_result(result: StageResult) -> dict[str, str]:
    return ct2phits_handoff_values(result.summary_path.parent, result.summary)


def _stage_status(result: StageResult) -> str:
    if result.summary:
        for key in ("stage_status", "status"):
            value = result.summary.get(key)
            if isinstance(value, str) and value:
                return value
    return "completed" if result.return_code == 0 else f"return_code={result.return_code}"


def _friendly_exception(spec: StageSpec, exc: Exception) -> str:
    if isinstance(exc, FileNotFoundError):
        return (
            f"{spec.label} could not start because a required command or file was not "
            "found. Review the saved tool settings and the selected paths."
        )
    return str(exc)


def _build_gui() -> int:
    import tkinter as tk
    from tkinter import filedialog, messagebox, scrolledtext, ttk

    colors = {
        "navy": "#071A2B",
        "deep": "#061521",
        "surface": "#0B2740",
        "surface_alt": "#0D3151",
        "blue": "#0C4A8A",
        "cyan": "#2EA8FF",
        "text": "#F4F8FC",
        "muted": "#A9BED1",
        "line": "#264A67",
        "success": "#45D483",
        "warning": "#F7C85A",
        "error": "#FF6B72",
    }

    root = tk.Tk()
    root.title("dicomxphits 3D-CRT Workflow")
    root.geometry("1360x820")
    root.minsize(1120, 720)
    root.configure(background=colors["navy"])
    try:
        root.state("zoomed")
    except tk.TclError:
        pass

    style = ttk.Style(root)
    style.theme_use("clam")
    style.configure("App.TFrame", background=colors["navy"])
    style.configure("Header.TFrame", background=colors["deep"])
    style.configure("Sidebar.TFrame", background=colors["deep"])
    style.configure("Content.TFrame", background=colors["navy"])
    style.configure("Surface.TFrame", background=colors["surface"])
    style.configure("AltSurface.TFrame", background=colors["surface_alt"])
    style.configure(
        "TLabel",
        background=colors["navy"],
        foreground=colors["text"],
        font=("Segoe UI", 10),
    )
    style.configure(
        "Title.TLabel",
        background=colors["deep"],
        foreground=colors["text"],
        font=("Segoe UI Semibold", 17),
    )
    style.configure(
        "PageTitle.TLabel",
        background=colors["navy"],
        foreground=colors["text"],
        font=("Segoe UI Semibold", 22),
    )
    style.configure(
        "Heading.TLabel",
        background=colors["surface"],
        foreground=colors["cyan"],
        font=("Segoe UI Semibold", 12),
    )
    style.configure(
        "Surface.TLabel",
        background=colors["surface"],
        foreground=colors["text"],
        font=("Segoe UI", 10),
    )
    style.configure(
        "Muted.TLabel",
        background=colors["navy"],
        foreground=colors["muted"],
        font=("Segoe UI", 9),
    )
    style.configure(
        "SurfaceMuted.TLabel",
        background=colors["surface"],
        foreground=colors["muted"],
        font=("Segoe UI", 9),
    )
    style.configure(
        "AltSurface.TLabel",
        background=colors["surface_alt"],
        foreground=colors["text"],
        font=("Segoe UI", 10),
    )
    style.configure(
        "AltSurfaceMuted.TLabel",
        background=colors["surface_alt"],
        foreground=colors["muted"],
        font=("Segoe UI", 9),
    )
    style.configure(
        "NavTitle.TLabel",
        background=colors["deep"],
        foreground=colors["text"],
        font=("Segoe UI Semibold", 15),
    )
    style.configure(
        "NavStatus.TLabel",
        background=colors["deep"],
        foreground=colors["muted"],
        font=("Segoe UI", 9),
    )
    style.configure(
        "TEntry",
        fieldbackground=colors["deep"],
        foreground=colors["text"],
        insertcolor=colors["text"],
        bordercolor=colors["line"],
        lightcolor=colors["cyan"],
        darkcolor=colors["line"],
        padding=(8, 7),
    )
    style.map(
        "TEntry",
        fieldbackground=[("readonly", colors["surface_alt"])],
        foreground=[("readonly", colors["muted"])],
        bordercolor=[("focus", colors["cyan"])],
    )
    style.configure(
        "TCombobox",
        fieldbackground=colors["deep"],
        background=colors["surface_alt"],
        foreground=colors["text"],
        arrowcolor=colors["cyan"],
        bordercolor=colors["line"],
        padding=(8, 7),
    )
    style.configure(
        "TButton",
        background=colors["surface_alt"],
        foreground=colors["text"],
        bordercolor=colors["line"],
        padding=(12, 8),
        font=("Segoe UI Semibold", 10),
    )
    style.map(
        "TButton",
        background=[("active", colors["blue"]), ("disabled", colors["surface"])],
        foreground=[("disabled", colors["muted"])],
        bordercolor=[("focus", colors["cyan"])],
    )
    style.configure(
        "Primary.TButton",
        background="#168FF2",
        foreground=colors["text"],
        bordercolor="#168FF2",
        padding=(20, 10),
        font=("Segoe UI Semibold", 11),
    )
    style.map(
        "Primary.TButton",
        background=[("active", colors["cyan"]), ("disabled", colors["surface_alt"])],
        foreground=[("disabled", colors["muted"])],
    )
    style.configure(
        "Nav.TButton",
        background=colors["deep"],
        foreground=colors["muted"],
        borderwidth=0,
        anchor="w",
        padding=(18, 12),
        font=("Segoe UI Semibold", 11),
    )
    style.configure(
        "NavActive.TButton",
        background=colors["blue"],
        foreground=colors["text"],
        bordercolor=colors["cyan"],
        anchor="w",
        padding=(18, 12),
        font=("Segoe UI Semibold", 11),
    )
    style.map("Nav.TButton", background=[("active", colors["surface_alt"])])
    style.map("NavActive.TButton", background=[("active", colors["blue"])])
    style.configure(
        "TCheckbutton",
        background=colors["surface"],
        foreground=colors["text"],
        font=("Segoe UI", 10),
        focuscolor=colors["cyan"],
    )
    style.map("TCheckbutton", background=[("active", colors["surface"])])

    defaults = _default_values()
    values = {name: tk.StringVar(value=value) for name, value in defaults.items()}
    browse_directories = _browse_directories()
    overwrite = tk.BooleanVar(value=False)
    confirmed_non_patient_phantom = tk.BooleanVar(value=False)
    manual_handoff = tk.BooleanVar(value=False)
    handoff_status = tk.StringVar(value="Not generated")
    execution_guard = StageExecutionGuard()
    action_buttons: list[ttk.Button] = []

    def values_snapshot() -> dict[str, str]:
        return {name: variable.get() for name, variable in values.items()}

    def config_from_entries() -> GuiConfig:
        try:
            timeout = float(values["ct2phits_timeout_seconds"].get())
        except ValueError:
            timeout = math.nan
        return GuiConfig(
            rtplan_path=values["rtplan_path"].get(),
            workspace_root=values["workspace_root"].get(),
            phits_root_folder=values["phits_root_folder"].get(),
            phits_executable_path=values["phits_executable_path"].get(),
            phits2dicom_executable_path=values[
                "phits2dicom_executable_path"
            ].get(),
            rtdose_template_dicom=values["rtdose_template_dicom"].get(),
            ct_reference_dicom=values["ct_reference_dicom"].get(),
            machine_config_path=values["machine_config_path"].get(),
            geometry_mode=values["geometry_mode"].get(),
            allow_overwrite=overwrite.get(),
            ct_datfiles_root=values["ct_datfiles_root"].get(),
            confirmed_non_patient_phantom=confirmed_non_patient_phantom.get(),
            source_rtplan_path=values["source_rtplan_path"].get(),
            ct_dicom_root=values["ct_dicom_root"].get(),
            rtphits_root=values["rtphits_root"].get(),
            ct2phits_workspace_root=values["ct2phits_workspace_root"].get(),
            ct_series_instance_uid=values["ct_series_instance_uid"].get(),
            ct2phits_timeout_seconds=timeout,
        )

    app = ttk.Frame(root, style="App.TFrame")
    app.grid(row=0, column=0, sticky="nsew")
    root.columnconfigure(0, weight=1)
    root.rowconfigure(0, weight=1)
    app.columnconfigure(0, weight=1)
    app.rowconfigure(1, weight=1)

    header = ttk.Frame(app, style="Header.TFrame", padding=(22, 14))
    header.grid(row=0, column=0, sticky="ew")
    header.columnconfigure(1, weight=1)
    ttk.Label(header, text="dicomxphits 3D-CRT", style="Title.TLabel").grid(
        row=0, column=0, sticky="w"
    )
    ttk.Label(
        header,
        text="Research • Fixed-field 3D-CRT • Non-patient phantom only",
        style="NavStatus.TLabel",
    ).grid(row=0, column=1, padx=(20, 0), sticky="w")
    global_status = tk.StringVar(value="Ready")
    ttk.Label(header, textvariable=global_status, style="NavStatus.TLabel").grid(
        row=0, column=2, sticky="e"
    )

    body = ttk.Frame(app, style="App.TFrame")
    body.grid(row=1, column=0, sticky="nsew")
    body.columnconfigure(1, weight=1)
    body.rowconfigure(0, weight=1)

    sidebar = ttk.Frame(body, style="Sidebar.TFrame", width=245, padding=(0, 20))
    sidebar.grid(row=0, column=0, sticky="nsw")
    sidebar.grid_propagate(False)
    sidebar.columnconfigure(0, weight=1)
    ttk.Label(sidebar, text="3D-CRT Workflow", style="NavTitle.TLabel").grid(
        row=0, column=0, padx=18, sticky="w"
    )
    ttk.Label(sidebar, text="Separate, auditable stages", style="NavStatus.TLabel").grid(
        row=1, column=0, padx=18, pady=(2, 16), sticky="w"
    )

    content = ttk.Frame(body, style="Content.TFrame", padding=(28, 20))
    content.grid(row=0, column=1, sticky="nsew")
    content.columnconfigure(0, weight=1)
    content.rowconfigure(1, weight=1)

    page_heading = ttk.Frame(content, style="Content.TFrame")
    page_heading.grid(row=0, column=0, sticky="ew", pady=(0, 14))
    page_heading.columnconfigure(0, weight=1)
    page_title = tk.StringVar(value="CT2PHITS — Case setup")
    page_subtitle = tk.StringVar(
        value="Configure inputs and generate the verified CT2PHITS handoff."
    )
    ttk.Label(page_heading, textvariable=page_title, style="PageTitle.TLabel").grid(
        row=0, column=0, sticky="w"
    )
    ttk.Label(page_heading, textvariable=page_subtitle, style="Muted.TLabel").grid(
        row=1, column=0, sticky="w", pady=(4, 0)
    )

    page_container = ttk.Frame(content, style="Content.TFrame")
    page_container.grid(row=1, column=0, sticky="nsew")
    page_container.columnconfigure(0, weight=1)
    page_container.rowconfigure(0, weight=1)

    activity_frame = ttk.Frame(content, style="Surface.TFrame", padding=(14, 10))
    activity_frame.grid(row=2, column=0, sticky="nsew", pady=(14, 0))
    activity_frame.columnconfigure(0, weight=1)
    ttk.Label(activity_frame, text="Activity log", style="Heading.TLabel").grid(
        row=0, column=0, sticky="w", pady=(0, 6)
    )
    output = scrolledtext.ScrolledText(
        activity_frame,
        height=2,
        background=colors["deep"],
        foreground=colors["text"],
        insertbackground=colors["text"],
        selectbackground=colors["blue"],
        relief="flat",
        borderwidth=0,
        font=("Cascadia Mono", 9),
        padx=10,
        pady=8,
        wrap="word",
    )
    output.grid(row=1, column=0, sticky="nsew")
    output.tag_configure("success", foreground=colors["success"])
    output.tag_configure("warning", foreground=colors["warning"])
    output.tag_configure("error", foreground=colors["error"])
    output.tag_configure("info", foreground=colors["text"])

    def append(text: str, tag: str = "info") -> None:
        output.insert(tk.END, f"{datetime.now():%H:%M:%S}  {text}\n", tag)
        output.see(tk.END)

    def save_local_settings(*, announce: bool = False) -> None:
        try:
            path = _save_gui_settings(values_snapshot(), browse_directories)
        except OSError as exc:
            append(f"Local settings could not be saved: {exc}", "warning")
            if announce:
                messagebox.showwarning("Local settings", str(exc))
            return
        if announce:
            append(f"Local tool settings saved: {path}", "success")

    def apply_safe_suggestions() -> None:
        plan = values["source_rtplan_path"].get().strip()
        if not plan:
            return
        workspace_parent = browse_directories.get("workspace_root", "")
        suggestions = suggest_case_paths(
            plan,
            rtphits_root=values["rtphits_root"].get(),
            workspace_parent=workspace_parent,
        )
        for name, suggestion in suggestions.items():
            if not values[name].get().strip():
                values[name].set(suggestion)
        append("Suggested case paths were filled without scanning the filesystem.")

    def browse_file(name: str, *, after_select: Callable[[], None] | None = None) -> None:
        selected = filedialog.askopenfilename(
            initialdir=str(
                browse_initial_directory(name, values_snapshot(), browse_directories)
            )
        )
        if selected:
            values[name].set(selected)
            remember_browse_directory(
                name,
                selected,
                selected_is_directory=False,
                browse_directories=browse_directories,
            )
            if after_select:
                after_select()
            save_local_settings()

    def browse_dir(
        name: str,
        *,
        new_workspace: bool = False,
        after_select: Callable[[], None] | None = None,
    ) -> None:
        selected_parent = filedialog.askdirectory(
            initialdir=str(
                browse_initial_directory(name, values_snapshot(), browse_directories)
            ),
            mustexist=True,
        )
        if selected_parent:
            selected_value = selected_parent
            if new_workspace:
                source_plan = values["source_rtplan_path"].get().strip()
                selected_value = str(
                    workspace_path_from_parent(
                        selected_parent,
                        source_plan or "phantom-case.dcm",
                        name,
                    )
                )
            values[name].set(selected_value)
            remember_browse_directory(
                name,
                selected_parent,
                selected_is_directory=True,
                browse_directories=browse_directories,
            )
            if after_select:
                after_select()
            save_local_settings()

    def path_row(
        parent: ttk.Frame,
        row: int,
        label: str,
        name: str,
        *,
        directory: bool,
        helper: str = "",
        readonly: bool = False,
        new_workspace: bool = False,
        after_select: Callable[[], None] | None = None,
    ) -> tuple[ttk.Entry, ttk.Button]:
        ttk.Label(parent, text=label, style="Surface.TLabel").grid(
            row=row, column=0, padx=(0, 14), pady=(6, 2), sticky="w"
        )
        entry = ttk.Entry(parent, textvariable=values[name])
        entry.grid(row=row, column=1, padx=(0, 10), pady=(6, 2), sticky="ew")
        if readonly:
            entry.state(["readonly"])
        if directory:
            command = lambda: browse_dir(
                name, new_workspace=new_workspace, after_select=after_select
            )
        else:
            command = lambda: browse_file(name, after_select=after_select)
        button = ttk.Button(parent, text="Browse…", command=command)
        button.grid(row=row, column=2, pady=(6, 2), sticky="ew")
        if readonly:
            button.state(["disabled"])
        if helper:
            ttk.Label(parent, text=helper, style="SurfaceMuted.TLabel").grid(
                row=row + 1,
                column=1,
                columnspan=2,
                padx=(0, 10),
                pady=(0, 3),
                sticky="w",
            )
        return entry, button

    pages: dict[str, ttk.Frame] = {}
    page_meta = {
        "ct2phits": (
            "CT2PHITS — Case setup",
            "Configure inputs and generate the verified CT2PHITS handoff.",
        ),
        "workspace": (
            "Workspace — Prepare 3D-CRT",
            "Review the frozen handoff and prepare the public fixed-field workspace.",
        ),
        "phits": (
            "PHITS — Segment execution",
            "Run the prepared fixed-field segments through the explicit adapter.",
        ),
        "sumtally": (
            "Sumtally — Dose aggregation",
            "Generate and run Sumtally as separately gated stages.",
        ),
        "rtdose": (
            "RTDOSE — Conversion",
            "Prepare and run RTDOSE conversion using the reviewed template.",
        ),
    }
    nav_status = {
        "ct2phits": tk.StringVar(value="Not started"),
        "workspace": tk.StringVar(value="Not prepared"),
        "phits": tk.StringVar(value="Not run"),
        "sumtally": tk.StringVar(value="Not run"),
        "rtdose": tk.StringVar(value="Not run"),
    }
    nav_buttons: dict[str, ttk.Button] = {}

    def show_page(page_key: str) -> None:
        for key, page in pages.items():
            page.grid() if key == page_key else page.grid_remove()
            nav_buttons[key].configure(
                style="NavActive.TButton" if key == page_key else "Nav.TButton"
            )
        title, subtitle = page_meta[page_key]
        page_title.set(title)
        page_subtitle.set(subtitle)

    for index, (key, label) in enumerate(
        (
            ("ct2phits", "1   CT2PHITS"),
            ("workspace", "2   Workspace"),
            ("phits", "3   PHITS"),
            ("sumtally", "4   Sumtally"),
            ("rtdose", "5   RTDOSE"),
        ),
        start=2,
    ):
        button = ttk.Button(
            sidebar,
            text=label,
            style="Nav.TButton",
            command=lambda selected=key: show_page(selected),
        )
        button.grid(row=index * 2, column=0, sticky="ew", pady=(2, 0))
        ttk.Label(
            sidebar, textvariable=nav_status[key], style="NavStatus.TLabel"
        ).grid(row=index * 2 + 1, column=0, padx=(53, 8), pady=(0, 10), sticky="w")
        nav_buttons[key] = button

    def new_page(key: str) -> ttk.Frame:
        page = ttk.Frame(page_container, style="Content.TFrame")
        page.grid(row=0, column=0, sticky="nsew")
        page.columnconfigure(0, weight=1)
        pages[key] = page
        return page

    ct2_page = new_page("ct2phits")
    case_frame = ttk.Frame(ct2_page, style="Surface.TFrame", padding=(18, 14))
    case_frame.grid(row=0, column=0, sticky="ew")
    case_frame.columnconfigure(1, weight=1)
    ttk.Label(case_frame, text="Case setup", style="Heading.TLabel").grid(
        row=0, column=0, columnspan=3, sticky="w", pady=(0, 6)
    )
    path_row(
        case_frame,
        1,
        "RT Plan (source)",
        "source_rtplan_path",
        directory=False,
        helper="Selecting a plan can suggest empty related fields; no DICOM scan is performed.",
        after_select=apply_safe_suggestions,
    )
    path_row(
        case_frame,
        3,
        "CT DICOM folder",
        "ct_dicom_root",
        directory=True,
        helper="Choose the folder containing the non-patient phantom CT series.",
    )
    path_row(
        case_frame,
        5,
        "CT2PHITS workspace",
        "ct2phits_workspace_root",
        directory=True,
        helper="Browse selects a parent; the proposed child must be new and below RT-PHITS.",
        new_workspace=True,
    )

    tool_toggle = ttk.Button(ct2_page, text="Tool settings   •   Show saved paths")
    tool_toggle.grid(row=1, column=0, sticky="ew", pady=(10, 0))
    tool_frame = ttk.Frame(ct2_page, style="Surface.TFrame", padding=(18, 12))
    tool_frame.grid(row=2, column=0, sticky="ew", pady=(2, 0))
    tool_frame.columnconfigure(1, weight=1)
    ttk.Label(tool_frame, text="Local tool settings", style="Heading.TLabel").grid(
        row=0, column=0, columnspan=3, sticky="w", pady=(0, 6)
    )
    path_row(
        tool_frame,
        1,
        "RT-PHITS root",
        "rtphits_root",
        directory=True,
        helper="User-supplied licensed installation; the GUI does not discover it.",
        after_select=apply_safe_suggestions,
    )
    path_row(tool_frame, 3, "PHITS root", "phits_root_folder", directory=True)
    path_row(
        tool_frame,
        5,
        "PHITS executable",
        "phits_executable_path",
        directory=False,
    )
    path_row(
        tool_frame,
        7,
        "phits2dicom executable",
        "phits2dicom_executable_path",
        directory=False,
    )
    path_row(
        tool_frame,
        9,
        "RTDOSE template",
        "rtdose_template_dicom",
        directory=False,
    )
    advanced = ttk.Frame(tool_frame, style="Surface.TFrame")
    advanced.grid(row=11, column=0, columnspan=3, sticky="ew", pady=(8, 0))
    advanced.columnconfigure(1, weight=1)
    ttk.Label(advanced, text="Series UID (optional)", style="Surface.TLabel").grid(
        row=0, column=0, padx=(0, 14), sticky="w"
    )
    ttk.Entry(advanced, textvariable=values["ct_series_instance_uid"]).grid(
        row=0, column=1, padx=(0, 10), sticky="ew"
    )
    ttk.Label(advanced, text="Timeout (seconds)", style="Surface.TLabel").grid(
        row=0, column=2, padx=(10, 8), sticky="w"
    )
    ttk.Entry(
        advanced, textvariable=values["ct2phits_timeout_seconds"], width=10
    ).grid(row=0, column=3, sticky="e")
    ttk.Button(
        tool_frame,
        text="Save local settings",
        command=lambda: save_local_settings(announce=True),
    ).grid(row=12, column=2, pady=(10, 0), sticky="e")
    tool_frame.grid_remove()

    def toggle_tool_settings() -> None:
        if tool_frame.winfo_ismapped():
            tool_frame.grid_remove()
            case_frame.grid()
            handoff_frame.grid()
            ct2_actions.grid()
            tool_toggle.configure(text="Tool settings   •   Show saved paths")
        else:
            case_frame.grid_remove()
            handoff_frame.grid_remove()
            ct2_actions.grid_remove()
            tool_frame.grid()
            tool_toggle.configure(text="Tool settings   •   Back to case setup")

    tool_toggle.configure(command=toggle_tool_settings)

    handoff_frame = ttk.Frame(ct2_page, style="Surface.TFrame", padding=(18, 12))
    handoff_frame.grid(row=3, column=0, sticky="ew", pady=(10, 0))
    ttk.Label(
        handoff_frame,
        text="Derived handoff after CT2PHITS",
        style="Heading.TLabel",
    ).grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 6))
    for column, (label, name) in enumerate(
        (
            ("Frozen RT Plan", "rtplan_path"),
            ("CT reference", "ct_reference_dicom"),
            ("CT2PHITS DATfiles", "ct_datfiles_root"),
        ),
    ):
        handoff_frame.columnconfigure(column, weight=1)
        cell = ttk.Frame(handoff_frame, style="AltSurface.TFrame", padding=(10, 8))
        cell.grid(
            row=1,
            column=column,
            padx=(0 if column == 0 else 5, 0 if column == 2 else 5),
            sticky="ew",
        )
        cell.columnconfigure(0, weight=1)
        ttk.Label(cell, text=label, style="AltSurface.TLabel").grid(
            row=0, column=0, pady=(0, 4), sticky="w"
        )
        entry = ttk.Entry(cell, textvariable=values[name])
        entry.state(["readonly"])
        entry.grid(row=1, column=0, sticky="ew")
        ttk.Label(
            cell,
            textvariable=handoff_status,
            style="AltSurfaceMuted.TLabel",
        ).grid(row=2, column=0, pady=(4, 0), sticky="w")

    ct2_actions = ttk.Frame(ct2_page, style="Surface.TFrame", padding=(18, 12))
    ct2_actions.grid(row=4, column=0, sticky="ew", pady=(2, 0))
    ct2_actions.columnconfigure(0, weight=1)
    ttk.Checkbutton(
        ct2_actions,
        text="I confirm non-patient phantom data",
        variable=confirmed_non_patient_phantom,
    ).grid(row=0, column=0, sticky="w")

    workspace_page = new_page("workspace")
    workspace_frame = ttk.Frame(
        workspace_page, style="Surface.TFrame", padding=(18, 14)
    )
    workspace_frame.grid(row=0, column=0, sticky="ew")
    workspace_frame.columnconfigure(1, weight=1)
    ttk.Label(
        workspace_frame, text="3D-CRT workspace", style="Heading.TLabel"
    ).grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 6))
    path_row(
        workspace_frame,
        1,
        "3D-CRT workspace",
        "workspace_root",
        directory=True,
        helper="Browse selects a parent for a proposed new workspace outside this repository.",
        new_workspace=True,
    )
    ttk.Label(workspace_frame, text="Geometry mode", style="Surface.TLabel").grid(
        row=3, column=0, padx=(0, 14), pady=6, sticky="w"
    )
    ttk.Combobox(
        workspace_frame,
        textvariable=values["geometry_mode"],
        values=GEOMETRY_MODES,
        state="readonly",
    ).grid(row=3, column=1, padx=(0, 10), pady=6, sticky="ew")
    path_row(
        workspace_frame,
        4,
        "Machine config (optional)",
        "machine_config_path",
        directory=False,
        helper="Leave empty to use the built-in public rectangular research model.",
    )
    ttk.Checkbutton(
        workspace_frame,
        text="Allow overwrite of downstream stage summaries",
        variable=overwrite,
    ).grid(row=6, column=1, sticky="w", pady=(6, 2))

    manual_frame = ttk.Frame(
        workspace_page, style="Surface.TFrame", padding=(18, 12)
    )
    manual_frame.grid(row=1, column=0, sticky="ew", pady=(10, 0))
    manual_frame.columnconfigure(1, weight=1)
    ttk.Checkbutton(
        manual_frame,
        text="Use an existing validated CT2PHITS handoff (advanced)",
        variable=manual_handoff,
    ).grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 6))
    manual_controls: list[tuple[ttk.Entry, ttk.Button]] = []
    manual_controls.append(
        path_row(
            manual_frame,
            1,
            "Frozen RT Plan",
            "rtplan_path",
            directory=False,
        )
    )
    manual_controls.append(
        path_row(
            manual_frame,
            2,
            "CT reference",
            "ct_reference_dicom",
            directory=False,
        )
    )
    manual_controls.append(
        path_row(
            manual_frame,
            3,
            "DATfiles",
            "ct_datfiles_root",
            directory=True,
        )
    )

    def update_manual_controls(*_args: object) -> None:
        enabled = manual_handoff.get()
        for entry, button in manual_controls:
            if enabled:
                entry.state(["!readonly"])
                button.state(["!disabled"])
            else:
                entry.state(["readonly"])
                button.state(["disabled"])
        if enabled:
            handoff_status.set("Manual handoff")
        elif handoff_status.get() == "Manual handoff":
            handoff_status.set("Not generated")

    manual_handoff.trace_add("write", update_manual_controls)
    update_manual_controls()

    workspace_action_frame = ttk.Frame(
        workspace_page, style="Surface.TFrame", padding=(18, 12)
    )
    workspace_action_frame.grid(row=2, column=0, sticky="ew", pady=(2, 0))
    workspace_action_frame.columnconfigure(0, weight=1)
    ttk.Label(
        workspace_action_frame,
        text=geometry_mode_guidance(GEOMETRY_MODE_RECTANGULAR_3DCRT),
        style="SurfaceMuted.TLabel",
        wraplength=780,
    ).grid(row=0, column=0, sticky="w")

    phits_page = new_page("phits")
    phits_frame = ttk.Frame(phits_page, style="Surface.TFrame", padding=(18, 14))
    phits_frame.grid(row=0, column=0, sticky="ew")
    phits_frame.columnconfigure(1, weight=1)
    ttk.Label(phits_frame, text="PHITS execution", style="Heading.TLabel").grid(
        row=0, column=0, columnspan=3, sticky="w", pady=(0, 6)
    )
    path_row(
        phits_frame,
        1,
        "PHITS executable",
        "phits_executable_path",
        directory=False,
    )
    ttk.Label(
        phits_frame,
        text="PHITS runs only through the explicit segment adapter and prepared workspace.",
        style="SurfaceMuted.TLabel",
    ).grid(row=3, column=1, columnspan=2, sticky="w", pady=(6, 10))

    sumtally_page = new_page("sumtally")
    sumtally_frame = ttk.Frame(
        sumtally_page, style="Surface.TFrame", padding=(18, 14)
    )
    sumtally_frame.grid(row=0, column=0, sticky="ew")
    sumtally_frame.columnconfigure(1, weight=1)
    ttk.Label(
        sumtally_frame, text="Sumtally stages", style="Heading.TLabel"
    ).grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 6))
    path_row(
        sumtally_frame,
        1,
        "PHITS root",
        "phits_root_folder",
        directory=True,
    )
    path_row(
        sumtally_frame,
        2,
        "PHITS executable",
        "phits_executable_path",
        directory=False,
    )

    rtdose_page = new_page("rtdose")
    rtdose_frame = ttk.Frame(
        rtdose_page, style="Surface.TFrame", padding=(18, 14)
    )
    rtdose_frame.grid(row=0, column=0, sticky="ew")
    rtdose_frame.columnconfigure(1, weight=1)
    ttk.Label(rtdose_frame, text="RTDOSE conversion", style="Heading.TLabel").grid(
        row=0, column=0, columnspan=3, sticky="w", pady=(0, 6)
    )
    path_row(
        rtdose_frame,
        1,
        "RTDOSE template",
        "rtdose_template_dicom",
        directory=False,
    )
    path_row(
        rtdose_frame,
        2,
        "CT reference",
        "ct_reference_dicom",
        directory=False,
        readonly=True,
    )
    path_row(
        rtdose_frame,
        3,
        "phits2dicom executable",
        "phits2dicom_executable_path",
        directory=False,
    )

    stage_to_nav = {
        "run_ct2phits": "ct2phits",
        "prepare_workspace": "workspace",
        "run_segments": "phits",
        "generate_sumtally": "sumtally",
        "run_sumtally": "sumtally",
        "prepare_rtdose": "rtdose",
        "run_rtdose": "rtdose",
    }

    def set_busy(stage_key: str | None) -> None:
        if stage_key is None:
            execution_guard.finish()
        else:
            execution_guard.begin(stage_key)
        busy = stage_key is not None
        for button in action_buttons:
            button.state(["disabled"] if busy else ["!disabled"])
        global_status.set(
            f"Running {stage_by_key(stage_key).label}…" if stage_key else "Ready"
        )

    def finish_stage_error(spec: StageSpec, message: str, *, validation: bool) -> None:
        nav_status[stage_to_nav[spec.key]].set("Validation failed" if validation else "Failed")
        append(
            f"{spec.label}: {'validation failed' if validation else 'failed'}: {message}",
            "error",
        )
        messagebox.showerror(spec.label, message)
        set_busy(None)

    def finish_stage_success(spec: StageSpec, result: StageResult) -> None:
        status = _stage_status(result)
        success = result.return_code == 0 and status in {
            "completed",
            "success",
            "prepared",
        }
        if not success:
            failure_reason = None
            if result.summary:
                candidate = result.summary.get("failure_reason")
                if isinstance(candidate, str) and candidate.strip():
                    failure_reason = candidate.strip()
            message = (
                failure_reason
                or result.stderr.strip()
                or f"{spec.label} returned {status}. Review {result.summary_path}."
            )
            nav_status[stage_to_nav[spec.key]].set("Failed")
            append(
                f"{spec.label}: failed: {message}; summary: {result.summary_path}",
                "error",
            )
            messagebox.showerror(spec.label, message)
            set_busy(None)
            return
        if spec.key == "run_ct2phits" and success:
            try:
                handoff = _ct2phits_handoff_from_result(result)
            except GuiValidationError as exc:
                finish_stage_error(spec, str(exc), validation=False)
                return
            for name, value in handoff.items():
                values[name].set(value)
            manual_handoff.set(False)
            handoff_status.set("Verified frozen handoff")
            append("Frozen CT2PHITS handoff applied to downstream preparation.", "success")
        nav_status[stage_to_nav[spec.key]].set(
            "Completed" if success else status.replace("_", " ").title()
        )
        append(
            f"{spec.label}: {status}; summary: {result.summary_path}",
            "success" if success else "warning",
        )
        if spec.key == "prepare_workspace":
            append(geometry_mode_guidance(geometry_mode_value(config_from_entries())))
        if result.stderr:
            append(result.stderr.strip(), "warning")
        set_busy(None)

    def start_stage(stage_key: str) -> None:
        if execution_guard.active_stage is not None:
            append("Another stage is already running.", "warning")
            return
        spec = stage_by_key(stage_key)
        config = config_from_entries()
        try:
            validate_stage(config, spec)
        except GuiValidationError as exc:
            finish_stage_error(spec, str(exc), validation=True)
            return
        set_busy(stage_key)
        nav_status[stage_to_nav[stage_key]].set("Running")
        append(f"{spec.label}: started")

        def worker() -> None:
            try:
                result = run_stage(config, stage_key)
            except Exception as exc:
                message = _friendly_exception(spec, exc)
                root.after(
                    0,
                    lambda: finish_stage_error(spec, message, validation=False),
                )
                return
            root.after(0, lambda: finish_stage_success(spec, result))

        threading.Thread(target=worker, daemon=True).start()

    ct2_button = ttk.Button(
        ct2_actions,
        text="Run CT2PHITS",
        style="Primary.TButton",
        command=lambda: start_stage("run_ct2phits"),
    )
    ct2_button.grid(row=0, column=1, sticky="e")
    action_buttons.append(ct2_button)

    workspace_button = ttk.Button(
        workspace_action_frame,
        text="Prepare workspace",
        style="Primary.TButton",
        command=lambda: start_stage("prepare_workspace"),
    )
    workspace_button.grid(row=0, column=1, padx=(18, 0), sticky="e")
    action_buttons.append(workspace_button)

    phits_button = ttk.Button(
        phits_frame,
        text="Run PHITS segments",
        style="Primary.TButton",
        command=lambda: start_stage("run_segments"),
    )
    phits_button.grid(row=4, column=2, pady=(10, 0), sticky="e")
    action_buttons.append(phits_button)

    sumtally_actions = ttk.Frame(
        sumtally_page, style="Surface.TFrame", padding=(18, 12)
    )
    sumtally_actions.grid(row=1, column=0, sticky="ew", pady=(2, 0))
    sumtally_actions.columnconfigure(0, weight=1)
    sumtally_generate_button = ttk.Button(
        sumtally_actions,
        text="Generate Sumtally",
        command=lambda: start_stage("generate_sumtally"),
    )
    sumtally_generate_button.grid(row=0, column=1, padx=(8, 4), sticky="e")
    action_buttons.append(sumtally_generate_button)
    sumtally_run_button = ttk.Button(
        sumtally_actions,
        text="Run Sumtally",
        style="Primary.TButton",
        command=lambda: start_stage("run_sumtally"),
    )
    sumtally_run_button.grid(row=0, column=2, padx=(4, 0), sticky="e")
    action_buttons.append(sumtally_run_button)

    rtdose_actions = ttk.Frame(
        rtdose_page, style="Surface.TFrame", padding=(18, 12)
    )
    rtdose_actions.grid(row=1, column=0, sticky="ew", pady=(2, 0))
    rtdose_actions.columnconfigure(0, weight=1)
    rtdose_prepare_button = ttk.Button(
        rtdose_actions,
        text="Prepare RTDOSE",
        command=lambda: start_stage("prepare_rtdose"),
    )
    rtdose_prepare_button.grid(row=0, column=1, padx=(8, 4), sticky="e")
    action_buttons.append(rtdose_prepare_button)
    rtdose_run_button = ttk.Button(
        rtdose_actions,
        text="Run RTDOSE",
        style="Primary.TButton",
        command=lambda: start_stage("run_rtdose"),
    )
    rtdose_run_button.grid(row=0, column=2, padx=(4, 0), sticky="e")
    action_buttons.append(rtdose_run_button)

    def close_gui() -> None:
        if execution_guard.active_stage is not None:
            messagebox.showwarning(
                "Stage running",
                "Wait for the active stage to finish before closing the GUI.",
            )
            return
        save_local_settings()
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", close_gui)
    show_page("ct2phits")
    append(
        "Ready. Select a source RT Plan and CT folder, review saved tool settings, "
        "then run CT2PHITS."
    )
    root.mainloop()
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    if list(argv) in (["-h"], ["--help"]):
        print(GUI_HELP_TEXT, end="")
        return 0
    if argv:
        print("dicomxphits-gui does not accept command-line arguments.", file=sys.stderr)
        return 2
    return _build_gui()


if __name__ == "__main__":
    raise SystemExit(main())
