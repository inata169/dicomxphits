from __future__ import annotations

import pytest

from dicomxphits.phits_geometry_diagnostics import (
    GEOMETRY_DIAGNOSTICS_SCHEMA_VERSION,
    PhitsGeometryDiagnosticsError,
    parse_phits_geometry_diagnostics,
    require_clean_phits_geometry_diagnostics,
)


CLEAN_SUMMARY = """\
 Number of lost particles = 0
 Number of geometry recovering : 0
 Number of unrecovered errors     0
"""

PHITS_335_CLEAN_SUMMARY = """\
 Number of lost particles     =     0 / nlost =    10000
 Number of geometry recovering = 0
 Number of unrecovered errors = 0
"""


def test_parse_clean_phits_geometry_diagnostics() -> None:
    evidence = parse_phits_geometry_diagnostics(CLEAN_SUMMARY.splitlines())

    assert evidence == {
        "schema_version": GEOMETRY_DIAGNOSTICS_SCHEMA_VERSION,
        "status": "clean",
        "counts": {
            "lost_particles": 0,
            "geometry_recovering": 0,
            "unrecovered_errors": 0,
        },
    }
    assert require_clean_phits_geometry_diagnostics(evidence) == evidence["counts"]


def test_parse_phits_335_lost_particle_summary() -> None:
    evidence = parse_phits_geometry_diagnostics(
        PHITS_335_CLEAN_SUMMARY.splitlines()
    )

    assert evidence["status"] == "clean"
    assert evidence["counts"] == {
        "lost_particles": 0,
        "geometry_recovering": 0,
        "unrecovered_errors": 0,
    }


def test_nonzero_phits_335_lost_particle_count_is_not_clean() -> None:
    text = PHITS_335_CLEAN_SUMMARY.replace(
        "Number of lost particles     =     0 / nlost =    10000",
        "Number of lost particles     =     2 / nlost =    10000",
    )

    evidence = parse_phits_geometry_diagnostics(text.splitlines())

    assert evidence["status"] == "error"
    assert evidence["counts"]["lost_particles"] == 2
    with pytest.raises(PhitsGeometryDiagnosticsError, match="not clean"):
        require_clean_phits_geometry_diagnostics(evidence)


@pytest.mark.parametrize(
    ("label", "expected_key"),
    [
        ("Number of lost particles", "lost_particles"),
        ("Number of geometry recovering", "geometry_recovering"),
        ("Number of unrecovered errors", "unrecovered_errors"),
    ],
)
def test_nonzero_phits_geometry_diagnostic_is_not_clean(
    label: str,
    expected_key: str,
) -> None:
    text = CLEAN_SUMMARY.replace(f"{label} = 0", f"{label} = 2").replace(
        f"{label} : 0", f"{label} : 2"
    ).replace(f"{label}     0", f"{label}     2")

    evidence = parse_phits_geometry_diagnostics(text.splitlines())

    assert evidence["status"] == "error"
    assert evidence["counts"][expected_key] == 2
    with pytest.raises(PhitsGeometryDiagnosticsError, match="not clean"):
        require_clean_phits_geometry_diagnostics(evidence)


@pytest.mark.parametrize(
    "text",
    [
        "Number of lost particles = 0\nNumber of geometry recovering = 0\n",
        CLEAN_SUMMARY + "Number of lost particles = 0\n",
        CLEAN_SUMMARY.replace("Number of geometry recovering : 0", "Number of geometry recovering = -1"),
        CLEAN_SUMMARY.replace("Number of unrecovered errors     0", "Number of unrecovered errors = NaN"),
        CLEAN_SUMMARY.replace(
            "Number of lost particles = 0",
            "Number of lost particles = 0 = 2",
        ),
        CLEAN_SUMMARY.replace(
            "Number of lost particles = 0",
            "Number of lost particles = 0 1",
        ),
    ],
)
def test_missing_duplicate_or_malformed_geometry_summary_fails(text: str) -> None:
    with pytest.raises(PhitsGeometryDiagnosticsError):
        parse_phits_geometry_diagnostics(text.splitlines())


@pytest.mark.parametrize(
    "suffix",
    [
        " / nlost =",
        " / nlost = -1",
        " / nlost = NaN",
        " / nlast = 10000",
        " /nlost = 10000",
        " / nlost=10000",
        " / nlost = 10000 trailing",
    ],
)
def test_invalid_phits_335_lost_particle_suffix_fails(suffix: str) -> None:
    text = CLEAN_SUMMARY.replace(
        "Number of lost particles = 0",
        f"Number of lost particles = 0{suffix}",
    )

    with pytest.raises(PhitsGeometryDiagnosticsError, match="malformed"):
        parse_phits_geometry_diagnostics(text.splitlines())


def test_unrelated_overlap_text_is_not_a_diagnostic_count() -> None:
    evidence = parse_phits_geometry_diagnostics(
        ["A title mentioning overlap", *CLEAN_SUMMARY.splitlines()]
    )

    assert evidence["status"] == "clean"
