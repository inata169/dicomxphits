from __future__ import annotations

import copy
import math
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import PurePosixPath
from typing import Any, Mapping

from dicomxphits.public_spectrum import PUBLIC_SPECTRUM_BIN_COUNT, PUBLIC_SPECTRUM_NAME, public_spectrum_lines


TRACE_PREFIX = "$ renderer-trace:"
SHIELDING_MATERIAL_ID = 1
TRANSPORT_VOID_MATERIAL = 0
VOID_CELL_MATERIAL = -1
WORLD_SURFACE_ID = 9000
BASE_TRANSPORT_CELL_ID = 3001
OUTSIDE_WORLD_CELL_ID = 9999
CELL_GEOMETRY_TOKENS_PER_LINE = 12
PUBLIC_SOURCE_CONE_PHITS_EXPRESSION = (
    "atan(sqrt(20**2+20**2)/2.0/100.0)*180.0/pi"
)


class RectangularPhitsRendererError(ValueError):
    """Raised when rectangular intermediate geometry cannot be rendered."""


def render_rectangular_phits_input(
    geometry: Mapping[str, Any],
    expected_output_path: str,
    *,
    maxcas: int = 1,
    maxbch: int = 1,
    epsout: float = 1,
    totfact_per_mu: str | Decimal | None = None,
    voxel_counts: tuple[int, int, int] | None = None,
    output_pdd_path: str | None = None,
) -> str:
    """Render a complete public CT-voxel rectangular PHITS input.

    Renderer-facing contract:

    - `geometry` is a mapping produced by the rectangular intermediate layer.
    - Geometry coordinates are already centimeters, angles are degrees, and
      densities are g/cm3.
    - `voxel_counts` must match the validated caller-supplied CT2PHITS assets.
    - The renderer is pure: it does not read DICOM, perform mm conversion,
      create files or directories, call private scripts, or mutate input.
    - The result uses the validated CT chassis, 101-cube dose grid, PDD tally,
      runtime gantry/collimator transforms, and optional approved dose factor.
    """

    params = _validate_params(
        maxcas=maxcas,
        maxbch=maxbch,
        epsout=epsout,
        totfact_per_mu=totfact_per_mu,
    )
    output_path = _validate_output_path(expected_output_path)
    if voxel_counts is None:
        raise RectangularPhitsRendererError(
            "voxel_counts from validated CT2PHITS assets are required"
        )
    pdd_path = (
        _validate_output_path(output_pdd_path)
        if output_pdd_path is not None
        else (PurePosixPath(output_path).parent / "deposit-pdd.out").as_posix()
    )
    from dicomxphits.prepare_ct_calibration import render_ct_runtime_input

    return render_ct_runtime_input(
        geometry,
        voxel_counts=voxel_counts,
        output_3d=output_path,
        output_pdd=pdd_path,
        totfact_per_mu=params.totfact_per_mu,
        maxcas_per_batch=params.maxcas,
        batches=params.maxbch,
        epsout=params.epsout,
    )


def render_rectangular_model_sections(
    geometry: Mapping[str, Any],
    *,
    totfact_per_mu: str | Decimal | None = None,
) -> str:
    """Render approved accelerator sections for composition into the CT chassis."""

    snapshot = copy.deepcopy(geometry)
    validated = _validate_geometry(geometry)
    normalized_totfact = _validate_totfact_per_mu(totfact_per_mu)
    model = _build_model(validated)
    _validate_model(model)
    lines = [
        "[ Source ]",
        *_source_lines(validated, totfact_per_mu=normalized_totfact),
        "",
        "[ Surface ]",
        *[f" {surface.surface_id} {surface.body}" for surface in model.surfaces],
        "",
        "[ Cell ]",
        *[line for cell in model.cells for line in _cell_lines(cell)],
        "",
        "[ Material ]",
        *_material_lines(validated, model.material_ids),
        "",
        "[ E N D ]",
    ]
    if geometry != snapshot:
        raise RectangularPhitsRendererError("renderer mutated input geometry")
    return "\n".join(lines) + "\n"


@dataclass(frozen=True)
class _Params:
    maxcas: int
    maxbch: int
    epsout: float
    totfact_per_mu: str | None


@dataclass(frozen=True)
class _Surface:
    surface_id: int
    body: str


@dataclass(frozen=True)
class _Cell:
    cell_id: int
    material_id: int | None
    material_name: str | None
    density: float | None
    surface_refs: tuple[int | str, ...]
    comment: str


@dataclass(frozen=True)
class _Model:
    surfaces: tuple[_Surface, ...]
    cells: tuple[_Cell, ...]
    material_ids: Mapping[str, int]


def _validate_params(
    *,
    maxcas: int,
    maxbch: int,
    epsout: Any,
    totfact_per_mu: str | Decimal | None,
) -> _Params:
    if isinstance(maxcas, bool) or not isinstance(maxcas, int) or maxcas <= 0:
        raise RectangularPhitsRendererError("maxcas must be a positive integer")
    if isinstance(maxbch, bool) or not isinstance(maxbch, int) or maxbch <= 0:
        raise RectangularPhitsRendererError("maxbch must be a positive integer")
    return _Params(
        maxcas=maxcas,
        maxbch=maxbch,
        epsout=_finite(epsout, "epsout"),
        totfact_per_mu=_validate_totfact_per_mu(totfact_per_mu),
    )


def _validate_totfact_per_mu(value: str | Decimal | None) -> str | None:
    if value is None:
        return None
    try:
        number = Decimal(str(value))
    except InvalidOperation as exc:
        raise RectangularPhitsRendererError(
            "totfact_per_mu must be a positive finite decimal"
        ) from exc
    if not number.is_finite() or number <= 0:
        raise RectangularPhitsRendererError(
            "totfact_per_mu must be a positive finite decimal"
        )
    return format(number, "E")


def _validate_output_path(value: str) -> str:
    if not isinstance(value, str) or not value:
        raise RectangularPhitsRendererError("expected_output_path must be a non-empty string")
    if "\n" in value or "\r" in value:
        raise RectangularPhitsRendererError("expected_output_path must not contain newlines")
    return str(PurePosixPath(value.replace("\\", "/")))


def _validate_geometry(geometry: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(geometry, Mapping):
        raise RectangularPhitsRendererError("geometry must be an object")
    data = copy.deepcopy(dict(geometry))
    if data.get("geometry_mode") != "rectangular_3dcrt":
        raise RectangularPhitsRendererError("geometry_mode must be rectangular_3dcrt")
    if data.get("renderer_ready_unit_marker") != "cm_deg_g_cm3":
        raise RectangularPhitsRendererError("renderer_ready_unit_marker must be cm_deg_g_cm3")
    units = _mapping(data.get("units"), "units")
    if units.get("geometry") != "cm" or units.get("angles") != "deg" or units.get("density") != "g/cm3":
        raise RectangularPhitsRendererError("units must be cm, deg, and g/cm3")
    _validate_jaws(data.get("jaw_positions_cm"))
    if data.get("y_diaphragm_positions_cm") is not None:
        _validate_jaws(data.get("y_diaphragm_positions_cm"))
    _validate_angles(data.get("angles_deg"))
    _validate_source(data.get("source"))
    _validate_z_component(data.get("y_diaphragm"), "y_diaphragm")
    _validate_mlc(data)
    _mapping(data.get("materials"), "materials")
    _validate_transport(data.get("transport"))
    return data


def _mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise RectangularPhitsRendererError(f"{label} must be an object")
    return value


def _finite(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise RectangularPhitsRendererError(f"{label} must be finite")
    number = float(value)
    if not math.isfinite(number):
        raise RectangularPhitsRendererError(f"{label} must be finite")
    return 0.0 if number == 0.0 else number


def _positive_finite(value: Any, label: str) -> float:
    number = _finite(value, label)
    if number <= 0.0:
        raise RectangularPhitsRendererError(f"{label} must be positive")
    return number


def _fmt(value: Any) -> str:
    number = _finite(value, "numeric value")
    if number == 0.0:
        number = 0.0
    text = f"{number:.12g}"
    return "0" if text in {"-0", "-0.0"} else text


def _validate_jaws(value: Any) -> None:
    jaws = _mapping(value, "jaw_positions_cm")
    x1 = _finite(jaws.get("x1"), "jaw_positions_cm.x1")
    x2 = _finite(jaws.get("x2"), "jaw_positions_cm.x2")
    y1 = _finite(jaws.get("y1"), "jaw_positions_cm.y1")
    y2 = _finite(jaws.get("y2"), "jaw_positions_cm.y2")
    if x1 >= x2 or y1 >= y2:
        raise RectangularPhitsRendererError("jaw aperture must be ordered")


def _validate_angles(value: Any) -> None:
    angles = _mapping(value, "angles_deg")
    for key in ("gantry", "collimator", "couch"):
        _finite(angles.get(key), f"angles_deg.{key}")


def _validate_source(value: Any) -> None:
    source = _mapping(value, "source")
    model = source.get("model")
    if model == "point":
        position = source.get("position_cm")
        if not isinstance(position, list) or len(position) != 3:
            raise RectangularPhitsRendererError("source.position_cm must contain three values")
        for index, item in enumerate(position):
            _finite(item, f"source.position_cm[{index}]")
        return
    if model == "rectangular_fwhm":
        _finite(source.get("plane_z_cm"), "source.plane_z_cm")
        _positive_finite(source.get("fwhm_x_cm"), "source.fwhm_x_cm")
        _positive_finite(source.get("fwhm_y_cm"), "source.fwhm_y_cm")
        return
    if model == "uniform_rectangular":
        _finite(source.get("plane_z_cm"), "source.plane_z_cm")
        _positive_finite(source.get("width_x_cm"), "source.width_x_cm")
        _positive_finite(source.get("width_y_cm"), "source.width_y_cm")
        return
    raise RectangularPhitsRendererError(
        "source.model must be point, rectangular_fwhm, or uniform_rectangular"
    )


def _validate_transport(value: Any) -> None:
    if value is None:
        return
    transport = _mapping(value, "transport")
    for key in (
        "photon_cutoff_mev",
        "electron_cutoff_mev",
        "positron_cutoff_mev",
    ):
        _positive_finite(transport.get(key), f"transport.{key}")


def _validate_z_component(value: Any, label: str) -> None:
    component = _mapping(value, label)
    upstream = _finite(component.get("upstream_z_cm"), f"{label}.upstream_z_cm")
    downstream = _finite(component.get("downstream_z_cm"), f"{label}.downstream_z_cm")
    if upstream >= downstream:
        raise RectangularPhitsRendererError(f"{label} z bounds must be ordered")
    if not isinstance(component.get("material"), str) or not component.get("material"):
        raise RectangularPhitsRendererError(f"{label}.material must be a non-empty string")


def _validate_mlc(data: Mapping[str, Any]) -> None:
    state = data.get("mlc_aperture_state")
    if state not in {"present", "fully_open_mlc", "no_mlc"}:
        raise RectangularPhitsRendererError("mlc_aperture_state must be present, fully_open_mlc, or no_mlc")
    positions = data.get("mlc_positions_cm")
    if positions in (None, {}):
        if state in {"no_mlc", "fully_open_mlc"}:
            return
        raise RectangularPhitsRendererError("mlc_positions_cm is required when MLC is present")
    if state == "no_mlc":
        raise RectangularPhitsRendererError("no_mlc geometry must not include MLC positions")
    mlc_geometry = _mapping(data.get("mlc_geometry"), "mlc_geometry")
    leaf_pair_count = mlc_geometry.get("leaf_pair_count")
    if isinstance(leaf_pair_count, bool) or not isinstance(leaf_pair_count, int) or leaf_pair_count < 1:
        raise RectangularPhitsRendererError("mlc_geometry.leaf_pair_count must be a positive integer")
    leaf_widths = mlc_geometry.get("leaf_widths_cm")
    if not isinstance(leaf_widths, list) or len(leaf_widths) != leaf_pair_count:
        raise RectangularPhitsRendererError("mlc_geometry.leaf_widths_cm length must match leaf_pair_count")
    for index, width in enumerate(leaf_widths):
        _positive_finite(width, f"mlc_geometry.leaf_widths_cm[{index}]")
    _positive_finite(mlc_geometry.get("leaf_depth_cm"), "mlc_geometry.leaf_depth_cm")
    _validate_z_component(mlc_geometry, "mlc_geometry")
    banks = _mapping(positions, "mlc_positions_cm")
    bank_a = banks.get("bank_a")
    bank_b = banks.get("bank_b")
    if not isinstance(bank_a, list) or not isinstance(bank_b, list):
        raise RectangularPhitsRendererError("mlc_positions_cm.bank_a and bank_b must be arrays")
    if len(bank_a) != leaf_pair_count or len(bank_b) != leaf_pair_count:
        raise RectangularPhitsRendererError("MLC bank lengths must match leaf_pair_count")
    for index, (a_value, b_value) in enumerate(zip(bank_a, bank_b)):
        a = _finite(a_value, f"mlc_positions_cm.bank_a[{index}]")
        b = _finite(b_value, f"mlc_positions_cm.bank_b[{index}]")
        if a >= b:
            raise RectangularPhitsRendererError(f"MLC bank pair {index} must be ordered")


def _build_model(geometry: Mapping[str, Any]) -> _Model:
    surfaces: list[_Surface] = [
        _Surface(WORLD_SURFACE_ID, "so 1000"),
        *_jaw_surfaces(geometry),
        *_mlc_surfaces(geometry),
    ]
    material_ids = {str(geometry["y_diaphragm"]["material"]): SHIELDING_MATERIAL_ID}
    mlc_geometry = geometry.get("mlc_geometry") or {}
    if _has_mlc_cells(geometry):
        material_ids.setdefault(str(mlc_geometry["material"]), len(material_ids) + 1)
    shield_cells = [
        *_jaw_cells(geometry, material_ids),
        *_mlc_cells(geometry, material_ids),
    ]
    cells = [
        *shield_cells,
        _base_transport_cell(shield_cells),
        _Cell(OUTSIDE_WORLD_CELL_ID, None, None, None, (WORLD_SURFACE_ID,), "outside world void"),
    ]
    return _Model(tuple(surfaces), tuple(cells), material_ids)


def _jaw_surfaces(geometry: Mapping[str, Any]) -> tuple[_Surface, _Surface]:
    jaws = geometry.get("y_diaphragm_positions_cm") or geometry["jaw_positions_cm"]
    y_diaphragm = geometry["y_diaphragm"]
    extent = max(abs(float(jaws["x1"])), abs(float(jaws["x2"])), abs(float(jaws["y1"])), abs(float(jaws["y2"]))) + 10.0
    x_min = -extent
    x_max = extent
    return (
        _Surface(
            1101,
            "rpp "
            f"{_fmt(x_min)} {_fmt(x_max)} {_fmt(-extent)} {_fmt(jaws['y1'])} "
            f"{_fmt(y_diaphragm['upstream_z_cm'])} {_fmt(y_diaphragm['downstream_z_cm'])}",
        ),
        _Surface(
            1102,
            "rpp "
            f"{_fmt(x_min)} {_fmt(x_max)} {_fmt(jaws['y2'])} {_fmt(extent)} "
            f"{_fmt(y_diaphragm['upstream_z_cm'])} {_fmt(y_diaphragm['downstream_z_cm'])}",
        ),
    )


def _has_mlc_cells(geometry: Mapping[str, Any]) -> bool:
    return geometry.get("mlc_positions_cm") not in (None, {})


def _mlc_surfaces(geometry: Mapping[str, Any]) -> tuple[_Surface, ...]:
    if not _has_mlc_cells(geometry):
        return ()
    positions = geometry["mlc_positions_cm"]
    mlc = geometry["mlc_geometry"]
    y_edges = _leaf_y_edges(mlc["leaf_widths_cm"])
    surfaces: list[_Surface] = []
    for index, (a_value, b_value) in enumerate(zip(positions["bank_a"], positions["bank_b"])):
        y_min, y_max = y_edges[index]
        depth = mlc["leaf_depth_cm"]
        z_min = mlc["upstream_z_cm"]
        z_max = mlc["downstream_z_cm"]
        surfaces.append(
            _Surface(
                2001 + index * 2,
                "rpp "
                f"{_fmt(float(a_value) - depth)} {_fmt(a_value)} {_fmt(y_min)} {_fmt(y_max)} "
                f"{_fmt(z_min)} {_fmt(z_max)}",
            )
        )
        surfaces.append(
            _Surface(
                2002 + index * 2,
                "rpp "
                f"{_fmt(b_value)} {_fmt(float(b_value) + depth)} {_fmt(y_min)} {_fmt(y_max)} "
                f"{_fmt(z_min)} {_fmt(z_max)}",
            )
        )
    return tuple(surfaces)


def _leaf_y_edges(widths: list[float]) -> list[tuple[float, float]]:
    total = sum(float(width) for width in widths)
    cursor = -total / 2.0
    edges = []
    for width in widths:
        next_cursor = cursor + float(width)
        edges.append((cursor, next_cursor))
        cursor = next_cursor
    return edges


def _jaw_cells(geometry: Mapping[str, Any], material_ids: Mapping[str, int]) -> tuple[_Cell, _Cell]:
    material = str(geometry["y_diaphragm"]["material"])
    density = _material_density(geometry, material)
    return (
        _Cell(3101, material_ids[material], material, density, (-1101,), "lower Y-Diaphragm shield"),
        _Cell(3102, material_ids[material], material, density, (-1102,), "upper Y-Diaphragm shield"),
    )


def _mlc_cells(geometry: Mapping[str, Any], material_ids: Mapping[str, int]) -> tuple[_Cell, ...]:
    if not _has_mlc_cells(geometry):
        return ()
    material = str(geometry["mlc_geometry"]["material"])
    density = _material_density(geometry, material)
    cells: list[_Cell] = []
    for index in range(int(geometry["mlc_geometry"]["leaf_pair_count"])):
        cells.append(_Cell(4101 + index * 2, material_ids[material], material, density, (-(2001 + index * 2),), f"MLC bank A leaf pair {index}"))
        cells.append(_Cell(4102 + index * 2, material_ids[material], material, density, (-(2002 + index * 2),), f"MLC bank B leaf pair {index}"))
    return tuple(cells)


def _base_transport_cell(shield_cells: list[_Cell]) -> _Cell:
    shield_exclusions = tuple(f"#{cell.cell_id}" for cell in shield_cells)
    return _Cell(
        BASE_TRANSPORT_CELL_ID,
        TRANSPORT_VOID_MATERIAL,
        None,
        None,
        (-WORLD_SURFACE_ID, *shield_exclusions),
        "inside world transport void excluding generated shields",
    )


def _material_density(geometry: Mapping[str, Any], material_name: str) -> float:
    materials = _mapping(geometry.get("materials"), "materials")
    material = _mapping(materials.get(material_name), f"materials.{material_name}")
    return _positive_finite(material.get("density_g_cm3"), f"materials.{material_name}.density_g_cm3")


def _validate_model(model: _Model) -> None:
    _unique([surface.surface_id for surface in model.surfaces], "surface IDs")
    cell_id_list = [cell.cell_id for cell in model.cells]
    _unique(cell_id_list, "cell IDs")
    cell_ids = set(cell_id_list)
    _unique(model.material_ids.values(), "material IDs")
    surface_ids = {surface.surface_id for surface in model.surfaces}
    material_ids = set(model.material_ids.values())
    for cell in model.cells:
        for ref in cell.surface_refs:
            if isinstance(ref, int):
                if abs(ref) not in surface_ids:
                    raise RectangularPhitsRendererError(f"cell {cell.cell_id} references undefined surface {abs(ref)}")
                continue
            if isinstance(ref, str) and ref.startswith("#") and ref[1:].isdigit():
                referenced_cell_id = int(ref[1:])
                if referenced_cell_id == cell.cell_id:
                    raise RectangularPhitsRendererError(f"cell {cell.cell_id} must not complement itself")
                if referenced_cell_id not in cell_ids:
                    raise RectangularPhitsRendererError(
                        f"cell {cell.cell_id} references undefined complement cell {referenced_cell_id}"
                    )
                continue
            raise RectangularPhitsRendererError(f"cell {cell.cell_id} has invalid geometry reference {ref!r}")
        if cell.material_id is not None and cell.material_id > 0 and cell.material_id not in material_ids:
            raise RectangularPhitsRendererError(f"cell {cell.cell_id} references undefined material {cell.material_id}")


def _unique(values: Any, label: str) -> None:
    items = list(values)
    if len(items) != len(set(items)):
        raise RectangularPhitsRendererError(f"{label} must be unique")


def _source_lines(
    geometry: Mapping[str, Any],
    *,
    totfact_per_mu: str | None = None,
) -> list[str]:
    source = geometry["source"]
    lines = [
        " s-type = 5",
        " proj = photon",
    ]
    if source["model"] == "point":
        x, y, z = source["position_cm"]
        lines.extend(
            [
                f" x0 = {_fmt(x)}",
                f" x1 = {_fmt(x)}",
                f" y0 = {_fmt(y)}",
                f" y1 = {_fmt(y)}",
                f" z0 = {_fmt(z)}",
                f" z1 = {_fmt(z)}",
            ]
        )
    elif source["model"] == "uniform_rectangular":
        half_width_x = float(source["width_x_cm"]) / 2.0
        half_width_y = float(source["width_y_cm"]) / 2.0
        lines.extend(
            [
                f"{TRACE_PREFIX} source_model = uniform_rectangular",
                f"{TRACE_PREFIX} source_plane_z_cm = {_fmt(source['plane_z_cm'])}",
                f"{TRACE_PREFIX} source_width_x_cm = {_fmt(source['width_x_cm'])}",
                f"{TRACE_PREFIX} source_width_y_cm = {_fmt(source['width_y_cm'])}",
                f" x0 = {_fmt(-half_width_x)}",
                f" x1 = {_fmt(half_width_x)}",
                f" y0 = {_fmt(-half_width_y)}",
                f" y1 = {_fmt(half_width_y)}",
                f" z0 = {_fmt(source['plane_z_cm'])}",
                f" z1 = {_fmt(source['plane_z_cm'])}",
            ]
        )
    else:
        lines.extend(
            [
                f"{TRACE_PREFIX} source_model = rectangular_fwhm",
                f"{TRACE_PREFIX} source_plane_z_cm = {_fmt(source['plane_z_cm'])}",
                f"{TRACE_PREFIX} source_fwhm_x_cm = {_fmt(source['fwhm_x_cm'])}",
                f"{TRACE_PREFIX} source_fwhm_y_cm = {_fmt(source['fwhm_y_cm'])}",
                f" x0 = 0",
                f" x1 = 0",
                f" y0 = 0",
                f" y1 = 0",
                f" z0 = {_fmt(source['plane_z_cm'])}",
                f" z1 = {_fmt(source['plane_z_cm'])}",
            ]
        )
    lines.extend(
        [
            " dir = 1",
            " phi = 0",
            f" dom = {PUBLIC_SOURCE_CONE_PHITS_EXPRESSION}",
            *(
                [f" totfact = {totfact_per_mu}"]
                if totfact_per_mu is not None
                else []
            ),
            " e-type = 1",
            f" ne = {PUBLIC_SPECTRUM_BIN_COUNT}",
            *public_spectrum_lines(),
        ]
    )
    return lines


def _transport_lines(geometry: Mapping[str, Any]) -> list[str]:
    transport = geometry.get("transport") or {
        "photon_cutoff_mev": 0.01,
        "electron_cutoff_mev": 0.7,
        "positron_cutoff_mev": 0.7,
    }
    return [
        f" emin(2) = {_fmt(transport['photon_cutoff_mev'])}",
        f" emin(12) = {_fmt(transport['electron_cutoff_mev'])}",
        f" emin(13) = {_fmt(transport['positron_cutoff_mev'])}",
        f" emin(14) = {_fmt(transport['photon_cutoff_mev'])}",
        " igamma = 2",
        " ipnint = 0",
        " negs = 1",
    ]


def _cell_prefix(cell: _Cell) -> str:
    if cell.material_id is None:
        return f" {cell.cell_id} {VOID_CELL_MATERIAL}"
    if cell.material_id == TRANSPORT_VOID_MATERIAL:
        return f" {cell.cell_id} {TRANSPORT_VOID_MATERIAL}"
    return f" {cell.cell_id} {cell.material_id} -{_fmt(cell.density)}"


def _chunked_refs(surface_refs: tuple[int | str, ...]) -> list[tuple[int | str, ...]]:
    return [
        surface_refs[index : index + CELL_GEOMETRY_TOKENS_PER_LINE]
        for index in range(0, len(surface_refs), CELL_GEOMETRY_TOKENS_PER_LINE)
    ]


def _cell_lines(cell: _Cell) -> list[str]:
    chunks = _chunked_refs(cell.surface_refs)
    lines: list[str] = []
    for index, refs in enumerate(chunks):
        refs_text = " ".join(str(ref) for ref in refs)
        prefix = _cell_prefix(cell) if index == 0 else "     "
        suffix = f" $ {cell.comment}" if index == len(chunks) - 1 else ""
        lines.append(f"{prefix} {refs_text}{suffix}")
    return lines


def _material_lines(geometry: Mapping[str, Any], material_ids: Mapping[str, int]) -> list[str]:
    materials = _mapping(geometry["materials"], "materials")
    lines: list[str] = []
    for material_name in sorted(material_ids, key=lambda name: material_ids[name]):
        material = _mapping(materials.get(material_name), f"materials.{material_name}")
        block = material.get("material_block")
        if not isinstance(block, str) or not block.strip():
            raise RectangularPhitsRendererError(f"materials.{material_name}.material_block is required")
        _validate_material_block(block, material_name)
        lines.append(f" MAT[{material_ids[material_name]}] $ {material_name}")
        lines.extend(f" {line}" if line.strip() else "" for line in block.splitlines())
    return lines


def _validate_material_block(block: str, material_name: str) -> None:
    for line in block.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("[") or "[ E N D ]" in stripped:
            raise RectangularPhitsRendererError(f"materials.{material_name}.material_block contains section injection")
