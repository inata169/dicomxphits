#!/usr/bin/env python3
"""Audit tracked files at the dicomxphits public repository boundary."""

from __future__ import annotations

import json
import posixpath
import subprocess
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Iterable, Mapping


REQUIRED_FILES = (
    ".codex/config.toml",
    ".devcontainer/devcontainer.json",
    ".github/workflows/ci.yml",
    ".gitignore",
    "AGENTS.md",
    "AI_AGENT_RULES.md",
    "docs/development.md",
    "tests/test_verify_public_tree.py",
    "tools/verify_public_tree.py",
)
ALLOWED_DICOM_BLOBS = {
    "templates/phits2dicom_rtdose_template.dcm": (
        "2268aac6213d0e889dac1136dc24c36e16bc1824"
    )
}
GENERATED_DIRS = frozenset(
    {
        ".cache",
        ".eggs",
        ".mypy_cache",
        ".nox",
        ".pytest_cache",
        ".ruff_cache",
        ".tox",
        ".venv",
        "__pycache__",
        "build",
        "dist",
        "htmlcov",
        "venv",
    }
)
SECRET_FILENAMES = frozenset(
    {
        "credentials.json",
        "id_dsa",
        "id_ed25519",
        "id_ecdsa",
        "id_rsa",
        "secret.json",
        "secrets.json",
    }
)
SECRET_SUFFIXES = frozenset({".jks", ".key", ".p12", ".pem", ".pfx"})
PHASE_SPACE_SUFFIXES = frozenset(
    {".egsphsp", ".egsphsp1", ".iaeaphsp", ".iaeaheader", ".phsp"}
)
PHITS_RESULT_NAMES = frozenset(
    {
        "phits.err",
        "phits.log",
        "phits.out",
        "phits2dicom.log",
        "sumtally.out",
    }
)


@dataclass(frozen=True)
class TrackedEntry:
    path: str
    mode: str = "100644"
    object_id: str = ""


def _run_git(repo: Path, *args: str) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def tracked_entries(repo: Path) -> list[TrackedEntry]:
    result = _run_git(repo, "ls-files", "--stage", "-z")
    if result.returncode != 0:
        detail = result.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"git ls-files failed: {detail or 'unknown error'}")

    entries: list[TrackedEntry] = []
    for raw_record in result.stdout.split(b"\0"):
        if not raw_record:
            continue
        metadata, separator, raw_path = raw_record.partition(b"\t")
        if not separator:
            raise RuntimeError("git ls-files returned an invalid record")
        fields = metadata.decode("ascii").split()
        if len(fields) != 3:
            raise RuntimeError("git ls-files returned invalid stage metadata")
        mode, object_id, stage = fields
        if stage != "0":
            raise RuntimeError("git index contains an unresolved merge entry")
        path = raw_path.decode("utf-8", errors="surrogateescape").replace("\\", "/")
        entries.append(TrackedEntry(path, mode, object_id))
    return entries


def indexed_blobs(repo: Path, entries: Iterable[TrackedEntry]) -> dict[str, bytes]:
    entries = list(entries)
    object_ids = list(dict.fromkeys(entry.object_id for entry in entries))
    process = subprocess.Popen(
        ["git", "-C", str(repo), "cat-file", "--batch"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    request = b"".join(object_id.encode("ascii") + b"\n" for object_id in object_ids)
    output, error = process.communicate(request)
    if process.returncode != 0:
        detail = error.decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"git cat-file failed: {detail or 'unknown error'}")

    objects: dict[str, bytes] = {}
    cursor = 0
    for requested_id in object_ids:
        header_end = output.find(b"\n", cursor)
        if header_end < 0:
            raise RuntimeError("git cat-file returned an incomplete header")
        fields = output[cursor:header_end].decode("ascii").split()
        if len(fields) != 3 or fields[1] != "blob":
            raise RuntimeError(f"git object {requested_id} is not a readable blob")
        actual_id, _object_type, size_text = fields
        size = int(size_text)
        data_start = header_end + 1
        data_end = data_start + size
        if data_end >= len(output) or output[data_end : data_end + 1] != b"\n":
            raise RuntimeError(f"git cat-file returned incomplete data for {requested_id}")
        objects[actual_id] = output[data_start:data_end]
        cursor = data_end + 1
    return {entry.path: objects[entry.object_id] for entry in entries}


def _looks_like_dicom(blob: bytes) -> bool:
    return len(blob) >= 132 and blob[128:132] == b"DICM"


def _path_issues(entry: TrackedEntry, blob: bytes) -> list[str]:
    path = entry.path
    pure = PurePosixPath(path)
    parts = tuple(part.lower() for part in pure.parts)
    name = pure.name.lower()
    suffix = pure.suffix.lower()
    issues: list[str] = []

    approved_object_id = ALLOWED_DICOM_BLOBS.get(path)
    if approved_object_id is not None and entry.object_id != approved_object_id:
        issues.append("reviewed DICOM template does not match its approved Git object ID")
    elif approved_object_id is None and (suffix == ".dcm" or _looks_like_dicom(blob)):
        issues.append("tracked DICOM is not the reviewed public template")
    if any(part in GENERATED_DIRS or part.endswith(".egg-info") for part in parts):
        issues.append("cache, virtual-environment, or build output is tracked")
    if suffix in {".pyc", ".pyo"}:
        issues.append("compiled Python output is tracked")
    if name == ".env" or name.startswith(".env."):
        issues.append("environment/credential file is tracked")
    if name in SECRET_FILENAMES or suffix in SECRET_SUFFIXES:
        issues.append("credential or private-key file is tracked")
    if suffix in {".json", ".toml", ".yaml", ".yml"} and any(
        marker in pure.stem.lower() for marker in ("credential", "secret", "token")
    ):
        issues.append("credential-like configuration file is tracked")
    if suffix in PHASE_SPACE_SUFFIXES or (
        "iaea" in name and any(marker in name for marker in ("header", "phase", "phsp"))
    ):
        issues.append("IAEA phase-space/header material is tracked")
    if name in PHITS_RESULT_NAMES or (
        name.startswith("deposit-target-3d") and suffix == ".out"
    ):
        issues.append("apparent PHITS or related execution result is tracked")
    if path.lower().startswith("config/") and name.endswith(".local.json"):
        issues.append("local path or machine configuration is tracked")
    return issues


def _symlink_issue(entry: TrackedEntry, blob: bytes) -> str | None:
    if entry.mode != "120000":
        return None
    target = blob.decode("utf-8", errors="surrogateescape").strip()
    if not target:
        return "symlink target is empty"
    if PurePosixPath(target).is_absolute() or PureWindowsPath(target).is_absolute():
        return f"symlink uses an absolute target: {target}"
    resolved = posixpath.normpath(posixpath.join(posixpath.dirname(entry.path), target))
    if resolved == ".." or resolved.startswith("../"):
        return f"symlink escapes the repository: {target}"
    return None


def _codex_config_issues(blob: bytes) -> list[tuple[str, str]]:
    try:
        config = tomllib.loads(blob.decode("utf-8"))
    except (UnicodeError, tomllib.TOMLDecodeError) as exc:
        return [(".codex/config.toml", f"cannot parse required Codex config: {exc}")]

    expected = {
        "approval_policy": "on-request",
        "approvals_reviewer": "user",
        "sandbox_mode": "workspace-write",
    }
    issues = [
        (".codex/config.toml", f"{key} must be {value!r}")
        for key, value in expected.items()
        if config.get(key) != value
    ]
    sandbox = config.get("sandbox_workspace_write")
    if not isinstance(sandbox, dict) or sandbox.get("network_access") is not False:
        issues.append((".codex/config.toml", "sandbox network_access must be false"))
    if isinstance(sandbox, dict) and "writable_roots" in sandbox:
        issues.append((".codex/config.toml", "extra writable_roots are not allowed"))
    if "permissions" in config or "default_permissions" in config:
        issues.append((".codex/config.toml", "permission profiles must not mix with sandbox settings"))
    return issues


def _devcontainer_issues(blob: bytes) -> list[tuple[str, str]]:
    relative = ".devcontainer/devcontainer.json"
    try:
        config = json.loads(blob.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        return [(relative, f"cannot parse required Dev Container config: {exc}")]
    if not isinstance(config, dict):
        return [(relative, "Dev Container config must be a JSON object")]

    issues: list[tuple[str, str]] = []
    if config.get("privileged") is True:
        issues.append((relative, "privileged mode is not allowed"))
    if str(config.get("networkMode", "")).lower() == "host":
        issues.append((relative, "host network mode is not allowed"))
    run_args = " ".join(str(value) for value in config.get("runArgs", []))
    lowered_args = run_args.lower()
    if "--privileged" in lowered_args or "--network=host" in lowered_args:
        issues.append((relative, "runArgs enable privileged or host-network mode"))

    mounts = config.get("mounts", [])
    mount_text = json.dumps(mounts, sort_keys=True).lower()
    for mount in mounts:
        if isinstance(mount, dict):
            mount_type = str(mount.get("type", "")).lower()
        else:
            fields = {}
            for item in str(mount).split(","):
                key, separator, value = item.strip().partition("=")
                if separator:
                    fields[key.lower()] = value
            mount_type = fields.get("type", "").lower()
        if mount_type == "bind":
            issues.append((relative, "additional host bind mounts are not allowed"))
            break
    forbidden_mount_markers = (
        "docker.sock",
        "patient",
        "clinical",
        "dicom-data",
        "dicom_data",
        "ct2phits",
        "phits",
        "sumtally",
        "gpr-comparing",
    )
    if any(marker in mount_text for marker in forbidden_mount_markers):
        issues.append((relative, "mounts expose Docker, patient/clinical data, or real external tools"))

    workspace_mount = config.get("workspaceMount")
    if workspace_mount is not None:
        fields = {}
        for item in str(workspace_mount).split(","):
            key, separator, value = item.strip().partition("=")
            if separator:
                fields[key] = value
        if fields.get("source") != "${localWorkspaceFolder}":
            issues.append((relative, "workspaceMount must be limited to the current repository"))
    if config.get("remoteUser") in {None, "root"}:
        issues.append((relative, "a non-root remoteUser is required"))
    return issues


def _string_values(value: object) -> Iterable[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for child in value.values():
            yield from _string_values(child)
    elif isinstance(value, list):
        for child in value:
            yield from _string_values(child)


def _repository_config_issues(
    tracked: set[str], blobs: Mapping[str, bytes]
) -> list[tuple[str, str]]:
    issues: list[tuple[str, str]] = []
    for relative in sorted(tracked):
        if not relative.startswith("config/") or not relative.lower().endswith(".json"):
            continue
        try:
            value = json.loads(blobs[relative].decode("utf-8"))
        except (KeyError, UnicodeError, json.JSONDecodeError) as exc:
            issues.append((relative, f"cannot parse tracked JSON configuration: {exc}"))
            continue
        for text in _string_values(value):
            if text.startswith(("http://", "https://")):
                continue
            if PureWindowsPath(text).is_absolute() or PurePosixPath(text).is_absolute():
                issues.append((relative, "configuration contains a local absolute path"))
                break
    return issues


def audit_entries(
    entries: Iterable[TrackedEntry], blobs: Mapping[str, bytes]
) -> list[tuple[str, str]]:
    entries = list(entries)
    tracked = {entry.path for entry in entries}
    issues: list[tuple[str, str]] = []
    for required in REQUIRED_FILES:
        if required not in tracked:
            issues.append((required, "required development-loop file is not tracked"))
    for entry in entries:
        blob = blobs.get(entry.path, b"")
        issues.extend((entry.path, reason) for reason in _path_issues(entry, blob))
        symlink_reason = _symlink_issue(entry, blob)
        if symlink_reason:
            issues.append((entry.path, symlink_reason))
    if ".codex/config.toml" in tracked:
        issues.extend(_codex_config_issues(blobs[".codex/config.toml"]))
    if ".devcontainer/devcontainer.json" in tracked:
        issues.extend(_devcontainer_issues(blobs[".devcontainer/devcontainer.json"]))
    issues.extend(_repository_config_issues(tracked, blobs))
    return sorted(set(issues))


def audit_repository(repo: Path) -> tuple[list[tuple[str, str]], int]:
    entries = tracked_entries(repo)
    blobs = indexed_blobs(repo, entries)
    return audit_entries(entries, blobs), len(entries)


def main() -> int:
    repo = Path(__file__).resolve().parents[1]
    try:
        issues, tracked_count = audit_repository(repo)
    except RuntimeError as exc:
        print(f"Public tree audit could not run: {exc}", file=sys.stderr)
        return 2
    if issues:
        print("Public tree audit failed:", file=sys.stderr)
        for path, reason in issues:
            print(f"- {path}: {reason}", file=sys.stderr)
        return 1
    print(f"Public tree audit passed ({tracked_count} tracked files checked).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
