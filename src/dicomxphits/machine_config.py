from __future__ import annotations

import copy
import json
import math
from pathlib import Path
from typing import Any, Mapping


SCHEMA_VERSION = "dicomxphits_public_machine_config_v1"
GEOMETRY_UNIT = "mm"
DENSITY_UNIT = "g/cm3"
ROOT_KEYS = {
    "$schema",
    "schema_version",
    "units",
    "coordinate_system",
    "sad_mm",
    "source",
    "materials",
    "y_diaphragm",
    "mlc",
    "transport",
}
UNITS_KEYS = {"geometry", "density"}
COORDINATE_SYSTEM_KEYS = {"origin", "z_axis", "z_positive"}
POINT_SOURCE_KEYS = {"model", "position_mm"}
RECTANGULAR_FWHM_SOURCE_KEYS = {"model", "plane_z_mm", "fwhm_x_mm", "fwhm_y_mm"}
UNIFORM_RECTANGULAR_SOURCE_KEYS = {"model", "plane_z_mm", "width_x_mm", "width_y_mm"}
MATERIAL_KEYS = {"density_g_cm3", "description", "material_block"}
Z_COMPONENT_KEYS = {"upstream_z_mm", "downstream_z_mm", "projection_scale", "material"}
MLC_KEYS = {
    "leaf_pair_count",
    "leaf_widths_mm",
    "leaf_depth_mm",
    "upstream_z_mm",
    "downstream_z_mm",
    "projection_scale",
    "material",
}
TRANSPORT_KEYS = {"photon_cutoff_mev", "electron_cutoff_mev", "positron_cutoff_mev"}


PUBLIC_DEFAULT_MACHINE_CONFIG: dict[str, Any] = {
    "schema_version": SCHEMA_VERSION,
    "units": {"geometry": GEOMETRY_UNIT, "density": DENSITY_UNIT},
    "coordinate_system": {
        "origin": "isocenter",
        "z_axis": "beam",
        "z_positive": "downstream",
    },
    "sad_mm": 1000.0,
    "source": {
        "model": "uniform_rectangular",
        "plane_z_mm": -1000.0,
        "width_x_mm": 3.0,
        "width_y_mm": 3.0,
    },
    "materials": {
        "author_tuned_tungsten_alloy": {
            "density_g_cm3": 11.34,
            "description": (
                "Author-and-collaborator-tuned public research model; "
                "not a vendor table or commissioned machine specification."
            ),
            "material_block": "184W -90.5\n58Ni -6.5\n56Fe -3.0",
        },
    },
    "y_diaphragm": {
        "upstream_z_mm": -489.0,
        "downstream_z_mm": -412.0,
        "projection_scale": 0.571,
        "material": "author_tuned_tungsten_alloy",
    },
    "mlc": {
        "leaf_pair_count": 80,
        "leaf_widths_mm": [5.0] * 80,
        "leaf_depth_mm": 200.0,
        "upstream_z_mm": -600.7,
        "downstream_z_mm": -500.7,
        "projection_scale": 0.483,
        "material": "author_tuned_tungsten_alloy",
    },
    "transport": {
        "photon_cutoff_mev": 0.01,
        "electron_cutoff_mev": 0.7,
        "positron_cutoff_mev": 0.7,
    },
}


class MachineConfigError(ValueError):
    """Raised when a public machine config fails semantic validation."""


def load_machine_config(path: str | Path) -> dict[str, Any]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return validate_machine_config(data)


def public_default_machine_config() -> dict[str, Any]:
    """Return a validated copy of the approved built-in public model."""

    return validate_machine_config(PUBLIC_DEFAULT_MACHINE_CONFIG)


def validate_machine_config(data: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(data, Mapping):
        raise MachineConfigError("machine config must be a JSON object")
    validated = copy.deepcopy(dict(data))
    _reject_extra_keys(validated, ROOT_KEYS, "machine config")
    _validate_schema_version(validated)
    _validate_units(validated)
    _validate_coordinate_system(validated)
    _positive_finite(validated.get("sad_mm"), "sad_mm")
    materials = _validate_materials(validated.get("materials"))
    _validate_source(validated.get("source"))
    _validate_z_component(validated.get("y_diaphragm"), "y_diaphragm", materials)
    _validate_mlc(validated.get("mlc"), materials)
    _validate_transport(validated.get("transport"))
    return validated


def _require_mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise MachineConfigError(f"{label} must be an object")
    return value


def _reject_extra_keys(value: Mapping[str, Any], allowed: set[str], label: str) -> None:
    extras = sorted(str(key) for key in value if key not in allowed)
    if extras:
        raise MachineConfigError(f"{label} has unsupported field(s): {', '.join(extras)}")


def _validate_schema_version(data: Mapping[str, Any]) -> None:
    version = data.get("schema_version")
    if version != SCHEMA_VERSION:
        raise MachineConfigError(f"schema_version must be {SCHEMA_VERSION}")


def _validate_units(data: Mapping[str, Any]) -> None:
    units = _require_mapping(data.get("units"), "units")
    _reject_extra_keys(units, UNITS_KEYS, "units")
    if units.get("geometry") != GEOMETRY_UNIT:
        raise MachineConfigError("units.geometry must be mm")
    if units.get("density") != DENSITY_UNIT:
        raise MachineConfigError("units.density must be g/cm3")


def _validate_coordinate_system(data: Mapping[str, Any]) -> None:
    coordinate_system = _require_mapping(data.get("coordinate_system"), "coordinate_system")
    _reject_extra_keys(coordinate_system, COORDINATE_SYSTEM_KEYS, "coordinate_system")
    if coordinate_system.get("origin") != "isocenter":
        raise MachineConfigError("coordinate_system.origin must be isocenter")
    if coordinate_system.get("z_axis") != "beam":
        raise MachineConfigError("coordinate_system.z_axis must be beam")
    if coordinate_system.get("z_positive") != "downstream":
        raise MachineConfigError("coordinate_system.z_positive must be downstream")


def _positive_finite(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise MachineConfigError(f"{label} must be a positive finite number")
    number = float(value)
    if not math.isfinite(number) or number <= 0:
        raise MachineConfigError(f"{label} must be a positive finite number")
    return number


def _finite_number(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise MachineConfigError(f"{label} must be a finite number")
    number = float(value)
    if not math.isfinite(number):
        raise MachineConfigError(f"{label} must be a finite number")
    return number


def _validate_vector3(value: Any, label: str) -> None:
    if not isinstance(value, list) or len(value) != 3:
        raise MachineConfigError(f"{label} must contain exactly 3 finite numbers")
    for index, item in enumerate(value):
        _finite_number(item, f"{label}[{index}]")


def _validate_source(value: Any) -> None:
    source = _require_mapping(value, "source")
    model = source.get("model")
    if model == "point":
        _reject_extra_keys(source, POINT_SOURCE_KEYS, "source")
        _validate_vector3(source.get("position_mm"), "source.position_mm")
        return
    if model == "rectangular_fwhm":
        _reject_extra_keys(source, RECTANGULAR_FWHM_SOURCE_KEYS, "source")
        _finite_number(source.get("plane_z_mm"), "source.plane_z_mm")
        _positive_finite(source.get("fwhm_x_mm"), "source.fwhm_x_mm")
        _positive_finite(source.get("fwhm_y_mm"), "source.fwhm_y_mm")
        return
    if model == "uniform_rectangular":
        _reject_extra_keys(source, UNIFORM_RECTANGULAR_SOURCE_KEYS, "source")
        _finite_number(source.get("plane_z_mm"), "source.plane_z_mm")
        _positive_finite(source.get("width_x_mm"), "source.width_x_mm")
        _positive_finite(source.get("width_y_mm"), "source.width_y_mm")
        return
    raise MachineConfigError(
        "source.model must be point, rectangular_fwhm, or uniform_rectangular"
    )


def _validate_materials(value: Any) -> set[str]:
    materials = _require_mapping(value, "materials")
    if not materials:
        raise MachineConfigError("materials must contain at least one material")
    names: set[str] = set()
    for name, material in materials.items():
        if not isinstance(name, str) or not name:
            raise MachineConfigError("material names must be non-empty strings")
        material_map = _require_mapping(material, f"materials.{name}")
        _reject_extra_keys(material_map, MATERIAL_KEYS, f"materials.{name}")
        _positive_finite(material_map.get("density_g_cm3"), f"materials.{name}.density_g_cm3")
        if not isinstance(material_map.get("material_block"), str) or not material_map["material_block"].strip():
            raise MachineConfigError(f"materials.{name}.material_block is required")
        for optional_text_key in ("description", "material_block"):
            if optional_text_key in material_map and not isinstance(material_map[optional_text_key], str):
                raise MachineConfigError(f"materials.{name}.{optional_text_key} must be a string")
        names.add(name)
    return names


def _validate_material_ref(value: Any, label: str, materials: set[str]) -> None:
    if not isinstance(value, str) or not value:
        raise MachineConfigError(f"{label} must be a non-empty material name")
    if value not in materials:
        raise MachineConfigError(f"{label} must reference a material in materials")


def _validate_z_order(component: Mapping[str, Any], label: str) -> None:
    upstream = _finite_number(component.get("upstream_z_mm"), f"{label}.upstream_z_mm")
    downstream = _finite_number(component.get("downstream_z_mm"), f"{label}.downstream_z_mm")
    if upstream >= downstream:
        raise MachineConfigError(f"{label}.upstream_z_mm must be less than {label}.downstream_z_mm")


def _validate_z_component(value: Any, label: str, materials: set[str]) -> None:
    component = _require_mapping(value, label)
    _reject_extra_keys(component, Z_COMPONENT_KEYS, label)
    _validate_z_order(component, label)
    _validate_projection_scale(component.get("projection_scale"), label)
    _validate_material_ref(component.get("material"), f"{label}.material", materials)


def _validate_mlc(value: Any, materials: set[str]) -> None:
    mlc = _require_mapping(value, "mlc")
    _reject_extra_keys(mlc, MLC_KEYS, "mlc")
    leaf_pair_count = mlc.get("leaf_pair_count")
    if isinstance(leaf_pair_count, bool) or not isinstance(leaf_pair_count, int) or leaf_pair_count < 1:
        raise MachineConfigError("mlc.leaf_pair_count must be a positive integer")
    leaf_widths = mlc.get("leaf_widths_mm")
    if not isinstance(leaf_widths, list):
        raise MachineConfigError("mlc.leaf_widths_mm must be an array")
    if len(leaf_widths) != leaf_pair_count:
        raise MachineConfigError("mlc.leaf_widths_mm length must match mlc.leaf_pair_count")
    for index, width in enumerate(leaf_widths):
        _positive_finite(width, f"mlc.leaf_widths_mm[{index}]")
    _positive_finite(mlc.get("leaf_depth_mm"), "mlc.leaf_depth_mm")
    _validate_z_order(mlc, "mlc")
    _validate_projection_scale(mlc.get("projection_scale"), "mlc")
    _validate_material_ref(mlc.get("material"), "mlc.material", materials)


def _validate_projection_scale(value: Any, label: str) -> None:
    if value is None:
        return
    number = _positive_finite(value, f"{label}.projection_scale")
    if number > 1.0:
        raise MachineConfigError(f"{label}.projection_scale must not exceed 1")


def _validate_transport(value: Any) -> None:
    if value is None:
        return
    transport = _require_mapping(value, "transport")
    _reject_extra_keys(transport, TRANSPORT_KEYS, "transport")
    for key in sorted(TRANSPORT_KEYS):
        _positive_finite(transport.get(key), f"transport.{key}")
