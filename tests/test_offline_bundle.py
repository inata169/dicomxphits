from __future__ import annotations

import importlib.util
from pathlib import Path
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "offline_bundle", ROOT / "tools" / "offline_bundle.py"
)
assert SPEC is not None and SPEC.loader is not None
offline_bundle = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = offline_bundle
SPEC.loader.exec_module(offline_bundle)


def _write_wheels(wheelhouse: Path, *, numpy_platform: str = "win_amd64") -> None:
    wheelhouse.mkdir()
    names = (
        f"numpy-2.3.0-cp312-cp312-{numpy_platform}.whl",
        "pydicom-3.0.1-py3-none-any.whl",
        "setuptools-80.0.0-py3-none-any.whl",
        "wheel-0.45.1-py3-none-any.whl",
    )
    for name in names:
        (wheelhouse / name).write_bytes(("synthetic:" + name).encode("ascii"))


def test_correct_cp312_windows_wheels_are_recognized(tmp_path):
    wheelhouse = tmp_path / "wheelhouse"
    _write_wheels(wheelhouse)

    wheels = offline_bundle.validate_wheelhouse(wheelhouse, ["numpy", "pydicom"])

    assert {wheel["distribution"] for wheel in wheels} == {
        "numpy",
        "pydicom",
        "setuptools",
        "wheel",
    }
    numpy = next(wheel for wheel in wheels if wheel["distribution"] == "numpy")
    assert numpy["python_tags"] == ["cp312"]
    assert numpy["abi_tags"] == ["cp312"]
    assert numpy["platform_tags"] == ["win_amd64"]


def test_numpy_platform_mismatch_is_rejected(tmp_path):
    wheelhouse = tmp_path / "wheelhouse"
    _write_wheels(wheelhouse, numpy_platform="win32")

    with pytest.raises(
        offline_bundle.OfflineBundleError,
        match="cp312-cp312-win_amd64",
    ):
        offline_bundle.validate_wheelhouse(wheelhouse, ["numpy", "pydicom"])


def test_missing_required_wheel_is_rejected(tmp_path):
    wheelhouse = tmp_path / "wheelhouse"
    _write_wheels(wheelhouse)
    (wheelhouse / "pydicom-3.0.1-py3-none-any.whl").unlink()

    with pytest.raises(offline_bundle.OfflineBundleError, match="pydicom"):
        offline_bundle.validate_wheelhouse(wheelhouse, ["numpy", "pydicom"])


def test_source_archive_in_wheelhouse_is_rejected(tmp_path):
    wheelhouse = tmp_path / "wheelhouse"
    _write_wheels(wheelhouse)
    (wheelhouse / "numpy-2.3.0.tar.gz").write_bytes(b"synthetic source archive")

    with pytest.raises(offline_bundle.OfflineBundleError, match="non-wheel"):
        offline_bundle.validate_wheelhouse(wheelhouse, ["numpy", "pydicom"])


def test_project_runtime_dependencies_are_read_from_pyproject(tmp_path):
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        """
[project]
name = "dicomxphits"
version = "1.2.3"
requires-python = ">=3.12,<3.13"
dependencies = ["numpy>=2", "pydicom"]
""".strip()
        + "\n",
        encoding="utf-8",
    )

    metadata = offline_bundle.load_project_metadata(pyproject)

    assert metadata["version"] == "1.2.3"
    assert metadata["dependencies"] == ["numpy>=2", "pydicom"]
    assert metadata["dependency_names"] == ["numpy", "pydicom"]


def test_source_copy_uses_only_git_indexed_regular_files(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    staging = tmp_path / "staging"
    repo.mkdir()
    staging.mkdir()
    for relative in offline_bundle.REQUIRED_BUNDLE_SOURCE_PATHS:
        path = repo / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"tracked {relative}\n", encoding="utf-8")
    tracked = repo / "README.md"
    tracked.write_text("tracked\n", encoding="utf-8")
    untracked = repo / "private-local.txt"
    untracked.write_text("must not copy\n", encoding="utf-8")
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(
        ["git", "add", *offline_bundle.REQUIRED_BUNDLE_SOURCE_PATHS, "README.md"],
        cwd=repo,
        check=True,
    )
    tracked.write_text("unstaged replacement must not copy\n", encoding="utf-8")
    monkeypatch.setattr(
        offline_bundle, "_run_public_tree_audit", lambda _repo, _snapshot: None
    )

    copied = offline_bundle.copy_indexed_public_source(repo, staging)

    assert "README.md" in copied
    assert (staging / "README.md").read_text(encoding="utf-8") == "tracked\n"
    assert not (staging / "private-local.txt").exists()


def test_indexed_metadata_ignores_unstaged_pyproject_change(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    pyproject = repo / "pyproject.toml"
    pyproject.write_text(
        """
[project]
name = "dicomxphits"
version = "1.0.1"
requires-python = ">=3.12,<3.13"
dependencies = ["numpy", "pydicom"]
""".strip()
        + "\n",
        encoding="utf-8",
    )
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "add", "pyproject.toml"], cwd=repo, check=True)
    pyproject.write_text("unstaged invalid metadata\n", encoding="utf-8")

    metadata = offline_bundle.load_indexed_project_metadata(repo)

    assert metadata["version"] == "1.0.1"
    assert metadata["dependencies"] == ["numpy", "pydicom"]


def test_git_index_fingerprint_changes_with_staged_content(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    source = repo / "source.txt"
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    source.write_text("first\n", encoding="utf-8")
    subprocess.run(["git", "add", "source.txt"], cwd=repo, check=True)
    first = offline_bundle._git_index_fingerprint(repo)
    source.write_text("second\n", encoding="utf-8")

    assert offline_bundle._git_index_fingerprint(repo) == first

    subprocess.run(["git", "add", "source.txt"], cwd=repo, check=True)
    assert offline_bundle._git_index_fingerprint(repo) != first


def test_snapshot_copy_and_fingerprint_ignore_concurrent_index_change(
    tmp_path, monkeypatch
):
    repo = tmp_path / "repo"
    staging = tmp_path / "staging"
    repo.mkdir()
    staging.mkdir()
    for relative in offline_bundle.REQUIRED_BUNDLE_SOURCE_PATHS:
        path = repo / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"snapshot {relative}\n", encoding="utf-8")
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    snapshot = offline_bundle._capture_git_index(repo)
    original_read = offline_bundle._read_indexed_blob
    changed = False

    def read_while_index_changes(repo_root, object_id, relative="indexed source"):
        nonlocal changed
        if not changed:
            changed = True
            source = repo / "install_offline.cmd"
            source.write_text("concurrent staged replacement\n", encoding="utf-8")
            subprocess.run(["git", "add", "install_offline.cmd"], cwd=repo, check=True)
        return original_read(repo_root, object_id, relative)

    monkeypatch.setattr(offline_bundle, "_read_indexed_blob", read_while_index_changes)
    monkeypatch.setattr(
        offline_bundle, "_run_public_tree_audit", lambda _repo, _snapshot: None
    )

    copied = offline_bundle.copy_indexed_public_source(
        repo, staging, snapshot=snapshot
    )

    assert "install_offline.cmd" in copied
    assert (staging / "install_offline.cmd").read_text(encoding="utf-8") == (
        "snapshot install_offline.cmd\n"
    )
    assert snapshot.fingerprint != offline_bundle._git_index_fingerprint(repo)


def test_prepare_script_has_fixed_binary_target_and_no_offline_fallback():
    text = (ROOT / "tools" / "prepare_offline_bundle.ps1").read_text(
        encoding="utf-8"
    )

    assert "https://www.python.org/ftp/python/$PythonVersion/" in text
    assert '"--only-binary=:all:"' in text
    assert '"--platform"' in text and '"win_amd64"' in text
    assert '"--python-version"' in text and '"3.12"' in text
    assert '"--implementation"' in text and '"cp"' in text
    assert '"--abi"' in text and '"cp312"' in text
    assert "Get-AuthenticodeSignature" in text
    assert "Python Software Foundation" in text
