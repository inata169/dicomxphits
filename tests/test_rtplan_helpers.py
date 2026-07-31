from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

PUBLIC_SRC = Path(__file__).resolve().parents[1] / "src"
if str(PUBLIC_SRC) not in sys.path:
    sys.path.insert(0, str(PUBLIC_SRC))

from dicomxphits.rtplan_helpers import (
    MLC_PREFIXES,
    as_float,
    as_float_list,
    as_int,
    beam_leaf_pair_counts,
    beam_leaf_position_boundaries,
    dcm_get,
    is_mlc_device,
)


def make_device(device_type: str, **values: object) -> SimpleNamespace:
    return SimpleNamespace(RTBeamLimitingDeviceType=device_type, **values)


def make_beam(*devices: SimpleNamespace) -> SimpleNamespace:
    return SimpleNamespace(BeamLimitingDeviceSequence=list(devices))


def test_dcm_get_returns_attribute_or_default() -> None:
    obj = SimpleNamespace(BeamNumber=7)

    assert dcm_get(obj, "BeamNumber") == 7
    assert dcm_get(obj, "Missing", "fallback") == "fallback"


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, None),
        ("1.25", 1.25),
        (2, 2.0),
        ("bad", None),
        (object(), None),
    ],
)
def test_as_float_coerces_safe_values(value: object, expected: float | None) -> None:
    assert as_float(value) == expected


def test_as_float_uses_default_for_missing_or_invalid_values() -> None:
    assert as_float(None, 3.5) == 3.5
    assert as_float("bad", 4.5) == 4.5


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, None),
        ("3", 3),
        (4.0, 4),
        ("bad", None),
        (object(), None),
    ],
)
def test_as_int_coerces_safe_values(value: object, expected: int | None) -> None:
    assert as_int(value) == expected


def test_as_int_uses_default_for_missing_or_invalid_values() -> None:
    assert as_int(None, 9) == 9
    assert as_int("bad", 8) == 8


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, []),
        ([1, "2.5", 3.0], [1.0, 2.5, 3.0]),
        ((4, "5.5"), [4.0, 5.5]),
        ("bad", []),
        ([1, "bad"], []),
    ],
)
def test_as_float_list_coerces_only_complete_numeric_sequences(
    value: object,
    expected: list[float],
) -> None:
    assert as_float_list(value) == expected


def test_mlc_prefix_definition_drives_mlc_detection() -> None:
    assert MLC_PREFIXES == ("MLC",)
    assert is_mlc_device("MLCX")
    assert is_mlc_device("MLCY")
    assert not is_mlc_device("ASYMX")
    assert not is_mlc_device("")


def test_beam_leaf_pair_counts_uses_device_metadata() -> None:
    data = make_beam(
        make_device("ASYMX", NumberOfLeafJawPairs=1),
        make_device("MLCX", NumberOfLeafJawPairs="80"),
        make_device("MLCY", NumberOfLeafJawPairs=40),
        make_device("", NumberOfLeafJawPairs=3),
        make_device("MLCZ", NumberOfLeafJawPairs="bad"),
    )

    assert beam_leaf_pair_counts(data) == {"ASYMX": 1, "MLCX": 80, "MLCY": 40}


def test_beam_leaf_pair_counts_handles_missing_sequence() -> None:
    assert beam_leaf_pair_counts(SimpleNamespace()) == {}


def test_beam_leaf_position_boundaries_keeps_mlc_boundaries_only() -> None:
    data = make_beam(
        make_device("ASYMX", LeafPositionBoundaries=[-10, 10]),
        make_device("MLCX", LeafPositionBoundaries=[-20, "0", 20]),
        make_device("MLCY", LeafPositionBoundaries=None),
        make_device("MLCZ", LeafPositionBoundaries=[-1, "bad", 1]),
    )

    assert beam_leaf_position_boundaries(data) == {"MLCX": [-20.0, 0.0, 20.0]}


def test_beam_leaf_position_boundaries_handles_missing_sequence() -> None:
    assert beam_leaf_position_boundaries(SimpleNamespace()) == {}
