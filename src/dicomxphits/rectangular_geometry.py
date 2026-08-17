from __future__ import annotations

import copy
import math
from decimal import Decimal
from typing import Any, Mapping

from dicomxphits.machine_config import MachineConfigError, validate_machine_config


GEOMETRY_MODE = "rectangular_3dcrt"
ACCEPTED_DELIVERY_TYPE = "3dcrt_static"
MLC_STATES = {"present", "fully_open_mlc", "no_mlc"}
PUBLIC_APERTURE_LIMIT_MM = Decimal("100.000")
PUBLIC_APERTURE_MAX_WIDTH_MM = Decimal("200.000")


class RectangularGeometryError(ValueError):
    """Raised when a manifest segment cannot become rectangular geometry."""


def build_intermediate_geometry(segment: Mapping[str, Any], machine_config: Mapping[str, Any]) -> dict[str, Any]:
    segment_copy = copy.deepcopy(dict(segment))
    try:
        config = validate_machine_config(machine_config)
    except MachineConfigError as exc:
        raise RectangularGeometryError(f"invalid machine config: {exc}") from exc

    validate_rectangular_segment_contract(segment_copy, config)
    return _intermediate_from_validated(segment_copy, config)


def build_intermediate_geometries(
    segments: list[Mapping[str, Any]], machine_config: Mapping[str, Any]
) -> list[dict[str, Any]]:
    return [build_intermediate_geometry(segment, machine_config) for segment in segments]


def validate_rectangular_segment_contract(segment: Mapping[str, Any], machine_config: Mapping[str, Any]) -> None:
    if not isinstance(segment, Mapping):
        raise RectangularGeometryError("manifest segment must be an object")
    config = validate_machine_config(machine_config)
    segment_id = segment.get("segment_id")
    if not isinstance(segment_id, str) or not segment_id:
        raise RectangularGeometryError("segment_id is required")
    if any(marker in segment_id.lower() for marker in ("uid", "patient", ".dcm", "/", "\\")):
        raise RectangularGeometryError("segment_id must not contain UID, patient, filename, or path markers")
    if str(segment.get("delivery_type") or "") != ACCEPTED_DELIVERY_TYPE:
        raise RectangularGeometryError("delivery_type must be 3dcrt_static")
    _validate_static_contract(segment)
    _validate_jaws(segment.get("resolved_jaw_positions_mm"))
    _validate_mlc(segment, int(config["mlc"]["leaf_pair_count"]))
    _validate_public_effective_aperture(segment, config)
    _fluence_weight(segment)


def _finite_number(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise RectangularGeometryError(f"{label} must be finite")
    number = float(value)
    if not math.isfinite(number):
        raise RectangularGeometryError(f"{label} must be finite")
    return number


def _positive_finite(value: Any, label: str) -> float:
    number = _finite_number(value, label)
    if number <= 0.0:
        raise RectangularGeometryError(f"{label} must be positive")
    return number


def _validate_static_contract(segment: Mapping[str, Any]) -> None:
    classification = segment.get("static_aperture_classification")
    diagnostics = segment.get("aperture_change_diagnostics")
    if not isinstance(classification, Mapping):
        raise RectangularGeometryError("static_aperture_classification is required")
    if not isinstance(diagnostics, Mapping):
        raise RectangularGeometryError("aperture_change_diagnostics is required")
    if classification.get("status") != "static":
        raise RectangularGeometryError("static_aperture_classification.status must be static")
    if diagnostics.get("status") != "static":
        raise RectangularGeometryError("aperture_change_diagnostics.status must be static")
    if diagnostics.get("dynamic_like") is not False:
        raise RectangularGeometryError("aperture_change_diagnostics.dynamic_like must be false")
    if diagnostics.get("jaw_changed") is not False or diagnostics.get("mlc_changed") is not False:
        raise RectangularGeometryError("aperture change diagnostics must not mark jaw or MLC changes")


def _validate_jaws(value: Any) -> None:
    if not isinstance(value, Mapping):
        raise RectangularGeometryError("resolved_jaw_positions_mm is required")
    x1 = _finite_number(value.get("x1"), "jaw_positions_mm.x1")
    x2 = _finite_number(value.get("x2"), "jaw_positions_mm.x2")
    y1 = _finite_number(value.get("y1"), "jaw_positions_mm.y1")
    y2 = _finite_number(value.get("y2"), "jaw_positions_mm.y2")
    if x1 >= x2:
        raise RectangularGeometryError("jaw_positions_mm.x1 must be less than x2")
    if y1 >= y2:
        raise RectangularGeometryError("jaw_positions_mm.y1 must be less than y2")


def _mlc_positions(value: Any, leaf_pair_count: int) -> dict[str, list[float]]:
    if not isinstance(value, Mapping):
        raise RectangularGeometryError("resolved_mlc_positions_mm is required")
    bank_a = value.get("bank_a")
    bank_b = value.get("bank_b")
    if not isinstance(bank_a, list) or not isinstance(bank_b, list):
        raise RectangularGeometryError("resolved_mlc_positions_mm.bank_a and bank_b must be arrays")
    if len(bank_a) != leaf_pair_count or len(bank_b) != leaf_pair_count:
        raise RectangularGeometryError("MLC bank lengths must match machine config leaf_pair_count")
    result = {"bank_a": [], "bank_b": []}
    for index, (a_value, b_value) in enumerate(zip(bank_a, bank_b)):
        a = _finite_number(a_value, f"bank_a[{index}]")
        b = _finite_number(b_value, f"bank_b[{index}]")
        if a >= b:
            raise RectangularGeometryError(f"bank_a[{index}] must be less than bank_b[{index}]")
        result["bank_a"].append(a)
        result["bank_b"].append(b)
    return result


def _validate_mlc(segment: Mapping[str, Any], leaf_pair_count: int) -> None:
    state = str(segment.get("mlc_aperture_state") or "")
    if state not in MLC_STATES:
        raise RectangularGeometryError("mlc_aperture_state must be present, fully_open_mlc, or no_mlc")
    positions = segment.get("resolved_mlc_positions_mm")
    if state == "no_mlc":
        if positions not in (None, {}):
            raise RectangularGeometryError("no_mlc segments must not include resolved MLC positions")
        return
    if state == "fully_open_mlc" and positions in (None, {}):
        return
    _mlc_positions(positions, leaf_pair_count)


def _decimal_number(value: Any, label: str) -> Decimal:
    return Decimal(str(_finite_number(value, label)))


def _validate_public_effective_aperture(
    segment: Mapping[str, Any],
    config: Mapping[str, Any],
) -> None:
    jaws = segment["resolved_jaw_positions_mm"]
    jaw_x_min = _decimal_number(jaws["x1"], "jaw_positions_mm.x1")
    jaw_x_max = _decimal_number(jaws["x2"], "jaw_positions_mm.x2")
    jaw_y_min = _decimal_number(jaws["y1"], "jaw_positions_mm.y1")
    jaw_y_max = _decimal_number(jaws["y2"], "jaw_positions_mm.y2")
    state = str(segment["mlc_aperture_state"])
    positions = segment.get("resolved_mlc_positions_mm")

    if state == "no_mlc" or positions in (None, {}):
        bounds = (jaw_x_min, jaw_x_max, jaw_y_min, jaw_y_max)
    else:
        leaf_widths = [
            _decimal_number(value, f"mlc.leaf_widths_mm[{index}]")
            for index, value in enumerate(config["mlc"]["leaf_widths_mm"])
        ]
        y_edge = -sum(leaf_widths, Decimal("0")) / Decimal("2")
        y_edges = [y_edge]
        for width in leaf_widths:
            y_edge += width
            y_edges.append(y_edge)

        banks = _mlc_positions(positions, int(config["mlc"]["leaf_pair_count"]))
        rectangles: list[tuple[Decimal, Decimal, Decimal, Decimal]] = []
        for index, (a_value, b_value) in enumerate(zip(banks["bank_a"], banks["bank_b"])):
            x_min = max(jaw_x_min, Decimal(str(a_value)))
            x_max = min(jaw_x_max, Decimal(str(b_value)))
            y_min = max(jaw_y_min, y_edges[index])
            y_max = min(jaw_y_max, y_edges[index + 1])
            if x_min < x_max and y_min < y_max:
                rectangles.append((x_min, x_max, y_min, y_max))
        if not rectangles:
            raise RectangularGeometryError("resolved jaw-MLC common aperture is empty")
        bounds = (
            min(row[0] for row in rectangles),
            max(row[1] for row in rectangles),
            min(row[2] for row in rectangles),
            max(row[3] for row in rectangles),
        )

    for axis, low, high in (
        ("X", bounds[0], bounds[1]),
        ("Y", bounds[2], bounds[3]),
    ):
        if low < -PUBLIC_APERTURE_LIMIT_MM:
            raise RectangularGeometryError(
                f"public aperture scope: {axis} minimum {low} mm is below -100.000 mm"
            )
        if high > PUBLIC_APERTURE_LIMIT_MM:
            raise RectangularGeometryError(
                f"public aperture scope: {axis} maximum {high} mm exceeds +100.000 mm"
            )
        width = high - low
        if width > PUBLIC_APERTURE_MAX_WIDTH_MM:
            raise RectangularGeometryError(
                f"public aperture scope: {axis} width {width} mm exceeds 200.000 mm"
            )


def _fluence_weight(segment: Mapping[str, Any]) -> dict[str, Any]:
    if segment.get("segment_mu") is not None:
        return {"kind": "monitor_units", "value": _positive_finite(segment.get("segment_mu"), "segment_mu")}
    return {"kind": "relative_weight", "value": _positive_finite(segment.get("segment_weight"), "segment_weight")}


def _cm(value: Any, label: str) -> float:
    return _finite_number(value, label) / 10.0


def _positions_cm(
    values: Mapping[str, Any],
    prefix: str,
    *,
    y_projection_scale: float = 1.0,
) -> dict[str, float]:
    result = {key: _cm(values.get(key), f"{prefix}.{key}") for key in values}
    result["y1"] *= y_projection_scale
    result["y2"] *= y_projection_scale
    return result


def _mlc_cm(
    state: str,
    positions: Any,
    *,
    projection_scale: float,
) -> dict[str, list[float]] | None:
    if state == "no_mlc" or positions in (None, {}):
        return None
    # IEC BEAM LIMITING DEVICE +X maps to PHITS local -X under the accepted
    # HFS/couch-zero transform.  Preserve each leaf pair's Y order while
    # reflecting its DICOM MLCX opening [a, b] to PHITS [-b, -a].
    return {
        "bank_a": [
            -_cm(value, "mlc.bank_b") * projection_scale
            for value in positions["bank_b"]
        ],
        "bank_b": [
            -_cm(value, "mlc.bank_a") * projection_scale
            for value in positions["bank_a"]
        ],
    }


def _source_cm(source: Mapping[str, Any]) -> dict[str, Any]:
    if source["model"] == "point":
        return {
            "model": "point",
            "position_cm": [_cm(value, "source.position_mm") for value in source["position_mm"]],
        }
    if source["model"] == "rectangular_fwhm":
        return {
            "model": "rectangular_fwhm",
            "plane_z_cm": _cm(source["plane_z_mm"], "source.plane_z_mm"),
            "fwhm_x_cm": _cm(source["fwhm_x_mm"], "source.fwhm_x_mm"),
            "fwhm_y_cm": _cm(source["fwhm_y_mm"], "source.fwhm_y_mm"),
        }
    return {
        "model": "uniform_rectangular",
        "plane_z_cm": _cm(source["plane_z_mm"], "source.plane_z_mm"),
        "width_x_cm": _cm(source["width_x_mm"], "source.width_x_mm"),
        "width_y_cm": _cm(source["width_y_mm"], "source.width_y_mm"),
    }


def _z_component_cm(component: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "upstream_z_cm": _cm(component["upstream_z_mm"], "upstream_z_mm"),
        "downstream_z_cm": _cm(component["downstream_z_mm"], "downstream_z_mm"),
        "projection_scale": float(component.get("projection_scale", 1.0)),
        "material": component["material"],
    }


def _mlc_geometry_cm(mlc: Mapping[str, Any]) -> dict[str, Any]:
    projection_scale = float(mlc.get("projection_scale", 1.0))
    geometry = _z_component_cm(mlc)
    geometry.update(
        {
            "leaf_pair_count": int(mlc["leaf_pair_count"]),
            "leaf_widths_cm": [
                _cm(value, "mlc.leaf_widths_mm") * projection_scale
                for value in mlc["leaf_widths_mm"]
            ],
            "leaf_depth_cm": _cm(
                mlc["leaf_depth_mm"],
                "mlc.leaf_depth_mm",
            ),
        }
    )
    return geometry


def _transport_settings(config: Mapping[str, Any]) -> dict[str, float]:
    transport = config.get("transport") or {
        "photon_cutoff_mev": 0.01,
        "electron_cutoff_mev": 0.7,
        "positron_cutoff_mev": 0.7,
    }
    return {key: float(value) for key, value in transport.items()}


def _intermediate_from_validated(segment: Mapping[str, Any], config: Mapping[str, Any]) -> dict[str, Any]:
    mlc_state = str(segment["mlc_aperture_state"])
    mlc_positions = segment.get("resolved_mlc_positions_mm")
    mlc_projection_scale = float(config["mlc"].get("projection_scale", 1.0))
    jaw_projection_scale = float(
        config["y_diaphragm"].get("projection_scale", 1.0)
    )
    return {
        "segment_id": segment["segment_id"],
        "geometry_mode": GEOMETRY_MODE,
        "units": {"geometry": "cm", "angles": "deg", "density": "g/cm3"},
        "delivery_type": ACCEPTED_DELIVERY_TYPE,
        "jaw_positions_cm": _positions_cm(
            segment["resolved_jaw_positions_mm"],
            "jaw_positions_mm",
        ),
        "y_diaphragm_positions_cm": _positions_cm(
            segment["resolved_jaw_positions_mm"],
            "jaw_positions_mm",
            y_projection_scale=jaw_projection_scale,
        ),
        "mlc_aperture_state": mlc_state,
        "mlc_positions_cm": _mlc_cm(
            mlc_state,
            mlc_positions,
            projection_scale=mlc_projection_scale,
        ),
        "angles_deg": {
            "gantry": _finite_number(segment.get("gantry_angle_deg"), "gantry_angle_deg"),
            "collimator": _finite_number(segment.get("collimator_angle_deg"), "collimator_angle_deg"),
            "couch": _finite_number(segment.get("couch_angle_deg"), "couch_angle_deg"),
        },
        "fluence_weight": _fluence_weight(segment),
        "source": _source_cm(config["source"]),
        "y_diaphragm": _z_component_cm(config["y_diaphragm"]),
        "mlc_geometry": _mlc_geometry_cm(config["mlc"]),
        "materials": copy.deepcopy(config["materials"]),
        "transport": _transport_settings(config),
        "coordinate_system": copy.deepcopy(config["coordinate_system"]),
        "renderer_ready_unit_marker": "cm_deg_g_cm3",
    }
