"""Install dicomxphits from a verified offline Windows bundle.

The module is standard-library only so it can run immediately after the
bundled CPython installer completes. Its pure command-building and validation
helpers are also used by synthetic tests.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import struct
import subprocess
import sys
from typing import Callable, Mapping, Sequence


_CHECKSUM_LINE_RE = re.compile(r"^([0-9a-f]{64}) \*(.+)$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_REQUIREMENT_NAME_RE = re.compile(r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)")
_REQUIRED_IMPORTS = ("tkinter", "numpy", "pydicom", "dicomxphits")


class OfflineInstallError(RuntimeError):
    """A controlled offline-installation failure."""


@dataclass(frozen=True)
class PythonProbe:
    executable: str
    implementation: str
    major: int
    minor: int
    micro: int
    bits: int

    @property
    def supported(self) -> bool:
        return (
            self.implementation == "cpython"
            and (self.major, self.minor) == (3, 12)
            and self.bits == 64
        )


class InstallLogger:
    def __init__(self, path: Path) -> None:
        self.path = path

    def write(self, message: str) -> None:
        timestamp = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
        line = f"[{timestamp}] {message}"
        print(line, flush=True)
        with self.path.open("a", encoding="utf-8", newline="\n") as stream:
            stream.write(line + "\n")


def _normalize_distribution_name(value: str) -> str:
    return re.sub(r"[-_.]+", "-", value).lower()


def _requirement_name(requirement: str) -> str:
    if "@" in requirement:
        raise OfflineInstallError(
            f"Direct URL requirement is not allowed offline: {requirement}"
        )
    match = _REQUIREMENT_NAME_RE.match(requirement)
    if match is None:
        raise OfflineInstallError(f"Cannot determine requirement name: {requirement}")
    return _normalize_distribution_name(match.group(1))


def _safe_relative(value: str) -> PurePosixPath:
    path = PurePosixPath(value.replace("\\", "/"))
    if path.is_absolute() or not path.parts:
        raise OfflineInstallError(f"Integrity path must be relative: {value}")
    if any(part in {"", ".", ".."} for part in path.parts):
        raise OfflineInstallError(f"Integrity path is not normalized: {value}")
    if re.match(r"^[A-Za-z]:", path.parts[0]):
        raise OfflineInstallError(f"Integrity path must not contain a drive: {value}")
    if any(":" in part for part in path.parts):
        raise OfflineInstallError(f"Integrity path must not contain an alternate stream: {value}")
    return path


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def parse_checksums(text: str) -> dict[str, str]:
    checksums: dict[str, str] = {}
    for line_number, raw_line in enumerate(text.splitlines(), start=1):
        if not raw_line:
            continue
        match = _CHECKSUM_LINE_RE.fullmatch(raw_line)
        if match is None:
            raise OfflineInstallError(
                f"Invalid SHA256SUMS.txt line {line_number}: {raw_line!r}"
            )
        digest, raw_path = match.groups()
        relative = _safe_relative(raw_path).as_posix()
        if relative in checksums:
            raise OfflineInstallError(f"Duplicate checksum path: {relative}")
        checksums[relative] = digest
    if not checksums:
        raise OfflineInstallError("SHA256SUMS.txt is empty")
    if "SHA256SUMS.txt" in checksums:
        raise OfflineInstallError("SHA256SUMS.txt must not claim a self-referential hash")
    return checksums


def _load_manifest(path: Path) -> dict[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise OfflineInstallError(f"Cannot read bundle-manifest.json: {exc}") from exc
    if not isinstance(value, dict) or value.get("schema_version") != 1:
        raise OfflineInstallError("Unsupported or malformed bundle manifest")
    return value


def verify_bundle(bundle_root: Path) -> dict[str, object]:
    root = bundle_root.resolve()
    checksum_path = root / "SHA256SUMS.txt"
    try:
        checksums = parse_checksums(checksum_path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise OfflineInstallError(f"Cannot read SHA256SUMS.txt: {exc}") from exc

    for relative, expected in checksums.items():
        path = root.joinpath(*PurePosixPath(relative).parts)
        if not path.is_file():
            raise OfflineInstallError(f"Bundle payload is missing: {relative}")
        actual = _sha256_file(path)
        if actual != expected:
            raise OfflineInstallError(
                f"SHA-256 mismatch for {relative}: expected {expected}, got {actual}"
            )

    if "bundle-manifest.json" not in checksums:
        raise OfflineInstallError("SHA256SUMS.txt does not protect bundle-manifest.json")
    manifest = _load_manifest(root / "bundle-manifest.json")
    raw_files = manifest.get("files")
    if not isinstance(raw_files, list):
        raise OfflineInstallError("Bundle manifest files must be a list")
    manifest_paths: set[str] = set()
    expected_wheel_paths: set[str] = set()
    for record in raw_files:
        if not isinstance(record, dict):
            raise OfflineInstallError("Bundle manifest contains a malformed file record")
        relative_value = record.get("path")
        digest = record.get("sha256")
        size = record.get("size")
        role = record.get("role")
        if not isinstance(relative_value, str):
            raise OfflineInstallError("Bundle manifest file path is missing")
        relative = _safe_relative(relative_value).as_posix()
        if relative in manifest_paths:
            raise OfflineInstallError(f"Duplicate manifest path: {relative}")
        if not isinstance(digest, str) or not _SHA256_RE.fullmatch(digest):
            raise OfflineInstallError(f"Invalid manifest SHA-256 for {relative}")
        if not isinstance(size, int) or size < 0:
            raise OfflineInstallError(f"Invalid manifest size for {relative}")
        if not isinstance(role, str) or not role:
            raise OfflineInstallError(f"Invalid manifest role for {relative}")
        if role == "dependency-wheel":
            if (
                len(PurePosixPath(relative).parts) != 2
                or not relative.startswith("wheelhouse/")
                or not relative.lower().endswith(".whl")
            ):
                raise OfflineInstallError(
                    f"Dependency wheel is outside the flat wheelhouse: {relative}"
                )
            expected_wheel_paths.add(relative)
        elif relative.startswith("wheelhouse/"):
            raise OfflineInstallError(
                f"Wheelhouse payload has an invalid manifest role: {relative}"
            )
        if checksums.get(relative) != digest:
            raise OfflineInstallError(
                f"Manifest and SHA256SUMS.txt disagree for {relative}"
            )
        path = root.joinpath(*PurePosixPath(relative).parts)
        if path.stat().st_size != size:
            raise OfflineInstallError(f"Manifest size mismatch for {relative}")
        manifest_paths.add(relative)

    expected_checksum_paths = manifest_paths | {"bundle-manifest.json"}
    if set(checksums) != expected_checksum_paths:
        missing = sorted(expected_checksum_paths - set(checksums))
        unexpected = sorted(set(checksums) - expected_checksum_paths)
        raise OfflineInstallError(
            "Integrity inventories disagree; "
            f"missing={missing or 'none'}, unexpected={unexpected or 'none'}"
        )

    if not expected_wheel_paths:
        raise OfflineInstallError("Bundle manifest contains no dependency wheels")
    wheelhouse = root / "wheelhouse"
    try:
        wheelhouse_entries = list(wheelhouse.iterdir())
    except OSError as exc:
        raise OfflineInstallError(f"Cannot inspect bundled wheelhouse: {exc}") from exc
    actual_wheel_paths: set[str] = set()
    invalid_entries: list[str] = []
    for entry in wheelhouse_entries:
        relative = f"wheelhouse/{entry.name}"
        if entry.is_symlink() or not entry.is_file():
            invalid_entries.append(relative)
        else:
            actual_wheel_paths.add(relative)
    if invalid_entries or actual_wheel_paths != expected_wheel_paths:
        missing = sorted(expected_wheel_paths - actual_wheel_paths)
        unexpected = sorted(actual_wheel_paths - expected_wheel_paths)
        raise OfflineInstallError(
            "Wheelhouse contents differ from the verified manifest; "
            f"missing={missing or 'none'}, "
            f"unexpected={(unexpected + sorted(invalid_entries)) or 'none'}"
        )

    required_source = {
        "install_offline.cmd",
        "tools/offline_install.py",
        "tools/install_offline_verified.ps1",
        "launchers/run_gui_venv.cmd",
        "pyproject.toml",
        "requirements/offline-win64.txt",
    }
    absent_source = sorted(required_source - manifest_paths)
    if absent_source:
        raise OfflineInstallError(
            "Bundle is missing required installation source: " + ", ".join(absent_source)
        )
    return manifest


def current_python_probe() -> PythonProbe:
    return PythonProbe(
        executable=sys.executable,
        implementation=sys.implementation.name,
        major=sys.version_info.major,
        minor=sys.version_info.minor,
        micro=sys.version_info.micro,
        bits=struct.calcsize("P") * 8,
    )


def python_probe_command(executable: Path) -> list[str]:
    program = (
        "import json,struct,sys;"
        "print(json.dumps({'executable':sys.executable,"
        "'implementation':sys.implementation.name,"
        "'major':sys.version_info.major,'minor':sys.version_info.minor,"
        "'micro':sys.version_info.micro,'bits':struct.calcsize('P')*8}))"
    )
    return [str(executable), "-I", "-S", "-c", program]


def probe_python(
    executable: Path,
    *,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> PythonProbe:
    result = runner(
        python_probe_command(executable),
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        raise OfflineInstallError(
            f"Python interpreter probe failed for {executable}: {detail}"
        )
    try:
        value = json.loads(result.stdout)
        probe = PythonProbe(
            executable=str(value["executable"]),
            implementation=str(value["implementation"]),
            major=int(value["major"]),
            minor=int(value["minor"]),
            micro=int(value["micro"]),
            bits=int(value["bits"]),
        )
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise OfflineInstallError(
            f"Python interpreter returned malformed probe data: {executable}"
        ) from exc
    return probe


def ensure_venv(
    bundle_root: Path,
    base_python: Path,
    logger: InstallLogger,
    *,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> Path:
    bundle_root = bundle_root.resolve()
    venv_root = bundle_root / ".venv"
    venv_python = venv_root / "Scripts" / "python.exe"
    if venv_root.is_symlink() or venv_root.is_junction():
        raise OfflineInstallError(
            "Existing .venv is a symbolic link or directory junction and may "
            "resolve outside the bundle. It was not changed. Rename or remove "
            "the link manually after confirming its target, then rerun."
        )
    if venv_root.exists():
        if not venv_root.is_dir() or not venv_python.is_file():
            raise OfflineInstallError(
                "Existing .venv is malformed or incomplete. It was not changed. "
                "Rename or remove it manually after confirming it is no longer needed, then rerun."
            )
        try:
            resolved_python = venv_python.resolve(strict=True)
            resolved_python.relative_to(venv_root)
        except (OSError, ValueError) as exc:
            raise OfflineInstallError(
                "Existing .venv Python resolves outside the repository-local "
                "environment. It was not changed. Rename or remove .venv "
                "manually after confirming its target, then rerun."
            ) from exc
        probe = probe_python(venv_python, runner=runner)
        if not probe.supported:
            raise OfflineInstallError(
                "Existing .venv is not CPython 3.12 x64. It was not changed. "
                "Rename or remove it manually after confirming it is no longer needed, then rerun."
            )
        logger.write(
            f"Reusing compatible .venv: Python {probe.major}.{probe.minor}.{probe.micro} "
            f"{probe.bits}-bit"
        )
        return venv_python

    logger.write("Creating repository-local .venv with CPython 3.12 x64")
    _run_logged(
        [str(base_python), "-I", "-S", "-m", "venv", str(venv_root)],
        logger=logger,
        runner=runner,
        cwd=bundle_root,
        environment=os.environ.copy(),
    )
    if not venv_python.is_file():
        raise OfflineInstallError("venv creation returned success but Python is missing")
    probe = probe_python(venv_python, runner=runner)
    if not probe.supported:
        raise OfflineInstallError("New .venv did not report CPython 3.12 x64")
    return venv_python


def offline_environment(wheelhouse: Path) -> dict[str, str]:
    environment = os.environ.copy()
    environment.update(
        {
            "PIP_NO_INDEX": "1",
            "PIP_FIND_LINKS": str(wheelhouse),
            "PIP_NO_BUILD_ISOLATION": "1",
            "PIP_DISABLE_PIP_VERSION_CHECK": "1",
            "PYTHONUTF8": "1",
        }
    )
    return environment


def offline_pip_command(
    venv_python: Path, wheelhouse: Path, arguments: Sequence[str]
) -> list[str]:
    return [
        str(venv_python),
        "-I",
        "-m",
        "pip",
        "install",
        "--no-index",
        "--find-links",
        str(wheelhouse),
        "--no-build-isolation",
        *arguments,
    ]


def _display_command(command: Sequence[str]) -> str:
    return subprocess.list2cmdline([str(value) for value in command])


def _run_logged(
    command: Sequence[str],
    *,
    logger: InstallLogger,
    runner: Callable[..., subprocess.CompletedProcess[str]],
    cwd: Path,
    environment: Mapping[str, str],
) -> subprocess.CompletedProcess[str]:
    logger.write("Run: " + _display_command(command))
    result = runner(
        list(command),
        cwd=cwd,
        env=dict(environment),
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    output = result.stdout or ""
    for line in output.splitlines():
        logger.write("  " + line)
    if result.returncode != 0:
        raise OfflineInstallError(
            f"Command failed with exit code {result.returncode}: {_display_command(command)}"
        )
    return result


def _runtime_requirements(manifest: Mapping[str, object]) -> list[str]:
    metadata = manifest.get("project_metadata")
    if not isinstance(metadata, dict):
        raise OfflineInstallError("Manifest project_metadata is missing")
    raw_dependencies = metadata.get("runtime_dependencies")
    raw_tools = metadata.get("editable_build_tools")
    if not isinstance(raw_dependencies, list) or not all(
        isinstance(value, str) and value for value in raw_dependencies
    ):
        raise OfflineInstallError("Manifest runtime dependencies are invalid")
    if not isinstance(raw_tools, list) or not all(
        isinstance(value, str) and value for value in raw_tools
    ):
        raise OfflineInstallError("Manifest editable build tools are invalid")
    dependency_names = {_requirement_name(value) for value in raw_dependencies}
    tool_names = {_requirement_name(value) for value in raw_tools}
    if not {"numpy", "pydicom"} <= dependency_names:
        raise OfflineInstallError("Manifest must retain numpy and pydicom dependencies")
    if not {"setuptools", "wheel"} <= tool_names:
        raise OfflineInstallError("Manifest must retain setuptools and wheel build tools")
    return list(raw_dependencies)


def _verify_imports(
    venv_python: Path,
    *,
    bundle_root: Path,
    logger: InstallLogger,
    runner: Callable[..., subprocess.CompletedProcess[str]],
    environment: Mapping[str, str],
) -> dict[str, str]:
    program = (
        "import importlib.metadata,json,sys,tkinter,numpy,pydicom,dicomxphits;"
        "print(json.dumps({'python':sys.version.split()[0],"
        "'numpy':numpy.__version__,'pydicom':pydicom.__version__,"
        "'dicomxphits':importlib.metadata.version('dicomxphits')}))"
    )
    result = _run_logged(
        [str(venv_python), "-I", "-c", program],
        logger=logger,
        runner=runner,
        cwd=bundle_root,
        environment=environment,
    )
    try:
        versions = json.loads((result.stdout or "").strip().splitlines()[-1])
    except (IndexError, json.JSONDecodeError) as exc:
        raise OfflineInstallError("Import verification did not return version metadata") from exc
    if not isinstance(versions, dict) or not all(
        isinstance(versions.get(name), str)
        for name in ("python", "numpy", "pydicom", "dicomxphits")
    ):
        raise OfflineInstallError("Import verification returned malformed version metadata")
    return {name: str(value) for name, value in versions.items()}


def install_bundle(
    bundle_root: Path,
    *,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> tuple[Path, dict[str, str]]:
    root = bundle_root.resolve()
    logger = InstallLogger(root / "offline-install.log")
    logger.write("Starting dicomxphits offline installation")
    logger.write("Run from an extracted local-disk folder, not directly from USB storage")
    manifest = verify_bundle(root)
    logger.write("Bundle SHA-256 and manifest verification passed")

    base_probe = current_python_probe()
    if not base_probe.supported:
        raise OfflineInstallError(
            "Bootstrap interpreter must be CPython 3.12 x64; "
            f"got {base_probe.implementation} {base_probe.major}.{base_probe.minor} "
            f"{base_probe.bits}-bit"
        )
    logger.write(
        f"Bootstrap Python: {base_probe.executable} "
        f"{base_probe.major}.{base_probe.minor}.{base_probe.micro} {base_probe.bits}-bit"
    )

    _runtime_requirements(manifest)
    lock_path = root / "requirements" / "offline-win64.txt"
    wheelhouse = root / "wheelhouse"
    venv_python = ensure_venv(
        root, Path(base_probe.executable), logger, runner=runner
    )
    environment = offline_environment(wheelhouse)
    commands = [
        offline_pip_command(
            venv_python,
            wheelhouse,
            ["--force-reinstall", "--require-hashes", "--requirement", str(lock_path)],
        ),
        offline_pip_command(
            venv_python, wheelhouse, ["--no-deps", "--editable", str(root)]
        ),
    ]
    for command in commands:
        _run_logged(
            command,
            logger=logger,
            runner=runner,
            cwd=root,
            environment=environment,
        )
    versions = _verify_imports(
        venv_python,
        bundle_root=root,
        logger=logger,
        runner=runner,
        environment=environment,
    )
    logger.write(
        "Verified versions: "
        f"Python {versions['python']}; NumPy {versions['numpy']}; "
        f"pydicom {versions['pydicom']}; dicomxphits {versions['dicomxphits']}"
    )
    logger.write("Offline installation completed successfully")
    return venv_python, versions


def offer_gui_launch(
    bundle_root: Path,
    *,
    input_fn: Callable[[str], str] = input,
    popen: Callable[..., subprocess.Popen[bytes]] = subprocess.Popen,
) -> bool:
    launcher = bundle_root.resolve() / "launchers" / "run_gui_venv.cmd"
    print("\nGUI launch command:")
    print(f'  "{launcher}"')
    try:
        choice = input_fn("Launch the dicomxphits GUI now? [y/N]: ").strip().lower()
    except EOFError:
        choice = ""
    if choice not in {"y", "yes"}:
        print("GUI was not launched. Run the command above when ready.")
        return False
    comspec = os.environ.get("COMSPEC", "cmd.exe")
    popen([comspec, "/d", "/c", str(launcher)], cwd=bundle_root.resolve())
    print("GUI launcher started.")
    return True


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--probe", action="store_true")
    parser.add_argument("--bundle-root", type=Path)
    parser.add_argument("--no-gui-prompt", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.probe:
        probe = current_python_probe()
        if probe.supported:
            print(probe.executable)
            return 0
        return 1
    if args.bundle_root is None:
        print("Offline install error: --bundle-root is required", file=sys.stderr)
        return 2
    try:
        install_bundle(args.bundle_root)
        if not args.no_gui_prompt:
            offer_gui_launch(args.bundle_root)
        return 0
    except (OfflineInstallError, OSError) as exc:
        message = f"Offline install error: {exc}"
        print(message, file=sys.stderr)
        try:
            logger = InstallLogger(args.bundle_root.resolve() / "offline-install.log")
            logger.write(message)
        except OSError:
            pass
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
