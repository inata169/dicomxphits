from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping


TOOL_PROFILE_STANDARD = "standard"
TOOL_PROFILE_CUSTOM = "custom"
TOOL_PROFILE_MODES = (TOOL_PROFILE_STANDARD, TOOL_PROFILE_CUSTOM)
STANDARD_WINDOWS_LAYOUT_ID = "phits-3.35-windows"

PHITS_EXECUTABLE_RELATIVE = Path("bin") / "phits_win.exe"
RTPHITS_ROOT_RELATIVE = Path("utility") / "RTphits"
RTPHITS_BATCH_RELATIVE = Path("RTphits_win.bat")
RTPHITS_HU_TABLE_RELATIVE = Path("data") / "HumanVoxelTable.data"
PHITS2DICOM_BIN_RELATIVE = Path("bin")

ROLE_PHITS_ROOT = "PHITS root"
ROLE_RTPHITS_ROOT = "RT-PHITS root"
ROLE_RTPHITS_BATCH = "RT-PHITS batch"
ROLE_HU_TABLE = "CT2PHITS HU table"
ROLE_PHITS_EXECUTABLE = "PHITS executable"
ROLE_PHITS2DICOM_EXECUTABLE = "phits2dicom executable"

ALL_TOOL_ROLES = (
    ROLE_PHITS_ROOT,
    ROLE_RTPHITS_ROOT,
    ROLE_RTPHITS_BATCH,
    ROLE_HU_TABLE,
    ROLE_PHITS_EXECUTABLE,
    ROLE_PHITS2DICOM_EXECUTABLE,
)

STAGE_TOOL_ROLES = {
    "run_ct2phits": (
        ROLE_RTPHITS_ROOT,
        ROLE_RTPHITS_BATCH,
        ROLE_HU_TABLE,
    ),
    "prepare_workspace": (ROLE_PHITS_ROOT,),
    "run_segments": (ROLE_PHITS_EXECUTABLE,),
    "generate_sumtally": (ROLE_PHITS_ROOT,),
    "run_sumtally": (ROLE_PHITS_EXECUTABLE,),
    "prepare_rtdose": (),
    "run_rtdose": (ROLE_PHITS2DICOM_EXECUTABLE,),
}


@dataclass(frozen=True)
class ToolProfileIssue:
    role: str
    message: str


@dataclass(frozen=True)
class ToolProfileResolution:
    mode: str
    layout_id: str | None
    phits_installation_folder: str
    phits_root_folder: str
    rtphits_root: str
    phits_executable_path: str
    phits2dicom_executable_path: str
    issues: tuple[ToolProfileIssue, ...]

    @property
    def ready(self) -> bool:
        return not self.issues

    def values(self) -> dict[str, str]:
        return {
            "phits_installation_folder": self.phits_installation_folder,
            "phits_root_folder": self.phits_root_folder,
            "rtphits_root": self.rtphits_root,
            "phits_executable_path": self.phits_executable_path,
            "phits2dicom_executable_path": self.phits2dicom_executable_path,
        }

    def issues_for_stage(self, stage_key: str) -> tuple[ToolProfileIssue, ...]:
        roles = STAGE_TOOL_ROLES.get(stage_key, ALL_TOOL_ROLES)
        return tuple(issue for issue in self.issues if issue.role in roles)

    def ready_for_stage(self, stage_key: str) -> bool:
        return not self.issues_for_stage(stage_key)


def _path_text(path: Path) -> str:
    return str(path.expanduser().resolve())


def _resolved_path_or_none(value: str | Path) -> Path | None:
    try:
        return Path(value).expanduser().resolve()
    except (OSError, RuntimeError, ValueError):
        return None


def _is_within(path: Path, root: Path) -> bool:
    resolved = _resolved_path_or_none(path)
    return resolved is not None and (resolved == root or root in resolved.parents)


def _unresolved_standard_profile(
    raw_root: str,
    root_message: str,
) -> ToolProfileResolution:
    dependent_messages = (
        (ROLE_RTPHITS_ROOT, "RT-PHITS root is unresolved."),
        (ROLE_RTPHITS_BATCH, "RT-PHITS batch is unresolved."),
        (ROLE_HU_TABLE, "CT2PHITS HU table is unresolved."),
        (ROLE_PHITS_EXECUTABLE, "PHITS executable is unresolved."),
        (ROLE_PHITS2DICOM_EXECUTABLE, "phits2dicom is unresolved."),
    )
    return ToolProfileResolution(
        mode=TOOL_PROFILE_STANDARD,
        layout_id=STANDARD_WINDOWS_LAYOUT_ID,
        phits_installation_folder=raw_root,
        phits_root_folder="",
        rtphits_root="",
        phits_executable_path="",
        phits2dicom_executable_path="",
        issues=(
            ToolProfileIssue(ROLE_PHITS_ROOT, root_message),
            *(ToolProfileIssue(role, message) for role, message in dependent_messages),
        ),
    )


def _phits2dicom_candidates(directory: Path) -> tuple[Path, ...]:
    try:
        children = tuple(directory.iterdir())
    except OSError:
        return ()
    return tuple(
        sorted(
            (
                child
                for child in children
                if child.is_file()
                and child.name.lower().startswith("phits2dicom")
                and child.suffix.lower() == ".exe"
            ),
            key=lambda path: path.name.lower(),
        )
    )


def resolve_standard_tool_profile(
    phits_installation_folder: str | Path,
) -> ToolProfileResolution:
    raw_root = str(phits_installation_folder).strip()
    if not raw_root:
        return _unresolved_standard_profile(
            "",
            "Select the PHITS installation folder.",
        )

    root = _resolved_path_or_none(raw_root)
    if root is None:
        return _unresolved_standard_profile(
            raw_root,
            "PHITS installation folder contains an invalid filesystem path.",
        )
    rtphits_root = root / RTPHITS_ROOT_RELATIVE
    phits_executable = root / PHITS_EXECUTABLE_RELATIVE
    phits2dicom_path = ""
    issues: list[ToolProfileIssue] = []
    phits_executable_within_root = _is_within(phits_executable, root)
    rtphits_within_root = _is_within(rtphits_root, root)

    if not root.is_dir():
        issues.append(
            ToolProfileIssue(
                ROLE_PHITS_ROOT,
                f"PHITS installation folder does not exist: {root}",
            )
        )
    if not phits_executable_within_root:
        issues.append(
            ToolProfileIssue(
                ROLE_PHITS_EXECUTABLE,
                "Standard PHITS executable escapes the selected installation folder.",
            )
        )
    elif not phits_executable.is_file():
        issues.append(
            ToolProfileIssue(
                ROLE_PHITS_EXECUTABLE,
                f"Missing standard PHITS executable: {PHITS_EXECUTABLE_RELATIVE.as_posix()}",
            )
        )
    if not rtphits_within_root:
        issues.append(
            ToolProfileIssue(
                ROLE_RTPHITS_ROOT,
                "Standard RT-PHITS folder escapes the selected installation folder.",
            )
        )
        issues.append(
            ToolProfileIssue(
                ROLE_PHITS2DICOM_EXECUTABLE,
                "Cannot resolve phits2dicom outside the selected installation folder.",
            )
        )
    elif not rtphits_root.is_dir():
        issues.append(
            ToolProfileIssue(
                ROLE_RTPHITS_ROOT,
                f"Missing standard RT-PHITS folder: {RTPHITS_ROOT_RELATIVE.as_posix()}",
            )
        )
        issues.append(
            ToolProfileIssue(
                ROLE_PHITS2DICOM_EXECUTABLE,
                "Cannot resolve phits2dicom because the standard RT-PHITS "
                "folder is missing.",
            )
        )
    else:
        batch = rtphits_root / RTPHITS_BATCH_RELATIVE
        if not _is_within(batch, root):
            issues.append(
                ToolProfileIssue(
                    ROLE_RTPHITS_BATCH,
                    "RT-PHITS batch escapes the selected installation folder.",
                )
            )
        elif not batch.is_file():
            issues.append(
                ToolProfileIssue(
                    ROLE_RTPHITS_BATCH,
                    f"Missing RT-PHITS batch: {RTPHITS_BATCH_RELATIVE.as_posix()}",
                )
            )
        table = rtphits_root / RTPHITS_HU_TABLE_RELATIVE
        if not _is_within(table, root):
            issues.append(
                ToolProfileIssue(
                    ROLE_HU_TABLE,
                    "CT2PHITS HU table escapes the selected installation folder.",
                )
            )
        elif not table.is_file():
            issues.append(
                ToolProfileIssue(
                    ROLE_HU_TABLE,
                    "Missing CT2PHITS HU table: "
                    + RTPHITS_HU_TABLE_RELATIVE.as_posix(),
                )
            )
        bin_directory = rtphits_root / PHITS2DICOM_BIN_RELATIVE
        if not _is_within(bin_directory, root):
            issues.append(
                ToolProfileIssue(
                    ROLE_PHITS2DICOM_EXECUTABLE,
                    "phits2dicom bin folder escapes the selected installation folder.",
                )
            )
        else:
            candidates = _phits2dicom_candidates(bin_directory)
            escaped = tuple(path for path in candidates if not _is_within(path, root))
            if escaped:
                rendered = ", ".join(path.name for path in escaped)
                issues.append(
                    ToolProfileIssue(
                        ROLE_PHITS2DICOM_EXECUTABLE,
                        f"phits2dicom candidate escapes the installation: {rendered}",
                    )
                )
            elif len(candidates) == 1:
                phits2dicom_path = _path_text(candidates[0])
            elif not candidates:
                issues.append(
                    ToolProfileIssue(
                        ROLE_PHITS2DICOM_EXECUTABLE,
                        "No phits2dicom*.exe file was found directly below "
                        + (
                            RTPHITS_ROOT_RELATIVE / PHITS2DICOM_BIN_RELATIVE
                        ).as_posix(),
                    )
                )
            else:
                rendered = ", ".join(path.name for path in candidates)
                issues.append(
                    ToolProfileIssue(
                        ROLE_PHITS2DICOM_EXECUTABLE,
                        f"Multiple phits2dicom executables were found: {rendered}",
                    )
                )

    return ToolProfileResolution(
        mode=TOOL_PROFILE_STANDARD,
        layout_id=STANDARD_WINDOWS_LAYOUT_ID,
        phits_installation_folder=_path_text(root),
        phits_root_folder=_path_text(root),
        rtphits_root=_path_text(rtphits_root) if rtphits_within_root else "",
        phits_executable_path=(
            _path_text(phits_executable) if phits_executable_within_root else ""
        ),
        phits2dicom_executable_path=phits2dicom_path,
        issues=tuple(issues),
    )


def validate_custom_tool_profile(
    values: Mapping[str, str],
) -> ToolProfileResolution:
    paths: dict[str, Path] = {}
    for name in (
        "phits_root_folder",
        "rtphits_root",
        "phits_executable_path",
        "phits2dicom_executable_path",
    ):
        raw_value = str(values.get(name, "")).strip()
        if raw_value:
            resolved = _resolved_path_or_none(raw_value)
            if resolved is not None:
                paths[name] = resolved
    issues: list[ToolProfileIssue] = []

    phits_root = paths.get("phits_root_folder")
    if phits_root is None or not phits_root.is_dir():
        issues.append(
            ToolProfileIssue(ROLE_PHITS_ROOT, "Custom PHITS root must be an existing folder.")
        )

    rtphits_root = paths.get("rtphits_root")
    if rtphits_root is None or not rtphits_root.is_dir():
        issues.append(
            ToolProfileIssue(
                ROLE_RTPHITS_ROOT,
                "Custom RT-PHITS root must be an existing folder.",
            )
        )
    else:
        if not (rtphits_root / RTPHITS_BATCH_RELATIVE).is_file():
            issues.append(
                ToolProfileIssue(
                    ROLE_RTPHITS_BATCH,
                    f"Custom RT-PHITS root is missing {RTPHITS_BATCH_RELATIVE.as_posix()}.",
                )
            )
        if not (rtphits_root / RTPHITS_HU_TABLE_RELATIVE).is_file():
            issues.append(
                ToolProfileIssue(
                    ROLE_HU_TABLE,
                    "Custom RT-PHITS root is missing "
                    + RTPHITS_HU_TABLE_RELATIVE.as_posix()
                    + ".",
                )
            )

    phits_executable = paths.get("phits_executable_path")
    if phits_executable is None or not phits_executable.is_file():
        issues.append(
            ToolProfileIssue(
                ROLE_PHITS_EXECUTABLE,
                "Custom PHITS executable must be an existing file.",
            )
        )

    phits2dicom_executable = paths.get("phits2dicom_executable_path")
    if phits2dicom_executable is None or not phits2dicom_executable.is_file():
        issues.append(
            ToolProfileIssue(
                ROLE_PHITS2DICOM_EXECUTABLE,
                "Custom phits2dicom executable must be an existing file.",
            )
        )

    return ToolProfileResolution(
        mode=TOOL_PROFILE_CUSTOM,
        layout_id=None,
        phits_installation_folder=str(
            values.get("phits_installation_folder", "")
        ).strip(),
        phits_root_folder=str(phits_root) if phits_root is not None else "",
        rtphits_root=str(rtphits_root) if rtphits_root is not None else "",
        phits_executable_path=(
            str(phits_executable) if phits_executable is not None else ""
        ),
        phits2dicom_executable_path=(
            str(phits2dicom_executable)
            if phits2dicom_executable is not None
            else ""
        ),
        issues=tuple(issues),
    )


def resolve_tool_profile(values: Mapping[str, str]) -> ToolProfileResolution:
    mode = str(values.get("tool_profile_mode", TOOL_PROFILE_STANDARD)).strip()
    if mode == TOOL_PROFILE_CUSTOM:
        return validate_custom_tool_profile(values)
    return resolve_standard_tool_profile(
        str(values.get("phits_installation_folder", ""))
    )


def standard_profile_matches_values(values: Mapping[str, str]) -> bool:
    root = str(values.get("phits_root_folder", "")).strip()
    if not root:
        return False
    resolution = resolve_standard_tool_profile(root)
    if not resolution.ready:
        return False
    expected = resolution.values()
    for name in (
        "phits_root_folder",
        "rtphits_root",
        "phits_executable_path",
        "phits2dicom_executable_path",
    ):
        resolved = _resolved_path_or_none(str(values.get(name, "")).strip())
        if resolved is None or str(resolved) != expected[name]:
            return False
    return True
