from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import pytest

PUBLIC_SRC = Path(__file__).resolve().parents[1] / "src"
if str(PUBLIC_SRC) not in sys.path:
    sys.path.insert(0, str(PUBLIC_SRC))

from dicomxphits.machine_config import (
    MachineConfigError,
    load_machine_config,
    public_default_machine_config,
    validate_machine_config,
)


PUBLIC_ROOT = Path(__file__).resolve().parents[1]


def valid_config(**overrides):
    config = {
        "schema_version": "dicomxphits_public_machine_config_v1",
        "units": {
            "geometry": "mm",
            "density": "g/cm3",
        },
        "coordinate_system": {
            "origin": "isocenter",
            "z_axis": "beam",
            "z_positive": "downstream",
        },
        "sad_mm": 1000.0,
        "source": {
            "model": "point",
            "position_mm": [0.0, 0.0, -1000.0],
        },
        "materials": {
            "shielding": {
                "density_g_cm3": 17.0,
                "description": "Synthetic public test material.",
                "material_block": "74W 1",
            },
        },
        "y_diaphragm": {
            "upstream_z_mm": -461.0,
            "downstream_z_mm": -380.0,
            "material": "shielding",
        },
        "mlc": {
            "leaf_pair_count": 4,
            "leaf_widths_mm": [5.0, 5.0, 5.0, 5.0],
            "leaf_depth_mm": 60.0,
            "upstream_z_mm": -350.0,
            "downstream_z_mm": -300.0,
            "material": "shielding",
        },
    }
    config.update(overrides)
    return config


def test_load_machine_config_reads_valid_json(tmp_path):
    path = tmp_path / "machine.json"
    path.write_text(json.dumps(valid_config()), encoding="utf-8")

    loaded = load_machine_config(path)

    assert loaded["schema_version"] == "dicomxphits_public_machine_config_v1"
    assert loaded["units"]["geometry"] == "mm"
    assert loaded["mlc"]["leaf_pair_count"] == 4


def test_public_example_machine_config_is_renderer_usable():
    loaded = load_machine_config(PUBLIC_ROOT / "config" / "dicomxphits.machine.example.json")

    material = loaded["materials"]["water_equivalent_public_placeholder"]
    assert material["material_block"].strip()
    assert loaded["y_diaphragm"]["material"] == "water_equivalent_public_placeholder"
    assert loaded["mlc"]["material"] == "water_equivalent_public_placeholder"


def test_public_default_machine_config_matches_approved_model():
    first = public_default_machine_config()
    second = public_default_machine_config()

    assert first is not second
    assert first["source"] == {
        "model": "uniform_rectangular",
        "plane_z_mm": -1000.0,
        "width_x_mm": 3.0,
        "width_y_mm": 3.0,
    }
    assert first["sad_mm"] == 1000.0
    assert first["y_diaphragm"]["upstream_z_mm"] == -489.0
    assert first["y_diaphragm"]["downstream_z_mm"] == -412.0
    assert first["y_diaphragm"]["projection_scale"] == 0.571
    assert first["mlc"]["leaf_pair_count"] == 80
    assert first["mlc"]["leaf_widths_mm"] == [5.0] * 80
    assert first["mlc"]["leaf_depth_mm"] == 200.0
    assert first["mlc"]["upstream_z_mm"] == -600.7
    assert first["mlc"]["downstream_z_mm"] == -500.7
    assert first["mlc"]["projection_scale"] == 0.483
    assert first["materials"]["author_tuned_tungsten_alloy"]["density_g_cm3"] == 11.34
    assert first["transport"] == {
        "photon_cutoff_mev": 0.01,
        "electron_cutoff_mev": 0.7,
        "positron_cutoff_mev": 0.7,
    }


@pytest.mark.parametrize("version", [None, "unknown"])
def test_validate_machine_config_rejects_missing_or_unknown_schema_version(version):
    config = valid_config()
    if version is None:
        config.pop("schema_version")
    else:
        config["schema_version"] = version

    with pytest.raises(MachineConfigError, match="schema_version"):
        validate_machine_config(config)


def test_validate_machine_config_rejects_unknown_source_model():
    config = valid_config(source={"model": "gaussian", "position_mm": [0.0, 0.0, -1000.0]})

    with pytest.raises(MachineConfigError, match="source.model"):
        validate_machine_config(config)


def test_validate_machine_config_rejects_extra_root_field():
    config = valid_config(unexpected=True)

    with pytest.raises(MachineConfigError, match="unsupported field"):
        validate_machine_config(config)


def test_validate_machine_config_requires_point_source_position():
    config = valid_config(source={"model": "point"})

    with pytest.raises(MachineConfigError, match="source.position_mm"):
        validate_machine_config(config)


def test_validate_machine_config_rejects_point_source_extra_fields():
    config = valid_config(
        source={
            "model": "point",
            "position_mm": [0.0, 0.0, -1000.0],
            "plane_z_mm": -950.0,
            "fwhm_x_mm": 1.0,
            "fwhm_y_mm": 1.0,
        }
    )

    with pytest.raises(MachineConfigError, match="unsupported field"):
        validate_machine_config(config)


def test_validate_machine_config_accepts_rectangular_fwhm_source():
    config = valid_config(
        source={
            "model": "rectangular_fwhm",
            "plane_z_mm": -950.0,
            "fwhm_x_mm": 1.5,
            "fwhm_y_mm": 2.5,
        }
    )

    validated = validate_machine_config(config)

    assert validated["source"]["model"] == "rectangular_fwhm"
    assert validated["source"]["fwhm_x_mm"] == 1.5


def test_validate_machine_config_accepts_uniform_rectangular_source():
    config = valid_config(
        source={
            "model": "uniform_rectangular",
            "plane_z_mm": -1000.0,
            "width_x_mm": 3.0,
            "width_y_mm": 3.0,
        }
    )

    validated = validate_machine_config(config)

    assert validated["source"]["model"] == "uniform_rectangular"
    assert validated["source"]["width_x_mm"] == 3.0


@pytest.mark.parametrize(
    "source",
    [
        {"model": "rectangular_fwhm", "fwhm_x_mm": 1.0, "fwhm_y_mm": 1.0},
        {"model": "rectangular_fwhm", "plane_z_mm": -950.0, "fwhm_y_mm": 1.0},
        {"model": "rectangular_fwhm", "plane_z_mm": -950.0, "fwhm_x_mm": 1.0},
    ],
)
def test_validate_machine_config_requires_rectangular_fwhm_fields(source):
    config = valid_config(source=source)

    with pytest.raises(MachineConfigError, match="source"):
        validate_machine_config(config)


@pytest.mark.parametrize("value", [0.0, -1.0, float("inf"), "wide"])
def test_validate_machine_config_rejects_invalid_fwhm_values(value):
    config = valid_config(
        source={
            "model": "rectangular_fwhm",
            "plane_z_mm": -950.0,
            "fwhm_x_mm": value,
            "fwhm_y_mm": 1.0,
        }
    )

    with pytest.raises(MachineConfigError, match="fwhm_x_mm"):
        validate_machine_config(config)


@pytest.mark.parametrize(
    "units",
    [
        {"geometry": "cm", "density": "g/cm3"},
        {"geometry": "mm", "density": "kg/m3"},
    ],
)
def test_validate_machine_config_rejects_invalid_units(units):
    config = valid_config(units=units)

    with pytest.raises(MachineConfigError, match="units"):
        validate_machine_config(config)


@pytest.mark.parametrize(
    "field, value",
    [
        ("units", {"geometry": "mm", "density": "g/cm3", "extra": "nope"}),
        ("coordinate_system", {"origin": "isocenter", "z_axis": "beam", "z_positive": "downstream", "extra": "nope"}),
    ],
)
def test_validate_machine_config_rejects_extra_settings_fields(field, value):
    config = valid_config(**{field: value})

    with pytest.raises(MachineConfigError, match="unsupported field"):
        validate_machine_config(config)


@pytest.mark.parametrize(
    "component",
    [
        ("y_diaphragm", {"upstream_z_mm": -380.0, "downstream_z_mm": -461.0, "material": "shielding"}),
        (
            "mlc",
            {
                "leaf_pair_count": 4,
                "leaf_widths_mm": [5.0, 5.0, 5.0, 5.0],
                "leaf_depth_mm": 60.0,
                "upstream_z_mm": -300.0,
                "downstream_z_mm": -350.0,
                "material": "shielding",
            },
        ),
    ],
)
def test_validate_machine_config_rejects_invalid_z_order(component):
    name, value = component
    config = valid_config(**{name: value})

    with pytest.raises(MachineConfigError, match="upstream_z_mm"):
        validate_machine_config(config)


@pytest.mark.parametrize(
    "leaf_widths",
    [
        [5.0, 5.0, 5.0],
        [5.0, 0.0, 5.0, 5.0],
        [5.0, float("inf"), 5.0, 5.0],
    ],
)
def test_validate_machine_config_rejects_invalid_leaf_widths(leaf_widths):
    config = valid_config()
    config["mlc"]["leaf_widths_mm"] = leaf_widths

    with pytest.raises(MachineConfigError, match="leaf_widths_mm"):
        validate_machine_config(config)


@pytest.mark.parametrize(
    "patch, match",
    [
        ({"y_diaphragm": {"upstream_z_mm": -461.0, "downstream_z_mm": -380.0, "material": "missing"}}, "material"),
        ({"materials": {"": {"density_g_cm3": 17.0}}}, "material names"),
        ({"materials": {"shielding": {}}}, "density_g_cm3"),
        ({"materials": {"shielding": {"density_g_cm3": 0.0}}}, "density_g_cm3"),
        ({"materials": {"shielding": {"density_g_cm3": 17.0}}}, "material_block"),
        ({"materials": {"shielding": {"density_g_cm3": 17.0, "material_block": ""}}}, "material_block"),
    ],
)
def test_validate_machine_config_rejects_invalid_materials(patch, match):
    config = valid_config()
    config.update(patch)

    with pytest.raises(MachineConfigError, match=match):
        validate_machine_config(config)


@pytest.mark.parametrize(
    "material",
    [
        {"density_g_cm3": 17.0, "unexpected": "nope"},
        {"density_g_cm3": 17.0, "material_block": 123},
        {"density_g_cm3": 17.0, "description": 123},
    ],
)
def test_validate_machine_config_rejects_schema_invalid_material_fields(material):
    config = valid_config(materials={"shielding": material})

    with pytest.raises(MachineConfigError):
        validate_machine_config(config)


@pytest.mark.parametrize(
    "component",
    [
        ("y_diaphragm", {"upstream_z_mm": -461.0, "downstream_z_mm": -380.0, "material": "shielding", "extra": "nope"}),
        (
            "mlc",
            {
                "leaf_pair_count": 4,
                "leaf_widths_mm": [5.0, 5.0, 5.0, 5.0],
                "leaf_depth_mm": 60.0,
                "upstream_z_mm": -350.0,
                "downstream_z_mm": -300.0,
                "material": "shielding",
                "extra": "nope",
            },
        ),
    ],
)
def test_validate_machine_config_rejects_extra_geometry_component_fields(component):
    name, value = component
    config = valid_config(**{name: value})

    with pytest.raises(MachineConfigError, match="unsupported field"):
        validate_machine_config(config)


def test_validate_machine_config_does_not_mutate_input_data():
    config = valid_config()
    original = copy.deepcopy(config)

    validated = validate_machine_config(config)

    assert config == original
    assert validated == original
    assert validated is not config
    assert validated["source"] is not config["source"]


def test_load_machine_config_does_not_create_files_or_outputs(tmp_path):
    path = tmp_path / "machine.json"
    path.write_text(json.dumps(valid_config()), encoding="utf-8")
    before = sorted(p.relative_to(tmp_path).as_posix() for p in tmp_path.rglob("*"))

    load_machine_config(path)

    after = sorted(p.relative_to(tmp_path).as_posix() for p in tmp_path.rglob("*"))
    assert after == before
