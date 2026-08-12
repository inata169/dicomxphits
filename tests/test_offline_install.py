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


def _make_bundle(root: Path) -> dict:
    payloads = {
        "install_offline.cmd": b"@echo off\r\n",
        "tools/offline_install.py": b"# synthetic helper\n",
        "tools/install_offline_verified.ps1": b"# synthetic verified stage\n",
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
        "tools/install_offline_verified.ps1": (
            ROOT / "tools" / "install_offline_verified.ps1"
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
        match="Wheelhouse contents differ from the verified manifest",
    ):
        offline_install.verify_bundle(tmp_path)


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
def test_cmd_accepts_complete_manifest_consistent_inventory(tmp_path):
    root = tmp_path / "日本語 user" / "valid offline bootstrap"
    root.mkdir(parents=True)
    manifest, marker = _make_cmd_bootstrap_bundle(root)
    stage = root / "tools" / "install_offline_verified.ps1"
    stage.write_text(
        "$ErrorActionPreference = 'Stop'\n"
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

    assert result.returncode == 0, result.stdout + result.stderr
    assert "Initial SHA-256 verification passed." in result.stdout
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
    root = tmp_path / "日本語 user" / "offline bundle"
    root.mkdir(parents=True)
    _make_bundle(root)
    venv_python = root / ".venv" / "Scripts" / "python.exe"
    venv_python.parent.mkdir(parents=True)
    venv_python.write_bytes(b"synthetic Python")
    runner = FakeRunner()

    selected, versions = offline_install.install_bundle(root, runner=runner)

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
        assert str(root / "wheelhouse") in command
        assert "--no-build-isolation" in command
        if index == 0:
            assert "--force-reinstall" in command
            assert "--require-hashes" in command
            assert "--requirement" in command
            assert str(root / "requirements" / "offline-win64.txt") in command
        else:
            assert "--no-deps" in command
        assert kwargs["env"]["PIP_NO_INDEX"] == "1"
        assert kwargs["env"]["PIP_FIND_LINKS"] == str(root / "wheelhouse")
        assert not any(value.startswith(("http://", "https://")) for value in command)
    assert str(root) in pip_calls[-1][0]
    assert (root / "offline-install.log").is_file()


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
    assert "& $SelectedPython -I -S -B $Helper" in text
    assert text.index("Lock-AuthenticatedRuntimeTree $RuntimeRoot") < text.index(
        "$Probe = & $SelectedPython"
    )


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
    assert f"(A;OICI;0x1200a9;;;{current_sid})" in sddl
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
