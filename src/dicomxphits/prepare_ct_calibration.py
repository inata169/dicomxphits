from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from dicomxphits.machine_config import public_default_machine_config
from dicomxphits.public_spectrum import (
    PUBLIC_SPECTRUM_NAME,
    PUBLIC_SPECTRUM_SHA256,
    PUBLIC_SPECTRUM_TEXT,
    public_spectrum_lines,
)
from dicomxphits.rectangular_geometry import build_intermediate_geometry
from dicomxphits.rectangular_phits_renderer import render_rectangular_model_sections


SCHEMA_VERSION = "dicomxphits_public_ct_calibration_v1"
DEFAULT_FIELD_SIZES_CM = (10, 3, 5, 20)
DEFAULT_BATCH_ALLOCATION = (64, 64, 64)
MAXCAS_PER_BATCH = 20_000_000
MIN_ACCEPTED_BATCHES = 64
MIN_ACCEPTED_HISTORIES = 1_280_000_000
DEFAULT_OMP_THREADS = 8
DOSE_GRID_COUNT = 101
DOSE_GRID_SPACING_CM = 0.3
DOSE_GRID_MIN_CM = -10.15
DOSE_GRID_MAX_CM = 20.15
DOSE_GRID_TRANSVERSE_MIN_CM = -15.15
DOSE_GRID_TRANSVERSE_MAX_CM = 15.15
PDD_TRANSVERSE_MIN_CM = -0.15
PDD_TRANSVERSE_MAX_CM = 0.15
REFERENCE_DEPTH_CM = 10.0

CT_ASSET_NAMES = (
    "CTusrparam.dat",
    "CTtrans.inp",
    "CTsurf.dat",
    "CTmaterial.dat",
    "CTuniverse.inp",
    "CTvoxel.inp",
)

REPLICA_SPECS = (
    ("pc_a", -1000),
    ("pc_b", -2000),
    ("pc_c", -3000),
)


class CtCalibrationError(ValueError):
    """Raised when a public CT calibration package cannot be prepared safely."""


@dataclass(frozen=True)
class CtAssetSet:
    root: Path
    files: Mapping[str, Path]
    sha256: Mapping[str, str]
    voxel_counts: tuple[int, int, int]


@dataclass(frozen=True)
class Replica:
    name: str
    irskip: int
    batches: int

    @property
    def histories(self) -> int:
        return self.batches * MAXCAS_PER_BATCH


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _json_sha256(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(payload.encode("ascii")).hexdigest()


def parse_batch_allocation(value: str | Sequence[int]) -> tuple[int, int, int]:
    if isinstance(value, str):
        raw = [item.strip() for item in value.split(",")]
        if len(raw) != 3 or any(not item for item in raw):
            raise CtCalibrationError(
                "batch allocation must contain three comma-separated integers, for example 64,0,0 or 22,21,21"
            )
        try:
            parsed = tuple(int(item) for item in raw)
        except ValueError as exc:
            raise CtCalibrationError("batch allocation values must be integers") from exc
    else:
        if len(value) != 3:
            raise CtCalibrationError("batch allocation must contain exactly three values")
        parsed = tuple(value)
    if any(isinstance(item, bool) or not isinstance(item, int) or item < 0 for item in parsed):
        raise CtCalibrationError("batch allocation values must be non-negative integers")
    if sum(parsed) < MIN_ACCEPTED_BATCHES:
        raise CtCalibrationError(
            f"batch allocation must total at least {MIN_ACCEPTED_BATCHES}; got {sum(parsed)}"
        )
    return parsed


def replicas_from_allocation(allocation: Sequence[int]) -> tuple[Replica, ...]:
    parsed = parse_batch_allocation(allocation)
    return tuple(
        Replica(name=name, irskip=irskip, batches=batches)
        for (name, irskip), batches in zip(REPLICA_SPECS, parsed)
        if batches > 0
    )


def _parse_ct_voxel_counts(path: Path) -> tuple[int, int, int]:
    text = path.read_text(encoding="utf-8")
    values: list[int] = []
    for index in (81, 82, 83):
        match = re.search(
            rf"(?im)^\s*set:\s*c{index}\[\s*(\d+)\s*\]",
            text,
        )
        if match is None:
            raise CtCalibrationError(f"{path.name} does not define positive integer c{index}")
        value = int(match.group(1))
        if value <= 0:
            raise CtCalibrationError(f"{path.name} c{index} must be positive")
        values.append(value)
    return values[0], values[1], values[2]


def validate_ct_assets(root: Path, *, confirmed_non_patient_phantom: bool) -> CtAssetSet:
    if not confirmed_non_patient_phantom:
        raise CtCalibrationError(
            "CT asset preparation requires explicit confirmation that the source is non-patient phantom data"
        )
    resolved = root.resolve()
    if not resolved.is_dir():
        raise CtCalibrationError(f"CT asset directory does not exist: {root}")
    files: dict[str, Path] = {}
    hashes: dict[str, str] = {}
    for name in CT_ASSET_NAMES:
        path = resolved / name
        if not path.is_file():
            raise CtCalibrationError(f"required CT asset is missing: {name}")
        if path.is_symlink():
            raise CtCalibrationError(f"CT assets must not be symbolic links: {name}")
        if path.stat().st_size <= 0:
            raise CtCalibrationError(f"required CT asset is empty: {name}")
        files[name] = path
        hashes[name] = _sha256(path)
    return CtAssetSet(
        root=resolved,
        files=files,
        sha256=hashes,
        voxel_counts=_parse_ct_voxel_counts(files["CTusrparam.dat"]),
    )


def _field_label(field_size_cm: int) -> str:
    return f"{field_size_cm}x{field_size_cm}"


def _validate_field_size(field_size_cm: int) -> int:
    if isinstance(field_size_cm, bool) or not isinstance(field_size_cm, int):
        raise CtCalibrationError("field size must be an integer number of centimeters")
    if field_size_cm <= 0 or field_size_cm > 20:
        raise CtCalibrationError("field size must be between 1 and 20 cm")
    return field_size_cm


def build_fixed_field_geometry(field_size_cm: int) -> dict[str, Any]:
    size = _validate_field_size(field_size_cm)
    half_width_mm = size * 5.0
    machine_config = public_default_machine_config()
    leaf_pair_count = int(machine_config["mlc"]["leaf_pair_count"])
    segment = {
        "segment_id": f"public_ct_{_field_label(size)}",
        "delivery_type": "3dcrt_static",
        "resolved_jaw_positions_mm": {
            "x1": -half_width_mm,
            "x2": half_width_mm,
            "y1": -half_width_mm,
            "y2": half_width_mm,
        },
        "mlc_aperture_state": "present",
        "resolved_mlc_positions_mm": {
            "bank_a": [-half_width_mm] * leaf_pair_count,
            "bank_b": [half_width_mm] * leaf_pair_count,
        },
        "gantry_angle_deg": 0.0,
        "collimator_angle_deg": 0.0,
        "couch_angle_deg": 0.0,
        "segment_mu": 1.0,
        "static_aperture_classification": {"status": "static"},
        "aperture_change_diagnostics": {
            "status": "static",
            "dynamic_like": False,
            "jaw_changed": False,
            "mlc_changed": False,
        },
    }
    return build_intermediate_geometry(segment, machine_config)


def _section_body(text: str, start: str, end: str) -> list[str]:
    lines = text.splitlines()
    try:
        start_index = lines.index(start)
        end_index = lines.index(end, start_index + 1)
    except ValueError as exc:
        raise CtCalibrationError(
            f"public renderer output is missing section boundary {start} -> {end}"
        ) from exc
    return lines[start_index + 1 : end_index]


def _externalize_public_spectrum(source_lines: list[str]) -> list[str]:
    rows = list(public_spectrum_lines())
    try:
        start = source_lines.index(rows[0])
    except ValueError as exc:
        raise CtCalibrationError("public renderer output is missing the approved spectrum") from exc
    if source_lines[start : start + len(rows)] != rows:
        raise CtCalibrationError("public renderer spectrum does not match the approved identity")
    return [
        *source_lines[:start],
        f" infl:{{{PUBLIC_SPECTRUM_NAME}}}",
        *source_lines[start + len(rows) :],
    ]


def _public_model_fragments(
    geometry: Mapping[str, Any],
    *,
    totfact_per_mu: str | None = None,
    rotate_source_for_runtime: bool = False,
) -> tuple[list[str], list[str], list[str], list[str], list[int]]:
    rendered = render_rectangular_model_sections(
        geometry,
        totfact_per_mu=totfact_per_mu,
    )
    source = _externalize_public_spectrum(
        _section_body(rendered, "[ Source ]", "[ Surface ]")
    )
    if rotate_source_for_runtime:
        source = _runtime_source_lines(source, geometry)
    surfaces = [
        line
        for line in _section_body(rendered, "[ Surface ]", "[ Cell ]")
        if line.strip() and not line.lstrip().startswith("9000 ")
    ]
    raw_cells = _section_body(rendered, "[ Cell ]", "[ Material ]")
    shield_cells: list[str] = []
    shield_ids: list[int] = []
    for line in raw_cells:
        match = re.match(r"^\s*(\d+)\s", line)
        if match is None:
            continue
        cell_id = int(match.group(1))
        if cell_id in {3001, 9999}:
            continue
        body, separator, comment = line.partition("$")
        shield_cells.append(
            f"{body.rstrip()} u=1"
            + (f"  $ {comment.strip()}" if separator else "")
        )
        shield_ids.append(cell_id)
    if not surfaces or not shield_cells:
        raise CtCalibrationError("public renderer did not produce accelerator geometry")
    materials = [
        line
        for line in _section_body(rendered, "[ Material ]", "[ E N D ]")
        if line.strip()
    ]
    return source, surfaces, shield_cells, materials, shield_ids


def _air_cell_lines(shield_ids: Sequence[int]) -> list[str]:
    refs = [f"#{cell_id}" for cell_id in shield_ids]
    chunks = [refs[index : index + 12] for index in range(0, len(refs), 12)]
    lines: list[str] = []
    for index, chunk in enumerate(chunks):
        prefix = " 1000 2 -1.20e-3 -999 " if index == 0 else "     "
        suffix = " u=1" if index == len(chunks) - 1 else ""
        lines.append(f"{prefix}{' '.join(chunk)}{suffix}")
    return lines


def _parameter_lines(
    geometry: Mapping[str, Any],
    *,
    batches: int,
    irskip: int | None,
    sumtally_mode: bool,
    maxcas_per_batch: int = MAXCAS_PER_BATCH,
) -> list[str]:
    transport = geometry["transport"]
    lines = [
        f" icntl = {13 if sumtally_mode else 0}",
        f" maxcas = {1 if sumtally_mode else maxcas_per_batch}",
        f" maxbch = {1 if sumtally_mode else batches}",
    ]
    if irskip is not None:
        lines.append(f" irskip = {irskip}")
    lines.extend(
        [
            " nlost = 10000",
            " infl:{libpath.inp}",
        ]
    )
    if not sumtally_mode:
        lines.append(" istdev = -1")
    lines.extend(
        [
            " infl:{CTusrparam.dat}",
            f" emin(2) = {transport['photon_cutoff_mev']:g}",
            f" emin(12) = {transport['electron_cutoff_mev']:g}",
            f" emin(13) = {transport['positron_cutoff_mev']:g}",
            f" emin(14) = {transport['photon_cutoff_mev']:g}",
            " igamma = 2",
            " ipnint = 0",
            " negs = 1",
            " file(6) = phits.out",
        ]
    )
    return lines


def _identity_accelerator_transforms() -> list[str]:
    return [
        "tr2   0.00000 0.00000 0.00000",
        "      1.00000 0.00000 0.00000",
        "      0.00000 1.00000 0.00000",
        "      0.00000 0.00000 1.00000",
        "      1",
        "tr3   0.00000 0.00000 0.00000",
        "      1.00000 0.00000 0.00000",
        "      0.00000 1.00000 0.00000",
        "      0.00000 0.00000 1.00000",
        "      1",
    ]


def _fmt_runtime(value: float) -> str:
    if abs(value) < 1.0e-12:
        value = 0.0
    return f"{value:.12g}"


def _runtime_source_lines(
    source_lines: list[str],
    geometry: Mapping[str, Any],
) -> list[str]:
    angles = geometry["angles_deg"]
    gantry_deg = float(angles["gantry"])
    couch_deg = float(angles["couch"])
    if not math.isclose(couch_deg, 0.0, abs_tol=1.0e-9):
        raise CtCalibrationError(
            "public v1 runtime supports couch angle 0 degrees only"
        )

    gantry_rad = math.radians(gantry_deg)
    direction_x = math.sin(gantry_rad)
    direction_y = 0.0
    direction_z = math.cos(gantry_rad)
    direction_x = 0.0 if abs(direction_x) < 1.0e-12 else direction_x
    direction_y = 0.0 if abs(direction_y) < 1.0e-12 else direction_y
    direction_z = 0.0 if abs(direction_z) < 1.0e-12 else direction_z
    source = geometry["source"]
    model = str(source["model"])
    if model == "point":
        source_distance = math.sqrt(
            sum(float(value) ** 2 for value in source["position_cm"])
        )
        half_width_x = 0.0
        half_width_y = 0.0
    elif model == "uniform_rectangular":
        source_distance = abs(float(source["plane_z_cm"]))
        half_width_x = float(source["width_x_cm"]) / 2.0
        half_width_y = float(source["width_y_cm"]) / 2.0
    elif model == "rectangular_fwhm":
        source_distance = abs(float(source["plane_z_cm"]))
        half_width_x = 0.0
        half_width_y = 0.0
    else:
        raise CtCalibrationError(f"unsupported public source model: {model}")

    center_x = -source_distance * direction_x
    center_y = -source_distance * direction_y
    center_z = -source_distance * direction_z
    replacements = {
        "x0": center_x - half_width_x,
        "x1": center_x + half_width_x,
        "y0": center_y - half_width_y,
        "y1": center_y + half_width_y,
        "z0": center_z,
        "z1": center_z,
        "dir": direction_z,
        "phi": math.degrees(math.atan2(direction_y, direction_x)),
    }
    rendered: list[str] = []
    for line in source_lines:
        match = re.match(r"^(\s*)(x0|x1|y0|y1|z0|z1|dir|phi)\s*=", line)
        if match is None:
            rendered.append(line)
            continue
        key = match.group(2)
        rendered.append(f"{match.group(1)}{key} = {_fmt_runtime(replacements[key])}")
    return rendered


def _runtime_accelerator_transforms(
    geometry: Mapping[str, Any],
) -> list[str]:
    angles = geometry["angles_deg"]
    gantry = float(angles["gantry"])
    collimator = float(angles["collimator"])
    couch = float(angles["couch"])
    if not math.isclose(couch, 0.0, abs_tol=1.0e-9):
        raise CtCalibrationError(
            "public v1 runtime supports couch angle 0 degrees only"
        )
    gantry_sine_rows = (
        (
            "      sin(c20/180*pi)",
            "     -sin(c20/180*pi)",
        )
        if math.isclose(gantry, 0.0, rel_tol=0.0, abs_tol=1.0e-9)
        else (
            "     -sin(c20/180*pi)",
            "      sin(c20/180*pi)",
        )
    )
    return [
        f"set: c10[{_fmt_runtime(collimator)}] $ Collimator angle (deg)",
        f"set: c20[{_fmt_runtime(gantry)}] $ Gantry angle (deg)",
        "set: c21[0]",
        "set: c31[0]",
        "tr2   0 0 0",
        "      cos(c10/180*pi)*cos(c21/180*pi)",
        "     -sin(c10/180*pi)*cos(c31/180*pi)+cos(c10/180*pi)*sin(c21/180*pi)*sin(c31/180*pi)",
        "     -sin(c10/180*pi)*sin(c31/180*pi)-cos(c10/180*pi)*sin(c21/180*pi)*cos(c31/180*pi)",
        "      sin(c10/180*pi)*cos(c21/180*pi)",
        "      cos(c10/180*pi)*cos(c31/180*pi)+sin(c10/180*pi)*sin(c21/180*pi)*sin(c31/180*pi)",
        "      cos(c10/180*pi)*sin(c31/180*pi)-sin(c10/180*pi)*sin(c21/180*pi)*cos(c31/180*pi)",
        "      sin(c21/180*pi)",
        "     -cos(c21/180*pi)*sin(c31/180*pi)",
        "      cos(c21/180*pi)*cos(c31/180*pi)",
        "      1",
        "tr3   0.0000 0.0000 0.0000",
        "      cos(c20/180*pi)",
        "      0",
        gantry_sine_rows[0],
        "      0",
        "      1",
        "      0",
        gantry_sine_rows[1],
        "      0",
        "      cos(c20/180*pi)",
        "      1",
    ]


def _render_gui_chassis_input(
    geometry: Mapping[str, Any],
    *,
    voxel_counts: tuple[int, int, int],
    batches: int,
    irskip: int | None,
    omp_threads: int,
    sumtally_target: str | None = None,
    maxcas_per_batch: int = MAXCAS_PER_BATCH,
    output_3d: str = "deposit-target-3D.out",
    output_pdd: str = "deposit-pdd.out",
    totfact_per_mu: str | None = None,
    runtime_angles: bool = False,
    epsout: float = 1,
) -> str:
    if batches <= 0:
        raise CtCalibrationError("replica batches must be positive")
    if omp_threads <= 0:
        raise CtCalibrationError("OMP thread count must be positive")
    if sumtally_target not in {None, "3d", "pdd"}:
        raise CtCalibrationError("Sumtally target must be 3d or pdd")

    source, surfaces, shield_cells, materials, shield_ids = _public_model_fragments(
        geometry,
        totfact_per_mu=totfact_per_mu,
        rotate_source_for_runtime=runtime_angles,
    )
    nx, ny, nz = voxel_counts
    z_min = min(
        float(geometry["mlc_geometry"]["upstream_z_cm"]),
        float(geometry["y_diaphragm"]["upstream_z_cm"]),
    )
    z_max = max(
        float(geometry["mlc_geometry"]["downstream_z_cm"]),
        float(geometry["y_diaphragm"]["downstream_z_cm"]),
    )
    sumtally_mode = sumtally_target is not None
    tally_lines = _dose_tally_lines(
        output_3d=(
            "merged-deposit-target-3D.out"
            if sumtally_mode
            else output_3d
        ),
        output_pdd="merged-deposit-pdd.out" if sumtally_mode else output_pdd,
        sumtally_3d_include=(
            "sumtally_3d_files.inp" if sumtally_target == "3d" else None
        ),
        sumtally_pdd_include=(
            "sumtally_pdd_files.inp" if sumtally_target == "pdd" else None
        ),
        epsout=epsout,
    )
    lines = [
        f"$OMP = {omp_threads}",
        "$ Public CT-derived voxel phantom calibration input",
        "$ CT/Air/universe chassis follows the GUI-validated CT2PHITS structure",
        "$ Accelerator source, rectangular MLC, Y-Diaphragms, and alloy use the approved public model",
        (
            "$ Approved public-model absolute-dose factor is applied in [Source]"
            if totfact_per_mu is not None
            else "$ Dose remains relative Gy/source; absolute-dose factor is intentionally absent pending approval"
        ),
        "",
        "[ Title ]",
        f"Public model {geometry['segment_id']}: CT-derived voxel phantom calibration",
        "$ renderer-trace: geometry_mode = rectangular_3dcrt",
        "$ renderer-trace: phantom = CT-derived voxel phantom",
        "$ renderer-trace: ct_chassis = gui_validated_ct2phits_air_universe",
        f"$ renderer-trace: photon_spectrum = {PUBLIC_SPECTRUM_NAME}",
        "",
        "[ Parameters ]",
        *_parameter_lines(
            geometry,
            batches=batches,
            irskip=irskip,
            sumtally_mode=sumtally_mode,
            maxcas_per_batch=maxcas_per_batch,
        ),
        "",
        "[ S o u r c e ]",
        *source,
        "",
        "[ Surface ]",
        " 999 so 1000.0",
        f" 11 pz {z_min - 0.00001:.5f}",
        f" 12 pz {z_max + 0.00001:.5f}",
        " 13 cz 80.0",
        *surfaces,
        " 901 so 150.0",
        " infl:{CTsurf.dat}",
        "",
        "[ Cell ]",
        " 9999 -1 999 $ outer void",
        " 1200 2 -1.20e-3 -999 #1201 #2 $ Air in main space",
        " 1201 0 -98 fill=4000 $ CT phantom wrapper in main space",
        " 2 0 11 -12 -13 fill=2 trcl=3 $ accelerator region",
        " 998 0 97 trcl=500 u=4000 $ Air layer outside CT voxel fill",
        " 997 0 -97 trcl=500 fill=5000 u=4000 $ CT voxel phantom fill",
        " infl:{CTuniverse.inp}",
        " 5000 0 -5000 lat=1 u=5000",
        f"      fill=0:{nx - 1} 0:{ny - 1} 0:{nz - 1}",
        " infl:{CTvoxel.inp}",
        " 901 0 -901 fill=1 trcl=2 u=2 $ public accelerator universe",
        " 900 2 -1.20e-3 -999 #901 u=2 $ Air in accelerator container",
        *_air_cell_lines(shield_ids),
        *shield_cells,
        "",
        "[ Material ]",
        *materials,
        " MAT[2] $ Air 1.20e-3 g/cm3",
        " 14N 3.910E-05",
        " 16O 1.054E-05",
        " infl:{CTmaterial.dat}",
        "",
        "[ Transform ]",
        *(
            _runtime_accelerator_transforms(geometry)
            if runtime_angles
            else _identity_accelerator_transforms()
        ),
        " infl:{CTtrans.inp}",
        "",
        *tally_lines,
        "",
        "[ E N D ]",
    ]
    rendered = "\n".join(lines) + "\n"
    if totfact_per_mu is None and "totfact" in rendered.lower():
        raise CtCalibrationError("calibration input must not contain a totfact")
    return rendered


def _dose_tally_lines(
    *,
    output_3d: str,
    output_pdd: str,
    sumtally_3d_include: str | None = None,
    sumtally_pdd_include: str | None = None,
    epsout: float = 1,
) -> list[str]:
    three_d_header = "[ T-Deposit ]" if sumtally_3d_include is not None or sumtally_pdd_include is None else "[ T-Deposit ] off"
    pdd_header = "[ T-Deposit ]" if sumtally_pdd_include is not None or sumtally_3d_include is None else "[ T-Deposit ] off"
    three_d = [
        three_d_header,
        " title = Public CT voxel 101x101x101 dose grid, 3 mm spacing",
        " mesh = xyz",
        " x-type = 2",
        f" xmin = {DOSE_GRID_TRANSVERSE_MIN_CM}",
        f" xmax = {DOSE_GRID_TRANSVERSE_MAX_CM}",
        f" nx = {DOSE_GRID_COUNT}",
        " y-type = 2",
        f" ymin = {DOSE_GRID_TRANSVERSE_MIN_CM}",
        f" ymax = {DOSE_GRID_TRANSVERSE_MAX_CM}",
        f" ny = {DOSE_GRID_COUNT}",
        " z-type = 2",
        f" zmin = {DOSE_GRID_MIN_CM}",
        f" zmax = {DOSE_GRID_MAX_CM}",
        f" nz = {DOSE_GRID_COUNT}",
        " unit = 0",
        " material = all",
        " output = dose",
        " axis = xy",
        f" file = {output_3d}",
        " part = all",
        f" epsout = {epsout:g}",
    ]
    if sumtally_3d_include is not None:
        three_d.append(f" infl:{{{sumtally_3d_include}}}")
    pdd = [
        "",
        pdd_header,
        f" title = Public CT voxel central-axis PDD, reference depth {REFERENCE_DEPTH_CM:g} cm",
        " mesh = xyz",
        " x-type = 2",
        f" xmin = {PDD_TRANSVERSE_MIN_CM}",
        f" xmax = {PDD_TRANSVERSE_MAX_CM}",
        " nx = 1",
        " y-type = 2",
        f" ymin = {PDD_TRANSVERSE_MIN_CM}",
        f" ymax = {PDD_TRANSVERSE_MAX_CM}",
        " ny = 1",
        " z-type = 2",
        f" zmin = {DOSE_GRID_MIN_CM}",
        f" zmax = {DOSE_GRID_MAX_CM}",
        f" nz = {DOSE_GRID_COUNT}",
        " unit = 0",
        " material = all",
        " output = dose",
        " axis = z",
        f" file = {output_pdd}",
        " part = all",
        f" epsout = {epsout:g}",
    ]
    if sumtally_pdd_include is not None:
        pdd.append(f" infl:{{{sumtally_pdd_include}}}")
    return [*three_d, *pdd]


def render_ct_calibration_input(
    geometry: Mapping[str, Any],
    *,
    voxel_counts: tuple[int, int, int],
    batches: int,
    irskip: int,
    omp_threads: int = DEFAULT_OMP_THREADS,
) -> str:
    return _render_gui_chassis_input(
        geometry,
        voxel_counts=voxel_counts,
        batches=batches,
        irskip=irskip,
        omp_threads=omp_threads,
    )


def render_ct_runtime_input(
    geometry: Mapping[str, Any],
    *,
    voxel_counts: tuple[int, int, int],
    output_3d: str,
    output_pdd: str,
    totfact_per_mu: str | None,
    maxcas_per_batch: int = 1_000_000,
    batches: int = 10,
    omp_threads: int = DEFAULT_OMP_THREADS,
    epsout: float = 1,
) -> str:
    if maxcas_per_batch <= 0 or batches <= 0:
        raise CtCalibrationError("runtime maxcas and maxbch must be positive")
    return _render_gui_chassis_input(
        geometry,
        voxel_counts=voxel_counts,
        batches=batches,
        irskip=None,
        omp_threads=omp_threads,
        maxcas_per_batch=maxcas_per_batch,
        output_3d=output_3d,
        output_pdd=output_pdd,
        totfact_per_mu=totfact_per_mu,
        runtime_angles=True,
        epsout=epsout,
    )


def _sumtally_block(
    *,
    output_name: str,
    source_name: str,
    replicas: Sequence[Replica],
) -> str:
    lines = [
        "sumtally start",
        "  isumtally = 2",
        f"  sfile = {output_name}",
        "  sumfactor = 1.0",
        f"  nfile = {len(replicas)}",
    ]
    for replica in replicas:
        lines.append(f"  ../{replica.name}/{source_name}  {replica.histories}")
    lines.append("sumtally end")
    return "\n".join(lines) + "\n"


def render_sumtally_wrapper(
    geometry: Mapping[str, Any],
    *,
    voxel_counts: tuple[int, int, int],
    target: str,
    omp_threads: int = DEFAULT_OMP_THREADS,
) -> str:
    return _render_gui_chassis_input(
        geometry,
        voxel_counts=voxel_counts,
        batches=1,
        irskip=None,
        omp_threads=omp_threads,
        sumtally_target=target,
    )


def _write_text(path: Path, text: str, *, windows_newlines: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    newline = "\r\n" if windows_newlines else "\n"
    with path.open("w", encoding="utf-8", newline=newline) as stream:
        stream.write(text)


def _copy_ct_assets(asset_set: CtAssetSet, destination: Path) -> None:
    for name, source in asset_set.files.items():
        shutil.copy2(source, destination / name)
    _write_text(destination / PUBLIC_SPECTRUM_NAME, PUBLIC_SPECTRUM_TEXT)


def _phits_binding_bat_lines() -> list[str]:
    return [
        "if not defined PHITS_ROOT (",
        "  echo ERROR: PHITS_ROOT is not set.",
        "  echo Set PHITS_ROOT to this PC's PHITS installation directory.",
        "  exit /b 2",
        ")",
        'if not exist "%PHITS_ROOT%\\." (',
        '  echo ERROR: PHITS_ROOT directory not found: "%PHITS_ROOT%"',
        "  exit /b 3",
        ")",
        "if not defined PHITS_EXE (",
        "  echo ERROR: PHITS_EXE is not set.",
        "  echo Set PHITS_EXE to the exact PHITS executable on this PC.",
        "  exit /b 4",
        ")",
        'if not exist "%PHITS_EXE%" (',
        '  echo ERROR: PHITS executable not found: "%PHITS_EXE%"',
        "  exit /b 5",
        ")",
        'set "PHITS_ROOT_PHITS=%PHITS_ROOT:\\=/%"',
        '> "libpath.inp.tmp" echo file(1) = %PHITS_ROOT_PHITS%',
        "if errorlevel 1 (",
        "  echo ERROR: Could not prepare libpath.inp.",
        "  exit /b 6",
        ")",
        'move /y "libpath.inp.tmp" "libpath.inp" >nul',
        "if errorlevel 1 (",
        "  echo ERROR: Could not replace libpath.inp.",
        "  exit /b 7",
        ")",
    ]


def _run_bat(input_name: str) -> str:
    return "\n".join(
        [
            "@echo off",
            "setlocal",
            'cd /d "%~dp0"',
            *_phits_binding_bat_lines(),
            f'echo Running {input_name} with "%PHITS_EXE%"',
            f'"%PHITS_EXE%" < "{input_name}" > "run_console.log" 2>&1',
            'set "RUN_RC=%ERRORLEVEL%"',
            'if not "%RUN_RC%"=="0" (',
            "  echo ERROR: PHITS returned %RUN_RC%. See run_console.log.",
            "  exit /b %RUN_RC%",
            ")",
            'if not exist "deposit-target-3D.out" (',
            "  echo ERROR: deposit-target-3D.out was not created.",
            "  exit /b 3",
            ")",
            'if not exist "deposit-pdd.out" (',
            "  echo ERROR: deposit-pdd.out was not created.",
            "  exit /b 4",
            ")",
            '> "run_complete.txt" echo PHITS completed with both required tally outputs.',
            "echo PHITS calculation completed.",
            "exit /b 0",
            "",
        ]
    )


def _sumtally_bat(*, suffix: str) -> str:
    return "\n".join(
        [
            "@echo off",
            "setlocal",
            'cd /d "%~dp0"',
            *_phits_binding_bat_lines(),
            f'"%PHITS_EXE%" < "merge_3d_{suffix}.inp" > "merge_3d_{suffix}.log" 2>&1',
            'if not "%ERRORLEVEL%"=="0" exit /b %ERRORLEVEL%',
            f'"%PHITS_EXE%" < "merge_pdd_{suffix}.inp" > "merge_pdd_{suffix}.log" 2>&1',
            'if not "%ERRORLEVEL%"=="0" exit /b %ERRORLEVEL%',
            'if not exist "merged-deposit-target-3D.out" exit /b 3',
            'if not exist "merged-deposit-pdd.out" exit /b 4',
            "echo Sumtally completed.",
            "exit /b 0",
            "",
        ]
    )


def _field_readme(field_size_cm: int, replicas: Sequence[Replica]) -> str:
    rows = [
        f"Public CT voxel calibration field: {_field_label(field_size_cm)} cm2",
        "",
        "Calculation requirement:",
        "  20M histories per batch",
        "  At least 64 accepted batches and 1280M histories in aggregate",
        "  One PC or any combination of PC A, PC B, and PC C is acceptable",
        "",
        "Prepared replicas:",
    ]
    rows.extend(
        f"  {replica.name}: {replica.batches} batches, {replica.histories} histories, irskip={replica.irskip}"
        for replica in replicas
    )
    rows.extend(
        [
            "",
            "Run:",
            "  1. Copy each prepared pc_* directory to the selected Windows PC.",
            "  2. In Command Prompt on each PC, set PHITS_ROOT to that PC's PHITS",
            "     installation directory and PHITS_EXE to its exact executable.",
            "  3. Run run_this_pc.bat in the same Command Prompt.",
            "     The BAT does not search for PHITS. It validates both values and",
            "     writes that PC's libpath.inp immediately before PHITS starts.",
            "  4. Return the completed pc_* directories to this field directory.",
            "  5. Confirm every accepted input hash matches calibration_manifest.json.",
            "  6. Set PHITS_ROOT and PHITS_EXE on the Sumtally PC, then run",
            "     sumtally/run_sumtally_all.bat when all prepared replicas are accepted.",
            "     If only one 64-batch replica is accepted, run the matching",
            "     sumtally/run_sumtally_pc_a.bat, pc_b.bat, or pc_c.bat.",
            "",
            "PHITS is external and is not included.",
            "The CT2PHITS voxel material assignments and GUI-validated CT transform are preserved.",
            "These outputs are research calibration evidence, not clinical dose.",
            "",
        ]
    )
    return "\n".join(rows)


def _prepare_field(
    *,
    output_root: Path,
    field_size_cm: int,
    asset_set: CtAssetSet,
    replicas: Sequence[Replica],
    omp_threads: int,
) -> dict[str, Any]:
    label = _field_label(field_size_cm)
    field_root = output_root / f"field_{label}"
    field_root.mkdir(parents=True)
    geometry = build_fixed_field_geometry(field_size_cm)
    replica_rows: list[dict[str, Any]] = []
    for replica in replicas:
        replica_root = field_root / replica.name
        replica_root.mkdir()
        _copy_ct_assets(asset_set, replica_root)
        input_name = f"public_ct_{label}.inp"
        input_text = render_ct_calibration_input(
            geometry,
            voxel_counts=asset_set.voxel_counts,
            batches=replica.batches,
            irskip=replica.irskip,
            omp_threads=omp_threads,
        )
        _write_text(replica_root / input_name, input_text)
        _write_text(
            replica_root / "run_this_pc.bat",
            _run_bat(input_name),
            windows_newlines=True,
        )
        replica_rows.append(
            {
                "replica": replica.name,
                "irskip": replica.irskip,
                "batches": replica.batches,
                "maxcas_per_batch": MAXCAS_PER_BATCH,
                "effective_histories": replica.histories,
                "input": f"{replica.name}/{input_name}",
                "input_sha256": _sha256(replica_root / input_name),
                "expected_outputs": [
                    f"{replica.name}/deposit-target-3D.out",
                    f"{replica.name}/deposit-pdd.out",
                ],
            }
        )

    sumtally_root = field_root / "sumtally"
    sumtally_root.mkdir()
    _copy_ct_assets(asset_set, sumtally_root)
    merge_sets: list[tuple[str, tuple[Replica, ...]]] = [("all", tuple(replicas))]
    merge_sets.extend((replica.name, (replica,)) for replica in replicas)
    for suffix, selected_replicas in merge_sets:
        _write_text(
            sumtally_root / f"sumtally_3d_{suffix}_files.inp",
            _sumtally_block(
                output_name="merged-deposit-target-3D.out",
                source_name="deposit-target-3D.out",
                replicas=selected_replicas,
            ),
        )
        _write_text(
            sumtally_root / f"sumtally_pdd_{suffix}_files.inp",
            _sumtally_block(
                output_name="merged-deposit-pdd.out",
                source_name="deposit-pdd.out",
                replicas=selected_replicas,
            ),
        )
        wrapper_3d = render_sumtally_wrapper(
            geometry,
            voxel_counts=asset_set.voxel_counts,
            target="3d",
            omp_threads=omp_threads,
        ).replace(
            "infl:{sumtally_3d_files.inp}",
            f"infl:{{sumtally_3d_{suffix}_files.inp}}",
        )
        wrapper_pdd = render_sumtally_wrapper(
            geometry,
            voxel_counts=asset_set.voxel_counts,
            target="pdd",
            omp_threads=omp_threads,
        ).replace(
            "infl:{sumtally_pdd_files.inp}",
            f"infl:{{sumtally_pdd_{suffix}_files.inp}}",
        )
        _write_text(sumtally_root / f"merge_3d_{suffix}.inp", wrapper_3d)
        _write_text(sumtally_root / f"merge_pdd_{suffix}.inp", wrapper_pdd)
        _write_text(
            sumtally_root / f"run_sumtally_{suffix}.bat",
            _sumtally_bat(suffix=suffix),
            windows_newlines=True,
        )
    _write_text(
        field_root / "README.txt",
        _field_readme(field_size_cm, replicas),
        windows_newlines=True,
    )
    return {
        "field_size_cm": [field_size_cm, field_size_cm],
        "field_label": label,
        "priority": DEFAULT_FIELD_SIZES_CM.index(field_size_cm) + 1,
        "geometry_sha256": _json_sha256(geometry),
        "replicas": replica_rows,
        "sumtally": {
            "mode": "isumtally_2_history_weighted_mean",
            "directory": f"field_{label}/sumtally",
            "prepared_acceptance_sets": [suffix for suffix, _selected in merge_sets],
            "default_launcher": f"field_{label}/sumtally/run_sumtally_all.bat",
            "expected_outputs": [
                f"field_{label}/sumtally/merged-deposit-target-3D.out",
                f"field_{label}/sumtally/merged-deposit-pdd.out",
            ],
        },
    }


def prepare_ct_calibration_packages(
    *,
    ct_asset_root: Path,
    output_root: Path,
    batch_allocation: str | Sequence[int] = DEFAULT_BATCH_ALLOCATION,
    field_sizes_cm: Sequence[int] = DEFAULT_FIELD_SIZES_CM,
    omp_threads: int = DEFAULT_OMP_THREADS,
    confirmed_non_patient_phantom: bool = False,
) -> dict[str, Any]:
    allocation = parse_batch_allocation(batch_allocation)
    replicas = replicas_from_allocation(allocation)
    if omp_threads <= 0:
        raise CtCalibrationError("OMP thread count must be positive")
    fields = tuple(_validate_field_size(value) for value in field_sizes_cm)
    if fields != DEFAULT_FIELD_SIZES_CM:
        raise CtCalibrationError(
            "field order must be exactly 10,3,5,20 so the publication-gating 10x10 calculation is prepared first"
        )
    if output_root.exists():
        raise CtCalibrationError(f"refusing to overwrite existing output root: {output_root}")
    asset_set = validate_ct_assets(
        ct_asset_root,
        confirmed_non_patient_phantom=confirmed_non_patient_phantom,
    )
    output_root.mkdir(parents=True)
    try:
        field_rows = [
            _prepare_field(
                output_root=output_root,
                field_size_cm=field_size,
                asset_set=asset_set,
                replicas=replicas,
                omp_threads=omp_threads,
            )
            for field_size in fields
        ]
        machine_config = public_default_machine_config()
        manifest = {
            "schema_version": SCHEMA_VERSION,
            "status": "prepared_not_executed",
            "public_model": {
                "machine_config_sha256": _json_sha256(machine_config),
                "spectrum_sha256": PUBLIC_SPECTRUM_SHA256,
                "absolute_dose_factor": None,
                "dose_semantics": "relative_gy_per_source_until_factor_approval",
            },
            "phantom": {
                "kind": "ct_derived_voxel_phantom",
                "chassis": "gui_validated_ct2phits_air_universe",
                "transform_asset": "CTtrans.inp",
                "material_assignment": "ct2phits_preserved",
                "confirmed_non_patient_phantom": True,
                "source_path_recorded": False,
                "voxel_counts": list(asset_set.voxel_counts),
                "asset_sha256": dict(asset_set.sha256),
            },
            "tallies": {
                "dose_grid": {
                    "counts": [DOSE_GRID_COUNT] * 3,
                    "spacing_mm": [DOSE_GRID_SPACING_CM * 10] * 3,
                    "bounds_cm": [
                        [DOSE_GRID_TRANSVERSE_MIN_CM, DOSE_GRID_TRANSVERSE_MAX_CM],
                        [DOSE_GRID_TRANSVERSE_MIN_CM, DOSE_GRID_TRANSVERSE_MAX_CM],
                        [DOSE_GRID_MIN_CM, DOSE_GRID_MAX_CM],
                    ],
                },
                "central_axis_pdd": {
                    "counts": [1, 1, DOSE_GRID_COUNT],
                    "spacing_mm": [3.0, 3.0, 3.0],
                    "reference_depth_cm": REFERENCE_DEPTH_CM,
                    "z_bounds_cm": [DOSE_GRID_MIN_CM, DOSE_GRID_MAX_CM],
                },
            },
            "history_requirement": {
                "maxcas_per_batch": MAXCAS_PER_BATCH,
                "minimum_accepted_batches": MIN_ACCEPTED_BATCHES,
                "minimum_accepted_histories": MIN_ACCEPTED_HISTORIES,
                "configured_batch_allocation": {
                    name: batches
                    for (name, _irskip), batches in zip(REPLICA_SPECS, allocation)
                },
                "configured_total_batches": sum(allocation),
                "configured_total_histories": sum(allocation) * MAXCAS_PER_BATCH,
                "pc_count_is_release_criterion": False,
            },
            "publication_gate": {
                "blocking_field": "10x10",
                "passes_after": [
                    "at_least_1280M_model_matching_histories_accepted",
                    "required_3d_and_pdd_outputs_structurally_valid",
                    "sumtally_completed",
                    "totfact_per_MU_derived_and_human_accepted",
                    "all_other_public_release_gates_pass",
                ],
                "non_blocking_follow_up_fields": ["3x3", "5x5", "20x20"],
                "automatic_publication": False,
            },
            "field_order": [_field_label(value) for value in fields],
            "fields": field_rows,
            "phits_execution_performed": False,
            "sumtally_execution_performed": False,
        }
        _write_text(
            output_root / "calibration_manifest.json",
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        )
        return manifest
    except Exception:
        shutil.rmtree(output_root, ignore_errors=True)
        raise


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Prepare public-model CT voxel PHITS calibration packages for "
            "10x10, 3x3, 5x5, and 20x20 cm2 fixed fields."
        )
    )
    parser.add_argument("--ct-asset-root", required=True)
    parser.add_argument("--output-root", required=True)
    parser.add_argument(
        "--batch-allocation",
        default="64,64,64",
        help="PC A, PC B, PC C batch counts; total must be at least 64",
    )
    parser.add_argument("--omp-threads", type=int, default=DEFAULT_OMP_THREADS)
    parser.add_argument(
        "--confirm-non-patient-phantom",
        action="store_true",
        help="Required confirmation that the CT assets are from a non-patient phantom",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        manifest = prepare_ct_calibration_packages(
            ct_asset_root=Path(args.ct_asset_root),
            output_root=Path(args.output_root),
            batch_allocation=args.batch_allocation,
            omp_threads=args.omp_threads,
            confirmed_non_patient_phantom=args.confirm_non_patient_phantom,
        )
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(Path(args.output_root) / "calibration_manifest.json")
    print(
        "Prepared "
        f"{manifest['history_requirement']['configured_total_histories']} histories "
        "per field; PHITS was not executed."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
