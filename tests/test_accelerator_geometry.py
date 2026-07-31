from __future__ import annotations

import sys
from pathlib import Path

import pytest

PUBLIC_SRC = Path(__file__).resolve().parents[1] / "src"
if str(PUBLIC_SRC) not in sys.path:
    sys.path.insert(0, str(PUBLIC_SRC))

from dicomxphits.accelerator_geometry import (
    AcceleratorGeometryDescriptor,
    AcceleratorGeometryError,
    MlcApertureState,
    MlcGeometry,
    SourceGeometry,
    YJawApertureState,
    YJawGeometry,
)


def source() -> SourceGeometry:
    return SourceGeometry(model="point", position_cm=(0.0, 0.0, -100.0), beam_direction=(0.0, 0.0, 1.0))


def mlc_geometry() -> MlcGeometry:
    return MlcGeometry(
        leaf_pair_count=2,
        leaf_widths_cm=(0.5, 0.5),
        upstream_z_cm=-60.0,
        downstream_z_cm=-50.0,
        leaf_depth_cm=6.0,
    )


def mlc_aperture() -> MlcApertureState:
    return MlcApertureState(state="present", bank_a_cm=(-2.0, -1.0), bank_b_cm=(2.0, 1.0))


def y_jaw_geometry() -> YJawGeometry:
    return YJawGeometry(upstream_z_cm=-46.1, downstream_z_cm=-38.0)


def y_jaw_aperture() -> YJawApertureState:
    return YJawApertureState(state="present", y1_cm=-5.0, y2_cm=5.0)


def test_source_only_descriptor_can_be_created() -> None:
    descriptor = AcceleratorGeometryDescriptor(source=source())

    assert descriptor.source.position_cm == (0.0, 0.0, -100.0)
    assert descriptor.coordinate_system == "phits_cm_isocenter"
    assert descriptor.mlc_geometry is None
    assert descriptor.y_jaw_geometry is None


def test_source_and_y_jaw_descriptor_can_be_created() -> None:
    descriptor = AcceleratorGeometryDescriptor(
        source=source(),
        y_jaw_geometry=y_jaw_geometry(),
        y_jaw_aperture=y_jaw_aperture(),
    )

    assert descriptor.y_jaw_geometry is not None
    assert descriptor.y_jaw_aperture is not None
    assert descriptor.y_jaw_aperture.y1_cm == -5.0


def test_source_mlc_and_y_jaw_descriptor_can_be_created() -> None:
    descriptor = AcceleratorGeometryDescriptor(
        source=source(),
        mlc_geometry=mlc_geometry(),
        mlc_aperture=mlc_aperture(),
        y_jaw_geometry=y_jaw_geometry(),
        y_jaw_aperture=y_jaw_aperture(),
    )

    assert descriptor.source is not None
    assert descriptor.mlc_geometry is not None
    assert descriptor.mlc_aperture is not None
    assert descriptor.y_jaw_geometry is not None
    assert descriptor.y_jaw_aperture is not None


def test_coordinate_system_rejects_arbitrary_values() -> None:
    with pytest.raises(AcceleratorGeometryError, match="coordinate_system"):
        AcceleratorGeometryDescriptor(source=source(), coordinate_system="dicom_lps_mm")


def test_beam_direction_rejects_zero_vector() -> None:
    with pytest.raises(AcceleratorGeometryError, match="zero vector"):
        SourceGeometry(model="point", position_cm=(0.0, 0.0, -100.0), beam_direction=(0.0, 0.0, 0.0))


def test_invalid_mlc_bank_length_raises_error() -> None:
    with pytest.raises(AcceleratorGeometryError, match="leaf_pair_count"):
        AcceleratorGeometryDescriptor(
            source=source(),
            mlc_geometry=mlc_geometry(),
            mlc_aperture=MlcApertureState(state="present", bank_a_cm=(-2.0,), bank_b_cm=(2.0,)),
        )


def test_present_mlc_aperture_rejects_missing_banks() -> None:
    with pytest.raises(AcceleratorGeometryError, match="requires bank_a_cm and bank_b_cm"):
        MlcApertureState(state="present")


def test_no_mlc_rejects_supplied_mlc_geometry() -> None:
    with pytest.raises(AcceleratorGeometryError, match="absent MLC geometry"):
        AcceleratorGeometryDescriptor(
            source=source(),
            mlc_geometry=mlc_geometry(),
            mlc_aperture=MlcApertureState(state="no_mlc"),
        )


def test_invalid_y_jaw_aperture_raises_error() -> None:
    with pytest.raises(AcceleratorGeometryError, match="y1_cm must be less than y2_cm"):
        YJawApertureState(state="present", y1_cm=5.0, y2_cm=5.0)


def test_present_y_jaw_aperture_rejects_missing_geometry() -> None:
    with pytest.raises(AcceleratorGeometryError, match="requires Y-Jaw geometry"):
        AcceleratorGeometryDescriptor(source=source(), y_jaw_aperture=y_jaw_aperture())


def test_invalid_z_boundary_raises_error() -> None:
    with pytest.raises(AcceleratorGeometryError, match="z boundaries"):
        YJawGeometry(upstream_z_cm=-38.0, downstream_z_cm=-46.1)


def test_to_dict_contains_first_class_descriptor_keys() -> None:
    descriptor = AcceleratorGeometryDescriptor(
        source=source(),
        mlc_geometry=mlc_geometry(),
        mlc_aperture=mlc_aperture(),
        y_jaw_geometry=y_jaw_geometry(),
        y_jaw_aperture=y_jaw_aperture(),
    )

    payload = descriptor.to_dict()

    assert {"source", "mlc_geometry", "mlc_aperture", "y_jaw_geometry", "y_jaw_aperture"} <= set(payload)
    assert payload["source"]["position_cm"] == (0.0, 0.0, -100.0)
    assert payload["mlc_geometry"]["leaf_pair_count"] == 2
    assert payload["mlc_aperture"]["state"] == "present"
    assert payload["y_jaw_geometry"]["upstream_z_cm"] == -46.1
    assert payload["y_jaw_aperture"]["state"] == "present"


def test_descriptor_does_not_generate_phits_text() -> None:
    descriptor = AcceleratorGeometryDescriptor(source=source())

    assert not hasattr(descriptor, "render")
    assert not hasattr(descriptor, "render_phits")
    assert "[ Source ]" not in str(descriptor.to_dict())
