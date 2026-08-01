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


def _clean_audit_input():
    codex_config = (
        'approval_policy = "on-request"\n'
        'approvals_reviewer = "user"\n'
        'sandbox_mode = "workspace-write"\n\n'
        '[sandbox_workspace_write]\n'
        'network_access = false\n'
    )
    devcontainer = {
        "image": "mcr.microsoft.com/devcontainers/python:1-3.12-bookworm",
        "workspaceMount": (
            "source=${localWorkspaceFolder},target=/workspaces/dicomxphits,type=bind"
        ),
        "remoteUser": "vscode",
    }
    paths = [*verify_public_tree.REQUIRED_FILES, "config/dicomxphits.paths.example.json"]
    entries = [
        verify_public_tree.TrackedEntry(path, object_id=f"test-object-{index}")
        for index, path in enumerate(paths)
    ]
    template_path, template_object_id = next(
        iter(verify_public_tree.ALLOWED_DICOM_BLOBS.items())
    )
    entries.append(
        verify_public_tree.TrackedEntry(template_path, object_id=template_object_id)
    )
    blobs = {entry.path: b"\n" for entry in entries}
    blobs[".codex/config.toml"] = codex_config.encode("utf-8")
    blobs[".devcontainer/devcontainer.json"] = json.dumps(devcontainer).encode("utf-8")
    blobs["config/dicomxphits.paths.example.json"] = json.dumps(
        {"phits_executable_path": ""}
    ).encode("utf-8")
    blobs[template_path] = b"\0" * 128 + b"DICM"
    return entries, blobs


def test_clean_public_tree_and_allowlisted_template_pass():
    entries, blobs = _clean_audit_input()

    assert verify_public_tree.audit_entries(entries, blobs) == []


def test_protected_and_generated_tracked_paths_fail():
    entries, blobs = _clean_audit_input()
    for index, path in enumerate(
        (
            ".env",
            "build/output.txt",
            "private/patient.dcm",
            "results/phits.out",
            "source.IAEAphsp",
        )
    ):
        entries.append(verify_public_tree.TrackedEntry(path, object_id=f"bad-{index}"))
        blobs[path] = b"not DICOM"

    issues = verify_public_tree.audit_entries(entries, blobs)
    issue_paths = {path for path, _reason in issues}

    assert {".env", "build/output.txt", "private/patient.dcm"} <= issue_paths
    assert {"results/phits.out", "source.IAEAphsp"} <= issue_paths


def test_replaced_template_and_extensionless_dicom_fail():
    entries, blobs = _clean_audit_input()
    template_path = next(iter(verify_public_tree.ALLOWED_DICOM_BLOBS))
    entries = [
        verify_public_tree.TrackedEntry(entry.path, entry.mode, "replacement-object")
        if entry.path == template_path
        else entry
        for entry in entries
    ]
    extensionless = verify_public_tree.TrackedEntry(
        "private/patient-image", object_id="extensionless-dicom"
    )
    entries.append(extensionless)
    blobs[extensionless.path] = b"\0" * 128 + b"DICM" + b"payload"

    issues = verify_public_tree.audit_entries(entries, blobs)
    issue_paths = {path for path, _reason in issues}

    assert {template_path, extensionless.path} <= issue_paths


def test_headerless_explicit_and_implicit_vr_dicom_fail():
    entries, blobs = _clean_audit_input()
    sop_class_uid = b"1.2.840.10008.5.1.4.1.1.2\0"
    explicit_vr = (
        b"\x08\x00\x16\x00UI"
        + len(sop_class_uid).to_bytes(2, "little")
        + sop_class_uid
    )
    implicit_vr = (
        b"\x08\x00\x16\x00"
        + len(sop_class_uid).to_bytes(4, "little")
        + sop_class_uid
        + b"\x08\x00\x18\x00\x04\x00\x00\x00" + b"1.2\0"
    )
    for index, (path, blob) in enumerate(
        (("private/raw-explicit", explicit_vr), ("private/raw-implicit", implicit_vr))
    ):
        entries.append(verify_public_tree.TrackedEntry(path, object_id=f"raw-{index}"))
        blobs[path] = blob

    issues = verify_public_tree.audit_entries(entries, blobs)
    issue_paths = {path for path, _reason in issues}

    assert {"private/raw-explicit", "private/raw-implicit"} <= issue_paths


def test_escaping_and_absolute_symlinks_fail():
    entries, blobs = _clean_audit_input()
    entries.extend(
        (
            verify_public_tree.TrackedEntry(
                "links/outside", mode="120000", object_id="outside-link"
            ),
            verify_public_tree.TrackedEntry(
                "links/absolute", mode="120000", object_id="absolute-link"
            ),
        )
    )
    blobs["links/outside"] = b"../../outside"
    blobs["links/absolute"] = b"C:/patient-data"

    issues = verify_public_tree.audit_entries(entries, blobs)
    issue_paths = {path for path, _reason in issues}

    assert {"links/outside", "links/absolute"} <= issue_paths


def test_dangerous_indexed_codex_and_devcontainer_settings_fail():
    entries, blobs = _clean_audit_input()
    blobs[".codex/config.toml"] = (
        'approval_policy = "never"\n'
        'approvals_reviewer = "user"\n'
        'sandbox_mode = "danger-full-access"\n\n'
        '[sandbox_workspace_write]\n'
        'network_access = true\n'
        'writable_roots = ["C:/patient-data"]\n'
    ).encode("utf-8")
    blobs[".devcontainer/devcontainer.json"] = json.dumps(
        {
            "image": "python:3.12",
            "privileged": True,
            "mounts": ["source=/home,target=/host,type=bind"],
            "remoteUser": "root",
        }
    ).encode("utf-8")

    issues = verify_public_tree.audit_entries(entries, blobs)
    issue_pairs = set(issues)

    assert any(path == ".codex/config.toml" for path, _reason in issue_pairs)
    assert (
        ".devcontainer/devcontainer.json",
        "additional host bind mounts are not allowed",
    ) in issue_pairs


def test_local_absolute_path_in_indexed_json_and_toml_configuration_fails():
    entries, blobs = _clean_audit_input()
    blobs["config/dicomxphits.paths.example.json"] = json.dumps(
        {"phits_executable_path": "C:/PHITS/bin/phits.exe"}
    ).encode("utf-8")
    toml_path = "config/site.toml"
    entries.append(verify_public_tree.TrackedEntry(toml_path, object_id="site-toml"))
    blobs[toml_path] = b'patient_data = "/srv/patient-data"\n'

    issues = verify_public_tree.audit_entries(entries, blobs)

    assert (
        "config/dicomxphits.paths.example.json",
        "configuration contains a local absolute path",
    ) in issues
    assert (toml_path, "configuration contains a local absolute path") in issues


def test_unsupported_indexed_configuration_format_fails_closed():
    entries, blobs = _clean_audit_input()
    yaml_path = "config/site.yaml"
    entries.append(verify_public_tree.TrackedEntry(yaml_path, object_id="site-yaml"))
    blobs[yaml_path] = b"patient_data: C:/patient-data\n"

    issues = verify_public_tree.audit_entries(entries, blobs)

    assert (yaml_path, "unsupported tracked configuration format") in issues
