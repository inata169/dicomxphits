from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "verify_public_tree", ROOT / "tools" / "verify_public_tree.py"
)
assert SPEC is not None and SPEC.loader is not None
verify_public_tree = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = verify_public_tree
SPEC.loader.exec_module(verify_public_tree)


def _write_clean_tree(root: Path):
    for relative in verify_public_tree.REQUIRED_FILES:
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n", encoding="utf-8")

    (root / ".codex" / "config.toml").write_text(
        'approval_policy = "on-request"\n'
        'approvals_reviewer = "user"\n'
        'sandbox_mode = "workspace-write"\n\n'
        '[sandbox_workspace_write]\n'
        'network_access = false\n',
        encoding="utf-8",
    )
    devcontainer = {
        "image": "mcr.microsoft.com/devcontainers/python:1-3.12-bookworm",
        "workspaceMount": (
            "source=${localWorkspaceFolder},target=/workspaces/dicomxphits,type=bind"
        ),
        "remoteUser": "vscode",
    }
    (root / ".devcontainer" / "devcontainer.json").write_text(
        json.dumps(devcontainer), encoding="utf-8"
    )
    paths = [*verify_public_tree.REQUIRED_FILES]
    config_example = root / "config" / "dicomxphits.paths.example.json"
    config_example.parent.mkdir(parents=True, exist_ok=True)
    config_example.write_text(
        json.dumps({"phits_executable_path": ""}), encoding="utf-8"
    )
    paths.append("config/dicomxphits.paths.example.json")
    paths.append("templates/phits2dicom_rtdose_template.dcm")
    return [verify_public_tree.TrackedEntry(path) for path in paths]


def test_clean_public_tree_and_allowlisted_template_pass(tmp_path):
    entries = _write_clean_tree(tmp_path)
    (tmp_path / "untracked.env").write_text("not audited", encoding="utf-8")

    assert verify_public_tree.audit_entries(tmp_path, entries) == []


def test_protected_and_generated_tracked_paths_fail(tmp_path):
    entries = _write_clean_tree(tmp_path)
    entries.extend(
        verify_public_tree.TrackedEntry(path)
        for path in (
            ".env",
            "build/output.txt",
            "private/patient.dcm",
            "results/phits.out",
            "source.IAEAphsp",
        )
    )

    issues = verify_public_tree.audit_entries(tmp_path, entries)
    issue_paths = {path for path, _reason in issues}

    assert {".env", "build/output.txt", "private/patient.dcm"} <= issue_paths
    assert {"results/phits.out", "source.IAEAphsp"} <= issue_paths


def test_escaping_and_absolute_symlinks_fail(tmp_path):
    entries = _write_clean_tree(tmp_path)
    entries.extend(
        (
            verify_public_tree.TrackedEntry(
                "links/outside", mode="120000", link_target="../../outside"
            ),
            verify_public_tree.TrackedEntry(
                "links/absolute", mode="120000", link_target="C:/patient-data"
            ),
        )
    )

    issues = verify_public_tree.audit_entries(tmp_path, entries)
    issue_paths = {path for path, _reason in issues}

    assert {"links/outside", "links/absolute"} <= issue_paths


def test_dangerous_codex_and_devcontainer_settings_fail(tmp_path):
    entries = _write_clean_tree(tmp_path)
    (tmp_path / ".codex" / "config.toml").write_text(
        'approval_policy = "never"\n'
        'approvals_reviewer = "user"\n'
        'sandbox_mode = "danger-full-access"\n\n'
        '[sandbox_workspace_write]\n'
        'network_access = true\n'
        'writable_roots = ["C:/patient-data"]\n',
        encoding="utf-8",
    )
    (tmp_path / ".devcontainer" / "devcontainer.json").write_text(
        json.dumps(
            {
                "image": "python:3.12",
                "privileged": True,
                "mounts": ["source=/var/run/docker.sock,target=/var/run/docker.sock"],
                "remoteUser": "root",
            }
        ),
        encoding="utf-8",
    )

    issues = verify_public_tree.audit_entries(tmp_path, entries)
    issue_paths = {path for path, _reason in issues}

    assert ".codex/config.toml" in issue_paths
    assert ".devcontainer/devcontainer.json" in issue_paths


def test_local_absolute_path_in_tracked_configuration_fails(tmp_path):
    entries = _write_clean_tree(tmp_path)
    (tmp_path / "config" / "dicomxphits.paths.example.json").write_text(
        json.dumps({"phits_executable_path": "C:/PHITS/bin/phits.exe"}),
        encoding="utf-8",
    )

    issues = verify_public_tree.audit_entries(tmp_path, entries)

    assert (
        "config/dicomxphits.paths.example.json",
        "configuration contains a local absolute path",
    ) in issues
