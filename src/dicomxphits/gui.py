from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Sequence


PUBLIC_ROOT = Path(__file__).resolve().parents[2]
GEOMETRY_MODE_RECTANGULAR_3DCRT = "rectangular_3dcrt"
GEOMETRY_MODES = (GEOMETRY_MODE_RECTANGULAR_3DCRT,)
GUI_DEFAULTS_ENV_VAR = "DICOMXPHITS_GUI_DEFAULTS_JSON"
GUI_DEFAULTS_FILE_NAME = "dicomxphits.gui.local.json"
GUI_HELP_TEXT = """\
usage: dicomxphits-gui [-h]

Launch the dicomxphits v1.0.0 GUI for validated 3D-CRT fixed-field
workflows only. IMRT, dynamic MLC delivery, and VMAT are not supported
as validated public workflows.

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


@dataclass(frozen=True)
class StageSpec:
    key: str
    label: str
    command: tuple[str, ...]
    required_paths: tuple[tuple[str, str, bool], ...]
    summary_relative_path: Path
    workspace_must_exist: bool
    fail_on_existing_summary: bool


@dataclass(frozen=True)
class StageResult:
    stage_key: str
    command: list[str]
    return_code: int
    summary_path: Path
    summary: dict[str, object] | None
    stdout: str
    stderr: str


def public_root() -> Path:
    return PUBLIC_ROOT


def stage_specs() -> tuple[StageSpec, ...]:
    workspace_only = (("workspace_root", "workspace root", True),)
    phits_root = (("phits_root_folder", "PHITS root folder", True),)
    phits_executable = (("phits_executable_path", "PHITS executable path", False),)
    phits2dicom_executable = (("phits2dicom_executable_path", "phits2dicom executable path", False),)
    return (
        StageSpec(
            key="prepare_workspace",
            label="Workspace Prepare",
            command=("dicomxphits-prepare-3dcrt-workspace",),
            required_paths=(
                ("rtplan_path", "RTPLAN path", False),
                ("workspace_root", "workspace root", True),
                ("ct_datfiles_root", "CT2PHITS DATfiles directory", True),
                ("ct_reference_dicom", "CT reference DICOM", False),
                *phits_root,
                *phits_executable,
                *phits2dicom_executable,
            ),
            summary_relative_path=Path("analysis") / "public_preparation_workspace_summary.json",
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
            summary_relative_path=Path("analysis") / "rtdose_conversion_prepare_summary.json",
            workspace_must_exist=True,
            fail_on_existing_summary=True,
        ),
        StageSpec(
            key="run_rtdose",
            label="RTDOSE Run",
            command=("dicomxphits-run-rtdose",),
            required_paths=(*workspace_only, *phits2dicom_executable),
            summary_relative_path=Path("analysis") / "rtdose_conversion_execution_summary.json",
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


def validate_stage(config: GuiConfig, spec: StageSpec, *, public_tree: Path | None = None) -> Path:
    public_tree = public_tree or public_root()
    geometry_mode = geometry_mode_value(config)
    required_paths = spec.required_paths
    if spec.key == "prepare_workspace":
        if geometry_mode not in GEOMETRY_MODES:
            raise GuiValidationError(f"unknown geometry_mode: {geometry_mode}")
        required_paths = tuple(
            requirement
            for requirement in required_paths
            if requirement[0] not in {"phits_executable_path", "phits2dicom_executable_path"}
        )
        if not config.confirmed_non_patient_phantom:
            raise GuiValidationError(
                "Confirm that the CT2PHITS DATfiles and CT reference come from "
                "non-patient phantom data"
            )
        if (
            geometry_mode == GEOMETRY_MODE_RECTANGULAR_3DCRT
            and _path_value(config, "machine_config_path")
        ):
            machine_config = _resolved_path(config, "machine_config_path")
            if not machine_config.is_file():
                raise GuiValidationError("machine_config_path must be an existing regular file")

    missing: list[str] = []
    for field_name, label, expect_dir in required_paths:
        if field_name == "workspace_root":
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

    workspace = _resolved_path(config, "workspace_root")
    if _inside_public_tree(workspace, public_tree):
        raise GuiValidationError("workspace root must be outside public_release/dicomxphits")
    if spec.workspace_must_exist and not workspace.is_dir():
        raise GuiValidationError("workspace root does not exist")
    if not spec.workspace_must_exist and not workspace.exists() and not workspace.parent.is_dir():
        raise GuiValidationError("workspace parent directory does not exist")
    if not spec.workspace_must_exist and workspace.exists() and any(workspace.iterdir()) and not config.allow_overwrite:
        raise GuiValidationError("workspace root already contains files")
    summary_path = workspace / spec.summary_relative_path
    if spec.fail_on_existing_summary and summary_path.exists() and not config.allow_overwrite:
        raise GuiValidationError(f"stage output already exists: {summary_path}")
    return workspace


def build_stage_command(config: GuiConfig, spec: StageSpec) -> list[str]:
    workspace = _resolved_path(config, "workspace_root")
    command = [*spec.command, "--workspace-root", str(workspace)]
    if spec.key == "prepare_workspace":
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
            command.extend(["--machine-config-path", str(_resolved_path(config, "machine_config_path"))])
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
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
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
        "rtplan_path": "",
        "workspace_root": "",
        "phits_root_folder": "",
        "phits_executable_path": "",
        "phits2dicom_executable_path": "",
        "rtdose_template_dicom": "",
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


def _default_values(defaults_path: Path | None = None) -> dict[str, str]:
    values = _base_default_values()
    path = defaults_path or gui_defaults_path()
    try:
        with path.open("r", encoding="utf-8-sig") as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return values
    if not isinstance(data, dict):
        return values
    for key in values:
        value = data.get(key)
        if isinstance(value, str):
            values[key] = value
    legacy_ct_root = data.get("ct_asset_root")
    if not values["ct_datfiles_root"] and isinstance(legacy_ct_root, str):
        values["ct_datfiles_root"] = legacy_ct_root
    if values["geometry_mode"] not in GEOMETRY_MODES:
        values["geometry_mode"] = GEOMETRY_MODE_RECTANGULAR_3DCRT
    return values


def _build_gui() -> int:
    import tkinter as tk
    from tkinter import filedialog, messagebox, scrolledtext

    root = tk.Tk()
    root.title("dicomxphits public 3D-CRT")
    values = {name: tk.StringVar(value=value) for name, value in _default_values().items()}
    overwrite = tk.BooleanVar(value=False)
    confirmed_non_patient_phantom = tk.BooleanVar(value=False)
    output = scrolledtext.ScrolledText(root, width=110, height=18)

    def config_from_entries() -> GuiConfig:
        return GuiConfig(
            rtplan_path=values["rtplan_path"].get(),
            workspace_root=values["workspace_root"].get(),
            phits_root_folder=values["phits_root_folder"].get(),
            phits_executable_path=values["phits_executable_path"].get(),
            phits2dicom_executable_path=values["phits2dicom_executable_path"].get(),
            rtdose_template_dicom=values["rtdose_template_dicom"].get(),
            ct_reference_dicom=values["ct_reference_dicom"].get(),
            machine_config_path=values["machine_config_path"].get(),
            geometry_mode=values["geometry_mode"].get(),
            allow_overwrite=overwrite.get(),
            ct_datfiles_root=values["ct_datfiles_root"].get(),
            confirmed_non_patient_phantom=confirmed_non_patient_phantom.get(),
        )

    def append(text: str) -> None:
        output.insert(tk.END, text + "\n")
        output.see(tk.END)

    def browse_file(name: str) -> None:
        selected = filedialog.askopenfilename()
        if selected:
            values[name].set(selected)

    def browse_dir(name: str) -> None:
        selected = filedialog.askdirectory()
        if selected:
            values[name].set(selected)

    def start_stage(stage_key: str) -> None:
        spec = stage_by_key(stage_key)
        try:
            result = run_stage(config_from_entries(), stage_key)
        except GuiValidationError as exc:
            messagebox.showerror(spec.label, str(exc))
            append(f"{spec.label}: validation failed: {exc}")
            return
        except Exception as exc:
            messagebox.showerror(spec.label, str(exc))
            append(f"{spec.label}: failed: {exc}")
            return
        status = result.summary.get("stage_status") if result.summary else f"return_code={result.return_code}"
        append(f"{spec.label}: {status}")
        if spec.key == "prepare_workspace":
            append(geometry_mode_guidance(geometry_mode_value(config_from_entries())))
        append(f"summary: {result.summary_path}")
        if result.stderr:
            append(result.stderr.strip())

    row = 0
    tk.Label(root, text="Geometry mode", anchor="w").grid(row=row, column=0, padx=6, pady=3, sticky="ew")
    tk.OptionMenu(root, values["geometry_mode"], *GEOMETRY_MODES).grid(
        row=row,
        column=1,
        padx=6,
        pady=3,
        sticky="w",
    )
    tk.Label(
        root,
        text="rectangular_3dcrt uses the built-in public model; machine config is an optional override",
        anchor="w",
    ).grid(row=row, column=2, padx=6, pady=3, sticky="ew")
    row += 1
    fields = (
        ("rtplan_path", "RTPLAN path", browse_file),
        ("workspace_root", "Workspace root", browse_dir),
        ("phits_root_folder", "PHITS root folder", browse_dir),
        ("phits_executable_path", "PHITS executable path", browse_file),
        ("phits2dicom_executable_path", "phits2dicom executable path", browse_file),
        ("rtdose_template_dicom", "RTDOSE template DICOM", browse_file),
        ("ct_reference_dicom", "CT reference DICOM", browse_file),
        (
            "ct_datfiles_root",
            "CT2PHITS DATfiles directory (output from ct2phits.exe)",
            browse_dir,
        ),
        ("machine_config_path", "machine config path (optional rectangular override)", browse_file),
    )
    for name, label, browse in fields:
        tk.Label(root, text=label, anchor="w").grid(row=row, column=0, padx=6, pady=3, sticky="ew")
        tk.Entry(root, textvariable=values[name], width=90).grid(row=row, column=1, padx=6, pady=3, sticky="ew")
        tk.Button(root, text="Browse", command=lambda n=name, b=browse: b(n)).grid(row=row, column=2, padx=6, pady=3)
        row += 1
    tk.Checkbutton(root, text="Allow overwrite", variable=overwrite).grid(row=row, column=1, sticky="w")
    row += 1
    tk.Checkbutton(
        root,
        text=(
            "I confirm the CT2PHITS DATfiles and CT reference are from "
            "non-patient phantom data"
        ),
        variable=confirmed_non_patient_phantom,
    ).grid(row=row, column=1, sticky="w")
    row += 1
    stage_frame = tk.Frame(root)
    stage_frame.grid(row=row, column=0, columnspan=3, padx=6, pady=6, sticky="ew")
    for index, spec in enumerate(stage_specs()):
        tk.Button(stage_frame, text=spec.label, command=lambda key=spec.key: start_stage(key)).grid(
            row=0,
            column=index,
            padx=3,
            pady=3,
        )
    row += 1
    output.grid(row=row, column=0, columnspan=3, padx=6, pady=6, sticky="nsew")
    root.columnconfigure(1, weight=1)
    root.rowconfigure(row, weight=1)
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
