from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "offline_install", ROOT / "tools" / "offline_install.py"
)
assert SPEC is not None and SPEC.loader is not None
offline_install = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = offline_install
SPEC.loader.exec_module(offline_install)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _powershell_function_prefix(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    functions, separator, _main = text.partition("\ntry {\n")
    assert separator
    return functions


def _trusted_windows_powershell() -> Path:
    return (
        Path(os.environ["SystemRoot"])
        / "System32"
        / "WindowsPowerShell"
        / "v1.0"
        / "powershell.exe"
    )


def _run_powershell_harness(path: Path, environment: dict[str, str]):
    return subprocess.run(
        [
            str(_trusted_windows_powershell()),
            "-NoLogo",
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(path),
        ],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env={**os.environ, **environment},
    )


def _make_bundle(root: Path) -> dict:
    payloads = {
        "install_offline.cmd": b"@echo off\r\n",
        "uninstall_offline.cmd": b"@echo off\r\n",
        "tools/offline_install.py": b"# synthetic helper\n",
        "tools/install_offline_verified.ps1": b"# synthetic verified stage\n",
        "tools/uninstall_offline_verified.ps1": b"# synthetic uninstall stage\n",
        "tools/lock_bundle_directories.ps1": (
            ROOT / "tools" / "lock_bundle_directories.ps1"
        ).read_bytes(),
        "launchers/run_gui_venv.cmd": b"@echo off\r\n",
        "pyproject.toml": b"[project]\nname='dicomxphits'\n",
        "requirements/offline-win64.txt": b"# synthetic lock\n",
        "wheelhouse/numpy-2.3.0-cp312-cp312-win_amd64.whl": b"numpy wheel",
        "wheelhouse/pydicom-3.0.1-py3-none-any.whl": b"pydicom wheel",
        "wheelhouse/setuptools-80.0.0-py3-none-any.whl": b"setuptools wheel",
        "wheelhouse/wheel-0.45.1-py3-none-any.whl": b"wheel wheel",
    }
    records = []
    for relative, content in payloads.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        records.append(
            {
                "path": relative,
                "role": "dependency-wheel" if relative.startswith("wheelhouse/") else "public-source",
                "size": len(content),
                "sha256": _sha256(path),
            }
        )
    manifest = {
        "schema_version": 1,
        "project_metadata": {
            "runtime_dependencies": ["numpy", "pydicom"],
            "editable_build_tools": ["setuptools", "wheel"],
        },
        "files": records,
    }
    manifest_path = root / "bundle-manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    lines = [f"{record['sha256']} *{record['path']}" for record in records]
    lines.append(f"{_sha256(manifest_path)} *bundle-manifest.json")
    (root / "SHA256SUMS.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return manifest


def _make_cmd_bootstrap_bundle(root: Path) -> tuple[dict, Path]:
    marker = root / "helper-executed.txt"
    payloads = {
        "install_offline.cmd": (ROOT / "install_offline.cmd").read_bytes(),
        "uninstall_offline.cmd": b"@echo off\r\n",
        "tools/install_offline_verified.ps1": (
            ROOT / "tools" / "install_offline_verified.ps1"
        ).read_bytes(),
        "tools/uninstall_offline_verified.ps1": b"# synthetic uninstall stage\n",
        "tools/lock_bundle_directories.ps1": (
            ROOT / "tools" / "lock_bundle_directories.ps1"
        ).read_bytes(),
        "tools/offline_install.py": (
            "from pathlib import Path\n"
            "Path(__file__).resolve().parents[1].joinpath("
            "'helper-executed.txt').write_text('executed', encoding='utf-8')\n"
        ).encode("utf-8"),
        "python/python.3.12.10.nupkg": b"synthetic runtime package",
        "python/tcltk.msi": b"synthetic Tcl/Tk component",
        "python/verifier/nuget.exe": b"synthetic verifier",
    }
    records = []
    for relative, content in payloads.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        records.append(
            {
                "path": relative,
                "role": "synthetic",
                "size": len(content),
                "sha256": _sha256(path),
            }
        )
    manifest = {"schema_version": 1, "files": records}
    _write_cmd_bootstrap_integrity(root, manifest)
    return manifest, marker


def _write_cmd_bootstrap_integrity(root: Path, manifest: dict) -> None:
    manifest_path = root / "bundle-manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    lines = [
        f"{_sha256(root / record['path'])} *{record['path']}"
        for record in manifest["files"]
    ]
    lines.append(f"{_sha256(manifest_path)} *bundle-manifest.json")
    (root / "SHA256SUMS.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _make_uninstall_cmd_bootstrap_bundle(root: Path) -> Path:
    marker = root / "uninstall-helper-executed.txt"
    payloads = {
        "uninstall_offline.cmd": (ROOT / "uninstall_offline.cmd").read_bytes(),
        "tools/uninstall_offline_verified.ps1": (
            "[IO.File]::WriteAllText((Join-Path "
            "$env:DICOMXPHITS_BUNDLE_ROOT 'uninstall-helper-executed.txt'),'ok')\n"
            "exit 0\n"
        ).encode("utf-8"),
        "tools/lock_bundle_directories.ps1": (
            ROOT / "tools" / "lock_bundle_directories.ps1"
        ).read_bytes(),
        "payload.txt": b"synthetic payload\n",
    }
    records = []
    for relative, content in payloads.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        records.append(
            {
                "path": relative,
                "role": "synthetic",
                "size": len(content),
                "sha256": _sha256(path),
            }
        )
    _write_cmd_bootstrap_integrity(root, {"schema_version": 1, "files": records})
    return marker


class FakeRunner:
    def __init__(self, *, venv_minor: int = 12) -> None:
        self.venv_minor = venv_minor
        self.calls: list[tuple[list[str], dict]] = []

    def __call__(self, command, **kwargs):
        command = [str(value) for value in command]
        self.calls.append((command, kwargs))
        if "pip" in command and "install" in command:
            return subprocess.CompletedProcess(command, 0, stdout="offline pip ok\n")
        program = command[-1] if command and command[-2:-1] == ["-c"] else ""
        if "importlib.metadata" in program:
            output = json.dumps(
                {
                    "python": "3.12.10",
                    "numpy": "2.3.0",
                    "pydicom": "3.0.1",
                    "dicomxphits": "1.0.1",
                }
            )
            return subprocess.CompletedProcess(command, 0, stdout=output + "\n")
        if "struct.calcsize" in program:
            output = json.dumps(
                {
                    "executable": command[0],
                    "implementation": "cpython",
                    "major": 3,
                    "minor": self.venv_minor,
                    "micro": 10,
                    "bits": 64,
                }
            )
            return subprocess.CompletedProcess(command, 0, stdout=output + "\n", stderr="")
        return subprocess.CompletedProcess(command, 0, stdout="")


@pytest.mark.skipif(sys.platform != "win32", reason="Windows PowerShell behavior")
def test_protected_runtime_identity_binds_root_and_manifest(tmp_path):
    stage = ROOT / "tools" / "install_offline_verified.ps1"
    functions = _powershell_function_prefix(stage)
    harness = tmp_path / "runtime-identity-harness.ps1"
    harness.write_text(
        functions
        + "\n$Same = Get-ProtectedRuntimeId $env:DICOMXPHITS_TEST_ROOT "
        "$env:DICOMXPHITS_TEST_MANIFEST_A\n"
        "$CaseOnly = Get-ProtectedRuntimeId "
        "$env:DICOMXPHITS_TEST_ROOT_CASE $env:DICOMXPHITS_TEST_MANIFEST_A\n"
        "$Changed = Get-ProtectedRuntimeId $env:DICOMXPHITS_TEST_ROOT "
        "$env:DICOMXPHITS_TEST_MANIFEST_B\n"
        "$MalformedRejected = $false\n"
        "try { $null = Get-ProtectedRuntimeId $env:DICOMXPHITS_TEST_ROOT 'bad' }\n"
        "catch { $MalformedRejected = $true }\n"
        "$MissingRejected = $false\n"
        "try { $null = Get-ProtectedRuntimeId $env:DICOMXPHITS_TEST_ROOT '' }\n"
        "catch { $MissingRejected = $true }\n"
        "Write-Output ('SAME=' + $Same)\n"
        "Write-Output ('CASE=' + $CaseOnly)\n"
        "Write-Output ('CHANGED=' + $Changed)\n"
        "Write-Output ('MALFORMED_REJECTED=' + $MalformedRejected)\n"
        "Write-Output ('MISSING_REJECTED=' + $MissingRejected)\n",
        encoding="utf-8",
    )
    bundle_root = str((tmp_path / "bundle root").resolve())
    manifest_a = "a" * 64
    manifest_b = "b" * 64
    trusted_powershell = (
        Path(os.environ["SystemRoot"])
        / "System32"
        / "WindowsPowerShell"
        / "v1.0"
        / "powershell.exe"
    )
    environment = {
        **os.environ,
        "DICOMXPHITS_BUNDLE_ROOT": bundle_root,
        "DICOMXPHITS_BUNDLE_MANIFEST_SHA256": manifest_a,
        "DICOMXPHITS_VERIFIED_STAGE": "synthetic-stage",
        "DICOMXPHITS_TEST_ROOT": bundle_root,
        "DICOMXPHITS_TEST_ROOT_CASE": bundle_root.swapcase(),
        "DICOMXPHITS_TEST_MANIFEST_A": manifest_a,
        "DICOMXPHITS_TEST_MANIFEST_B": manifest_b,
    }
    result = subprocess.run(
        [
            str(trusted_powershell),
            "-NoLogo",
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(harness),
        ],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=environment,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    values = dict(line.split("=", 1) for line in result.stdout.splitlines())
    expected = hashlib.sha256(
        (
            "bundle-root-manifest-v1\n"
            + str(Path(bundle_root).resolve()).upper()
            + "\n"
            + manifest_a
        ).encode()
    ).hexdigest()
    assert values["SAME"] == expected
    assert values["CASE"] == expected
    assert values["CHANGED"] != expected
    assert values["MALFORMED_REJECTED"] == "True"
    assert values["MISSING_REJECTED"] == "True"


@pytest.mark.skipif(sys.platform != "win32", reason="Windows PowerShell behavior")
def test_exact_runtime_collision_fails_without_mutating_existing_target(tmp_path):
    stage = ROOT / "tools" / "install_offline_verified.ps1"
    existing_runtime = tmp_path / "existing-runtime"
    existing_runtime.mkdir()
    sentinel = existing_runtime / "sentinel.txt"
    sentinel.write_bytes(b"preserve exact runtime\n")
    harness = tmp_path / "runtime-collision-harness.ps1"
    harness.write_text(
        _powershell_function_prefix(stage)
        + "\n$script:RuntimeRoot=[IO.Path]::GetFullPath($env:DICOMXPHITS_TEST_RUNTIME)\n"
        "$script:ProtectedRuntimeReceipt=[IO.Path]::GetFullPath($env:DICOMXPHITS_TEST_RECEIPT)\n"
        "$script:RuntimeLog=[IO.Path]::GetFullPath($env:DICOMXPHITS_TEST_LOG)\n"
        "try { New-AuthenticatedPythonRuntime; exit 8 }\n"
        "catch {\n"
        "  if ($_.Exception.Message -notmatch 'already exists') { Write-Error $_; exit 9 }\n"
        "  Write-Output 'EXACT_COLLISION_REJECTED'\n"
        "  exit 0\n"
        "}\n",
        encoding="utf-8",
    )
    result = _run_powershell_harness(
        harness,
        {
            "DICOMXPHITS_BUNDLE_ROOT": str(tmp_path),
            "DICOMXPHITS_BUNDLE_MANIFEST_SHA256": "a" * 64,
            "DICOMXPHITS_VERIFIED_STAGE": "synthetic-stage",
            "DICOMXPHITS_TEST_RUNTIME": str(existing_runtime),
            "DICOMXPHITS_TEST_RECEIPT": str(tmp_path / "receipt.json"),
            "DICOMXPHITS_TEST_LOG": str(tmp_path / "runtime.log"),
        },
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "EXACT_COLLISION_REJECTED" in result.stdout.splitlines()
    assert sentinel.read_bytes() == b"preserve exact runtime\n"


@pytest.mark.skipif(sys.platform != "win32", reason="Windows PowerShell behavior")
@pytest.mark.parametrize(
    ("diagnostic", "expected"),
    [
        (
            {
                "schema_version": 1,
                "verified_stage": "expected-stage",
                "runtime_id": "a" * 64,
                "category": "runtime-construction",
                "message": "Protected target already exists.",
            },
            "Protected target already exists.",
        ),
        (
            {
                "schema_version": 1,
                "verified_stage": "wrong-stage",
                "runtime_id": "a" * 64,
                "category": "runtime-construction",
                "message": "must not be trusted",
            },
            "NULL",
        ),
        ({"malformed": True}, "NULL"),
        (None, "NULL"),
    ],
)
def test_runtime_failure_diagnostic_is_display_only_and_nonce_bound(
    tmp_path, diagnostic, expected
):
    stage = ROOT / "tools" / "install_offline_verified.ps1"
    diagnostic_path = tmp_path / "failure.json"
    if diagnostic is not None:
        diagnostic_path.write_text(json.dumps(diagnostic), encoding="utf-8")
    harness = tmp_path / "runtime-diagnostic-harness.ps1"
    harness.write_text(
        _powershell_function_prefix(stage)
        + "\nfunction Assert-NoReparsePath { param($Path,$Label) }\n"
        "function Assert-ProtectedRuntimeSecurity { param($Path,$IsDirectory,$Label) }\n"
        "$script:ProtectedFailureDiagnostic=[IO.Path]::GetFullPath($env:DICOMXPHITS_TEST_DIAGNOSTIC)\n"
        "$script:ProtectedRuntimeId='" + ("a" * 64) + "'\n"
        "$Reason=Read-ProtectedRuntimeFailureDiagnostic\n"
        "if ([string]::IsNullOrWhiteSpace($Reason)) { Write-Output 'NULL' }\n"
        "else { Write-Output $Reason }\n",
        encoding="utf-8",
    )
    result = _run_powershell_harness(
        harness,
        {
            "DICOMXPHITS_BUNDLE_ROOT": str(tmp_path),
            "DICOMXPHITS_BUNDLE_MANIFEST_SHA256": "b" * 64,
            "DICOMXPHITS_VERIFIED_STAGE": "expected-stage",
            "DICOMXPHITS_TEST_DIAGNOSTIC": str(diagnostic_path),
        },
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.strip() == expected


@pytest.mark.skipif(sys.platform != "win32", reason="Windows PowerShell behavior")
@pytest.mark.parametrize("problem", ["valid", "unknown", "modified", "reparse"])
def test_uninstall_inventory_rejects_unsafe_root_before_deletion(tmp_path, problem):
    bundle_root = tmp_path / "installed bundle"
    protected_root = tmp_path / "protected source"
    bundle_root.mkdir()
    protected_root.mkdir()
    payload = bundle_root / "payload.txt"
    payload.write_text("payload\n", encoding="utf-8")
    record = {
        "path": "payload.txt",
        "role": "public-source",
        "size": payload.stat().st_size,
        "sha256": _sha256(payload),
    }
    manifest = {"schema_version": 1, "files": [record]}
    for root in (bundle_root, protected_root):
        (root / "payload.txt").write_text("payload\n", encoding="utf-8")
        (root / "bundle-manifest.json").write_text(
            json.dumps(manifest, sort_keys=True) + "\n", encoding="utf-8"
        )
        (root / "SHA256SUMS.txt").write_text(
            f"{record['sha256']} *payload.txt\n", encoding="utf-8"
        )
    (bundle_root / ".venv" / "Scripts").mkdir(parents=True)
    (bundle_root / ".venv" / "Scripts" / "python.exe").write_bytes(b"generated")
    (bundle_root / "offline-install.log").write_text("generated\n", encoding="utf-8")
    if problem == "valid":
        expected = "INVENTORY_OK"
        expected_code = 0
    elif problem == "unknown":
        (bundle_root / "keep-me.txt").write_text("user content\n", encoding="utf-8")
        expected = "unknown file"
        expected_code = 17
    elif problem == "modified":
        payload.write_text("modified\n", encoding="utf-8")
        expected = "was modified"
        expected_code = 17
    else:
        (tmp_path / "junction target").mkdir()
        expected = "reparse point"
        expected_code = 17

    helper = ROOT / "tools" / "uninstall_offline_verified.ps1"
    harness = tmp_path / "uninstall-inventory-harness.ps1"
    harness.write_text(
        "$env:DICOMXPHITS_BUNDLE_ROOT=$env:DICOMXPHITS_TEST_ROOT\n"
        + _powershell_function_prefix(helper)
        + "\nfunction Assert-ProtectedSecurity { param($Path,$IsDirectory,$Label) }\n"
        "$script:BundleRoot=[IO.Path]::GetFullPath($env:DICOMXPHITS_TEST_ROOT)\n"
        "$script:BundlePrefix=$script:BundleRoot.TrimEnd([IO.Path]::DirectorySeparatorChar)+[IO.Path]::DirectorySeparatorChar\n"
        "$script:ProtectedSourceRoot=[IO.Path]::GetFullPath($env:DICOMXPHITS_TEST_PROTECTED)\n"
        "$script:BundleManifestSha256=$env:DICOMXPHITS_TEST_MANIFEST\n"
        "if ($env:DICOMXPHITS_TEST_PROBLEM -eq 'reparse') {"
        "New-Item -ItemType Junction -Path (Join-Path $script:BundleRoot 'linked') "
        "-Target $env:DICOMXPHITS_TEST_TARGET | Out-Null}\n"
        "try { Assert-ExactInstallationRoot; Write-Output 'INVENTORY_OK'; exit 0 }\n"
        "catch { Write-Output ('CONTROLLED=' + $_.Exception.Message); exit 17 }\n",
        encoding="utf-8",
    )
    trusted_powershell = (
        Path(os.environ["SystemRoot"])
        / "System32"
        / "WindowsPowerShell"
        / "v1.0"
        / "powershell.exe"
    )
    result = subprocess.run(
        [
            str(trusted_powershell),
            "-NoLogo",
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(harness),
        ],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env={
            **os.environ,
            "DICOMXPHITS_TEST_ROOT": str(bundle_root),
            "DICOMXPHITS_TEST_PROTECTED": str(protected_root),
            "DICOMXPHITS_TEST_MANIFEST": _sha256(protected_root / "bundle-manifest.json"),
            "DICOMXPHITS_TEST_PROBLEM": problem,
            "DICOMXPHITS_TEST_TARGET": str(tmp_path / "junction target"),
        },
    )

    assert result.returncode == expected_code, result.stdout + result.stderr
    assert expected in result.stdout
    assert bundle_root.is_dir()
    assert protected_root.is_dir()


@pytest.mark.skipif(sys.platform != "win32", reason="Windows PowerShell behavior")
@pytest.mark.parametrize(
    "mismatch",
    [
        "none",
        "bundle_root",
        "manifest",
        "runtime_root",
        "user_sid",
        "identity_schema",
        "malformed",
    ],
)
def test_uninstall_receipt_is_bound_to_exact_installation(tmp_path, mismatch):
    bundle_root = tmp_path / "installed bundle"
    runtime_root = tmp_path / "protected runtime"
    protected_source = runtime_root / "dicomxphits-source"
    bundle_root.mkdir()
    protected_source.mkdir(parents=True)
    receipt = tmp_path / "runtime-receipt.json"
    sentinel = runtime_root / "sentinel.txt"
    sentinel.write_bytes(b"protected runtime remains\n")
    harness = tmp_path / "uninstall-receipt-harness.ps1"
    harness.write_text(
        _powershell_function_prefix(ROOT / "tools" / "uninstall_offline_verified.ps1")
        + "\nfunction Assert-ProtectedSecurity { param($Path,$IsDirectory,$Label) }\n"
        "$script:InstallingUserSid=[Security.Principal.WindowsIdentity]::GetCurrent().User\n"
        "$script:BundleManifestSha256='" + ("a" * 64) + "'\n"
        "$script:RuntimeRoot=[IO.Path]::GetFullPath($env:DICOMXPHITS_TEST_RUNTIME)\n"
        "$script:ProtectedSourceRoot=[IO.Path]::GetFullPath($env:DICOMXPHITS_TEST_SOURCE)\n"
        "$script:ProtectedRuntimeReceipt=[IO.Path]::GetFullPath($env:DICOMXPHITS_TEST_RECEIPT)\n"
        "$Record=[ordered]@{schema_version=1;runtime_identity_schema='bundle-root-manifest-v1';"
        "bundle_manifest_sha256=$script:BundleManifestSha256;bundle_root=$script:BundleRoot;"
        "runtime_root=$script:RuntimeRoot;protected_source_root=$script:ProtectedSourceRoot;"
        "installing_user_sid=$script:InstallingUserSid.Value}\n"
        "switch ($env:DICOMXPHITS_TEST_MISMATCH) {\n"
        " 'bundle_root' {$Record.bundle_root=[IO.Path]::GetFullPath((Join-Path $script:BundleRoot '..\\other'))}\n"
        " 'manifest' {$Record.bundle_manifest_sha256='" + ("b" * 64) + "'}\n"
        " 'runtime_root' {$Record.runtime_root=[IO.Path]::GetFullPath((Join-Path $script:RuntimeRoot '..\\other'))}\n"
        " 'user_sid' {$Record.installing_user_sid='S-1-5-18'}\n"
        " 'identity_schema' {$Record.runtime_identity_schema='wrong-schema'}\n"
        "}\n"
        "if ($env:DICOMXPHITS_TEST_MISMATCH -eq 'malformed') {"
        "Set-Content -LiteralPath $script:ProtectedRuntimeReceipt -Value '{' -Encoding UTF8}\n"
        "else {$Record|ConvertTo-Json -Compress|Set-Content -LiteralPath $script:ProtectedRuntimeReceipt -Encoding UTF8}\n"
        "try { $null=Import-ExactProtectedReceipt; Write-Output 'RECEIPT_OK'; exit 0 }\n"
        "catch { Write-Output ('CONTROLLED=' + $_.Exception.Message); exit 17 }\n",
        encoding="utf-8",
    )
    result = _run_powershell_harness(
        harness,
        {
            "DICOMXPHITS_BUNDLE_ROOT": str(bundle_root),
            "DICOMXPHITS_TEST_RUNTIME": str(runtime_root),
            "DICOMXPHITS_TEST_SOURCE": str(protected_source),
            "DICOMXPHITS_TEST_RECEIPT": str(receipt),
            "DICOMXPHITS_TEST_MISMATCH": mismatch,
        },
    )

    expected_code = 0 if mismatch == "none" else 17
    assert result.returncode == expected_code, result.stdout + result.stderr
    if mismatch == "none":
        assert "RECEIPT_OK" in result.stdout
    elif mismatch != "malformed":
        assert "does not identify this exact installation" in result.stdout
    else:
        assert "CONTROLLED=" in result.stdout
    assert sentinel.read_bytes() == b"protected runtime remains\n"


@pytest.mark.skipif(sys.platform != "win32", reason="Windows PowerShell behavior")
def test_uninstall_process_guard_refuses_synthetic_installed_gui(tmp_path):
    bundle_root = tmp_path / "installed bundle"
    bundle_root.mkdir()
    harness = tmp_path / "uninstall-process-harness.ps1"
    harness.write_text(
        _powershell_function_prefix(ROOT / "tools" / "uninstall_offline_verified.ps1")
        + "\n$script:RuntimeRoot=[IO.Path]::GetFullPath($env:DICOMXPHITS_TEST_RUNTIME)\n"
        "function Get-CimInstance { [pscustomobject]@{ProcessId=4242;Name='pythonw.exe';"
        "ExecutablePath=(Join-Path $script:BundleRoot '.venv\\Scripts\\pythonw.exe')} }\n"
        "try { Assert-NoAssociatedProcesses @(); exit 8 }\n"
        "catch {\n"
        " if ($_.Exception.Message -notmatch 'Associated process must be closed') {Write-Error $_;exit 9}\n"
        " Write-Output 'ACTIVE_PROCESS_REJECTED'; exit 0\n"
        "}\n",
        encoding="utf-8",
    )
    result = _run_powershell_harness(
        harness,
        {
            "DICOMXPHITS_BUNDLE_ROOT": str(bundle_root),
            "DICOMXPHITS_TEST_RUNTIME": str(tmp_path / "runtime"),
        },
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "ACTIVE_PROCESS_REJECTED" in result.stdout.splitlines()


@pytest.mark.skipif(sys.platform != "win32", reason="Windows file-lock behavior")
def test_uninstall_refuses_locked_root_before_any_exact_target_deletion(tmp_path):
    bundle_root = tmp_path / "installed bundle"
    runtime_root = tmp_path / "protected runtime"
    cleanup = tmp_path / "cleanup staging"
    for directory in (bundle_root, runtime_root, cleanup):
        directory.mkdir()
        (directory / "sentinel.txt").write_bytes(b"must remain\n")
    receipt = tmp_path / "runtime-receipt.json"
    runtime_log = tmp_path / "runtime-msi.log"
    for path in (receipt, runtime_log):
        path.write_bytes(b"must remain\n")

    harness = tmp_path / "uninstall-delete-share-harness.ps1"
    harness.write_text(
        _powershell_function_prefix(ROOT / "tools" / "uninstall_offline_verified.ps1")
        + "\n"
        + (ROOT / "tools" / "lock_bundle_directories.ps1").read_text(
            encoding="utf-8"
        )
        + "\n$Targets=@($env:DICOMXPHITS_TEST_ROOT,$env:DICOMXPHITS_TEST_RUNTIME,"
        "$env:DICOMXPHITS_TEST_RECEIPT,$env:DICOMXPHITS_TEST_LOG,"
        "$env:DICOMXPHITS_TEST_CLEANUP)\n"
        "$Lock=Open-LockedBundleDirectory $env:DICOMXPHITS_TEST_ROOT\n"
        "try {\n"
        " try {$DeleteHandles=Open-ExactUninstallDeleteHandles $Targets;"
        "foreach($Handle in $DeleteHandles){$Handle.Dispose()};exit 8}\n"
        " catch {\n"
        "  if ($_.Exception.Message -notmatch 'target is in use') {Write-Error $_;exit 9}\n"
        "  foreach($Target in $Targets){if(-not([IO.File]::Exists($Target)-or"
        "[IO.Directory]::Exists($Target))){exit 10}}\n"
        "  Write-Output 'LOCKED_TARGETS_PRESERVED'\n"
        " }\n"
        "}\n"
        "finally {$Lock.Dispose()}\n"
        "$DeleteHandles=Open-ExactUninstallDeleteHandles $Targets\n"
        "foreach($Handle in $DeleteHandles){$Handle.Dispose()}\n"
        "Write-Output 'UNLOCKED_PREFLIGHT_OK'\n",
        encoding="utf-8",
    )
    result = _run_powershell_harness(
        harness,
        {
            "DICOMXPHITS_BUNDLE_ROOT": str(bundle_root),
            "DICOMXPHITS_TEST_ROOT": str(bundle_root),
            "DICOMXPHITS_TEST_RUNTIME": str(runtime_root),
            "DICOMXPHITS_TEST_RECEIPT": str(receipt),
            "DICOMXPHITS_TEST_LOG": str(runtime_log),
            "DICOMXPHITS_TEST_CLEANUP": str(cleanup),
        },
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "LOCKED_TARGETS_PRESERVED" in result.stdout.splitlines()
    assert "UNLOCKED_PREFLIGHT_OK" in result.stdout.splitlines()
    for directory in (bundle_root, runtime_root, cleanup):
        assert (directory / "sentinel.txt").read_bytes() == b"must remain\n"
    assert receipt.read_bytes() == b"must remain\n"
    assert runtime_log.read_bytes() == b"must remain\n"


@pytest.mark.skipif(sys.platform != "win32", reason="Windows PowerShell behavior")
@pytest.mark.parametrize("problem", ["valid", "unknown", "modified_helper"])
def test_uninstall_cleanup_staging_is_closed_and_authenticated(tmp_path, problem):
    bundle_root = tmp_path / "installed bundle"
    protected_source = tmp_path / "protected source"
    cleanup = tmp_path / "cleanup staging"
    (protected_source / "tools").mkdir(parents=True)
    cleanup.mkdir()
    helper_bytes = b"# authenticated cleanup helper\n"
    (protected_source / "tools" / "uninstall_offline_verified.ps1").write_bytes(
        helper_bytes
    )
    (cleanup / "uninstall_offline_verified.ps1").write_bytes(helper_bytes)
    (cleanup / "cleanup-plan.json").write_text("{}\n", encoding="utf-8")
    if problem == "unknown":
        (cleanup / "unknown.txt").write_text("unknown\n", encoding="utf-8")
    elif problem == "modified_helper":
        (cleanup / "uninstall_offline_verified.ps1").write_text(
            "# modified\n", encoding="utf-8"
        )
    harness = tmp_path / "uninstall-staging-harness.ps1"
    harness.write_text(
        _powershell_function_prefix(ROOT / "tools" / "uninstall_offline_verified.ps1")
        + "\nfunction Assert-ProtectedSecurity { param($Path,$IsDirectory,$Label) }\n"
        "$script:ProtectedSourceRoot=[IO.Path]::GetFullPath($env:DICOMXPHITS_TEST_SOURCE)\n"
        "try { Assert-ExactCleanupStaging $env:DICOMXPHITS_TEST_CLEANUP;"
        "Write-Output 'STAGING_OK';exit 0 }\n"
        "catch { Write-Output ('CONTROLLED=' + $_.Exception.Message);exit 17 }\n",
        encoding="utf-8",
    )
    result = _run_powershell_harness(
        harness,
        {
            "DICOMXPHITS_BUNDLE_ROOT": str(bundle_root),
            "DICOMXPHITS_TEST_SOURCE": str(protected_source),
            "DICOMXPHITS_TEST_CLEANUP": str(cleanup),
        },
    )

    expected_code = 0 if problem == "valid" else 17
    assert result.returncode == expected_code, result.stdout + result.stderr
    if problem == "valid":
        assert "STAGING_OK" in result.stdout
    else:
        assert "CONTROLLED=" in result.stdout
    assert cleanup.is_dir()


@pytest.mark.skipif(sys.platform != "win32", reason="Windows PowerShell behavior")
def test_uninstall_exact_cleanup_preserves_siblings(tmp_path):
    bundle_root = tmp_path / "installed bundle"
    runtime_parent = tmp_path / "offline-runtimes"
    runtime_root = runtime_parent / ("a" * 64)
    sibling_runtime = runtime_parent / ("b" * 64)
    sibling_install = tmp_path / "other installation"
    case_folder = tmp_path / "dicomxphits-cases" / "synthetic-case"
    external_tool = tmp_path / "external-tools" / "phits"
    user_settings = tmp_path / "LocalAppData" / "dicomxphits"
    preserved = (
        sibling_runtime,
        sibling_install,
        case_folder,
        external_tool,
        user_settings,
    )
    for directory in (bundle_root, runtime_root, *preserved):
        directory.mkdir(parents=True)
        (directory / "sentinel.txt").write_bytes(b"keep or remove\n")
    receipt = runtime_parent / (("a" * 64) + ".json")
    runtime_log = runtime_parent / (("a" * 64) + "-msi.log")
    failure = runtime_parent / (("a" * 64) + "-failure.json")
    for path in (receipt, runtime_log, failure):
        path.write_text("target\n", encoding="utf-8")

    helper = ROOT / "tools" / "uninstall_offline_verified.ps1"
    harness = tmp_path / "uninstall-cleanup-harness.ps1"
    harness.write_text(
        "$env:DICOMXPHITS_BUNDLE_ROOT=$env:DICOMXPHITS_TEST_ROOT\n"
        + _powershell_function_prefix(helper)
        + "\n$script:BundleRoot=[IO.Path]::GetFullPath($env:DICOMXPHITS_TEST_ROOT)\n"
        "$script:RuntimeRoot=[IO.Path]::GetFullPath($env:DICOMXPHITS_TEST_RUNTIME)\n"
        "$script:ProtectedRuntimeReceipt=[IO.Path]::GetFullPath($env:DICOMXPHITS_TEST_RECEIPT)\n"
        "$script:RuntimeLog=[IO.Path]::GetFullPath($env:DICOMXPHITS_TEST_LOG)\n"
        "$script:FailureDiagnostic=[IO.Path]::GetFullPath($env:DICOMXPHITS_TEST_FAILURE)\n"
        "$DeleteHandles=Open-ExactUninstallDeleteHandles @($script:BundleRoot,"
        "$script:RuntimeRoot,$script:ProtectedRuntimeReceipt,$script:RuntimeLog,"
        "$script:FailureDiagnostic)\n"
        "try {Remove-ExactInstallationTargets}\n"
        "finally {foreach($Handle in $DeleteHandles){$Handle.Dispose()}}\n"
        "Write-Output 'EXACT_CLEANUP_OK'\n",
        encoding="utf-8",
    )
    trusted_powershell = (
        Path(os.environ["SystemRoot"])
        / "System32"
        / "WindowsPowerShell"
        / "v1.0"
        / "powershell.exe"
    )
    result = subprocess.run(
        [
            str(trusted_powershell),
            "-NoLogo",
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(harness),
        ],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env={
            **os.environ,
            "DICOMXPHITS_TEST_ROOT": str(bundle_root),
            "DICOMXPHITS_TEST_RUNTIME": str(runtime_root),
            "DICOMXPHITS_TEST_RECEIPT": str(receipt),
            "DICOMXPHITS_TEST_LOG": str(runtime_log),
            "DICOMXPHITS_TEST_FAILURE": str(failure),
        },
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "EXACT_CLEANUP_OK" in result.stdout.splitlines()
    assert not bundle_root.exists()
    assert not runtime_root.exists()
    assert not receipt.exists()
    assert not runtime_log.exists()
    assert not failure.exists()
    for directory in preserved:
        assert (directory / "sentinel.txt").read_bytes() == b"keep or remove\n"


@pytest.mark.skipif(sys.platform != "win32", reason="Windows PowerShell behavior")
def test_uninstall_partial_failure_report_lists_only_exact_remaining_targets(tmp_path):
    bundle_root = tmp_path / "installed bundle"
    runtime_root = tmp_path / "runtime"
    cleanup = tmp_path / "cleanup"
    sibling = tmp_path / "sibling-must-not-be-reported"
    for directory in (bundle_root, runtime_root, cleanup, sibling):
        directory.mkdir()
    acl_template = cleanup / "acl-template.txt"
    acl_template.write_text("template\n", encoding="utf-8")
    harness = tmp_path / "uninstall-failure-report-harness.ps1"
    harness.write_text(
        _powershell_function_prefix(ROOT / "tools" / "uninstall_offline_verified.ps1")
        + "\nfunction Assert-ProtectedSecurity { param($Path,$IsDirectory,$Label) }\n"
        "function Get-ProtectedRuntimeSecurity { param($IsDirectory) "
        "return [IO.File]::GetAccessControl($env:DICOMXPHITS_TEST_ACL_TEMPLATE) }\n"
        "$script:InstallingUserSid=[Security.Principal.WindowsIdentity]::GetCurrent().User\n"
        "$script:RuntimeRoot=[IO.Path]::GetFullPath($env:DICOMXPHITS_TEST_RUNTIME)\n"
        "$script:ProtectedRuntimeReceipt=[IO.Path]::GetFullPath($env:DICOMXPHITS_TEST_RECEIPT)\n"
        "$script:RuntimeLog=[IO.Path]::GetFullPath($env:DICOMXPHITS_TEST_LOG)\n"
        "$script:FailureDiagnostic=[IO.Path]::GetFullPath($env:DICOMXPHITS_TEST_DIAGNOSTIC)\n"
        "$script:ProtectedRuntimeId='" + ("a" * 64) + "'\n"
        "Write-ProtectedCleanupFailure $env:DICOMXPHITS_TEST_CLEANUP 'synthetic partial failure'\n",
        encoding="utf-8",
    )
    result = _run_powershell_harness(
        harness,
        {
            "DICOMXPHITS_BUNDLE_ROOT": str(bundle_root),
            "DICOMXPHITS_UNINSTALL_NONCE": "b" * 32,
            "DICOMXPHITS_TEST_RUNTIME": str(runtime_root),
            "DICOMXPHITS_TEST_RECEIPT": str(tmp_path / "missing-receipt.json"),
            "DICOMXPHITS_TEST_LOG": str(tmp_path / "missing-log.txt"),
            "DICOMXPHITS_TEST_DIAGNOSTIC": str(tmp_path / "missing-diagnostic.json"),
            "DICOMXPHITS_TEST_CLEANUP": str(cleanup),
            "DICOMXPHITS_TEST_ACL_TEMPLATE": str(acl_template),
        },
    )

    assert result.returncode == 0, result.stdout + result.stderr
    report = json.loads((cleanup / "failure.json").read_text(encoding="utf-8-sig"))
    assert report["message"] == "synthetic partial failure"
    assert {Path(path) for path in report["remaining_paths"]} == {
        bundle_root.resolve(),
        runtime_root.resolve(),
        cleanup.resolve(),
    }
    assert sibling.resolve() not in {Path(path) for path in report["remaining_paths"]}


@pytest.mark.skipif(sys.platform != "win32", reason="Windows PowerShell behavior")
def test_uninstall_waits_for_direct_elevated_stage_without_descendant_wait(tmp_path):
    helper = ROOT / "tools" / "uninstall_offline_verified.ps1"
    harness = tmp_path / "uninstall-direct-stage-wait-harness.ps1"
    harness.write_text(
        _powershell_function_prefix(helper)
        + "\n$script:BundleRoot=[IO.Path]::GetFullPath($env:DICOMXPHITS_TEST_ROOT)\n"
        "$script:BundleManifestSha256='" + ("a" * 64) + "'\n"
        "$script:ProtectedRuntimeParent=[IO.Path]::GetFullPath($env:DICOMXPHITS_TEST_RUNTIME_PARENT)\n"
        "$script:ProtectedRuntimeId='" + ("b" * 64) + "'\n"
        "$script:ProtectedSourceRoot=[IO.Path]::GetFullPath($env:DICOMXPHITS_TEST_SOURCE)\n"
        "$script:FakeWaitCalled=$false\n"
        "$script:StartProcessWaitSwitch=$false\n"
        "$script:FakeProcess=[pscustomobject]@{ExitCode=0}\n"
        "$script:FakeProcess|Add-Member -MemberType ScriptMethod -Name WaitForExit "
        "-Value {$script:FakeWaitCalled=$true}\n"
        "function Get-CimInstance { [pscustomobject]@{ParentProcessId=4242} }\n"
        "function Start-Process {\n"
        " param([string]$FilePath,[string]$Verb,[switch]$Wait,[switch]$PassThru,"
        "[string]$WindowStyle,[object[]]$ArgumentList)\n"
        " $script:StartProcessWaitSwitch=[bool]$Wait\n"
        " return $script:FakeProcess\n"
        "}\n"
        "$Cleanup=Invoke-ElevatedCleanup $env:SystemRoot\n"
        "if (-not $script:FakeWaitCalled) {exit 8}\n"
        "if ($script:StartProcessWaitSwitch) {exit 9}\n"
        "if ($Cleanup -notmatch 'offline-cleanup') {exit 10}\n"
        "Write-Output 'DIRECT_STAGE_WAIT_ONLY'\n",
        encoding="utf-8",
    )
    result = _run_powershell_harness(
        harness,
        {
            "DICOMXPHITS_BUNDLE_ROOT": str(tmp_path),
            "DICOMXPHITS_TEST_ROOT": str(tmp_path / "bundle"),
            "DICOMXPHITS_TEST_RUNTIME_PARENT": str(
                tmp_path / "ProgramData" / "dicomxphits" / "offline-runtimes"
            ),
            "DICOMXPHITS_TEST_SOURCE": str(tmp_path / "protected-source"),
        },
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "DIRECT_STAGE_WAIT_ONLY" in result.stdout.splitlines()


def test_offline_uninstaller_has_bounded_verified_contract():
    cmd = (ROOT / "uninstall_offline.cmd").read_text(encoding="utf-8")
    helper = (ROOT / "tools" / "uninstall_offline_verified.ps1").read_text(
        encoding="utf-8"
    )
    install_cmd = (ROOT / "install_offline.cmd").read_text(encoding="utf-8")
    install_stage = (ROOT / "tools" / "install_offline_verified.ps1").read_text(
        encoding="utf-8"
    )

    assert "%__APPDIR__%WindowsPowerShell\\v1.0\\powershell.exe" in cmd
    assert "Type UNINSTALL" in helper
    assert "Import-ExactProtectedReceipt" in helper
    assert "Assert-ExactInstallationRoot" in helper
    assert "Assert-NoAssociatedProcesses" in helper
    assert "Writable uninstall helper does not match" in helper
    assert "Write-ProtectedCleanupPlan" in helper
    assert "Assert-ProtectedCleanupPlan" in helper
    assert "Assert-ExactCleanupStaging" in helper
    assert "cleanup_helper_sha256" in helper
    assert "failure.json" in helper
    assert "Remove-ExactInstallationTargets" in helper
    assert "Open-ExactUninstallDeleteHandles" in helper
    assert "Cannot safely begin uninstallation because a target is in use" in helper
    assert "Cleanup staging remains after cleanup" in helper
    assert "-Verb RunAs -Wait" not in helper
    assert "$Process.WaitForExit()" in helper
    assert "$BundleRoot, $RuntimeRoot, $ProtectedRuntimeReceipt" in helper
    assert "LocalAppData" not in helper
    assert "Get-ChildItem" not in helper
    assert "DICOMXPHITS_BUNDLE_MANIFEST_SHA256" in install_cmd
    assert "runtime_identity_schema = $RuntimeIdentitySchema" in install_stage
    assert "bundle_manifest_sha256 = $BundleManifestSha256" in install_stage
    assert "Write-ProtectedRuntimeFailureDiagnostic" in install_stage
    assert "Read-ProtectedRuntimeFailureDiagnostic" in install_stage


@pytest.mark.skipif(sys.platform != "win32", reason="Windows bootstrap behavior")
@pytest.mark.parametrize("tamper_helper", [False, True])
def test_uninstall_cmd_verifies_and_locks_payloads_before_helper(tmp_path, tamper_helper):
    root = tmp_path / "offline uninstall bootstrap"
    root.mkdir()
    marker = _make_uninstall_cmd_bootstrap_bundle(root)
    if tamper_helper:
        (root / "tools" / "uninstall_offline_verified.ps1").write_text(
            "raise changed\n", encoding="utf-8"
        )

    result = subprocess.run(
        ["cmd.exe", "/d", "/c", str(root / "uninstall_offline.cmd")],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env={**os.environ, "PYTHONUTF8": "1"},
    )

    if tamper_helper:
        assert result.returncode != 0
        assert "SHA-256 mismatch" in result.stdout + result.stderr
        assert not marker.exists()
    else:
        assert result.returncode == 0, result.stdout + result.stderr
        assert marker.read_text(encoding="utf-8") == "ok"


def test_sha256_mismatch_is_rejected_before_installation(tmp_path):
    _make_bundle(tmp_path)
    (tmp_path / "wheelhouse" / "pydicom-3.0.1-py3-none-any.whl").write_bytes(
        b"changed"
    )

    with pytest.raises(offline_install.OfflineInstallError, match="SHA-256 mismatch"):
        offline_install.verify_bundle(tmp_path)


@pytest.mark.parametrize(
    "extra_name",
    [
        "numpy-99.0.0-cp312-cp312-win_amd64.whl",
        "numpy-99.0.0.tar.gz",
    ],
)
def test_unmanifested_wheelhouse_artifact_is_rejected(tmp_path, extra_name):
    _make_bundle(tmp_path)
    (tmp_path / "wheelhouse" / extra_name).write_bytes(b"unverified artifact")

    with pytest.raises(
        offline_install.OfflineInstallError,
        match="verified manifest",
    ):
        offline_install.verify_bundle(tmp_path)


def test_unmanifested_setup_py_is_rejected(tmp_path):
    _make_bundle(tmp_path)
    (tmp_path / "setup.py").write_text("raise SystemExit(99)\n", encoding="utf-8")
    runner = FakeRunner()

    with pytest.raises(
        offline_install.OfflineInstallError,
        match="Bundle source tree differs from the verified manifest",
    ):
        offline_install.install_bundle(tmp_path, runner=runner)

    assert runner.calls == []


@pytest.mark.skipif(sys.platform != "win32", reason="Windows bootstrap behavior")
@pytest.mark.parametrize("inventory_problem", ["empty", "missing-helper", "manifest-mismatch"])
def test_cmd_rejects_incomplete_or_manifest_inconsistent_inventory_before_python(
    tmp_path, inventory_problem
):
    root = tmp_path / "日本語 user" / "offline bootstrap"
    root.mkdir(parents=True)
    manifest, marker = _make_cmd_bootstrap_bundle(root)
    checksum_path = root / "SHA256SUMS.txt"
    if inventory_problem == "empty":
        checksum_path.write_text("", encoding="utf-8")
    elif inventory_problem == "missing-helper":
        lines = checksum_path.read_text(encoding="utf-8").splitlines()
        checksum_path.write_text(
            "\n".join(
                line for line in lines if not line.endswith("*tools/offline_install.py")
            )
            + "\n",
            encoding="utf-8",
        )
    else:
        helper_record = next(
            record
            for record in manifest["files"]
            if record["path"] == "tools/offline_install.py"
        )
        helper_record["sha256"] = "0" * 64
        _write_cmd_bootstrap_integrity(root, manifest)
    environment = os.environ.copy()
    environment["PYTHONUTF8"] = "1"

    result = subprocess.run(
        ["cmd.exe", "/d", "/c", str(root / "install_offline.cmd")],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=environment,
    )

    assert result.returncode != 0
    assert "Initial SHA-256 verification passed." not in result.stdout
    assert not marker.exists()
    assert not (root / ".venv").exists()


@pytest.mark.skipif(sys.platform != "win32", reason="Windows bootstrap behavior")
@pytest.mark.parametrize("launcher", ["cmd", "powershell-parent"])
def test_cmd_accepts_complete_manifest_consistent_inventory(tmp_path, launcher):
    root = tmp_path / "日本語 user" / "valid offline bootstrap"
    root.mkdir(parents=True)
    manifest, marker = _make_cmd_bootstrap_bundle(root)
    stage = root / "tools" / "install_offline_verified.ps1"
    stage.write_text(
        "$ErrorActionPreference = 'Stop'\n"
        "$Root = $env:DICOMXPHITS_BUNDLE_ROOT\n"
        "$MovedRoot = $Root + '-moved'\n"
        "$RootMoved = $false\n"
        "try { [IO.Directory]::Move($Root, $MovedRoot); $RootMoved = $true }\n"
        "catch { [IO.File]::WriteAllText((Join-Path "
        "$Root 'root-directory-rename-blocked.txt'),'blocked') }\n"
        "if ($RootMoved) { [IO.Directory]::Move($MovedRoot, $Root); "
        "throw 'bundle root rename was not blocked' }\n"
        "$Tools = Join-Path $env:DICOMXPHITS_BUNDLE_ROOT 'tools'\n"
        "try { [IO.Directory]::Move($Tools, ($Tools + '-moved')); exit 98 }\n"
        "catch { [IO.File]::WriteAllText((Join-Path "
        "$env:DICOMXPHITS_BUNDLE_ROOT 'directory-rename-blocked.txt'),'blocked') }\n"
        "$Helper = Join-Path $env:DICOMXPHITS_BUNDLE_ROOT 'tools\\offline_install.py'\n"
        "& $env:DICOMXPHITS_TEST_PYTHON -I -S -B $Helper\n"
        "exit $LASTEXITCODE\n",
        encoding="utf-8",
    )
    helper = root / "tools" / "offline_install.py"
    helper.write_text(
        "import sys\n"
        "from pathlib import Path\n"
        "try:\n"
        "    Path(__file__).write_text('replaced after verification', encoding='utf-8')\n"
        "except OSError:\n"
        "    Path(__file__).resolve().parents[1].joinpath(\n"
        "        'replacement-blocked.txt'\n"
        "    ).write_text('blocked', encoding='utf-8')\n"
        "else:\n"
        "    raise SystemExit(99)\n"
        "Path(__file__).resolve().parents[1].joinpath("
        "'helper-executed.txt').write_text('executed', encoding='utf-8')\n",
        encoding="utf-8",
    )
    helper_record = next(
        record
        for record in manifest["files"]
        if record["path"] == "tools/offline_install.py"
    )
    helper_record["size"] = helper.stat().st_size
    helper_record["sha256"] = _sha256(helper)
    stage_record = next(
        record
        for record in manifest["files"]
        if record["path"] == "tools/install_offline_verified.ps1"
    )
    stage_record["size"] = stage.stat().st_size
    stage_record["sha256"] = _sha256(stage)
    _write_cmd_bootstrap_integrity(root, manifest)
    environment = os.environ.copy()
    environment.update(
        {"PYTHONUTF8": "1", "DICOMXPHITS_TEST_PYTHON": sys.executable}
    )

    if launcher == "powershell-parent":
        trusted_powershell = (
            Path(os.environ["SystemRoot"])
            / "System32"
            / "WindowsPowerShell"
            / "v1.0"
            / "powershell.exe"
        )
        command = [
            str(trusted_powershell),
            "-NoLogo",
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            "& '.\\install_offline.cmd'; exit $LASTEXITCODE",
        ]
    else:
        command = ["cmd.exe", "/d", "/c", str(root / "install_offline.cmd")]

    result = subprocess.run(
        command,
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=environment,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "Initial SHA-256 verification passed." in result.stdout
    assert (root / "root-directory-rename-blocked.txt").read_text() == "blocked"
    assert (root / "directory-rename-blocked.txt").read_text() == "blocked"
    assert (root / "replacement-blocked.txt").read_text(encoding="utf-8") == "blocked"
    assert marker.read_text(encoding="utf-8") == "executed"


@pytest.mark.parametrize(
    "line,match",
    [
        ("0" * 64 + " *../escape.whl\n", "not normalized"),
        ("0" * 64 + " *C:/absolute.whl\n", "drive"),
        (
            "0" * 64 + " *wheelhouse/a.whl\n" + "1" * 64 + " *wheelhouse/a.whl\n",
            "Duplicate",
        ),
    ],
)
def test_unsafe_or_duplicate_checksum_paths_are_rejected(line, match):
    with pytest.raises(offline_install.OfflineInstallError, match=match):
        offline_install.parse_checksums(line)


def test_incompatible_existing_venv_is_rejected_without_deletion(tmp_path):
    venv_python = tmp_path / ".venv" / "Scripts" / "python.exe"
    venv_python.parent.mkdir(parents=True)
    venv_python.write_bytes(b"synthetic Python")
    sentinel = tmp_path / ".venv" / "keep-me.txt"
    sentinel.write_text("preserve", encoding="utf-8")
    logger = offline_install.InstallLogger(tmp_path / "offline-install.log")

    with pytest.raises(offline_install.OfflineInstallError, match="not CPython 3.12"):
        offline_install.ensure_venv(
            tmp_path,
            Path(sys.executable),
            logger,
            runner=FakeRunner(venv_minor=11),
        )

    assert sentinel.read_text(encoding="utf-8") == "preserve"
    assert venv_python.exists()


def test_linked_existing_venv_is_rejected_without_probing(tmp_path, monkeypatch):
    venv_python = tmp_path / ".venv" / "Scripts" / "python.exe"
    venv_python.parent.mkdir(parents=True)
    venv_python.write_bytes(b"synthetic Python")
    logger = offline_install.InstallLogger(tmp_path / "offline-install.log")
    original_is_junction = Path.is_junction

    def report_venv_as_junction(path):
        return path == tmp_path / ".venv" or original_is_junction(path)

    monkeypatch.setattr(Path, "is_junction", report_venv_as_junction)
    runner = FakeRunner()

    with pytest.raises(
        offline_install.OfflineInstallError,
        match="symbolic link or directory junction",
    ):
        offline_install.ensure_venv(
            tmp_path,
            Path(sys.executable),
            logger,
            runner=runner,
        )

    assert runner.calls == []
    assert venv_python.exists()


def test_offline_install_uses_only_bundled_wheels_in_unicode_space_path(tmp_path):
    source_root = tmp_path / "protected source"
    install_root = tmp_path / "日本語 user" / "offline bundle"
    source_root.mkdir(parents=True)
    install_root.mkdir(parents=True)
    _make_bundle(source_root)
    venv_python = install_root / ".venv" / "Scripts" / "python.exe"
    venv_python.parent.mkdir(parents=True)
    venv_python.write_bytes(b"synthetic Python")
    runner = FakeRunner()

    selected, versions = offline_install.install_bundle(
        source_root, install_root=install_root, runner=runner
    )

    assert selected == venv_python
    assert versions == {
        "python": "3.12.10",
        "numpy": "2.3.0",
        "pydicom": "3.0.1",
        "dicomxphits": "1.0.1",
    }
    pip_calls = [
        (command, kwargs)
        for command, kwargs in runner.calls
        if "pip" in command and "install" in command
    ]
    assert len(pip_calls) == 2
    for index, (command, kwargs) in enumerate(pip_calls):
        assert command[1:4] == ["-I", "-m", "pip"]
        assert "--no-index" in command
        assert "--find-links" in command
        assert str(source_root / "wheelhouse") in command
        assert "--no-build-isolation" in command
        if index == 0:
            assert "--force-reinstall" in command
            assert "--require-hashes" in command
            assert "--requirement" in command
            assert str(source_root / "requirements" / "offline-win64.txt") in command
        else:
            assert "--no-deps" in command
        assert kwargs["env"]["PIP_NO_INDEX"] == "1"
        assert kwargs["env"]["PIP_FIND_LINKS"] == str(source_root / "wheelhouse")
        assert not any(value.startswith(("http://", "https://")) for value in command)
    assert str(source_root) in pip_calls[-1][0]
    assert (install_root / "offline-install.log").is_file()


def test_new_venv_creation_uses_isolated_module_resolution(tmp_path):
    logger = offline_install.InstallLogger(tmp_path / "offline-install.log")
    runner = FakeRunner()

    with pytest.raises(
        offline_install.OfflineInstallError,
        match="venv creation returned success but Python is missing",
    ):
        offline_install.ensure_venv(
            tmp_path,
            Path(sys.executable),
            logger,
            runner=runner,
        )

    command, kwargs = runner.calls[0]
    assert command[1:6] == ["-I", "-S", "-B", "-m", "venv"]
    assert kwargs["cwd"] == tmp_path.resolve()


def test_python_probe_disables_site_customization():
    command = offline_install.python_probe_command(Path("python.exe"))

    assert command[1:5] == ["-I", "-S", "-B", "-c"]


def test_gui_is_only_started_after_affirmative_choice(tmp_path, monkeypatch):
    launcher = tmp_path / "launchers" / "run_gui_venv.cmd"
    launcher.parent.mkdir()
    launcher.write_text("@echo off\n", encoding="utf-8")
    calls = []

    def fake_popen(command, **kwargs):
        calls.append((command, kwargs))
        return object()

    assert not offline_install.offer_gui_launch(
        tmp_path, input_fn=lambda _prompt: "", popen=fake_popen
    )
    assert calls == []

    assert offline_install.offer_gui_launch(
        tmp_path, input_fn=lambda _prompt: "yes", popen=fake_popen
    )
    assert len(calls) == 1
    assert calls[0][0][-1] == str(launcher)


def test_existing_public_gui_launcher_remains_the_offline_target():
    installer_text = (ROOT / "tools" / "offline_install.py").read_text(
        encoding="utf-8"
    )
    launcher_text = (ROOT / "launchers" / "run_gui_venv.cmd").read_text(
        encoding="utf-8"
    )

    assert '"launchers" / "run_gui_venv.cmd"' in installer_text
    assert ".venv\\Scripts\\python.exe" in launcher_text
    assert "-m dicomxphits.gui" in launcher_text


def test_project_declares_pep660_backend_for_read_only_editable_source():
    project_text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")

    assert '[build-system]' in project_text
    assert 'requires = ["setuptools", "wheel"]' in project_text
    assert 'build-backend = "setuptools.build_meta"' in project_text


@pytest.mark.skipif(sys.platform != "win32", reason="Windows offline editable path")
def test_pep660_editable_install_does_not_mutate_source_tree(tmp_path):
    if importlib.util.find_spec("setuptools") is None or importlib.util.find_spec(
        "wheel"
    ) is None:
        pytest.skip("requires the offline editable build tools")

    source = tmp_path / "protected-source-copy"
    (source / "src").mkdir(parents=True)
    for name in ("pyproject.toml", "README.md", "LICENSE"):
        shutil.copyfile(ROOT / name, source / name)
    shutil.copytree(ROOT / "src" / "dicomxphits", source / "src" / "dicomxphits")

    def source_inventory() -> dict[str, str]:
        return {
            path.relative_to(source).as_posix(): _sha256(path)
            for path in source.rglob("*")
            if path.is_file()
        }

    before = source_inventory()
    venv = tmp_path / "pep660-venv"
    creation = subprocess.run(
        [sys.executable, "-I", "-m", "venv", "--system-site-packages", str(venv)],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    assert creation.returncode == 0, creation.stdout + creation.stderr
    venv_python = venv / "Scripts" / "python.exe"
    result = subprocess.run(
        [
            str(venv_python),
            "-I",
            "-m",
            "pip",
            "install",
            "--no-index",
            "--no-build-isolation",
            "--no-deps",
            "--editable",
            str(source),
        ],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert source_inventory() == before
    assert not list(source.rglob("*.egg-info"))
    probe = subprocess.run(
        [
            str(venv_python),
            "-I",
            "-c",
            "import dicomxphits,importlib.metadata;"
            "assert importlib.metadata.version('dicomxphits') == '1.0.1'",
        ],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    assert probe.returncode == 0, probe.stdout + probe.stderr


def test_cmd_bootstrap_verifies_before_authenticated_runtime_stage():
    text = (ROOT / "install_offline.cmd").read_text(encoding="utf-8")
    stage = (ROOT / "tools" / "install_offline_verified.ps1").read_text(
        encoding="utf-8"
    )

    checksum_position = text.index("Get-Sha256")
    verified_stage_position = text.index("install_offline_verified.ps1')")
    module_path_position = text.index(
        "$env:PSModulePath=[IO.Path]::Combine($PSHOME,'Modules')"
    )
    error_preference_position = text.index("$ErrorActionPreference='Stop'")
    assert module_path_position < error_preference_position < checksum_position
    assert checksum_position < verified_stage_position
    assert "tools/lock_bundle_directories.ps1" in text
    assert "Lock-BundleDirectoryPaths" in text
    assert text.index("Lock-BundleDirectoryPaths") < verified_stage_position
    assert "Bundle payload path changed before elevation" in text
    assert "python.3.12.10.nupkg" in stage
    assert "tcltk.msi" in stage
    assert "python\\verifier\\nuget.exe" in stage
    assert "Security.Cryptography.SHA256" in text
    assert "Get-FileHash" not in text
    assert "[IO.FileShare]::Read" in text
    assert "DICOMXPHITS_VERIFIED_STAGE" in text
    assert 'set "__APPDIR__="' in text
    assert (
        'set "TrustedPowerShell=%__APPDIR__%WindowsPowerShell\\v1.0\\powershell.exe"'
        in text
    )
    assert "%SystemRoot%\\System32\\WindowsPowerShell" not in text
    assert '"%TrustedPowerShell%" -NoLogo' in text
    powershell_start = text.index('\n"%TrustedPowerShell%" -NoLogo')
    for variable in (
        "COR_ENABLE_PROFILING",
        "COR_PROFILER",
        "COR_PROFILER_PATH",
        "CORECLR_ENABLE_PROFILING",
        "CORECLR_PROFILER",
        "CORECLR_PROFILER_PATH",
        "APPDOMAIN_MANAGER_ASM",
        "APPDOMAIN_MANAGER_TYPE",
        "DOTNET_STARTUP_HOOKS",
    ):
        clear_line = f'set "{variable}="'
        assert clear_line in text
        assert text.index(clear_line) < powershell_start

    lock_helper = (ROOT / "tools" / "lock_bundle_directories.ps1").read_text(
        encoding="utf-8"
    )
    assert "$DirectoryPath,\n        0x10080," in lock_helper
    assert "if ($ErrorCode -eq 5)" not in lock_helper
    assert "if ($null -eq $Handle) { continue }" not in lock_helper
    assert text.count(
        "[IO.FileShare]::Read -bor [IO.FileShare]::Delete"
    ) == 2


@pytest.mark.skipif(sys.platform != "win32", reason="Windows directory handles")
def test_bundle_directory_locks_block_rename(tmp_path):
    root = tmp_path / "bundle"
    tools = root / "tools"
    tools.mkdir(parents=True)
    payload = tools / "install_offline_verified.ps1"
    payload.write_text("# verified stage\n", encoding="utf-8")
    harness = tmp_path / "bundle-directory-lock-harness.ps1"
    harness.write_text(
        "$ErrorActionPreference = 'Stop'\n"
        + ". "
        + repr(str(ROOT / "tools" / "lock_bundle_directories.ps1"))
        + "\n$Root = [IO.Path]::GetFullPath($env:DICOMXPHITS_TEST_BUNDLE_ROOT)\n"
        "$Tools = [IO.Path]::Combine($Root, 'tools')\n"
        "$Moved = [IO.Path]::Combine($Root, 'tools-moved')\n"
        "$Payload = [IO.Path]::Combine($Tools, 'install_offline_verified.ps1')\n"
        "$Handles = @(Lock-BundleDirectoryPaths $Root @($Payload))\n"
        "try {\n"
        "  if ($Handles.Count -ne 1) { exit 7 }\n"
        "  $Blocked = $false\n"
        "  try { [IO.Directory]::Move($Tools, $Moved) } catch { $Blocked = $true }\n"
        "  if (-not $Blocked -or -not [IO.Directory]::Exists($Tools) -or "
        "[IO.Directory]::Exists($Moved)) { exit 8 }\n"
        "  Write-Output 'DIRECTORY_RENAME_DENIED'\n"
        "  exit 0\n"
        "}\n"
        "finally { foreach ($Handle in $Handles) { $Handle.Dispose() } }\n",
        encoding="utf-8",
    )
    trusted_powershell = (
        Path(os.environ["SystemRoot"])
        / "System32"
        / "WindowsPowerShell"
        / "v1.0"
        / "powershell.exe"
    )
    result = subprocess.run(
        [
            str(trusted_powershell),
            "-NoLogo",
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(harness),
        ],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env={
            **os.environ,
            "DICOMXPHITS_TEST_BUNDLE_ROOT": str(root),
            "PSModulePath": str(trusted_powershell.parent / "Modules"),
        },
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "DIRECTORY_RENAME_DENIED" in result.stdout.splitlines()


@pytest.mark.skipif(sys.platform != "win32", reason="Windows PowerShell behavior")
def test_verified_stage_resolves_the_running_system_powershell(tmp_path):
    stage_text = (ROOT / "tools" / "install_offline_verified.ps1").read_text(
        encoding="utf-8"
    )
    function_text, separator, _main = stage_text.partition(
        '\ntry {\n    Assert-NoReparsePath $BundleRoot "Bundle root"'
    )
    assert separator
    harness = tmp_path / "trusted-powershell-harness.ps1"
    harness.write_text(
        function_text
        + "\n$Trusted = Assert-TrustedPowerShellProcess\n"
        "Write-Output ('TRUSTED_POWERSHELL=' + $Trusted)\n",
        encoding="utf-8",
    )
    trusted_powershell = (
        Path(os.environ["SystemRoot"])
        / "System32"
        / "WindowsPowerShell"
        / "v1.0"
        / "powershell.exe"
    )
    result = subprocess.run(
        [
            str(trusted_powershell),
            "-NoLogo",
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(harness),
        ],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env={
            **os.environ,
            "DICOMXPHITS_VERIFIED_STAGE": "synthetic-test-stage",
            "DICOMXPHITS_BUNDLE_ROOT": str(tmp_path),
            "PSModulePath": str(trusted_powershell.parent / "Modules"),
        },
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert f"TRUSTED_POWERSHELL={trusted_powershell}".casefold() in {
        line.casefold() for line in result.stdout.splitlines()
    }


@pytest.mark.skipif(sys.platform != "win32", reason="Windows directory handles")
def test_bundle_directory_lock_follows_shared_delete_verification(tmp_path):
    root = tmp_path / "bundle"
    tools = root / "tools"
    tools.mkdir(parents=True)
    payload = tools / "payload.txt"
    payload.write_text("payload\n", encoding="utf-8")
    harness = tmp_path / "bundle-directory-bootstrap-order-harness.ps1"
    harness.write_text(
        "$ErrorActionPreference = 'Stop'\n"
        + ". "
        + repr(str(ROOT / "tools" / "lock_bundle_directories.ps1"))
        + "\n$Root = [IO.Path]::GetFullPath($env:DICOMXPHITS_TEST_BUNDLE_ROOT)\n"
        "$Tools = [IO.Path]::Combine($Root, 'tools')\n"
        "$Moved = [IO.Path]::Combine($Root, 'tools-moved')\n"
        "$Payload = [IO.Path]::Combine($Tools, 'payload.txt')\n"
        "$Initial = [IO.File]::Open(\n"
        "  $Payload,\n"
        "  [IO.FileMode]::Open,\n"
        "  [IO.FileAccess]::Read,\n"
        "  [IO.FileShare]::Read -bor [IO.FileShare]::Delete\n"
        ")\n"
        "$Handles = @()\n"
        "$Strict = $null\n"
        "try {\n"
        "  $Handles = @(Lock-BundleDirectoryPaths $Root @($Payload))\n"
        "  if ($Handles.Count -ne 1) { exit 11 }\n"
        "  $Strict = [IO.File]::Open(\n"
        "    $Payload,\n"
        "    [IO.FileMode]::Open,\n"
        "    [IO.FileAccess]::Read,\n"
        "    [IO.FileShare]::Read\n"
        "  )\n"
        "  $Blocked = $false\n"
        "  try { [IO.Directory]::Move($Tools, $Moved) } catch { $Blocked = $true }\n"
        "  if (-not $Blocked -or -not [IO.Directory]::Exists($Tools)) { exit 12 }\n"
        "  Write-Output 'SHARED_DELETE_VERIFY_THEN_STRICT_LOCK_SUCCEEDED'\n"
        "}\n"
        "finally {\n"
        "  if ($null -ne $Strict) { $Strict.Dispose() }\n"
        "  foreach ($Handle in $Handles) { $Handle.Dispose() }\n"
        "  $Initial.Dispose()\n"
        "}\n",
        encoding="utf-8",
    )
    trusted_powershell = (
        Path(os.environ["SystemRoot"])
        / "System32"
        / "WindowsPowerShell"
        / "v1.0"
        / "powershell.exe"
    )
    result = subprocess.run(
        [
            str(trusted_powershell),
            "-NoLogo",
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(harness),
        ],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env={
            **os.environ,
            "DICOMXPHITS_TEST_BUNDLE_ROOT": str(root),
            "PSModulePath": str(trusted_powershell.parent / "Modules"),
        },
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert (
        "SHARED_DELETE_VERIFY_THEN_STRICT_LOCK_SUCCEEDED"
        in result.stdout.splitlines()
    )


@pytest.mark.skipif(sys.platform != "win32", reason="Windows reparse handles")
def test_bundle_directory_lock_rejects_opened_junction(tmp_path):
    target = tmp_path / "target"
    target.mkdir()
    junction = tmp_path / "junction"
    harness = tmp_path / "bundle-junction-lock-harness.ps1"
    harness.write_text(
        "$ErrorActionPreference = 'Stop'\n"
        + ". "
        + repr(str(ROOT / "tools" / "lock_bundle_directories.ps1"))
        + "\n$Target = [IO.Path]::GetFullPath($env:DICOMXPHITS_TEST_TARGET)\n"
        "$Junction = [IO.Path]::GetFullPath($env:DICOMXPHITS_TEST_JUNCTION)\n"
        "New-Item -ItemType Junction -Path $Junction -Target $Target | Out-Null\n"
        "try {\n"
        "  $Handle = Open-LockedBundleDirectory $Junction\n"
        "  if ($null -ne $Handle) { $Handle.Dispose() }\n"
        "  exit 9\n"
        "}\n"
        "catch {\n"
        "  if ($_ -notmatch 'reparse point') { Write-Error $_; exit 10 }\n"
        "  Write-Output 'OPENED_JUNCTION_REJECTED'\n"
        "  exit 0\n"
        "}\n",
        encoding="utf-8",
    )
    trusted_powershell = (
        Path(os.environ["SystemRoot"])
        / "System32"
        / "WindowsPowerShell"
        / "v1.0"
        / "powershell.exe"
    )
    result = subprocess.run(
        [
            str(trusted_powershell),
            "-NoLogo",
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(harness),
        ],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env={
            **os.environ,
            "DICOMXPHITS_TEST_TARGET": str(target),
            "DICOMXPHITS_TEST_JUNCTION": str(junction),
            "PSModulePath": str(trusted_powershell.parent / "Modules"),
        },
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "OPENED_JUNCTION_REJECTED" in result.stdout.splitlines()


def test_verified_stage_uses_only_authenticated_application_local_python():
    text = (ROOT / "tools" / "install_offline_verified.ps1").read_text(encoding="utf-8")

    assert "LocalAppData" not in text
    assert "ProgramFiles" not in text
    assert "PythonCore\\3.12\\InstallPath" not in text
    assert "Get-PythonCandidates" not in text
    assert "Assert-IsolatedVerifierDirectory" in text
    assert "Invoke-NuGetPackageVerification" in text
    assert "NUGET_CERT_REVOCATION_MODE = \"offline\"" in text
    assert "-CertificateFingerprint $PythonNuGetSignerSha256" in text
    assert "Expand-VerifiedPythonPackage" in text
    assert "Invoke-TclTkAdministrativeExtraction" in text
    assert "Get-SafeRuntimeDestination" in text
    assert "MsiFileHash" in text
    assert "ExpectedRuntimeHashes" in text
    assert "Lock-AuthenticatedRuntimeTree $RuntimeRoot" in text
    assert "Get-AuthenticodeSignature" in text
    assert "Python Software Foundation" in text
    assert '"python312.dll"' in text
    assert '"vcruntime140.dll"' in text
    assert "Microsoft Windows Software Compatibility Publisher" in text
    assert "& $SelectedPython -I -S -B -c" in text
    assert "Copy-ProtectedBundleSnapshot" in text
    assert "$ProtectedHelper = Join-Path $ProtectedSourceRoot" in text
    assert "--bundle-root $ProtectedSourceRoot --install-root $BundleRoot" in text
    assert text.index("Copy-ProtectedBundleSnapshot") < text.index(
        "$Probe = & $SelectedPython"
    )
    assert text.index("Lock-AuthenticatedRuntimeTree $RuntimeRoot") < text.index(
        "$Probe = & $SelectedPython"
    )


@pytest.mark.skipif(sys.platform != "win32", reason="Windows PowerShell behavior")
def test_protected_source_snapshot_excludes_unmanifested_setup_py(tmp_path):
    root = tmp_path / "bundle"
    root.mkdir()
    manifest = _make_bundle(root)
    (root / "setup.py").write_text("raise SystemExit(99)\n", encoding="utf-8")
    protected = tmp_path / "protected-source"
    stage_text = (ROOT / "tools" / "install_offline_verified.ps1").read_text(
        encoding="utf-8"
    )
    function_text, separator, _main = stage_text.partition(
        '\ntry {\n    Assert-NoReparsePath $BundleRoot "Bundle root"'
    )
    assert separator
    harness = tmp_path / "protected-source-harness.ps1"
    harness.write_text(
        function_text
        + "\nfunction New-ProtectedRuntimeDirectory([string]$Path,[string]$Label) { "
        "[IO.Directory]::CreateDirectory($Path) | Out-Null }\n"
        "$script:ProtectedSourceRoot = "
        + repr(str(protected))
        + "\nCopy-ProtectedBundleSnapshot\n"
        "if ([IO.File]::Exists((Join-Path $ProtectedSourceRoot 'setup.py'))) { exit 8 }\n"
        f"if ($ExpectedRuntimeHashes.Count -ne {len(manifest['files']) + 2}) {{ exit 9 }}\n"
        "Write-Output 'PROTECTED_SOURCE_EXCLUDES_SETUP'\n",
        encoding="utf-8",
    )
    trusted_powershell = (
        Path(os.environ["SystemRoot"])
        / "System32"
        / "WindowsPowerShell"
        / "v1.0"
        / "powershell.exe"
    )
    result = subprocess.run(
        [
            str(trusted_powershell),
            "-NoLogo",
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(harness),
        ],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env={
            **os.environ,
            "DICOMXPHITS_VERIFIED_STAGE": "synthetic-test-stage",
            "DICOMXPHITS_BUNDLE_ROOT": str(root),
            "PSModulePath": str(trusted_powershell.parent / "Modules"),
        },
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "PROTECTED_SOURCE_EXCLUDES_SETUP" in result.stdout.splitlines()


def test_verified_stage_requires_protected_elevation_before_runtime_execution():
    text = (ROOT / "tools" / "install_offline_verified.ps1").read_text(encoding="utf-8")

    assert "-Verb RunAs" in text
    assert "DICOMXPHITS_INSTALLING_USER_SID" in text
    assert "DICOMXPHITS_ELEVATED_STAGE" in text
    assert "[Convert]::ToBase64String" in text
    assert '$ChildCommand = $ChildCommand.Replace' in text
    assert '$env:DICOMXPHITS_ELEVATED_ACTION = "construct-runtime"' not in text
    assert "$env:DICOMXPHITS_INSTALLING_USER_SID = $ParentIdentity.User.Value" not in text
    assert "CommonApplicationData" in text
    assert 'New-Object System.Security.Principal.SecurityIdentifier("S-1-3-4")' in text
    assert "SetAccessRuleProtection($true, $false)" in text
    assert "Assert-AuthenticatedRuntimeInventory $RootFull" in text
    assert "Invoke-ElevatedRuntimeConstruction\n    Import-ProtectedRuntimeReceipt" in text
    assert text.index("Invoke-ElevatedRuntimeConstruction\n    Import-ProtectedRuntimeReceipt") < text.index(
        "$Probe = & $SelectedPython"
    )
    assert text.index("Import-ProtectedRuntimeReceipt") < text.index(
        "$Probe = & $SelectedPython"
    )
    assert text.index("Lock-AuthenticatedRuntimeTree $RuntimeRoot") < text.index(
        "$Probe = & $SelectedPython"
    )


@pytest.mark.skipif(sys.platform != "win32", reason="Windows PowerShell behavior")
def test_denied_elevation_stops_before_runtime_construction(tmp_path):
    stage_text = (ROOT / "tools" / "install_offline_verified.ps1").read_text(
        encoding="utf-8"
    )
    function_text, separator, _main = stage_text.partition(
        '\ntry {\n    Assert-NoReparsePath $BundleRoot "Bundle root"'
    )
    assert separator
    harness = tmp_path / "denied-elevation-harness.ps1"
    harness.write_text(
        function_text
        + "\nfunction Assert-TrustedPowerShellProcess { "
        "return [Diagnostics.Process]::GetCurrentProcess().MainModule.FileName }\n"
        "function Test-IsAdministrator { return $false }\n"
        "function Start-Process { throw 'synthetic UAC denial' }\n"
        "try { Invoke-ElevatedRuntimeConstruction; exit 8 }\n"
        "catch {\n"
        "  if ($_.Exception.Message -ne "
        "'Administrator approval is required before runtime construction.') { exit 9 }\n"
        "  Write-Output 'ELEVATION_DENIED'\n"
        "  exit 0\n"
        "}\n",
        encoding="utf-8",
    )
    trusted_powershell = (
        Path(os.environ["SystemRoot"])
        / "System32"
        / "WindowsPowerShell"
        / "v1.0"
        / "powershell.exe"
    )
    environment = os.environ.copy()
    environment.update(
        {
            "DICOMXPHITS_VERIFIED_STAGE": "synthetic-test-stage",
            "DICOMXPHITS_BUNDLE_ROOT": str(tmp_path),
            "PSModulePath": str(trusted_powershell.parent / "Modules"),
        }
    )
    result = subprocess.run(
        [
            str(trusted_powershell),
            "-NoLogo",
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(harness),
        ],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=environment,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "ELEVATION_DENIED" in result.stdout.splitlines()


@pytest.mark.skipif(sys.platform != "win32", reason="Windows ACL behavior")
def test_protected_runtime_acl_suppresses_owner_write_dac(tmp_path):
    stage_text = (ROOT / "tools" / "install_offline_verified.ps1").read_text(
        encoding="utf-8"
    )
    function_text, separator, _main = stage_text.partition(
        '\ntry {\n    Assert-NoReparsePath $BundleRoot "Bundle root"'
    )
    assert separator
    harness = tmp_path / "acl-harness.ps1"
    harness.write_text(
        function_text
        + "\n$script:InstallingUserSid = "
        "[Security.Principal.WindowsIdentity]::GetCurrent().User\n"
        "$Security = Get-ProtectedRuntimeSecurity $true\n"
        "$Sddl = $Security.GetSecurityDescriptorSddlForm("
        "[Security.AccessControl.AccessControlSections]::Owner -bor "
        "[Security.AccessControl.AccessControlSections]::Access)\n"
        "Write-Output $Sddl\n"
        "if (Test-IsAdministrator) {\n"
        "  $AdminRules = @($Security.GetAccessRules($true,$false,"
        "[Security.Principal.SecurityIdentifier]) | Where-Object { "
        "$_.IdentityReference.Value -eq $AdministratorsSid.Value })\n"
        "  foreach ($AdminRule in $AdminRules) { "
        "$Security.RemoveAccessRuleSpecific($AdminRule) }\n"
        "  Write-Output 'ADMIN_RULE_REMOVED=True'\n"
        "} else { Write-Output 'ADMIN_RULE_REMOVED=False' }\n"
        "$Container = [IO.Path]::GetFullPath($env:DICOMXPHITS_TEST_ACL_CONTAINER)\n"
        "$Protected = [IO.Path]::Combine($Container, 'protected')\n"
        "[IO.Directory]::CreateDirectory($Container) | Out-Null\n"
        "$Inheritance = [Security.AccessControl.InheritanceFlags]::ContainerInherit -bor "
        "[Security.AccessControl.InheritanceFlags]::ObjectInherit\n"
        "$ParentSecurity = [IO.Directory]::GetAccessControl($Container)\n"
        "$ParentSecurity.SetAccessRule((New-Object "
        "Security.AccessControl.FileSystemAccessRule("
        "$InstallingUserSid,[Security.AccessControl.FileSystemRights]::FullControl,"
        "$Inheritance,[Security.AccessControl.PropagationFlags]::None,"
        "[Security.AccessControl.AccessControlType]::Allow)))\n"
        "[IO.Directory]::SetAccessControl($Container,$ParentSecurity)\n"
        "$Security.SetOwner($InstallingUserSid)\n"
        "[IO.Directory]::CreateDirectory($Protected,$Security) | Out-Null\n"
        "$Injected = [IO.Path]::Combine($Protected, 'python312._pth')\n"
        "try { [IO.File]::WriteAllText($Injected, 'sitecustomize.py'); "
        "Write-Output 'WRITE_SUCCEEDED' } "
        "catch [UnauthorizedAccessException] { Write-Output 'WRITE_DENIED' }\n"
        "Write-Output ('INJECTED_EXISTS=' + [IO.File]::Exists($Injected))\n"
        "[IO.Directory]::Delete($Protected)\n"
        "[IO.Directory]::Delete($Container)\n",
        encoding="utf-8",
    )
    trusted_powershell = (
        Path(os.environ["SystemRoot"])
        / "System32"
        / "WindowsPowerShell"
        / "v1.0"
        / "powershell.exe"
    )
    environment = os.environ.copy()
    environment.update(
        {
            "DICOMXPHITS_VERIFIED_STAGE": "synthetic-test-stage",
            "DICOMXPHITS_BUNDLE_ROOT": str(tmp_path),
            "DICOMXPHITS_TEST_ACL_CONTAINER": str(tmp_path / "acl-container"),
            "PSModulePath": str(trusted_powershell.parent / "Modules"),
        }
    )
    result = subprocess.run(
        [
            str(trusted_powershell),
            "-NoLogo",
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(harness),
        ],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=environment,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    output_lines = result.stdout.splitlines()
    sddl = output_lines[0]
    current_sid = subprocess.run(
        [
            str(trusted_powershell),
            "-NoLogo",
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            "[Security.Principal.WindowsIdentity]::GetCurrent().User.Value",
        ],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=environment,
    ).stdout.strip()
    assert sddl.startswith("O:BA")
    assert "(A;OICI;FA;;;SY)" in sddl
    assert "(A;OICI;FA;;;BA)" in sddl
    assert (
        f"(A;OICI;0x1200a9;;;{current_sid})" in sddl
        or "(A;OICI;0x1200a9;;;LA)" in sddl
    )
    assert "(A;OICI;0x1200a9;;;OW)" in sddl
    assert "WD" not in sddl
    assert "WRITE_DENIED" in output_lines
    assert "INJECTED_EXISTS=False" in output_lines
    assert not (tmp_path / "acl-container").exists()


@pytest.mark.skipif(sys.platform != "win32", reason="Windows Authenticode behavior")
def test_verified_stage_never_starts_host_python_with_malicious_standard_library(
    tmp_path,
):
    base_executable = Path(getattr(sys, "_base_executable", sys.executable)).resolve()
    local_app_data = tmp_path / "local-app-data"
    candidate_dir = local_app_data / "Programs" / "Python" / "Python312"
    candidate_dir.mkdir(parents=True)
    runtime_files = [
        base_executable,
        base_executable.parent / "python312.dll",
        base_executable.parent / "vcruntime140.dll",
    ]
    encodings = Path(sys.base_prefix) / "Lib" / "encodings"
    if not all(path.is_file() for path in runtime_files) or not encodings.is_dir():
        pytest.skip("requires an installed CPython 3.12 runtime layout")
    for source in runtime_files:
        shutil.copyfile(source, candidate_dir / source.name)
    shutil.copytree(encodings, candidate_dir / "Lib" / "encodings")
    (candidate_dir / "python312._pth").write_text("Lib\n.\n", encoding="utf-8")
    candidate_marker = tmp_path / "host-python-started.txt"
    init_path = candidate_dir / "Lib" / "encodings" / "__init__.py"
    init_path.write_text(
        f"import _io; _io.open({str(candidate_marker)!r}, 'wb').write(b'started')\n"
        + init_path.read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    candidate = candidate_dir / base_executable.name
    fixture_probe = subprocess.run(
        [str(candidate), "-I", "-S", "-B", "-c", "pass"],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    assert fixture_probe.returncode == 0, fixture_probe.stdout + fixture_probe.stderr
    assert candidate_marker.read_text(encoding="utf-8") == "started"
    candidate_marker.unlink()

    root = tmp_path / "bundle"
    root.mkdir()
    _manifest, helper_marker = _make_cmd_bootstrap_bundle(root)
    environment = os.environ.copy()
    environment.update(
        {
            "LocalAppData": str(local_app_data),
            "DICOMXPHITS_ELEVATED_ACTION": "construct-runtime",
            "PYTHONUTF8": "1",
        }
    )
    result = subprocess.run(
        ["cmd.exe", "/d", "/c", str(root / "install_offline.cmd")],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=environment,
    )

    assert result.returncode != 0
    assert "Initial SHA-256 verification passed." in result.stdout
    assert not candidate_marker.exists()
    assert not helper_marker.exists()


@pytest.mark.skipif(sys.platform != "win32", reason="Windows PowerShell behavior")
def test_verified_runtime_extractor_rejects_escaping_archive_path(tmp_path):
    import zipfile

    root = tmp_path / "bundle"
    package = root / "python" / "python.3.12.10.nupkg"
    package.parent.mkdir(parents=True)
    with zipfile.ZipFile(package, "w") as archive:
        archive.writestr("tools/../escaped.py", "malicious")
    stage_text = (ROOT / "tools" / "install_offline_verified.ps1").read_text(
        encoding="utf-8"
    )
    function_text, separator, _main = stage_text.partition(
        '\ntry {\n    Assert-NoReparsePath $BundleRoot "Bundle root"'
    )
    assert separator
    harness = tmp_path / "extract-harness.ps1"
    harness.write_text(
        function_text
        + "\ntry {\n"
        "    $Destination = New-BoundedWorkingDirectory 'test'\n"
        "    Expand-VerifiedPythonPackage $Destination\n"
        "    exit 8\n"
        "}\n"
        "catch { exit 0 }\n"
        "finally { foreach ($Stream in $LockedPythonFiles) { $Stream.Dispose() } }\n",
        encoding="utf-8",
    )
    trusted_powershell = (
        Path(os.environ["SystemRoot"])
        / "System32"
        / "WindowsPowerShell"
        / "v1.0"
        / "powershell.exe"
    )
    environment = os.environ.copy()
    environment.update(
        {
            "DICOMXPHITS_VERIFIED_STAGE": "synthetic-test-stage",
            "DICOMXPHITS_BUNDLE_ROOT": str(root),
            "PSModulePath": str(trusted_powershell.parent / "Modules"),
        }
    )
    result = subprocess.run(
        [
            str(trusted_powershell),
            "-NoLogo",
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(harness),
        ],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=environment,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert not (root / "escaped.py").exists()


@pytest.mark.skipif(sys.platform != "win32", reason="Windows file-lock behavior")
def test_runtime_substitution_is_rejected_before_lock(tmp_path):
    import zipfile

    root = tmp_path / "bundle"
    package = root / "python" / "python.3.12.10.nupkg"
    package.parent.mkdir(parents=True)
    with zipfile.ZipFile(package, "w") as archive:
        archive.writestr("tools/Lib/encodings/__init__.py", "trusted")
    runtime = root / ".python-runtime"
    target = runtime / "Lib" / "encodings" / "__init__.py"
    stage_text = (ROOT / "tools" / "install_offline_verified.ps1").read_text(
        encoding="utf-8"
    )
    function_text, separator, _main = stage_text.partition(
        '\ntry {\n    Assert-NoReparsePath $BundleRoot "Bundle root"'
    )
    assert separator
    harness = tmp_path / "lock-harness.ps1"
    harness.write_text(
        function_text
        + "\ntry {\n"
        "    [IO.Directory]::CreateDirectory($RuntimeRoot) | Out-Null\n"
        "    Expand-VerifiedPythonPackage $RuntimeRoot\n"
        "    [IO.File]::WriteAllText($env:DICOMXPHITS_TEST_LOCKED_FILE, 'changed')\n"
        "    try { Lock-AuthenticatedRuntimeTree $RuntimeRoot; exit 8 }\n"
        "    catch { exit 0 }\n"
        "}\n"
        "finally { foreach ($Stream in $LockedPythonFiles) { $Stream.Dispose() } }\n",
        encoding="utf-8",
    )
    trusted_powershell = (
        Path(os.environ["SystemRoot"])
        / "System32"
        / "WindowsPowerShell"
        / "v1.0"
        / "powershell.exe"
    )
    environment = os.environ.copy()
    environment.update(
        {
            "DICOMXPHITS_VERIFIED_STAGE": "synthetic-test-stage",
            "DICOMXPHITS_BUNDLE_ROOT": str(root),
            "DICOMXPHITS_TEST_LOCKED_FILE": str(target),
            "PSModulePath": str(trusted_powershell.parent / "Modules"),
        }
    )
    result = subprocess.run(
        [
            str(trusted_powershell),
            "-NoLogo",
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(harness),
        ],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=environment,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert target.read_text(encoding="utf-8") == "changed"


@pytest.mark.skipif(sys.platform != "win32", reason="Windows file-lock behavior")
def test_authenticated_runtime_tree_remains_read_locked(tmp_path):
    import zipfile

    root = tmp_path / "bundle"
    package = root / "python" / "python.3.12.10.nupkg"
    package.parent.mkdir(parents=True)
    with zipfile.ZipFile(package, "w") as archive:
        archive.writestr("tools/Lib/encodings/__init__.py", "trusted")
    runtime = root / ".python-runtime"
    target = runtime / "Lib" / "encodings" / "__init__.py"
    stage_text = (ROOT / "tools" / "install_offline_verified.ps1").read_text(
        encoding="utf-8"
    )
    function_text, separator, _main = stage_text.partition(
        '\ntry {\n    Assert-NoReparsePath $BundleRoot "Bundle root"'
    )
    assert separator
    harness = tmp_path / "locked-tree-harness.ps1"
    harness.write_text(
        function_text
        + "\ntry {\n"
        "    [IO.Directory]::CreateDirectory($RuntimeRoot) | Out-Null\n"
        "    Expand-VerifiedPythonPackage $RuntimeRoot\n"
        "    Lock-AuthenticatedRuntimeTree $RuntimeRoot\n"
        "    try {\n"
        "        [IO.File]::WriteAllText($env:DICOMXPHITS_TEST_LOCKED_FILE, 'changed')\n"
        "        exit 8\n"
        "    }\n"
        "    catch [IO.IOException] { exit 0 }\n"
        "}\n"
        "finally { foreach ($Stream in $LockedPythonFiles) { $Stream.Dispose() } }\n",
        encoding="utf-8",
    )
    trusted_powershell = (
        Path(os.environ["SystemRoot"])
        / "System32"
        / "WindowsPowerShell"
        / "v1.0"
        / "powershell.exe"
    )
    environment = os.environ.copy()
    environment.update(
        {
            "DICOMXPHITS_VERIFIED_STAGE": "synthetic-test-stage",
            "DICOMXPHITS_BUNDLE_ROOT": str(root),
            "DICOMXPHITS_TEST_LOCKED_FILE": str(target),
            "PSModulePath": str(trusted_powershell.parent / "Modules"),
        }
    )
    result = subprocess.run(
        [
            str(trusted_powershell),
            "-NoLogo",
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(harness),
        ],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=environment,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert target.read_text(encoding="utf-8") == "trusted"


@pytest.mark.skipif(sys.platform != "win32", reason="Windows PowerShell behavior")
def test_authenticated_runtime_inventory_rejects_injected_file(tmp_path):
    import zipfile

    root = tmp_path / "bundle"
    package = root / "python" / "python.3.12.10.nupkg"
    package.parent.mkdir(parents=True)
    with zipfile.ZipFile(package, "w") as archive:
        archive.writestr("tools/Lib/encodings/__init__.py", "trusted")
    runtime = root / ".python-runtime"
    injected = runtime / "Lib" / "evil.py"
    stage_text = (ROOT / "tools" / "install_offline_verified.ps1").read_text(
        encoding="utf-8"
    )
    function_text, separator, _main = stage_text.partition(
        '\ntry {\n    Assert-NoReparsePath $BundleRoot "Bundle root"'
    )
    assert separator
    harness = tmp_path / "inventory-harness.ps1"
    harness.write_text(
        function_text
        + "\ntry {\n"
        "    [IO.Directory]::CreateDirectory($RuntimeRoot) | Out-Null\n"
        "    Expand-VerifiedPythonPackage $RuntimeRoot\n"
        "    [IO.File]::WriteAllText($env:DICOMXPHITS_TEST_INJECTED_FILE, 'evil')\n"
        "    try { Lock-AuthenticatedRuntimeTree $RuntimeRoot; exit 8 }\n"
        "    catch { exit 0 }\n"
        "}\n"
        "finally { foreach ($Stream in $LockedPythonFiles) { $Stream.Dispose() } }\n",
        encoding="utf-8",
    )
    trusted_powershell = (
        Path(os.environ["SystemRoot"])
        / "System32"
        / "WindowsPowerShell"
        / "v1.0"
        / "powershell.exe"
    )
    environment = os.environ.copy()
    environment.update(
        {
            "DICOMXPHITS_VERIFIED_STAGE": "synthetic-test-stage",
            "DICOMXPHITS_BUNDLE_ROOT": str(root),
            "DICOMXPHITS_TEST_INJECTED_FILE": str(injected),
            "PSModulePath": str(trusted_powershell.parent / "Modules"),
        }
    )
    result = subprocess.run(
        [
            str(trusted_powershell),
            "-NoLogo",
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(harness),
        ],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=environment,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_installer_never_uses_bare_executable_discovery():
    bootstrap = (ROOT / "install_offline.cmd").read_text(encoding="utf-8")
    stage = (ROOT / "tools" / "install_offline_verified.ps1").read_text(encoding="utf-8")

    assert "powershell.exe -" not in bootstrap.lower()
    assert "`py.exe" not in bootstrap.lower()
    assert "`python.exe" not in bootstrap.lower()
    assert 'Get-Command "py.exe"' not in stage
    assert 'Get-Command "python.exe"' not in stage


@pytest.mark.skipif(sys.platform != "win32", reason="Windows cmd.exe behavior")
@pytest.mark.parametrize("fake_name", ["powershell.exe", "python.exe", "py.exe"])
def test_cmd_rejects_top_level_fake_executables_without_running_them(tmp_path, fake_name):
    root = tmp_path / "日本語 user" / "fake executable bundle"
    root.mkdir(parents=True)
    _make_cmd_bootstrap_bundle(root)
    (root / fake_name).write_text("This is intentionally not an executable.\n", encoding="utf-8")

    result = subprocess.run(
        ["cmd.exe", "/d", "/c", str(root / "install_offline.cmd")],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    assert result.returncode != 0
    assert "Unexpected executable or script at bundle root" in result.stderr
    assert not (root / "helper-executed.txt").exists()


@pytest.mark.skipif(sys.platform != "win32", reason="Windows cmd.exe behavior")
def test_cmd_ignores_mutable_system_directory_environment(tmp_path):
    text = (ROOT / "install_offline.cmd").read_text(encoding="utf-8")
    bootstrap_lines = [
        line
        for line in text.splitlines()
        if line.startswith('set "__APPDIR__=')
        or line.startswith('set "TrustedPowerShell=')
    ]
    assert len(bootstrap_lines) == 2

    root = tmp_path / "日本語 user" / "mutable environment probe"
    root.mkdir(parents=True)
    trusted_cmd = Path(os.environ["SystemRoot"]) / "System32" / "cmd.exe"
    expected_powershell = (
        trusted_cmd.parent / "WindowsPowerShell" / "v1.0" / "powershell.exe"
    )
    probe = root / "probe.cmd"
    probe.write_text(
        "@echo off\r\n"
        "setlocal EnableExtensions DisableDelayedExpansion\r\n"
        + "\r\n".join(bootstrap_lines)
        + "\r\n"
        + '"%PROBE_PYTHON%" -c "import sys;print(sys.argv[1])" '
        '"%TrustedPowerShell%"\r\n',
        encoding="utf-8",
    )
    environment = os.environ.copy()
    environment["SystemRoot"] = str(tmp_path / "fake-system")
    environment["__APPDIR__"] = str(tmp_path / "fake-app") + os.sep
    environment["PROBE_PYTHON"] = sys.executable
    environment["PYTHONUTF8"] = "1"

    result = subprocess.run(
        [str(trusted_cmd), "/d", "/c", str(probe)],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=environment,
    )

    assert result.returncode == 0, result.stderr
    assert Path(result.stdout.strip()) == expected_powershell


@pytest.mark.skipif(sys.platform != "win32", reason="Windows PowerShell module loading")
def test_cmd_pins_powershell_modules_before_authenticode_lookup(tmp_path):
    root = tmp_path / "日本語 user" / "module path bootstrap"
    root.mkdir(parents=True)
    _manifest, helper_marker = _make_cmd_bootstrap_bundle(root)

    base_executable = Path(getattr(sys, "_base_executable", sys.executable)).resolve()
    base_directory = base_executable.parent
    runtime_files = [
        base_executable,
        base_directory / "python312.dll",
        base_directory / "vcruntime140.dll",
    ]
    if not all(path.is_file() for path in runtime_files):
        pytest.skip("requires an installed CPython 3.12 runtime layout")
    local_app_data = tmp_path / "local-app-data"
    candidate_directory = local_app_data / "Programs" / "Python" / "Python312"
    candidate_directory.mkdir(parents=True)
    for source in runtime_files:
        target_name = "python.exe" if source == base_executable else source.name
        shutil.copyfile(source, candidate_directory / target_name)

    malicious_modules = tmp_path / "malicious-modules"
    security_module = malicious_modules / "Microsoft.PowerShell.Security"
    security_module.mkdir(parents=True)
    module_marker = tmp_path / "malicious-module-loaded.txt"
    (security_module / "Microsoft.PowerShell.Security.psd1").write_text(
        "@{\n"
        "RootModule = 'Microsoft.PowerShell.Security.psm1'\n"
        "ModuleVersion = '1.0.0'\n"
        "GUID = 'b72b1f20-9f0b-4dc8-a15c-718e52f23bdb'\n"
        "FunctionsToExport = @('Get-AuthenticodeSignature')\n"
        "}\n",
        encoding="utf-8",
    )
    (security_module / "Microsoft.PowerShell.Security.psm1").write_text(
        "function Get-AuthenticodeSignature {\n"
        "    param([string]$LiteralPath)\n"
        "    Add-Content -LiteralPath $env:DICOMXPHITS_TEST_PSMODULE_MARKER -Value $LiteralPath\n"
        "    $subject = if ([IO.Path]::GetFileName($LiteralPath) -ieq 'vcruntime140.dll') {\n"
        "        'CN=Microsoft Windows Software Compatibility Publisher, O=Microsoft Corporation, L=Redmond, S=Washington, C=US'\n"
        "    } else {\n"
        "        'CN=Python Software Foundation, O=Python Software Foundation, L=Beaverton, S=Oregon, C=US'\n"
        "    }\n"
        "    [pscustomobject]@{\n"
        "        Status = [System.Management.Automation.SignatureStatus]::Valid\n"
        "        SignerCertificate = [pscustomobject]@{ Subject = $subject }\n"
        "    }\n"
        "}\n"
        "Export-ModuleMember -Function Get-AuthenticodeSignature\n",
        encoding="utf-8",
    )
    system_modules = (
        Path(os.environ["SystemRoot"])
        / "System32"
        / "WindowsPowerShell"
        / "v1.0"
        / "Modules"
    )
    environment = os.environ.copy()
    environment.update(
        {
            "LocalAppData": str(local_app_data),
            "DICOMXPHITS_ELEVATED_ACTION": "construct-runtime",
            "PSModulePath": os.pathsep.join(
                [str(malicious_modules), str(system_modules)]
            ),
            "DICOMXPHITS_TEST_PSMODULE_MARKER": str(module_marker),
            "PYTHONUTF8": "1",
        }
    )

    result = subprocess.run(
        ["cmd.exe", "/d", "/c", str(root / "install_offline.cmd")],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=environment,
    )

    assert result.returncode != 0
    assert not module_marker.exists()
    assert not helper_marker.exists()


@pytest.mark.skipif(sys.platform != "win32", reason="Windows cmd.exe behavior")
def test_cmd_passes_bundle_root_without_a_trailing_quote_in_unicode_space_path(
    tmp_path,
):
    text = (ROOT / "install_offline.cmd").read_text(encoding="utf-8")
    root_line = next(
        line
        for line in text.splitlines()
        if line.startswith('for %%I in ("%~dp0.") do set "BundleRoot=')
    )
    root = tmp_path / "日本語 user" / "offline bundle"
    root.mkdir(parents=True)
    probe = root / "probe.cmd"
    probe.write_text(
        "@echo off\r\n"
        "setlocal EnableExtensions DisableDelayedExpansion\r\n"
        f"{root_line}\r\n"
        '"%PROBE_PYTHON%" -c "import sys;print(sys.argv[1])" "%BundleRoot%"\r\n',
        encoding="utf-8",
    )
    environment = os.environ.copy()
    environment["PROBE_PYTHON"] = sys.executable
    environment["PYTHONUTF8"] = "1"

    result = subprocess.run(
        ["cmd.exe", "/d", "/c", str(probe)],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=environment,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == str(root.resolve())
