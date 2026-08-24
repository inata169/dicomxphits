from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass
from decimal import Decimal, localcontext
from fractions import Fraction
from pathlib import Path
from typing import Any, Mapping, Sequence

from dicomxphits.rtdose_geometry import (
    GEOMETRY_TOLERANCE_MM,
    derive_rtdose_placement,
    tally_mesh_geometry_sha256,
)


SCHEMA_VERSION = "dicomxphits_public_calculation_config_v1"
EVIDENCE_SCHEMA_VERSION = "dicomxphits_public_calculation_geometry_v1"
MAX_CONFIG_BYTES = 65_536
MAX_NUMERIC_TOKEN_CHARACTERS = 64
MAX_CANONICAL_CHARACTERS = 64
MAX_AXIS_BINS = 1_000
MAX_TOTAL_VOXELS = 10_000_000
MAX_DICOM_DS_CHARACTERS = 16
DECIMAL_WORKING_PRECISION = MAX_CANONICAL_CHARACTERS * 4
AXES = ("x", "y", "z")
ROOT_KEYS = {"$schema", "schema_version", "dose_tally_3d"}
DOSE_TALLY_KEYS = {"center_min_mm", "center_max_mm", "voxel_size_mm"}
_JSON_NUMBER = re.compile(
    r"-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?"
)


class CalculationConfigError(ValueError):
    """Raised when a calculation configuration fails closed validation."""


@dataclass(frozen=True)
class NormalizedCalculationConfig:
    source: str
    source_sha256: str | None
    center_min_mm: tuple[Decimal, Decimal, Decimal]
    center_max_mm: tuple[Decimal, Decimal, Decimal]
    voxel_size_mm: tuple[Decimal, Decimal, Decimal]
    counts: tuple[int, int, int]
    edge_min_cm: tuple[Decimal, Decimal, Decimal]
    edge_max_cm: tuple[Decimal, Decimal, Decimal]
    semantic_sha256: str

    def semantic_payload(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "center_min_mm": [_canonical_decimal(value) for value in self.center_min_mm],
            "center_max_mm": [_canonical_decimal(value) for value in self.center_max_mm],
            "voxel_size_mm": [_canonical_decimal(value) for value in self.voxel_size_mm],
            "counts": list(self.counts),
            "edge_min_cm": [_canonical_decimal(value) for value in self.edge_min_cm],
            "edge_max_cm": [_canonical_decimal(value) for value in self.edge_max_cm],
        }

    def renderer_mesh(self) -> dict[str, Any]:
        return {
            "axes": {
                axis: {
                    "minimum_cm": _canonical_decimal(self.edge_min_cm[index]),
                    "maximum_cm": _canonical_decimal(self.edge_max_cm[index]),
                    "bin_count": self.counts[index],
                    "voxel_size_mm": _canonical_decimal(self.voxel_size_mm[index]),
                }
                for index, axis in enumerate(AXES)
            }
        }

    def tally_geometry(self) -> dict[str, Any]:
        return {
            "axes": {
                axis: {
                    "minimum_cm": float(self.edge_min_cm[index]),
                    "maximum_cm": float(self.edge_max_cm[index]),
                    "bin_count": self.counts[index],
                }
                for index, axis in enumerate(AXES)
            }
        }

    def tally_geometry_sha256(self) -> str:
        return tally_mesh_geometry_sha256(self.tally_geometry())

    def evidence(
        self,
        *,
        rtdose_preflight: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        result = {
            "schema_version": EVIDENCE_SCHEMA_VERSION,
            "source": self.source,
            "source_sha256": self.source_sha256,
            "decimal_encoding": "canonical_plain_decimal_strings",
            "semantic_sha256": self.semantic_sha256,
            "tally_geometry_sha256": self.tally_geometry_sha256(),
            "dose_tally_3d": self.semantic_payload(),
        }
        if rtdose_preflight is not None:
            result["rtdose_serialization_preflight"] = dict(rtdose_preflight)
        return result


def public_default_calculation_config() -> NormalizedCalculationConfig:
    return _normalize_calculation_config(
        {
            "schema_version": SCHEMA_VERSION,
            "dose_tally_3d": {
                "center_min_mm": [Decimal("-150"), Decimal("-150"), Decimal("-100")],
                "center_max_mm": [Decimal("150"), Decimal("150"), Decimal("200")],
                "voxel_size_mm": [Decimal("3"), Decimal("3"), Decimal("3")],
            },
        },
        source="built_in_legacy_default",
        source_sha256=None,
    )


def load_calculation_config(path: str | Path) -> NormalizedCalculationConfig:
    source_path = Path(path)
    try:
        with source_path.open("rb") as stream:
            raw = stream.read(MAX_CONFIG_BYTES + 1)
    except OSError as exc:
        raise CalculationConfigError(
            f"calculation config is unreadable: {source_path}"
        ) from exc
    if len(raw) > MAX_CONFIG_BYTES:
        raise CalculationConfigError(
            f"calculation config exceeds {MAX_CONFIG_BYTES} bytes"
        )
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise CalculationConfigError("calculation config must be UTF-8 JSON") from exc

    for token in _numeric_tokens(text):
        if len(token) > MAX_NUMERIC_TOKEN_CHARACTERS:
            raise CalculationConfigError(
                "calculation config numeric token exceeds 64 ASCII characters"
            )
        if _lexical_plain_length(token) > MAX_CANONICAL_CHARACTERS:
            raise CalculationConfigError(
                "calculation config number exceeds the 64-character canonical limit"
            )
    try:
        data = json.loads(
            text,
            parse_float=Decimal,
            parse_int=Decimal,
            parse_constant=_reject_json_constant,
            object_pairs_hook=_unique_object,
        )
    except (json.JSONDecodeError, CalculationConfigError) as exc:
        if isinstance(exc, CalculationConfigError):
            raise
        raise CalculationConfigError("calculation config is malformed JSON") from exc
    return _normalize_calculation_config(
        data,
        source="user_supplied",
        source_sha256=hashlib.sha256(raw).hexdigest(),
    )


def validate_rtdose_serialization_preflight(
    config: NormalizedCalculationConfig,
    *,
    rtplan_isocenter_dicom_mm: Sequence[float],
) -> dict[str, Any]:
    placement = derive_rtdose_placement(
        config.tally_geometry(),
        rtplan_isocenter_dicom_mm=rtplan_isocenter_dicom_mm,
    )
    serialized: dict[str, list[str]] = {}
    for field, key in (
        ("PixelSpacing", "pixel_spacing_mm"),
        ("GridFrameOffsetVector", "grid_frame_offset_vector_mm"),
        ("ImagePositionPatient", "image_position_patient_mm"),
    ):
        values = [float(value) for value in placement[key]]
        tokens = [f"{value:.10f}" for value in values]
        for token in tokens:
            if len(token) > MAX_DICOM_DS_CHARACTERS:
                raise CalculationConfigError(
                    f"{field} is not representable as a 16-character DICOM Decimal String"
                )
            reparsed = float(token)
            if not math.isfinite(reparsed):
                raise CalculationConfigError(
                    f"{field} does not reparse as finite DICOM geometry"
                )
        if any(
            abs(float(token) - expected) > GEOMETRY_TOLERANCE_MM
            for token, expected in zip(tokens, values)
        ):
            raise CalculationConfigError(
                f"{field} fixed-decimal round-trip exceeds the existing geometry tolerance"
            )
        serialized[field] = tokens

    pixel_spacing = [Decimal(token) for token in serialized["PixelSpacing"]]
    if any(value <= 0 for value in pixel_spacing):
        raise CalculationConfigError(
            "PixelSpacing must remain positive after DICOM serialization"
        )
    offsets = [Decimal(token) for token in serialized["GridFrameOffsetVector"]]
    if any(current <= previous for previous, current in zip(offsets, offsets[1:])):
        raise CalculationConfigError(
            "GridFrameOffsetVector must remain strictly increasing after DICOM serialization"
        )

    isocenter = tuple(Decimal(str(value)) for value in rtplan_isocenter_dicom_mm)
    if len(isocenter) != 3 or any(not value.is_finite() for value in isocenter):
        raise CalculationConfigError("RT Plan isocenter must contain three finite values")
    ipp = [Decimal(token) for token in serialized["ImagePositionPatient"]]
    exact_centres = [
        [
            config.center_min_mm[axis] + config.voxel_size_mm[axis] * index
            for index in range(config.counts[axis])
        ]
        for axis in range(3)
    ]
    maximum_residual = Decimal(0)

    for column in range(config.counts[0]):
        actual = ipp[0] + pixel_spacing[1] * column
        expected = isocenter[0] - exact_centres[0][config.counts[0] - 1 - column]
        maximum_residual = max(maximum_residual, abs(actual - expected))
    for row in range(config.counts[2]):
        actual = ipp[1] + pixel_spacing[0] * row
        expected = isocenter[1] + exact_centres[2][row]
        maximum_residual = max(maximum_residual, abs(actual - expected))
    for frame in range(config.counts[1]):
        actual = ipp[2] + offsets[frame]
        expected = isocenter[2] + exact_centres[1][frame]
        maximum_residual = max(maximum_residual, abs(actual - expected))

    tolerance = Decimal(str(GEOMETRY_TOLERANCE_MM))
    if maximum_residual > tolerance:
        raise CalculationConfigError(
            "predicted RTDOSE voxel-position residual exceeds 1e-6 mm"
        )
    return {
        "status": "passed",
        "serialization": "fixed_decimal_10_places",
        "dicom_ds_max_characters": MAX_DICOM_DS_CHARACTERS,
        "checked_axis_position_count": sum(config.counts),
        "maximum_absolute_component_residual_mm": float(maximum_residual),
        "absolute_tolerance_mm": GEOMETRY_TOLERANCE_MM,
    }


def require_rendered_3d_mesh(
    text: str,
    config: NormalizedCalculationConfig,
) -> None:
    try:
        block = text.split("[ T-Deposit ]\n", 1)[1].split("\n[ T-Deposit ]", 1)[0]
    except IndexError as exc:
        raise CalculationConfigError("generated input is missing the active 3D tally") from exc
    assignments: dict[str, str] = {}
    for line in block.splitlines():
        match = re.match(r"\s*(xmin|xmax|nx|ymin|ymax|ny|zmin|zmax|nz)\s*=\s*(\S+)", line)
        if match is not None:
            assignments[match.group(1)] = match.group(2)
    expected: dict[str, str] = {}
    mesh = config.renderer_mesh()["axes"]
    for axis in AXES:
        expected[f"{axis}min"] = str(mesh[axis]["minimum_cm"])
        expected[f"{axis}max"] = str(mesh[axis]["maximum_cm"])
        expected[f"n{axis}"] = str(mesh[axis]["bin_count"])
    if assignments != expected:
        raise CalculationConfigError(
            "generated active segment does not contain the normalized 3D tally mesh"
        )


def _normalize_calculation_config(
    data: Any,
    *,
    source: str,
    source_sha256: str | None,
) -> NormalizedCalculationConfig:
    root = _mapping(data, "calculation config")
    _reject_extra_keys(root, ROOT_KEYS, "calculation config")
    if root.get("schema_version") != SCHEMA_VERSION:
        raise CalculationConfigError(f"schema_version must be {SCHEMA_VERSION}")
    if "$schema" in root and not isinstance(root["$schema"], str):
        raise CalculationConfigError("$schema must be a string when present")
    tally = _mapping(root.get("dose_tally_3d"), "dose_tally_3d")
    _reject_extra_keys(tally, DOSE_TALLY_KEYS, "dose_tally_3d")
    center_min = _decimal_vector(tally.get("center_min_mm"), "center_min_mm")
    center_max = _decimal_vector(tally.get("center_max_mm"), "center_max_mm")
    voxel_size = _decimal_vector(tally.get("voxel_size_mm"), "voxel_size_mm")

    counts: list[int] = []
    edge_min: list[Decimal] = []
    edge_max: list[Decimal] = []
    total = 1
    for index, axis in enumerate(AXES):
        minimum = center_min[index]
        maximum = center_max[index]
        spacing = voxel_size[index]
        if minimum >= maximum:
            raise CalculationConfigError(
                f"center_min_mm[{index}] must be less than center_max_mm[{index}]"
            )
        if spacing <= 0:
            raise CalculationConfigError(f"voxel_size_mm[{index}] must be positive")
        minimum_fraction = Fraction(minimum)
        maximum_fraction = Fraction(maximum)
        spacing_fraction = Fraction(spacing)
        quotient = (maximum_fraction - minimum_fraction) / spacing_fraction
        if quotient.denominator != 1:
            raise CalculationConfigError(
                f"{axis} centre span must be an exact multiple of voxel size"
            )
        count = quotient.numerator + 1
        if count <= 0 or count > MAX_AXIS_BINS:
            raise CalculationConfigError(
                f"{axis} derived bin count must not exceed {MAX_AXIS_BINS}"
            )
        if total > MAX_TOTAL_VOXELS // count:
            raise CalculationConfigError(
                f"derived mesh must not exceed {MAX_TOTAL_VOXELS} total voxels"
            )
        total *= count
        lower = _decimal_from_fraction(
            (minimum_fraction - spacing_fraction / 2) / 10
        )
        upper = _decimal_from_fraction(
            (maximum_fraction + spacing_fraction / 2) / 10
        )
        spacing_cm = _decimal_from_fraction(spacing_fraction / 10)
        for value, label in (
            (lower, f"{axis} lower PHITS edge"),
            (upper, f"{axis} upper PHITS edge"),
            (spacing_cm, f"{axis} PHITS spacing"),
        ):
            _ensure_canonical_limit(value, label)
        lower_float = float(lower)
        upper_float = float(upper)
        spacing_float = (upper_float - lower_float) / count
        if (
            not math.isfinite(lower_float)
            or not math.isfinite(upper_float)
            or not math.isfinite(spacing_float)
            or upper_float <= lower_float
            or spacing_float <= 0.0
            or not math.isfinite(float(spacing_cm))
            or float(spacing_cm) <= 0.0
        ):
            raise CalculationConfigError(
                f"{axis} derived geometry is incompatible with downstream binary64"
            )
        counts.append(count)
        edge_min.append(lower)
        edge_max.append(upper)

    payload = {
        "schema_version": SCHEMA_VERSION,
        "center_min_mm": [_canonical_decimal(value) for value in center_min],
        "center_max_mm": [_canonical_decimal(value) for value in center_max],
        "voxel_size_mm": [_canonical_decimal(value) for value in voxel_size],
        "counts": counts,
        "edge_min_cm": [_canonical_decimal(value) for value in edge_min],
        "edge_max_cm": [_canonical_decimal(value) for value in edge_max],
    }
    semantic = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("ascii")
    return NormalizedCalculationConfig(
        source=source,
        source_sha256=source_sha256,
        center_min_mm=center_min,
        center_max_mm=center_max,
        voxel_size_mm=voxel_size,
        counts=tuple(counts),  # type: ignore[arg-type]
        edge_min_cm=tuple(edge_min),  # type: ignore[arg-type]
        edge_max_cm=tuple(edge_max),  # type: ignore[arg-type]
        semantic_sha256=hashlib.sha256(semantic).hexdigest(),
    )


def _mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise CalculationConfigError(f"{label} must be a JSON object")
    return value


def _decimal_from_fraction(value: Fraction) -> Decimal:
    with localcontext() as context:
        context.prec = DECIMAL_WORKING_PRECISION
        result = Decimal(value.numerator) / Decimal(value.denominator)
    if Fraction(result) != value:
        raise CalculationConfigError(
            "derived value exceeds bounded exact-decimal working precision"
        )
    return result


def _reject_extra_keys(value: Mapping[str, Any], allowed: set[str], label: str) -> None:
    extras = sorted(str(key) for key in value if key not in allowed)
    if extras:
        raise CalculationConfigError(
            f"{label} has unsupported field(s): {', '.join(extras)}"
        )


def _decimal_vector(
    value: Any,
    label: str,
) -> tuple[Decimal, Decimal, Decimal]:
    if not isinstance(value, list) or len(value) != 3:
        raise CalculationConfigError(f"{label} must contain exactly three JSON numbers")
    result: list[Decimal] = []
    for index, item in enumerate(value):
        if isinstance(item, bool) or not isinstance(item, Decimal):
            raise CalculationConfigError(f"{label}[{index}] must be a JSON number")
        if not item.is_finite():
            raise CalculationConfigError(f"{label}[{index}] must be finite")
        _ensure_canonical_limit(item, f"{label}[{index}]")
        result.append(Decimal(0) if item.is_zero() else item)
    return tuple(result)  # type: ignore[return-value]


def _numeric_tokens(text: str) -> list[str]:
    tokens: list[str] = []
    index = 0
    while index < len(text):
        if text[index] == '"':
            index += 1
            while index < len(text):
                if text[index] == "\\":
                    index += 2
                elif text[index] == '"':
                    index += 1
                    break
                else:
                    index += 1
            continue
        if text[index] == "-" or text[index].isdigit():
            match = _JSON_NUMBER.match(text, index)
            if match is not None:
                tokens.append(match.group(0))
                index = match.end()
                continue
        index += 1
    return tokens


def _lexical_plain_length(token: str) -> int:
    sign = 1 if token.startswith("-") else 0
    unsigned = token[1:] if sign else token
    mantissa, exponent_text = re.split(r"[eE]", unsigned, maxsplit=1) if re.search(r"[eE]", unsigned) else (unsigned, "0")
    integer, fraction = mantissa.split(".", 1) if "." in mantissa else (mantissa, "")
    digits = (integer + fraction).lstrip("0")
    if not digits:
        return 1
    exponent = int(exponent_text) - len(fraction)
    trailing = len(digits) - len(digits.rstrip("0"))
    if trailing:
        digits = digits[:-trailing]
        exponent += trailing
    return sign + _plain_length(len(digits), exponent)


def _plain_length(digit_count: int, exponent: int) -> int:
    point = digit_count + exponent
    if exponent >= 0:
        return point
    if point > 0:
        return digit_count + 1
    return 2 + (-point) + digit_count


def _canonical_parts(value: Decimal) -> tuple[str, int, bool]:
    if value.is_zero():
        return "0", 0, False
    item = value.as_tuple()
    digits = "".join(str(digit) for digit in item.digits).lstrip("0") or "0"
    exponent = item.exponent
    trailing = len(digits) - len(digits.rstrip("0"))
    if trailing:
        digits = digits[:-trailing]
        exponent += trailing
    return digits, exponent, bool(item.sign)


def _decimal_plain_length(value: Decimal) -> int:
    digits, exponent, negative = _canonical_parts(value)
    if digits == "0":
        return 1
    return (1 if negative else 0) + _plain_length(len(digits), exponent)


def _ensure_canonical_limit(value: Decimal, label: str) -> None:
    if _decimal_plain_length(value) > MAX_CANONICAL_CHARACTERS:
        raise CalculationConfigError(
            f"{label} exceeds the 64-character canonical plain-decimal limit"
        )


def _canonical_decimal(value: Decimal) -> str:
    _ensure_canonical_limit(value, "decimal value")
    digits, exponent, negative = _canonical_parts(value)
    if digits == "0":
        return "0"
    point = len(digits) + exponent
    if exponent >= 0:
        body = digits + "0" * exponent
    elif point > 0:
        body = digits[:point] + "." + digits[point:]
    else:
        body = "0." + "0" * (-point) + digits
    return ("-" if negative else "") + body


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise CalculationConfigError(f"calculation config duplicates field {key!r}")
        result[key] = value
    return result


def _reject_json_constant(value: str) -> Any:
    raise CalculationConfigError(f"calculation config rejects non-finite value {value}")
