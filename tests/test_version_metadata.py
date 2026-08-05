from __future__ import annotations

import tomllib
from pathlib import Path

import dicomxphits


ROOT = Path(__file__).resolve().parents[1]
TARGET_VERSION = "1.0.1"


def test_release_version_metadata_is_consistent() -> None:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))

    assert project["project"]["version"] == TARGET_VERSION
    assert dicomxphits.__version__ == TARGET_VERSION
    assert f"Version {TARGET_VERSION}" in (ROOT / "README.md").read_text(
        encoding="utf-8-sig"
    )
    assert (ROOT / "docs" / "release-notes-v1.0.1.md").is_file()
