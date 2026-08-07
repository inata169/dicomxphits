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
        "launchers/run_gui_venv.cmd": b"@echo off\r\n",
        "pyproject.toml": b"[project]\nname='dicomxphits'\n",
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
    helper = root / "tools" / "offline_install.py"
    helper.write_text(
        "import sys\n"
        "from pathlib import Path\n"
        "if '--probe' in sys.argv:\n"
        "    print(sys.executable)\n"
        "    raise SystemExit(0)\n"
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
    assert len(pip_calls) == 3
    for command, kwargs in pip_calls:
        assert "--no-index" in command
        assert "--find-links" in command
        assert str(root / "wheelhouse") in command
        assert "--no-build-isolation" in command
        assert kwargs["env"]["PIP_NO_INDEX"] == "1"
        assert kwargs["env"]["PIP_FIND_LINKS"] == str(root / "wheelhouse")
        assert not any(value.startswith(("http://", "https://")) for value in command)
    assert str(root) in pip_calls[-1][0]
    assert (root / "offline-install.log").is_file()


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

    checksum_position = text.index("Get-Sha256")
    installer_position = text.index('"%Installer%" /quiet')
    assert checksum_position < installer_position
    assert "InstallAllUsers=0" in text
    assert "Include_pip=1" in text
    assert "Include_launcher=1" in text
    assert "InstallLauncherAllUsers=0" in text
    assert "Include_tcltk=1" in text
    assert "AssociateFiles=0" in text
    assert "Security.Cryptography.SHA256" in text
    assert "Get-FileHash" not in text


def test_cmd_validates_the_new_current_user_python_without_for_f_capture():
    text = (ROOT / "install_offline.cmd").read_text(encoding="utf-8")

    expected_probe = (
        '"%LocalAppData%\\Programs\\Python\\Python312\\python.exe" '
        '"%Helper%" --probe >nul 2>&1'
    )
    assert expected_probe in text
    assert (
        'set "SelectedPython=%LocalAppData%\\Programs\\Python\\Python312\\python.exe"'
        in text
    )


def test_cmd_rejects_python_launcher_not_found_text_as_an_executable():
    text = (ROOT / "install_offline.cmd").read_text(encoding="utf-8")

    py_probe = (
        'for /f "usebackq delims=" %%P in (`py.exe -3.12 "%Helper%" '
        '--probe 2^>nul`) do if not defined SelectedPython if exist "%%P" '
        'set "SelectedPython=%%P"'
    )
    path_probe = (
        'for /f "usebackq delims=" %%P in (`python.exe "%Helper%" '
        '--probe 2^>nul`) do if not defined SelectedPython if exist "%%P" '
        'set "SelectedPython=%%P"'
    )
    assert py_probe in text
    assert path_probe in text
    assert 'Using Python: "Python 3.12 not found!"' not in text


@pytest.mark.skipif(sys.platform != "win32", reason="Windows cmd.exe behavior")
def test_cmd_for_f_guard_ignores_launcher_not_found_stdout(tmp_path):
    text = (ROOT / "install_offline.cmd").read_text(encoding="utf-8")
    py_probe = next(
        line
        for line in text.splitlines()
        if line.startswith('for /f "usebackq delims=" %%P in (`py.exe -3.12')
    )
    guarded_probe = py_probe.replace(
        'in (`py.exe -3.12 "%Helper%" --probe 2^>nul`)',
        'in (`echo Python 3.12 not found!`)',
    )
    probe = tmp_path / "launcher-not-found-probe.cmd"
    probe.write_text(
        "@echo off\r\n"
        "setlocal EnableExtensions DisableDelayedExpansion\r\n"
        "set \"SelectedPython=\"\r\n"
        f"{guarded_probe}\r\n"
        "if defined SelectedPython exit /b 1\r\n"
        "exit /b 0\r\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        ["cmd.exe", "/d", "/c", str(probe)],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )

    assert result.returncode == 0, result.stdout + result.stderr


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
