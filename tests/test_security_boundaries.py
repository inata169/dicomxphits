from __future__ import annotations

import csv
import os
from pathlib import Path
import subprocess
import sys

import pytest

from dicomxphits.csv_security import neutralize_external_csv_value
from dicomxphits.rtplan_segments import write_csv
from dicomxphits.safe_output import UnsafeWorkspacePathError, WorkspaceOutputGuard


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("Beam A", "Beam A"),
        ("日本語ビーム", "日本語ビーム"),
        ("", ""),
        ("=1+1", "'=1+1"),
        ("+SUM(A1:A2)", "'+SUM(A1:A2)"),
        ("-2+3", "'-2+3"),
        ("@SUM(A1:A2)", "'@SUM(A1:A2)"),
        ("\t=1+1", "'\t=1+1"),
        ("\r=1+1", "'\r=1+1"),
        ("\n=1+1", "'\n=1+1"),
        ("\x00=1+1", "'\x00=1+1"),
        ("\x85=1+1", "'\x85=1+1"),
        ('Beam, "quoted"', 'Beam, "quoted"'),
    ],
)
def test_external_csv_string_neutralization(value, expected):
    assert neutralize_external_csv_value(value) == expected


def test_external_csv_neutralization_preserves_non_string_values():
    assert neutralize_external_csv_value(12) == 12
    assert neutralize_external_csv_value(-3.5) == -3.5
    assert neutralize_external_csv_value(None) is None


def test_beam_csv_round_trip_preserves_columns_and_neutralizes_only_dangerous_strings(
    tmp_path,
):
    case_root = tmp_path / "日本語 case root"
    case_root.mkdir()
    rows = [
        {"beam_number": 1, "beam_name": "Ordinary Beam"},
        {"beam_number": 2, "beam_name": "=1+1"},
        {"beam_number": 3, "beam_name": "+SUM(A1:A2)"},
        {"beam_number": 4, "beam_name": "-2+3"},
        {"beam_number": 5, "beam_name": "@SUM(A1:A2)"},
        {"beam_number": 6, "beam_name": ""},
        {"beam_number": 7, "beam_name": "日本語, \"照射野\""},
        {"beam_number": 8, "beam_name": "line one\nline two"},
        {"beam_number": 9, "beam_name": "\tformula-like"},
    ]
    output = case_root / "analysis" / "beam_summary.csv"

    with WorkspaceOutputGuard(case_root) as guard:
        write_csv(
            output,
            rows,
            ["beam_number", "beam_name"],
            guard=guard,
        )

    with output.open("r", encoding="utf-8", newline="") as stream:
        restored = list(csv.DictReader(stream))

    assert list(restored[0]) == ["beam_number", "beam_name"]
    assert [row["beam_number"] for row in restored] == [str(i) for i in range(1, 10)]
    assert [row["beam_name"] for row in restored] == [
        "Ordinary Beam",
        "'=1+1",
        "'+SUM(A1:A2)",
        "'-2+3",
        "'@SUM(A1:A2)",
        "",
        '日本語, "照射野"',
        "line one\nline two",
        "'\tformula-like",
    ]


def test_workspace_writer_rejects_symlinked_output_parent_without_outside_write(
    tmp_path,
):
    case_root = tmp_path / "case"
    outside = tmp_path / "outside"
    case_root.mkdir()
    outside.mkdir()
    sentinel = outside / "sentinel.txt"
    sentinel.write_text("preserve", encoding="utf-8")
    try:
        (case_root / "analysis").symlink_to(outside, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"symbolic links are unavailable: {exc}")

    with pytest.raises(UnsafeWorkspacePathError, match="symbolic link|reparse"):
        with WorkspaceOutputGuard(case_root) as guard:
            guard.write_text(case_root / "analysis" / "result.csv", "unsafe")

    assert sentinel.read_text(encoding="utf-8") == "preserve"
    assert not (outside / "result.csv").exists()


def test_workspace_writer_preserves_platform_default_newline_translation(tmp_path):
    case_root = tmp_path / "case"
    case_root.mkdir()
    guarded = case_root / "guarded.inp"
    reference = case_root / "reference.inp"
    content = "first\nsecond\n"

    reference.write_text(content, encoding="utf-8")
    with WorkspaceOutputGuard(case_root) as guard:
        guard.write_text(guarded, content)

    assert guarded.read_bytes() == reference.read_bytes()


def test_workspace_copy_new_only_preserves_an_existing_regular_file(tmp_path):
    case_root = tmp_path / "case"
    case_root.mkdir()
    source = case_root / "staged.out"
    destination = case_root / "final.out"
    source.write_bytes(b"new")
    destination.write_bytes(b"preserve")

    with pytest.raises(FileExistsError):
        with WorkspaceOutputGuard(case_root) as guard:
            guard.copy_file(source, destination, overwrite=False)

    assert destination.read_bytes() == b"preserve"


def test_workspace_writer_rejects_symlinked_case_root(tmp_path):
    actual_root = tmp_path / "actual"
    actual_root.mkdir()
    linked_root = tmp_path / "linked-case"
    try:
        linked_root.symlink_to(actual_root, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"symbolic links are unavailable: {exc}")

    with pytest.raises(UnsafeWorkspacePathError, match="Case root|reparse"):
        with WorkspaceOutputGuard(linked_root) as guard:
            guard.write_text(linked_root / "analysis" / "result.csv", "unsafe")

    assert not (actual_root / "analysis" / "result.csv").exists()


def test_workspace_writer_rejects_symlinked_existing_output_without_overwrite(
    tmp_path,
):
    case_root = tmp_path / "case"
    analysis = case_root / "analysis"
    analysis.mkdir(parents=True)
    outside = tmp_path / "outside.csv"
    outside.write_text("preserve", encoding="utf-8")
    linked_output = analysis / "result.csv"
    try:
        linked_output.symlink_to(outside)
    except OSError as exc:
        pytest.skip(f"symbolic links are unavailable: {exc}")

    with pytest.raises(UnsafeWorkspacePathError, match="symbolic link|reparse"):
        with WorkspaceOutputGuard(case_root) as guard:
            guard.write_text(linked_output, "unsafe")

    assert outside.read_text(encoding="utf-8") == "preserve"


def test_workspace_cleanup_rejects_symlinked_directory_without_outside_delete(
    tmp_path,
):
    case_root = tmp_path / "case"
    outside = tmp_path / "outside"
    case_root.mkdir()
    outside.mkdir()
    sentinel = outside / "sentinel.txt"
    sentinel.write_text("preserve", encoding="utf-8")
    linked_directory = case_root / "staging"
    try:
        linked_directory.symlink_to(outside, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"symbolic links are unavailable: {exc}")

    with pytest.raises(UnsafeWorkspacePathError, match="symbolic link|reparse"):
        with WorkspaceOutputGuard(case_root) as guard:
            guard.rmtree(linked_directory)

    assert sentinel.read_text(encoding="utf-8") == "preserve"
    assert linked_directory.is_symlink()


@pytest.mark.skipif(sys.platform != "win32", reason="real Windows junction behavior")
def test_workspace_writer_rejects_real_windows_junction(tmp_path):
    case_root = tmp_path / "日本語 case"
    outside = tmp_path / "outside"
    case_root.mkdir()
    outside.mkdir()
    (outside / "sentinel.txt").write_text("preserve", encoding="utf-8")
    junction = case_root / "analysis"
    system_root = Path(os.environ["SystemRoot"])
    trusted_cmd = system_root / "System32" / "cmd.exe"
    result = subprocess.run(
        [str(trusted_cmd), "/d", "/c", "mklink", "/J", str(junction), str(outside)],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0:
        pytest.skip(f"junction creation is unavailable: {result.stdout}{result.stderr}")
    assert junction.is_junction()

    with pytest.raises(UnsafeWorkspacePathError, match="junction|reparse"):
        with WorkspaceOutputGuard(case_root) as guard:
            guard.write_text(junction / "result.csv", "unsafe")

    with pytest.raises(UnsafeWorkspacePathError, match="junction|reparse"):
        with WorkspaceOutputGuard(case_root) as guard:
            guard.rmtree(junction)

    assert not (outside / "result.csv").exists()
    assert (outside / "sentinel.txt").read_text(encoding="utf-8") == "preserve"
