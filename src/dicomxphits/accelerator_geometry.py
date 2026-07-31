from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from typing import Any, Literal


COORDINATE_SYSTEM = "phits_cm_isocenter"
SourceModel = Literal["point", "finite_rect"]
MlcApertureKind = Literal["present", "fully_open_mlc", "no_mlc"]
YJawApertureKind = Literal["present", "absent"]


class AcceleratorGeometryError(ValueError):
    """Raised when an accelerator geometry descriptor violates the public contract."""


def _finite_number(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise AcceleratorGeometryError(f"{label} must be a finite number")
    number = float(value)
    if not math.isfinite(number):
        raise AcceleratorGeometryError(f"{label} must be a finite number")
    return 0.0 if number == 0.0 else number


def _finite_tuple(value: Any, label: str, length: int) -> tuple[float, ...]:
    if not isinstance(value, (tuple, list)) or len(value) != length:
        raise AcceleratorGeometryError(f"{label} must contain {length} finite numbers")
    return tuple(_finite_number(item, f"{label}[{index}]") for index, item in enumerate(value))


def _optional_number_tuple(value: Any, label: str) -> tuple[float, ...] | None:
    if value is None:
        return None
    if not isinstance(value, (tuple, list)) or not value:
        raise AcceleratorGeometryError(f"{label} must contain positive finite numbers")
    numbers = tuple(_finite_number(item, f"{label}[{index}]") for index, item in enumerate(value))
    if any(number <= 0.0 for number in numbers):
        raise AcceleratorGeometryError(f"{label} values must be positive")
    return numbers


def _ordered_z(upstream_z_cm: Any, downstream_z_cm: Any, label: str) -> tuple[float, float]:
    upstream = _finite_number(upstream_z_cm, f"{label}.upstream_z_cm")
    downstream = _finite_number(downstream_z_cm, f"{label}.downstream_z_cm")
    if upstream >= downstream:
        raise AcceleratorGeometryError(f"{label} z boundaries must be ordered")
    return upstream, downstream


def _finite_list(value: Any, label: str) -> tuple[float, ...]:
    if value is None:
        return ()
    if not isinstance(value, (tuple, list)):
        raise AcceleratorGeometryError(f"{label} must be a sequence of finite numbers")
    return tuple(_finite_number(item, f"{label}[{index}]") for index, item in enumerate(value))


@dataclass(frozen=True)
class SourceGeometry:
    model: SourceModel
    position_cm: tuple[float, float, float]
    beam_direction: tuple[float, float, float] | None = None
    finite_source_size_cm: tuple[float, ...] | None = None

    def __post_init__(self) -> None:
        if self.model not in {"point", "finite_rect"}:
            raise AcceleratorGeometryError("source model must be point or finite_rect")
        object.__setattr__(self, "position_cm", _finite_tuple(self.position_cm, "source.position_cm", 3))
        if self.beam_direction is not None:
            direction = _finite_tuple(self.beam_direction, "source.beam_direction", 3)
            if all(component == 0.0 for component in direction):
                raise AcceleratorGeometryError("source.beam_direction must not be a zero vector")
            object.__setattr__(self, "beam_direction", direction)
        object.__setattr__(
            self,
            "finite_source_size_cm",
            _optional_number_tuple(self.finite_source_size_cm, "source.finite_source_size_cm"),
        )


@dataclass(frozen=True)
class MlcGeometry:
    leaf_pair_count: int
    leaf_widths_cm: tuple[float, ...]
    upstream_z_cm: float
    downstream_z_cm: float
    leaf_depth_cm: float | None = None

    def __post_init__(self) -> None:
        if isinstance(self.leaf_pair_count, bool) or not isinstance(self.leaf_pair_count, int) or self.leaf_pair_count <= 0:
            raise AcceleratorGeometryError("mlc.leaf_pair_count must be a positive integer")
        widths = _finite_list(self.leaf_widths_cm, "mlc.leaf_widths_cm")
        if len(widths) != self.leaf_pair_count:
            raise AcceleratorGeometryError("mlc.leaf_widths_cm length must match leaf_pair_count")
        if any(width <= 0.0 for width in widths):
            raise AcceleratorGeometryError("mlc.leaf_widths_cm values must be positive")
        upstream, downstream = _ordered_z(self.upstream_z_cm, self.downstream_z_cm, "mlc")
        object.__setattr__(self, "leaf_widths_cm", widths)
        object.__setattr__(self, "upstream_z_cm", upstream)
        object.__setattr__(self, "downstream_z_cm", downstream)
        if self.leaf_depth_cm is not None:
            depth = _finite_number(self.leaf_depth_cm, "mlc.leaf_depth_cm")
            if depth <= 0.0:
                raise AcceleratorGeometryError("mlc.leaf_depth_cm must be positive")
            object.__setattr__(self, "leaf_depth_cm", depth)


@dataclass(frozen=True)
class MlcApertureState:
    state: MlcApertureKind
    bank_a_cm: tuple[float, ...] = ()
    bank_b_cm: tuple[float, ...] = ()

    def __post_init__(self) -> None:
        if self.state not in {"present", "fully_open_mlc", "no_mlc"}:
            raise AcceleratorGeometryError("mlc aperture state must be present, fully_open_mlc, or no_mlc")
        bank_a = _finite_list(self.bank_a_cm, "mlc_aperture.bank_a_cm")
        bank_b = _finite_list(self.bank_b_cm, "mlc_aperture.bank_b_cm")
        if self.state == "present" and (not bank_a or not bank_b):
            raise AcceleratorGeometryError("present MLC aperture requires bank_a_cm and bank_b_cm")
        if len(bank_a) != len(bank_b):
            raise AcceleratorGeometryError("MLC bank lengths must match")
        if self.state == "no_mlc" and (bank_a or bank_b):
            raise AcceleratorGeometryError("no_mlc aperture must not include bank positions")
        for index, (a_value, b_value) in enumerate(zip(bank_a, bank_b)):
            if a_value >= b_value:
                raise AcceleratorGeometryError(f"MLC bank_a_cm[{index}] must be less than bank_b_cm[{index}]")
        object.__setattr__(self, "bank_a_cm", bank_a)
        object.__setattr__(self, "bank_b_cm", bank_b)


@dataclass(frozen=True)
class YJawGeometry:
    upstream_z_cm: float
    downstream_z_cm: float

    def __post_init__(self) -> None:
        upstream, downstream = _ordered_z(self.upstream_z_cm, self.downstream_z_cm, "y_jaw")
        object.__setattr__(self, "upstream_z_cm", upstream)
        object.__setattr__(self, "downstream_z_cm", downstream)


@dataclass(frozen=True)
class YJawApertureState:
    state: YJawApertureKind
    y1_cm: float | None = None
    y2_cm: float | None = None

    def __post_init__(self) -> None:
        if self.state not in {"present", "absent"}:
            raise AcceleratorGeometryError("Y-Jaw aperture state must be present or absent")
        if self.state == "absent":
            if self.y1_cm is not None or self.y2_cm is not None:
                raise AcceleratorGeometryError("absent Y-Jaw aperture must not include y1_cm or y2_cm")
            return
        if self.y1_cm is None or self.y2_cm is None:
            raise AcceleratorGeometryError("present Y-Jaw aperture requires y1_cm and y2_cm")
        y1 = _finite_number(self.y1_cm, "y_jaw_aperture.y1_cm")
        y2 = _finite_number(self.y2_cm, "y_jaw_aperture.y2_cm")
        if y1 >= y2:
            raise AcceleratorGeometryError("y_jaw_aperture.y1_cm must be less than y2_cm")
        object.__setattr__(self, "y1_cm", y1)
        object.__setattr__(self, "y2_cm", y2)


@dataclass(frozen=True)
class AcceleratorGeometryDescriptor:
    source: SourceGeometry
    mlc_geometry: MlcGeometry | None = None
    mlc_aperture: MlcApertureState | None = None
    y_jaw_geometry: YJawGeometry | None = None
    y_jaw_aperture: YJawApertureState | None = None
    coordinate_system: str = COORDINATE_SYSTEM

    def __post_init__(self) -> None:
        if self.coordinate_system != COORDINATE_SYSTEM:
            raise AcceleratorGeometryError("coordinate_system must be phits_cm_isocenter")
        if not isinstance(self.source, SourceGeometry):
            raise AcceleratorGeometryError("source must be SourceGeometry")
        self._validate_mlc_contract()
        self._validate_y_jaw_contract()

    def _validate_mlc_contract(self) -> None:
        if self.mlc_geometry is not None and not isinstance(self.mlc_geometry, MlcGeometry):
            raise AcceleratorGeometryError("mlc_geometry must be MlcGeometry")
        if self.mlc_aperture is not None and not isinstance(self.mlc_aperture, MlcApertureState):
            raise AcceleratorGeometryError("mlc_aperture must be MlcApertureState")
        if self.mlc_aperture is None:
            return
        if self.mlc_aperture.state == "no_mlc":
            if self.mlc_geometry is not None:
                raise AcceleratorGeometryError("no_mlc aperture requires absent MLC geometry")
            return
        if self.mlc_geometry is None:
            raise AcceleratorGeometryError("MLC aperture requires MLC geometry")
        bank_count = len(self.mlc_aperture.bank_a_cm)
        if self.mlc_aperture.state == "present" and bank_count != self.mlc_geometry.leaf_pair_count:
            raise AcceleratorGeometryError("present MLC aperture bank lengths must match leaf_pair_count")
        if self.mlc_aperture.state == "fully_open_mlc" and bank_count not in {0, self.mlc_geometry.leaf_pair_count}:
            raise AcceleratorGeometryError("fully_open_mlc banks must be empty or match leaf_pair_count")

    def _validate_y_jaw_contract(self) -> None:
        if self.y_jaw_geometry is not None and not isinstance(self.y_jaw_geometry, YJawGeometry):
            raise AcceleratorGeometryError("y_jaw_geometry must be YJawGeometry")
        if self.y_jaw_aperture is not None and not isinstance(self.y_jaw_aperture, YJawApertureState):
            raise AcceleratorGeometryError("y_jaw_aperture must be YJawApertureState")
        if self.y_jaw_aperture is None:
            return
        if self.y_jaw_aperture.state == "present" and self.y_jaw_geometry is None:
            raise AcceleratorGeometryError("present Y-Jaw aperture requires Y-Jaw geometry")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
