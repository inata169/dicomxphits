from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from pathlib import Path
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
        "python/python-3.12.10-amd64.exe": b"synthetic installer",
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


def _windows_has_bounded_python312_candidate() -> bool:
    if sys.platform != "win32":
        return False
    candidates: list[Path] = []
    allowed_roots: list[Path] = []
    local_app_data = os.environ.get("LocalAppData")
    if local_app_data:
        python_root = Path(local_app_data) / "Programs" / "Python"
        allowed_roots.append(python_root)
        candidates.append(python_root / "Python312" / "python.exe")
    for variable in ("ProgramFiles", "ProgramFiles(x86)"):
        value = os.environ.get(variable)
        if value:
            allowed_roots.append(Path(value))
    import winreg

    for hive, key in (
        (winreg.HKEY_CURRENT_USER, r"Software\Python\PythonCore\3.12\InstallPath"),
        (winreg.HKEY_LOCAL_MACHINE, r"Software\Python\PythonCore\3.12\InstallPath"),
        (winreg.HKEY_LOCAL_MACHINE, r"Software\WOW6432Node\Python\PythonCore\3.12\InstallPath"),
    ):
        try:
            with winreg.OpenKey(hive, key) as handle:
                value, _kind = winreg.QueryValueEx(handle, None)
        except OSError:
            continue
        candidates.append(Path(value) / "python.exe")
    return any(
        path.is_file()
        and any(
            path.resolve().is_relative_to(root.resolve()) for root in allowed_roots
        )
        for path in candidates
    )


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
    if not _windows_has_bounded_python312_candidate():
        pytest.skip("requires a canonical installed CPython 3.12 candidate")
    root = tmp_path / "日本語 user" / "valid offline bootstrap"
    root.mkdir(parents=True)
    manifest, marker = _make_cmd_bootstrap_bundle(root)
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
    assert command[1:4] == ["-I", "-m", "venv"]
    assert kwargs["cwd"] == tmp_path.resolve()


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


def test_cmd_bootstrap_verifies_before_python_and_enables_required_features():
    text = (ROOT / "install_offline.cmd").read_text(encoding="utf-8")
    stage = (ROOT / "tools" / "install_offline_verified.ps1").read_text(
        encoding="utf-8"
    )

    checksum_position = text.index("Get-Sha256")
    verified_stage_position = text.index("install_offline_verified.ps1')")
    assert checksum_position < verified_stage_position
    assert "InstallAllUsers=0" in stage
    assert "Include_pip=1" in stage
    assert "Include_launcher=1" in stage
    assert "InstallLauncherAllUsers=0" in stage
    assert "Include_tcltk=1" in stage
    assert "AssociateFiles=0" in stage
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


def test_verified_stage_uses_only_absolute_bounded_python_candidates():
    text = (ROOT / "tools" / "install_offline_verified.ps1").read_text(encoding="utf-8")

    assert 'Programs\\Python\\Python312\\python.exe' in text
    assert "PythonCore\\3.12\\InstallPath" in text
    assert "Test-UnderAllowedPythonRoot" in text
    assert "Get-AuthenticodeSignature" in text
    assert "Python Software Foundation" in text
    assert "& $Candidate -I -c" in text
    assert "& $SelectedPython -I $Helper" in text


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
