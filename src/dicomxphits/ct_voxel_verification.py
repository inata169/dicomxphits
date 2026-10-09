"""Independent checks for the CT2PHITS coarse voxel lattice.

The source images and conversion table are read from the frozen workspace.  This
module does not change the DICOM snapshots or the external RT-PHITS installation.
"""

from __future__ import annotations

import bisect
import itertools
import math
import os
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, Sequence

import numpy as np
import pydicom

from dicomxphits.ct_pixel_clipping import ClipBounds, coarse_coverage


class CtVoxelVerificationError(ValueError):
    """The generated CT lattice cannot be verified or safely corrected."""


@dataclass(frozen=True)
class VoxelVerification:
    voxel_count: int
    mismatched_voxels: int
    corrected: bool


@dataclass(frozen=True)
class _ConversionTable:
    thresholds: tuple[float, ...]
    densities: tuple[float, ...]
    compositions: tuple[tuple[str, ...], ...]


def _fortran_float(value: str) -> float:
    try:
        result = float(value.replace("D", "E").replace("d", "e"))
    except ValueError as exc:
        raise CtVoxelVerificationError("invalid CT conversion table number") from exc
    if not math.isfinite(result):
        raise CtVoxelVerificationError("non-finite CT conversion table number")
    return result


def _read_table(path: Path) -> _ConversionTable:
    lines = path.read_text(encoding="utf-8").splitlines()
    if len(lines) < 4:
        raise CtVoxelVerificationError("CT conversion table is incomplete")
    def fields(line: str) -> list[str]:
        return line.split("!", 1)[0].split()
    try:
        count_fields = fields(lines[1])
        if len(count_fields) != 1 or not count_fields[0].isdigit():
            raise ValueError
        count = int(count_fields[0])
        if count < 2 or len(lines) < count + 3:
            raise ValueError
        thresholds = []
        densities = []
        element_counts = []
        for line in lines[2 : 2 + count]:
            row = fields(line)
            if len(row) != 3:
                raise ValueError
            thresholds.append(_fortran_float(row[0]))
            densities.append(_fortran_float(row[1]))
            if not row[2].isdigit() or int(row[2]) <= 0:
                raise ValueError
            element_counts.append(int(row[2]))
        upper_fields = fields(lines[2 + count])
        if len(upper_fields) != 1 or _fortran_float(upper_fields[0]) <= thresholds[-1]:
            raise ValueError
        if any(a >= b for a, b in zip(thresholds, thresholds[1:])):
            raise ValueError
        position = 3 + count
        compositions = []
        for element_count in element_counts:
            if position >= len(lines) or not lines[position].lstrip().startswith("#"):
                raise ValueError
            compositions.append(tuple(line.strip() for line in lines[position+1:position+1+element_count]))
            position += element_count + 1
        if position > len(lines):
            raise ValueError
    except (ValueError, IndexError) as exc:
        raise CtVoxelVerificationError("unsupported CT conversion table layout") from exc
    return _ConversionTable(tuple(thresholds), tuple(densities), tuple(compositions))


def _verify_material_assets(datfiles: Path, table: _ConversionTable) -> None:
    material_lines = (datfiles / "CTmaterial.dat").read_text(encoding="utf-8").splitlines()
    sections: list[list[str]] = []
    for line in material_lines:
        match = re.match(r"\s*MAT\[\s*(\d+)\s*\]", line, re.I)
        if match:
            if int(match.group(1)) != 5001 + len(sections):
                raise CtVoxelVerificationError("CT material IDs disagree with conversion table")
            sections.append([])
        elif sections and line.strip():
            sections[-1].append(line.strip())
    if tuple(tuple(section) for section in sections) != table.compositions:
        raise CtVoxelVerificationError("CT material compositions disagree with conversion table")
    universe_lines = (datfiles / "CTuniverse.dat").read_text(encoding="utf-8").splitlines()
    if len(universe_lines) != len(table.densities):
        raise CtVoxelVerificationError("CT universe count disagrees with conversion table")
    for index, (line, density) in enumerate(zip(universe_lines, table.densities), 1):
        match = re.fullmatch(
            r"\s*(\d+)\s+(\d+)\s+([+-]?[\d.]+)\s+-99\s+u=(\d+)\s*",
            line, re.I,
        )
        material_id = 5000 + index
        if (match is None or int(match.group(1)) != material_id
            or int(match.group(2)) != material_id
            or int(match.group(4)) != material_id
            or not math.isclose(float(match.group(3)), density, rel_tol=0, abs_tol=5.1e-6)):
            raise CtVoxelVerificationError("CT universe material or density disagrees with conversion table")


def _parameters(path: Path) -> dict[int, float]:
    result: dict[int, float] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        match = re.match(r"\s*set:\s*c(8[1-9]|90)\[\s*([^\]]+)\s*\]", line, re.I)
        if match:
            number = int(match.group(1))
            if number in result:
                raise CtVoxelVerificationError(f"duplicate CT c{number} parameter")
            result[number] = _fortran_float(match.group(2).strip())
    if set(result) != set(range(81, 91)):
        raise CtVoxelVerificationError("CT lattice parameters c81-c90 are incomplete")
    return result


def _verify_geometry(
    datfiles: Path, source_files: Sequence[Path], bounds: ClipBounds,
    factors: tuple[int, int, int], counts: tuple[int, int, int],
) -> None:
    first = pydicom.dcmread(str(source_files[bounds.first - 1]), stop_before_pixels=True)
    spacing_y, spacing_x = (float(value) / 10.0 for value in first.PixelSpacing)
    if bounds.last > bounds.first:
        second = pydicom.dcmread(str(source_files[bounds.first]), stop_before_pixels=True)
        spacing_z = (float(second.ImagePositionPatient[2]) - float(first.ImagePositionPatient[2])) / 10.0
    elif len(source_files) > 1:
        neighbour = 1 if bounds.first == 1 else bounds.first - 2
        other = pydicom.dcmread(str(source_files[neighbour]), stop_before_pixels=True)
        spacing_z = abs(float(other.ImagePositionPatient[2]) - float(first.ImagePositionPatient[2])) / 10.0
    else:
        raise CtVoxelVerificationError("single-slice CT spacing cannot be verified")
    expected = {
        81: counts[0], 82: counts[1], 83: counts[2],
        84: spacing_x * factors[0], 85: spacing_y * factors[1],
        86: spacing_z * factors[2],
        87: (bounds.nx_min - 1.5) * spacing_x,
        88: (bounds.ny_min - 1.5) * spacing_y,
        89: -0.5 * spacing_z,
        90: 1.0e-5,
    }
    actual = _parameters(datfiles / "CTusrparam.dat")
    for number, value in expected.items():
        tolerance = 0 if number <= 83 else 5.1e-6  # CT2PHITS prints five decimals.
        if not math.isclose(actual[number], value, rel_tol=0, abs_tol=tolerance):
            raise CtVoxelVerificationError(f"CT lattice c{number} disagrees with source geometry")
    surface = " ".join((datfiles / "CTsurf.dat").read_text(encoding="utf-8").split()).lower()
    for fragment in (
        "5000 rpp c87 c87+c84 c88 c88+c85 c89 c89+c86",
        "97 rpp c87 c87+c81*c84 c88 c88+c82*c85 c89 c89+c83*c86",
        "98 500 rpp c87+c90 c87+c81*c84-c90 c88+c90 c88+c82*c85-c90 c89+c90 c89+c83*c86-c90",
    ):
        if fragment not in surface:
            raise CtVoxelVerificationError("CT surfaces do not use the verified lattice parameters")
    cell = " ".join((datfiles / "CTcell.dat").read_text(encoding="utf-8").split()).lower()
    if (f"fill= 0:{counts[0]-1} 0:{counts[1]-1} 0:{counts[2]-1}" not in cell
        or "5000 0 -5000 lat=1 u=5000" not in cell
        or "infl:{ctuniverse.inp}" not in cell
        or "infl:{ctvoxel.inp}" not in cell):
        raise CtVoxelVerificationError("CT cell fill does not match verified voxel counts")


def _expected_materials(
    source_files: Sequence[Path], bounds: ClipBounds,
    factors: tuple[int, int, int], thresholds: tuple[float, ...],
) -> Iterator[int]:
    nx, ny, nz = coarse_coverage(bounds, factors).voxel_counts
    x0, y0 = bounds.nx_min - 1, bounds.ny_min - 1
    sx, sy, sz = factors
    for z in range(nz):
        sums = np.zeros((ny, nx), dtype=np.float64)
        for z_in_block in range(sz):
            path = source_files[bounds.first - 1 + z * sz + z_in_block]
            try:
                dataset = pydicom.dcmread(str(path))
                if (str(getattr(dataset, "PhotometricInterpretation", "")) != "MONOCHROME2"
                    or int(getattr(dataset, "SamplesPerPixel", 0)) != 1
                    or int(getattr(dataset, "NumberOfFrames", 1)) != 1
                    or int(getattr(dataset, "BitsAllocated", 0)) not in (8, 16)):
                    raise CtVoxelVerificationError("unsupported CT pixel encoding for material verification")
                pixels = dataset.pixel_array
                if pixels.ndim != 2 or pixels.dtype.kind not in "iu":
                    raise CtVoxelVerificationError("unsupported decoded CT pixels")
                slope = float(getattr(dataset, "RescaleSlope", 1))
                intercept = float(getattr(dataset, "RescaleIntercept", 0))
                if not math.isfinite(slope) or not math.isfinite(intercept):
                    raise CtVoxelVerificationError("non-finite CT rescale values")
            except CtVoxelVerificationError:
                raise
            except Exception as exc:
                raise CtVoxelVerificationError("cannot decode frozen CT pixels") from exc
            region = pixels[y0 : y0 + ny * sy, x0 : x0 + nx * sx]
            if region.shape != (ny * sy, nx * sx):
                raise CtVoxelVerificationError("decoded CT dimensions disagree with source geometry")
            # The installed reader stores rescaled HU in float32 before the
            # Fortran converter accumulates them in double precision.
            hu = (region.astype(np.float64) * slope + intercept).astype(np.float32)
            if not np.isfinite(hu).all():
                raise CtVoxelVerificationError("non-finite rescaled CT pixels")
            # Match the converter's Y-then-X traversal and per-pixel division.
            # A reduced sum can round differently at a material threshold.
            for y_in_block in range(sy):
                for x_in_block in range(sx):
                    sums += hu[y_in_block::sy, x_in_block::sx].astype(np.float64) / (sx * sy * sz)
        for hu in sums.flat:
            yield 5000 + max(1, bisect.bisect_right(thresholds, float(hu)))


def _iter_decoded_voxels(path: Path, voxel_count: int) -> Iterator[int]:
    emitted = 0
    previous: int | None = None
    try:
        with path.open("r", encoding="ascii") as stream:
            for line in stream:
                for token in line.split():
                    value = int(token)
                    if value >= 0:
                        previous = value
                        repeat = 1
                    elif value < 0 and previous is not None:
                        repeat = -value
                    else:
                        raise ValueError
                    if emitted + repeat > voxel_count:
                        raise ValueError
                    emitted += repeat
                    for _ in range(repeat):
                        yield previous
    except (ValueError, UnicodeError) as exc:
        raise CtVoxelVerificationError("invalid CT voxel material encoding") from exc
    if emitted != voxel_count:
        raise CtVoxelVerificationError("CT voxel material count disagrees with lattice")


def _decode_voxels(path: Path, voxel_count: int) -> list[int]:
    """Small-fixture convenience wrapper; production comparison is streamed."""
    return list(_iter_decoded_voxels(path, voxel_count))


def _iter_encoded_voxels(values: Iterator[int]) -> Iterator[int]:
    previous = None
    repeated = 0
    for value in values:
        if value == previous:
            repeated += 1
        else:
            if repeated:
                yield -repeated
            yield value
            previous = value
            repeated = 0
    if repeated:
        yield -repeated


def _write_voxels(path: Path, values: Iterator[int]) -> None:
    with path.open("w", encoding="ascii", newline="\n") as stream:
        encoded = _iter_encoded_voxels(values)
        while chunk := tuple(itertools.islice(encoded, 10)):
            stream.write("      " + "".join(f" {item:10d}" for item in chunk) + "\n")


def verify_and_correct_ct_voxels(
    *, datfiles_root: Path, table_path: Path, source_files: Sequence[Path],
    bounds: ClipBounds, factors: tuple[int, int, int],
) -> VoxelVerification:
    coverage = coarse_coverage(bounds, factors)
    counts = coverage.voxel_counts
    _verify_geometry(datfiles_root, source_files, bounds, factors, counts)
    table = _read_table(table_path)
    _verify_material_assets(datfiles_root, table)
    voxel_count = math.prod(counts)
    voxel_path = datfiles_root / "CTvoxel.dat"
    expected = _expected_materials(source_files, bounds, factors, table.thresholds)
    actual = _iter_decoded_voxels(voxel_path, voxel_count)
    mismatches = 0
    nx, ny, _nz = counts
    correct_y_source_limit = ny * factors[0]
    compared = 0
    for index, (a, b) in enumerate(itertools.zip_longest(actual, expected)):
        compared += 1
        if a is None or b is None:
            raise CtVoxelVerificationError("CT voxel material count disagrees with lattice")
        y = (index // nx) % ny
        known_defect_row = (
            factors[0] < factors[1]
            and (y + 1) * factors[1] > correct_y_source_limit
        )
        if (a < 5001 or a > 5000 + len(table.thresholds)) and not (a == 0 and known_defect_row):
            raise CtVoxelVerificationError("CT voxel output contains an unknown material ID")
        if a != b:
            mismatches += 1
            if factors[0] == factors[1]:
                raise CtVoxelVerificationError("CT2PHITS materials disagree with source CT")
            if not known_defect_row:
                raise CtVoxelVerificationError("CT2PHITS material mismatch outside known Y-count defect")
    if compared != voxel_count:
        raise CtVoxelVerificationError("CT voxel material count disagrees with lattice")
    if not mismatches:
        return VoxelVerification(voxel_count, 0, False)
    descriptor, name = tempfile.mkstemp(prefix="ctvoxel-verified-", suffix=".tmp", dir=datfiles_root)
    os.close(descriptor)
    candidate = Path(name)
    try:
        _write_voxels(candidate, _expected_materials(source_files, bounds, factors, table.thresholds))
        for index, (a, b) in enumerate(itertools.zip_longest(
            _iter_decoded_voxels(candidate, voxel_count),
            _expected_materials(source_files, bounds, factors, table.thresholds),
        )):
            if a != b:
                raise CtVoxelVerificationError(f"corrected CT voxel output failed at {index}")
        os.replace(candidate, voxel_path)
    finally:
        candidate.unlink(missing_ok=True)
    return VoxelVerification(voxel_count, mismatches, True)
