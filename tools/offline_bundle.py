"""Build and validate the public Windows offline-installation bundle.

This helper intentionally uses only the Python standard library. Network
access and Authenticode validation remain visible in the PowerShell wrapper.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
import tempfile
import tomllib
import zipfile


PYTHON_VERSION = "3.12.10"
PYTHON_INSTALLER_NAME = f"python-{PYTHON_VERSION}-amd64.exe"
PYTHON_INSTALLER_URL = (
    f"https://www.python.org/ftp/python/{PYTHON_VERSION}/{PYTHON_INSTALLER_NAME}"
)
TARGET_PLATFORM = "win_amd64"
TARGET_IMPLEMENTATION = "cp"
TARGET_PYTHON_VERSION = "3.12"
TARGET_ABI = "cp312"
REQUIRED_BUILD_TOOLS = ("setuptools", "wheel")
REQUIRED_BUNDLE_SOURCE_PATHS = (
    "install_offline.cmd",
    "tools/offline_bundle.py",
    "tools/offline_install.py",
    "tools/prepare_offline_bundle.ps1",
    "docs/windows-offline-installation.md",
    "docs/windows-offline-installation.ja.md",
)

_REQUIREMENT_NAME_RE = re.compile(r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class OfflineBundleError(RuntimeError):
    """A controlled bundle preparation or validation failure."""


@dataclass(frozen=True)
class GitIndexEntry:
    mode: str
    object_id: str
    path: str


@dataclass(frozen=True)
class GitIndexSnapshot:
    raw: bytes
    entries: tuple[GitIndexEntry, ...]

    @property
    def fingerprint(self) -> str:
        return hashlib.sha256(self.raw).hexdigest()


def normalize_distribution_name(value: str) -> str:
    return re.sub(r"[-_.]+", "-", value).lower()


def requirement_name(requirement: str) -> str:
    if "@" in requirement:
        raise OfflineBundleError(
            f"Direct URL requirements are not supported in an offline bundle: {requirement}"
        )
    match = _REQUIREMENT_NAME_RE.match(requirement)
    if match is None:
        raise OfflineBundleError(f"Cannot determine requirement name: {requirement}")
    return normalize_distribution_name(match.group(1))


def _parse_project_metadata(text: str, source: str) -> dict[str, object]:
    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError as exc:
        raise OfflineBundleError(f"Cannot parse project metadata from {source}: {exc}") from exc
    project = data.get("project")
    if not isinstance(project, dict):
        raise OfflineBundleError("pyproject.toml does not contain [project]")

    name = project.get("name")
    version = project.get("version")
    requires_python = project.get("requires-python")
    dependencies = project.get("dependencies")
    if not isinstance(name, str) or not name:
        raise OfflineBundleError("project.name is missing")
    if not isinstance(version, str) or not version:
        raise OfflineBundleError("project.version is missing")
    if not isinstance(requires_python, str) or "3.12" not in requires_python:
        raise OfflineBundleError(
            "project.requires-python must retain the supported Python 3.12 range"
        )
    if not isinstance(dependencies, list) or not all(
        isinstance(value, str) and value.strip() for value in dependencies
    ):
        raise OfflineBundleError("project.dependencies must be a non-empty string list")

    dependency_names = [requirement_name(value) for value in dependencies]
    for required in ("numpy", "pydicom"):
        if required not in dependency_names:
            raise OfflineBundleError(
                f"Required runtime dependency is missing from pyproject.toml: {required}"
            )
    return {
        "name": name,
        "version": version,
        "requires_python": requires_python,
        "dependencies": list(dependencies),
        "dependency_names": dependency_names,
    }


def load_project_metadata(pyproject_path: Path) -> dict[str, object]:
    try:
        text = pyproject_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise OfflineBundleError(f"Cannot read project metadata: {exc}") from exc
    return _parse_project_metadata(text, str(pyproject_path))


def parse_wheel_filename(path: Path) -> dict[str, object]:
    if path.suffix.lower() != ".whl":
        raise OfflineBundleError(f"Wheelhouse contains a non-wheel artifact: {path.name}")
    parts = path.stem.split("-")
    if len(parts) < 5:
        raise OfflineBundleError(f"Invalid wheel filename: {path.name}")
    python_tags = parts[-3].split(".")
    abi_tags = parts[-2].split(".")
    platform_tags = parts[-1].split(".")
    if not all(python_tags) or not all(abi_tags) or not all(platform_tags):
        raise OfflineBundleError(f"Invalid wheel compatibility tags: {path.name}")
    return {
        "filename": path.name,
        "distribution": normalize_distribution_name(parts[0]),
        "python_tags": python_tags,
        "abi_tags": abi_tags,
        "platform_tags": platform_tags,
    }


def _validate_wheel_names(
    artifact_names: list[str], runtime_dependencies: list[str]
) -> list[dict[str, object]]:
    if not artifact_names:
        raise OfflineBundleError("Wheelhouse is empty")

    wheels = [parse_wheel_filename(Path(name)) for name in artifact_names]
    available = {str(wheel["distribution"]) for wheel in wheels}
    required = {
        *(requirement_name(value) for value in runtime_dependencies),
        *(normalize_distribution_name(value) for value in REQUIRED_BUILD_TOOLS),
    }
    missing = sorted(required - available)
    if missing:
        raise OfflineBundleError(
            "Wheelhouse is missing required distributions: " + ", ".join(missing)
        )

    numpy_wheels = [wheel for wheel in wheels if wheel["distribution"] == "numpy"]
    compatible_numpy = any(
        "cp312" in wheel["python_tags"]
        and "cp312" in wheel["abi_tags"]
        and "win_amd64" in wheel["platform_tags"]
        for wheel in numpy_wheels
    )
    if not compatible_numpy:
        names = ", ".join(str(wheel["filename"]) for wheel in numpy_wheels) or "none"
        raise OfflineBundleError(
            "NumPy wheel must have cp312-cp312-win_amd64 compatibility; found: "
            + names
        )
    return wheels


def _capture_wheelhouse(
    wheelhouse: Path, runtime_dependencies: list[str]
) -> tuple[list[dict[str, object]], dict[str, bytes]]:
    try:
        entries = sorted(wheelhouse.iterdir(), key=lambda path: path.name)
    except OSError as exc:
        raise OfflineBundleError(f"Cannot read wheelhouse: {exc}") from exc
    invalid = [
        path.name for path in entries if path.is_symlink() or not path.is_file()
    ]
    if invalid:
        raise OfflineBundleError(
            "Wheelhouse contains a non-regular artifact: " + ", ".join(invalid)
        )
    captured: dict[str, bytes] = {}
    for path in entries:
        try:
            captured[path.name] = path.read_bytes()
        except OSError as exc:
            raise OfflineBundleError(
                f"Cannot read wheel artifact {path.name}: {exc}"
            ) from exc
        if path.is_symlink():
            raise OfflineBundleError(
                f"Wheel artifact became a symbolic link while being captured: {path.name}"
            )
    wheels = _validate_wheel_names(list(captured), runtime_dependencies)
    return wheels, captured


def validate_wheelhouse(
    wheelhouse: Path, runtime_dependencies: list[str]
) -> list[dict[str, object]]:
    wheels, _captured = _capture_wheelhouse(wheelhouse, runtime_dependencies)
    return wheels


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _safe_relative_path(value: str) -> PurePosixPath:
    relative = PurePosixPath(value.replace("\\", "/"))
    if relative.is_absolute() or not relative.parts:
        raise OfflineBundleError(f"Bundle path must be relative: {value}")
    if any(part in {"", ".", ".."} for part in relative.parts):
        raise OfflineBundleError(f"Bundle path is not normalized: {value}")
    if re.match(r"^[A-Za-z]:", relative.parts[0]):
        raise OfflineBundleError(f"Bundle path must not contain a drive: {value}")
    return relative


def _capture_git_index(repo_root: Path) -> GitIndexSnapshot:
    result = subprocess.run(
        ["git", "ls-files", "--stage", "-z"],
        cwd=repo_root,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode != 0:
        detail = result.stderr.decode("utf-8", errors="replace").strip()
        raise OfflineBundleError(f"Cannot enumerate Git-indexed files: {detail}")
    entries = result.stdout.split(b"\0")
    parsed: list[GitIndexEntry] = []
    for raw in entries:
        if not raw:
            continue
        metadata, separator, encoded_path = raw.partition(b"\t")
        fields = metadata.split()
        if not separator or len(fields) != 3:
            raise OfflineBundleError("Unexpected git ls-files --stage output")
        mode = fields[0].decode("ascii", errors="strict")
        object_id = fields[1].decode("ascii", errors="strict").lower()
        stage = fields[2].decode("ascii", errors="strict")
        if stage != "0":
            raise OfflineBundleError("Git index contains an unresolved merge entry")
        if mode not in {"100644", "100755"}:
            display = encoded_path.decode("utf-8", errors="replace")
            raise OfflineBundleError(
                f"Unsupported indexed entry type {mode} for offline source: {display}"
            )
        if not re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", object_id):
            raise OfflineBundleError("Git index contains an invalid object ID")
        path = encoded_path.decode("utf-8", errors="strict")
        parsed.append(
            GitIndexEntry(
                mode=mode,
                object_id=object_id,
                path=_safe_relative_path(path).as_posix(),
            )
        )
    paths = [entry.path for entry in parsed]
    if len(paths) != len(set(paths)):
        raise OfflineBundleError("Git index contains duplicate normalized paths")
    entries = tuple(sorted(parsed, key=lambda entry: entry.path))
    return GitIndexSnapshot(raw=result.stdout, entries=entries)


def _git_indexed_files(repo_root: Path) -> list[str]:
    return [entry.path for entry in _capture_git_index(repo_root).entries]


def _git_index_fingerprint(repo_root: Path) -> str:
    return _capture_git_index(repo_root).fingerprint


def _run_public_tree_audit(
    repo_root: Path, snapshot: GitIndexSnapshot | None = None
) -> None:
    snapshot = snapshot or _capture_git_index(repo_root)
    verifier_entry = next(
        (
            entry
            for entry in snapshot.entries
            if entry.path == "tools/verify_public_tree.py"
        ),
        None,
    )
    if verifier_entry is None:
        raise OfflineBundleError("Indexed public-tree verifier is missing")
    git_directory_result = subprocess.run(
        ["git", "rev-parse", "--absolute-git-dir"],
        cwd=repo_root,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if git_directory_result.returncode != 0:
        detail = git_directory_result.stderr.strip()
        raise OfflineBundleError(f"Cannot locate Git object database: {detail}")
    git_directory = git_directory_result.stdout.strip()
    with tempfile.TemporaryDirectory(prefix=".dicomxphits-audit-index-") as temporary:
        snapshot_root = Path(temporary) / "snapshot"
        verifier_path = snapshot_root / "tools" / "verify_public_tree.py"
        verifier_path.parent.mkdir(parents=True)
        verifier_path.write_bytes(
            _read_indexed_blob(
                repo_root, verifier_entry.object_id, verifier_entry.path
            )
        )
        index_path = Path(temporary) / "index"
        environment = os.environ.copy()
        environment["GIT_DIR"] = git_directory
        environment["GIT_INDEX_FILE"] = str(index_path)
        environment["GIT_WORK_TREE"] = str(repo_root)
        initialize = subprocess.run(
            ["git", "read-tree", "--empty"],
            cwd=repo_root,
            env=environment,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        if initialize.returncode != 0:
            detail = initialize.stderr.decode("utf-8", errors="replace").strip()
            raise OfflineBundleError(f"Cannot initialize audit index: {detail}")
        populate = subprocess.run(
            ["git", "update-index", "-z", "--index-info"],
            cwd=repo_root,
            env=environment,
            input=snapshot.raw,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        if populate.returncode != 0:
            detail = populate.stderr.decode("utf-8", errors="replace").strip()
            raise OfflineBundleError(f"Cannot populate audit index: {detail}")
        result = subprocess.run(
            [sys.executable, "-I", str(verifier_path)],
            cwd=snapshot_root,
            env=environment,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    if result.returncode != 0:
        raise OfflineBundleError(
            "Captured public-tree verification failed before bundle staging:\n"
            + result.stdout
        )


def _read_indexed_blob(
    repo_root: Path, object_id: str, relative: str = "indexed source"
) -> bytes:
    result = subprocess.run(
        ["git", "cat-file", "blob", object_id],
        cwd=repo_root,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode != 0:
        detail = result.stderr.decode("utf-8", errors="replace").strip()
        raise OfflineBundleError(
            f"Cannot read indexed source blob {relative}: {detail}"
        )
    return result.stdout


def load_indexed_project_metadata(
    repo_root: Path, snapshot: GitIndexSnapshot | None = None
) -> dict[str, object]:
    snapshot = snapshot or _capture_git_index(repo_root)
    entry = next(
        (entry for entry in snapshot.entries if entry.path == "pyproject.toml"), None
    )
    if entry is None:
        raise OfflineBundleError("Indexed pyproject.toml is missing")
    try:
        text = _read_indexed_blob(
            repo_root, entry.object_id, entry.path
        ).decode("utf-8")
    except UnicodeError as exc:
        raise OfflineBundleError("Indexed pyproject.toml is not UTF-8") from exc
    return _parse_project_metadata(text, "indexed pyproject.toml")


def copy_indexed_public_source(
    repo_root: Path,
    staging_root: Path,
    snapshot: GitIndexSnapshot | None = None,
    *,
    run_audit: bool = True,
) -> list[str]:
    snapshot = snapshot or _capture_git_index(repo_root)
    if run_audit:
        _run_public_tree_audit(repo_root, snapshot)
    indexed = [entry.path for entry in snapshot.entries]
    indexed_set = set(indexed)
    missing_required = sorted(set(REQUIRED_BUNDLE_SOURCE_PATHS) - indexed_set)
    if missing_required:
        raise OfflineBundleError(
            "Required offline source files are not Git-indexed: "
            + ", ".join(missing_required)
        )
    for entry in snapshot.entries:
        relative = entry.path
        destination = staging_root.joinpath(*PurePosixPath(relative).parts)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(
            _read_indexed_blob(repo_root, entry.object_id, relative)
        )
    return indexed


def _artifact_record(root: Path, relative: str, role: str) -> dict[str, object]:
    safe = _safe_relative_path(relative).as_posix()
    path = root.joinpath(*PurePosixPath(safe).parts)
    if not path.is_file():
        raise OfflineBundleError(f"Bundle payload is missing: {safe}")
    return {
        "path": safe,
        "role": role,
        "size": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def _git_head(repo_root: Path) -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo_root,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0:
        raise OfflineBundleError("Cannot determine source Git commit")
    value = result.stdout.strip().lower()
    if not re.fullmatch(r"[0-9a-f]{40}", value):
        raise OfflineBundleError("Git HEAD is not a full commit object ID")
    return value


def _load_signature_metadata(
    path: Path, installer_sha256: str
) -> dict[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise OfflineBundleError(f"Cannot read Authenticode metadata: {exc}") from exc
    if not isinstance(value, dict):
        raise OfflineBundleError("Authenticode metadata must be an object")
    if value.get("status") != "Valid":
        raise OfflineBundleError("Python installer Authenticode status is not Valid")
    subject = value.get("signer_subject")
    if not isinstance(subject, str) or "Python Software Foundation" not in subject:
        raise OfflineBundleError("Python installer signer is not the Python Software Foundation")
    thumbprint = value.get("signer_thumbprint")
    if not isinstance(thumbprint, str) or not re.fullmatch(
        r"[0-9A-Fa-f]{40,64}", thumbprint
    ):
        raise OfflineBundleError("Python installer signer thumbprint is invalid")
    recorded_hash = value.get("installer_sha256")
    if not isinstance(recorded_hash, str) or not _SHA256_RE.fullmatch(
        recorded_hash
    ):
        raise OfflineBundleError("Authenticode metadata installer SHA-256 is invalid")
    if recorded_hash != installer_sha256:
        raise OfflineBundleError(
            "Python installer bytes do not match the Authenticode-validated SHA-256"
        )
    return value


def _write_zip(staging_root: Path, output_zip: Path, top_level: str) -> None:
    output_zip.parent.mkdir(parents=True, exist_ok=True)
    if output_zip.exists():
        raise OfflineBundleError(f"Output ZIP already exists: {output_zip}")
    temporary = output_zip.with_name(output_zip.name + ".tmp")
    if temporary.exists():
        temporary.unlink()
    try:
        with zipfile.ZipFile(
            temporary, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
        ) as archive:
            for path in sorted(item for item in staging_root.rglob("*") if item.is_file()):
                relative = path.relative_to(staging_root).as_posix()
                archive.write(path, f"{top_level}/{relative}")
        os.replace(temporary, output_zip)
    finally:
        if temporary.exists():
            temporary.unlink()


def build_bundle(
    *,
    repo_root: Path,
    wheelhouse: Path,
    python_installer: Path,
    signature_metadata_path: Path,
    output_zip: Path,
) -> dict[str, object]:
    snapshot = _capture_git_index(repo_root)
    _run_public_tree_audit(repo_root, snapshot)
    metadata = load_indexed_project_metadata(repo_root, snapshot)
    wheels, wheel_artifacts = _capture_wheelhouse(
        wheelhouse, list(metadata["dependencies"])
    )
    if python_installer.name.lower() != PYTHON_INSTALLER_NAME.lower():
        raise OfflineBundleError(
            f"Expected Python installer named {PYTHON_INSTALLER_NAME}, got {python_installer.name}"
        )
    if not python_installer.is_file():
        raise OfflineBundleError(f"Python installer is missing: {python_installer}")
    try:
        python_installer_bytes = python_installer.read_bytes()
    except OSError as exc:
        raise OfflineBundleError(f"Cannot read Python installer: {exc}") from exc
    installer_sha256 = hashlib.sha256(python_installer_bytes).hexdigest()
    signature = _load_signature_metadata(
        signature_metadata_path, installer_sha256
    )

    top_level = f"dicomxphits-offline-win64-{metadata['version']}"
    with tempfile.TemporaryDirectory(
        prefix=".dicomxphits-offline-stage-", dir=output_zip.parent
    ) as temporary:
        staging_root = Path(temporary) / top_level
        staging_root.mkdir(parents=True)
        source_paths = copy_indexed_public_source(
            repo_root, staging_root, snapshot, run_audit=False
        )

        installer_relative = f"python/{PYTHON_INSTALLER_NAME}"
        installer_destination = staging_root / installer_relative
        installer_destination.parent.mkdir(parents=True)
        installer_destination.write_bytes(python_installer_bytes)

        wheel_relatives: list[str] = []
        wheel_destination = staging_root / "wheelhouse"
        wheel_destination.mkdir()
        for wheel_name, wheel_bytes in wheel_artifacts.items():
            relative = f"wheelhouse/{wheel_name}"
            (staging_root / relative).write_bytes(wheel_bytes)
            wheel_relatives.append(relative)

        records = [
            *(_artifact_record(staging_root, path, "public-source") for path in source_paths),
            _artifact_record(staging_root, installer_relative, "python-installer"),
            *(
                _artifact_record(staging_root, relative, "dependency-wheel")
                for relative in wheel_relatives
            ),
        ]
        records.sort(key=lambda value: str(value["path"]))
        manifest = {
            "schema_version": 1,
            "bundle": {
                "name": top_level,
                "project": metadata["name"],
                "version": metadata["version"],
                "target": "Windows 10/11 x64",
                "python": "CPython 3.12 x64",
            },
            "source": {
                "git_head_commit": _git_head(repo_root),
                "git_index_entries_sha256": snapshot.fingerprint,
                "selection": "git-indexed-public-regular-files",
                "file_count": len(source_paths),
            },
            "project_metadata": {
                "requires_python": metadata["requires_python"],
                "runtime_dependencies": metadata["dependencies"],
                "editable_build_tools": list(REQUIRED_BUILD_TOOLS),
            },
            "wheel_target": {
                "implementation": TARGET_IMPLEMENTATION,
                "python_version": TARGET_PYTHON_VERSION,
                "abi": TARGET_ABI,
                "platform": TARGET_PLATFORM,
                "binary_only": True,
                "validated_wheels": wheels,
            },
            "python_installer": {
                "path": installer_relative,
                "version": PYTHON_VERSION,
                "url": PYTHON_INSTALLER_URL,
                "authenticode": signature,
            },
            "integrity": {
                "algorithm": "SHA-256",
                "checksum_file": "SHA256SUMS.txt",
                "checksum_file_self_excluded": True,
            },
            "files": records,
        }
        manifest_path = staging_root / "bundle-manifest.json"
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

        checksum_records = [
            *(f"{record['sha256']} *{record['path']}" for record in records),
            f"{sha256_file(manifest_path)} *bundle-manifest.json",
        ]
        (staging_root / "SHA256SUMS.txt").write_text(
            "\n".join(checksum_records) + "\n", encoding="utf-8"
        )
        _write_zip(staging_root, output_zip, top_level)

    return {
        "output_zip": str(output_zip),
        "output_sha256": sha256_file(output_zip),
        "bundle_name": top_level,
        "source_file_count": len(source_paths),
        "wheel_count": len(wheels),
    }


def _metadata_command(args: argparse.Namespace) -> int:
    metadata = (
        load_indexed_project_metadata(args.repo_root.resolve())
        if args.repo_root is not None
        else load_project_metadata(args.pyproject)
    )
    json.dump(metadata, sys.stdout, ensure_ascii=False)
    sys.stdout.write("\n")
    return 0


def _validate_wheels_command(args: argparse.Namespace) -> int:
    metadata = (
        load_indexed_project_metadata(args.repo_root.resolve())
        if args.repo_root is not None
        else load_project_metadata(args.pyproject)
    )
    wheels = validate_wheelhouse(args.wheelhouse, list(metadata["dependencies"]))
    json.dump(wheels, sys.stdout, ensure_ascii=False)
    sys.stdout.write("\n")
    return 0


def _build_command(args: argparse.Namespace) -> int:
    result = build_bundle(
        repo_root=args.repo_root.resolve(),
        wheelhouse=args.wheelhouse.resolve(),
        python_installer=args.python_installer.resolve(),
        signature_metadata_path=args.signature_metadata.resolve(),
        output_zip=args.output_zip.resolve(),
    )
    json.dump(result, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    metadata = subparsers.add_parser("metadata")
    metadata_source = metadata.add_mutually_exclusive_group(required=True)
    metadata_source.add_argument("--pyproject", type=Path)
    metadata_source.add_argument("--repo-root", type=Path)
    metadata.set_defaults(handler=_metadata_command)

    validate = subparsers.add_parser("validate-wheels")
    validate_source = validate.add_mutually_exclusive_group(required=True)
    validate_source.add_argument("--pyproject", type=Path)
    validate_source.add_argument("--repo-root", type=Path)
    validate.add_argument("--wheelhouse", type=Path, required=True)
    validate.set_defaults(handler=_validate_wheels_command)

    build = subparsers.add_parser("build")
    build.add_argument("--repo-root", type=Path, required=True)
    build.add_argument("--wheelhouse", type=Path, required=True)
    build.add_argument("--python-installer", type=Path, required=True)
    build.add_argument("--signature-metadata", type=Path, required=True)
    build.add_argument("--output-zip", type=Path, required=True)
    build.set_defaults(handler=_build_command)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return int(args.handler(args))
    except OfflineBundleError as exc:
        print(f"Offline bundle error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
